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

YouTube blocks transcript requests from cloud/datacenter IPs, and paid residential-proxy workarounds aren't worth their monthly cost for a single-user tool. Run TLDL from a residential connection — corporate egress, datacenter IPs, and most VPNs will also get blocked.

## Limitations

- **Local only.** Run TLDL from a residential connection; cloud hosting isn't supported.
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
├── .env.example             # LOG_LEVEL
├── .gitignore
├── CLAUDE.md                # project rules for Claude Code agents
├── README.md
└── src/tldl/
    ├── __init__.py
    ├── markdown.py          # frontmatter + paragraph coalescing
    ├── youtube.py           # video_id parse + transcript fetch + yt-dlp metadata
    ├── resolver.py          # shared YouTube search + rapidfuzz scoring (used by Spotify + Apple)
    ├── spotify.py           # oEmbed → resolver
    ├── apple.py             # iTunes Lookup → resolver
    └── server.py            # FastMCP app, get_transcript tool, stdio entrypoint
```

## Credits

This project would not exist without:

- **[youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)** by [@jdepoix](https://github.com/jdepoix) — does the entire transcript-fetching layer.
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — YouTube metadata extraction and the `ytsearch1:` fallback used to resolve Spotify episodes to YouTube.
- **[FastMCP](https://gofastmcp.com)** — the MCP server framework.
- **[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)** — fuzzy string matching for Spotify→YouTube confidence scoring.

## License

MIT.
