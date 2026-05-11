# Shopping Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two slash-command skills — `/advise` (pre-purchase advisor) and `/reccos` (proactive discovery) — that read sid's shared `shopping-context/` + order history + Gmail, score candidates against his values, render shortlists with cross-platform price-parity + card-discount math, and append machine-parseable log blocks that a PostHog hook captures.

**Architecture:** Skills are LLM-instruction documents (`SKILL.md`) — the LLM does the reasoning at runtime, no compiled code. Each skill reads from `.claude/skills/shopping-context/` (already drafted, gitignored) + Flipkart/Swiggy xlsx (already at fixed paths) + Gmail MCP + WebFetch/WebSearch. Advisor writes `.shopping/reccos/<slug>/{brief,shortlist,price-parity,verdict}.md`. Both skills append to `logs/shopping-*-log.md`. A new `posthog_shopping_capture.py` hook mirrors the existing `posthog_weekly_coach_capture.py` pattern: scans transcript for `/advise` or `/reccos`, parses the latest log block, emits a PostHog event, records idempotency in `logs/posthog-shopping-sent.log`.

**Tech Stack:** Markdown SKILL.md (YAML frontmatter), Python 3 hook (uses existing `_hook_common.py`), Gmail MCP (already configured), `openpyxl` (already used by skills via Bash), `WebFetch` + `WebSearch` tools. No new dependencies.

---

## Spec coverage map

| Spec section | Task # |
|---|---|
| `/advise` flow | 2, 3 |
| `/reccos` flow | 4, 5 |
| Cross-platform price-parity | 2 (step 5 of advise) |
| Card-discount layer | 2 (step 6 of advise) |
| Always-include-links rule | 2, 4 (rendered in templates) |
| Per-slug output dir (no date) | 2 (step 7 of advise) |
| Logs (append) | 2, 4 (log block template); 6 (hook parses) |
| PostHog hook | 6, 7 |
| Inventory write-back forbidden | 2 (invariants) |
| Ovo-veg default | 2, 4 (food-adjacent reccos) |
| Default to self+Bangalore | 2, 4 (defaults section) |
| Smoke tests | 3, 5, 8 |
| CLAUDE.md doc update | 9 |

---

## File Structure

| File | Purpose | Status |
|---|---|---|
| `.claude/skills/shopping-assist/SKILL.md` | `/advise` slash command, full instructions | **Create** |
| `.claude/skills/shopping-reccos/SKILL.md` | `/reccos` slash command, full instructions | **Create** |
| `.claude/skills/shopping-context/*.md` | 5 context files (profile/inventory/interests/budget-rules/data-sources) | Already drafted (gitignored) |
| `.claude/hooks/posthog_shopping_capture.py` | PostHog capture hook | **Create** |
| `.claude/hooks/tests/test_posthog_shopping_capture.py` | Unit tests for hook log-block parser | **Create** |
| `.claude/settings.json` | Wire new hook into PostToolUse + Stop | **Modify** |
| `.claude/CLAUDE.md` | Document the new skills in the "How this system works" section + Key files table | **Modify** |
| `logs/shopping-advise-log.md` | Append-only log of /advise runs (gitignored) | Created on first run |
| `logs/shopping-reccos-log.md` | Append-only log of /reccos runs (gitignored) | Created on first run |
| `logs/posthog-shopping-sent.log` | Idempotency ledger for PostHog events (gitignored) | Created on first event |

Note: `.shopping/reccos/<slug>/` per-advise output dirs are created at runtime by the skill itself, not part of repo structure.

---

## Task 1: Verify preconditions

**Files:** read-only checks

- [ ] **Step 1: Verify context files exist**

Run: `ls .claude/skills/shopping-context/`
Expected: `budget-rules.md  data-sources.md  interests.md  inventory.md  profile.md`

If any missing — STOP. Re-run the brainstorming session to draft the missing file before continuing.

- [ ] **Step 2: Verify gitignore entries in place**

Run: `grep -E 'shopping-context|\.shopping' .gitignore`
Expected output:
```
.claude/skills/shopping-context/
.shopping
/.shopping/
```

If missing — add to `.gitignore` and commit before proceeding.

- [ ] **Step 3: Verify order-history xlsx paths**

Run:
```
ls "/Users/sid-j/Documents/Claude/Projects/flipkart orders data/Flipkart_Orders_2025-2026.xlsx" \
   "/Users/sid-j/Documents/Claude/Projects/swiggy-exploration/Swiggy_Orders_Last_6_Months.xlsx"
```
Expected: both files print without `No such file or directory` error.

If missing — update `data-sources.md` to point to the correct paths before continuing.

- [ ] **Step 4: Verify openpyxl + Gmail MCP available**

Run: `python3 -c "from openpyxl import load_workbook; print('ok')"`
Expected: `ok`

Run: `grep -A2 '"gmail"' .claude/settings.json`
Expected: shows the Gmail MCP entry.

If openpyxl missing: `pip3 install openpyxl --break-system-packages`.

- [ ] **Step 5: No commit (preconditions only)**

---

## Task 2: Create `shopping-assist/SKILL.md`

**Files:**
- Create: `.claude/skills/shopping-assist/SKILL.md`

- [ ] **Step 1: Create the skill file**

Write `.claude/skills/shopping-assist/SKILL.md` with the following content (verbatim — every section is required):

````markdown
---
name: shopping-assist
description: Pre-purchase advisor for sid. Triggers on /advise, "advise me on …", "what should I buy for …", "help me pick a …", "/shop", or any explicit pre-purchase ask where the user names a product category they're about to buy. Reads .claude/skills/shopping-context/ + Flipkart/Swiggy xlsx + Gmail to ground recommendations in sid's values (highest-value, nature-friendly, user-friendly, positive reviews) + household + inventory + budget. Outputs ranked shortlist with cross-platform price parity, card-discount math, working links to manufacturer/retailer/Reddit/YouTube. Writes `.shopping/reccos/<slug>/` (gitignored). Appends to `logs/shopping-advise-log.md` for PostHog capture.
version: 1.0
author: sid
---

# Shopping Advisor Skill

## What this skill does

When sid says "I want to buy X" or invokes `/advise <thing>`, this skill:

