---
name: update-job
description: Light post-meeting / ad-hoc update for a company already tracked under `jobs/<slug>/`. Triggers on `/update-job <slug-or-notes>`, "had a call with [co]", "met [interviewer-name]", "[co] recap/debrief/follow-up", "update my [co] doc", pasted meeting notes that mention a tracked company, or a Granola sync surfacing new meetings with a tracked company. Pulls fresh Granola, folds in sid's free-text notes, and appends a dated `## Update — YYYY-MM-DD` section to that folder's README.md — never overwrites. Falls back to the `job-research` skill (`/job-research`) when the company isn't already tracked.
version: 1.0
author: sid
referenced_files:
  - jobs/me/resume.md
  - jobs/me/interests.md
---

# Update-Job Skill

## What this skill does

Light path for keeping an existing `jobs/<slug>/` running doc current after a meeting, recruiter ping, or fresh signal. Designed to be cheap: no parallel subagent fan-out, no re-research, no rewrite. Append a dated update; preserve prior understanding as memory.

If the company isn't already tracked under `jobs/`, **hand off to the `job-research` skill** (full `/job-research` flow). This skill assumes the folder already exists.

---

## Output style — caveman terse

All artifacts and chat output write in **caveman-full** voice:

- Drop articles (a/an/the), filler (just/really/basically), pleasantries, hedging.
- Fragments OK. Short synonyms. Pattern: `[thing] [action] [reason]. [next step].`
- Tables and bullets > prose paragraphs. Numbers + sources, not narration.
- Code, exact quotes from JDs, exact compensation strings — render normal, unchanged.
- Hyperlink rule applies: every external reference (post, article, Granola note, tweet) must embed its URL inline.

---

## Steps

1. **Resolve the folder.** From the user input or pasted notes, identify which `jobs/<slug>/` to update. If no folder exists for that company, stop and route to the `job-research` skill instead — `/update-job` is only for already-tracked cos.

2. **Pull fresh Granola.** Call `mcp__granola__query_granola_meetings` with company name + interviewer names. Compare against existing files in `meetings/`. For any new meeting:
   - Call `mcp__granola__get_meetings` w/ the meeting_id to grab metadata + deeplink.
   - Save transcript summary to `meetings/<YYYY-MM-DD>-<short-slug>.md` using the standard meeting template (decisions / open threads / quotes / contradicts-public-narrative / what-this-changes).
   - Header MUST include Granola deeplink: `_Granola: [<title>](https://notes.granola.ai/d/<meeting_id>)_` (or `share_url`/`url` from `get_meetings` if returned). Without link, sid can't reopen the source — non-negotiable.

3. **Fold user's free-text notes.** If user pasted notes in chat, save them to `meetings/<YYYY-MM-DD>-<topic>.md` with `_Source: sid notes_` header. Don't paraphrase aggressively — keep sid's words.

4. **Append a dated update to README.md.** Use this template (caveman-terse, ≤25 lines):

```markdown
## Update — YYYY-MM-DD

_Source: <granola: <meeting-id> / sid notes / both>_

### What changed
- <bullet>

### Updated recommendation
- <one line — investigate / pass / push hard, w/ reason for change>

### Resolved questions
- <bullet from prior Open Questions, now answered, w/ answer>

### New open questions
- <bullet>
```

5. **Move resolved items.** Strike through resolved items in main "Open questions" section, or move them inline to the Update's "Resolved questions" block.

6. **Don't re-run** company-researcher / role-analyzer / comp-triangulator / interviewer-profiler subagents unless user explicitly asks ("re-research <X>", "comp got stale, refresh"). The whole point is light. For heavy re-research, route to the `job-research` skill.

7. **Output to chat:**
   - Path to updated folder
   - The new `## Update —` block verbatim
   - "Want me to dig deeper on anything?"

---

## When to bail to `/job-research`

- No folder exists yet under `jobs/<slug>/` for the company referenced.
- User explicitly asks to "re-research", "refresh comp", "redo the brief", or any signal the running doc is too stale to patch.
- Granola surfaces a meeting with a company that's never been researched.

In all those cases, hand off to the `job-research` skill — don't try to bootstrap a new folder from this skill.

---

## Why a separate workflow

Full `/job-research` re-runs 7 subagents — heavy + slow. Most updates after the first pass = "Granola has a new meeting + here's what I learned." Light path keeps it cheap and preserves the running-doc-as-memory invariant (append, never overwrite).

---

## Failure modes to avoid

- **Overwriting the README on re-run.** The doc is a memory. Append a `## Update — YYYY-MM-DD` block; never replace.
- **Skipping Granola.** Even if there are no new meetings, the explicit "no new meetings since <last update>" tells sid the channel is dry.
- **Skipping the Granola deeplink.** Meeting summary w/o the deeplink header is non-recoverable — sid can't reopen the source.
- **Trying to bootstrap a new folder.** If `jobs/<slug>/` doesn't exist, this skill should bail to `job-research`. Don't fabricate a folder from a sparse meeting note.
- **Paraphrasing sid's pasted notes.** Keep his words verbatim under `_Source: sid notes_` — paraphrase loses signal.
- **Re-running subagents silently.** Heavy re-research belongs in `/job-research`. If the user wants it, route there explicitly.

---

## Self-check before finishing

- [ ] Did I resolve the correct `jobs/<slug>/` folder (or bail to `job-research` if untracked)?
- [ ] Did I call `mcp__granola__query_granola_meetings` and check for new meetings since last update?
- [ ] Does every new meeting summary include the Granola deeplink header?
- [ ] Did I append a `## Update — YYYY-MM-DD` block rather than overwriting?
- [ ] Did I move resolved items out of the main "Open questions" section?
- [ ] Did I keep sid's pasted notes verbatim under `_Source: sid notes_`?
- [ ] Did I avoid silently re-running subagents (heavy refresh = explicit `/job-research` only)?

If any check fails, fix it before showing output.
