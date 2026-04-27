import re
from functools import cache
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

_VIDEO_ID_RE = re.compile(
    r"(?:v=|/shorts/|/embed/|/live/|youtu\.be/)([0-9A-Za-z_-]{11})"
)


def extract_youtube_video_id(url: str) -> str | None:
    m = _VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


@cache
def _ytt() -> YouTubeTranscriptApi:
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
        "webpage_url": info.get("webpage_url")
        or f"https://www.youtube.com/watch?v={video_id}",
        "video_id": video_id,
    }
