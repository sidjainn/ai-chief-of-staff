"""Shared helpers for Claude Code PostToolUse / Stop hooks.

Hooks share five concerns (transcript resolution, .env loading, JSONL parsing,
idempotency, PostHog capture). This module is the single source of truth — bug
fixes should land here, not in each wrapper.

All public functions swallow their own errors and return safe defaults.
Telemetry/logging hooks must never block the user.
"""

from __future__ import annotations

import datetime as _dt
import hashlib as _hashlib
import json as _json
import os as _os
import re as _re
import subprocess as _subprocess
import sys as _sys
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs"
DEBUG_LOG = LOGS_DIR / "hook-debug.log"
CACHE_DIR = LOGS_DIR / ".hook-cache"


def debug_log(tag: str, msg: str) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        with DEBUG_LOG.open("a") as fh:
            fh.write(f"[{ts}] [{tag}] {msg}\n")
    except Exception:
        pass


def read_stdin_payload() -> dict:
    try:
        raw = _sys.stdin.read()
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        d = _json.loads(raw)
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def load_project_env(project_root: Path = PROJECT_ROOT) -> None:
    """Source PROJECT_ROOT/.env into os.environ. Project values WIN over inherited.

    The PostHog Code wrapper sets its own ``pha_`` key into the inherited shell
    env that routes events to a different project. The project's own .env must
    take precedence so events land in the right place.
    """
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            val = val.strip()
            # Strip surrounding quotes
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            _os.environ[key] = val
    except Exception as e:
        debug_log("hook-common", f"load_project_env failed: {e}")


def resolve_transcript(payload: dict) -> Path | None:
    """Return the transcript path. Stop hooks pass `transcript_path` directly;
    PostToolUse passes only `session_id` — fall back to scanning ~/.claude/projects."""
    p = payload.get("transcript_path") or ""
    if p:
        path = Path(p)
        if path.is_file():
            return path
    sid = payload.get("session_id") or ""
    if not sid:
        return None
    root = Path.home() / ".claude" / "projects"
    if not root.exists():
        return None
    try:
        for match in root.rglob(f"{sid}.jsonl"):
            return match
    except Exception:
        return None
    return None


def _unwrap_message(entry: dict) -> dict | None:
    """VSCode extension wraps the assistant/user message under a 'message' key.
    Some clients write the message inline. Returns None if the entry has neither
    a usable wrapped message nor a role of its own — caller skips."""
    msg = entry.get("message")
    if isinstance(msg, dict):
        return msg
    if "message" in entry and not isinstance(msg, dict):
        return None
    return entry


