---
name: pm-usability-test
description: Phase 3 of the product-builder chain. Generate a shareable usability test plan plus a feedback template testers fill out and return.
argument-hint: <slug>
context: fork
agent: general-purpose
disable-model-invocation: true
allowed-tools: Read Write Edit Glob Grep Bash(mkdir *) Bash(ls *)
---

You are the **Usability Test** phase. The owner runs you with `/pm-usability-test <slug>`. Your job is to produce two artifacts the owner can copy-paste and send to testers:

1. `briefs/$0/usability-test.md` — the test plan the tester reads.
2. `briefs/$0/feedback-template.md` — the form the tester fills in and returns.

## Preconditions

1. Read `briefs/$0/brief.md` and `briefs/$0/prototype.md`. If either is missing, stop and tell the owner what to run.
2. Pull the hypothesis verbatim from the brief — every task you design must produce evidence for or against it.

## Design rules for the test

- **3–5 tasks max.** More than that and feedback gets shallow.
- **Tasks describe goals, not steps.** Wrong: "Click the green button." Right: "You want to find a quiet hotel near the beach. Show me how you'd do that."
- **One task = one piece of hypothesis evidence.** For each task, write the implicit question it answers in the synthesis phase.
- **Open the test with context, close it with reflection.** Pre-task: who they are, what the prototype is, that it's a prototype not a product. Post-task: what surprised them, what they'd change, would they use it.
- **Time estimate:** target 15–20 minutes for the tester. Cut tasks until you fit.

## usability-test.md template

```markdown
# Usability Test — <slug>

**Estimated time:** ~<N> minutes
**Prototype:** <link or path the tester opens>

## Welcome

Hi — thanks for helping me test this. A few things up front:
- This is an early prototype, not a finished product. Some things won't work.
- I'm testing the design, not you. There are no wrong answers.
- Please **think out loud** as you go — tell me what you're looking at, what you expect to happen, what's confusing.
- Feel free to be blunt. Polite feedback won't help me.

## Before we start

1. In one sentence, what do you do day-to-day?
2. Have you used <closest existing tool / behavior> before?
3. What were you hoping this would do when I described it?

## Tasks

### Task 1 — <short title>
**Scenario:** <1–2 sentences setting the scene>
**Your goal:** <what they're trying to accomplish>
**What I'm watching for:** <hidden from tester — keep this in the doc but mark it FOR FACILITATOR>

> FOR FACILITATOR — Hypothesis link: <which part of the hypothesis this tests>

<...repeat for each task...>

## After the tasks

1. What surprised you, good or bad?
2. If you could change one thing, what would it be?
3. Would you use this in real life? Why / why not?
4. Anything I didn't ask about that you want to say?

## Wrap-up

Thanks. Please fill out the [feedback template](feedback-template.md) and send it back.
```

## feedback-template.md template

Make this a low-friction form. Plain markdown the tester can fill in inline. No matrices, no scales the tester won't use seriously.

```markdown
# Feedback — <slug>

**Tester:** <your name or anonymous>
**Date:** <YYYY-MM-DD>

## Per-task notes

### Task 1 — <title>
- What I tried first:
- Where I got stuck (if anywhere):
- What I expected vs. what happened:
- One sentence summary:

<...repeat for each task...>

## Overall

- What surprised you?
- One thing you'd change:
- Would you use this? Why / why not:
- Anything else:
```

## Finish with

1. Print a one-paragraph summary of what the test covers and which hypothesis sub-claims each task probes.
2. Tell the owner: "Share `usability-test.md` with testers. When their `feedback-*.md` files are dropped into `briefs/$0/feedback/`, run `/pm-synthesize $0`."
3. Create the `briefs/$0/feedback/` directory with a `.gitkeep` so testers' files have a home.
