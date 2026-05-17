# Personal Assistant

> Built on Claude Code. Skills + hooks wired into one system that gets smarter the more context you give it.

Top-level: a personal assistant that lives in this repo. Underneath: discrete **use cases**, each a self-contained workflow w/ its own skills and artifacts. Add new ones without disturbing the others.

Every workflow is a skill — so the same setup ports cleanly to Codex or any other harness with skill auto-discovery.

---

## Use cases


| Use case                       | Trigger                                                                                                  | What it does                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Growth Buddy**               | `/weekly-coach`                                                                                          | Monday reflection + planning coach. Pulls annual charter, weekly to-do sheet, daily-log monthly Docs via public Google export endpoints (no GCP, no MCP). Surfaces 6-week patterns — avoidance, drift, breakthroughs. Writes `weeks/<ISO>/` (reflection / plan / patterns). Plan rendered in your exact sheet column format. Stop-hook posts `weekly_coach_run` event to PostHog w/ counts. |
| **Job Researcher**             | `/job-research <jd-or-link>` · `/update-job <slug>` · pasted JD / "interviewing at X" / "had a call w/ " | Deep research per company w/ parallel subagents (company / role / comp / interviewers / Granola). Verification pass cross-checks numbers. Synthesizes candidate-personalized doc under `jobs/<slug>/`. Re-runs append dated updates — running doc as memory. Light update path pulls fresh Granola (w/ deeplink) + folds in notes, no re-research.                                          |
| **Email Triage (WIP)**         | `/email-triage`                                                                                          | Daily triage across Gmail + Calendar. P0/P1/P2 brief tuned to your priorities, team, voice. Draft replies activate the `email-reply` skill — voice-matched, banned-phrase-aware, correct CCs. Hook auto-logs every run for monthly pattern review. Context refinement pending, gcal mcp connection pending.                                                                                |
| **Shopping Advisor**           | `/shopping-assist <product>` · `/reccos [topic]`                                                          | Pre-purchase advisor + proactive discovery. Reads shared `shopping-context/` (profile, inventory, interests, budget-rules, data-sources) + Flipkart/Swiggy xlsx + Gmail to ground every recommendation in your values, household, owned cards, and order history. `/shopping-assist` returns a 3-candidate shortlist w/ 5-dim scoring, cross-platform price-parity, card-discount math (Flipkart Axis / SBI Rupay / Swiggy HDFC). `/reccos` surfaces 3-5 tagged items ([upgrade] / [gap] / [interest-match] / [swap-from-current]) for discovery. Context-capture catches preferences mid-convo and offers to persist them. Hook posts `shopping_advise_run` / `shopping_reccos_run` events to PostHog. |


---

## How a use case is built

Every use case follows the same pattern:

```
.claude/skills/    # workflows — slash-invokable (/skill-name) and auto-triggered 
                   # each skill keeps its own context: example.context/ (public template) + context/ (gitignored real content)
.claude/hooks/     # silent persistence — logs, telemetry
artifacts/         # running docs (logs/, jobs/<slug>/, ...) — memory, not snapshots
```

- **Skills** = the workflow. Type `/<skill-name>` to invoke, or trigger via natural-language phrases ("draft a reply", "interviewing at X", "had a call w/ ").
- **Hooks** = invisible. Run after tool calls, persist state. Useful for transmitting events to posthog.
- **Artifacts** = append-only. Re-runs add dated sections, never overwrite.

---

## Repo structure

```
ai-chief-of-staff/
├── .claude/
│   ├── CLAUDE.md                       # Project rules
│   ├── settings.json                   # MCP servers + hooks
│   ├── skills/
│   │   ├── weekly-coach/SKILL.md       # growth-buddy (reflection + planning)  — /weekly-coach
│   │   ├── job-research/SKILL.md       # job-researcher (heavy first-pass)      — /job-research
│   │   ├── update-job/SKILL.md         # post-meeting light update              — /update-job
│   │   ├── email-triage/
│   │   │   ├── SKILL.md                # email-triage (P0/P1/P2 brief)          — /email-triage
│   │   │   ├── example.context/        # Public template — sample priorities/team/voice
│   │   │   └── context/                # Real personal content (gitignored)
│   │   ├── email-reply/SKILL.md        # email-reply (voice-matched draft)      — auto on "draft a reply"
│   │   ├── shopping-assist/SKILL.md    # pre-purchase advisor                   — /shopping-assist
│   │   ├── shopping-reccos/SKILL.md    # proactive discovery                    — /reccos
│   │   └── shopping-context/*.md       # Shared shopping context (gitignored): profile, inventory, interests, budget-rules, data-sources
│   ├── scripts/
│   │   └── fetch-coach-sources.sh      # Pulls charter/sheet/daily-log via public export
│   └── hooks/
│       ├── post-triage-log.sh          # Auto-log after Gmail MCP → email-runs/<DATE>.md
│       ├── posthog-capture.sh          # Triage telemetry → PostHog
│       ├── posthog-job-research-capture.sh  # Job-research telemetry → PostHog
│       ├── posthog-weekly-coach-capture.sh  # Weekly-coach telemetry → PostHog
│       └── posthog_shopping_capture.py       # Shopping (advise + reccos) telemetry → PostHog
├── email-runs/<DATE>.md                # email-triage artifacts (gitignored) — one file per day, one section per run
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
├── .shopping/reccos/<slug>/            # shopping-advisor artifacts (gitignored) — brief / shortlist / price-parity / verdict
├── logs/                               # hook idempotency ledgers + per-run log blocks (gitignored)
├── demo/                               # Before/after walkthroughs
└── setup/                              # MCP + PostHog setup guides
```

