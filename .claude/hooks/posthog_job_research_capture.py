#!/usr/bin/env python3
"""Send `job_research_run` or `job_research_update` event when /job-research
or /update-job completes.

Detects invocation by scanning the transcript for the slash command in user
messages, then tallies subagent dispatches and slug mentions ONLY in the
segment after the most recent command — a previous /job-research's tally must
not leak into a later /update-job event (commit 3b62c5b).
"""

from __future__ import annotations

import re
import sys
from collections import Counter

from _hook_common import (
    PROJECT_ROOT,
    date_props,
    debug_log,
    idempotency_check,
    idempotency_record,
    load_project_env,
    parse_transcript,
    posthog_capture,
    read_stdin_payload,
    resolve_transcript,
    should_run,
)

HOOK_NAME = "posthog-jr"
SENT_LOG = PROJECT_ROOT / "logs" / "posthog-job-research-sent.log"

CMD_REGEX = r"/(?:job-research|update-job)\b"
SLUG_PATH_RE = re.compile(r"jobs/([a-z0-9][a-z0-9\-]*)/")
RESEARCH_RE = re.compile(r"/job-research\b", re.IGNORECASE)
UPDATE_RE = re.compile(r"/update-job\b", re.IGNORECASE)


def _text_blocks(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return []


def _scan(entries: list[dict]) -> dict:
    result = {
        "command": None,
        "slug": None,
        "subagent_count": 0,
        "readme_created": False,
        "readme_appended": False,
        "user_input": "",
    }

    cmd_idx = -1
    cmd_type = None
    cmd_text = ""
    for i, msg in enumerate(entries):
        if msg.get("role") != "user":
            continue
        joined = "\n".join(_text_blocks(msg.get("content", "")))
        if RESEARCH_RE.search(joined):
            cmd_idx, cmd_type, cmd_text = i, "job-research", joined
        elif UPDATE_RE.search(joined):
            cmd_idx, cmd_type, cmd_text = i, "update-job", joined

    if cmd_idx < 0:
        return result

    result["command"] = cmd_type
    result["user_input"] = cmd_text[:500]

    slug_candidates: list[str] = []
    subagent_dispatches = 0
    for msg in entries[cmd_idx:]:
        role = msg.get("role", "")
        content = msg.get("content", "")

        text_blocks: list[str] = []
        if isinstance(content, str):
            text_blocks.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_blocks.append(block.get("text", "") or "")
                elif block.get("type") == "tool_use" and block.get("name") == "Agent":
                    subagent_dispatches += 1

        joined = "\n".join(text_blocks)

        for m in SLUG_PATH_RE.finditer(joined):
            cand = m.group(1)
            if cand != "me":
                slug_candidates.append(cand)

        if role == "assistant":
            low = joined.lower()
            if "creating jobs/" in low or "create jobs/" in low or "created folder" in low:
                result["readme_created"] = True
            if "## update —" in low or "appending" in low or "appended a dated" in low:
                result["readme_appended"] = True

    if slug_candidates:
        result["slug"] = Counter(slug_candidates).most_common(1)[0][0]
    result["subagent_count"] = subagent_dispatches
    return result


def main() -> int:
    payload = read_stdin_payload()
    load_project_env()

    transcript = resolve_transcript(payload)
    if not should_run(payload, hook_name=HOOK_NAME, transcript=transcript, command_regex=CMD_REGEX):
        return 0
    if transcript is None:
        return 0

    entries = parse_transcript(transcript)
    scan = _scan(entries)
    command = scan.get("command")
    if not command:
        return 0

    slug = scan.get("slug") or ""
    props_date = date_props()
    sent_key = f"{props_date['date']} {props_date['time']} {command} {slug}"
    if idempotency_check(SENT_LOG, sent_key):
        return 0

    event = "job_research_update" if command == "update-job" else "job_research_run"
    debug_log(
        HOOK_NAME,
        f"capturing {event} slug={slug} subagents={scan['subagent_count']} "
        f"created={scan['readme_created']} appended={scan['readme_appended']}",
    )

    ok = posthog_capture(
        event,
        {
            **props_date,
            "command": command,
            "company_slug": slug or None,
            "subagent_count": int(scan.get("subagent_count") or 0),
            "readme_created": bool(scan.get("readme_created")),
            "readme_appended": bool(scan.get("readme_appended")),
        },
    )
    if ok:
        idempotency_record(SENT_LOG, sent_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
