#!/usr/bin/env bash
# posthog-weekly-coach-capture.sh
# Sends `weekly_coach_run` event to PostHog when /weekly-coach completes.
# Detects invocation by scanning transcript for the slash command in user messages.
# Extracts counts from logs/weekly-coach-log.md (latest week section).
# Mirrors transcript-resolution + idempotency contracts of posthog-job-research-capture.sh.
# Exits 0 silently when POSTHOG_API_KEY unset, no command detected, or any network failure.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SENT_LOG="$PROJECT_ROOT/logs/posthog-weekly-coach-sent.log"
DEBUG_LOG="$PROJECT_ROOT/logs/hook-debug.log"
COACH_LOG="$PROJECT_ROOT/logs/weekly-coach-log.md"
DATE=$(date +"%Y-%m-%d")
TIME=$(date +"%H:%M")
WEEK=$(date +"%Y-W%V")
DOW=$(date +"%A")

mkdir -p "$PROJECT_ROOT/logs"
log() { echo "[$(date '+%H:%M:%S')] [posthog-wc] $*" >> "$DEBUG_LOG"; }

if [ -z "$POSTHOG_API_KEY" ] && [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

if [ -z "$POSTHOG_API_KEY" ]; then
    exit 0
fi

POSTHOG_HOST="${POSTHOG_HOST:-https://us.posthog.com}"
DISTINCT_ID="${POSTHOG_DISTINCT_ID:-$(whoami)}"

INPUT=$(cat 2>/dev/null || true)

TRANSCRIPT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except:
    print('')
" 2>/dev/null || echo "")

if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', ''))
except:
    print('')
" 2>/dev/null || echo "")

    if [ -n "$SESSION_ID" ]; then
        TRANSCRIPT=$(find ~/.claude/projects -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
    fi
fi

if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    exit 0
fi

# Scan transcript for /weekly-coach invocation in user messages.
SCAN=$(python3 - "$TRANSCRIPT" <<'EOF'
import sys, json, re

transcript_path = sys.argv[1]
result = {
    "command_seen": False,
    "iso_week": None,
}

try:
    with open(transcript_path) as f:
        lines = f.readlines()
except:
    print(json.dumps(result))
    sys.exit(0)

cmd_re = re.compile(r"/weekly-coach\b", re.IGNORECASE)
iso_re = re.compile(r"\b(\d{4}-W\d{2})\b")

for line in lines:
    try:
        entry = json.loads(line.strip())
    except:
        continue
    msg = entry.get("message", entry)
    role = msg.get("role", "")
    content = msg.get("content", "")

    text_blocks = []
    if isinstance(content, str):
        text_blocks.append(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_blocks.append(block.get("text", ""))

    joined = "\n".join(text_blocks)

    if role == "user" and cmd_re.search(joined):
        result["command_seen"] = True
        m = iso_re.search(joined)
        if m:
            result["iso_week"] = m.group(1)

print(json.dumps(result))
EOF
)

CMD_SEEN=$(echo "$SCAN" | python3 -c "import sys, json; print('true' if json.load(sys.stdin).get('command_seen') else 'false')")
SCANNED_ISO=$(echo "$SCAN" | python3 -c "import sys, json; print(json.load(sys.stdin).get('iso_week') or '')")

if [ "$CMD_SEEN" != "true" ]; then
    exit 0
fi

# Parse latest week section from logs/weekly-coach-log.md to extract counts.
COUNTS=$(python3 - "$COACH_LOG" "$SCANNED_ISO" <<'EOF'
import sys, os, re, json

path = sys.argv[1]
hint_iso = sys.argv[2] if len(sys.argv) > 2 else ""
result = {
    "iso_week": hint_iso or "",
    "patterns_count": 0,
    "next_week_items": 0,
    "charter_areas_covered": 0,
    "avoidance_items": 0,
    "breakthroughs": 0,
    "intent": "",
}

if not os.path.exists(path):
    print(json.dumps(result))
    sys.exit(0)

try:
    with open(path) as f:
        text = f.read()
except:
    print(json.dumps(result))
    sys.exit(0)

# Find all "## Week <ISO> — coaching" sections; pick the last.
sections = list(re.finditer(r"^## Week (\S+)\s+\u2014\s+coaching", text, flags=re.MULTILINE))
if not sections:
    sections = list(re.finditer(r"^## Week (\S+)\s+(?:-|\u2014)\s+coaching", text, flags=re.MULTILINE))

if not sections:
    print(json.dumps(result))
    sys.exit(0)

last = sections[-1]
result["iso_week"] = last.group(1)
start = last.start()
end = sections[-1].end() if len(sections) == 1 else len(text)
# block = from this section header to next section header
next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
block_end = last.end() + next_header.start() if next_header else len(text)
block = text[start:block_end]

def grab_int(key):
    m = re.search(rf"{key}\s*:\s*(\d+)", block, flags=re.IGNORECASE)
    return int(m.group(1)) if m else 0

def grab_intent():
    m = re.search(r"intent\s*:\s*(.+)", block, flags=re.IGNORECASE)
    return m.group(1).strip()[:200] if m else ""

def grab_ratio(key):
    m = re.search(rf"{key}\s*:\s*(\d+)\s*/\s*(\d+)", block, flags=re.IGNORECASE)
    return int(m.group(1)) if m else grab_int(key)

result["patterns_count"] = grab_int("patterns_count")
result["next_week_items"] = grab_int("next_week_items")
result["charter_areas_covered"] = grab_ratio("charter_areas_covered")
result["avoidance_items"] = grab_int("avoidance_items")
result["breakthroughs"] = grab_int("breakthroughs")
result["intent"] = grab_intent()

print(json.dumps(result))
EOF
)

ISO_WEEK=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('iso_week') or '')")
PATTERNS_COUNT=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('patterns_count') or 0)")
NEXT_WEEK_ITEMS=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('next_week_items') or 0)")
CHARTER_AREAS=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('charter_areas_covered') or 0)")
AVOIDANCE_ITEMS=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('avoidance_items') or 0)")
BREAKTHROUGHS=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('breakthroughs') or 0)")
INTENT=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('intent') or '')")

