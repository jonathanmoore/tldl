import logging

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .apple import resolve_apple_to_youtube
from .config import settings
from .markdown import render_markdown
from .resolver import ResolutionError
from .spotify import resolve_spotify_to_youtube
from .youtube import (
    extract_youtube_video_id,
    fetch_youtube_metadata,
    fetch_youtube_transcript,
)

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("tldl")

auth = StaticTokenVerifier(
    tokens={
        settings.bearer_token: {
            "client_id": "owner",
            "scopes": ["transcripts:read"],
        }
    },
    required_scopes=["transcripts:read"],
)

mcp = FastMCP(name="TLDL", auth=auth)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _detect(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "open.spotify.com" in u and "/episode/" in u:
        return "spotify"
    if "podcasts.apple.com" in u:
        return "apple"
    return "unknown"


def _friendly_error(e: Exception) -> str:
    from youtube_transcript_api import (
        IpBlocked,
        NoTranscriptFound,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
    )

    if isinstance(e, TranscriptsDisabled):
        return "This video has captions disabled."
    if isinstance(e, NoTranscriptFound):
        return "No transcript available in the requested language."
    if isinstance(e, VideoUnavailable):
        return "Video is unavailable (private, deleted, or region-locked)."
    if isinstance(e, (IpBlocked, RequestBlocked)):
        return (
            "YouTube blocked the request. The server's outbound IP is rate-limited; "
            "configure WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD."
        )
    return f"{type(e).__name__}: {e}"


@mcp.tool
def get_transcript(
    url: str,
    language: str = "en",
    include_timestamps: bool = False,
) -> str:
    """
    Fetch the auto-caption transcript for a podcast URL and return it as
    Markdown with YAML frontmatter.

    - YouTube: uses the video's manual or auto-generated captions.
    - Spotify: resolves the episode to the same upload on YouTube via oEmbed
      + YouTube search. Spotify-exclusive episodes are not supported.
    - Apple Podcasts: resolves the episode via the iTunes Lookup API and
      then matches it on YouTube. Apple-exclusive episodes are not supported.

    Args:
        url: YouTube, Spotify episode, or Apple Podcasts episode URL.
        language: ISO language code for captions (default "en").
        include_timestamps: If true, insert section markers every 5 minutes.
    """
    log.info("get_transcript url=%s language=%s ts=%s", url, language, include_timestamps)
    kind = _detect(url)
    try:
        if kind == "youtube":
            video_id = extract_youtube_video_id(url)
            if not video_id:
                raise ToolError(f"Could not parse a YouTube video id from: {url}")
            transcript = fetch_youtube_transcript(video_id, language)
            metadata = fetch_youtube_metadata(video_id)
            return render_markdown(
                transcript,
                metadata,
                source={"kind": "youtube", "original_url": url},
                include_timestamps=include_timestamps,
            )

        if kind == "spotify":
            video_id, metadata, match = resolve_spotify_to_youtube(url)
            transcript = fetch_youtube_transcript(video_id, language)
            return render_markdown(
                transcript,
                metadata,
                source={
                    "kind": "spotify-via-youtube",
                    "original_url": url,
                    "match": match,
                },
                include_timestamps=include_timestamps,
            )

        if kind == "apple":
            video_id, metadata, match = resolve_apple_to_youtube(url)
            transcript = fetch_youtube_transcript(video_id, language)
            return render_markdown(
                transcript,
                metadata,
                source={
                    "kind": "apple-via-youtube",
                    "original_url": url,
                    "match": match,
                },
                include_timestamps=include_timestamps,
            )

        raise ToolError(
            f"Unsupported URL (need a YouTube, Spotify, or Apple Podcasts URL): {url}"
        )

    except ToolError:
        raise
    except ResolutionError as e:
        raise ToolError(str(e)) from e
    except Exception as e:
        log.exception("get_transcript failed for %s", url)
        raise ToolError(_friendly_error(e)) from e


app = mcp.http_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "tldl.server:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
