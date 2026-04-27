---
name: setup
description: Walk a new user through getting TLDL running locally and testing the transcript tool. Triggered by "/setup" or natural-language requests like "help me set this up".
---

# TLDL setup skill

You are guiding the user through setting up TLDL — an MCP server that turns YouTube/Spotify/Apple Podcasts URLs into markdown transcripts. TLDL runs locally over stdio (Claude Code spawns the process; no token, no port, no second terminal).

Address yourself as the actor: you run commands, you verify output, you ask the user only when input is genuinely required.

**Local-only is intentional.** TLDL is stdio-only. There is no HTTP transport, no bearer-token auth, no cloud-hosting story.

## Phase 1 — State detection

Before anything else, run:

```
claude mcp list
git status
```

Branch on what you find:

- **`tldl-local` is registered** → local stdio is set up. Check whether the `get_transcript` MCP tool is exposed in this session:
  - **If `get_transcript` IS exposed**: this is almost certainly a post-Phase-4.5 restart. Say "Welcome back — `tldl-local` is connected and the `get_transcript` tool is available. Running the self-test now." Skip directly to Phase 5.
  - **If `get_transcript` is NOT exposed**: registration happened in a prior session but tools haven't loaded. Tell the user to restart Claude Code (per Phase 4.5) and stop.
  - If the user's intent is clearly something else (e.g. they typed "uninstall tldl"), honor that — branch to the relevant phase.
- **`tldl` is registered** → an HTTP entry exists from a prior cloud deploy. TLDL no longer ships an HTTP transport. Remove the dead entry (`claude mcp remove tldl --scope user`) and continue to Phase 2 for a fresh local install. If the user previously deployed to Railway (or any cloud), remind them to delete the service in their provider's dashboard so they stop being billed.
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

Required: `uv` any recent version, Python ≥ 3.12, git, claude CLI.

If anything is missing, present a checklist with install hints:

- `uv` → `brew install uv` (macOS) or see https://docs.astral.sh/uv/getting-started/installation/
- Python 3.12+ → `brew install python@3.12` (macOS) or https://www.python.org/downloads/
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
claude mcp add --scope user tldl-local -- uv run --directory $(pwd) python -m tldl.server
```

Use literal `$(pwd)` so the registration is repo-location-agnostic. Then:

```
claude mcp list
```

Confirm `tldl-local` shows `✓ Connected`. If it shows failed, the most common causes are: (1) `uv sync` was skipped or failed; (2) the user is running this from outside the repo so `$(pwd)` resolved to the wrong path — in that case, remove the entry (`claude mcp remove tldl-local --scope user`) and re-run from the repo root.

Tell the user, briefly:

> Claude Code spawns the Python server on demand and shuts it down when the session ends. No separate terminal, no token, no port — TLDL only runs over stdio.

### Phase 4.5 — STOP and restart Claude Code

**Hard stop.** Claude Code loads MCP tools at session startup. The `get_transcript` tool is *not* available in this session even though `claude mcp list` shows `tldl-local` connected — it will only appear after you restart.

Resolve the actual repo path first (run `pwd` if you don't already have it from Phase 1) and substitute it into the message below before speaking — the user should see their real path, not a literal `$(pwd)`.

Tell the user (substituting `<REPO_PATH>` with the resolved absolute path):

> `tldl-local` is registered and showing connected. To actually use the `get_transcript` tool I need you to restart Claude Code:
>
> 1. End this session: type `/exit` or press Ctrl+D
> 2. From `<REPO_PATH>`, run `claude` to start a fresh session
> 3. In the new session, say `/setup` or "continue tldl setup"
>
> The skill will detect `tldl-local` is already registered and pick up at the self-test. I'm stopping here — see you on the other side.

**Do not proceed past this point in the current session. Do not run the self-test in this session.** Specifically:

- Do NOT invoke `get_transcript` via `python -c "from tldl.server import get_transcript; ..."` or any other direct Python call. That proves the code imports — it does not prove the MCP integration works, which is the entire point of the self-test.
- Do NOT spawn the server via `uv run python -m tldl.server` to "test it manually."
- Do NOT register the MCP a second time, edit `~/.claude.json` directly, or invent any other workaround.

The only acceptable path forward is the user restarting Claude Code. If they push back ("just test it now"), explain that any in-session test would be a false positive: it would pass even if the MCP wiring were broken, because it bypasses the wiring. Then stop and wait.

## Phase 5 — Self-test

**Precondition check first.** Before doing anything, verify the `get_transcript` MCP tool is exposed in *this* session. List the MCP tools you have access to. If `get_transcript` (from the `tldl-local` server) is not in your tool list, the user is in a session that started before registration. Tell them to restart Claude Code per Phase 4.5 and stop. Do not attempt a Python fallback, do not re-register, do not invent workarounds.

If the tool is exposed, continue.

Load `.claude/skills/setup/test-urls.md` from this same directory for the canonical test URLs. Read the file end-to-end, including the stability caveat at the bottom — if the Apple URL has aged out of the iTunes lookup window, treat that as a `test-urls.md` maintenance task (ask the user for a more recent Apple Podcasts URL), not a code bug.

For each URL in the file:

1. Call the `get_transcript` MCP tool (not a Python import) with the URL.
2. Check the returned markdown's YAML frontmatter for the expected `source:` value (and `match_confidence` where listed).
3. Tell the user what was tested and whether it passed.

If a call fails *through the MCP layer* (timeout, transport error, tool-not-found), that is a real bug — surface it. Do not retry by switching to a non-MCP invocation.

If the pinned Apple URL has aged out of the iTunes lookup window (the resolver returns "out of lookup window"), say so to the user and ask for a more recent Apple Podcasts URL. Note this as a `test-urls.md` maintenance task rather than a code bug.

Diagnose failures:

- **YouTube fails with IP-block / 429-ish error** → likely a non-residential IP (VPN, cloud workspace, corporate egress). Ask the user to disable VPN and retry. There is no proxy escape hatch — TLDL only works from a residential connection.
- **Spotify or Apple resolution fails** → resolver couldn't find a YouTube match. Try a different episode. If `match_confidence` is below 0.5 the resolver intentionally refuses; this is correct behavior, not a bug.
- **Unsupported URL fails with a stack trace instead of `ToolError("Unsupported URL ...")`** → real bug. Surface it: file path `src/tldl/server.py`, function `get_transcript`.

## Phase 6 — Wrap up

Summarize what was done:

- Local stdio MCP `tldl-local` was added (or removed, if the user was uninstalling).
- Self-test pass/fail per platform.

Mention undo:

- **Uninstall local**: `claude mcp remove tldl-local --scope user`.

If the user asks about remote access: not supported. TLDL is stdio-only and runs on the same machine as Claude Code.
