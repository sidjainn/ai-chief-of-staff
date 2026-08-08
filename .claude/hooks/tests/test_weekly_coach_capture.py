"""Regression tests for the weekly-coach PostHog capture hook.

Covers the duplicate-emission bug: the hook fired repeatedly during a single
/weekly-coach run, and because the idempotency key contained the run date *and*
the iso_week scraped from maps/weekly-coach-log.md — the file the run itself
rewrites at the end — an early fire emitted last week's block and a late fire
emitted this week's, giving two events per run.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import posthog_weekly_coach_capture as hook  # noqa: E402


W31_BLOCK = """\
## Week 2026-W31 — coaching

- next_week_items: 3
- rolled_over_items: 5
- pillars_served: 4/12
- state: steady
"""

W32_BLOCK = """\
## Week 2026-W32 — coaching

- next_week_items: 2
- rolled_over_items: 6
- pillars_served: 5/12
- state: charged
"""


def _wire(monkeypatch, tmp_path, coach_log_text):
    """Point the hook at temp files and stub everything outside the unit."""
    coach_log = tmp_path / "weekly-coach-log.md"
    coach_log.write_text(coach_log_text, encoding="utf-8")
    sent_log = tmp_path / "posthog-weekly-coach-sent.log"

    captured = []
    monkeypatch.setattr(hook, "COACH_LOG", coach_log)
    monkeypatch.setattr(hook, "SENT_LOG", sent_log)
    monkeypatch.setattr(hook, "read_stdin_payload", lambda: {"session_id": "s1"})
    monkeypatch.setattr(hook, "load_project_env", lambda: None)
    monkeypatch.setattr(hook, "resolve_transcript", lambda payload: tmp_path / "t.jsonl")
    monkeypatch.setattr(hook, "should_run", lambda *a, **k: True)
    monkeypatch.setattr(hook, "_scan_invoked", lambda transcript: True)
    monkeypatch.setattr(
        hook,
        "posthog_capture",
        lambda event, props: (captured.append((event, props)), True)[1],
    )
    return coach_log, captured


def test_one_event_per_run_despite_repeated_fires(monkeypatch, tmp_path):
    """A run fires the hook many times, spanning the coach-log rewrite.

    Only the new week may emit — last week's block was already sent last week.
    """
    coach_log, captured = _wire(monkeypatch, tmp_path, W31_BLOCK)
    hook.SENT_LOG.write_text("weekly-coach 2026-W31\n", encoding="utf-8")

    # Early fires: skill hasn't written the W32 block yet.
    hook.main()
    hook.main()
    assert captured == [], "re-emitted last week's block"

    # Skill appends this week's block partway through the run.
    coach_log.write_text(W31_BLOCK + "\n" + W32_BLOCK, encoding="utf-8")

    # Late fires: PostToolUse + Stop both land after the write.
    hook.main()
    hook.main()

    assert len(captured) == 1
    event, props = captured[0]
    assert event == "weekly_coach_run"
    assert props["iso_week"] == "2026-W32"
    assert props["next_week_items"] == 2


def test_old_dated_ledger_entries_still_dedupe(monkeypatch, tmp_path):
    """Pre-fix ledger lines carry a date prefix; they must keep suppressing."""
    _, captured = _wire(monkeypatch, tmp_path, W31_BLOCK + "\n" + W32_BLOCK)
    hook.SENT_LOG.write_text("2026-08-02 weekly-coach 2026-W32\n", encoding="utf-8")

    hook.main()

    assert captured == []


def test_unreadable_coach_log_emits_nothing(monkeypatch, tmp_path):
    """No parseable block means no data — abort rather than send zeros.

    maps/weekly-coach-log.md is a symlink into a private repo; when it can't be
    read the hook used to fall back to a transcript regex and ship an all-zero
    payload under whatever iso_week it found.
    """
    _, captured = _wire(monkeypatch, tmp_path, "# no coaching sections here\n")

    rc = hook.main()

    assert rc == 0
    assert captured == []


def test_missing_coach_log_emits_nothing(monkeypatch, tmp_path):
    _, captured = _wire(monkeypatch, tmp_path, W32_BLOCK)
    hook.COACH_LOG.unlink()

    hook.main()

    assert captured == []
