---
name: garmin-monthly-coach
description: Run an incremental Garmin data refresh or a longitudinal training review from the private Chief of Staff database. Use for Garmin coach check-ins, fresh training-data reviews, and weekly-report integration.
---

# Garmin Monthly Coach

Use this skill for Garmin syncs and analysis. The activity database and athlete-specific context are private; this skill contains only reusable workflow and classification rules.

## Private source of truth

Read Garmin data from `garmin/`, the local symlink to the private companion repository. If it is unavailable, check the private checkout's `garmin/` directory. Never create a second copy of the activity database.

Before a monthly review, read:

- `garmin/DATABASE_SCHEMA.md` for table definitions and stable keys.
- `garmin/COACHING_PROFILE.md` for private athlete-specific heart-rate and long-run guardrails.
- `garmin/data/garmin_data.json` for metric histories and `metadata.last_successful_sync`.
- The last object in `garmin/analysis/coach_reviews.jsonl` and the latest report in `garmin/reports/`.

Use the Garmin MCP connector for new personal data when available. Preserve source values, label derived calculations, and never invent missing fields. Do not store credentials or tokens.

## Incremental data refresh

Use this mode when `/weekly-coach` needs a fresh Garmin summary or the user asks for a fresh pull without a full monthly review.

1. Read `last_successful_sync` from the canonical metadata. Fetch running activities from that point with a 72-hour overlap through the current date. Retrieve splits and typed run/walk/stand blocks for new or corrected activities, plus available lactate-threshold, VO2-max, training-status, and training-load data.
2. Upsert activities by `activity_id`, laps by `activity_id + lap_number`, and typed blocks by `activity_id + messageIndex + type`. Preserve shorter laps and blocks; exclude laps under 400 m or 60 s only from lap-level calculations.
3. Update metric histories, database row counts, and sync metadata in `garmin/data/garmin_data.json`. Keep activity rows only in CSVs; do not duplicate them in JSON.
4. Validate JSON, CSV headers, unique keys, parent coverage, row counts, and date freshness.

This mode updates the canonical database only. It does not append a monthly review or create another report. If the Garmin connector is unavailable, use the last stored sync, mark the week incomplete where its dates are not covered, and do not infer that no activity happened.

## Weekly report integration

When `/weekly-coach` runs, refresh Garmin data first if the connector is available, then add a concise `Running (Garmin)` section to that week's private `weeks/<ISO-week>/reflection.md`. Use Monday through Sunday for the report week.

Include only evidence supported by the database:

- sync date and whether the report week is fully covered;
- run count, total distance and duration;
- easy-long-run count and verified structured-session count, using the private coaching profile and typed/lap evidence;
- spacing or large load changes when relevant; and
- latest dated VO2 max, lactate-threshold HR/speed/power, and Garmin load/status context when available.

Lead with process adherence, then outcomes. Automatic Garmin `INTERVAL` lap labels alone do not prove structured intervals. Use the private profile's thresholds only inside private reports and conversations. Do not copy raw Garmin rows, routes, exact personal metrics, or the profile into this public repository. The weekly reflection is the weekly report; do not duplicate the database or create a second Garmin report for the same week.

## Monthly coach review

Compare the trailing 28 days with the previous 28 days and the January 1, 2026-to-present baseline. January 1 is the analytical baseline, not the fetch start. Process comes first: easy long runs, easy-time share, structured intervals and recoveries, spacing between hard days, load spikes, and follow-through on the prior one or two recommendations. Outcomes follow: VO2 max direction and variability, lactate-threshold HR/speed/power, comparable pace or power at similar HR, HR drift, and Garmin training-load response.

Use these reusable classification rules; use the private profile for athlete-specific aerobic guardrails:

- **Usable lap:** at least 400 m and 60 s.
- **Structured interval session:** at least three repeated, comparable active bouts with recoveries of at least 90 s. Verify the work/recovery pattern; automatic lap labels are insufficient.
- **Threshold-style session:** sustained work near current lactate-threshold intensity, supported by duration, effort, and structure. Cardiac drift or an uninterrupted hard run alone is insufficient.
- **Easy long run:** meet the private profile's duration/distance and aerobic-control criteria, including HR drift when the data supports it.

For a completed monthly review, append exactly one object to `garmin/analysis/coach_reviews.jsonl`, create one immutable `garmin/reports/coach_report_YYYY-MM-DD.md`, update `garmin/LATEST.md`, and append `garmin/CHANGELOG.md`. Weekly refreshes do not create these monthly artifacts.

Separate verified Garmin facts, derived calculations, and coaching inference. Treat single Garmin metric updates as noisy. If a value is missing, stale, or based on a partial window, state that limitation. Training guidance is not medical diagnosis.

## Completion checks

For a database refresh or monthly review, validate JSON syntax, CSV headers, stable-key uniqueness, parent coverage, row counts, sync freshness, and that only one canonical database exists. For a monthly review, also validate period boundaries, comparison metrics, the appended review object, the timestamped report, and `LATEST.md` links. If Garmin or repository access fails, stop without fabricating or changing canonical data.
