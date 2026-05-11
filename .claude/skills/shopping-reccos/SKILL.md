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
