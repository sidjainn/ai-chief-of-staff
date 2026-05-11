#!/usr/bin/env python3
"""Send `shopping_advise_run` or `shopping_reccos_run` event to PostHog.

Detects invocation by scanning the transcript for /advise or /reccos in user msgs.
Extracts metric fields from the latest section of logs/shopping-advise-log.md
or logs/shopping-reccos-log.md.
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

HOOK_NAME = "posthog-shopping"
SENT_LOG = PROJECT_ROOT / "logs" / "posthog-shopping-sent.log"
ADVISE_LOG = PROJECT_ROOT / "logs" / "shopping-advise-log.md"
RECCOS_LOG = PROJECT_ROOT / "logs" / "shopping-reccos-log.md"

ADVISE_CMD_REGEX = r"/advise\b"
RECCOS_CMD_REGEX = r"/reccos\b"
ANY_CMD_REGEX = r"/(?:advise|reccos)\b"


def _scan_command(transcript) -> tuple[str, str]:
    """Return (mode, slug_or_topic_hint). mode in {'advise','reccos',''}."""
    mode = ""
    hint = ""
    for blocks in iter_user_messages(transcript):
        joined = "\n".join(blocks)
        if re.search(ADVISE_CMD_REGEX, joined, re.IGNORECASE):
            mode = "advise"
            m = re.search(r"/advise\s+([\w-]+)", joined, re.IGNORECASE)
            if m:
                hint = m.group(1).lower()
        elif re.search(RECCOS_CMD_REGEX, joined, re.IGNORECASE):
            mode = "reccos"
            m = re.search(r"/reccos\s+([\w-]+)", joined, re.IGNORECASE)
            if m:
                hint = m.group(1).lower()
    return mode, hint


def _grab_int(block: str, key: str) -> int:
    m = re.search(rf"{key}\s*:\s*(\d+)", block, flags=re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _grab_string(block: str, key: str, max_len: int = 400) -> str:
    m = re.search(rf"{key}\s*:\s*(.+)", block, flags=re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1).strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    elif val.startswith('"'):
        val = val[1:]
    elif val.startswith("'"):
        val = val[1:]
    return val[:max_len]


def _grab_list(block: str, key: str) -> list[str]:
    m = re.search(rf"{key}\s*:\s*\[([^\]]*)\]", block, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    items = [x.strip().strip('"').strip("'") for x in raw.split(",")]
    return [x for x in items if x]


def _parse_advise_log(path) -> dict:
    result = {
        "slug": "",
        "top_pick": "",
        "retailer": "",
        "best_card": "",
        "list_price": 0,
        "effective_price": 0,
        "alts": [],
        "values_winner": "",
        "recco_path": "",
    }
    if not os.path.exists(path):
        return result
    try:
        text = open(path).read()
    except Exception:
        return result

    sections = list(re.finditer(r"^## (\S+)\s+\u2014\s+advise", text, flags=re.MULTILINE))
    if not sections:
        sections = list(re.finditer(r"^## (\S+)\s+(?:-|\u2014)\s+advise", text, flags=re.MULTILINE))
    if not sections:
        return result

    last = sections[-1]
    result["slug"] = last.group(1)
    next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
    block_end = last.end() + next_header.start() if next_header else len(text)
    block = text[last.start():block_end]

    result["top_pick"] = _grab_string(block, "top_pick")
    result["retailer"] = _grab_string(block, "retailer", 80)
    result["best_card"] = _grab_string(block, "best_card", 100)
    result["list_price"] = _grab_int(block, "list_price")
    result["effective_price"] = _grab_int(block, "effective_price")
    result["alts"] = _grab_list(block, "alts")
    result["values_winner"] = _grab_string(block, "values_winner", 50)
    result["recco_path"] = _grab_string(block, "recco_path", 300)
    return result


def _parse_reccos_log(path) -> dict:
    result = {
        "topic": "",
        "count": 0,
        "slugs": [],
        "tags": [],
        "top_reason": "",
    }
    if not os.path.exists(path):
        return result
    try:
        text = open(path).read()
    except Exception:
        return result

    sections = list(re.finditer(r"^## (\S+)\s+\u2014\s+reccos", text, flags=re.MULTILINE))
    if not sections:
        sections = list(re.finditer(r"^## (\S+)\s+(?:-|\u2014)\s+reccos", text, flags=re.MULTILINE))
    if not sections:
        return result

    last = sections[-1]
    next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
    block_end = last.end() + next_header.start() if next_header else len(text)
    block = text[last.start():block_end]

    result["topic"] = _grab_string(block, "topic", 60)
    result["count"] = _grab_int(block, "count")
    result["slugs"] = _grab_list(block, "slugs")
    result["tags"] = _grab_list(block, "tags")
    result["top_reason"] = _grab_string(block, "top_reason", 250)
    return result


def main() -> int:
    payload = read_stdin_payload()
    load_project_env()

    transcript = resolve_transcript(payload)
    if not should_run(payload, hook_name=HOOK_NAME, transcript=transcript, command_regex=ANY_CMD_REGEX):
        return 0
    if transcript is None:
        return 0

    mode, hint = _scan_command(transcript)
    if not mode:
        return 0

    props_date = date_props()

    if mode == "advise":
        counts = _parse_advise_log(str(ADVISE_LOG))
        slug = counts.get("slug") or hint or ""
        if not slug:
            return 0
        sent_key = f"{props_date['date']} {props_date['time']} shopping-advise {slug}"
        if idempotency_check(SENT_LOG, sent_key):
            return 0
        debug_log(
            HOOK_NAME,
            f"capturing shopping_advise_run slug={slug} retailer={counts.get('retailer')} "
            f"eff={counts.get('effective_price')} card={counts.get('best_card')}",
        )
        ok = posthog_capture(
            "shopping_advise_run",
            {
                **props_date,
                "slug": slug,
                "top_pick": counts.get("top_pick") or None,
                "retailer": counts.get("retailer") or None,
                "best_card": counts.get("best_card") or None,
                "list_price": int(counts.get("list_price") or 0),
                "effective_price": int(counts.get("effective_price") or 0),
                "savings": int(counts.get("list_price") or 0) - int(counts.get("effective_price") or 0),
                "alts": counts.get("alts") or [],
                "alts_count": len(counts.get("alts") or []),
                "values_winner": counts.get("values_winner") or None,
                "recco_path": counts.get("recco_path") or None,
            },
        )
        if ok:
            idempotency_record(SENT_LOG, sent_key)
        return 0

    if mode == "reccos":
        counts = _parse_reccos_log(str(RECCOS_LOG))
        topic = counts.get("topic") or hint or "broad"
        sent_key = f"{props_date['date']} {props_date['time']} shopping-reccos {topic}"
        if idempotency_check(SENT_LOG, sent_key):
            return 0
        debug_log(
            HOOK_NAME,
            f"capturing shopping_reccos_run topic={topic} count={counts.get('count')} "
            f"slugs={counts.get('slugs')}",
        )
        ok = posthog_capture(
            "shopping_reccos_run",
            {
                **props_date,
                "topic": topic,
                "count": int(counts.get("count") or 0),
                "slugs": counts.get("slugs") or [],
                "tags": counts.get("tags") or [],
                "top_reason": counts.get("top_reason") or None,
            },
        )
        if ok:
            idempotency_record(SENT_LOG, sent_key)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
