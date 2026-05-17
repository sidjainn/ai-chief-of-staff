"""Reuses fixtures/multi-command-transcript.jsonl to assert the scoping fix
from commit 3b62c5b: subagent + slug tally must scope to the latest command's
segment only — not across earlier /job-research invocations."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

from _hook_common import parse_transcript  # noqa: E402
from posthog_job_research_capture import _scan  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "multi-command-transcript.jsonl"


class JobResearchScanTest(unittest.TestCase):
    def test_scopes_to_latest_command(self):
        entries = parse_transcript(FIXTURE)
        result = _scan(entries)
        self.assertEqual(result["command"], "job-research")
        self.assertEqual(result["slug"], "company-b")
        self.assertEqual(result["subagent_count"], 1)


if __name__ == "__main__":
    unittest.main()