def _text_blocks(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(b.get("text", "") or "")
        return out
    return []


def _tool_uses(content) -> list[dict]:
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
    return []


def parse_transcript(transcript: Path) -> list[dict]:
    """Read JSONL and return entries with the 'message' wrap stripped.
    Returns ``[]`` on read failure. Single read; reuse for multi-pass scans."""
    out: list[dict] = []
    try:
        with transcript.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = _json.loads(line)
                except Exception:
                    continue
                msg = _unwrap_message(entry)
                if not isinstance(msg, dict):
                    continue
                out.append(msg)
    except Exception as e:
        debug_log("hook-common", f"parse_transcript failed: {e}")
    return out


def iter_assistant_messages(transcript: Path) -> Iterator[tuple[list[str], list[dict]]]:
    for msg in parse_transcript(transcript):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        yield _text_blocks(content), _tool_uses(content)


def iter_user_messages(transcript: Path) -> Iterator[list[str]]:
    for msg in parse_transcript(transcript):
        if msg.get("role") != "user":
            continue
        yield _text_blocks(msg.get("content", ""))


def idempotency_check(sent_log: Path, key: str) -> bool:
    """Return True if `key` is already present in sent_log (treat as 'already sent')."""
    if not sent_log.exists():
        return False
    try:
        with sent_log.open() as fh:
            for line in fh:
                if key in line:
                    return True
    except Exception:
        return False
    return False


def idempotency_record(sent_log: Path, key: str) -> None:
    try:
        sent_log.parent.mkdir(parents=True, exist_ok=True)
        with sent_log.open("a") as fh:
            fh.write(key + "\n")
    except Exception as e:
        debug_log("hook-common", f"idempotency_record failed: {e}")


def date_props(now: _dt.datetime | None = None) -> dict:
    n = now or _dt.datetime.now()
    return {
        "date": n.strftime("%Y-%m-%d"),
        "time": n.strftime("%H:%M"),
        "week": n.strftime("%Y-W%V"),
        "day_of_week": n.strftime("%A"),
    }


def posthog_capture(event: str, properties: dict, *, distinct_id: str | None = None) -> bool:
    """POST event to PostHog. Silently no-ops when POSTHOG_API_KEY unset.
    Returns True on HTTP success, False otherwise. Never raises."""
    api_key = _os.environ.get("POSTHOG_API_KEY")
    if not api_key:
        return False
    host = _os.environ.get("POSTHOG_HOST", "https://us.posthog.com")
    distinct = distinct_id or _os.environ.get("POSTHOG_DISTINCT_ID") or _os.environ.get("USER", "unknown")
    payload = {
        "api_key": api_key,
        "event": event,
        "distinct_id": distinct,
        "properties": {**properties, "source": properties.get("source", "claude-code-hook")},
    }
    try:
        body = _json.dumps(payload)
    except Exception as e:
        debug_log("hook-common", f"posthog_capture serialize failed: {e}")
        return False
    url = host.rstrip("/") + "/i/v0/e/"
    try:
        result = _subprocess.run(
            [
                "curl", "-fsS", "--max-time", "5",
                "-H", "Content-Type: application/json",
                "-X", "POST",
                "-d", body,
                url,
            ],
            capture_output=True, text=True, timeout=8,
        )
        if result.returncode != 0:
            debug_log("hook-common", f"curl failed rc={result.returncode}: {result.stderr.strip()}")
            return False
        debug_log("hook-common", f"posthog {event} ok: {result.stdout.strip()[:200]}")
        return True
    except Exception as e:
        debug_log("hook-common", f"posthog_capture curl raised: {e}")
        return False


# ---------- Pre-gate ----------

_GATE_CACHE_VERSION = 1


def _cache_path_for(transcript: Path, hook_name: str) -> Path:
    digest = _hashlib.sha1(f"{hook_name}::{transcript}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{hook_name}-{digest}.json"


def transcript_changed(transcript: Path, hook_name: str) -> bool:
    """Return True if transcript size/mtime differs from cached. Records new state.
    Use as a cheap pre-gate so unrelated PostToolUse events skip the full scan."""
    try:
        st = transcript.stat()
    except Exception:
        return True
    cur = {"v": _GATE_CACHE_VERSION, "size": st.st_size, "mtime": int(st.st_mtime)}
    cache_file = _cache_path_for(transcript, hook_name)
    prev = None
    if cache_file.exists():
        try:
            prev = _json.loads(cache_file.read_text())
        except Exception:
            prev = None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(_json.dumps(cur))
    except Exception:
        pass
    if not prev:
        return True
    return prev.get("size") != cur["size"] or prev.get("mtime") != cur["mtime"]


def tail_bytes(transcript: Path, n: int = 65536) -> str:
    """Read last n bytes of transcript as UTF-8, ignoring decode errors."""
    try:
        with transcript.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - n))
            return fh.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def stdin_marker_hit(payload: dict, marker: str) -> bool:
    """Cheapest possible signal: does last_assistant_message already contain marker?"""
    return marker in (payload.get("last_assistant_message") or "")


def should_run(
    payload: dict,
    *,
    hook_name: str,
    transcript: Path | None,
    assistant_marker: str | None = None,
    command_regex: str | None = None,
) -> bool:
    """Cheap pre-gate: skip the expensive full-transcript scan when the hook
    obviously doesn't apply.

    Returns True when the hook *should* proceed to the full scan. False means
    the wrapper can exit immediately.

    Logic:
      - If `assistant_marker` is set and present in `last_assistant_message`, run.
      - If transcript is None (no transcript yet), and no stdin signal: skip.
      - If transcript file size+mtime unchanged since last cache: skip.
      - Otherwise scan only the last 64 KB for marker/command_regex.
    """
    if assistant_marker and stdin_marker_hit(payload, assistant_marker):
        return True
    if transcript is None:
        return False
    # Always update cache; result tells us if there's anything new.
    changed = transcript_changed(transcript, hook_name)
    if not changed:
        return False
    tail = tail_bytes(transcript)
    if assistant_marker and assistant_marker in tail:
        return True
    if command_regex:
        try:
            if _re.search(command_regex, tail, _re.IGNORECASE):
                return True
        except _re.error:
            return True  # regex broken — fail open, let full scan handle it
    if not assistant_marker and not command_regex:
        return True
    return False
