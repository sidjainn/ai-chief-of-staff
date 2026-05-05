#!/usr/bin/env bash
# Tests the embedded SCAN python in posthog-job-research-capture.sh by
# extracting the heredoc into a temp file and running it against a fixture
# transcript that exercises two /research-job invocations.
#
# Expectations after the fix:
#   - command       == "research-job"     (last command)
#   - slug          == "company-b"        (only mentions in run B's segment)
#   - subagent_count == 1                 (only run B's Agent dispatch)
#
# Pre-fix this would report subagent_count=4 and could pick "company-a".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/../posthog-job-research-capture.sh"
FIXTURE="$SCRIPT_DIR/fixtures/multi-command-transcript.jsonl"

if [ ! -f "$HOOK" ]; then
    echo "FAIL hook not found: $HOOK" >&2
    exit 1
fi
if [ ! -f "$FIXTURE" ]; then
    echo "FAIL fixture not found: $FIXTURE" >&2
    exit 1
fi

TMP_PY=$(mktemp -t job_research_scan.XXXXXX.py)
trap 'rm -f "$TMP_PY"' EXIT

awk '
    /^SCAN=\$\(python3 - "\$TRANSCRIPT" <<'\''EOF'\''$/ { in_block=1; next }
    in_block && /^EOF$/ { in_block=0; next }
    in_block { print }
' "$HOOK" > "$TMP_PY"

if [ ! -s "$TMP_PY" ]; then
    echo "FAIL could not extract SCAN python heredoc from $HOOK" >&2
    exit 1
fi

OUT=$(python3 "$TMP_PY" "$FIXTURE")

CMD=$(echo "$OUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('command') or '')")
SLUG=$(echo "$OUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('slug') or '')")
SUBA=$(echo "$OUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('subagent_count') or 0)")

FAIL=0
[ "$CMD" = "research-job" ] || { echo "FAIL command: got '$CMD' want 'research-job'" >&2; FAIL=1; }
[ "$SLUG" = "company-b" ]   || { echo "FAIL slug: got '$SLUG' want 'company-b'" >&2; FAIL=1; }
[ "$SUBA" = "1" ]           || { echo "FAIL subagent_count: got '$SUBA' want 1" >&2; FAIL=1; }

if [ "$FAIL" -ne 0 ]; then
    echo "Scan output: $OUT" >&2
    exit 1
fi

echo "PASS subagent_count=$SUBA slug=$SLUG command=$CMD"
