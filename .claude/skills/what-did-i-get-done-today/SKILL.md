---
name: what-did-i-get-done-today
description: Build sid's end-of-day "what did i get done today?" note from Instinct and WhatsApp, Gmail, Calendar, Granola and Claude Code/Codex sessions, push it to the private repo and send it to PostHog. Use for the nightly 10 pm routine or when sid asks what he got done today.
---

# what did i get done today

A nightly note of what sid got done. It exists for accountability and for closure. The day ends, the note says what moved, what got let go and what carries into tomorrow. Then the day is done.

Repo: `~/ai-chief-of-staff`. Paths below are relative to it. Timezone is IST (Asia/Kolkata).

## Files

- `.claude/skills/what-did-i-get-done-today/context/sources.md` - WhatsApp ids and the voice guide id. Private (gitignored, symlinked to the private repo). Read it first. `example.context/sources.md` shows the shape.
- `.claude/skills/what-did-i-get-done-today/scripts/harness_activity.py` - prints sid's Claude Code and Codex prompts and git commits for a window.
- `what-i-got-done/YYYY/YYYY-MM-DD.md` - one note per day. Pushed to the private repo as soon as it is written.
- `.claude/hooks/posthog_what_i_got_done_capture.py` - sends each new note to PostHog as a `what_i_got_done` event with the full body. It also runs as a Stop hook in Claude Code. A ledger stops double sends.

`what-i-got-done/` is a symlink to `~/ai-chief-of-staff-private/what-i-got-done`.

## Hard rules

- Read-only on every source. Never send a WhatsApp message, email or invite. Never mark anything read.
- No phone numbers, account numbers, bib numbers or money amounts in a note. Say what moved, not the figures.
- Skip banter and private personal chats. The note covers what sid did or decided, not what friends said.
- If a source fails, keep going with the rest. Record it in `sources_missing`.

## 1. Work out the window

- `window_end` is now.
- `window_start` is the latest `window_end` found in the frontmatter of any note under `what-i-got-done/`. If there is none, use 00:00 IST today.
- If a note for this date already exists, you are re-running. Keep its `window_start`, move `window_end` to now and rebuild it in place. Then run step 5 again.
- If the window covers more than one calendar day, say so in the note's first line.
- If the newest note lists anything in `sources_missing`, backfill it first. Fetch those sources for that note's window, fold what they add into that note, update its `sources_missing`, and run step 5 for it. Then build tonight's note.

## 2. Gather

Run these in parallel.

Use the claude.ai connectors for Gmail, Calendar and Granola. Their tool names look like `mcp__<id>__search_threads`, `mcp__<id>__list_events` and `mcp__<id>__list_meetings`. Load them with ToolSearch by tool name. The `gmail`, `gcal` and `granola` entries in `.mcp.json` and the project config are broken. Ignore their startup errors ("ENOTFOUND", "needs auth"). Do not mark a source missing until its connector tool has been called and has failed.

A connector can return "The connector's server isn't responding" for a stretch of minutes. Granola did this on Sep 24 from 22:51 to 23:13, then worked again. So when a call fails, gather the other sources first, then retry it. Retry once more just before writing the note. If it still fails, record it in `sources_missing` and move on. The next run backfills it (step 1).

### Instinct (the main source)

Instinct is sid's to-do agent on WhatsApp. Its chat id is in `context/sources.md`.

- `list_messages` with `chat_jid` set, the window as `after`/`before`, `limit` 100, `include_context` false. Page until fewer than 100 come back.
- Instinct sends a short wrap of the day around 21:30. Start from it. Where sid corrected the wrap, his correction wins.
- Compare the first and the last `*Today*` list in the window. Items that dropped off are done or let go. sid's messages say which.
- Things sid tells Instinct ("X is done", "i reminded Y", "remove Z") are the strongest evidence there is.

### Everything else sid sent on WhatsApp

- `list_messages` once per sender id in `context/sources.md`. sid's messages come from both his phone id and his LID. Same window, same paging.
- `context/sources.md` also names his notes-to-self group.
- Chats often show as numbers. Name a person only when the messages name them. Do not guess who a number is.
- Keep only messages that show sid doing, deciding, asking for or declining something.

