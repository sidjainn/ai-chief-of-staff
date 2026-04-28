You are running a **light update** on an existing job-research folder. Treat the user message after `/update-job` as the input — slug, company name, or freeform notes.

## What this is (vs `/research-job`)

`/research-job` = full deep dive. Dispatches 7 subagents. Creates folder. Heavy.

`/update-job` = light. Pulls only fresh Granola meetings + folds in user notes + appends dated update to README. Skips re-research of company/comp/interviewers unless explicitly asked.

## What to do

Activate the **`job-research`** skill in `skills/job-research/SKILL.md`. Follow the **§Update Workflow** section (not the full workflow).

## Input handling

- **Slug or company name** (e.g. `plum`, `Plum`, `plumhq`) → resolve to `jobs/<slug>/`. If folder doesn't exist, fall back to `/research-job` instead.
- **Freeform notes** ("had call w/ Atul, here's what came up: …") → detect company from notes (cross-check `jobs/*/`), fold notes into `meetings/<date>-<short-slug>.md`, append dated update to README.
- **Empty** → ask: "Which job? Or paste meeting notes."

## Required steps

1. **Resolve folder.** `jobs/<slug>/` must exist. If not — say so, suggest `/research-job` instead.
2. **Pull fresh Granola** via `mcp__granola__query_granola_meetings` for company name + interviewer names. New meetings since last `meetings/_no-prior-meetings.md` or last `meetings/*.md` timestamp → save transcripts.
3. **Fold user notes** into `meetings/<YYYY-MM-DD>-<topic>.md` if free-text provided.
4. **Append dated update to README.md**:

```markdown
## Update — YYYY-MM-DD

_Source: <granola meeting / sid notes / both>_

### What changed
- <bullet>

### Updated recommendation
- <one line>

### New open questions
- <bullet>

### Resolved questions
- <bullet from prior Open Questions section, now answered>
```

5. **Don't re-run company/comp/interviewer subagents** unless user explicitly asks ("re-research <X>"). The whole point is light.

## Output (chat)

- Path to updated folder
- New `## Update —` section verbatim
- "Want me to dig deeper on anything?"

That's it. No re-narration of the full doc.
