# TLDL — Project Rules for Claude

## What this is
A FastMCP server that turns YouTube, Spotify, and Apple Podcasts URLs into markdown transcripts using the platforms' own captions. **Local-only**: stdio is the supported and documented transport. HTTP transport plumbing is retained for a future Tailscale-based path but is not currently set up by the onboarding flow.

## Architecture invariants
- Two transport modes are selected by `TLDL_TRANSPORT`: `stdio` (default, local, no auth, spawned by Claude Code) and `http` (uvicorn + bearer-token, intended for future LAN/Tailscale exposure). `mcp.http_app()` is exposed at module scope as `app` so the http path stays importable.
- Bearer token is required ONLY when transport is http. stdio uses the process boundary as the trust boundary.
- **No cloud hosting.** YouTube blocks transcript requests from cloud/datacenter IPs, and Webshare-style residential-proxy services have stopped reliably bypassing it. Do not add a Dockerfile, deploy config, or proxy code path back. If a future cloud workaround appears, discuss before re-adding.
- TLDL must be run from a residential connection. The `IpBlocked` / `RequestBlocked` friendly error tells the user this — do not rewrite it to suggest a proxy.

## Setup skill is the source of truth for onboarding
The user-facing onboarding flow lives in `.claude/skills/setup/SKILL.md`. The README is intentionally minimal and points users to the skill.

**When you change any of these files, you MUST re-read `.claude/skills/setup/SKILL.md` and update it if anything in your change makes the skill's instructions wrong:**
- `pyproject.toml` (deps, Python version)
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
- Don't re-introduce Webshare or any other proxy integration. Cloud hosting is not on the roadmap; the future remote-access story is Tailscale, not proxies.
