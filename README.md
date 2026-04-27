# TLDL — Too Long; Didn't Listen

A small MCP server that turns a YouTube, Spotify, or Apple Podcasts URL into a markdown transcript using the platforms' own auto-captions — no LLM transcription, no audio download. Deployable to Railway. Designed for personal use: public source, private deployment behind a bearer token.

> **Too Long; Didn't Listen. Your AI did.**\
> Useful for note-taking, summaries, or just talking to Claude about a podcast you skipped.

## What it does

One MCP tool:

```
get_transcript(url, language="en", include_timestamps=False) -> markdown
```

- **YouTube URLs** (`youtube.com/watch`, `youtu.be`, `/shorts/`, `/embed/`, `/live/`) — fetches manual or auto-generated captions and renders coalesced paragraphs with YAML frontmatter (title, channel, duration, language, fetched_at, etc.).
- **Spotify episode URLs** (`open.spotify.com/episode/...`) — Spotify has no public transcript API, so the server resolves the episode title via Spotify's oEmbed endpoint, finds the same upload on YouTube via search, and fetches captions there. Works for podcasts that double-post. Spotify-exclusives return a clear error naming the best guess so you can decide whether to find an alternate source.
- **Apple Podcasts URLs** (`podcasts.apple.com/.../id<show>?i=<episode>`) — same pattern as Spotify but via the public iTunes Lookup API to get the episode title. Apple-exclusives won't work; very old episodes (outside the most recent 200 for a show) return a clear "out of lookup window" error.
- Optional `include_timestamps=true` adds `## [MM:SS]` section markers every 5 minutes.

## Why a proxy is required on Railway

