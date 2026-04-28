# Chief of Staff — Project Instructions

This project is a personal AI Chief of Staff built on Claude Code.
It uses commands, skills, and hooks together as a system — not one feature at a time.

## How this system works

```
/triage                          # Run morning triage (email + calendar)
  └── reads context/             # Priorities, team, comms style
  └── triggers hook              # Logs triage to weekly-log.md

"draft a reply"                  # After triage flags an email
  └── activates email-reply skill
  └── reads communication-style.md + my-team.md

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

/weekly-coach                    # Weekly reflection + next-week planning
  └── pulls charter + sheet + daily logs (gdrive MCP)
  └── 6-week pattern detection   # Avoidance / drift / breakthroughs
  └── writes weeks/<ISO>/        # reflection.md + plan.md + patterns.md
  └── appends weekly-coach-log   # Hook captures counts to PostHog
```

## Key files

| File | Purpose |
|------|---------|
| `.claude/context/my-priorities.md` | What matters this quarter |
| `.claude/context/my-team.md` | Who people are and how to handle them |
| `.claude/context/communication-style.md` | How I write — voice and rules |
| `.claude/commands/triage.md` | The /triage command |
| `skills/email-reply/SKILL.md` | Email drafting skill |
| `.claude/commands/research-job.md` | The /research-job command |
| `.claude/commands/update-job.md` | The /update-job command (light post-meeting updates) |
| `skills/job-research/SKILL.md` | Job research skill (auto-triggers on JDs/job URLs + meeting recaps) |
| `jobs/me/resume.md` | Sid's resume — read every job-research invocation |
| `jobs/me/interests.md` | What sid wants in a role — used to score fit |
| `.claude/hooks/post-triage-log.sh` | Auto-log hook |
| `logs/weekly-log.md` | Auto-generated, gitignored |
| `.claude/commands/weekly-coach.md` | The /weekly-coach command |
| `skills/weekly-coach/SKILL.md` | Weekly reflection + planning skill (gdrive MCP) |
| `.claude/hooks/posthog-weekly-coach-capture.sh` | PostHog event hook for weekly-coach |
| `weeks/<ISO>/` | Per-week reflection, plan, patterns (gitignored) |
| `logs/weekly-coach-log.md` | Append-only summary log (gitignored) |

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