1. Reads his shared context (profile, inventory, interests, budget-rules, data-sources).
2. Pulls relevant order history (Flipkart xlsx, Swiggy xlsx if food-adjacent, Gmail for everything else).
3. Asks 2-4 sharp clarifying questions inline.
4. Researches 5-8 candidates on the open web.
5. Filters to a 3-item shortlist on disqualifiers (out-of-budget / out-of-stock / banned brand or category).
6. Scores each candidate on 5 dimensions: value, nature-friendly, user-friendly, reviews, budget-fit.
7. Cross-platform price parity check on at least 3 retailers.
8. Card-discount layer using sid's owned cards (and flags borrowable-card opportunities).
9. Writes 4 markdown artifacts under `.shopping/reccos/<slug>/`.
10. Renders a terse inline verdict.
11. Appends a machine-parseable log block to `logs/shopping-advise-log.md`.

## Core invariants

1. **One product per `/advise`.** If sid asks for multiple things, split into separate runs.
2. **Always cite links.** Every candidate, every review citation MUST be a clickable URL. No bare brand names.
3. **Cross-platform price parity is mandatory.** Min 3 retailers checked per shortlist item.
4. **Card-discount layer is mandatory.** Effective price after best owned card is the headline number.
5. **Default to "for self, in Bangalore".** Explicit override required for Agra/dad/friends.
6. **Ovo-veg default for food-adjacent.** Eggs OK; no meat/fish/seafood.
7. **No inventory write-back.** Recommendation ≠ purchase.
8. **Slug = kebab-case product name.** No date prefix. Re-running same slug overwrites.
9. **Logs append; never overwrite.** Each run = one block.
10. **Caveman voice in chat output.** Files can be normal prose.

## Output style — caveman terse

Same voice convention as weekly-coach + email-triage skills:
- Drop articles, filler, pleasantries, hedging in chat output.
- Fragments OK. Pattern: `[thing] [signal] [meaning]. [next step].`
- Tables + bullets > paragraphs.
- File artifacts can be normal prose.

Length budget:
- chat output: top pick + 2 alts + 1-line per dim score + best-card line + log path. Nothing more.
- `brief.md`: ≤30 lines.
- `shortlist.md`: 3 items × ~15 lines each = ≤60 lines.
- `price-parity.md`: one table per shortlist item.
- `verdict.md`: ≤25 lines.

## Workflow

### Step 1 — Read all context

Read every file in `.claude/skills/shopping-context/`:

- `profile.md` — identity, households (Bangalore + Agra), values, payment methods, no-go list
- `inventory.md` — durable goods owned, tagged by address
- `interests.md` — hobbies, curiosities, active to-dos with purchase implications
- `budget-rules.md` — per-category ceilings + BOCO caps + no-go list
- `data-sources.md` — xlsx paths + Gmail query template + refresh recipes

If `profile.md` is missing — STOP and tell sid to scaffold his context before running advise.

### Step 2 — Read relevant order history

Always read:

- Flipkart xlsx (path in `data-sources.md`) — all 100+ orders, look for prior purchases in the same category
- Recent weekly reflections (`weeks/<latest-ISO>/reflection.md`) — confirms current need + intent

Conditionally read:

- Swiggy xlsx — if asking about food/restaurants/cuisine, kitchen tools, eating-out patterns
- Gmail via MCP — search recent orders across Amazon, Myntra, Blinkit, Zepto, IKEA, Apple, etc. Use the query template in `data-sources.md`. Window = last 12mo by default; tighten to 90d for "what did I buy recently" framing.

### Step 3 — Clarify (2-4 questions)

Ask inline via `AskUserQuestion` if the answers aren't already in the user's invocation prompt:

- **Budget ceiling** — anchor to `budget-rules.md` defaults but confirm
- **Deadline** — same-day / week / month / no rush
- **Deal-breakers** — colors, sizes, brand preferences/aversions
- **Aesthetic constraints** — if applicable (apparel, home goods)

Skip any question already answered in the prompt. Cap at 4.

### Step 4 — Web research

Use `WebSearch` to discover 5-8 candidates. Use `WebFetch` to confirm specs + reviews. Prefer these sources (in order):

1. **Manufacturer page** — official specs, materials, warranty
2. **Reddit (r/IndiaInvestments, r/IndianGaming, r/cycling, r/MaleFashionAdvice, etc.)** — real usage feedback
3. **YouTube product reviews** — for chairs, electronics, treks
4. **TheWirecutter / Wired** — international neutrality (filter for India availability)
5. **Indian retailer reviews** — Flipkart + Amazon, sort recent + verified

Avoid: AI-generated listicle blogs, affiliate spam, content-farm review sites.

Filter the 5-8 down to 3 by disqualifying:
- Over budget (`budget-rules.md` ceilings)
- Out of stock at all 3+ retailers
- Banned brand or category (`profile.md ## No-go`)

### Step 5 — Score each shortlist item (5-dim rubric)

Each candidate scored 1-5 on:

| Dim | Definition |
|---|---|
| **Value** | Price vs durability, lifespan, TCO |
| **Nature** | Materials, repairability, shipping footprint, brand ethics |
| **User-friendly** | Ergonomics, fit for sid's specific use-case (cite inventory pain point if relevant) |
| **Reviews** | Cross-source sentiment, weighted to recent + verified-purchase |
| **Budget fit** | vs `budget-rules.md` category ceiling |

Each score MUST have a 1-line reason + at least one link. Render in `shortlist.md` as a table.

Weighted total = `0.25·value + 0.20·nature + 0.25·user-friendly + 0.20·reviews + 0.10·budget`. Tunable if sid says e.g. "I'll pay more, give me the most ergonomic" — adjust weights inline and note the adjustment in `verdict.md`.

### Step 6 — Cross-platform price parity

For each shortlist item check 3-4 retailers. Always:
- Flipkart
- Amazon.in
- Brand-direct (if brand sells direct)
- One specialist retailer based on category (Croma / Decathlon / Reliance Digital / Pepperfry / Urban Ladder / Nykaa / Decathlon / etc.)

Record per retailer: listed price, current discount, total after discount (pre-card). Note stock status.

Render `price-parity.md` as one table per shortlist item:

```markdown
## <item name>

| Retailer | Listed | Discount | Pre-card price | Stock | Link |
|---|---|---|---|---|---|
| Flipkart | ₹15,999 | -₹2,000 (12%) | ₹13,999 | In stock | https://... |
| Amazon.in | ₹14,499 | — | ₹14,499 | In stock | https://... |
| brand.com | ₹16,000 | — | ₹16,000 | In stock | https://... |
| Pepperfry | ₹17,499 | -₹3,500 | ₹13,999 | Limited | https://... |
```

### Step 7 — Card-discount layer

For each (retailer, owned card) pairing in `profile.md ## Payment methods`, compute effective price:

