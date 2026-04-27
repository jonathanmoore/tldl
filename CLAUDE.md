# TLDL — Project Rules for Claude

## What this is
A FastMCP server that turns YouTube, Spotify, and Apple Podcasts URLs into markdown transcripts using the platforms' own captions. Dual-transport: stdio for local dev, HTTP for self-hosted deploys (Railway).

## Architecture invariants
- The server has two transport modes selected by `TLDL_TRANSPORT`: `stdio` (local default, no auth, spawned by Claude Code) and `http` (Railway, bearer-token auth, uvicorn). `mcp.http_app()` is exposed at module scope as `app` for the Dockerfile start command.
- Bearer token is required ONLY when transport is http. stdio uses the process boundary as the trust boundary.
- The Dockerfile sets `TLDL_TRANSPORT=http` so production never accidentally runs stdio.

## Setup skill is the source of truth for onboarding
The user-facing onboarding flow lives in `.claude/skills/setup/SKILL.md`. The README is intentionally minimal and points users to the skill.

**When you change any of these files, you MUST re-read `.claude/skills/setup/SKILL.md` and update it if anything in your change makes the skill's instructions wrong:**
- `pyproject.toml` (deps, Python version)
- `Dockerfile`, `railway.json` (deploy config)
- `.env.example` (env vars)
- `src/tldl/config.py` (env var loading, what's required when)
- `src/tldl/server.py` (transport selection, the `get_transcript` tool signature, auth)
- The "Environment variables" or "Limitations" sections of `README.md`

**When you add a new platform handler (e.g., a new podcast service):**
1. Add a representative URL + expected frontmatter snippet to `.claude/skills/setup/test-urls.md`
2. Add a self-test step in `.claude/skills/setup/SKILL.md` Phase 5
3. Update the supported-URLs bullet in `README.md`
4. Run the self-test against the new platform before declaring done

## Coding conventions
- Python 3.12+, uv-managed.
- FastMCP for the MCP layer; do not introduce a second MCP framework.
- Errors raised from tool handlers should be `ToolError` with friendly messages; map library exceptions in `_friendly_error`.
- No LLM transcription, no audio download — this server is strictly a captions wrapper.

## Don't
- Don't commit secrets. `.env` is gitignored; `.env.example` is the template.
- Don't add OAuth or session auth — bearer-token-only is intentional for the single-user self-hosted model.
- Don't add new transports beyond stdio and http without discussion.
