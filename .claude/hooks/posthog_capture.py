#!/usr/bin/env python3
"""Send a `triage_run` event to PostHog when /email-triage completes.

Mirrors the transcript-resolution + idempotency contracts of post_triage_log.py.
Exits 0 silently on missing API key or any failure — telemetry must never block.
"""

from __future__ import annotations

import re
import sys

from _hook_common import (
    PROJECT_ROOT,
    date_props,
    debug_log,
    idempotency_check,
    idempotency_record,
    iter_assistant_messages,
    load_project_env,
    posthog_capture,
    read_stdin_payload,
    resolve_transcript,
    should_run,
)

MARKER = "Morning Triage"
HOOK_NAME = "posthog-triage"
SENT_LOG = PROJECT_ROOT / "logs" / "posthog-email-triage-sent.log"


def _count_marker(text: str, label: str) -> int:
    return len(re.findall(rf"(?:^|[^A-Za-z]){re.escape(label)}(?:[^A-Za-z]|$)", text))


def main() -> int:
    payload = read_stdin_payload()
    load_project_env()

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
        return 0

    props = date_props()
    key = f"{props['date']} {props['time']}"
    if idempotency_check(SENT_LOG, key):
        return 0

    p0 = _count_marker(triage, "P0")
    p1 = _count_marker(triage, "P1")
    p2 = _count_marker(triage, "P2")

    debug_log(HOOK_NAME, f"capturing triage_run P0={p0} P1={p1} P2={p2} chars={len(triage)}")

    ok = posthog_capture(
        "triage_run",
        {
            **props,
            "p0_count": p0,
            "p1_count": p1,
            "p2_count": p2,
            "triage_chars": len(triage),
        },
    )
    if ok:
        idempotency_record(SENT_LOG, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