- **Flipkart + Flipkart Axis Bank Credit Card** → typically 5% cashback → subtract
- **Swiggy/Instamart + Swiggy HDFC Credit Card** → typically 10% off → subtract
- **Amazon + Amazon Pay ICICI (if borrowable)** → 5% Prime cashback — flag as borrowable opportunity only when material
- **Anywhere + SBI Rupay Debit** — UPI rewards, network offers — apply if known offer

Render in `price-parity.md` as an "effective price" column appended to the table. Bold the row with the lowest effective price.

**Borrowable-card rule:** if a borrowable card (not owned) materially changes the winner (≥5% difference vs best owned card), mention it as a single line in `verdict.md`. Do NOT plan around it as the primary path.

### Step 8 — Write artifacts

Slug = kebab-case of product noun. Examples: `office-chair`, `running-shoes`, `wired-headphones`, `cookware-set`, `kindle-replacement`.

If `.shopping/reccos/<slug>/` already exists — **overwrite** all four files (no archival). Sid keeps history elsewhere if he wants it.

```
.shopping/reccos/<slug>/
├── brief.md          # need + context + clarifying answers
├── shortlist.md      # 3 candidates × 5-dim scores w/ links
├── price-parity.md   # one table per item
└── verdict.md        # top pick + best card + effective price + 2 alts + reasoning
```

`brief.md` template:
```markdown
# Brief — <product>

**Date:** <YYYY-MM-DD>
**Slug:** <slug>
**Asked for:** self (Bangalore) / for <other>
**Use case:** <one-liner from sid>
**Budget ceiling:** ₹<n>
**Deadline:** <none / by date>
**Constraints:** <list>

## Prior purchases in this category (from order history)

- <item 1, brand, date, ₹, source>
- ...

## Current pain point (from inventory.md)

<copy from inventory.md if there's a matching entry, else "n/a">
```

`verdict.md` template:
```markdown
# Verdict — <product>

**Top pick:** [<brand model>](<manufacturer-url>)

- **Buy at:** <retailer> · ₹<effective-price> (after <card name>) · [link](<retailer-url>)
- **List price:** ₹<list> · **Discount:** ₹<disc> · **Card cashback:** -₹<cashback>
- **Why this:** <2-3 lines on value + user-fit + nature score>
- **Reviews:** [<source>](<url>) · [<source>](<url>)

## Alternatives

1. [<brand model>](<url>) — ₹<eff> at <retailer>. Win condition: <when this beats top pick>
2. [<brand model>](<url>) — ₹<eff> at <retailer>. Win condition: <...>

## Borrowable-card opportunity (if any)

<one line — "if you can borrow an HDFC Regalia, Amazon drops to ₹X (₹Y less)" — else omit section>

## Weight tuning

Default weights used / Adjusted weights: <show the deltas if any>
```

### Step 9 — Render inline (chat)

Print top pick + 2 alts + best card + effective price + path to `.shopping/reccos/<slug>/`. Keep terse. Example:

```
office-chair — top: Featherlite Optima Plus @ ₹13,499 amazon.in (SBI Rupay UPI offer).
alt1: Wakefit Ergo X ₹12,799 wakefit-direct. alt2: Green Soul Vienna ₹14,200 flipkart (+Axis 5%).
links + scores: .shopping/reccos/office-chair/verdict.md
```

### Step 10 — Append log block

Append the following block (verbatim format — the hook parses it) to `logs/shopping-advise-log.md`. Create the file if it does not exist.

```markdown
## <slug> — advise

_Generated <YYYY-MM-DD HH:MM>. Caveman log._

- slug: <slug>
- top_pick: "<brand model>" | <manufacturer-url>
- retailer: <retailer-domain>
- best_card: <card name>
- list_price: <int rupees>
- effective_price: <int rupees>
- alts: ["<alt1 brand model>", "<alt2 brand model>"]
- values_winner: <value | nature | user-friendly | reviews | budget-fit>
- recco_path: .shopping/reccos/<slug>/
```

Field rules (must be traceable for the hook):
- `slug`: lowercase kebab-case, no spaces, no `/`
- `top_pick`: quoted string + ` | ` + URL
- `retailer`: bare domain (`amazon.in`, `flipkart.com`, `wakefit.co`, etc.)
- `best_card`: exact name from `profile.md ## Payment methods`
- `list_price` + `effective_price`: integer rupees, no decimals, no commas
- `alts`: JSON-ish list of 0-2 strings
- `values_winner`: one of the five rubric dims
- `recco_path`: relative path from repo root

## Failure modes to avoid

- **Vibes scoring.** Every 1-5 score needs an external citation + 1-line reason.
- **Bare brand names.** Always link. If you can't find a working link, drop the candidate.
- **Single-retailer recco.** Min 3 retailers in price-parity. Non-negotiable.
- **Card math hand-waving.** Show the cashback subtraction explicitly.
- **Slug drift.** If you change the slug between brief.md and verdict.md, the hook breaks. Pick once, use everywhere in the run.
- **Writing to inventory.md.** Don't. Sid updates inventory manually post-purchase.
- **Multi-product bundling.** One product per /advise. If sid asks for "chair + monitor", suggest two separate runs.
- **Skipping the log block.** Without it, the PostHog hook never fires.

## Self-check before finishing

- [ ] Read all 5 context files this run?
- [ ] Read Flipkart xlsx + Swiggy xlsx (if relevant) + Gmail (if categories beyond Flipkart/Swiggy apply)?
- [ ] 3 shortlist items, not 5+?
- [ ] Each item scored on all 5 dims with citation links?
- [ ] Price-parity table has ≥3 retailers per item?
- [ ] Card-discount layer applied + best card surfaced?
- [ ] All 4 artifacts written under `.shopping/reccos/<slug>/`?
- [ ] Log block appended to `logs/shopping-advise-log.md` in exact format?
- [ ] Inline output is caveman-terse, ≤8 lines?
- [ ] Did not write to `inventory.md`?
````

- [ ] **Step 2: Verify the file exists + frontmatter parses**

Run:
```
ls -la .claude/skills/shopping-assist/SKILL.md
head -5 .claude/skills/shopping-assist/SKILL.md
```
Expected: file exists; first lines show `---` + `name: shopping-assist` + `description:` + `version: 1.0` + `author: sid` + `---`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/shopping-assist/SKILL.md
git commit -m "$(cat <<'EOF'
feat(shopping): add shopping-assist skill for pre-purchase advisor

