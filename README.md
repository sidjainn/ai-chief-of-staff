# Personal Assistant

> Built on Claude Code. Commands + skills + hooks wired into one system that gets smarter the more context you give it.

Top-level: a personal assistant that lives in this repo. Underneath: discrete **use cases**, each a self-contained workflow w/ its own commands, skills, and artifacts. Add new ones without disturbing the others.

---

## Use cases


| Use case                       | Trigger                                                                                                  | What it does                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Email Chief of Staff (WIP)** | `/triage`                                                                                                | Daily triage across Gmail + Calendar. P0/P1/P2 brief tuned to your priorities, team, voice. Draft replies activate the `email-reply` skill — voice-matched, banned-phrase-aware, correct CCs. Hook auto-logs every run for monthly pattern review. Context refinement pending, gcal mcp connection pending.                                                                                 |
| **Job Researcher**             | `/research-job <jd-or-link>` · `/update-job <slug>` · pasted JD / "interviewing at X" / "had a call w/ " | Deep research per company w/ parallel subagents (company / role / comp / interviewers / Granola). Verification pass cross-checks numbers. Synthesizes candidate-personalized doc under `jobs/<slug>/`. Re-runs append dated updates — running doc as memory. Light update path pulls fresh Granola (w/ deeplink) + folds in notes, no re-research.                                          |
| **Weekly Coach**               | `/weekly-coach`                                                                                          | Monday reflection + planning coach. Pulls annual charter, weekly to-do sheet, daily-log monthly Docs via public Google export endpoints (no GCP, no MCP). Surfaces 6-week patterns — avoidance, drift, breakthroughs. Writes `weeks/<ISO>/` (reflection / plan / patterns). Plan rendered in your exact sheet column format. Stop-hook posts `weekly_coach_run` event to PostHog w/ counts. |


---

## How a use case is built

Every use case follows the same pattern:

```
.claude/context/   # what Claude needs to know about you (priorities, voice, team, resume)
.claude/commands/  # /slash entrypoints
.claude/skills/    # auto-triggered behavior on natural-language signals
.claude/hooks/     # silent persistence — logs, telemetry.
artifacts/         # running docs (logs/, jobs/<slug>/, ...) — memory, not snapshots
```

The split matters:

- **Commands** = explicit. You type them.
- **Skills** = implicit. They fire on phrases ("draft a reply", "interviewing at X", "had a call w/ ").
- **Hooks** = invisible. Run after tool calls, persist state. Useful for transmitting events to posthog.
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
│   │   ├── update-job.md               # /update-job       (job-researcher)
│   │   └── weekly-coach.md             # /weekly-coach     (growth-buddy)
│   ├── skills/
│   │   ├── email-reply/SKILL.md        # email-cos
│   │   ├── job-research/SKILL.md       # job-researcher (full + light update)
│   │   └── weekly-coach/SKILL.md       # growth-buddy (reflection + planning)
│   ├── scripts/
│   │   └── fetch-coach-sources.sh      # Pulls charter/sheet/daily-log via public export
│   └── hooks/
│       ├── post-triage-log.sh          # Auto-log after Gmail MCP
│       ├── posthog-capture.sh          # Triage telemetry → PostHog
│       └── posthog-weekly-coach-capture.sh  # Weekly-coach telemetry → PostHog
├── jobs/                               # job-researcher artifacts
│   ├── me/
│   │   ├── resume.md                   # Candidate lens
│   │   └── interests.md                # Yes/no signals
│   └── <company-slug>/                 # Auto-created per company
│       ├── README.md                   # TL;DR + fit + questions
│       ├── company.md, jd.md, comp.md
│       ├── interviewers/<name>.md
│       └── meetings/<date>-<slug>.md   # Granola summary w/ deeplink
├── weeks/<ISO-week>/                   # growth-buddy artifacts (gitignored)
│   ├── reflection.md
│   ├── plan.md
│   └── patterns.md
├── logs/                               # email-cos + growth-buddy logs (gitignored)
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
draft a reply to the manoj email
```

`email-reply` skill activates. Reads `communication-style.md` + `my-team.md` before writing. Output: short, direct, voice-matched, correct CCs. Banned phrases blocked.

Every triage fires a `PostToolUse` hook → `logs/weekly-log.md`. After a month:

```
"Look at last month of logs. What patterns? Where am I spending time
 that doesn't match my stated priorities?"
```

See `[demo/triage-before.md](demo/triage-before.md)` vs `[demo/triage-after.md](demo/triage-after.md)`, `[demo/email-draft-before.md](demo/email-draft-before.md)` vs `[demo/email-draft-after.md](demo/email-draft-after.md)`.

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

Or natural: "had a call w/ Posthog", "Posthog debrief". Pulls fresh Granola (w/ deeplink), folds in pasted notes, appends `## Update — DATE` block. No re-research. Doc accumulates.

