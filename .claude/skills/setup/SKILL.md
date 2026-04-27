---
name: setup
description: Walk a new user through getting TLDL running locally, testing the transcript tool, optionally deploying to Railway, and migrating from local-stdio to remote-HTTP. Triggered by "/setup" or natural-language requests like "help me set this up".
---

# TLDL setup skill

You are guiding the user through setting up TLDL — an MCP server that turns YouTube/Spotify/Apple Podcasts URLs into markdown transcripts. Local install uses stdio transport (no token, no port, no second terminal). Railway deployment uses HTTP transport with a bearer token.

Address yourself as the actor: you run commands, you verify output, you ask the user only when input is genuinely required (a Webshare credential, a Railway domain, a yes/no branch).

## Phase 1 — State detection

Before anything else, run:

```
claude mcp list
git status
```

Branch on what you find:

- **`transcripts-local` is registered** → local stdio is set up. Ask the user: "You already have a local TLDL registered. Want to (a) re-run the self-test, (b) deploy to Railway and migrate to HTTP, (c) uninstall, or (d) rotate the bearer token on a deployed instance?" Skip to the relevant phase.
- **`transcripts` is registered** → an HTTP entry already exists. Ask: "Looks like a deployed TLDL is already wired up. Want to (a) re-run the self-test against it, (b) rotate the bearer token, (c) switch back to local stdio for dev, or (d) uninstall?"
- **Both are registered** → coexistence is intentional. Ask which one the user wants to operate on.
- **Neither is registered** → fresh install. Continue to Phase 2.

If `git status` shows the repo is dirty in suspicious ways (e.g. `pyproject.toml` or `src/` modified), flag it but don't block — the user may be developing.

## Phase 2 — Prereq check

Run each of these and collect results:

```
uv --version
python3 --version
git --version
claude --version
```

Required: `uv` any recent version, Python ≥ 3.12, git, claude CLI. If the deploy phase is on the table, also check `gh --version`.

If anything is missing, present a checklist with install hints:

- `uv` → `brew install uv` (macOS) or see https://docs.astral.sh/uv/getting-started/installation/
- Python 3.12+ → `brew install python@3.12` (macOS) or https://www.python.org/downloads/
- `gh` → `brew install gh` (macOS) or https://cli.github.com/
- `claude` → https://docs.claude.com/en/docs/claude-code

Do not proceed until all required tools are present. Re-check after the user installs.

## Phase 3 — Local install

From the repo root:

```
uv sync
```

Confirm it completes without errors. If it fails on Python version, the user's `python3` may not be 3.12+ even if a newer one is installed elsewhere — check `uv python list` and suggest `uv python install 3.12`.

## Phase 4 — Register the stdio MCP

Run, from the repo root, exactly:

```
claude mcp add --scope user transcripts-local -- uv run --directory $(pwd) python -m tldl.server
```

Use literal `$(pwd)` so the registration is repo-location-agnostic. Then:

```
claude mcp list
```

Confirm `transcripts-local` shows `✓ Connected`. If it shows failed, the most common causes are: (1) `uv sync` was skipped or failed; (2) the user is running this from outside the repo so `$(pwd)` resolved to the wrong path — in that case, remove the entry (`claude mcp remove transcripts-local --scope user`) and re-run from the repo root.

Tell the user, briefly:

> Claude Code spawns the Python server on demand and shuts it down when the session ends. No separate terminal, no token, no port. That's stdio mode. When `TLDL_TRANSPORT` is unset the server defaults to stdio.

## Phase 5 — Self-test

Load `.claude/skills/setup/test-urls.md` from this same directory for the canonical test URLs.

For each URL in the file:

1. Call `get_transcript` with the URL.
2. Check the returned markdown's YAML frontmatter for the expected `source:` value (and `match_confidence` where listed).
3. Tell the user what was tested and whether it passed.

If the pinned Apple URL has aged out of the iTunes lookup window (the resolver returns "out of lookup window"), say so to the user and ask for a more recent Apple Podcasts URL. Note this as a `test-urls.md` maintenance task rather than a code bug.

Diagnose failures:

- **YouTube fails with IP-block / 429-ish error** → likely a non-residential IP (VPN, cloud workspace, corporate egress). Ask the user to disable VPN and retry. Locally, no Webshare proxy is needed; on Railway it is.
- **Spotify or Apple resolution fails** → resolver couldn't find a YouTube match. Try a different episode. If `match_confidence` is below 0.5 the resolver intentionally refuses; this is correct behavior, not a bug.
- **Unsupported URL fails with a stack trace instead of `ToolError("Unsupported URL ...")`** → real bug. Surface it: file path `src/tldl/server.py`, function `get_transcript`.

