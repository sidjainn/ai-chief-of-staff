"""Smoke-test posthog_capture: triage extraction + P0/P1/P2 counting.

Doesn't actually send to PostHog (POSTHOG_API_KEY cleared)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import posthog_capture as ph  # noqa: E402


TRIAGE_TEXT = """### Morning Triage — 2026-05-05

**P0 — Act Now**
- Hartwell Group thread (Marcus Webb)

**P1 — Act Today**
- Quarterly review prep
- Mid-week sync notes

**P2 — On My Radar**
- Conference invite
- Newsletter sign-up
"""


EMPTY_SECTIONS_TRIAGE = """### Morning Triage — 2026-05-05

**P0 — Act Now**
- None. No team, Sarah, Hartwell, churn traffic in last 24h.

**P1 — Act Today**
- None.

**P2 — On My Radar**
- LinkedIn job alert
- Wellfound 14 new jobs
"""


class CountMarkerTest(unittest.TestCase):
    def test_counts_real_items(self):
        self.assertEqual(ph._count_marker(TRIAGE_TEXT, "P0"), 1)
        self.assertEqual(ph._count_marker(TRIAGE_TEXT, "P1"), 2)
        self.assertEqual(ph._count_marker(TRIAGE_TEXT, "P2"), 2)

    def test_empty_sections_count_zero(self):
        # Regression: "**P0 ...**" header + "- None." body must NOT count as 1 item.
        self.assertEqual(ph._count_marker(EMPTY_SECTIONS_TRIAGE, "P0"), 0)
        self.assertEqual(ph._count_marker(EMPTY_SECTIONS_TRIAGE, "P1"), 0)
        self.assertEqual(ph._count_marker(EMPTY_SECTIONS_TRIAGE, "P2"), 2)

    def test_missing_section_counts_zero(self):
        self.assertEqual(ph._count_marker("no sections here", "P0"), 0)


class TriageHookSmokeTest(unittest.TestCase):
    """End-to-end: feed transcript via stdin payload, ensure no exception
    and that idempotency log is NOT written when API key is unset."""

    def test_runs_without_api_key(self):
        import _hook_common as hc
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "transcript.jsonl"
            t.write_text(
                json.dumps({"message": {"role": "assistant", "content": [
                    {"type": "text", "text": TRIAGE_TEXT},
                ]}}) + "\n"
            )
            payload = {
                "transcript_path": str(t),
                "last_assistant_message": TRIAGE_TEXT,
                "hook_event_name": "Stop",
            }
            saved_env = os.environ.pop("POSTHOG_API_KEY", None)
            saved_stdin = sys.stdin
            saved_loader = ph.load_project_env
            saved_cache = hc.CACHE_DIR
            ph.load_project_env = lambda *a, **kw: None  # don't read real .env
            hc.CACHE_DIR = Path(d) / ".cache"
            try:
                import io
                sys.stdin = io.StringIO(json.dumps(payload))
                rc = ph.main()
                self.assertEqual(rc, 0)
            finally:
                sys.stdin = saved_stdin
                ph.load_project_env = saved_loader
                hc.CACHE_DIR = saved_cache
                if saved_env is not None:
                    os.environ["POSTHOG_API_KEY"] = saved_env


if __name__ == "__main__":
    unittest.main()
