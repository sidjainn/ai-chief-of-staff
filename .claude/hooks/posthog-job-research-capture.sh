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


def extract_text_blocks(content):
    blocks = []
    if isinstance(content, str):
        blocks.append(content)
    elif isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                blocks.append(b.get("text", ""))
    return blocks


entries = []
for line in lines:
    try:
        entries.append(json.loads(line.strip()))
    except:
        entries.append(None)

# Pass 1: locate the *last* user message containing /research-job or /update-job.
# Tallies must scope to this command's segment only — otherwise prior /research-job
# subagent dispatches and slug mentions leak into a later /update-job event.
cmd_idx = -1
cmd_type = None
cmd_text = ""
for i, entry in enumerate(entries):
    if entry is None:
        continue
    msg = entry.get("message", entry)
    if msg.get("role") != "user":
        continue
    joined = "\n".join(extract_text_blocks(msg.get("content", "")))
    if research_cmd_re.search(joined):
        cmd_idx, cmd_type, cmd_text = i, "research-job", joined
    elif update_cmd_re.search(joined):
        cmd_idx, cmd_type, cmd_text = i, "update-job", joined

if cmd_idx < 0:
    print(json.dumps(result))
    sys.exit(0)

result["command"] = cmd_type
result["user_input"] = cmd_text[:500]

# Pass 2: tally only entries from the command line onward.
slug_candidates = []
subagent_dispatches = 0
for entry in entries[cmd_idx:]:
    if entry is None:
        continue
    msg = entry.get("message", entry)
    role = msg.get("role", "")
    content = msg.get("content", "")

    text_blocks = []
    if isinstance(content, str):
        text_blocks.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_blocks.append(block.get("text", ""))
            elif block.get("type") == "tool_use" and block.get("name") == "Agent":
                subagent_dispatches += 1

    joined = "\n".join(text_blocks)

    for m in slug_path_re.finditer(joined):
        candidate = m.group(1)
        if candidate != "me":
            slug_candidates.append(candidate)

    if role == "assistant":
        low = joined.lower()
        if "creating jobs/" in low or "create jobs/" in low or "created folder" in low:
            result["readme_created"] = True
        if "## update —" in low or "appending" in low or "appended a dated" in low:
            result["readme_appended"] = True

if slug_candidates:
    from collections import Counter
    result["slug"] = Counter(slug_candidates).most_common(1)[0][0]

result["subagent_count"] = subagent_dispatches

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
