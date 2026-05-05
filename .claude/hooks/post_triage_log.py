#!/usr/bin/env python3
"""Append the latest Morning Triage output to email-runs/<DATE>.md.

Works as both PostToolUse and Stop hook:
  - PostToolUse: receives {session_id, tool_name, ...} — finds transcript via session_id
  - Stop:        receives {transcript_path, last_assistant_message, ...}
"""

from __future__ import annotations

import sys
from datetime import datetime

from _hook_common import (
    PROJECT_ROOT,
    debug_log,
    iter_assistant_messages,
    read_stdin_payload,
    resolve_transcript,
    should_run,
)

MARKER = "Morning Triage"
HOOK_NAME = "post-triage-log"


def main() -> int:
    payload = read_stdin_payload()
    transcript = resolve_transcript(payload)
    if not should_run(payload, hook_name=HOOK_NAME, transcript=transcript, assistant_marker=MARKER):
        return 0
    if transcript is None:
        return 0

    triage = payload.get("last_assistant_message", "") or ""
    if MARKER not in triage:
        triage = ""
        for blocks, _ in iter_assistant_messages(transcript):
            for text in blocks:
                if MARKER in text:
                    triage = text
    if not triage:
        debug_log(HOOK_NAME, "no triage content found — exiting")
        return 0

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")

    runs_dir = PROJECT_ROOT / "email-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    log_file = runs_dir / f"{date}.md"

    if not log_file.exists():
        log_file.write_text(f"# Email Triage — {date}\n")

    entry_header = f"## {time}"
    try:
        existing = log_file.read_text()
    except Exception:
        existing = ""
    if entry_header in existing:
        return 0

    with log_file.open("a") as fh:
        fh.write(f"\n{entry_header}\n\n{triage}\n")
    debug_log(HOOK_NAME, f"wrote {log_file} {entry_header}")
    print(f"Triage logged to {log_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
