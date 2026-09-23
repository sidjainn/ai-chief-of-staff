"""Tests for the what-i-got-done PostHog capture hook.

The hook fires on every Stop and the skill also calls it directly, so the same
note must send once. A rebuilt note sends again as the next revision.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import posthog_what_i_got_done_capture as hook  # noqa: E402


NOTE = """\
---
date: {date}
window_start: {date}T00:00:00+05:30
window_end: {date}T22:00:00+05:30
sources_missing: [granola]
---

# wed 23 sep - what did i get done

interview day.

done:
- neo exploratory round - went well
- website pr merged
- sent: the reply

let go:
- cubbon park on sunday

tomorrow:
- tax consult, 12:30

rippling has carried over twice now.
"""


def _wire(monkeypatch, tmp_path):
    notes = tmp_path / "what-i-got-done"
    captured = []
    monkeypatch.setattr(hook, "NOTES_DIR", notes)
    monkeypatch.setattr(hook, "SENT_LOG", tmp_path / "posthog-what-i-got-done-sent.log")
    monkeypatch.setattr(hook, "load_project_env", lambda: None)
    monkeypatch.setattr(hook, "debug_log", lambda tag, msg: None)
    monkeypatch.setattr(
        hook,
        "posthog_capture",
        lambda event, props: (captured.append((event, props)), True)[1],
    )
    return notes, captured


def _write(notes: Path, date: dt.date, text: str | None = None) -> Path:
    path = notes / str(date.year) / f"{date.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or NOTE.format(date=date.isoformat()), encoding="utf-8")
    return path


def test_one_event_per_note_with_body_and_counts(monkeypatch, tmp_path):
    notes, captured = _wire(monkeypatch, tmp_path)
    today = dt.date.today()
    _write(notes, today)

    hook.main()
    hook.main()
    hook.main()

    assert len(captured) == 1
    event, props = captured[0]
    assert event == "what_i_got_done"
    assert props["date"] == today.isoformat()
    assert props["body"].startswith("# wed 23 sep - what did i get done")
    assert "---" not in props["body"], "frontmatter leaked into the body"
    assert props["done_count"] == 3
    assert props["let_go_count"] == 1
    assert props["moved_forward_count"] == 0
    assert props["tomorrow_count"] == 1
    assert props["sources_missing"] == ["granola"]
    assert props["revision"] == 1


def test_rebuilt_note_sends_again_as_next_revision(monkeypatch, tmp_path):
    notes, captured = _wire(monkeypatch, tmp_path)
    today = dt.date.today()
    path = _write(notes, today)
    hook.main()

    path.write_text(path.read_text() + "\none more line.\n", encoding="utf-8")
    hook.main()
    hook.main()

    assert [p["revision"] for _, p in captured] == [1, 2]


def test_old_notes_are_not_replayed(monkeypatch, tmp_path):
    """A lost ledger or a fresh clone must not resend the whole history."""
    notes, captured = _wire(monkeypatch, tmp_path)
    _write(notes, dt.date.today() - dt.timedelta(days=hook.MAX_AGE_DAYS + 1))

    hook.main()

    assert captured == []


def test_missing_folder_and_bad_files_emit_nothing(monkeypatch, tmp_path):
    notes, captured = _wire(monkeypatch, tmp_path)
    hook.main()  # folder doesn't exist yet

    _write(notes, dt.date.today(), text="no frontmatter here\n")
    (notes / "2026" / "notes-index.md").write_text("---\n---\n", encoding="utf-8")
    hook.main()

    assert captured == []


def test_failed_send_is_retried_next_fire(monkeypatch, tmp_path):
    notes, captured = _wire(monkeypatch, tmp_path)
    _write(notes, dt.date.today())
    monkeypatch.setattr(hook, "posthog_capture", lambda event, props: False)
    hook.main()

    monkeypatch.setattr(
        hook,
        "posthog_capture",
        lambda event, props: (captured.append((event, props)), True)[1],
    )
    hook.main()

    assert len(captured) == 1
    assert captured[0][1]["revision"] == 1
