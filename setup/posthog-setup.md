# PostHog Setup Guide — Analytics for the Chief of Staff

Track how often `/email-triage` runs, the P0/P1/P2 mix over time, and build a dashboard over it. Setup takes about 5 minutes.

> Use a **new, personal PostHog project** — not a shared/production one. The hook sends data on every triage run.

---

## 1. Create the project

1. Sign in to the PostHog account you want to use.
2. Create a new project (suggested name: `chief-of-staff`).
3. From **Project Settings → API Keys**, copy:
   - **Project API key** (`phc_…`) — write key for event capture.
4. From **Personal Settings → Personal API Keys**, create a key scoped to this project only. Copy:
   - **Personal API key** (`phx_…`) — read/write key for the MCP server.

---

## 2. Set env vars (via direnv)

Env vars live in a project-local `.env` file (gitignored) and load automatically when you `cd` into the project via [direnv](https://direnv.net/).

Install direnv once:

```bash
brew install direnv
# add this to ~/.zshrc (once):
eval "$(direnv hook zsh)"
```

Create `.env` in the project root:

```bash
export POSTHOG_API_KEY="phc_..."              # project write key, used by the hook
export POSTHOG_HOST="https://us.posthog.com"  # or https://eu.posthog.com
export POSTHOG_PERSONAL_API_KEY="phx_..."     # personal key, used by the MCP server
```

The repo already ships with an `.envrc` containing `dotenv`, which tells direnv to source `.env`. Authorize it once:

```bash
cd ~/ai-chief-of-staff
direnv allow .
```

Verify (after `cd`-ing into the project):

```bash
echo $POSTHOG_API_KEY | head -c 8        # → phc_
echo $POSTHOG_PERSONAL_API_KEY | head -c 8   # → phx_
```

**Alternative (no direnv):** Keep the same `.env` and manually `source .env && claude` every time you start a session.

---

## 3. Register the PostHog MCP server

The capture hook (`posthog-capture.sh`) is already registered in both `PostToolUse` and `Stop` arrays in `.claude/settings.json` — no changes needed there.

You do need to add the PostHog MCP server so Claude can read your project (create dashboards, run queries, etc.). Add this under `mcpServers` in `.claude/settings.json`:

```json
"mcpServers": {
  "gmail": {
    "type": "http",
    "url": "https://gmail.mcp.claude.com/mcp"
  },
  "posthog": {
    "type": "http",
    "url": "https://mcp.posthog.com/mcp",
    "headers": {
      "Authorization": "Bearer ${POSTHOG_PERSONAL_API_KEY}"
    }
  }
}
```

Restart Claude Code after editing so the MCP server picks up the env var.

---

## 4. Verify end-to-end

### MCP reachable

Start a new Claude Code session from the project root and run `/mcp`. You should see `posthog` listed.

In a Claude session, ask: "Use the PostHog MCP to get the current project details." It should return your new project (confirm the ID is **not** any production project).

### Hook fires

```bash
# Send a test event directly (sanity check before running /email-triage):
curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$POSTHOG_API_KEY\",\"event\":\"setup_test\",\"distinct_id\":\"$(whoami)\"}" \
  "$POSTHOG_HOST/i/v0/e/"
# Expect: {"status":1} or similar 1xx status
```

Then run `/email-triage` in Claude Code. After it completes:

- `email-runs/<YYYY-MM-DD>.md` gets a new `## HH:MM` section (file is created if first run of the day).
- `logs/hook-debug.log` shows `[posthog] PostHog response: {"status":1}`.
- In PostHog, **Activity → Live events** shows `triage_run` with `p0_count`, `p1_count`, `p2_count` properties.

### Graceful degradation

`unset POSTHOG_API_KEY` in a shell, run `/email-triage`, and confirm the triage still logs to `email-runs/<DATE>.md` (the hook exits 0 silently when the key is missing).

---

## 5. Build the dashboard

Once 3+ events have landed, ask Claude in a session:

> "Using the PostHog MCP, create a dashboard called 'Chief of Staff Telemetry' with three insights:
> 1. Daily trend of `triage_run` over 30 days.
> 2. Weekly average of `p0_count`, `p1_count`, `p2_count`.
> 3. Day-of-week breakdown of `triage_run` count."

The dashboard is regenerable via MCP — no code artifact needed.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/mcp` doesn't list `posthog` | MCP entry missing from `settings.json` (see step 3), or `POSTHOG_PERSONAL_API_KEY` unset in the shell that launched Claude Code |
| No events in PostHog, no errors in `hook-debug.log` | `posthog-capture.sh` not in the hook arrays in `settings.json` |
| `curl failed` in `hook-debug.log` | Wrong `POSTHOG_HOST` or invalid `phc_…` key |
| `403 / 401` response | Using personal key (`phx_…`) where project key (`phc_…`) is expected, or vice versa |