# Idempotency: skip if (iso_week, date) already sent.
SENT_KEY="$DATE $TIME weekly-coach $ISO_WEEK"
if [ -f "$SENT_LOG" ] && grep -qF "$SENT_KEY" "$SENT_LOG"; then
    exit 0
fi

log "Capturing weekly_coach_run (iso=$ISO_WEEK patterns=$PATTERNS_COUNT items=$NEXT_WEEK_ITEMS)"

export POSTHOG_API_KEY DISTINCT_ID ISO_WEEK PATTERNS_COUNT NEXT_WEEK_ITEMS CHARTER_AREAS AVOIDANCE_ITEMS BREAKTHROUGHS INTENT DATE WEEK DOW
PAYLOAD=$(python3 -c "
import json, os
payload = {
    'api_key': os.environ['POSTHOG_API_KEY'],
    'event': 'weekly_coach_run',
    'distinct_id': os.environ['DISTINCT_ID'],
    'properties': {
        'iso_week': os.environ['ISO_WEEK'] or None,
        'patterns_count': int(os.environ['PATTERNS_COUNT']),
        'next_week_items': int(os.environ['NEXT_WEEK_ITEMS']),
        'charter_areas_covered': int(os.environ['CHARTER_AREAS']),
        'avoidance_items': int(os.environ['AVOIDANCE_ITEMS']),
        'breakthroughs': int(os.environ['BREAKTHROUGHS']),
        'intent': os.environ['INTENT'] or None,
        'date': os.environ['DATE'],
        'week': os.environ['WEEK'],
        'day_of_week': os.environ['DOW'],
        'source': 'claude-code-hook',
    },
}
print(json.dumps(payload))
")

RESPONSE=$(curl -fsS --max-time 5 \
    -H "Content-Type: application/json" \
    -X POST \
    -d "$PAYLOAD" \
    "${POSTHOG_HOST}/i/v0/e/" 2>&1) || {
    log "curl failed: $RESPONSE"
    exit 0
}

log "PostHog response: $RESPONSE"
echo "$SENT_KEY" >> "$SENT_LOG"
