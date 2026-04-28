#!/usr/bin/env bash
# posthog-job-research-capture.sh
# Sends `job_research_run` or `job_research_update` event to PostHog when /research-job or /update-job completes.
# Detects invocation by scanning transcript for the slash command in user messages.
# Mirrors transcript-resolution + idempotency contracts of posthog-capture.sh.
# Exits 0 silently when POSTHOG_API_KEY unset, no command detected, or any network failure — telemetry must never block user.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SENT_LOG="$PROJECT_ROOT/logs/posthog-job-research-sent.log"
DEBUG_LOG="$PROJECT_ROOT/logs/hook-debug.log"
DATE=$(date +"%Y-%m-%d")
TIME=$(date +"%H:%M")
WEEK=$(date +"%Y-W%V")
DOW=$(date +"%A")
TS=$(date +"%s")

mkdir -p "$PROJECT_ROOT/logs"
log() { echo "[$(date '+%H:%M:%S')] [posthog-jr] $*" >> "$DEBUG_LOG"; }

# Project-local .env wins over inherited shell env (PostHog Code wrapper sets its own pha_ key
# that routes to a different project). Always source if present.
if [ -f "$PROJECT_ROOT/.env" ]; then
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

# Scan transcript for /research-job or /update-job invocation in user messages.
# Capture: command type, slug (from input or extracted from `jobs/<slug>/` path mentions in assistant output),
# subagent dispatch count, README state (created vs appended).
SCAN=$(python3 - "$TRANSCRIPT" <<'EOF'
import sys, json, re

transcript_path = sys.argv[1]
result = {
    "command": None,
    "slug": None,
    "subagent_count": 0,
    "readme_created": False,
    "readme_appended": False,
    "user_input": "",
}

try:
    with open(transcript_path) as f:
        lines = f.readlines()
except:
    print(json.dumps(result))
    sys.exit(0)

slug_path_re = re.compile(r"jobs/([a-z0-9][a-z0-9\-]*)/")
research_cmd_re = re.compile(r"/research-job\b", re.IGNORECASE)
update_cmd_re = re.compile(r"/update-job\b", re.IGNORECASE)

slug_candidates = []
subagent_dispatches = 0
last_user_after_cmd = ""
seen_cmd = False

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
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_blocks.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name == "Agent":
                        subagent_dispatches += 1

    joined = "\n".join(text_blocks)

    if role == "user":
        if research_cmd_re.search(joined):
            result["command"] = "research-job"
            seen_cmd = True
            last_user_after_cmd = joined
        elif update_cmd_re.search(joined):
            result["command"] = "update-job"
            seen_cmd = True
            last_user_after_cmd = joined

    for m in slug_path_re.finditer(joined):
        candidate = m.group(1)
        if candidate not in ("me",):
            slug_candidates.append(candidate)

    if role == "assistant" and seen_cmd:
        if "creating jobs/" in joined.lower() or "create jobs/" in joined.lower() or "created folder" in joined.lower():
            result["readme_created"] = True
        if "## update —" in joined.lower() or "appending" in joined.lower() or "appended a dated" in joined.lower():
            result["readme_appended"] = True

if seen_cmd and slug_candidates:
    from collections import Counter
    result["slug"] = Counter(slug_candidates).most_common(1)[0][0]

result["subagent_count"] = subagent_dispatches
result["user_input"] = last_user_after_cmd[:500]

print(json.dumps(result))
EOF
)

COMMAND=$(echo "$SCAN" | python3 -c "import sys, json; print(json.load(sys.stdin).get('command') or '')")
SLUG=$(echo "$SCAN" | python3 -c "import sys, json; print(json.load(sys.stdin).get('slug') or '')")
SUBAGENT_COUNT=$(echo "$SCAN" | python3 -c "import sys, json; print(json.load(sys.stdin).get('subagent_count') or 0)")
README_CREATED=$(echo "$SCAN" | python3 -c "import sys, json; print('true' if json.load(sys.stdin).get('readme_created') else 'false')")
README_APPENDED=$(echo "$SCAN" | python3 -c "import sys, json; print('true' if json.load(sys.stdin).get('readme_appended') else 'false')")

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Idempotency: skip if same (command, slug, date, time-bucket) already sent.
SENT_KEY="$DATE $TIME $COMMAND $SLUG"
if [ -f "$SENT_LOG" ] && grep -qF "$SENT_KEY" "$SENT_LOG"; then
    exit 0
fi

EVENT_NAME="job_research_run"
if [ "$COMMAND" = "update-job" ]; then
    EVENT_NAME="job_research_update"
fi

log "Capturing $EVENT_NAME (slug=$SLUG subagents=$SUBAGENT_COUNT created=$README_CREATED appended=$README_APPENDED)"

export POSTHOG_API_KEY DISTINCT_ID EVENT_NAME COMMAND SLUG SUBAGENT_COUNT README_CREATED README_APPENDED DATE WEEK DOW
PAYLOAD=$(python3 -c "
import json, os
payload = {
    'api_key': os.environ['POSTHOG_API_KEY'],
    'event': os.environ['EVENT_NAME'],
    'distinct_id': os.environ['DISTINCT_ID'],
    'properties': {
        'command': os.environ['COMMAND'],
        'company_slug': os.environ['SLUG'] or None,
        'subagent_count': int(os.environ['SUBAGENT_COUNT']),
        'readme_created': os.environ['README_CREATED'] == 'true',
        'readme_appended': os.environ['README_APPENDED'] == 'true',
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
