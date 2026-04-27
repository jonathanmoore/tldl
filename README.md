# TLDL — Too Long; Didn't Listen

A small MCP server that turns a YouTube, Spotify, or Apple Podcasts URL into a markdown transcript using the platforms' own auto-captions — no LLM transcription, no audio download. Runs locally on your own machine over stdio.

> **Too Long; Didn't Listen. Your AI did.**\
> Useful for note-taking, summaries, or just talking to Claude about a podcast you skipped.

## Quickstart

Open this repo in [Claude Code](https://claude.com/claude-code) and say:

> help me get this set up

Or run `/setup`. The setup skill walks you through local install and testing.

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

Claude Code spawns the Python server over stdio when you start a session and shuts it down when the session ends. No port, no token, no second terminal — the process boundary is the trust boundary.

### Why local-only

YouTube aggressively blocks transcript requests from cloud-provider IPs. Residential-proxy services (Webshare and similar) used to be a workaround but have stopped working reliably — the request blocks now happen even on paid plans. Running TLDL on a cloud host (Railway, Fly, Render, etc.) is no longer a viable path, so this repo no longer ships Dockerfile / Railway config.

You need a residential connection. Corporate egress, datacenter IPs, and most VPNs will also get blocked.

### Future: Tailscale

The repo still has an HTTP transport (`TLDL_TRANSPORT=http`, bearer-token auth via FastMCP's `StaticTokenVerifier`, served by uvicorn on `$PORT`, healthcheck at `/healthz`). The intended future use is to run TLDL on one of your own machines (a NAS, a home server, a desktop that's always on) and reach it from your laptop via [Tailscale](https://tailscale.com). That setup isn't documented yet; for now, run TLDL on the same machine as Claude Code.

### A note on Claude clients

The Claude.ai / Claude Desktop **Custom Connectors** UI only supports OAuth ([source](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)). For a local stdio MCP like this, **Claude Code (CLI)** is the supported path.

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `TLDL_TRANSPORT` | no | `stdio` (default, local) or `http` (LAN / future Tailscale use). |
| `MCP_BEARER_TOKEN` | when http | Required when `TLDL_TRANSPORT=http`. Not needed for stdio. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `LOG_LEVEL` | no | Default `INFO`. Use `DEBUG` to trace requests |
| `PORT` | no | HTTP listen port. Default 8000. Only used in http mode. |

## Limitations

- **Local only.** YouTube blocks cloud/datacenter IPs; residential proxies no longer reliably bypass it. Run TLDL from a residential connection.
- **Platform-exclusive content** won't work — for Spotify (some Joe Rogan, Gimlet, Spotify Originals) and Apple Podcasts (Apple-exclusives) there's no YouTube version to fall back to. Error message names the best guess so you can decide.
- **Apple Podcasts lookup window** is the most recent 200 episodes per show (iTunes Lookup limit). Older episodes return an "out of lookup window" error.
- **Caption-disabled videos** return a clear "captions disabled" error.
- **Caption quality varies** with audio quality and accent. The server can't fix bad source captions.
- The transcript libraries (`youtube-transcript-api`, `yt-dlp`) reverse-engineer YouTube's endpoints. YouTube changes them periodically; bump those deps when things start failing.

## Project layout

```
.
├── pyproject.toml           # uv-managed deps
├── uv.lock
├── .env.example
├── .gitignore
├── CLAUDE.md                # project rules for Claude Code agents
├── README.md
└── src/tldl/
    ├── __init__.py
    ├── config.py            # env-var loader, transport selection, fail-closed
    ├── markdown.py          # frontmatter + paragraph coalescing
    ├── youtube.py           # video_id parse + transcript fetch + yt-dlp metadata
    ├── resolver.py          # shared YouTube search + rapidfuzz scoring (used by Spotify + Apple)
    ├── spotify.py           # oEmbed → resolver
    ├── apple.py             # iTunes Lookup → resolver
    └── server.py            # FastMCP app, get_transcript tool, /healthz, stdio/http entrypoint
```

## Credits

This project would not exist without:

- **[youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)** by [@jdepoix](https://github.com/jdepoix) — does the entire transcript-fetching layer.
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — YouTube metadata extraction and the `ytsearch1:` fallback used to resolve Spotify episodes to YouTube.
- **[FastMCP](https://gofastmcp.com)** — the MCP server framework, including built-in bearer-token auth via `StaticTokenVerifier`.
- **[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)** — fuzzy string matching for Spotify→YouTube confidence scoring.

## License

MIT.