YouTube aggressively blocks transcript requests from cloud-provider IPs. On a residential connection it works without a proxy; on Railway it will fail without one. The server has built-in support for [Webshare](https://www.webshare.io) residential proxies (cheap, ~$1/GB; transcripts are tiny so even the smallest plan lasts forever). Set the proxy env vars below and the underlying library handles rotation.

## Try it locally

Recommended: get it working on `localhost` first, then deploy. From a residential connection you don't need Webshare — direct YouTube requests work.

### 1. Install and start the server

```bash
# Clone, install deps
git clone https://github.com/<you>/<repo> tldl
cd tldl
uv sync

# Generate and export a bearer token
export MCP_BEARER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "$MCP_BEARER_TOKEN"   # save this — you'll paste it in step 2

# Run the server (binds to 0.0.0.0:8000)
uv run python -m tldl.server
```

You should see `Uvicorn running on http://0.0.0.0:8000`. The MCP endpoint is `http://localhost:8000/mcp`; the healthcheck is `http://localhost:8000/healthz` (returns `ok`). Leave this terminal running.

### 2. Register the local server with Claude Code

In a **second terminal**:

```bash
export TRANSCRIPT_MCP_TOKEN='<paste the token from step 1>'

claude mcp add --scope user --transport http transcripts-local \
  http://localhost:8000/mcp \
  --header "Authorization: Bearer ${TRANSCRIPT_MCP_TOKEN}"

claude mcp list
```

`transcripts-local` should appear with `✓ Connected`.

### 3. Test it from a Claude session

```bash
claude
```

Try these prompts in order — watch the first terminal for `get_transcript url=...` log lines:

**Golden path — short YouTube video:**
> Use the get_transcript tool to fetch https://www.youtube.com/watch?v=jNQXAC9IVRw and return the markdown verbatim.

**Real podcast (long captions, exercises the paragraph coalescer):**
> Use get_transcript on https://www.youtube.com/watch?v=RaKFP_DuqpA and summarize the three biggest ideas.

**Spotify resolves to YouTube (a podcast that double-posts to both):**
> Use get_transcript on https://open.spotify.com/episode/1cXQalDxiGgptzM1nC7SCh and tell me what attribution change Meta made.

You should see `source: spotify-via-youtube` and `match_confidence: 0.6` in the frontmatter.

**Error path — unsupported URL:**
> Use get_transcript on https://example.com/foo

Expected: a clean `"Unsupported URL ..."` error, not a stack trace.

### 4. Clean up when done

```bash
# in terminal 2, stop using the local server
claude mcp remove transcripts-local --scope user

# in terminal 1, Ctrl+C the server
```

### Optional: MCP Inspector

If you want a visual UI to poke at the tool without going through Claude Code:

```bash
uv run fastmcp dev inspector src/tldl/server.py
```

---

## Deploying to Railway via GitHub

These instructions assume you push the repo to GitHub and connect that repo to a Railway service.

### 1. Push the repo to GitHub

```bash
gh repo create tldl --public --source=. --push
```

(Or use the GitHub UI — the repo can be public; secrets stay in Railway env vars, not in code.)

### 2. Create the Railway service

1. Open the [Railway dashboard](https://railway.com/dashboard) and click **New Project** → **Deploy from GitHub repo**.
2. If prompted, install/authorize the Railway GitHub app on your account and grant it access to the repo.
3. Select the repo. Railway creates the project and starts an initial build.
4. Railway detects `Dockerfile` (and the `railway.json` reinforces this with `"builder": "DOCKERFILE"`). It will use the Dockerfile, not Railpack/nixpacks.

### 3. Set environment variables

Click the service tile → **Variables** tab → **RAW Editor** → paste:

```env
MCP_BEARER_TOKEN=<paste a generated token>
WEBSHARE_PROXY_USERNAME=<your-webshare-username>
WEBSHARE_PROXY_PASSWORD=<your-webshare-password>
WEBSHARE_PROXY_LOCATIONS=us
```

Then click **Update Variables** → **Deploy** at the top of the canvas (Railway uses a staged-changes model; variables aren't applied until you click Deploy).

Generate the bearer token locally before pasting:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

`PORT` is injected automatically by Railway — do not set it.

### 4. Generate a public HTTPS URL

Railway does **not** auto-create a public URL. Click the service → **Settings** → **Networking** → **Public Networking** → **Generate Domain**. You'll get something like `tldl-production.up.railway.app` with a free auto-renewing SSL cert.

Your MCP endpoint is now `https://<service>-production.up.railway.app/mcp`.

### 5. Verify

- Build/deploy logs: click the service tile → click the latest deployment → **Deploy Logs**. Wait for `Application startup complete.`
- Healthcheck: `curl https://<your-service>.up.railway.app/healthz` → returns `ok`. Railway uses this path (configured in `railway.json`) to mark deploys healthy.
- Auth check: `curl -X POST https://<your-service>.up.railway.app/mcp` → returns `401` with an `invalid_token` JSON body. That's correct — clients must send `Authorization: Bearer <MCP_BEARER_TOKEN>`.

Push to `main` (or your default branch) auto-redeploys. Configure or change the watched branch under Service → **Settings** → **Source** → trigger branch.

---

## Connecting from Claude

> **Heads up on auth:** the Claude.ai / Claude Desktop **Custom Connectors** UI only supports OAuth — you can't paste a bearer token through it ([source](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)). For a single-user self-hosted server like this one, **Claude Code (CLI)** is the path that works. If you need claude.ai web/desktop access, you'd have to add OAuth to the server (out of scope here).

### Claude Code (CLI)

The simplest path. Set the token in your shell, then add the server:

```bash
export TRANSCRIPT_MCP_TOKEN='<paste your MCP_BEARER_TOKEN>'

claude mcp add --scope user --transport http transcripts \
  https://<your-service>.up.railway.app/mcp \
  --header "Authorization: Bearer ${TRANSCRIPT_MCP_TOKEN}"
```

Flags:
- `--scope user` makes it available across all your projects (alternatives: `--scope project` writes to `.mcp.json` in the repo for sharing; `--scope local` is project-private).
- `--transport http` is the current Streamable HTTP transport.
- Repeat `--header` for additional headers if needed.

You can also edit the config directly. **User scope** lives in `~/.claude.json`:

```json
{
  "mcpServers": {
    "transcripts": {
      "type": "http",
      "url": "https://<your-service>.up.railway.app/mcp",
      "headers": {
        "Authorization": "Bearer ${TRANSCRIPT_MCP_TOKEN}"
      }
    }
  }
}
```

The `${VAR}` syntax reads from the shell environment at startup, so you can safely commit a `.mcp.json` (project scope) without leaking the token, as long as `TRANSCRIPT_MCP_TOKEN` is set in your shell.

**Verify:**

```bash
claude mcp list           # shows registered servers + connection status
claude mcp get transcripts
```

In a Claude Code session, `/mcp` shows the server's status and tool list.

### Test prompt

> "Fetch the transcript of https://www.youtube.com/watch?v=jNQXAC9IVRw and summarize the main points."

Claude Code should call `get_transcript` and ground the summary in the returned markdown. If the call doesn't happen, double-check `claude mcp list` shows `transcripts` connected and that the bearer token matches `MCP_BEARER_TOKEN` on Railway. The same test prompts from the [Try it locally](#try-it-locally) section work against the deployed URL.

---

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `MCP_BEARER_TOKEN` | yes | Server refuses to start without it. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
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
├── Dockerfile               # uv slim base + uvicorn on $PORT
├── railway.json             # Dockerfile builder + /healthz healthcheck
├── .env.example
├── .gitignore
├── README.md
└── src/tldl/
    ├── __init__.py
    ├── config.py            # env-var loader, fail-closed
    ├── markdown.py          # frontmatter + paragraph coalescing
    ├── youtube.py           # video_id parse + proxy-aware transcript fetch + yt-dlp metadata
    ├── resolver.py          # shared YouTube search + rapidfuzz scoring (used by Spotify + Apple)
    ├── spotify.py           # oEmbed → resolver
    ├── apple.py             # iTunes Lookup → resolver
    └── server.py            # FastMCP app, get_transcript tool, /healthz route
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
