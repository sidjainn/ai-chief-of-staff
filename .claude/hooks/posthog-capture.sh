#!/usr/bin/env bash
# posthog-capture.sh
# Sends a `triage_run` event to PostHog when /triage completes.
# Mirrors the transcript-resolution contract of post-triage-log.sh.
# Exits 0 silently when POSTHOG_API_KEY is unset or on any network failure — telemetry must never block the user.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/weekly-log.md"
SENT_LOG="$PROJECT_ROOT/logs/posthog-sent.log"
DEBUG_LOG="$PROJECT_ROOT/logs/hook-debug.log"
DATE=$(date +"%Y-%m-%d")
TIME=$(date +"%H:%M")
WEEK=$(date +"%Y-W%V")
DOW=$(date +"%A")

mkdir -p "$PROJECT_ROOT/logs"
log() { echo "[$(date '+%H:%M:%S')] [posthog] $*" >> "$DEBUG_LOG"; }

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

TRIAGE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    msg = d.get('last_assistant_message', '')
    if 'Morning Triage' in msg:
        print(msg)
except:
    pass
" 2>/dev/null || echo "")

if [ -z "$TRIAGE" ] && [ -f "$TRANSCRIPT" ]; then
    TRIAGE=$(python3 - "$TRANSCRIPT" <<'EOF'
import sys, json

transcript_path = sys.argv[1]
triage_content = None

try:
    with open(transcript_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                msg = entry.get('message', entry)
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                text = block.get('text', '')
                                if 'Morning Triage' in text:
                                    triage_content = text
                    elif isinstance(content, str) and 'Morning Triage' in content:
                        triage_content = content
            except:
                continue
except:
    pass

if triage_content:
    print(triage_content)
EOF
)
fi

if [ -z "$TRIAGE" ]; then
    exit 0
fi

# Idempotency: skip if we already sent an event for this triage (matched by the weekly-log entry header the other hook writes).
ENTRY_HEADER="### $DATE — $TIME"
SENT_KEY="$DATE $TIME"
if [ -f "$SENT_LOG" ] && grep -qF "$SENT_KEY" "$SENT_LOG"; then
    exit 0
fi

P0_COUNT=$(echo "$TRIAGE" | grep -cE '(^|[^A-Za-z])P0([^A-Za-z]|$)' || echo 0)
P1_COUNT=$(echo "$TRIAGE" | grep -cE '(^|[^A-Za-z])P1([^A-Za-z]|$)' || echo 0)
P2_COUNT=$(echo "$TRIAGE" | grep -cE '(^|[^A-Za-z])P2([^A-Za-z]|$)' || echo 0)
TRIAGE_CHARS=${#TRIAGE}

log "Capturing triage_run event (P0=$P0_COUNT P1=$P1_COUNT P2=$P2_COUNT chars=$TRIAGE_CHARS)"

export POSTHOG_API_KEY DISTINCT_ID P0_COUNT P1_COUNT P2_COUNT TRIAGE_CHARS DATE WEEK DOW
PAYLOAD=$(python3 -c "
import json, os
payload = {
    'api_key': os.environ['POSTHOG_API_KEY'],
    'event': 'triage_run',
    'distinct_id': os.environ['DISTINCT_ID'],
    'properties': {
        'p0_count': int(os.environ['P0_COUNT']),
        'p1_count': int(os.environ['P1_COUNT']),
        'p2_count': int(os.environ['P2_COUNT']),
        'triage_chars': int(os.environ['TRIAGE_CHARS']),
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
