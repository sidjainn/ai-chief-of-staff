"""Regression tests for phantom emissions from the job-research capture hook.

The hook fires whenever /job-research or /update-job appears anywhere in the
transcript, including sessions that merely discuss the command. Two leaks
followed from that:

- No slug guard: a discussion session produced an event with company_slug null
  and every flag false. 42 of 89 events in PostHog were this shape.
- Dated idempotency key: `{date} {command} {slug}` made a fresh key every day,
  so a later session that still referenced jobs/<slug>/ re-sent the same run.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import posthog_job_research_capture as hook  # noqa: E402


def _wire(monkeypatch, tmp_path, scan, session="sess-a"):
    """Point the hook at temp files and stub everything outside the unit."""
    sent_log = tmp_path / "posthog-job-research-sent.log"
    sent_log.touch()

    captured = []
    monkeypatch.setattr(hook, "SENT_LOG", sent_log)
    monkeypatch.setattr(hook, "read_stdin_payload", lambda: {"session_id": session})
    monkeypatch.setattr(hook, "load_project_env", lambda: None)
    monkeypatch.setattr(
        hook, "resolve_transcript", lambda payload: tmp_path / f"{session}.jsonl"
    )
    monkeypatch.setattr(hook, "should_run", lambda *a, **k: True)
    monkeypatch.setattr(hook, "parse_transcript", lambda t: [])
    monkeypatch.setattr(hook, "_scan", lambda entries: dict(scan))
    monkeypatch.setattr(
        hook,
        "posthog_capture",
        lambda event, props: (captured.append((event, props)), True)[1],
    )
    return captured


REAL_RUN = {
    "command": "job-research",
    "slug": "acme-corp",
    "subagent_count": 0,
    "readme_created": False,
    "readme_appended": True,
    "user_input": "/job-research acme corp",
}

# A session that only talks about the command: regex hits, no jobs/<slug>/ path.
DISCUSSION = {
    "command": "job-research",
    "slug": None,
    "subagent_count": 0,
    "readme_created": False,
    "readme_appended": False,
    "user_input": "why does /job-research double-fire?",
}


def test_no_slug_emits_nothing(monkeypatch, tmp_path):
    """Without a slug there is no run to report — the payload would be empty."""
    captured = _wire(monkeypatch, tmp_path, DISCUSSION)

    rc = hook.main()

    assert rc == 0
    assert captured == []


def test_one_event_per_session_despite_repeated_fires(monkeypatch, tmp_path):
    """PostToolUse + Stop fire the hook many times across a single run."""
    captured = _wire(monkeypatch, tmp_path, REAL_RUN)

    hook.main()
    hook.main()
    hook.main()

    assert len(captured) == 1
    event, props = captured[0]
    assert event == "job_research_run"
    assert props["company_slug"] == "acme-corp"


def test_later_session_mentioning_same_slug_does_not_re_emit(monkeypatch, tmp_path):
    """One slug leaked 6 events across 5 days for a single research run.

    A later session still had jobs/acme-corp/ paths in scope, so the scan
    resolved the same slug and the dated key let it ship again.
    """
    sent_log = tmp_path / "posthog-job-research-sent.log"
    sent_log.write_text("sess-a job-research acme-corp\n", encoding="utf-8")
    captured = _wire(monkeypatch, tmp_path, REAL_RUN, session="sess-a")

    hook.main()

    assert captured == []


def test_genuine_rerun_in_new_session_still_captured(monkeypatch, tmp_path):
    """Cost check: re-researching a company later is a real run worth keeping."""
    captured = _wire(monkeypatch, tmp_path, REAL_RUN, session="sess-a")
    hook.main()
    assert len(captured) == 1

    # Same slug, different session — a second, deliberate /job-research.
    captured_2 = _wire(monkeypatch, tmp_path, REAL_RUN, session="sess-b")
    hook.main()

    assert len(captured_2) == 1
    assert captured_2[0][1]["company_slug"] == "acme-corp"


def test_update_job_keyed_separately_from_research(monkeypatch, tmp_path):
    """/update-job on an already-researched company is its own event."""
    captured = _wire(monkeypatch, tmp_path, REAL_RUN, session="sess-a")
    hook.main()
    assert captured[0][0] == "job_research_run"

    update = dict(REAL_RUN, command="update-job")
    captured_2 = _wire(monkeypatch, tmp_path, update, session="sess-a")
    hook.main()

    assert len(captured_2) == 1
    assert captured_2[0][0] == "job_research_update"
