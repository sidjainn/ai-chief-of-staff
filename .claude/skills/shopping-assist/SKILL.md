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
- One specialist retailer based on category (Croma / Decathlon / Reliance Digital / Pepperfry / Urban Ladder / Nykaa / etc.)

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

**Header MUST use em-dash (U+2014, ` — `), not ASCII hyphen.** The hook regex looks for `## <slug> — advise`. ASCII `-` or `--` will silently break PostHog capture.

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
- `retailer`: bare domain only (`amazon.in`, `flipkart.com`, `wakefit.co`, etc.). No parenthetical notes (e.g. NOT `amazon.in (Prime exclusive)`). Max 80 chars.
- `best_card`: exact name from `profile.md ## Payment methods`
- `list_price` + `effective_price`: integer rupees, no decimals, no commas
- `alts`: JSON-ish list of 0-2 strings. If fewer than 2 alts, emit only the ones that exist; empty list `[]` allowed. Never pad with empty strings.
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
