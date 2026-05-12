---
name: shopping-reccos
description: Proactive product-discovery skill for sid. Triggers on /reccos, /reccos <topic>, "recommend me something", "what should I buy", "surprise me with products", "I'm bored, what's on my radar", or any open-ended discovery ask. Reads .claude/skills/shopping-context/ (focus on interests + inventory gaps + recent order patterns) to surface 3-5 things sid would plausibly want — tagged [upgrade] / [gap] / [interest-match] / [swap-from-current]. Each item: 1-line why-for-you + 1 alt + values fit. Always includes manufacturer + retailer + 1 social link. Lightweight (no file artifacts); deep-dive any pick via /shopping-assist <slug>. Appends to `logs/shopping-reccos-log.md` for PostHog capture.
version: 1.0
author: sid
---

# Shopping Discovery Skill

## What this skill does

Surfaces 3-5 products sid would plausibly want, with rationale tags. Lightweight — no per-item file dump. If a recco resonates, sid runs `/shopping-assist <slug>` to deep-dive.

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

Read the same 5 context files as `shopping-assist` (profile / inventory / interests / budget-rules / data-sources), PLUS the latest week's reflection for stuck-on signals.

Focus on:
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

Filter:
- Skip if in `profile.md ## No-go` (banned brands/categories)
- Skip if budget-rules ceiling makes it implausible
- Cross-check `inventory.md` for exact-category match — if owned AND no wear signal in inventory notes → skip

### Step 4 — Render

For each item, in chat output:

```markdown
N. [<tag>] **<product type — brand model>** (slug: `<kebab-slug>`) — <one-line why, citing source like "inventory.md: HOF mesh chair, 2yr, lumbar pain" or "interests.md ## Endurance / charter goal #4">
   - alt: <brand model>
   - top dim: <value | nature | user-friendly | reviews | budget-fit>
   - links: [mfr](<url>) · [retailer](<url>) · [<social-source>](<url>)
```

End with: `Deep-dive any pick: /shopping-assist <slug>` and list the 3-5 slug candidates.

### Step 5 — Append log block

Append to `logs/shopping-reccos-log.md` (create the file if it doesn't exist).

**Header MUST use em-dash (U+2014, ` — `), not ASCII hyphen.** The hook regex looks for `## <topic> — reccos`. ASCII `-` or `--` will silently break PostHog capture.

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
- `topic`: bare lowercase token or `broad`. Max 60 chars.
- `count`: integer matching number of slugs
- `slugs`: JSON-ish list, kebab-case, parallel to tags
- `tags`: JSON-ish list, parallel to slugs (same order, same count)
- `top_reason`: quoted string, ≤200 chars

## Context Capture

Sid often surfaces preferences mid-conversation that belong in shared context. Catch them and offer to persist.

### Writable files

- `profile.md` — values, leanings, no-go list, payment methods, household additions
- `interests.md` — new hobbies, "want to try", "stopped caring about X", domain curiosities
- `budget-rules.md` — ceiling changes, new no-go brands, new buy-once-cry-once entries

### Never auto-write

- `inventory.md` — purchase events only, declarations don't count. Sid updates manually post-purchase.
- `data-sources.md` — paths rarely change.

### Signal types

**Explicit (write immediately):**
- "save: <thing>" / "remember <thing>" / "add to profile/interests/budget"
- "update <file>.md to reflect …"

**Soft (propose diff, ask y/n before writing):**
- Preference statements: "I hate plastic", "I don't trust Chinese OEM clones", "no leather"
- Budget shifts: "₹15K ceiling for headphones now", "raise mattress BOCO to ₹30K"
- New interests/hobbies: "got into pickleball", "starting to learn watercolour"
- Lifestyle changes: "moved to vegan-only meals", "WFH 5 days now, not 3"
- Card changes: "got HDFC Diners now", "lost SBI Rupay card"
- Household changes: "partner moved in", "friend X visits often"

### Flow

1. Detect signal mid-convo. Don't break the reccos flow — surface inline.
2. Format: `[context-signal] <one-line restatement> → <target file>.md ## <section>`
3. Show proposed diff (2-5 lines max). Use Edit-style old→new.
4. Ask: `Save to <file>.md? (y/n)`
5. On `y` → run Edit tool. On `n` or no response → drop silently, continue.
6. Explicit signals skip the y/n; just edit + confirm in 1 line.

### Boundaries

- Max 1 capture per /reccos run unless sid pushes multiples.
- Never invent preferences not stated. Restatement must be verbatim or near-verbatim.
- If file/section doesn't exist, propose creating it, don't auto-create.

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