---

## Use case 1 — Growth Buddy

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

## Use case 2 — Job Researcher

```
/job-research https://jobs.lever.co/<co>/<id>
```

Auto-triggers on JDs, job URLs, "interviewing at X", or pasted recruiter mail.

**Full-research workflow:**

1. Reads `jobs/me/resume.md` + `jobs/me/interests.md` — candidate lens.
2. Dispatches parallel subagents: `company-researcher`, `role-analyzer`, `comp-triangulator`, `interviewer-profiler`, `granola-puller`. Each writes one file. Main agent never loads raw web fetches.
3. Verification pass — cross-checks funding / headcount / comp / valuation across artifacts. Catches subagent hallucinations before synthesis.
4. Synthesizes `jobs/<slug>/README.md` — TL;DR, fit score vs `interests.md`, comp band, interviewer notes, questions grouped by intent (preparation / de-risk / real problems).

**Light update workflow:**

```
/update-job company_ref
```

Or natural: "had a call w/ Posthog", "Posthog debrief". Pulls fresh Granola (w/ deeplink), folds in pasted notes, appends `## Update — DATE` block. No re-research. Doc accumulates.

**Hard rules:**

- Auth-walled sources (LinkedIn, Levels.fyi) escalate to sandboxed Playwright profile at `~/.claude-playwright-profile`.
- Every external reference embeds inline URL — no bare titles.
- Every URL validated before write — no dead links propagated across artifacts.
- Source-staleness tiers labeled: `priority` (last 6mo) / `context` (6mo–2yr) / `background` (>2yr).
- Re-runs append, never overwrite. Running doc = memory.

---

## Use case 3 — Email Triage

```
/email-triage
```

Pulls Gmail (Gmail MCP) + Calendar (Google Calendar MCP), reads `context/` files, produces P0/P1/P2 brief.

- **Without context:** generic summaries, no prioritization.
- **With context:** knows stakeholders, deadlines, noise filters.

After triage flags an email:

```
draft a reply to the manoj email
```

`email-reply` skill activates. Reads `communication-style.md` + `my-team.md` before writing. Output: short, direct, voice-matched, correct CCs. Banned phrases blocked.

Every triage fires a `PostToolUse` hook → `email-runs/<DATE>.md` (one file per day, one section per run). After a month:

```
"Look at last month of email-runs. What patterns? Where am I spending time
 that doesn't match my stated priorities?"
```

See `[demo/triage-before.md](demo/triage-before.md)` vs `[demo/triage-after.md](demo/triage-after.md)`, `[demo/email-draft-before.md](demo/email-draft-before.md)` vs `[demo/email-draft-after.md](demo/email-draft-after.md)`.

---

## Use case 4 — Shopping Advisor

```
/shopping-assist <product>
/reccos [topic]
```

Pre-purchase advisor + proactive discovery. Two skills, one shared context store.

**`/shopping-assist`** — paste what you're about to buy ("office chair, current HOF mesh, 2yr, lumbar pain after 6h"). Skill:

1. Reads all five `shopping-context/` files (profile / inventory / interests / budget-rules / data-sources).
2. Pulls relevant order history — Flipkart xlsx, Swiggy xlsx if food-adjacent, Gmail for anything else.
3. Researches 5-8 candidates on the open web (Reddit, YouTube, manufacturer pages, Indian retailer reviews).
4. Filters to a 3-candidate shortlist on disqualifiers (out-of-budget / out-of-stock / banned brand or category).
5. Scores each on 5 dims: **value · nature · user-friendly · reviews · budget-fit** — every score backed by a citation link.
6. Runs cross-platform price-parity (≥3 retailers per item) + applies card-discount math using your owned cards (Flipkart Axis / SBI Rupay / Swiggy HDFC) — flags borrowable-card opportunities only when material.
7. Writes `.shopping/reccos/<slug>/` w/ four artifacts: `brief.md`, `shortlist.md`, `price-parity.md`, `verdict.md`. Renders terse inline verdict.
8. Stop-hook posts `shopping_advise_run` to PostHog w/ top pick + retailer + effective price + values winner.

