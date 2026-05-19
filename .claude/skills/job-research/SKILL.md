---
name: job-research
description: Deep first-pass research on a job + company. Triggers on `/job-research`, a pasted JD, a job link (Greenhouse/Lever/Ashby/Workday/LinkedIn etc.), "I'm interviewing at [company]", or "what should I know about [company]" in a hiring context. Creates a per-company folder under `jobs/<slug>/` with company info, role breakdown, comp triangulation, interviewer profiles, Granola meeting context, and questions to ask. Dispatches subagents in parallel and runs a verification pass before synthesis. For post-meeting or ad-hoc updates on a company that's ALREADY tracked under `jobs/<slug>/` (recaps, "had a call with [co]", pasted notes), use the lighter `update-job` skill instead — this skill is the heavy new-co flow.
version: 1.0
author: sid
referenced_files:
  - jobs/me/resume.md
  - jobs/me/interests.md
---

# Job Research Skill

## What this skill does

Turns a JD or job link into a candidate-personalized, deeply-researched brief — every time, in the same shape, persisted on disk so it can be iterated on across sessions and meetings.

Optimizes for two things sid cares about:

1. **Context preservation** — heavy research is delegated to subagents that each write one artifact. The main agent only ever reads final artifacts, never raw web fetches.
2. **Iteration over rewriting** — re-running on a company appends a new dated section instead of overwriting prior understanding. The doc is a memory, not a snapshot.

## How to use

The user will give one of:
- A job URL (Greenhouse, Lever, Ashby, Workday, Workable, LinkedIn, company careers page, etc.)
- Raw JD text pasted into chat
- A company name + role title in conversation
- A meeting reference like "I'm interviewing at [company] tomorrow"

Trigger the skill in all of these cases — don't wait for the user to say "research this job."

---

## Output style — caveman terse

All artifacts (`README.md`, `company.md`, `jd.md`, `comp.md`, `interviewers/*.md`, meeting summaries) and the final chat output write in **caveman-full** voice:

