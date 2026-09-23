#!/usr/bin/env python3
"""Send a `what_i_got_done` event for each nightly note under what-i-got-done/.

Triggers on the note files, not the transcript, so the skill can also run this
script directly from harnesses without Claude Code hooks (Codex). The event
carries the full note body. The idempotency key is the note date plus a hash of
the body, so a rebuilt note sends once more with a higher revision.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import sys

from _hook_common import (
    PROJECT_ROOT,
    debug_log,
    idempotency_check,
    idempotency_record,
    load_project_env,
    posthog_capture,
)

HOOK_NAME = "posthog-wigd"
NOTES_DIR = PROJECT_ROOT / "what-i-got-done"
SENT_LOG = PROJECT_ROOT / "logs" / "posthog-what-i-got-done-sent.log"
# Only recent notes, so a lost ledger or a fresh clone can't replay history.
MAX_AGE_DAYS = 7

NOTE_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
SECTIONS = {
    "done": "done_count",
    "let go": "let_go_count",
    "moved forward": "moved_forward_count",
    "tomorrow": "tomorrow_count",
}


def parse_note(text: str) -> tuple[dict, str, dict] | None:
    m = NOTE_RE.match(text)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        key, sep, val = line.partition(":")
        if sep:
            meta[key.strip()] = val.strip()
    body = m.group(2).strip()

    counts = dict.fromkeys(SECTIONS.values(), 0)
    current = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and stripped[:-1].lower() in SECTIONS:
            current = SECTIONS[stripped[:-1].lower()]
        elif current and stripped.startswith("- "):
            counts[current] += 1
        elif not stripped:
            current = None
    return meta, body, counts


def _prior_sends(stem: str) -> int:
    if not SENT_LOG.exists():
        return 0
    try:
        return sum(1 for line in SENT_LOG.read_text().splitlines() if line.startswith(stem + " "))
    except Exception:
        return 0


def main() -> int:
    load_project_env()
    cutoff = dt.date.today() - dt.timedelta(days=MAX_AGE_DAYS)

    for path in sorted(NOTES_DIR.glob("*/*.md")):
        try:
            note_date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if note_date < cutoff:
            continue
        try:
            parsed = parse_note(path.read_text(encoding="utf-8"))
        except Exception as e:
            debug_log(HOOK_NAME, f"read failed {path}: {e}")
            continue
        if not parsed:
            debug_log(HOOK_NAME, f"no frontmatter in {path} — skipping")
            continue
        meta, body, counts = parsed

        digest = hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]
        sent_key = f"{path.stem} {digest}"
        if idempotency_check(SENT_LOG, sent_key):
            continue

        missing = [s.strip() for s in meta.get("sources_missing", "").strip("[]").split(",") if s.strip()]
        props = {
            "date": note_date.isoformat(),
            "week": note_date.strftime("%Y-W%V"),
            "day_of_week": note_date.strftime("%A"),
            "window_start": meta.get("window_start"),
            "window_end": meta.get("window_end"),
            "body": body,
            "word_count": len(body.split()),
            "sources_missing": missing,
            "revision": _prior_sends(path.stem) + 1,
            **counts,
        }
        debug_log(HOOK_NAME, f"capturing what_i_got_done {path.stem} rev={props['revision']}")
        if posthog_capture("what_i_got_done", props):
            idempotency_record(SENT_LOG, sent_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