/advise — reads shared context, order history, Gmail; scores 3 candidates
on value/nature/user-friendly/reviews/budget; cross-platform price parity
+ card-discount math; writes .shopping/reccos/<slug>/ + appends log block.

Generated-By: PostHog Code
Task-Id: 162eedf3-ab94-4458-9cb7-2aa7ffbd0b0c
EOF
)"
```

---

## Task 3: Smoke-test `shopping-assist`

**Files:** read-only verification of skill behavior

- [ ] **Step 1: Pick a real test scenario**

Sid mentioned office-chair pain point in the original brainstorm (now resolved with Wakefit, but a good smoke-test target). Use a new scenario instead — sid's deferred "buy cookware" item from W20 patterns:

Prompt to test: `/advise cookware-set (basic Indian veg kitchen — kadai + tawa + 2 pots + 1 pressure cooker, mid-budget)`

- [ ] **Step 2: Invoke the skill in a fresh Claude Code session**

Open a new session in this repo, paste the test prompt. Verify:
- Skill triggers (not job-research or email-triage)
- Reads `shopping-context/*` (visible in tool calls)
- Asks 2-4 clarifying questions
- Returns 3-candidate shortlist
- Each has manufacturer + retailer + 1 social link
- Price-parity covers ≥3 retailers per item
- Card-discount math visible
- 4 files written to `.shopping/reccos/cookware-set/`

- [ ] **Step 3: Verify artifacts on disk**

```bash
ls -la .shopping/reccos/cookware-set/
```
Expected:
```
brief.md
shortlist.md
price-parity.md
verdict.md
```

```bash
grep -c "https" .shopping/reccos/cookware-set/verdict.md
```
Expected: ≥4 (manufacturer + retailer + 2 review links minimum)

- [ ] **Step 4: Verify log block appended**

```bash
tail -15 logs/shopping-advise-log.md
```
Expected: a `## cookware-set — advise` block with all the required fields (slug, top_pick, retailer, best_card, list_price, effective_price, alts, values_winner, recco_path).

- [ ] **Step 5: If any step fails, edit `SKILL.md` to fix**

Common fixes:
- If links missing → strengthen Step 8 of skill workflow
- If price-parity skipped → strengthen invariant #3 wording
- If log block malformed → tighten Step 10 field rules

- [ ] **Step 6: No commit yet** — proceed to Task 4 and bundle skills together.

---

## Task 4: Create `shopping-reccos/SKILL.md`

**Files:**
- Create: `.claude/skills/shopping-reccos/SKILL.md`

- [ ] **Step 1: Create the skill file**

Write `.claude/skills/shopping-reccos/SKILL.md`:

````markdown
---
name: shopping-reccos
description: Proactive product-discovery skill for sid. Triggers on /reccos, /reccos <topic>, "recommend me something", "what should I buy", "surprise me with products", "I'm bored, what's on my radar", or any open-ended discovery ask. Reads .claude/skills/shopping-context/ (focus on interests + inventory gaps + recent order patterns) to surface 3-5 things sid would plausibly want — tagged [upgrade] / [gap] / [interest-match] / [swap-from-current]. Each item: 1-line why-for-you + 1 alt + values fit. Always includes manufacturer + retailer + 1 social link. Lightweight (no file artifacts); deep-dive any pick via /advise <slug>. Appends to `logs/shopping-reccos-log.md` for PostHog capture.
version: 1.0
author: sid
---

# Shopping Discovery Skill

## What this skill does

Surfaces 3-5 products sid would plausibly want, with rationale tags. Lightweight — no per-item file dump. If a recco resonates, sid runs `/advise <slug>` to deep-dive.

## Core invariants

1. **Lightweight output.** 3-5 items, ~3 lines each. No per-item artifact files.
2. **Tag every item.** One of: `[upgrade]`, `[gap]`, `[interest-match]`, `[swap-from-current]`.
3. **Always link.** Manufacturer + retailer + 1 social proof (Reddit / Twitter/X / YouTube / blog).
4. **Default ovo-veg + Bangalore + for self.**
5. **No write to inventory.md or `.shopping/reccos/`.** Discovery is ephemeral. Only the log block persists.
6. **Caveman voice.**

## Output style

Length budget:
- 3-5 items × ~3 lines = ≤20 lines total in chat
- Log block: ≤15 lines

## Workflow

### Step 1 — Read context

Same 5 files as `shopping-assist`. Focus on:
- `interests.md` — hard interests + active curiosities + active to-dos with purchase implications
- `inventory.md` — items showing wear ("must replace", "feels like a problem") + gaps + recent dates
- `weeks/<latest-ISO>/reflection.md` — "stuck-on" items that might be unblocked with a purchase

### Step 2 — Parse topic arg (optional)

If sid invoked `/reccos kitchen` or `/reccos books`, scope to that topic. Without arg = broad scan across all charter pillars.

Common topics: `kitchen`, `books`, `tech`, `home`, `apparel`, `music`, `endurance`, `trek`, `office`.

### Step 3 — Surface 3-5 candidates

Each must fit one tag:

| Tag | Trigger condition |
|---|---|
| `[upgrade]` | Inventory item with stated pain or ≥2yr age + wear signal |
| `[gap]` | Charter / interest pillar that lacks a corresponding owned item |
| `[interest-match]` | Recent daily-log mention of curiosity ("excited to try X", "want to explore Y") |
| `[swap-from-current]` | Repeat-buy in xlsx that could be replaced by a better-aligned alternative |

Filter: skip if in `profile.md ## No-go` or if budget-rules ceiling makes it implausible. Don't surface things sid clearly already owns.

### Step 4 — Render

For each item, in chat output:

```markdown
N. [<tag>] **<product type — brand model>** — <one-line why for sid>
   - alt: <brand model>
   - top dim: <value | nature | user-friendly | reviews | budget-fit>
   - links: [mfr](<url>) · [retailer](<url>) · [<social-source>](<url>)
```

End with: `Deep-dive any pick: /advise <slug>` and list the 3-5 slug candidates.

### Step 5 — Append log block

Append to `logs/shopping-reccos-log.md`:

```markdown
## <topic-or-broad> — reccos

_Generated <YYYY-MM-DD HH:MM>. Caveman log._

- topic: <kitchen | books | tech | home | apparel | broad | ...>
- count: <N>
- slugs: ["<slug1>", "<slug2>", "<slug3>"]
- tags: ["upgrade", "interest-match", "gap", ...]
- top_reason: "<one-line strongest pick rationale>"
```

Field rules:
- `topic`: bare lowercase token or `broad`
- `count`: integer
- `slugs`: JSON-ish list, kebab-case
- `tags`: JSON-ish list, parallel to slugs (same order)
- `top_reason`: quoted string, ≤200 chars

## Failure modes to avoid

- **Surfacing things sid owns.** Read inventory.md first.
- **Generic listicle vibes.** Each item must trace back to a specific signal in his context (cite the file + line in the why).
- **No links.** Always link.
- **Skipping the tag.** Tag is required for every item.
- **Skipping the log block.** Without it, PostHog hook never fires.

## Self-check before finishing

- [ ] Read all 5 context files this run?
- [ ] Each item has a tag from the allowed set?
- [ ] Each item has a 1-line why that cites a real signal?
- [ ] Each item has manufacturer + retailer + 1 social link?
- [ ] 3-5 items, not 6+?
- [ ] Log block appended in exact format?
- [ ] No file artifacts written to `.shopping/reccos/`?
````

- [ ] **Step 2: Verify file exists**

Run: `head -5 .claude/skills/shopping-reccos/SKILL.md`
Expected: frontmatter with `name: shopping-reccos`.

- [ ] **Step 3: No commit yet** — bundle with Task 5 smoke test.

---

## Task 5: Smoke-test `shopping-reccos`

- [ ] **Step 1: Invoke**

In a fresh Claude Code session: `/reccos` (no topic) and separately `/reccos endurance`.

- [ ] **Step 2: Verify outputs**

Both invocations should:
- Render 3-5 items in chat
- Each item tagged + has manufacturer/retailer/social link
- No files written under `.shopping/reccos/`
- Log block appended to `logs/shopping-reccos-log.md`

```bash
ls .shopping/reccos/ 2>&1 | grep -v cookware
```
Expected: empty (only Task 3's `cookware-set` should exist from the prior smoke test).

```bash
tail -20 logs/shopping-reccos-log.md
```
Expected: two `## <topic> — reccos` blocks with all required fields.

- [ ] **Step 3: Fix issues, then commit both skills together**

```bash
git add .claude/skills/shopping-assist/SKILL.md .claude/skills/shopping-reccos/SKILL.md
git commit -m "$(cat <<'EOF'
feat(shopping): add shopping-assist + shopping-reccos skills

shopping-assist (/advise): pre-purchase advisor — 3 candidates × 5-dim
scores, cross-platform price parity, card-discount math, writes
.shopping/reccos/<slug>/.

shopping-reccos (/reccos): proactive discovery — 3-5 tagged items
([upgrade]/[gap]/[interest-match]/[swap-from-current]). No file
artifacts; deep-dive via /advise.

Both append machine-parseable log blocks to logs/shopping-*-log.md.

Generated-By: PostHog Code
Task-Id: 162eedf3-ab94-4458-9cb7-2aa7ffbd0b0c
EOF
)"
```

---

## Task 6: Create PostHog capture hook

**Files:**
- Create: `.claude/hooks/posthog_shopping_capture.py`

- [ ] **Step 1: Write the hook**

Create `.claude/hooks/posthog_shopping_capture.py` with the following content (mirrors `posthog_weekly_coach_capture.py` exactly except for command regex + log path + event name + field set):

```python
#!/usr/bin/env python3
"""Send `shopping_advise_run` or `shopping_reccos_run` event to PostHog.

Detects invocation by scanning the transcript for /advise or /reccos in user msgs.
Extracts metric fields from the latest section of logs/shopping-advise-log.md
or logs/shopping-reccos-log.md.
"""

from __future__ import annotations

import os
import re
import sys

from _hook_common import (
    PROJECT_ROOT,
    date_props,
    debug_log,
    idempotency_check,
    idempotency_record,
    iter_user_messages,
    load_project_env,
    posthog_capture,
    read_stdin_payload,
    resolve_transcript,
    should_run,
)

HOOK_NAME = "posthog-shopping"
SENT_LOG = PROJECT_ROOT / "logs" / "posthog-shopping-sent.log"
ADVISE_LOG = PROJECT_ROOT / "logs" / "shopping-advise-log.md"
RECCOS_LOG = PROJECT_ROOT / "logs" / "shopping-reccos-log.md"

ADVISE_CMD_REGEX = r"/advise\b"
RECCOS_CMD_REGEX = r"/reccos\b"
ANY_CMD_REGEX = r"/(?:advise|reccos)\b"


def _scan_command(transcript) -> tuple[str, str]:
    """Return (mode, slug_or_topic_hint). mode in {'advise','reccos',''}."""
    mode = ""
    hint = ""
    for blocks in iter_user_messages(transcript):
        joined = "\n".join(blocks)
        if re.search(ADVISE_CMD_REGEX, joined, re.IGNORECASE):
            mode = "advise"
            m = re.search(r"/advise\s+([\w-]+)", joined, re.IGNORECASE)
            if m:
                hint = m.group(1).lower()
        elif re.search(RECCOS_CMD_REGEX, joined, re.IGNORECASE):
            mode = "reccos"
            m = re.search(r"/reccos\s+([\w-]+)", joined, re.IGNORECASE)
            if m:
                hint = m.group(1).lower()
    return mode, hint


def _grab_int(block: str, key: str) -> int:
    m = re.search(rf"{key}\s*:\s*(\d+)", block, flags=re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _grab_string(block: str, key: str, max_len: int = 400) -> str:
    m = re.search(rf"{key}\s*:\s*(.+)", block, flags=re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1).strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return val[:max_len]


def _grab_list(block: str, key: str) -> list[str]:
    m = re.search(rf"{key}\s*:\s*\[([^\]]*)\]", block, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    items = [x.strip().strip('"').strip("'") for x in raw.split(",")]
    return [x for x in items if x]


def _parse_advise_log(path) -> dict:
    result = {
        "slug": "",
        "top_pick": "",
        "retailer": "",
        "best_card": "",
        "list_price": 0,
        "effective_price": 0,
        "alts": [],
        "values_winner": "",
        "recco_path": "",
    }
    if not os.path.exists(path):
        return result
    try:
        text = open(path).read()
    except Exception:
        return result

    sections = list(re.finditer(r"^## (\S+)\s+\u2014\s+advise", text, flags=re.MULTILINE))
    if not sections:
        sections = list(re.finditer(r"^## (\S+)\s+(?:-|\u2014)\s+advise", text, flags=re.MULTILINE))
    if not sections:
        return result

    last = sections[-1]
    result["slug"] = last.group(1)
    next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
    block_end = last.end() + next_header.start() if next_header else len(text)
    block = text[last.start():block_end]

    result["top_pick"] = _grab_string(block, "top_pick")
    result["retailer"] = _grab_string(block, "retailer", 80)
    result["best_card"] = _grab_string(block, "best_card", 100)
    result["list_price"] = _grab_int(block, "list_price")
    result["effective_price"] = _grab_int(block, "effective_price")
    result["alts"] = _grab_list(block, "alts")
    result["values_winner"] = _grab_string(block, "values_winner", 50)
    result["recco_path"] = _grab_string(block, "recco_path", 300)
    return result


def _parse_reccos_log(path) -> dict:
    result = {
        "topic": "",
        "count": 0,
        "slugs": [],
        "tags": [],
        "top_reason": "",
    }
    if not os.path.exists(path):
        return result
    try:
        text = open(path).read()
    except Exception:
        return result

    sections = list(re.finditer(r"^## (\S+)\s+\u2014\s+reccos", text, flags=re.MULTILINE))
    if not sections:
        sections = list(re.finditer(r"^## (\S+)\s+(?:-|\u2014)\s+reccos", text, flags=re.MULTILINE))
    if not sections:
        return result

    last = sections[-1]
    next_header = re.search(r"^## ", text[last.end():], flags=re.MULTILINE)
    block_end = last.end() + next_header.start() if next_header else len(text)
    block = text[last.start():block_end]

    result["topic"] = _grab_string(block, "topic", 60)
    result["count"] = _grab_int(block, "count")
    result["slugs"] = _grab_list(block, "slugs")
    result["tags"] = _grab_list(block, "tags")
    result["top_reason"] = _grab_string(block, "top_reason", 250)
    return result


def main() -> int:
    payload = read_stdin_payload()
    load_project_env()

    transcript = resolve_transcript(payload)
    if not should_run(payload, hook_name=HOOK_NAME, transcript=transcript, command_regex=ANY_CMD_REGEX):
        return 0
    if transcript is None:
        return 0

    mode, hint = _scan_command(transcript)
    if not mode:
        return 0

    props_date = date_props()

    if mode == "advise":
        counts = _parse_advise_log(str(ADVISE_LOG))
        slug = counts.get("slug") or hint or ""
        if not slug:
            return 0
        sent_key = f"{props_date['date']} {props_date['time']} shopping-advise {slug}"
        if idempotency_check(SENT_LOG, sent_key):
            return 0
        debug_log(
            HOOK_NAME,
            f"capturing shopping_advise_run slug={slug} retailer={counts.get('retailer')} "
            f"eff={counts.get('effective_price')} card={counts.get('best_card')}",
        )
        ok = posthog_capture(
            "shopping_advise_run",
            {
                **props_date,
                "slug": slug,
                "top_pick": counts.get("top_pick") or None,
                "retailer": counts.get("retailer") or None,
                "best_card": counts.get("best_card") or None,
                "list_price": int(counts.get("list_price") or 0),
                "effective_price": int(counts.get("effective_price") or 0),
                "savings": int(counts.get("list_price") or 0) - int(counts.get("effective_price") or 0),
                "alts": counts.get("alts") or [],
                "alts_count": len(counts.get("alts") or []),
                "values_winner": counts.get("values_winner") or None,
                "recco_path": counts.get("recco_path") or None,
            },
        )
        if ok:
            idempotency_record(SENT_LOG, sent_key)
        return 0

    if mode == "reccos":
        counts = _parse_reccos_log(str(RECCOS_LOG))
        topic = counts.get("topic") or hint or "broad"
        sent_key = f"{props_date['date']} {props_date['time']} shopping-reccos {topic}"
        if idempotency_check(SENT_LOG, sent_key):
            return 0
        debug_log(
            HOOK_NAME,
            f"capturing shopping_reccos_run topic={topic} count={counts.get('count')} "
            f"slugs={counts.get('slugs')}",
        )
        ok = posthog_capture(
            "shopping_reccos_run",
            {
                **props_date,
                "topic": topic,
                "count": int(counts.get("count") or 0),
                "slugs": counts.get("slugs") or [],
                "tags": counts.get("tags") or [],
                "top_reason": counts.get("top_reason") or None,
            },
        )
        if ok:
            idempotency_record(SENT_LOG, sent_key)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x .claude/hooks/posthog_shopping_capture.py
```

- [ ] **Step 3: Smoke-import it**

```bash
python3 -c "import sys; sys.path.insert(0, '.claude/hooks'); import posthog_shopping_capture; print('ok')"
```
Expected: `ok`

If it fails — fix imports / syntax before continuing.

- [ ] **Step 4: No commit yet** — bundle with test in Task 8.

---

## Task 7: Wire hook into `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Add the hook command to PostToolUse + Stop arrays**

Current shape (already in settings.json):

```json
{
  "hooks": {
    "PostToolUse": [{"hooks": [{"type": "command", "command": "python3 .claude/hooks/post_triage_log.py"}, {"type": "command", "command": "python3 .claude/hooks/posthog_capture.py"}, {"type": "command", "command": "python3 .claude/hooks/posthog_job_research_capture.py"}, {"type": "command", "command": "python3 .claude/hooks/posthog_weekly_coach_capture.py"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 .claude/hooks/post_triage_log.py"}, {"type": "command", "command": "python3 .claude/hooks/posthog_capture.py"}, {"type": "command", "command": "python3 .claude/hooks/posthog_job_research_capture.py"}, {"type": "command", "command": "python3 .claude/hooks/posthog_weekly_coach_capture.py"}]}]
  }
}
```

Append `{"type": "command", "command": "python3 .claude/hooks/posthog_shopping_capture.py"}` as the last entry in BOTH the `PostToolUse[0].hooks` array AND the `Stop[0].hooks` array.

Use Edit tool for precision:

```
old_string: "command": "python3 .claude/hooks/posthog_weekly_coach_capture.py"
          }
        ]
      }
    ],
    "Stop":
new_string: "command": "python3 .claude/hooks/posthog_weekly_coach_capture.py"
          },
          {
            "type": "command",
            "command": "python3 .claude/hooks/posthog_shopping_capture.py"
          }
        ]
      }
    ],
    "Stop":
```

And separately for the Stop block (same shape, same hook command appended).

- [ ] **Step 2: Verify settings.json still valid JSON**

```bash
python3 -c "import json; json.load(open('.claude/settings.json')); print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Verify both hook entries present**

```bash
grep -c "posthog_shopping_capture.py" .claude/settings.json
```
Expected: `2` (one in PostToolUse, one in Stop)

- [ ] **Step 4: No commit yet** — bundle with hook in Task 8.

---

## Task 8: Test the PostHog hook

**Files:**
- Create: `.claude/hooks/tests/test_posthog_shopping_capture.py`

- [ ] **Step 1: Look at existing hook tests for pattern**

```bash
ls .claude/hooks/tests/
cat .claude/hooks/tests/test_posthog_weekly_coach_capture.py 2>/dev/null | head -40
```

If the weekly-coach test doesn't exist, write the new test following standard pytest pattern using temp files. The test focuses on the log-parser functions, not the full hook invocation (which needs a transcript fixture).

- [ ] **Step 2: Write the test file**

Create `.claude/hooks/tests/test_posthog_shopping_capture.py`:

```python
"""Unit tests for the shopping log-block parsers in posthog_shopping_capture."""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import posthog_shopping_capture as hook  # noqa: E402


ADVISE_LOG_SAMPLE = """\
## office-chair — advise

_Generated 2026-05-12 10:33. Caveman log._

- slug: office-chair
- top_pick: "Featherlite Optima Plus" | https://featherlite.in/optima-plus
- retailer: amazon.in
- best_card: SBI Rupay Debit Card
- list_price: 15999
- effective_price: 13499
- alts: ["Wakefit Ergo X", "Green Soul Vienna"]
- values_winner: user-friendly
- recco_path: .shopping/reccos/office-chair/

## cookware-set — advise

_Generated 2026-05-12 11:05. Caveman log._

- slug: cookware-set
- top_pick: "Hawkins Futura Hard Anodised 5-Piece" | https://hawkinscookers.com/futura-set
- retailer: flipkart.com
- best_card: Flipkart Axis Bank Credit Card
- list_price: 5999
- effective_price: 5399
- alts: ["Prestige Omega Deluxe", "Vinod Platinum"]
- values_winner: value
- recco_path: .shopping/reccos/cookware-set/
"""


RECCOS_LOG_SAMPLE = """\
## broad — reccos

_Generated 2026-05-12 09:00. Caveman log._

- topic: broad
- count: 4
- slugs: ["chess-set", "monitor-27in", "tanpura-electronic", "running-shoes-trail"]
- tags: ["interest-match", "gap", "interest-match", "upgrade"]
- top_reason: "Charter pillar #11 chess explored Feb 2026, no quality set yet"

## kitchen — reccos

_Generated 2026-05-12 09:30. Caveman log._

- topic: kitchen
- count: 3
- slugs: ["cookware-set", "knife-chef", "wok-carbon-steel"]
- tags: ["gap", "gap", "interest-match"]
- top_reason: "Cookware deferred 6+ weeks in W20 patterns; charter prioritises home"
"""


def test_parse_advise_returns_latest_block(tmp_path):
    log = tmp_path / "shopping-advise-log.md"
    log.write_text(ADVISE_LOG_SAMPLE, encoding="utf-8")
    result = hook._parse_advise_log(str(log))
    assert result["slug"] == "cookware-set"
    assert result["top_pick"].startswith("Hawkins Futura Hard Anodised")
    assert "hawkinscookers.com" in result["top_pick"]
    assert result["retailer"] == "flipkart.com"
    assert result["best_card"] == "Flipkart Axis Bank Credit Card"
    assert result["list_price"] == 5999
    assert result["effective_price"] == 5399
    assert result["alts"] == ["Prestige Omega Deluxe", "Vinod Platinum"]
    assert result["values_winner"] == "value"
    assert result["recco_path"] == ".shopping/reccos/cookware-set/"


def test_parse_advise_handles_missing_file(tmp_path):
    log = tmp_path / "missing.md"
    result = hook._parse_advise_log(str(log))
    assert result["slug"] == ""
    assert result["list_price"] == 0
    assert result["alts"] == []


def test_parse_advise_handles_empty_log(tmp_path):
    log = tmp_path / "shopping-advise-log.md"
    log.write_text("# nothing here\n", encoding="utf-8")
    result = hook._parse_advise_log(str(log))
    assert result["slug"] == ""


def test_parse_reccos_returns_latest_block(tmp_path):
    log = tmp_path / "shopping-reccos-log.md"
    log.write_text(RECCOS_LOG_SAMPLE, encoding="utf-8")
    result = hook._parse_reccos_log(str(log))
    assert result["topic"] == "kitchen"
    assert result["count"] == 3
    assert result["slugs"] == ["cookware-set", "knife-chef", "wok-carbon-steel"]
    assert result["tags"] == ["gap", "gap", "interest-match"]
    assert "Cookware deferred" in result["top_reason"]


def test_parse_reccos_empty_list(tmp_path):
    log = tmp_path / "shopping-reccos-log.md"
    log.write_text(
        "## broad — reccos\n\n"
        "- topic: broad\n"
        "- count: 0\n"
        "- slugs: []\n"
        "- tags: []\n"
        "- top_reason: \"\"\n",
        encoding="utf-8",
    )
    result = hook._parse_reccos_log(str(log))
    assert result["topic"] == "broad"
    assert result["count"] == 0
    assert result["slugs"] == []
    assert result["tags"] == []


def test_grab_int_zero_when_missing():
    block = "- topic: foo\n- count: 0\n"
    assert hook._grab_int(block, "missing") == 0
    assert hook._grab_int(block, "count") == 0


def test_grab_string_strips_quotes():
    block = '- top_reason: "quoted value"\n'
    assert hook._grab_string(block, "top_reason") == "quoted value"


def test_grab_list_returns_items():
    block = '- slugs: ["a", "b", "c"]\n'
    assert hook._grab_list(block, "slugs") == ["a", "b", "c"]


def test_grab_list_empty():
    block = "- slugs: []\n"
    assert hook._grab_list(block, "slugs") == []
```

- [ ] **Step 3: Run the tests**

```bash
cd .claude/hooks && python3 -m pytest tests/test_posthog_shopping_capture.py -v
```
Expected: all 9 tests PASS.

If any fail — fix the corresponding parser in `posthog_shopping_capture.py`.

- [ ] **Step 4: Commit hook + test + settings together**

```bash
git add .claude/hooks/posthog_shopping_capture.py \
        .claude/hooks/tests/test_posthog_shopping_capture.py \
        .claude/settings.json
git commit -m "$(cat <<'EOF'
feat(hooks): add posthog_shopping_capture for /advise + /reccos

Mirrors posthog_weekly_coach_capture pattern. Parses latest log block
from logs/shopping-advise-log.md or logs/shopping-reccos-log.md, emits
shopping_advise_run or shopping_reccos_run event to PostHog, records
idempotency in logs/posthog-shopping-sent.log.

Wired into PostToolUse + Stop in settings.json. Unit tests cover parser
edge cases (missing file, empty log, missing keys, quoted strings, lists).

Generated-By: PostHog Code
Task-Id: 162eedf3-ab94-4458-9cb7-2aa7ffbd0b0c
EOF
)"
```

---

## Task 9: Update `.claude/CLAUDE.md` documentation

**Files:**
- Modify: `.claude/CLAUDE.md`

- [ ] **Step 1: Add to "How this system works" section**

Use Edit tool. Find the existing block ending with the `/email-triage` flow and the `"draft a reply"` flow. Append BEFORE the closing ` ``` ` of the diagram:

```
old_string:
"draft a reply"                  # After triage flags an email
  └── activates email-reply skill
  └── reads communication-style.md + my-team.md
```

new_string:
"draft a reply"                  # After triage flags an email
  └── activates email-reply skill
  └── reads communication-style.md + my-team.md

/advise <product>                # Pre-purchase advisor
  └── reads shopping-context/    # profile, inventory, interests, budget, sources
  └── reads Flipkart + Swiggy xlsx + Gmail (recent orders)
  └── 3-candidate shortlist w/ 5-dim scoring + cross-platform price parity
  └── card-discount math (Flipkart Axis / SBI Rupay / Swiggy HDFC)
  └── writes .shopping/reccos/<slug>/{brief,shortlist,price-parity,verdict}.md
  └── appends shopping-advise-log; hook captures to PostHog

/reccos [topic]                  # Proactive discovery
  └── same shopping-context/
  └── 3-5 tagged items ([upgrade]/[gap]/[interest-match]/[swap-from-current])
  └── always includes mfr + retailer + 1 social link
  └── deep-dive via /advise <slug>
  └── appends shopping-reccos-log; hook captures to PostHog
```

- [ ] **Step 2: Add to Key files table**

Use Edit tool. Find the last row of the table (currently the `logs/weekly-coach-log.md` row) and append new rows:

```
old_string:
| `weeks/<ISO>/` | Per-week reflection, plan, patterns (gitignored) |
| `logs/weekly-coach-log.md` | Append-only summary log (gitignored) |

new_string:
| `weeks/<ISO>/` | Per-week reflection, plan, patterns (gitignored) |
| `logs/weekly-coach-log.md` | Append-only summary log (gitignored) |
| `.claude/skills/shopping-assist/SKILL.md` | Pre-purchase advisor — slash `/advise <product>` |
| `.claude/skills/shopping-reccos/SKILL.md` | Proactive discovery — slash `/reccos [topic]` |
| `.claude/skills/shopping-context/*.md` | Shared shopping context (gitignored): profile, inventory, interests, budget-rules, data-sources |
| `.shopping/reccos/<slug>/` | Per-advise output: brief + shortlist + price-parity + verdict (gitignored) |
| `.claude/hooks/posthog_shopping_capture.py` | PostHog event hook for shopping-assist + shopping-reccos |
| `logs/shopping-advise-log.md` | Per-/advise log blocks (gitignored) |
| `logs/shopping-reccos-log.md` | Per-/reccos log blocks (gitignored) |
| `logs/posthog-shopping-sent.log` | Idempotency ledger for shopping PostHog events (gitignored) |
```

- [ ] **Step 3: Verify edits**

Run: `grep -E "shopping-assist|shopping-reccos|/advise|/reccos" .claude/CLAUDE.md | head -20`
Expected: ~8-10 lines matching the new content.

- [ ] **Step 4: Commit**

```bash
git add .claude/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(claude.md): document shopping-assist + shopping-reccos skills

Adds /advise and /reccos to the 'How this system works' diagram and
extends the Key files table with all new artifacts (skill SKILL.md,
context dir, output dir, hook, log files).

Generated-By: PostHog Code
Task-Id: 162eedf3-ab94-4458-9cb7-2aa7ffbd0b0c
EOF
)"
```

---

## Task 10: End-to-end verification + final commit

- [ ] **Step 1: Re-run smoke tests with hook live**

In a fresh session:
- `/advise wired-keyboard-mechanical (sub-₹10K, low profile, daily-use, Bangalore)`
- After completion, verify a log block appended:
  ```bash
  grep -c "^## wired-keyboard-mechanical — advise" logs/shopping-advise-log.md
  ```
  Expected: ≥1

- In another fresh session: `/reccos tech`
- Verify:
  ```bash
  grep -c "^## tech — reccos" logs/shopping-reccos-log.md
  ```
  Expected: ≥1

- [ ] **Step 2: Check PostHog idempotency ledger appended**

```bash
ls logs/posthog-shopping-sent.log
wc -l logs/posthog-shopping-sent.log
```
Expected: file exists with ≥2 lines (one per run).

- [ ] **Step 3: Check PostHog project for live events**

Open PostHog → project `395475` → Events → filter for `shopping_advise_run` and `shopping_reccos_run`.
Expected: both events present from the smoke tests, with all properties populated.

(If `POSTHOG_API_KEY` not set in `.env`, the hook silently no-ops — that's intentional. Verify by `grep POSTHOG_API_KEY .env`.)

- [ ] **Step 4: Run full test suite once more**

```bash
cd .claude/hooks && python3 -m pytest tests/test_posthog_shopping_capture.py -v
```
Expected: all 9 PASS.

- [ ] **Step 5: If everything passes, no new commit needed**

If any smoke-test issue surfaced and you edited a SKILL.md, commit the edit:

```bash
git add .claude/skills/shopping-assist/SKILL.md .claude/skills/shopping-reccos/SKILL.md
git commit -m "$(cat <<'EOF'
fix(shopping): tighten <specific failure> after smoke test

<one-line explanation>

Generated-By: PostHog Code
Task-Id: 162eedf3-ab94-4458-9cb7-2aa7ffbd0b0c
EOF
)"
```

- [ ] **Step 6: Print branch status**

```bash
git log --oneline shopping-skill..HEAD | head -10
git status
```
Expected: 5-6 new commits on `shopping-skill` branch; working tree clean.

- [ ] **Step 7: Ready to merge / PR**

Tell sid:
- All commits on `shopping-skill`
- Suggest PR to `main` if happy
- Mention smoke test slugs created: `.shopping/reccos/cookware-set/`, `.shopping/reccos/wired-keyboard-mechanical/` are sid's first real reccos
