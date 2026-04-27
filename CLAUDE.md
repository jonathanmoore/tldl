# TLDL — Project Rules for Claude

## What this is
A FastMCP server that turns YouTube, Spotify, and Apple Podcasts URLs into markdown transcripts using the platforms' own captions. **Local-only, stdio-only.** Claude Code spawns the process; the process boundary is the trust boundary.

## Architecture invariants
- Single transport: stdio. `server.py` exposes `mcp = FastMCP(...)` and `main()` calls `mcp.run()`. There is no HTTP server, no bearer-token auth, no `/healthz`.
- **No cloud hosting.** YouTube blocks transcript requests from cloud/datacenter IPs, and Webshare-style residential-proxy services have stopped reliably bypassing it. Do not add a Dockerfile, deploy config, or proxy code path back. If a future cloud workaround appears, discuss before re-adding.
- TLDL must be run from a residential connection. The `IpBlocked` / `RequestBlocked` friendly error tells the user this — do not rewrite it to suggest a proxy.
- If HTTP transport is ever needed again (e.g. for a Tailscale-exposed home-server path), the prior implementation can be recovered from git history before this commit: `mcp.http_app()` served by uvicorn, bearer-token auth via FastMCP's `StaticTokenVerifier`, with a `/healthz` route. Do not rebuild it speculatively — only add it back when there's a concrete user need.

## Setup skill is the source of truth for onboarding
The user-facing onboarding flow lives in `.claude/skills/setup/SKILL.md`. The README is intentionally minimal and points users to the skill.

**When you change any of these files, you MUST re-read `.claude/skills/setup/SKILL.md` and update it if anything in your change makes the skill's instructions wrong:**
- `pyproject.toml` (deps, Python version)
- `.env.example` (env vars)
- `src/tldl/server.py` (the `get_transcript` tool signature, MCP setup)
- The "Limitations" section of `README.md`

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
- Don't add new transports beyond stdio without discussion.
- Don't re-introduce Webshare or any other proxy integration. Cloud hosting is not on the roadmap; if remote access is wanted, the path is "run TLDL on a home server, reach over Tailscale" — not proxies.