## Phase 6 — Branch: done, or deploy?

Ask: "Local setup is working. Want to stop here, or deploy to Railway?"

If "done": remind the user they can re-run `/setup` later for deployment, rotation, or to uninstall. End cleanly.

If "deploy": continue to Phase 7.

## Phase 7 — Deploy to Railway

### 7a. Push to GitHub (if needed)

Check `git remote -v`. If no GitHub remote:

```
gh repo create tldl --public --source=. --push
```

**Confirm with the user before running this** — the repo will be public. (Secrets stay in Railway env vars, never in git, so public is fine for this project, but the user should know.)

### 7b. Railway dashboard (manual UI steps)

Walk the user through these steps from the README — this part can't be automated:

1. https://railway.com/dashboard → **New Project** → **Deploy from GitHub repo**.
2. Authorize the Railway GitHub app on the repo if prompted.
3. Select the repo. Railway detects the Dockerfile and starts a build.
4. Service tile → **Variables** tab → **RAW Editor**.

### 7c. Generate a fresh bearer token

```
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save the output — you'll need it twice (Railway env, and the `claude mcp add` later).

### 7d. Env var block

Have the user paste this into Railway's RAW Editor:

```
TLDL_TRANSPORT=http
MCP_BEARER_TOKEN=<token from 7c>
WEBSHARE_PROXY_USERNAME=<from webshare.io>
WEBSHARE_PROXY_PASSWORD=<from webshare.io>
WEBSHARE_PROXY_LOCATIONS=us
```

Note for the user: `TLDL_TRANSPORT=http` is also set in the Dockerfile, so it's redundant — but explicit-is-better-than-implicit, and it future-proofs against the Dockerfile changing. The Webshare credentials are the proxy username/password (not the account email); without them YouTube will block requests from Railway IPs.

If the user doesn't have a Webshare account, point them at https://www.webshare.io — the smallest plan (~$1/GB) is fine since transcripts are tiny.

### 7e. Generate domain

Service → **Settings** → **Networking** → **Public Networking** → **Generate Domain**. Ask the user to paste the resulting domain (e.g. `tldl-production.up.railway.app`).

### 7f. Verify deploy

```
curl https://<domain>/healthz
```

Expect `ok`. If it doesn't return ok, check Railway's Deploy Logs for `Application startup complete.`

Auth check (optional):

```
curl -X POST https://<domain>/mcp
```

Expect 401 with `invalid_token` JSON — that's correct, it means auth is wired up.

## Phase 8 — Migration: stdio → HTTP

Now switch the user's Claude Code from local stdio to the deployed HTTP server:

```
claude mcp remove transcripts-local --scope user
export TRANSCRIPT_MCP_TOKEN='<the bearer token from 7c>'
claude mcp add --scope user --transport http transcripts https://<domain>/mcp --header "Authorization: Bearer ${TRANSCRIPT_MCP_TOKEN}"
claude mcp list
```

Confirm `transcripts` shows `✓ Connected`.

Re-run the self-test from Phase 5 against the deployed server. **This is the single most important step** — it catches Webshare misconfiguration, which is the #1 deploy failure mode (YouTube blocking from Railway IPs). If YouTube fetches fail here but worked locally, the Webshare creds are wrong or missing.

Mention to the user: the local entry was named `transcripts-local` and the deployed one is `transcripts` on purpose — they could coexist. After migration the local one is gone, but the user can always re-add it for dev work without conflict.

## Phase 9 — Wrap up

Summarize what was done:

- Local stdio MCP `transcripts-local` was added/removed (whichever applies).
- Repo deployed to Railway at `https://<domain>` (if applicable).
- HTTP MCP `transcripts` registered with bearer auth (if applicable).
- Self-test pass/fail per platform.

Mention undo and rotation:

- **Uninstall local**: `claude mcp remove transcripts-local --scope user`.
- **Uninstall deployed**: `claude mcp remove transcripts --scope user` (and delete the Railway service if you want to stop paying for it).
- **Rotate bearer token**: Railway → Variables → update `MCP_BEARER_TOKEN` → Deploy. Then locally: `claude mcp remove transcripts --scope user` and re-run the `claude mcp add` from Phase 8 with the new token.