**Hard rules:**

- Auth-walled sources (LinkedIn, Levels.fyi) escalate to sandboxed Playwright profile at `~/.claude-playwright-profile`.
- Every external reference embeds inline URL — no bare titles.
- Every URL validated before write — no dead links propagated across artifacts.
- Source-staleness tiers labeled: `priority` (last 6mo) / `context` (6mo–2yr) / `background` (>2yr).
- Re-runs append, never overwrite. Running doc = memory.

---

## Use case 3 — Growth Buddy

```
/weekly-coach
```

Monday-morning ritual. Reflects on prior week, surfaces patterns across last 6 weeks (not just one), names what you're avoiding, names what's breaking through, sets intentions aligned to your annual charter.

**Three live Google sources, pulled via public export endpoints — no GCP project, no Drive MCP:**

- **Annual charter** (Google Doc) — year-level focus areas. The lens.
- **Weekly to-do sheet** (Google Sheet) — one tab per week, last 6 read for patterns.
- **Daily log folder** (Drive folder) — one Google Doc per month w/ a tab per day.

All three docs must be shared "anyone with the link". IDs live in `.env` (gitignored), referenced by env var name only — never committed.

**Outputs to `weeks/<ISO-week>/`** (gitignored — personal):

- `reflection.md` — what last week revealed
- `plan.md` — next week's plan in your exact sheet column format, paste-ready
- `patterns.md` — multi-week avoidance / drift / breakthrough threads

Coach voice — pushes back. Names the question you're avoiding. Asks 3 sharp questions back. No assistant fluff.

**Hook:** Stop-hook fires after the run, posts `weekly_coach_run` event to PostHog w/ item counts (focus areas, drops, intentions). Planning trends become observable over time.

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/sidjainn/ai-chief-of-staff.git
cd ai-chief-of-staff
claude
```

### 2. Personalize context

Replace dummy data:

- `[.claude/context/my-priorities.md](.claude/context/my-priorities.md)` — quarterly goals
- `[.claude/context/my-team.md](.claude/context/my-team.md)` — manager, reports, stakeholders
- `[.claude/context/communication-style.md](.claude/context/communication-style.md)` — voice + rules

For job-researcher: also seed `jobs/me/resume.md` + `jobs/me/interests.md` (skill auto-fetches from your site if missing).

For growth-buddy: copy `.env.example` → `.env`, fill three Google file IDs (`WEEKLY_COACH_CHARTER_DOC_ID`, `WEEKLY_COACH_SHEET_ID`, `WEEKLY_COACH_DAILY_LOG_FOLDER_ID`). All three docs must be shared "anyone with the link". `.env` is gitignored.

Highest-leverage 20 minutes you'll spend.

### 3. Set up MCPs (optional)

- Gmail + Calendar: `[setup/mcp-setup.md](setup/mcp-setup.md)` (~2 min)
- PostHog telemetry: `[setup/posthog-setup.md](setup/posthog-setup.md)`
- Granola (job-researcher meeting pull): MCP entry already in `.mcp.json` — sign in once.
- Playwright profile (auth-walled research): `~/.claude-playwright-profile` — sid logs into LinkedIn / Levels.fyi once, sessions persist.
- Growth-buddy: no MCP needed. Public Google export endpoints used directly.

### 4. Run

```
/triage                                  # email-cos
/research-job <jd-or-link>               # job-researcher
/update-job <slug>                       # post-meeting light update
/weekly-coach                            # growth-buddy (Monday morning)
```

---

## Updating the system

- **Daily:** `/triage` (email-cos). Hook auto-logs.
- **Post-meeting:** `/update-job <slug>` or "had a call w/ " — running doc accumulates.
- **Weekly (Mon):** `/weekly-coach` — patterns file gets richer w/ every week of data.
- **Monthly:** review `logs/weekly-log.md` vs `my-priorities.md`. Adjust context files where output drifted.
- **Quarterly:** update `my-priorities.md` + annual charter. Whole system reorients.
- **Output off?** Correct Claude once, then update the relevant context file. Never correct twice.

---

## Resources

- MCP setup: `[setup/mcp-setup.md](setup/mcp-setup.md)`
- PostHog setup: `[setup/posthog-setup.md](setup/posthog-setup.md)`

---

Built by [siddharth](https://www.linkedin.com/in/siddharth-j/) with inspiration from [@akshat2430](https://github.com/Akshat2430) · [other projects](https://sidjainn.github.io)