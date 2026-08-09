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


# Real blocks pad the value, then annotate it. The annotation is prose and can
# itself contain a '#', so only 2+ spaces before the '#' marks the boundary.
ANNOTATED_BLOCK = """\
## Week 2026-W33 — coaching

- next_week_items: 2
- rolled_over_items: 21                           # blank in both tabs (scripted diff)
- pillars_served: 8/9                             # +1 on WATCH, not at-risk
- pillars_at_risk: []                             # one pillar on WATCH, not drift
- state: steady                                   # steady-to-peak in body, thin on hope
- intervention_hit_rate: 3/7                      # all three that landed were stand-downs
- interference_top: unclear                       # task-shape rows most frequent
- chronic_in_immunity_map: 2                      # two open blocks
- top_question: "Ship the thing you already wrote, or say out loud that it is parked \
— which is it? The rewrite is not the blocker and you named that yourself on Friday, \
so the only open question left is whether the thread is live at all this week or \
whether it goes on the shelf until the other one lands. Three people asked for the \
same artifact and none of them has been told either way, which is its own answer if \
it runs another week. The honest version costs one sentence; the avoidant version \
costs a month and you have run that experiment twice already this quarter."
- intent: Turn the open question into a list I can answer.
"""


def _wire(monkeypatch, tmp_path, coach_log_text):
    """Point the hook at temp files and stub everything outside the unit."""
    coach_log = tmp_path / "weekly-coach-log.md"
    coach_log.write_text(coach_log_text, encoding="utf-8")
    sent_log = tmp_path / "posthog-weekly-coach-sent.log"

    captured = []
    monkeypatch.setattr(hook, "COACH_LOG", coach_log)
    monkeypatch.setattr(hook, "SENT_LOG", sent_log)
    # Nothing transcript-shaped is stubbed: the hook triggers on the log block.
    monkeypatch.setattr(hook, "read_stdin_payload", lambda: {"session_id": "s1"})
    monkeypatch.setattr(hook, "load_project_env", lambda: None)
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

    # Last week's run recorded W31 under its own payload fingerprint.
    hook.main()
    assert [p["iso_week"] for _, p in captured] == ["2026-W31"]
    captured.clear()

    # Early fires this week: skill hasn't written the W32 block yet, so the
    # parse still yields W31 unchanged and must not re-send it.
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


def test_pre_revision_ledger_line_migrates_once_then_settles(monkeypatch, tmp_path):
    """Ledger lines written before payload fingerprints exist carry no hash.

    They can't match a fingerprinted key, so the week emits once more — which is
    wanted, since that older event holds only the opening draft. It must then
    settle, not re-emit on every fire.
    """
    _, captured = _wire(monkeypatch, tmp_path, W31_BLOCK + "\n" + W32_BLOCK)
    hook.SENT_LOG.write_text("2026-08-02 weekly-coach 2026-W32\n", encoding="utf-8")

    hook.main()
    hook.main()
    hook.main()

    assert len(captured) == 1
    assert captured[0][1]["iso_week"] == "2026-W32"
    assert captured[0][1]["revision"] == 2, "counts the pre-fingerprint event"


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


def test_inline_annotation_stripped_from_string_values(monkeypatch, tmp_path):
    """Values are padded then annotated; only the value belongs in the event.

    Before this was handled, `state` shipped as 'steady' + 41 spaces + '# steady-'
    — the padding and the comment ate the 50-char budget.
    """
    _, captured = _wire(monkeypatch, tmp_path, ANNOTATED_BLOCK)

    hook.main()

    _, props = captured[0]
    assert props["state"] == "steady"
    assert props["interference_top"] == "unclear"


def test_annotation_stripping_leaves_numeric_fields_alone(monkeypatch, tmp_path):
    """The numeric grabbers match narrow patterns and were never affected."""
    _, captured = _wire(monkeypatch, tmp_path, ANNOTATED_BLOCK)

    hook.main()

    _, props = captured[0]
    assert props["rolled_over_items"] == 21
    assert props["pillars_served"] == 8
    assert props["pillars_total"] == 9
    assert props["chronic_in_immunity_map"] == 2
    assert props["intervention_hit_rate"] == round(3 / 7, 3)
    assert props["pillars_at_risk"] == []


def test_top_question_survives_intact(monkeypatch, tmp_path):
    """The question is the payload — a 400-char cap cut off its ending."""
    _, captured = _wire(monkeypatch, tmp_path, ANNOTATED_BLOCK)

    hook.main()

    _, props = captured[0]
    question = props["top_question"]
    assert len(question) > 400, "fixture must exceed the old cap to be a regression"
    assert question.startswith("Ship the thing you already wrote")
    assert question.endswith("run that experiment twice already this quarter.")
    assert not question.startswith('"')


