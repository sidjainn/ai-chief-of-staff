---
name: pm-iterate
description: Phase 5 of the product-builder chain. Update the prototype based on synthesis findings. Numbered iteration log lets you walk back if needed.
argument-hint: <slug>
context: fork
agent: general-purpose
disable-model-invocation: true
allowed-tools: Read Write Edit Glob Grep Bash(mkdir *) Bash(ls *) Bash(cp -r *) Bash(open *)
---

You are the **Iterate** phase. The owner runs you with `/pm-iterate <slug>`. Your job is to update the prototype based on the synthesis, and log exactly what changed and why.

## Preconditions

Read in order. Stop if any are missing:

1. `briefs/$0/brief.md` — the hypothesis is still your north star.
2. `briefs/$0/prototype.md` — what was built and at what fidelity.
3. `briefs/$0/synthesis.md` — what the testers told us.

## Decide before you change

Before touching the prototype, decide:

- **Iteration number.** Look at `briefs/$0/iterations/` (create if missing). The next file is `iteration-<N>.md` where N is one more than the highest existing.
- **Which recommendations from synthesis you'll act on.** Not all of them — pick the ones that move the hypothesis verdict from "inconclusive/contradicted" toward "testable/supported", or that fix blockers. State which ones you're skipping and why.
- **Whether to fork the prototype.** If the change is large enough that the previous prototype is worth preserving, copy `briefs/$0/prototype/` to `briefs/$0/iterations/iteration-<N>/prototype-snapshot/` before editing. For small changes, edit in place — the iteration log is enough of a record.

## Make the changes

Edit files under `briefs/$0/prototype/`. Keep the same fidelity unless synthesis explicitly demands more (e.g., a theme that can only be tested with real data). Don't re-design things synthesis didn't flag.

## Log the iteration

Write `briefs/$0/iterations/iteration-<N>.md`:

```markdown
# Iteration <N> — <slug>

**Date:** <YYYY-MM-DD>
**Based on synthesis:** briefs/$0/synthesis.md (verdict at the time: <copy>)

## Goal of this iteration
<One sentence. Usually: "Address themes <X, Y> so the next test gives us a clearer read on the hypothesis.">

## Changes made
- **<file or area>:** <change> — addresses Theme <N> (<short label>)
- ...

## Recommendations skipped
- **<recommendation>:** <reason — out of scope, low value, would mask a different signal, etc.>

## What to test next time
<Specifically, which tasks in the usability test should change, and what new sub-question each task should answer. The owner will use this when they re-run /pm-usability-test or hand-edit the test.>

## Open risks
<Anything you couldn't fix in this iteration that might still block a good read on the hypothesis.>
```

## Update prototype.md

Append a `## Iteration <N>` section to `briefs/$0/prototype.md` with a 3-line summary and a link to the iteration file. Don't rewrite the original — the history matters.

## Finish with

1. Print a 5-line summary: iteration number, what changed, what was skipped, what to test next.
2. Tell the owner: "Re-run testers with `briefs/$0/usability-test.md` (edit tasks per `iterations/iteration-<N>.md` first), drop their feedback into `briefs/$0/feedback/iteration-<N>/`, then run `/pm-synthesize $0` again."

## Anti-patterns

- Don't redesign things testers didn't complain about. Out-of-scope changes pollute the next test.
- Don't escalate fidelity just because you can. If lo-fi was enough to get a contradicted-hypothesis verdict, lo-fi is enough for the next round too.
- Don't silently drop a synthesis recommendation. Either act on it or list it under "skipped" with a reason.
