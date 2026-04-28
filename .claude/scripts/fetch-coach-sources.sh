#!/usr/bin/env bash
# fetch-coach-sources.sh
# Pulls weekly-coach source data via public Google export endpoints.
# Requires: docs shared "anyone with the link can view".
# Outputs to a timestamped dir and prints a manifest path on stdout.
#
# Sources:
#   1. Charter doc (text export)
#   2. Weekly sheet (per-tab CSV exports)
#   3. Daily-log monthly docs in folder (text exports)
#
# Usage: bash fetch-coach-sources.sh [--out <dir>]
#   --out  override output dir (default: /tmp/weekly-coach/<UTC ISO ts>)

set -euo pipefail

# Load doc IDs from project .env (gitignored).
# Required vars:
#   WEEKLY_COACH_CHARTER_DOC_ID
#   WEEKLY_COACH_SHEET_ID
#   WEEKLY_COACH_DAILY_LOG_FOLDER_ID
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

CHARTER_DOC_ID="${WEEKLY_COACH_CHARTER_DOC_ID:-}"
WEEKLY_SHEET_ID="${WEEKLY_COACH_SHEET_ID:-}"
DAILY_LOG_FOLDER_ID="${WEEKLY_COACH_DAILY_LOG_FOLDER_ID:-}"

if [ -z "$CHARTER_DOC_ID" ] || [ -z "$WEEKLY_SHEET_ID" ] || [ -z "$DAILY_LOG_FOLDER_ID" ]; then
    echo "[fetch-coach] ERROR: missing one or more of WEEKLY_COACH_CHARTER_DOC_ID / WEEKLY_COACH_SHEET_ID / WEEKLY_COACH_DAILY_LOG_FOLDER_ID. Set them in .env." >&2
    exit 1
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
NOW=$(date -u +"%Y%m%dT%H%M%SZ")
OUT_DIR="/tmp/weekly-coach/${NOW}"

while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT_DIR="$2"; shift 2;;
        *) echo "unknown arg: $1" >&2; exit 2;;
    esac
done

mkdir -p "$OUT_DIR/sheet" "$OUT_DIR/daily"

log() { echo "[fetch-coach] $*" >&2; }

fetch() {
    local url="$1" out="$2"
    curl -sLf -A "$UA" -m 30 "$url" -o "$out" || { log "FAIL: $url"; return 1; }
}

# 1. Charter
log "Charter doc → charter.txt"
fetch "https://docs.google.com/document/d/${CHARTER_DOC_ID}/export?format=txt" "$OUT_DIR/charter.txt" || true

# 2. Sheet — discover tabs via htmlview, then export each as CSV
log "Sheet htmlview → tab discovery"
fetch "https://docs.google.com/spreadsheets/d/${WEEKLY_SHEET_ID}/htmlview" "$OUT_DIR/sheet/_htmlview.html" || true

python3 - "$OUT_DIR" "$WEEKLY_SHEET_ID" "$UA" <<'PY'
import os, re, sys, json, urllib.request

out_dir, sheet_id, ua = sys.argv[1], sys.argv[2], sys.argv[3]
html_path = os.path.join(out_dir, "sheet", "_htmlview.html")
tabs_index = []

if os.path.exists(html_path):
    h = open(html_path).read()
    # Pairs of "name":"...", ... "gid":"..."
    pairs = re.findall(
        r'(?:"name"|name)\s*:\s*"([^"]+)"[^}]{0,200}?(?:"gid"|gid)\s*:\s*"?(\d+)',
        h,
    )
    seen = set()
    for name, gid in pairs:
        if gid in seen:
            continue
        seen.add(gid)
        tabs_index.append({"name": name, "gid": gid})

# fetch each tab as CSV
fetched = []
for t in tabs_index:
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', t["name"])[:80]
    fname = f"{safe}__{t['gid']}.csv"
    path = os.path.join(out_dir, "sheet", fname)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={t['gid']}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        fetched.append({"name": t["name"], "gid": t["gid"], "path": path, "bytes": len(data)})
    except Exception as e:
        fetched.append({"name": t["name"], "gid": t["gid"], "path": None, "error": str(e)})

with open(os.path.join(out_dir, "sheet", "_tabs.json"), "w") as f:
    json.dump(fetched, f, indent=2)
print(f"[fetch-coach] sheet tabs fetched: {sum(1 for t in fetched if t.get('path'))}/{len(fetched)}", file=sys.stderr)
PY

# 3. Daily log folder — discover docs via embeddedfolderview
log "Daily-log folder → embeddedfolderview"
fetch "https://drive.google.com/embeddedfolderview?id=${DAILY_LOG_FOLDER_ID}#list" "$OUT_DIR/daily/_folder.html" || true

python3 - "$OUT_DIR" "$UA" <<'PY'
import os, re, sys, json, urllib.request

out_dir, ua = sys.argv[1], sys.argv[2]
folder_html = os.path.join(out_dir, "daily", "_folder.html")
entries = []

if os.path.exists(folder_html):
    h = open(folder_html).read()
    # entry-<docid> ... <div class="...flip-entry-title...">title</div>
    matches = re.findall(
        r'id="entry-([a-zA-Z0-9_-]{20,})"[\s\S]*?<div[^>]*flip-entry-title[^>]*>([\s\S]*?)</div>',
        h,
    )
    for fid, title in matches:
        clean = re.sub(r'<[^>]+>', '', title).strip()
        entries.append({"id": fid, "title": clean})

# fetch each doc as text
fetched = []
for e in entries:
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', e["title"])[:80]
    fname = f"{safe}__{e['id'][:12]}.txt"
    path = os.path.join(out_dir, "daily", fname)
    url = f"https://docs.google.com/document/d/{e['id']}/export?format=txt"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        fetched.append({"title": e["title"], "id": e["id"], "path": path, "bytes": len(data)})
    except Exception as ex:
        fetched.append({"title": e["title"], "id": e["id"], "path": None, "error": str(ex)})

with open(os.path.join(out_dir, "daily", "_docs.json"), "w") as f:
    json.dump(fetched, f, indent=2)
print(f"[fetch-coach] daily-log docs fetched: {sum(1 for d in fetched if d.get('path'))}/{len(fetched)}", file=sys.stderr)
PY

# 4. Manifest
python3 - "$OUT_DIR" "$CHARTER_DOC_ID" "$WEEKLY_SHEET_ID" "$DAILY_LOG_FOLDER_ID" <<'PY'
import os, sys, json
out_dir, charter_id, sheet_id, folder_id = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
charter_path = os.path.join(out_dir, "charter.txt")
manifest = {
    "out_dir": out_dir,
    "charter": {
        "doc_id": charter_id,
        "path": charter_path if os.path.exists(charter_path) else None,
        "bytes": os.path.getsize(charter_path) if os.path.exists(charter_path) else 0,
    },
    "sheet": {
        "sheet_id": sheet_id,
        "tabs_json": os.path.join(out_dir, "sheet", "_tabs.json"),
    },
    "daily": {
        "folder_id": folder_id,
        "docs_json": os.path.join(out_dir, "daily", "_docs.json"),
    },
}
mpath = os.path.join(out_dir, "manifest.json")
with open(mpath, "w") as f:
    json.dump(manifest, f, indent=2)
print(mpath)
PY
