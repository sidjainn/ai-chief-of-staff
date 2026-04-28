# briefs/

> **For human reference only.** Claude doesn't auto-load this file — the chain logic lives in `.claude/skills/pm-*/SKILL.md`, which Claude loads on invocation. This README is here so a human reading the directory cold can see the whole flow at a glance.

Workspace for the product-builder skill chain. Each `briefs/<slug>/` directory is one product idea moving through the phases.

## The chain

```
/pm-brief <slug> [notes]      # 1. Capture brief — gated on a sharp hypothesis.
/pm-prototype <slug>          # 2. Build the smallest artifact that tests the hypothesis.
/pm-usability-test <slug>     # 3. Generate a shareable test plan + feedback template.
                              #    [Owner runs the tests offline. Drop responses
                              #     into briefs/<slug>/feedback/.]
/pm-synthesize <slug>         # 4. Cluster feedback into themes, verdict the hypothesis.
                              #    Owner-invoked only — wait until feedback is in.
/pm-iterate <slug>            # 5. Update the prototype based on synthesis.
                              #    Logs each iteration so history is walkable.
```

Each skill runs in a forked context (`context: fork`), so state is passed via files in this directory — not the chat. That's why every phase reads/writes its own markdown.

## Per-slug layout

```
briefs/<slug>/
├── brief.md                  # phase 1
├── prototype.md              # phase 2 — what was built and why
├── prototype/                # phase 2 — actual artifact (HTML by default)
├── usability-test.md         # phase 3 — what to send to testers
├── feedback-template.md      # phase 3 — what testers fill in
├── feedback/                 # phase 3+ — testers' returned files
│   ├── feedback-alice.md
│   └── ...
├── synthesis.md              # phase 4
└── iterations/               # phase 5
    ├── iteration-1.md
    └── iteration-2.md
```

## Why this is gated

`/pm-brief` refuses to write the brief without a testable hypothesis. Every later phase checks the brief exists and the hypothesis is sharp before doing anything. Skipping the gate produces prototypes nobody can learn from.

## Why these skills are manual-only

All five have `disable-model-invocation: true`. The owner controls the cadence — Claude won't decide on its own that "we're ready to synthesize."
