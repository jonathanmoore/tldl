import re
from functools import cache
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from yt_dlp import YoutubeDL

from .config import settings

_VIDEO_ID_RE = re.compile(
    r"(?:v=|/shorts/|/embed/|/live/|youtu\.be/)([0-9A-Za-z_-]{11})"
)


def extract_youtube_video_id(url: str) -> str | None:
    m = _VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


@cache
def _ytt() -> YouTubeTranscriptApi:
    if settings.webshare_username and settings.webshare_password:
        kwargs: dict[str, Any] = dict(
            proxy_username=settings.webshare_username,
            proxy_password=settings.webshare_password,
            retries_when_blocked=10,
        )
        if settings.webshare_locations:
            kwargs["filter_ip_locations"] = list(settings.webshare_locations)
        return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(**kwargs))
    return YouTubeTranscriptApi()


def fetch_youtube_transcript(video_id: str, language: str) -> Any:
    # api.fetch() prefers manually-created transcripts over auto-generated and
    # raises NoTranscriptFound if neither exists in the requested language.
    return _ytt().fetch(video_id, languages=[language])


def fetch_youtube_metadata(video_id: str) -> dict[str, Any]:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )
    return {
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "description": (info.get("description") or "").strip() or None,
        "webpage_url": info.get("webpage_url")
        or f"https://www.youtube.com/watch?v={video_id}",
        "video_id": video_id,
    }


_BARE_CHANNEL_RE = re.compile(
    r"^(https?://(?:www\.)?youtube\.com/(?:@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+))/?$"
)


def list_youtube_videos(channel_url: str, limit: int) -> dict[str, Any]:
    """
    List recent videos from a YouTube channel or playlist URL.
    Returns {"channel", "source_url", "videos": [{...}, ...]}.

    Uses extract_flat so we don't pay per-video metadata cost.
    """
    # Bare channel URLs (no /videos, /streams, /shorts) yield sub-tabs as
    # results instead of videos. Append /videos for the conventional case.
    bare = _BARE_CHANNEL_RE.match(channel_url)
    fetch_url = f"{bare.group(1)}/videos" if bare else channel_url

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": limit,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(fetch_url, download=False)

    entries = info.get("entries") or []
    videos: list[dict[str, Any]] = []
    for e in entries[:limit]:
        vid = e.get("id")
        videos.append(
            {
                "title": e.get("title"),
                "video_id": vid,
                "url": e.get("webpage_url")
                or e.get("url")
                or (f"https://www.youtube.com/watch?v={vid}" if vid else None),
                "duration": e.get("duration"),
                "upload_date": e.get("upload_date"),
                "channel": e.get("channel") or e.get("uploader"),
            }
        )

    return {
        "channel": info.get("channel") or info.get("uploader") or info.get("title"),
        "source_url": info.get("webpage_url") or channel_url,
        "videos": videos,
    }
