---
name: weekly-coach
description: Weekly reflection + next-week planning coach for sid. Triggers on /weekly-coach, "weekly review", "plan my week", "Monday planning", "let's reflect on the week", or when sid says he wants to think through the past week and plan ahead. Pulls annual charter, weekly to-do sheet (last 6 tabs), daily logs (last 14 days) via gdrive MCP, then surfaces multi-week patterns (avoidance, breakthroughs, charter drift), writes reflection + plan to weeks/<ISO-week>/, and asks 3 sharp coach questions back. Plan is rendered as a markdown table in sid's exact sheet column format so he can paste into a new sheet tab.
version: 1.0
author: sid
referenced_files:
  - .claude/context/my-priorities.md
  - .claude/context/my-team.md
sources:
  charter_doc_id: 1oKQnv4qZ6fQDl7-wWNbqhRrTeFQE1ATHjHqNBEgauUQ
  weekly_sheet_id: 1FjLBxDeZn0zWV4Wcp3XLautaQoJrN1_vleX9siijBlU
  daily_log_folder_id: 1q2SGgLg8ZadSpZ580vTg_eFmsHU1zLRG
---

# Weekly Coach Skill

## What this skill does

Runs sid's Monday morning ritual: reflect on the prior week, surface patterns across the last 6 weeks (not just one), name what he's avoiding, name what's breaking through, set intentions for the upcoming week aligned to his annual charter — output a markdown plan table he pastes into his sheet.

The doc is a memory, not a snapshot. Every week appends. Patterns surface over time.

## Core invariants

1. **Multi-week lookback always.** Single-week reflection is shallow — patterns only emerge across 4-6 weeks.
2. **Charter is the lens.** Every observation, every plan item maps to a focus area in the annual charter. Items that don't map = noise to challenge.
3. **Coach voice, not assistant voice.** Push back. Ask the question sid is avoiding. Name the pattern even when uncomfortable.
4. **Plan format = sheet format.** Detect columns from the most recent tab. Don't invent shape.
5. **Append, never overwrite.** `weeks/<ISO-week>/` per week. `logs/weekly-coach-log.md` summary log appends.

## Output style — caveman terse

Caveman voice for all artifacts and chat output:
- Drop articles, filler, pleasantries, hedging.
- Fragments OK. Pattern: `[thing] [signal] [meaning]. [what to do].`
- Tables and bullets > paragraphs.
- Quotes from sid's daily logs / sheet — render verbatim, unchanged.
- Coach questions — render normal (full sentences). Questions need to land.

Length budget:
- `reflection.md` — 60 lines max
- `plan.md` — table only + 5-line "intent for week" header
- `patterns.md` — 80 lines max (multi-week observations, citations to specific weeks/days)
- chat output — TL;DR + 3 patterns + 3 questions. Nothing more.

## Workflow

### Step 1 — Pull source data via gdrive MCP (parallel)

In a single message, read in parallel:

1. **Annual charter** — `mcp__gdrive__*` read doc id `1oKQnv4qZ6fQDl7-wWNbqhRrTeFQE1ATHjHqNBEgauUQ`. Extract the focus areas verbatim. These are the **pillars** every plan item must map to.

2. **Weekly to-do sheet** — list tabs of sheet id `1FjLBxDeZn0zWV4Wcp3XLautaQoJrN1_vleX9siijBlU`. Identify the last 6 weekly tabs by name (assume tab names are week identifiers). Read each tab's content. The most recent tab = prior week (the one being reflected on). The 5 before = lookback for patterns.

3. **Daily logs** — list files in folder id `1q2SGgLg8ZadSpZ580vTg_eFmsHU1zLRG`. Identify current month doc + previous month doc. Read both. Each doc has tabs per day. Focus parsing on the last 14 days.

If gdrive MCP is not yet authenticated, stop and tell sid to complete OAuth first. Don't proceed without source data.

### Step 2 — Detect sheet column schema

From the most recent tab, read the header row. Capture column names and order **exactly**. This becomes the plan table shape. Save to `weeks/<ISO-week>/patterns.md` so sid can sanity-check the schema parsing.

If the sheet has no obvious header row (sid uses the same row 1 as the first task), ask sid for column names once and cache the answer at the top of `patterns.md` for future runs.

### Step 3 — Pattern analysis (the coaching part)

Across the 6-week window, look for:

| Signal | What to detect | What it means |
|---|---|---|
| **Repeats** | Same/similar item rolled forward 2+ weeks | Avoidance candidate — surface w/ exact item text + week count |
| **Charter drift** | % of items per pillar / pillars w/ 0 items | Energy not aligned to stated priorities |
| **Breakthroughs** | Completed items that took multi-week prep, or wins called out in daily logs | What enabled it — replicate it |
| **Energy signals** | Reflection text in daily logs — recurring frustrations, fatigue, excitement | Where sid is alive vs depleted |
| **Cadence** | Days w/ no log entry, weeks w/ no movement on a pillar | Blind spots / quiet collapses |
| **Stakeholder pull** | Items tagged to specific people from `my-team.md` keep slipping | Misaligned commitment / capacity |

For each pattern found, cite specifics: "Item X appeared in W14, W15, W16, W17 — never closed" or "Pillar Y had zero entries 3 of last 4 weeks".

