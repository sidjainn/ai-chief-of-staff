#!/usr/bin/env python3
"""Send `weekly_coach_run` event to PostHog when /weekly-coach completes.

Detects invocation by scanning the transcript for /weekly-coach in user msgs.
Extracts metric counts from the latest section of maps/weekly-coach-log.md.
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
COACH_LOG = PROJECT_ROOT / "maps" / "weekly-coach-log.md"

CMD_REGEX = r"/weekly-coach\b"


def _scan_invoked(transcript) -> bool:
    for blocks in iter_user_messages(transcript):
        if re.search(CMD_REGEX, "\n".join(blocks), re.IGNORECASE):
            return True
    return False


def _parse_coach_log(path) -> dict | None:
    """Return the latest coaching block's metrics, or None if none is parseable.

    None means "no data" — the caller must not emit. maps/weekly-coach-log.md is
    a symlink into a private repo, so an unreadable file is a real possibility;
    guessing an iso_week and shipping zeros pollutes the event stream.
    """
    result = {
        "iso_week": "",
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
        # NEW (skill 1.4) — additive fields; absent in pre-1.4 log blocks → defaults stand
        "state": "",
        "intervention_acted": 0,
        "intervention_total": 0,
        "interference_top": "",
        "chronic_in_immunity_map": 0,
    }
    if not os.path.exists(path):
        return None
    try:
        text = open(path).read()
    except Exception:
        return None

    sections = list(re.finditer(r"^## Week (\S+)\s+\u2014\s+coaching", text, flags=re.MULTILINE))
    if not sections:
        sections = list(re.finditer(r"^## Week (\S+)\s+(?:-|\u2014)\s+coaching", text, flags=re.MULTILINE))
    if not sections:
        return None

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
    # NEW (skill 1.4) — additive; pre-1.4 blocks lack these keys → defaults (0 / "") stand
    result["state"] = grab_string("state", 50)
    acted, total = grab_ratio("intervention_hit_rate")
    result["intervention_acted"] = acted
    result["intervention_total"] = total
    result["interference_top"] = grab_string("interference_top", 50)
    result["chronic_in_immunity_map"] = grab_int("chronic_in_immunity_map")
    return result


def main() -> int:
    payload = read_stdin_payload()
    load_project_env()

    transcript = resolve_transcript(payload)
    if not should_run(payload, hook_name=HOOK_NAME, transcript=transcript, command_regex=CMD_REGEX):
        return 0
    if transcript is None:
        return 0

    if not _scan_invoked(transcript):
        return 0

    counts = _parse_coach_log(str(COACH_LOG))
    if counts is None:
        debug_log(HOOK_NAME, "no parseable coaching block — skipping")
        return 0
    iso_week = counts["iso_week"]

    # Key on iso_week alone. The hook fires many times across a single run, and
    # the coach log — which supplies iso_week — is rewritten partway through it.
    # A dated key therefore changed mid-run and let the same run emit twice:
    # once carrying last week's block, once carrying this week's.
    props_date = date_props()
    sent_key = f"weekly-coach {iso_week}"
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
            # NEW (skill 1.4)
            "state": counts.get("state") or None,
            "intervention_acted": int(counts.get("intervention_acted") or 0),
            "intervention_total": int(counts.get("intervention_total") or 0),
            "intervention_hit_rate": (
                round(int(counts.get("intervention_acted") or 0) / int(counts.get("intervention_total") or 0), 3)
                if int(counts.get("intervention_total") or 0) > 0
                else None
            ),
            "interference_top": counts.get("interference_top") or None,
            "chronic_in_immunity_map": int(counts.get("chronic_in_immunity_map") or 0),
        },
    )
    if ok:
        idempotency_record(SENT_LOG, sent_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
