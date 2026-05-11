# Chief of Staff — Project Instructions

This project is a personal AI Chief of Staff built on Claude Code.
It uses skills and hooks together as a system — not one feature at a time. Every workflow lives as a skill so it ports cleanly to other harnesses (Codex etc.).

## How this system works

```
/weekly-coach                    # Weekly reflection + next-week planning
  └── pulls charter + sheet + daily logs (public Google export endpoints)
  └── 6-week pattern detection   # Avoidance / drift / breakthroughs
  └── writes weeks/<ISO>/        # reflection.md + plan.md + patterns.md
  └── appends weekly-coach-log   # Hook captures counts to PostHog

/research-job <jd-or-link>       # Deep research on a job + company
  └── reads jobs/me/             # Resume + interests as candidate lens
  └── creates jobs/<slug>/       # Per-company running doc + research
  └── dispatches subagents       # Company / role / comp / interviewers / Granola

/update-job <slug-or-notes>      # Light post-meeting update on existing co
  └── pulls fresh Granola         # New meetings since last update
  └── folds in pasted notes       # Ad-hoc info from sid
  └── appends ## Update — DATE   # Dated section, doesn't overwrite

"had a call w/ <co>"             # Auto-triggers job-research skill
  └── routes to update workflow  # If <co> already in jobs/

/email-triage                    # Morning triage (email + calendar)
  └── reads context/             # Priorities, team, comms style
  └── triggers hook              # Logs triage to email-runs/<DATE>.md

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

## Key files

| File | Purpose |
|------|---------|
| `.claude/skills/email-triage/context/my-priorities.md` | What matters this quarter (gitignored, real personal content) |
| `.claude/skills/email-triage/context/my-team.md` | Who people are and how to handle them (gitignored) |
| `.claude/skills/email-triage/context/communication-style.md` | How I write — voice and rules (gitignored) |
| `.claude/skills/email-triage/example.context/` | Public template — sample dummy context committed for repo readers; never read at runtime |
| `.claude/skills/weekly-coach/SKILL.md` | Weekly reflection + planning skill — slash `/weekly-coach` |
| `.claude/skills/job-research/SKILL.md` | Job research skill — slash `/research-job` + `/update-job`; auto-triggers on JDs / job URLs / meeting recaps |
| `.claude/skills/email-triage/SKILL.md` | Morning email + calendar triage — slash `/email-triage` |
| `.claude/skills/email-reply/SKILL.md` | Email drafting skill — auto-triggers on "draft a reply" |
| `jobs/me/resume.md` | Sid's resume — read every job-research invocation |
| `jobs/me/interests.md` | What sid wants in a role — used to score fit |
| `.claude/hooks/_hook_common.py` | Shared library — transcript resolution, .env loading, JSONL parse, idempotency, PostHog capture, pre-gate cache |
| `.claude/hooks/post_triage_log.py` | Auto-log hook (writes to `email-runs/<DATE>.md`) |
| `email-runs/<DATE>.md` | Per-day triage runs (gitignored) — one file per day, one section per run |
| `.claude/hooks/posthog_capture.py` | PostHog event hook for email-triage |
| `logs/posthog-email-triage-sent.log` | Idempotency ledger — sent triage events (gitignored) |
| `.claude/skills/weekly-coach/charter-pillar-modes.md` | Pillar-mode tags (cadence/episodic/hybrid) — coach lens for charter coverage |
| `.claude/hooks/posthog_weekly_coach_capture.py` | PostHog event hook for weekly-coach |
| `.claude/hooks/posthog_job_research_capture.py` | PostHog event hook for job-research |
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

## Updating your context

These files are the system's brain. Keep them current:
- Update `my-priorities.md` each quarter
- Update `my-team.md` when org changes
- Update `communication-style.md` if you correct the output repeatedly

## Rules for Claude in this project

- Always read context files before triaging or drafting
- Never open with "I hope this email finds you well" or any banned phrase from communication-style.md
- Hartwell Group emails always CC Marcus Webb and Sarah Chen
- When in doubt about priority, refer to my-priorities.md
- The weekly log is auto-generated — do not edit it manually

## Voice — caveman mode

Terse like caveman. Technical substance exact. Only fluff die.

Drop: articles, filler (just/really/basically), pleasantries, hedging.

Fragments OK. Short synonyms. Code unchanged.

Pattern: [thing] [action] [reason]. [next step].

ACTIVE EVERY RESPONSE. No revert after many turns. No filler drift.

Code/commits/PRs: normal. Off: "stop caveman" / "normal mode".
