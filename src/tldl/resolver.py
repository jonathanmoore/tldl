"""
Shared logic for resolving an external podcast platform's episode metadata
(title + show name) to a matching YouTube upload. Used by spotify.py and
apple.py — both can only fall back to YouTube because their own platforms
do not expose transcript APIs.
"""

import logging
from typing import Any

from rapidfuzz import fuzz
from yt_dlp import YoutubeDL

from .youtube import fetch_youtube_metadata

log = logging.getLogger(__name__)

CONFIDENT_THRESHOLD = 0.75
WARN_THRESHOLD = 0.55


class ResolutionError(Exception):
    """Raised when a non-YouTube URL cannot be confidently resolved to a YouTube video."""


def _search_youtube(query: str) -> dict[str, Any] | None:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
    entries = info.get("entries") or []
    return entries[0] if entries else None


def _score(
    title: str, show: str | None, yt_title: str, yt_channel: str
) -> float:
    title_score = fuzz.token_set_ratio(title, yt_title) / 100.0
    if show:
        channel_score = fuzz.token_set_ratio(show, yt_channel) / 100.0
        return 0.7 * title_score + 0.3 * channel_score
    return title_score * 0.85


def find_youtube_match(
    episode_title: str, show_name: str | None
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Search YouTube for `episode_title` (and `show_name` if available) and
    return (video_id, yt_metadata, match_info). Raises ResolutionError when
    no match exists or confidence is below WARN_THRESHOLD.
    """
    if not episode_title:
        raise ResolutionError("Cannot search YouTube without an episode title.")

    if show_name:
        query = f"{episode_title} {show_name} podcast"
    else:
        query = f"{episode_title} podcast"

    result = _search_youtube(query)
    if not result:
        raise ResolutionError(
            "No matching YouTube video found. The episode may not be cross-posted to YouTube."
        )

    yt_title = result.get("title") or ""
    yt_channel = result.get("channel") or result.get("uploader") or ""
    confidence = _score(episode_title, show_name, yt_title, yt_channel)
    if not show_name:
        confidence = min(confidence, 0.6)

    if confidence < WARN_THRESHOLD:
        raise ResolutionError(
            f"Could not find this episode on YouTube. It may not be cross-posted. "
            f"(best guess: '{yt_title}' on '{yt_channel}', confidence {confidence:.2f})"
        )

    video_id = result.get("id")
    if not video_id:
        raise ResolutionError("YouTube search returned no video id.")

    metadata = fetch_youtube_metadata(video_id)
    match_info = {
        "confidence": confidence,
        "title": episode_title,
        "show": show_name,
        "yt_title": yt_title,
        "yt_channel": yt_channel,
    }
    return video_id, metadata, match_info