- Drop articles (a/an/the), filler (just/really/basically), pleasantries, hedging.
- Fragments OK. Short synonyms. Pattern: `[thing] [action] [reason]. [next step].`
- Tables and bullets > prose paragraphs. Numbers + sources, not narration.
- Citations stay verbatim — `[Source: <url>]` mandatory for every fact (verification pass still binding).
- **Hyperlink rule (mandatory).** Every reference to an external artifact — post, article, podcast, Medium piece, LinkedIn post, tweet, press release, JD, blog, podcast episode — MUST embed the URL inline. Format: `[short title](url)` or `(url)` after a verbatim quote. **Never reference a source by title alone.** Failure mode: morning-of checklist items like "re-read X post" with no URL = useless. Subagents fetching via Playwright/WebFetch must capture the source URL alongside every quote and pass it through.
- **Absolute-date rule (mandatory).** NEVER write relative dates: "today", "tomorrow", "yesterday", "last week", "next week", "morning of," "in 2 days." Always use ISO/calendar dates: `2026-05-19`, `Tue 2026-05-19, 5:30 PM IST`, `week of 2026-W21`. Even calendar/section headers — write `## 2026-05-19 — Abhishek (call flow)` not `## Tomorrow — Abhishek`. **Reason:** these docs are running memory read days/weeks later. "Tomorrow" rots the instant the calendar turns. Exceptions: (a) verbatim quoted interview questions where "today" means "in your current operations" (time-agnostic conversational use), (b) spoken-script lines wrapped in quotes if explicitly tagged "[spoken on DATE]." Default to absolute. When user pastes a meeting w/ relative dates, convert to absolute via current-date context before writing.
- **Link-validation rule (mandatory).** Every URL written into any artifact MUST be validated to return 200 (or to render real content via Playwright) BEFORE the file is written. Common failure modes: (a) slug-only Medium URLs like `medium.com/plumhq/<slug>` that need a hash suffix `-<id>`; (b) hallucinated `careers/<co>` paths; (c) handle confusion (e.g. `@tanish2k` was wrongly attributed to Shreyas — verified via web search to be Saurabh's actual handle). **Verification methods, in order:** (1) WebFetch the URL — 404 / "page not found" / redirect to home = dead. (2) On 4xx / login wall, try Playwright. (3) For ambiguous handles or slug-only URLs, run `WebSearch` to disambiguate before writing. (4) If a URL can't be verified, write `_(link unverified — search [<query>](google.com/search?q=...) to locate)_` rather than commit a dead link. **Never copy a URL from a sister artifact / earlier subagent without independently verifying.** A real example: `medium.com/plumhq/engineering-challenges-at-plum` was propagated through 3 artifacts before being caught dead — real URL is `…engineering-challenges-at-plum-40a8ed2dd3df`.
- Code, exact quotes from JDs, exact compensation strings — render normal, unchanged.
- Security/irreversible/legal warnings — drop caveman, render normal.
- Confidence labels stay: `(high)` / `(medium)` / `(low)`.

Length budget per artifact:
- `README.md` — 80 lines max
- `company.md` — 60 lines max
- `jd.md` — 50 lines max (verbatim raw JD doesn't count)
- `comp.md` — 30 lines max
- `interviewers/*.md` — 40 lines max each
- chat output — TL;DR + top 3 questions + open questions. No re-narration of the doc.

Caveman = compression, not info loss. Every fact survives. Only fluff dies.

## Workflow

### Step 1 — Bootstrap candidate context

Always read these two files first:
- `jobs/me/resume.md` — sid's experience, edge, tools
- `jobs/me/interests.md` — what makes a role a yes / no for him

If either file is missing, WebFetch `https://sidjainn.github.io` and seed them before continuing. If both exist, do not refresh unless the user explicitly asks ("refresh my resume", "pull my latest from the site"). Manual edits beat automatic refreshes.

### Step 2 — Parse the input

Extract:
- **Company name** (canonical — e.g. "Anthropic" not "anthropic.com")
- **Role title** (cleaned — e.g. "Senior Product Manager, Voice")
- **Location / remote policy**
- **Source URL** (if any — keep for the doc header)
- **Level signals** (Senior, Staff, Founding, IC vs Lead, etc.)

If the input is just a company name with no role, ask which role. If it's just a URL, fetch it first.

### Step 3 — Slugify and create the folder

`<company-slug>` = lowercase, hyphenated, no punctuation (e.g. `anthropic`, `eleven-labs`, `cresta-ai`).

- If `jobs/<company-slug>/` does **not** exist: create it with all subdirectories (`interviewers/`, `meetings/`).
- If it **already** exists: this is a re-run. Don't overwrite. Append a new dated section to README.md ("## Update — YYYY-MM-DD") and add new artifacts alongside existing ones (e.g. `comp-2026-04-26.md`). The point is to accumulate understanding.

### Step 3.5 — Auth-walled sources (Playwright escalation)

LinkedIn, X / Twitter, Glassdoor, Levels.fyi, and similar sources frequently block plain `WebFetch` with 403 / login walls. The project ships a Playwright MCP with a persistent Chrome profile at `~/.claude-playwright-profile` (resolved from `${HOME}` in `.mcp.json`) — log in once per source, sessions persist across runs.

Rules for subagents (especially `interviewer-profiler`, `comp-triangulator`, `company-researcher`):

1. **Try `WebFetch` first.** It's cheap and fast.
2. **On 403 / login wall / Cloudflare / "Sign in to view"** → escalate to Playwright MCP via the `mcp__plugin_playwright_playwright__browser_*` tools:
   - `browser_navigate` to the URL
   - `browser_snapshot` to capture rendered DOM
   - Parse the snapshot for the structured data needed (job titles, tenure, recent posts, comp bands, etc.)
3. **If Playwright also hits a login wall** → the user hasn't logged in to that source yet. Write the artifact with what's available, flag the gap explicitly: `⚠️ <source>: login required, persistent session not yet authenticated. Sid runs setup at .claude-playwright-profile/.`
4. **Volume discipline.** No more than ~5 LinkedIn profile fetches per `/job-research` invocation. LinkedIn rate-limits and flags accounts with bot-like access patterns. If more interviewers need profiling, batch across multiple sessions.
5. **Never use sid's daily-driver Chrome profile.** The dedicated `~/.claude-playwright-profile` is sandboxed — if that account gets restricted, sid's main account is untouched.
6. **Don't attempt to bypass paywalls** (Levels.fyi premium, LinkedIn Sales Navigator, Glassdoor's gated reports). Free tier only.
7. **ToS reality.** LinkedIn ToS prohibits automated access even from logged-in sessions. The escalation exists for low-volume professional research, not bulk scraping.

### Step 4 — Dispatch parallel subagents

Send all relevant subagents in **a single message** with multiple Agent tool calls so they run concurrently. Each one writes its own file and only its own file. Pass each agent the company name, role title, and explicit write-path for its artifact.

| Subagent | Writes | Job |
|---|---|---|
| **company-researcher** | `jobs/<slug>/company.md` | What they do (1-sentence, no jargon), stage/funding/last round, headcount trend (LinkedIn 6/12mo delta if accessible), open-roles count by function (try Greenhouse/Lever/Ashby JSON APIs first — `boards-api.greenhouse.io/v1/boards/<slug>/jobs`, `api.lever.co/v0/postings/<slug>`, `api.ashbyhq.com/posting-api/job-board/<slug>`), **recent exec posts/ships from the last 3-6 months specifically — current thinking, not historical career arcs. Capture verbatim post snippets w/ dates. CEO + CTO + key VPs.** Growth signals, risk signals (exec departures, Glassdoor trend, layoff chatter). **Every numerical claim must cite a source URL inline `[Source: ...]`. Cross-check funding totals across at least 2 of: Crunchbase, Tracxn, CB Insights, official press, TechCrunch/Entrackr/YourStory.** |
| **role-analyzer** | `jobs/<slug>/jd.md` | Raw JD + parsed must-haves, nice-to-haves, hidden asks (what the JD implies but doesn't say), and a fit assessment vs `jobs/me/resume.md` + `jobs/me/interests.md`. Use a reflection loop: extract → self-critique → refine. Cite specific resume bullets per requirement. **Do NOT make claims about the company's funding, stage, headcount, or competitive position — that's company-researcher's job. If the fit assessment needs stage context, note "see company.md §X" rather than inventing a number.** |
| **comp-triangulator** | `jobs/<slug>/comp.md` | Triangulate Levels.fyi + Glassdoor + h1bdata.info + the JD itself + any India-specific source if Bangalore-based. Disagreement between sources IS the signal — flag it. State confidence level. Note staleness. |
| **interviewer-profiler** | `jobs/<slug>/interviewers/<name>.md` per person | Only run if interviewer names are known. Tenure at this company, prior companies (their playbook), public writing/talks (their bar), what they've actually shipped at this co, axes sid can connect on. **Heaviest weight on last 3-6 months: their LI/X posts, what they're publicly talking about right now, recent shipped features they took credit for, recent talks/podcasts. Verbatim snippets w/ dates.** Historical career arc = context. Recent posts = signal of current thinking. **Source-staleness tiers (mandatory):** (a) **priority** = last 6mo (LI/X/blog/press), (b) **context** = 6mo–2yr, (c) **background only** = >2yr — must be labeled w/ year inline (e.g. "[Engineering Challenges at Plum (Jul 2020 — 6yr stale)](url)"). Morning-of checklists + prep docs lead w/ priority tier. Background tier = skim only, never drives interview strategy when priority signal exists. One file per person. Skip this subagent entirely if no names are known yet — don't fabricate. |
| **granola-puller** | `jobs/<slug>/meetings/<date>-<title>.md` per match | Use `mcp__granola__query_granola_meetings` with company name. For each match: pull transcript via `mcp__granola__get_meeting_transcript` AND full record via `mcp__granola__get_meetings` to capture meeting URL + metadata. Write focused summary (decisions, open threads, who-said-what, contradicts public narrative). **Header MUST include Granola deeplink** in form `_Granola: [<title>](https://notes.granola.ai/d/<meeting_id>)_` — fall back to whatever `share_url` / `url` / `link` field the `get_meetings` response surfaces; if none, write `_Granola ID: <meeting_id>_` so sid can paste into app. |

**Why subagents:** each one runs in its own context window and burns tokens on raw fetches that the main agent never has to load. The main agent only reads the final artifact files. This is what keeps the workflow scalable across many companies in one chat.

### Step 4.5 — Verification pass (MANDATORY before synthesis)

Before writing README.md, run a verification check on the artifacts. This step exists because **subagents without web access tend to hallucinate company facts** (funding amounts, headcount, valuations) when asked to reason about fit. Caught a real $95M-vs-$41M error on the Plum run.

Rules:

1. **Single source of truth per fact type.** `company.md` is the ONLY artifact allowed to make claims about funding, stage, valuation, headcount, customers, layoffs, exec changes, and product roadmap. `comp.md` is the only artifact allowed to make compensation claims. `jd.md` only makes claims about the JD itself + fit vs resume.md/interests.md. `interviewers/*.md` only make claims about the named individual.

2. **Cross-artifact consistency check.** Read `company.md` and `jd.md` (and any others). Identify any company-level claim made in `jd.md` (e.g. "$Xm raised", "Series Y", "N employees", "valued at $Z"). For each one, verify it matches `company.md` exactly. If `jd.md` makes a company-level claim that contradicts or doesn't appear in `company.md` → **delete or rewrite the claim in `jd.md`** before synthesizing. Mark the correction inline: `_[Corrected YYYY-MM-DD — original synthesis hallucinated <X>; verified against company.md §N.]_`

3. **Citation rule for the README.** Every numerical or factual claim in the README that isn't sid's own resume content must reference an artifact section: `Source: company.md §2`, `Source: comp.md`, `Source: interviewers/<name>.md`. If a claim exists in the README but the citation chain ends at a subagent's reasoning rather than an external source, demote it from a fact to a hedge ("appears to be", "estimated"). No bare numbers without provenance.

4. **Spot-verify one number externally.** Pick the single most load-bearing number in the brief (usually total funding or last-round size) and re-fetch the original source URL cited in `company.md` to confirm. If the source returns 403/404/captcha, find a second authoritative URL and confirm there. If two sources disagree, flag the disagreement in the README — do NOT pick one silently.

5. **Re-running on an existing folder?** Verification still mandatory. Compare new artifacts against existing README claims and flag any drift in a "## Update — YYYY-MM-DD: Corrections" section. Don't silently overwrite — sid needs to see what changed.

6. **Confidence labels.** When the README states a fact, label confidence inline where uncertainty matters: `(high confidence — primary source)`, `(medium — single secondary source)`, `(low — estimated)`. This is non-negotiable for funding numbers, comp numbers, and headcount.

If verification surfaces issues, fix them in the artifact files first (with inline correction notes), then synthesize. Never hide a correction inside the synthesis silently — sid needs to be able to trust the running doc as a memory.

### Step 5 — Synthesize the running doc

After all subagents complete, write `jobs/<slug>/README.md` (or append a dated section if it already exists) using **this exact template**:

```markdown
# <Company> — <Role>

_Last updated: <YYYY-MM-DD>. Source: <jd-url-or "pasted JD">_

## TL;DR
- **What they do:** <one sentence, no jargon>
- **Why this could be a fit for me:** <2 bullets, each tied to a specific item in interests.md>
- **Top risk:** <one bullet>
- **Recommendation:** investigate / pass / push hard

## Company snapshot
- Stage, funding, last round, valuation if known
- Headcount trend (6/12mo delta)
- Open roles count by function — where the money is going
- Recent exec posts / ships worth knowing about
- Growth signals
- Risk signals

## Role breakdown
- **Must-haves** (with my evidence per item from resume.md)
- **Nice-to-haves**
- **Hidden asks** (what the JD implies but doesn't say)
- **Fit score** — X/10 with reasoning

## Comp band
- Triangulated range with confidence + sources
- Red flags or gaps in the data

## Interviewers
- Per known interviewer: tenure, prior cos, public bar, connect-on axes — link to `interviewers/<name>.md`
- (Empty if no names known yet — flagged in Open Questions)

## Questions to ask (grouped by intent)

**"I've done the work" — show preparation**
- <3-5 questions that name a specific company move/post/launch and ask a smart follow-up>

**"De-risk my decision" — surface what could go wrong**
- <3-5 questions about runway, exec turnover, whether the role's mandate is real, what the last person in the seat did>

**"Real team problems" — what they're actually solving**
- <3-5 questions about the hardest current problem, where they're stuck, what's broken in the product, what they wish they'd hired for 6 months ago>

## Open questions
- <auto-populated — what we still don't know that would change the recommendation>

## Meeting context
- <links to summaries of any Granola notes, with 1-line each on what's relevant>

---
```

If this is a **re-run on an existing company**, do NOT replace the existing README. Append:

```markdown
## Update — YYYY-MM-DD

_Source: <new input>_

### What changed since last time
- <bullet>

### Updated recommendation
- <one line>

### New open questions
- <bullet>
```

### Step 6 — Ask for what's missing

After synthesis, use AskUserQuestion to fill the gaps the research couldn't reach. Common ones:
- Known interviewer names (only if not in the JD/recruiter email)
- Target comp / range sid is anchoring on
- Recruiter context (cold inbound vs sid applied vs warm intro)
- Anything sid already knows that didn't surface (e.g. "I talked to [ex-employee]")

Keep it to **2-4 questions max** — don't pepper. Skip this step entirely if everything important is already in the doc.

### Step 7 — Re-synthesize with the answers

After answers come back, update `README.md` (or the latest dated section) so the answers are folded in. Move resolved items out of "Open questions." Add new interviewers as their own files via the interviewer-profiler subagent if names just came in.

---

## Output format (what to show in chat)

Don't dump the whole README into chat. Show:

1. **Path to the folder** (so sid can open it)
2. **TL;DR section** copied verbatim from README
3. **Top 3 questions to ask** (pick the strongest from each intent group)
4. **Open questions** as a list with a "want me to dig further on any?" prompt

That's it. The full doc lives on disk where it belongs.

---

## Self-check before finishing

- [ ] Did I read `jobs/me/resume.md` and `jobs/me/interests.md` first?
- [ ] Did I dispatch subagents in **parallel** (single message, multiple Agent calls), not sequentially?
- [ ] Did each subagent write to its own file? Did the main agent read only those files (not raw web content)?
- [ ] **Did I run the Step 4.5 verification pass? Did I cross-check `jd.md` claims against `company.md` and reconcile?**
- [ ] **Does every numerical/factual claim in the README cite an artifact section (`Source: company.md §X`)?**
- [ ] **Did I spot-verify the single most load-bearing number against a primary source?**
- [ ] Is the recommendation tied to specific items in `interests.md`, not generic?
- [ ] Are the "questions to ask" specific enough that an interviewer could tell sid actually researched the company? (No generic "what's the team like?")
- [ ] If the company folder already existed, did I append rather than overwrite?
- [ ] Did I check Granola for prior context, even if the result is "no prior meetings"?
- [ ] Did I flag low-confidence comp data instead of hiding the uncertainty?
- [ ] **Did I add confidence labels (high / medium / low) to funding, comp, and headcount numbers?**
- [ ] **Does every external reference (post, article, Medium, LinkedIn post, tweet, podcast, press release, JD, blog) have an inline URL?** No bare titles. Morning-of checklists, "re-read X" items, verbatim quotes — all need clickable links.
- [ ] **Was every URL validated (WebFetch returns 200 or Playwright renders real content) before write?** No copy-pasted URLs from sister artifacts. No slug-only Medium URLs. No hallucinated career paths. Unverified links flagged with `_(link unverified — search ...)_`.

If any check fails, fix it before showing output.

---

## Updates on an already-tracked company

For post-meeting recaps, ad-hoc notes, or any signal that an existing `jobs/<slug>/` folder needs updating — **don't run this workflow**. Use the sibling `update-job` skill (`/update-job <slug-or-notes>`). It pulls fresh Granola, folds in sid's pasted notes, and appends a dated `## Update — YYYY-MM-DD` block to the folder's README without overwriting prior research.

This skill is the heavy first-pass flow only. If the company isn't tracked yet, do the full workflow above. If it is tracked, stop and route to `update-job`.

## Failure modes to avoid

- **Hallucinated company numbers.** Subagents without web access (especially role-analyzer) tend to make up funding, headcount, or valuation when they need stage context. The Step 4.5 verification pass catches this — never skip it. Real example: on the first Plum run, role-analyzer wrote "Plum raised ~$95M" when company.md (with sources) said $41M total. Corrected at sid's prompt.
- **Fabricating interviewer details.** If a name doesn't surface real public info, say so. Don't pad.
- **Generic questions.** "What's the culture like?" is useless. Every question should reference something specific to this company.
- **Overwriting the doc on re-run.** The doc is a memory. Append, don't replace.
- **Loading raw web fetches into the main context.** That's what subagents are for. If you're tempted to WebFetch from the main agent, dispatch a subagent instead.
- **Skipping Granola.** Even if there are no prior meetings, the explicit "no prior meetings found" tells sid he's going in cold.
- **Asking too many clarifying questions up front.** Do the research first, then ask only for what the research couldn't find.
