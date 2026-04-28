# Personal Assistant

> Built on Claude Code. Commands + skills + hooks wired into one system that gets smarter the more context you give it.

Top-level: a personal assistant that lives in this repo. Underneath: discrete **use cases**, each a self-contained workflow w/ its own commands, skills, and artifacts. Add new ones without disturbing the others.

---

## Use cases

| Use case | Status | Trigger | What it does |
|---|---|---|---|
| **Email Chief of Staff** | shipped | `/triage` | Daily triage across Gmail + Calendar. P0/P1/P2 brief tuned to your priorities, team, voice. Draft replies activate the `email-reply` skill — voice-matched, banned-phrase-aware, correct CCs. Hook auto-logs every run for monthly pattern review. |
| **Job Researcher** | shipped | `/research-job <jd-or-link>` · `/update-job <slug>` · pasted JD / "interviewing at X" / "had a call w/ <co>" | Deep research per company w/ parallel subagents (company / role / comp / interviewers / Granola). Verification pass cross-checks numbers. Synthesizes candidate-personalized doc under `jobs/<slug>/`. Re-runs append dated updates — running doc as memory. Light update path pulls fresh Granola (w/ deeplink) + folds in notes, no re-research. |
| **Growth Buddy** | upcoming | TBD | Tracks personal growth goals, weekly check-ins, surfaces drift vs stated intent. Reuses log/context spine. |

---

## How a use case is built

Every use case follows the same pattern:

```
context/        # what Claude needs to know about you (priorities, voice, team, resume)
commands/       # /slash entrypoints
skills/         # auto-triggered behavior on natural-language signals
hooks/          # silent persistence — logs, telemetry
artifacts/      # running docs (logs/, jobs/<slug>/, ...) — memory, not snapshots
```

The split matters:
- **Commands** = explicit. You type them.
- **Skills** = implicit. They fire on phrases ("draft a reply", "interviewing at X", "had a call w/ <co>").
- **Hooks** = invisible. Run after tool calls, persist state.
- **Artifacts** = append-only. Re-runs add dated sections, never overwrite.

---

## Repo structure

```
ai-chief-of-staff/
├── .claude/
│   ├── CLAUDE.md                       # Project rules
│   ├── settings.json                   # MCP servers + hooks
│   ├── context/                        # Shared spine across use cases
│   │   ├── my-priorities.md            # Quarterly focus
│   │   ├── my-team.md                  # Stakeholders + handling
│   │   └── communication-style.md      # Voice + banned phrases
│   ├── commands/
│   │   ├── triage.md                   # /triage           (email-cos)
│   │   ├── research-job.md             # /research-job     (job-researcher)
│   │   └── update-job.md               # /update-job       (job-researcher)
│   └── hooks/
│       └── post-triage-log.sh          # Auto-log after Gmail MCP
├── skills/
│   ├── email-reply/SKILL.md            # email-cos
│   └── job-research/SKILL.md           # job-researcher (full + light update)
├── jobs/                               # job-researcher artifacts
│   ├── me/
│   │   ├── resume.md                   # Candidate lens
│   │   └── interests.md                # Yes/no signals
│   └── <company-slug>/                 # Auto-created per company
│       ├── README.md                   # TL;DR + fit + questions
│       ├── company.md, jd.md, comp.md
│       ├── interviewers/<name>.md
│       └── meetings/<date>-<slug>.md   # Granola summary w/ deeplink
├── logs/                               # email-cos artifacts (gitignored)
│   └── weekly-log.md
├── demo/                               # Before/after walkthroughs
└── setup/                              # MCP + PostHog setup guides
```

---

## Use case 1 — Email Chief of Staff

```
/triage
```

Pulls Gmail (Gmail MCP) + Calendar (Google Calendar MCP), reads `context/` files, produces P0/P1/P2 brief.

- **Without context:** generic summaries, no prioritization.
- **With context:** knows stakeholders, deadlines, noise filters.

After triage flags an email:

```
draft a reply to the Hartwell email
```

`email-reply` skill activates. Reads `communication-style.md` + `my-team.md` before writing. Output: short, direct, voice-matched, correct CCs. Banned phrases blocked.

Every triage fires a `PostToolUse` hook → `logs/weekly-log.md`. After a month:

