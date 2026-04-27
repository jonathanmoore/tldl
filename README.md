# TLDL — Too Long; Didn't Listen

A small MCP server that turns a YouTube, Spotify, or Apple Podcasts URL into a markdown transcript using the platforms' own auto-captions — no LLM transcription, no audio download. Runs locally over stdio or self-hosted over HTTP (Railway-ready). Public source, private deployment behind a bearer token.

> **Too Long; Didn't Listen. Your AI did.**\
> Useful for note-taking, summaries, or just talking to Claude about a podcast you skipped.

## Quickstart

Open this repo in [Claude Code](https://claude.com/claude-code) and say:

> help me get this set up

Or run `/setup`. The setup skill walks you through local install → testing → optional Railway deployment → migration. It uses stdio for local (no token, no second terminal) and HTTP for Railway.

## What it does

One MCP tool:

```
get_transcript(url, language="en", include_timestamps=False) -> markdown
```

- **YouTube URLs** (`youtube.com/watch`, `youtu.be`, `/shorts/`, `/embed/`, `/live/`) — fetches manual or auto-generated captions and renders coalesced paragraphs with YAML frontmatter (title, channel, duration, language, fetched_at, etc.).
- **Spotify episode URLs** (`open.spotify.com/episode/...`) — Spotify has no public transcript API, so the server resolves the episode title via Spotify's oEmbed endpoint, finds the same upload on YouTube via search, and fetches captions there. Works for podcasts that double-post. Spotify-exclusives return a clear error naming the best guess so you can decide whether to find an alternate source.
- **Apple Podcasts URLs** (`podcasts.apple.com/.../id<show>?i=<episode>`) — same pattern as Spotify but via the public iTunes Lookup API to get the episode title. Apple-exclusives won't work; very old episodes (outside the most recent 200 for a show) return a clear "out of lookup window" error.
- Optional `include_timestamps=true` adds `## [MM:SS]` section markers every 5 minutes.

## How it works

The server picks one of two transports based on `TLDL_TRANSPORT`:

- **`stdio`** (default, local dev) — Claude Code spawns the process directly. No bearer token, no port, no second terminal. The process boundary is the trust boundary.
- **`http`** (Railway, anything self-hosted) — uvicorn on `$PORT`, MCP at `/mcp`, healthcheck at `/healthz`, bearer-token auth via FastMCP's `StaticTokenVerifier`. The Dockerfile pins this mode so production never falls back to stdio.

Both transports expose the same single tool. The setup skill picks the right one for you.

### Why a proxy is required on Railway

YouTube aggressively blocks transcript requests from cloud-provider IPs. On a residential connection it works without a proxy; on Railway it will fail without one. The server has built-in support for [Webshare](https://www.webshare.io) residential proxies (cheap, ~$1/GB; transcripts are tiny so even the smallest plan lasts forever). Set the proxy env vars below and the underlying library handles rotation.

### A note on Claude clients

The Claude.ai / Claude Desktop **Custom Connectors** UI only supports OAuth — you can't paste a bearer token through it ([source](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)). For a single-user self-hosted server like this one, **Claude Code (CLI)** is the path that works. If you need claude.ai web/desktop access, you'd have to add OAuth to the server (out of scope here).

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `TLDL_TRANSPORT` | no | `stdio` (default, local) or `http` (Railway). The Dockerfile sets `http`. |
| `MCP_BEARER_TOKEN` | when http | Required when `TLDL_TRANSPORT=http`. Not needed for stdio. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `WEBSHARE_PROXY_USERNAME` | for Railway | Webshare proxy username (not your account email) |
| `WEBSHARE_PROXY_PASSWORD` | for Railway | Webshare proxy password |
| `WEBSHARE_PROXY_LOCATIONS` | no | Comma-separated 2-letter country codes, e.g. `us,de` |
| `LOG_LEVEL` | no | Default `INFO`. Use `DEBUG` to trace requests |
| `PORT` | no | Railway injects this; do not set it |

## Limitations

- **Platform-exclusive content** won't work — for Spotify (some Joe Rogan, Gimlet, Spotify Originals) and Apple Podcasts (Apple-exclusives) there's no YouTube version to fall back to. Error message names the best guess so you can decide.
- **Apple Podcasts lookup window** is the most recent 200 episodes per show (iTunes Lookup limit). Older episodes return an "out of lookup window" error.
- **Caption-disabled videos** return a clear "captions disabled" error.
- **Caption quality varies** with audio quality and accent. The server can't fix bad source captions.
- **Long episodes (3+ hours)** can take 20–30s to render. Within Railway's healthcheck timeout, but close.
- The transcript libraries (`youtube-transcript-api`, `yt-dlp`) reverse-engineer YouTube's endpoints. YouTube changes them periodically; bump those deps when things start failing.
- **Webshare pools occasionally get blocked** under load. If a region's pool stops working, change `WEBSHARE_PROXY_LOCATIONS` to a different country and redeploy.

## Project layout

```
.
├── pyproject.toml           # uv-managed deps
├── uv.lock
├── Dockerfile               # uv slim base + uvicorn on $PORT (TLDL_TRANSPORT=http)
├── railway.json             # Dockerfile builder + /healthz healthcheck
├── .env.example
├── .gitignore
├── CLAUDE.md                # project rules for Claude Code agents
├── README.md
└── src/tldl/
    ├── __init__.py
    ├── config.py            # env-var loader, transport selection, fail-closed
    ├── markdown.py          # frontmatter + paragraph coalescing
    ├── youtube.py           # video_id parse + proxy-aware transcript fetch + yt-dlp metadata
    ├── resolver.py          # shared YouTube search + rapidfuzz scoring (used by Spotify + Apple)
    ├── spotify.py           # oEmbed → resolver
    ├── apple.py             # iTunes Lookup → resolver
    └── server.py            # FastMCP app, get_transcript tool, /healthz, stdio/http entrypoint
```

## Credits

This project would not exist without:

- **[youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)** by [@jdepoix](https://github.com/jdepoix) — does the entire transcript-fetching layer including the Webshare proxy integration. This server is essentially a wrapper around it.
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — YouTube metadata extraction and the `ytsearch1:` fallback used to resolve Spotify episodes to YouTube.
- **[FastMCP](https://gofastmcp.com)** — the MCP server framework, including built-in bearer-token auth via `StaticTokenVerifier`.
- **[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)** — fuzzy string matching for Spotify→YouTube confidence scoring.
- **[Webshare](https://www.webshare.io)** — residential proxies, the only practical way to fetch YouTube captions from a cloud host.

## License

MIT.
