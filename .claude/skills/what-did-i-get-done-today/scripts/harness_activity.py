#!/usr/bin/env python3
"""Print what sid asked Claude Code and Codex to do in a time window, plus git commits.

Usage: harness_activity.py --since 2026-09-23T00:00:00+05:30 [--until 2026-09-24T00:00:00+05:30]
Defaults: --since = local midnight today, --until = now.
"""
import argparse
import glob
import json
import os
import subprocess
from datetime import datetime

HOME = os.path.expanduser("~")
MAX_PROMPTS = 6
MAX_CHARS = 220


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def clean(text):
    text = " ".join(text.split())
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "..."


def is_real_prompt(text):
    t = text.lstrip()
    return bool(t) and not t.startswith(("<", "Caveat:", "[Request interrupted"))


def claude_sessions(since, until):
    for path in glob.glob(f"{HOME}/.claude/projects/*/*.jsonl"):
        if datetime.fromtimestamp(os.path.getmtime(path)).astimezone() < since:
            continue
        title, cwd, prompts = None, None, []
        with open(path, errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") in ("custom-title", "ai-title"):
                    title = d.get("customTitle") or title or d.get("aiTitle")
                if d.get("type") != "user" or d.get("isMeta") or "timestamp" not in d:
                    continue
                ts = parse_ts(d["timestamp"])
                if not since <= ts < until:
                    continue
                content = d.get("message", {}).get("content")
                if isinstance(content, list):
                    if any(b.get("type") == "tool_result" for b in content if isinstance(b, dict)):
                        continue
                    content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                if isinstance(content, str) and is_real_prompt(content):
                    cwd = d.get("cwd", cwd)
                    prompts.append((ts, content))
        if prompts:
            yield "claude-code", title, cwd, prompts


def codex_sessions(since, until):
    paths = glob.glob(f"{HOME}/.codex/sessions/**/*.jsonl", recursive=True)
    paths += glob.glob(f"{HOME}/.codex/archived_sessions/**/*.jsonl", recursive=True)
    for path in paths:
        if datetime.fromtimestamp(os.path.getmtime(path)).astimezone() < since:
            continue
        cwd, prompts = None, []
        with open(path, errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                p = d.get("payload") or {}
                if d.get("type") == "session_meta":
                    cwd = p.get("cwd")
                if d.get("type") != "event_msg" or p.get("type") != "user_message":
                    continue
                ts = parse_ts(d["timestamp"])
                if since <= ts < until and is_real_prompt(p.get("message", "")):
                    prompts.append((ts, p["message"]))
        if prompts:
            yield "codex", None, cwd, prompts


def git_commits(cwds, since, until):
    seen = set()
    for cwd in sorted(c for c in cwds if c and os.path.isdir(c)):
        common = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True).stdout.strip()
        if not common or common in seen:
            continue
        seen.add(common)
        log = subprocess.run(["git", "-C", cwd, "log", "--all", "--no-merges",
                              f"--since={since.isoformat()}", f"--until={until.isoformat()}",
                              "--format=%ad %s", "--date=format-local:%H:%M"],
                             capture_output=True, text=True).stdout.strip()
        if log:
            yield os.path.dirname(common) if common.endswith("/.git") else common, log.splitlines()


def main():
    now = datetime.now().astimezone()
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat())
    ap.add_argument("--until", default=now.isoformat())
    a = ap.parse_args()
    since, until = parse_ts(a.since), parse_ts(a.until)

    sessions = list(claude_sessions(since, until)) + list(codex_sessions(since, until))
    sessions.sort(key=lambda s: s[3][0][0])
    print(f"window {since.isoformat()} -> {until.isoformat()}")
    print(f"{len(sessions)} sessions with prompts in window\n")
    for harness, title, cwd, prompts in sessions:
        local = [(ts.astimezone(), text) for ts, text in prompts]
        span = f"{local[0][0]:%H:%M}-{local[-1][0]:%H:%M}"
        print(f"[{harness}] {title or '(untitled)'} | {cwd} | {span} | {len(prompts)} prompts")
        for ts, text in local[:MAX_PROMPTS]:
            print(f"  {ts:%H:%M} {clean(text)}")
        if len(local) > MAX_PROMPTS:
            print(f"  ... {len(local) - MAX_PROMPTS} more, last: {clean(local[-1][1])}")
        print()

    print("git commits in window")
    any_commits = False
    for repo, lines in git_commits({s[2] for s in sessions}, since, until):
        any_commits = True
        print(f"  {repo}")
        for line in lines:
            print(f"    {line}")
    if not any_commits:
        print("  none")


if __name__ == "__main__":
    main()