**`/reccos`** — proactive discovery. Optional topic arg (`/reccos kitchen`, `/reccos endurance`) or broad scan. Surfaces 3-5 items tagged `[upgrade]` / `[gap]` / `[interest-match]` / `[swap-from-current]`. Each item: 1-line why-for-you + 1 alt + manufacturer / retailer / 1 social link (Reddit / YouTube / Twitter). Lightweight — no per-item file dump. Deep-dive any pick via `/shopping-assist <slug>`. Hook posts `shopping_reccos_run` to PostHog.

**Context capture (mid-conversation):** if you surface a preference while talking ("no leather", "raise headphone ceiling to ₹15K", "got into pickleball"), skill proposes a diff to the right file (`profile.md` / `interests.md` / `budget-rules.md`) and asks `y/n` before writing. Explicit signals (`save: X`, `remember Y`) skip the prompt. Never auto-writes `inventory.md` — purchases only.

**Hard rules:**

- Always link — every candidate, every review citation. No bare brand names.
- Min 3 retailers in price-parity. Non-negotiable.
- Card-discount layer mandatory — effective price (after best owned card) is the headline number.
- Default "for self, in Bangalore" — explicit override required for Agra / dad / friends.
- Ovo-veg default for food-adjacent.
- Re-running same slug overwrites `.shopping/reccos/<slug>/` (clean re-run).
- Never writes to `inventory.md` (recommendation ≠ purchase).

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

Email-triage + email-reply read context from `.claude/skills/email-triage/context/`. The repo ships a public template at `.claude/skills/email-triage/example.context/` — copy it and edit:

```bash
cp -r .claude/skills/email-triage/example.context .claude/skills/email-triage/context
# then edit the 3 files inside .claude/skills/email-triage/context/ (gitignored)
```

Files to fill in:

- `my-priorities.md` — quarterly goals
- `my-team.md` — manager, reports, stakeholders
- `communication-style.md` — voice + rules

For job-researcher: also seed `jobs/me/resume.md` + `jobs/me/interests.md` (skill auto-fetches from your site if missing).

For growth-buddy: copy `.env.example` → `.env`, fill three Google file IDs (`WEEKLY_COACH_CHARTER_DOC_ID`, `WEEKLY_COACH_SHEET_ID`, `WEEKLY_COACH_DAILY_LOG_FOLDER_ID`). All three docs must be shared "anyone with the link". `.env` is gitignored.

For shopping-advisor: scaffold `.claude/skills/shopping-context/` with five files (gitignored):

- `profile.md` — identity, household(s), values, payment methods (Flipkart Axis / SBI Rupay / Swiggy HDFC etc.), no-go list
- `inventory.md` — durable goods owned, tagged by address; never auto-updated from advisor output
- `interests.md` — hobbies, curiosities, active to-dos w/ purchase implications
- `budget-rules.md` — per-category ceilings + buy-once-cry-once caps + no-go brands
- `data-sources.md` — paths to Flipkart / Swiggy xlsx + Gmail query template

First-time bootstrap: ask Claude to draft all five from your order-history xlsx + charter + daily logs, then review.

Highest-leverage 20 minutes you'll spend.

### 3. Set up MCPs (optional)

- Gmail + Calendar: `[setup/mcp-setup.md](setup/mcp-setup.md)` (~2 min)
- PostHog telemetry: `[setup/posthog-setup.md](setup/posthog-setup.md)`
- Granola (job-researcher meeting pull): MCP entry already in `.mcp.json` — sign in once.
- Playwright profile (auth-walled research): `~/.claude-playwright-profile` — sid logs into LinkedIn / Levels.fyi once, sessions persist.
- Growth-buddy: no MCP needed. Public Google export endpoints used directly.

### 4. Run

```
/weekly-coach                            # growth-buddy (Monday morning)
/job-research <jd-or-link>               # job-researcher
/update-job <slug>                       # post-meeting light update
/email-triage                            # email-triage
/shopping-assist <product>               # shopping-advisor (pre-purchase)
/reccos [topic]                          # shopping-advisor (proactive discovery)
```

---

## Updating the system

- **Daily:** `/email-triage`. Hook auto-logs.
- **Pre-purchase:** `/shopping-assist <product>` — 3-candidate shortlist w/ price-parity + card-discount math. `/reccos` for discovery.
- **Post-meeting:** `/update-job <slug>` or "had a call w/ " — running doc accumulates.
- **Weekly (Mon):** `/weekly-coach` — patterns file gets richer w/ every week of data.
- **Monthly:** review `email-runs/` vs `my-priorities.md`. Adjust context files where output drifted.
- **Quarterly:** update `my-priorities.md` + annual charter. Whole system reorients.
- **Output off?** Correct Claude once, then update the relevant context file. Never correct twice.

---

## Resources

- MCP setup: `[setup/mcp-setup.md](setup/mcp-setup.md)`
- PostHog setup: `[setup/posthog-setup.md](setup/posthog-setup.md)`

---

Built by [siddharth](https://www.linkedin.com/in/siddharth-j/) with inspiration from [@akshat2430](https://github.com/Akshat2430) · [other projects](https://sidjainn.github.io)