```
"Look at last month of logs. What patterns? Where am I spending time
 that doesn't match my stated priorities?"
```

See [`demo/triage-before.md`](demo/triage-before.md) vs [`demo/triage-after.md`](demo/triage-after.md), [`demo/email-draft-before.md`](demo/email-draft-before.md) vs [`demo/email-draft-after.md`](demo/email-draft-after.md).

---

## Use case 2 — Job Researcher

```
/research-job https://jobs.lever.co/<co>/<id>
```

Auto-triggers on JDs, job URLs, "interviewing at X", or pasted recruiter mail.

**Full-research workflow:**

1. Reads `jobs/me/resume.md` + `jobs/me/interests.md` — candidate lens.
2. Dispatches parallel subagents: `company-researcher`, `role-analyzer`, `comp-triangulator`, `interviewer-profiler`, `granola-puller`. Each writes one file. Main agent never loads raw web fetches.
3. Verification pass — cross-checks funding / headcount / comp / valuation across artifacts. Catches subagent hallucinations before synthesis.
4. Synthesizes `jobs/<slug>/README.md` — TL;DR, fit score vs `interests.md`, comp band, interviewer notes, questions grouped by intent (preparation / de-risk / real problems).

**Light update workflow:**

```
/update-job plum
```

Or natural: "had a call w/ Plum", "Plum debrief". Pulls fresh Granola (w/ deeplink), folds in pasted notes, appends `## Update — DATE` block. No re-research. Doc accumulates.

**Hard rules:**
- Auth-walled sources (LinkedIn, Levels.fyi) escalate to sandboxed Playwright profile at `~/.claude-playwright-profile`.
- Every external reference embeds inline URL — no bare titles.
- Every URL validated before write — no dead links propagated across artifacts.
- Source-staleness tiers labeled: `priority` (last 6mo) / `context` (6mo–2yr) / `background` (>2yr).
- Re-runs append, never overwrite. Running doc = memory.

---

## Use case 3 — Growth Buddy *(upcoming)*

Personal-growth companion. Tracks goals across weeks, surfaces drift between stated intent and observed behavior, prompts weekly reviews. Will reuse the `logs/` spine + `context/my-priorities.md` so the same priority signal drives both work triage and personal growth.

Status: design phase. Not yet wired.

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/Akshat2430/ai-chief-of-staff.git
cd ai-chief-of-staff
claude
```

### 2. Personalize context

Replace dummy data:

- [`.claude/context/my-priorities.md`](.claude/context/my-priorities.md) — quarterly goals
- [`.claude/context/my-team.md`](.claude/context/my-team.md) — manager, reports, stakeholders
- [`.claude/context/communication-style.md`](.claude/context/communication-style.md) — voice + rules

For job-researcher: also seed `jobs/me/resume.md` + `jobs/me/interests.md` (skill auto-fetches from your site if missing).

Highest-leverage 20 minutes you'll spend.

### 3. Set up MCPs (optional)

- Gmail + Calendar: [`setup/mcp-setup.md`](setup/mcp-setup.md) (~2 min)
- PostHog telemetry: [`setup/posthog-setup.md`](setup/posthog-setup.md)
- Granola (job-researcher meeting pull): MCP entry already in `.mcp.json` — sign in once.
- Playwright profile (auth-walled research): `~/.claude-playwright-profile` — sid logs into LinkedIn / Levels.fyi once, sessions persist.

### 4. Run

```
/triage                                  # email-cos
/research-job <jd-or-link>               # job-researcher
/update-job <slug>                       # post-meeting light update
```

---

## Updating the system

- **Monthly:** review `logs/weekly-log.md` vs `my-priorities.md`. Adjust context files where output drifted.
- **Quarterly:** update `my-priorities.md`. Whole system reorients.
- **Output off?** Correct Claude once, then update the relevant context file. Never correct twice.

---

## Resources

- Demo: [`demo/`](demo/)
- MCP setup: [`setup/mcp-setup.md`](setup/mcp-setup.md)
- PostHog setup: [`setup/posthog-setup.md`](setup/posthog-setup.md)

---

Built by [Akshat Kharbanda](https://www.linkedin.com/in/akshatkharbanda/) · [@akshat2430](https://github.com/Akshat2430)