### Step 4 — Write reflection

`weeks/<ISO-week>/reflection.md`:

```markdown
# Reflection — Week <ISO> (covering <prior ISO>)

_Generated <YYYY-MM-DD>. Source: charter doc + last 6 sheet tabs + last 14 daily logs._

## Wins (last week)
- <bullet — verbatim if from sid's own log>

## Stuck-on
- <bullet — name it, w/ how many weeks rolled>

## Patterns (across last 6 weeks)
- **Avoidance hypothesis:** <one line, w/ evidence>
- **Breakthrough:** <one line, w/ what enabled it>
- **Drift:** <pillar: % of items / weeks w/ zero entries>
- **Energy:** <recurring signal from daily logs>

## Charter alignment scorecard

| Pillar | Items last week | Items last 6w | % of total | Trend |
|---|---|---|---|---|
| <pillar 1> | N | N | X% | up/flat/down |

## What I'd push sid on this week
- <one sharp observation tied to a real pattern, not generic>
```

### Step 5 — Write next-week plan (sheet format)

`weeks/<ISO-week>/plan.md`:

```markdown
# Plan — Week <ISO>

**Intent for the week:** <one sentence — what will be different vs last week>

**Pillars served:** <list>

## Items (paste this table into new sheet tab)

| <col1 from sheet> | <col2> | <col3> | ... |
|---|---|---|---|
| <item> | <value> | <value> | ... |
```

Rules for the items table:
- Use **exact column names + order** from Step 2.
- If sheet has a "focus area" or "pillar" column, map every row to a charter pillar. If not, add a `Pillar` column at the end as a coaching aid sid can drop before pasting.
- Keep ≤5 items per pillar by default. If more, force a cut conversation in Step 6.
- Carry forward repeats only if sid commits — if sid hasn't, recommend dropping.
- New items: each one must trace to a pillar + a reason (last week's pattern, blocker, breakthrough to extend).

### Step 6 — Coach questions (chat only, NOT in files)

Pick 3 questions from the patterns. Each must:
- Reference a **specific** observed pattern (not generic).
- Be uncomfortable — the one sid is most likely to deflect.
- End with a real choice: drop / commit / reframe.

Examples (replace w/ real patterns from this run):
- "Item X has rolled forward 4 weeks. Drop it, or block 3 hours Tuesday morning to finish — pick one."
- "Pillar Y had 1 item in 6 weeks despite being a top-3 charter focus. Is it actually a priority or aspirational?"
- "Win on Z came from <X behavior>. What stops you from doing that again next week?"

### Step 7 — Append summary to log

Append to `logs/weekly-coach-log.md`:

```markdown
## Week <ISO> — coaching

_Generated <YYYY-MM-DD>. Lookback: 6 weeks. Daily logs read: <N>._

- patterns_count: <N>
- next_week_items: <N>
- charter_areas_covered: <N>/<total pillars>
- avoidance_items: <N>
- breakthroughs: <N>
- intent: <one line>
```

This is what the PostHog hook scans — keep counts machine-extractable.

### Step 8 — Output to chat

Show ONLY:

1. Path: `weeks/<ISO-week>/`
2. **TL;DR** (3 bullets):
   - Last week wins
   - Last week stuck-on
   - Charter drift / standout pattern
3. **Top 3 patterns spotted** across 6-week lookback (1 line each)
4. **3 coach questions** from Step 6
5. Prompt: `Want to refine before I lock the plan? Cut anything? Push harder anywhere?`

Do NOT paste the full plan table or reflection inline. The files are the durable artifact; chat is the conversation.

### Step 9 — Iterate

After sid responds:
- Update `plan.md` table per his decisions.
- Re-print **only the updated table** for sheet paste.
- Update `logs/weekly-coach-log.md` if counts changed.

## Self-check before finishing

- [ ] Did I pull from all 3 sources (charter, sheet, daily logs) — not just one?
- [ ] Lookback covered 6 weeks, not just last week?
- [ ] Every pattern cited a specific week / day / item — no hand-wave generalities?
- [ ] Plan table columns match the sheet exactly?
- [ ] Every plan item maps to a charter pillar?
- [ ] 3 coach questions are uncomfortable and specific (not generic "what do you want to focus on")?
- [ ] Chat output is TL;DR + patterns + questions only — full plan stays in file?
- [ ] Summary appended to `logs/weekly-coach-log.md` with machine-readable counts?

If any check fails, fix before output.

## Failure modes to avoid

- **Single-week tunnel vision.** Patterns only emerge across 4-6 weeks. Don't shortcut.
- **Generic coaching.** "How do you feel about progress?" is useless. Every question references a real observed signal.
- **Overwriting the plan.** New week = new folder. The history is the value.
- **Inventing sheet columns.** Always detect from header row. Ask once if ambiguous, cache the answer.
- **Soft-pedaling avoidance.** If an item rolled 4+ weeks, name it. Sid hired the coach for honesty, not encouragement.
- **Skipping daily logs.** The sheet shows tasks; the daily log shows energy. Patterns need both.
- **Dumping the whole plan in chat.** The file is the artifact. Chat is the conversation.
