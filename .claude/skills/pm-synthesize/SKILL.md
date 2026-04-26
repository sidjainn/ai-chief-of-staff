---
name: pm-synthesize
description: Phase 4 of the product-builder chain. Synthesize tester feedback into themed findings tied back to the hypothesis. Run only after the owner confirms feedback is collected.
argument-hint: <slug>
context: fork
agent: general-purpose
disable-model-invocation: true
allowed-tools: Read Write Edit Glob Grep Bash(ls *)
---

You are the **Synthesize** phase. The owner runs you with `/pm-synthesize <slug>` only after they've collected feedback. **Do not run this skill on your own initiative** — wait for the owner.

## Preconditions

1. Read `briefs/$0/brief.md` (for the hypothesis) and `briefs/$0/prototype.md` (for what was actually tested).
2. List `briefs/$0/feedback/`. If it's empty or has fewer than 2 files, stop and ask the owner to confirm they're ready — small N produces noise, not signal.
3. Read every feedback file in that directory.

## What good synthesis looks like

You are not writing a book report. The owner needs to decide what to change. Three rules:

- **Cluster, then count.** Group raw observations into themes. A theme isn't a theme until two testers hit it. Single-tester observations go in a "single signal" appendix — kept, not lost, but not promoted.
- **Tie every theme back to the hypothesis.** For each theme, mark whether it supports, contradicts, or is unrelated to the hypothesis.
- **Severity ≠ frequency.** A blocker hit by one tester can outrank a mild annoyance hit by all of them. Rate severity (blocker / major / minor / nit) separately from frequency.

## synthesis.md output

Write to `briefs/$0/synthesis.md`:

```markdown
# Synthesis — <slug>

**Date:** <YYYY-MM-DD>
**Testers:** <N>
**Source:** briefs/$0/feedback/*.md

## Hypothesis verdict

**Hypothesis (verbatim):** <copy from brief>

**Verdict:** supported | partially supported | contradicted | inconclusive

**Why:** <2–3 sentences. Cite specific themes below.>

## Themes (≥2 testers)

### Theme 1 — <short label>
- **Hits:** <N of M testers>
- **Severity:** blocker | major | minor | nit
- **Hypothesis link:** supports | contradicts | unrelated
- **What testers said:** <2–4 paraphrased quotes with attribution like "T1, T3">
- **Why it matters:** <one sentence>

<...repeat for each theme...>

## Single signals (1 tester)
<Bullet list. Don't lose them — sometimes the lone voice is the right one. Flag any the owner should still take seriously.>

## What to change next
<3–5 specific, prioritized recommendations. Each one names the prototype change and the theme it addresses. Order: blockers first, then by hypothesis impact.>

## What to leave alone
<Things testers complained about that are out of scope per the brief, or that would distract from testing the hypothesis. Saying "no" explicitly here saves arguments later.>
```

## Finish with

1. Print the verdict and the top 3 recommendations to the chat.
2. End with the literal next-step command: `/pm-iterate $0`.

## Anti-patterns

- Don't quote testers verbatim at length. Paraphrase tightly with tester IDs.
- Don't recommend a fix you can't tie to a theme.
- Don't soften the verdict. If the hypothesis was contradicted, say so clearly — that's a finding, not a failure.
