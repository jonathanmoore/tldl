import logging
import re

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .apple import (
    fetch_apple_episode_info,
    list_apple_episodes,
    resolve_apple_to_youtube,
)
from .config import settings
from .markdown import render_episode_info, render_episode_list, render_markdown
from .resolver import ResolutionError
from .spotify import fetch_spotify_episode_info, resolve_spotify_to_youtube
from .youtube import (
    extract_youtube_video_id,
    fetch_youtube_metadata,
    fetch_youtube_transcript,
    list_youtube_videos,
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


_YOUTUBE_LISTABLE_RE = re.compile(
    r"youtube\.com/(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+|playlist\?)"
)


def _is_youtube_video_url(url: str) -> bool:
    return extract_youtube_video_id(url) is not None


def _is_apple_episode_url(url: str) -> bool:
    return bool(re.search(r"[?&]i=\d+", url))


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


@mcp.tool
def get_episode_info(url: str) -> str:
    """
    Fetch metadata for an episode without pulling the transcript. Useful when
    you want to confirm "is this the right episode?" without paying the tokens
    for a full transcript, or when you just want to reference an episode.

    Returns markdown with YAML frontmatter (title, show/channel, duration,
    release date, etc.) and a brief description body when one is available.

    - YouTube: full metadata via yt-dlp (title, channel, duration, upload
      date, description).
    - Apple Podcasts: full metadata via the iTunes Lookup API (title, show,
      duration, release date, description, audio_url).
    - Spotify: limited metadata via oEmbed (title, show only — Spotify does
      not expose duration or release date publicly).

    Args:
        url: A YouTube video URL, Spotify episode URL, or Apple Podcasts
             episode URL (must include ?i= for Apple).
    """
    log.info("get_episode_info url=%s", url)
    kind = _detect(url)
    try:
        if kind == "youtube":
            video_id = extract_youtube_video_id(url)
            if not video_id:
                raise ToolError(
                    f"That YouTube URL looks like a channel/playlist, not a video. "
                    f"Use list_recent_episodes for channels: {url}"
                )
            info = fetch_youtube_metadata(video_id)
            info["source_url"] = info.get("webpage_url") or url
            return render_episode_info(info, source="youtube")

        if kind == "spotify":
            info = fetch_spotify_episode_info(url)
            return render_episode_info(info, source="spotify")

        if kind == "apple":
            if not _is_apple_episode_url(url):
                raise ToolError(
                    "That Apple Podcasts URL is for a show, not an episode. "
                    "Use list_recent_episodes to see recent episodes."
                )
            info = fetch_apple_episode_info(url)
            return render_episode_info(info, source="apple")

        raise ToolError(
            f"Unsupported URL (need a YouTube, Spotify, or Apple Podcasts episode URL): {url}"
        )

    except ToolError:
        raise
    except ResolutionError as e:
        raise ToolError(str(e)) from e
    except Exception as e:
        log.exception("get_episode_info failed for %s", url)
        raise ToolError(_friendly_error(e)) from e


@mcp.tool
def list_recent_episodes(url: str, limit: int = 10) -> str:
    """
    List recent episodes/videos from a podcast show or YouTube channel URL.

    - Apple Podcasts show URL (`podcasts.apple.com/.../id<show>`): up to 200
      most recent episodes via iTunes Lookup. If you pass an Apple episode
      URL, the `?i=` is ignored and the show's episodes are listed.
    - YouTube channel URL (`youtube.com/@name`, `/channel/...`, `/c/...`,
      `/user/...`) or playlist URL (`youtube.com/playlist?list=...`): recent
      videos via yt-dlp.
    - Spotify show URLs are not supported (no public episodes API).

    Args:
        url: An Apple Podcasts show URL, a YouTube channel/playlist URL,
             (or an Apple episode URL — the show portion is used).
        limit: Number of episodes to return. Capped at 50.
    """
    log.info("list_recent_episodes url=%s limit=%s", url, limit)
    limit = max(1, min(int(limit), 50))
    if "open.spotify.com" in url.lower():
        raise ToolError(
            "Spotify show listings are not supported (Spotify has no public "
            "episodes API). Try the same show on Apple Podcasts or YouTube."
        )
    kind = _detect(url)
    try:
        if kind == "apple":
            payload = list_apple_episodes(url, limit=limit)
            return render_episode_list(payload, source="apple")

        if kind == "youtube":
            if _is_youtube_video_url(url) and not _YOUTUBE_LISTABLE_RE.search(url):
                raise ToolError(
                    "That looks like a single video URL. Pass a channel URL "
                    "(e.g. https://www.youtube.com/@channelname) or a playlist URL."
                )
            payload = list_youtube_videos(url, limit=limit)
            return render_episode_list(payload, source="youtube")

        raise ToolError(
            f"Unsupported URL (need an Apple Podcasts show URL or a YouTube "
            f"channel/playlist URL): {url}"
        )

    except ToolError:
        raise
    except ResolutionError as e:
        raise ToolError(str(e)) from e
    except Exception as e:
        log.exception("list_recent_episodes failed for %s", url)
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
