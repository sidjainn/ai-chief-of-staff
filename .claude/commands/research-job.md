You are running deep job research for sid. Treat the user message after `/research-job` as the input — it can be a job URL, a raw JD pasted in, or a company name + role.

## What to do

Activate the **`job-research`** skill in `.claude/skills/job-research/SKILL.md` and follow it end-to-end. The skill defines the full workflow: bootstrap candidate context → parse input → create the per-company folder under `jobs/` → dispatch parallel subagents (company / role / comp / interviewers / Granola) → synthesize the running doc → ask follow-ups → re-synthesize.

Do not duplicate the skill's instructions here. The skill is the source of truth so command and skill stay in sync.

## Input handling

- **URL** → fetch and parse before doing anything else.
- **Raw JD text** → use it directly.
- **Company name only** → ask which role, then proceed.
- **Empty** → ask sid for a JD, link, or company name.

## Output

Per the skill: don't dump the full doc into chat. Show only:
1. Path to the new (or updated) folder under `jobs/`
2. TL;DR section verbatim from README
3. Top 3 questions to ask
4. Open questions + "want me to dig further on any?"

## Reminders

- Always read `jobs/me/resume.md` and `jobs/me/interests.md` first — they are the lens for everything.
- Dispatch subagents in parallel, in a **single message** with multiple Agent tool calls.
- If `jobs/<slug>/` already exists, append a dated update — never overwrite.
- Pull Granola context even if you expect nothing — the absence of prior meetings is itself a signal.
