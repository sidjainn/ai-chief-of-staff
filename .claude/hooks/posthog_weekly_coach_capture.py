#!/usr/bin/env python3
"""Send `weekly_coach_run` event to PostHog when /weekly-coach completes.

Detects invocation by scanning the transcript for /weekly-coach in user msgs.
Extracts metric counts from the latest section of logs/weekly-coach-log.md.
"""

from __future__ import annotations

import os
import re
import sys

from _hook_common import (
    PROJECT_ROOT,
    date_props,
    debug_log,
    idempotency_check,
    idempotency_record,
    iter_user_messages,
    load_project_env,
    posthog_capture,
    read_stdin_payload,
    resolve_transcript,
    should_run,
)

HOOK_NAME = "posthog-wc"
SENT_LOG = PROJECT_ROOT / "logs" / "posthog-weekly-coach-sent.log"
COACH_LOG = PROJECT_ROOT / "logs" / "weekly-coach-log.md"

CMD_REGEX = r"/weekly-coach\b"
ISO_RE = re.compile(r"\b(\d{4}-W\d{2})\b")


def _scan_iso_hint(transcript) -> tuple[bool, str]:
    seen = False
    iso_hint = ""
    for blocks in iter_user_messages(transcript):
        joined = "\n".join(blocks)
        if re.search(CMD_REGEX, joined, re.IGNORECASE):
            seen = True
            m = ISO_RE.search(joined)
            if m:
                iso_hint = m.group(1)
    return seen, iso_hint


def _parse_coach_log(path, hint_iso: str) -> dict:
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
        return result
    try:
        text = open(path).read()
    except Exception:
        return result

    sections = list(re.finditer(r"^## Week (\S+)\s+\u2014\s+coaching", text, flags=re.MULTILINE))
    if not sections:
        sections = list(re.finditer(r"^## Week (\S+)\s+(?:-|\u2014)\s+coaching", text, flags=re.MULTILINE))
    if not sections:
        return result

    last = sections[-1]
    result["iso_week"] = last.group(1)
    next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
    block_end = last.end() + next_header.start() if next_header else len(text)
    block = text[last.start():block_end]

    def grab_int(key: str) -> int:
        m = re.search(rf"{key}\s*:\s*(\d+)", block, flags=re.IGNORECASE)
        return int(m.group(1)) if m else 0

    def grab_string(key: str, max_len: int = 400) -> str:
        m = re.search(rf"{key}\s*:\s*(.+)", block, flags=re.IGNORECASE)
        if not m:
            return ""
        val = m.group(1).strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        return val[:max_len]

    def grab_ratio(key: str) -> tuple[int, int]:
        m = re.search(rf"{key}\s*:\s*(\d+)\s*/\s*(\d+)", block, flags=re.IGNORECASE)
        if m:
            return int(m.group(1)), int(m.group(2))
        return 0, 0

    def grab_list(key: str) -> list[str]:
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
    return result


def main() -> int:
    payload = read_stdin_payload()
    load_project_env()

    transcript = resolve_transcript(payload)
    if not should_run(payload, hook_name=HOOK_NAME, transcript=transcript, command_regex=CMD_REGEX):
        return 0
    if transcript is None:
        return 0

    seen, iso_hint = _scan_iso_hint(transcript)
    if not seen:
        return 0

    counts = _parse_coach_log(str(COACH_LOG), iso_hint)
    iso_week = counts.get("iso_week") or ""

    props_date = date_props()
    sent_key = f"{props_date['date']} weekly-coach {iso_week}"
    if idempotency_check(SENT_LOG, sent_key):
        return 0

    debug_log(
        HOOK_NAME,
        f"capturing weekly_coach_run iso={iso_week} items={counts.get('next_week_items')} "
        f"rolled={counts.get('rolled_over_items')} pillars={counts.get('pillars_served')}/"
        f"{counts.get('pillars_total')} at_risk={counts.get('pillars_at_risk_count')}",
    )

    ok = posthog_capture(
        "weekly_coach_run",
        {
            **props_date,
            "iso_week": iso_week or None,
            "next_week_items": int(counts.get("next_week_items") or 0),
            "rolled_over_items": int(counts.get("rolled_over_items") or 0),
            "pillars_served": int(counts.get("pillars_served") or 0),
            "pillars_total": int(counts.get("pillars_total") or 0),
            "pillars_at_risk_count": int(counts.get("pillars_at_risk_count") or 0),
            "pillars_at_risk": counts.get("pillars_at_risk") or [],
            "pillars_episodic_due_count": int(counts.get("pillars_episodic_due_count") or 0),
            "pillars_episodic_due": counts.get("pillars_episodic_due") or [],
            "top_question": counts.get("top_question") or None,
            "intent": counts.get("intent") or None,
        },
    )
    if ok:
        idempotency_record(SENT_LOG, sent_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
