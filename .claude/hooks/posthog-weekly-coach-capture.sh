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
    "next_week_items": 0,
    "rolled_over_items": 0,
    "pillars_served": 0,
    "pillars_total": 0,
    "pillars_at_risk_count": 0,
    "pillars_at_risk": [],
    "pillars_episodic_due_count": 0,
    "pillars_episodic_due": [],
    "top_question": "",
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
# block = from this section header to next section header
next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
block_end = last.end() + next_header.start() if next_header else len(text)
block = text[last.start():block_end]

def grab_int(key):
    m = re.search(rf"{key}\s*:\s*(\d+)", block, flags=re.IGNORECASE)
    return int(m.group(1)) if m else 0

def grab_string(key, max_len=400):
    # Stop at end of line; strip surrounding quotes.
    m = re.search(rf"{key}\s*:\s*(.+)", block, flags=re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1).strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return val[:max_len]

def grab_ratio(key):
    m = re.search(rf"{key}\s*:\s*(\d+)\s*/\s*(\d+)", block, flags=re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0

def grab_list(key):
    # Match `key: [a, b, c]` — capture inside brackets, split on commas.
    m = re.search(rf"{key}\s*:\s*\[([^\]]*)\]", block, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    items = [x.strip().strip('"').strip("'") for x in raw.split(",")]
    return [x for x in items if x]

result["next_week_items"] = grab_int("next_week_items")
result["rolled_over_items"] = grab_int("rolled_over_items")
served, total = grab_ratio("pillars_served")
result["pillars_served"] = served
result["pillars_total"] = total
at_risk = grab_list("pillars_at_risk")
result["pillars_at_risk"] = at_risk
result["pillars_at_risk_count"] = len(at_risk)
ep_due = grab_list("pillars_episodic_due")
result["pillars_episodic_due"] = ep_due
result["pillars_episodic_due_count"] = len(ep_due)
result["top_question"] = grab_string("top_question")
result["intent"] = grab_string("intent", 200)

print(json.dumps(result))
EOF
)

ISO_WEEK=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('iso_week') or '')")
NEXT_WEEK_ITEMS=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('next_week_items') or 0)")
ROLLED_OVER_ITEMS=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('rolled_over_items') or 0)")
PILLARS_SERVED=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('pillars_served') or 0)")
PILLARS_TOTAL=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('pillars_total') or 0)")
PILLARS_AT_RISK_COUNT=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('pillars_at_risk_count') or 0)")
PILLARS_EPISODIC_DUE_COUNT=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('pillars_episodic_due_count') or 0)")
TOP_QUESTION=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('top_question') or '')")
INTENT=$(echo "$COUNTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('intent') or '')")

# Idempotency: skip if (iso_week, date) already sent.
SENT_KEY="$DATE $TIME weekly-coach $ISO_WEEK"
if [ -f "$SENT_LOG" ] && grep -qF "$SENT_KEY" "$SENT_LOG"; then
    exit 0
fi

log "Capturing weekly_coach_run (iso=$ISO_WEEK items=$NEXT_WEEK_ITEMS rolled=$ROLLED_OVER_ITEMS pillars=$PILLARS_SERVED/$PILLARS_TOTAL at_risk=$PILLARS_AT_RISK_COUNT)"

export POSTHOG_API_KEY DISTINCT_ID ISO_WEEK NEXT_WEEK_ITEMS ROLLED_OVER_ITEMS PILLARS_SERVED PILLARS_TOTAL PILLARS_AT_RISK_COUNT PILLARS_EPISODIC_DUE_COUNT TOP_QUESTION INTENT DATE WEEK DOW COUNTS
PAYLOAD=$(python3 -c "
import json, os
counts = json.loads(os.environ.get('COUNTS') or '{}')
payload = {
    'api_key': os.environ['POSTHOG_API_KEY'],
    'event': 'weekly_coach_run',
    'distinct_id': os.environ['DISTINCT_ID'],
    'properties': {
        'iso_week': os.environ['ISO_WEEK'] or None,
        'next_week_items': int(os.environ['NEXT_WEEK_ITEMS']),
        'rolled_over_items': int(os.environ['ROLLED_OVER_ITEMS']),
        'pillars_served': int(os.environ['PILLARS_SERVED']),
        'pillars_total': int(os.environ['PILLARS_TOTAL']),
        'pillars_at_risk_count': int(os.environ['PILLARS_AT_RISK_COUNT']),
        'pillars_at_risk': counts.get('pillars_at_risk') or [],
        'pillars_episodic_due_count': int(os.environ['PILLARS_EPISODIC_DUE_COUNT']),
        'pillars_episodic_due': counts.get('pillars_episodic_due') or [],
        'top_question': os.environ['TOP_QUESTION'] or None,
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