def test_hash_inside_prose_is_not_treated_as_annotation():
    """A single space before '#' is prose; 2+ spaces marks the annotation."""
    prose = "Revisit re-framing #1 and the #2 follow-up before Sunday."
    assert hook._strip_annotation(prose) == prose
    assert hook._strip_annotation("steady    # steady-to-peak in body") == "steady"
    assert hook._strip_annotation("unclear  # task-shape rows most frequent") == "unclear"
    assert hook._strip_annotation("no annotation here") == "no annotation here"


# The narrative section is free-form by design: across 16 weeks, 92 of 102
# distinct keys appear in only one week. The hook pins the envelope, not names.
NARRATIVE_BLOCK = """\
## Week 2026-W34 — coaching

- next_week_items: 2
- state: steady                                   # padded annotation, stripped
- top_question: "Is the thread live or parked?"
- load_decision: ceiling 3, taking 2 — hours are not the constraint
- one_off_finding_nobody_will_repeat: a thing observed once, never again
- CORRECTION_2026-08-16_misread: coach read the pain as solvency; it was scaffolding
- majors_2026-08-16: (1) Record it once (2) Process the list you already wrote
"""


def test_narrative_rows_captured_verbatim(monkeypatch, tmp_path):
    """Every non-core row ships, whatever it is called this week."""
    _, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)

    hook.main()

    _, props = captured[0]
    assert props["narrative_count"] == 4
    assert props["narrative_keys"] == [
        "load_decision",
        "one_off_finding_nobody_will_repeat",
        "CORRECTION_2026-08-16_misread",
        "majors_2026-08-16",
    ]
    joined = "\n".join(props["narrative"])
    assert "ceiling 3, taking 2" in joined
    assert "it was scaffolding" in joined
    assert "Record it once" in joined
    assert props["narrative_chars"] > 0


def test_narrative_excludes_core_scalar_rows(monkeypatch, tmp_path):
    """Core fields have their own properties — they must not be duplicated."""
    _, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)

    hook.main()

    _, props = captured[0]
    for core in ("next_week_items", "state", "top_question"):
        assert core not in props["narrative_keys"]
    assert props["state"] == "steady"


def test_revised_block_emits_a_new_revision(monkeypatch, tmp_path):
    """The session keeps editing the block for an hour after the first fire.

    The captured payload changed, so a further event must ship, tagged as a
    later revision. Reading the week means taking the newest one.
    """
    coach_log, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)

    hook.main()
    assert captured[0][1]["revision"] == 1

    # Discussion adds a finding and revises the majors.
    coach_log.write_text(
        NARRATIVE_BLOCK + "- late_finding_from_discussion: surfaced at the end\n",
        encoding="utf-8",
    )
    hook.main()

    assert len(captured) == 2
    assert captured[1][1]["revision"] == 2
    assert captured[1][1]["narrative_count"] == 5
    assert "late_finding_from_discussion" in captured[1][1]["narrative_keys"]


def test_unchanged_block_does_not_re_emit(monkeypatch, tmp_path):
    """Repeated fires with no edit stay a single event — the #10 guarantee."""
    _, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)

    hook.main()
    hook.main()
    hook.main()

    assert len(captured) == 1


def test_prefix_ledger_line_from_before_revisions_does_not_block(monkeypatch, tmp_path):
    """Old ledger lines have no payload hash; they must not suppress forever."""
    _, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)
    hook.SENT_LOG.write_text("weekly-coach 2026-W34\n", encoding="utf-8")

    hook.main()

    assert len(captured) == 1
    assert captured[0][1]["revision"] == 2


def test_emits_with_no_transcript_evidence_at_all(monkeypatch, tmp_path):
    """The trigger is the log block changing, not the transcript.

    should_run scanned only the last 64 KB for /weekly-coach. Sessions here run
    800 KB-8 MB, so the invocation scrolled out of that window mid-session and
    every later revision was lost — dead in 3 of 8 real transcripts. The hook no
    longer consults the transcript, so a stdin payload with nothing in it still
    captures a changed block.
    """
    _, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)
    monkeypatch.setattr(hook, "read_stdin_payload", lambda: {})

    hook.main()

    assert len(captured) == 1
    assert captured[0][1]["iso_week"] == "2026-W34"


def test_still_silent_when_block_unchanged_and_no_transcript(monkeypatch, tmp_path):
    """Dropping the transcript gate must not turn every Stop into an event."""
    _, captured = _wire(monkeypatch, tmp_path, NARRATIVE_BLOCK)
    monkeypatch.setattr(hook, "read_stdin_payload", lambda: {})

    hook.main()
    for _ in range(5):
        hook.main()

    assert len(captured) == 1
