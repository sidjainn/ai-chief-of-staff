# Shopping skills — design spec

_Date: 2026-05-11. Author: sid (via brainstorming). Status: draft for review._

## Problem

Sid wants help making purchase decisions that match his values. Currently:

- Pre-purchase research is slow and inconsistent — quality varies trip-to-trip.
- Discovery is reactive — interesting products surface only when he stumbles into them.
- Personal context (what he owns, what he values, what he's read, household setup) is scattered across daily logs, charter, jobs/me/, Gmail, and two order-history Excel exports — never consolidated.

## Goals

1. **Pre-purchase advisor** — paste a need + current pain → get a values-aligned recommendation with shortlist, scores, reasoning, where-to-buy.
2. **Proactive discovery** — surface 3-5 products sid would plausibly want, with rationale (gap, upgrade, interest-match, swap).
3. **Shared context** — one source of truth for who sid is as a shopper. Both skills read it. No duplication.

## Non-goals

- Not transactional. Skill does not place orders, does not integrate with payment, does not auto-cart.
- Not real-time price tracking or deal-hunting.
- Not a household ledger or budget tracker (that's `weekly-coach` / sheet territory).
- Not auto-refresh of context. Interests + inventory snapshots; user refreshes manually.

## Values rubric (sid's stated heuristics)

Every shortlist item scored 1-5 on each:

| Dim | Meaning |
|---|---|
| **Value** | Price vs durability, lifespan, total-cost-of-ownership |
| **Nature-friendly** | Materials, repairability, shipping footprint, brand ethics |
| **User-friendly** | Ergonomics, ease, fit for sid's specific use-case |
| **Reviews** | Cross-source sentiment; weight to recent + verified-purchase |
| **Budget fit** | Against `budget-rules.md` ceilings + category posture |

Weighted total → ranked top pick. Scores rendered transparently so sid can override.

Default weights: value 0.25, nature 0.20, user-friendly 0.25, reviews 0.20, budget 0.10. Tunable per-invocation if sid says e.g. "I'll pay more, just give me the most ergonomic".

## Architecture

### Two skills, one shared context

```
.claude/skills/shopping-assist/                 # /advise — pre-purchase advisor
  └── SKILL.md
.claude/skills/shopping-reccos/                 # /reccos — proactive discovery
  └── SKILL.md
.claude/skills/shopping-context/                # SHARED, gitignored
  ├── profile.md          # me + household + addresses + leanings
  ├── inventory.md        # durable goods owned, tagged by address
  ├── interests.md        # 1-time snapshot from daily-logs/charter/weeks
  ├── budget-rules.md     # category ceilings + posture
  └── data-sources.md     # Gmail recipes + xlsx paths
.shopping/reccos/<slug>/                        # per-advise output, gitignored. 1 slug per item, no date prefix
  ├── brief.md            # the need + context fed in
  ├── shortlist.md        # 3-5 candidates with values scores + links
  ├── price-parity.md     # cross-platform price comparison (Flipkart vs Amazon vs brand-direct vs Croma etc.)
  └── verdict.md          # top pick + reasoning + where-to-buy + best card to use
```

**Slug rule:** kebab-case product name, e.g. `office-chair`, `wired-headphones`, `running-shoes-trail`. If user invokes `/advise` again for same slug, **overwrite** prior brief.md/shortlist.md/price-parity.md/verdict.md (clean re-run). User keeps a tracked history elsewhere if needed.

### Why two skills, not one

- Different jobs-to-be-done. Advisor = reactive, specific need, deep web research per invocation. Reccos = exploratory, broad scan, surface options.
- Different trigger surfaces. Advisor = `/advise <thing>`. Reccos = `/reccos [topic]`.
- Same context, different lens. Same pattern as `email-triage` + `email-reply` in this repo.

## `/advise` flow

1. **Read context.** All of `shopping-context/*`. Pull relevant order history (Flipkart xlsx + Gmail search + Swiggy xlsx if food-adjacent).
2. **Clarify.** Ask 2-4 sharp questions inline: budget ceiling, deadline, deal-breakers, aesthetic constraints. Skip if user already provided.
3. **Web research.** Surface 5-8 candidates. Filter to 3 by basic disqualifiers (out of budget, out of stock, banned brand/category).
4. **Score.** Each candidate scored on the 5-dim rubric. Cite sources for each score (review URL, brand page, Reddit thread, Twitter/X thread, YouTube review).
5. **Cross-platform price parity.** For each shortlisted item, check Flipkart, Amazon, brand-direct, and one specialist retailer (Croma / Decathlon / Reliance Digital / Pepperfry / Urban Ladger depending on category). Record listed price + current discount.
6. **Card-discount layer.** For each retailer × card pairing in `profile.md ## Payment methods`, factor in the applicable offer (e.g. Flipkart Axis 5% cashback on Flipkart, Swiggy HDFC 10% on Swiggy). Compute effective price after best owned card. Flag if a borrowable card (e.g. HDFC Regalia 10% on Amazon) materially changes the winner.
7. **Write artifacts.** `.shopping/reccos/<slug>/{brief,shortlist,price-parity,verdict}.md`. Slug = kebab-case product name; overwrite on re-run.
8. **Always include links.** Every candidate and source MUST have a clickable link: manufacturer page, retailer listing, primary review URL, Reddit thread, Twitter/X thread, YouTube. No bare brand names.
9. **Render inline.** Top pick + 2 alternatives + best-card recommendation + effective total cost + where-to-buy. Keep terse.
10. **Never write to inventory.** Recommendation ≠ purchase.
11. **Append to log.** `logs/shopping-advise-log.md` — per invocation: slug, top pick, retailer, card used, effective price, top alt. One block, machine-parseable for the PostHog hook.

### Default assumptions

- Purchase is for **self** unless user explicitly says "for dad" / "for X". Address defaults to Bangalore.
- Veg-only food/grocery (confirmed pattern from Swiggy data).
- Reuse existing favored brands when relevant (Yogabar, Whole Truth, Open Secret, etc. — see inventory).
- Prefer durable repairable products over disposable.

## `/reccos` flow

1. **Read context.** Same context as advisor. Focus on `interests.md` + inventory gaps + recent order patterns.
2. **Optional topic arg.** "kitchen" / "books" / "tech" / "home". Without arg = broad scan.
3. **Surface 3-5 items.** Each tagged:
   - `[upgrade]` — replacement for something owned + showing wear
   - `[gap]` — category sid likely cares about but hasn't bought
   - `[interest-match]` — surfaces from daily-log / charter signal
   - `[swap-from-current]` — better alternative to a repeat-buy
4. **Each item.** 1-line why-for-you + 1 alt + values fit (top dim that wins). **Always include manufacturer + retailer + 1 social link** (Reddit / Twitter / YouTube).
5. **No detailed file writes.** Reccos are lightweight. User runs `/advise <slug>` to deep-dive any pick → that goes to disk under `.shopping/reccos/<slug>/`.
6. **Append to log.** `logs/shopping-reccos-log.md` — per invocation: topic, 3-5 slugs surfaced, one-line reasoning each. Mirrors pattern in weekly-coach-log.md.

## Data sources

| Source | Use | Access |
|---|---|---|
| `shopping-context/*` | Profile, inventory, interests, rules | Local read |
| Flipkart xlsx | 12mo order history, category breakdown | Local read of `/Users/sid-j/Documents/Claude/Projects/flipkart orders data/Flipkart_Orders_2025-2026.xlsx` |
| Swiggy xlsx | 6mo food orders, restaurants, cuisines, ratings | Local read of `/Users/sid-j/Documents/Claude/Projects/swiggy-exploration/Swiggy_Orders_Last_6_Months.xlsx` |
| Gmail | Live recent purchases across Amazon, Myntra, Blinkit, Zepto, IKEA, Apple, etc. | Gmail MCP, query: `from:(noreply@flipkart OR amazon OR swiggy OR zomato OR myntra OR blinkit OR zepto OR apple OR ikea) subject:(order OR delivered)` |
| Daily logs (Google Docs) | Used 1-time to seed `interests.md` | Public export endpoint via `.claude/scripts/fetch-coach-sources.sh` |
| Charter (Google Doc) | Same — seeds values + interests | Same fetch script |
| `weeks/<ISO>/` | Cross-reference current intent, breakthroughs | Local read |
| Web research | Live product info, reviews, price | WebFetch + WebSearch |

## Defaults + invariants

1. **Caveman voice for output.** Same as other skills in this repo.
2. **One thing at a time per advise.** Don't bundle multi-product asks; ask user to split.
3. **Cite sources for scores.** No vibes. Each 1-5 score has a 1-line reason + link.
4. **Always link.** Manufacturer + retailer + 1 social proof URL (Reddit / Twitter / YouTube / blog) per candidate. Never recommend a product without a working link.
5. **Cross-platform price parity always.** No single-retailer recommendation. Min 3 platforms checked.
6. **Card-discount layer always.** Effective price post-card-offer is the headline number.
7. **Reccos are gitignored.** `.shopping/reccos/` never enters version control.
8. **Inventory write-back is manual only.** Skill never edits inventory.md on its own.
9. **Default to "for self, in Bangalore".** Explicit override required for Agra/dad/friends.
10. **Ovo-veg by default for any food-adjacent recco.** Eggs OK; no meat/fish/seafood.
11. **Logs append, never overwrite.** `logs/shopping-advise-log.md` + `logs/shopping-reccos-log.md`. Mirrors weekly-coach pattern.

## Open questions resolved during brainstorm

- ✅ Skill split: two skills, shared context.
- ✅ Order history representation: drop `order-history.md`, use Gmail + xlsx pointers in `data-sources.md`.
- ✅ Inventory granularity: medium (item + brand/model + age + pain point), durable goods only.
- ✅ Flipkart Agra-tagging: no reliable signal. Default = self. Flag supplements/knee-pad/protein for review.
- ✅ Daily-logs lookback: all available (Feb-May 2026 currently fetchable).
- ✅ Skill names: `shopping-assist` (advisor) + `shopping-reccos` (discovery).
- ✅ Household: just self in Bangalore. Friends only if explicit.
- ✅ Reccos folder per-item, gitignored. No inventory write-back.

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Context drift — interests.md gets stale | Document refresh-recipe in `interests.md`. User reruns when needed. |
| Hallucinated product specs | Always cite source URL. Prefer manufacturer + 2 review sources. |
| Recco overload | Cap reccos at 5. Cap shortlist at 3. |
| Privacy — order data leaks | All context dirs gitignored. Reccos dir gitignored. xlsx files stay outside repo. |
| User asks for non-veg / for dad → wrong default | Explicit override mechanism baked into prompts. Skill confirms before proceeding if signal is ambiguous. |

## Logging + hooks (v1 minimum)

Mirror the pattern of `weekly-coach` + `email-triage`:

```
logs/shopping-advise-log.md           # append per /advise invocation
logs/shopping-reccos-log.md           # append per /reccos invocation
.claude/hooks/posthog_shopping_capture.py   # PostHog event capture, parses log blocks
logs/posthog-shopping-sent.log         # idempotency ledger (sent events)
```

Log block format (machine-parseable, ≤10 lines per block):

```markdown
## <slug> — advise (or topic — reccos)

_Generated <YYYY-MM-DD HH:MM>. Caveman log._

- slug: office-chair
- top_pick: "Featherlite Optima Plus" | https://...
- retailer: amazon.in
- best_card: Flipkart Axis Bank Credit Card  # cross-card winner if Flipkart wins overall
- list_price: 14999
- effective_price: 13499                       # after card + discounts
- alts: ["Wakefit Ergo X", "Green Soul Vienna"]
- values_winner: user-friendly                 # top scoring dim
```

PostHog hook reads new blocks since last sent, captures one event per block. Same idempotency ledger pattern as existing hooks.

## Out of scope (for v1)

- Auto-refresh of interests / inventory
- Discovery scheduling (cron) — manual invoke only
- Cookware / appliance "kitchen advisor" specialization
- Subscription-vs-one-off optimization
- Borrowable-card automated lookup (skill mentions in verdict if applicable, but no automated card-offer database)
- Trek-gear specialist mode

## Implementation order

After this spec is approved:

1. Context files drafted (this PR / branch)
2. Spec committed
3. Implementation plan written via `writing-plans` skill
4. `shopping-assist/SKILL.md` + `shopping-reccos/SKILL.md` built
5. Smoke test: `/advise office chair` (real need sid mentioned)
6. Smoke test: `/reccos`
7. Optional: PostHog hook for capture (mirror existing skills)