WhatsApp time filter quirk. `after` and `before` are compared against IST wall-clock time. Pass naive local times with no `Z` and no offset, for example `2026-09-23T00:00:00`. Output timestamps are IST too. Passing UTC shifts the window by 5.5 hours.

### Gmail

- Sent: `search_threads` with `in:sent after:<window_start epoch> before:<window_end epoch>`. Use epoch seconds. Date-only Gmail queries do not follow IST.
- Received: same window with `-category:promotions -category:social`. Keep a received mail only when it confirms something sid did, such as a booking, an application, a submission or a registration.

### Calendar

`list_events` on the primary calendar for the window, `timeZone` `Asia/Kolkata`. An event counts as done only with evidence: a Granola note, a message about it, or sid's own word. Events still at `needsAction` do not count.

### Granola

`list_meetings` with `time_range` `this_week`, plus `last_week` if the window starts before Monday. Keep meetings inside the window. `get_meetings` on those for the summary and next steps.

### Claude Code and Codex

```
python3 .claude/skills/what-did-i-get-done-today/scripts/harness_activity.py --since <window_start ISO> --until <window_end ISO>
```

It prints each session's title, folder and sid's prompts, then git commits from those repos. Merged PRs and commits count as done. Ignore runs of scheduled routines, including this one, unless sid typed in them. claude.ai chats outside Claude Code are not readable here.

## 3. Decide what counts

- done: finished, sent, submitted, shipped, attended, booked. Needs evidence from a source.
- let go: dropped from the list, declined, untracked on purpose. This is closure. Always include it when there is any.
- moved forward: real progress without finishing. Nudges sent, waiting on someone, a draft that went out.
- tomorrow: the top 3 open items from Instinct's last `*Today*` list, plus anything booked for tomorrow. Three items at most.
- Things Instinct did on its own count only where they moved one of sid's items.
- One event, one line. Merge duplicates across sources.

## 4. Write the note

Write to `what-i-got-done/YYYY/YYYY-MM-DD.md`, dated by `window_end` in IST. If the run happens after midnight, date it by the day that just ended.

```
---
date: YYYY-MM-DD
window_start: <ISO with +05:30>
window_end: <ISO with +05:30>
sources_missing: []
---

# <ddd d mmm> - what did i get done

<one or two lines on the shape of the day>

done:
- ...

let go:
- ...

moved forward:
- ...

tomorrow:
- ...

<one closing line - an honest observation, e.g. something carried too many days>
```

Leave out a section when it is empty. Aim for under 200 words.

### Voice

The note is written as sid, in first person, for himself. Read the full voice guide from Google Drive when the connector is there (id in `context/sources.md`). The rules that matter here:

- Lowercase is fine. Lowercase "i" is fine.
- Use a spaced hyphen " - " for every dash. Never an em-dash.
- Observation first, then the "so what" after the hyphen.
- Concrete over abstract. Names, products, PR numbers, times.
- Plain labels with a colon on their own line. No bold. No emoji as bullets.
- British/Indian spelling: realise, organise, programme, colour.
- One emoji at most, only at the end.
- Hedge with "i think" or "seems like" when a line is an inference, then still say it.
- Never: delve, tapestry, synergy, robust, seamless, unlock, supercharge, game-changer, "excited to".
- Do not invent feelings. If the day's mood is not in the data, leave it out.

## 5. Push, send, show

1. In `~/ai-chief-of-staff-private`: `git add what-i-got-done/YYYY/YYYY-MM-DD.md && git commit -m "day: YYYY-MM-DD" && git push -q origin main`. If the push fails, say so. The note is safe in the local commit, and the next auto-sync push carries it.
2. Send it to PostHog: `python3 .claude/hooks/posthog_what_i_got_done_capture.py`. Codex and other harnesses without Claude Code hooks need this call. In Claude Code the Stop hook would send it too, and the ledger keeps it to one event.
3. Post the full note in chat. Under it, list every line that is an inference with its source.
4. If sid asks for changes, edit the note in place and run steps 1 and 2 again. The fix goes out as a new commit and a new event with a higher `revision`.
