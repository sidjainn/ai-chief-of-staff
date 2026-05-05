"""Unit tests for _hook_common helpers."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import _hook_common as hc  # noqa: E402


class ParseTranscriptTest(unittest.TestCase):
    def test_unwraps_message_envelope_and_bare_entries(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"message": {"role": "assistant", "content": "wrapped"}}) + "\n")
            f.write(json.dumps({"role": "user", "content": "bare"}) + "\n")
            f.write("not-json\n")
            f.write(json.dumps({"message": "not-a-dict"}) + "\n")
            f.write(json.dumps({"message": {"role": "assistant", "content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "name": "Agent"},
            ]}}) + "\n")
            path = Path(f.name)
        try:
            entries = hc.parse_transcript(path)
            roles = [e.get("role") for e in entries]
            self.assertEqual(roles, ["assistant", "user", "assistant"])
            asst_blocks = list(hc.iter_assistant_messages(path))
            self.assertEqual(len(asst_blocks), 2)
            self.assertEqual(asst_blocks[0][0], ["wrapped"])
            self.assertEqual(asst_blocks[1][0], ["hello"])
            self.assertEqual(len(asst_blocks[1][1]), 1)
            self.assertEqual(asst_blocks[1][1][0]["name"], "Agent")
        finally:
            path.unlink()


class ResolveTranscriptTest(unittest.TestCase):
    def test_uses_transcript_path_when_present(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write("{}\n")
            path = Path(f.name)
        try:
            self.assertEqual(hc.resolve_transcript({"transcript_path": str(path)}), path)
        finally:
            path.unlink()

    def test_returns_none_when_neither_path_nor_session(self):
        self.assertIsNone(hc.resolve_transcript({}))


class IdempotencyTest(unittest.TestCase):
    def test_check_and_record_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "sent.log"
            self.assertFalse(hc.idempotency_check(log, "k1"))
            hc.idempotency_record(log, "k1")
            self.assertTrue(hc.idempotency_check(log, "k1"))
            self.assertFalse(hc.idempotency_check(log, "k2"))


class LoadProjectEnvTest(unittest.TestCase):
    """Locks the weekly-coach drift bug: project .env must beat inherited shell env."""

    def test_project_env_wins_over_inherited(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".env").write_text(
                'POSTHOG_API_KEY=project_key\n'
                'POSTHOG_HOST="https://app.posthog.com"\n'
                "# comment\n"
                "export EMPTY=\n"
            )
            saved = {k: os.environ.get(k) for k in ("POSTHOG_API_KEY", "POSTHOG_HOST", "EMPTY")}
            try:
                os.environ["POSTHOG_API_KEY"] = "inherited_wrapper_key"
                hc.load_project_env(root)
                self.assertEqual(os.environ["POSTHOG_API_KEY"], "project_key")
                self.assertEqual(os.environ["POSTHOG_HOST"], "https://app.posthog.com")
                self.assertEqual(os.environ.get("EMPTY"), "")
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v


class TranscriptChangedTest(unittest.TestCase):
    def test_returns_false_on_unchanged_file(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "x.jsonl"
            t.write_text("hi\n")
            cache_orig = hc.CACHE_DIR
            hc.CACHE_DIR = Path(d) / ".cache"
            try:
                self.assertTrue(hc.transcript_changed(t, "test"))
                self.assertFalse(hc.transcript_changed(t, "test"))
                time.sleep(1.1)
                with t.open("a") as fh:
                    fh.write("more\n")
                # bump mtime explicitly so the test isn't filesystem-resolution-flaky
                os.utime(t, (time.time(), time.time()))
                self.assertTrue(hc.transcript_changed(t, "test"))
            finally:
                hc.CACHE_DIR = cache_orig


class ShouldRunTest(unittest.TestCase):
    def test_short_circuits_on_stdin_marker(self):
        self.assertTrue(hc.should_run(
            {"last_assistant_message": "# Morning Triage today"},
            hook_name="t", transcript=None, assistant_marker="Morning Triage",
        ))

    def test_skips_when_no_transcript_and_no_signal(self):
        self.assertFalse(hc.should_run(
            {}, hook_name="t", transcript=None, assistant_marker="Morning Triage",
        ))

    def test_runs_when_tail_contains_command(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "x.jsonl"
            t.write_text(json.dumps({"message": {"role": "user", "content": "/research-job foo"}}) + "\n")
            cache_orig = hc.CACHE_DIR
            hc.CACHE_DIR = Path(d) / ".cache"
            try:
                self.assertTrue(hc.should_run(
                    {}, hook_name="jr", transcript=t, command_regex=r"/research-job\b",
                ))
                # Second call: cache says nothing changed → skip.
                self.assertFalse(hc.should_run(
                    {}, hook_name="jr", transcript=t, command_regex=r"/research-job\b",
                ))
            finally:
                hc.CACHE_DIR = cache_orig


if __name__ == "__main__":
    unittest.main()
