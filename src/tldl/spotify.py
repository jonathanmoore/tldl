import logging
import re
from typing import Any

import httpx
from rapidfuzz import fuzz
from yt_dlp import YoutubeDL

from .youtube import fetch_youtube_metadata

log = logging.getLogger(__name__)

OEMBED_URL = "https://open.spotify.com/oembed"
_SHOW_RE = re.compile(r" by ([^\"<]+)")

CONFIDENT_THRESHOLD = 0.75
WARN_THRESHOLD = 0.55


class SpotifyResolutionError(Exception):
    pass


def _oembed(spotify_url: str) -> dict[str, Any]:
    try:
        r = httpx.get(
            OEMBED_URL,
            params={"url": spotify_url},
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        raise SpotifyResolutionError(f"Failed to reach Spotify oEmbed: {e}") from e
    if r.status_code == 404:
        raise SpotifyResolutionError("Spotify episode not found or private.")
    r.raise_for_status()
    data = r.json()
    title = (data.get("title") or "").strip()
    if not title:
        raise SpotifyResolutionError("Spotify oEmbed returned no episode title.")
    show = None
    html = data.get("html") or ""
    m = _SHOW_RE.search(html)
    if m:
        show = m.group(1).strip()
    else:
        log.warning("Could not parse show name from Spotify oEmbed html for %s", spotify_url)
    return {"title": title, "show": show}


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
    spotify_title: str, spotify_show: str | None, yt_title: str, yt_channel: str
) -> float:
    title_score = fuzz.token_set_ratio(spotify_title, yt_title) / 100.0
    if spotify_show:
        channel_score = fuzz.token_set_ratio(spotify_show, yt_channel) / 100.0
        return 0.7 * title_score + 0.3 * channel_score
    return title_score * 0.85


def resolve_spotify_to_youtube(
    spotify_url: str, *, language: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Returns (video_id, metadata, match_info).
    Raises SpotifyResolutionError when no acceptable YouTube match is found.
    """
    info = _oembed(spotify_url)
    sp_title = info["title"]
    sp_show = info["show"]

    if sp_show:
        query = f"{sp_title} {sp_show} podcast"
    else:
        query = f"{sp_title} podcast"

    result = _search_youtube(query)
    if not result:
        raise SpotifyResolutionError(
            "No matching YouTube video found. Likely a Spotify exclusive."
        )

    yt_title = result.get("title") or ""
    yt_channel = result.get("channel") or result.get("uploader") or ""
    confidence = _score(sp_title, sp_show, yt_title, yt_channel)
    if not sp_show:
        confidence = min(confidence, 0.6)

    if confidence < WARN_THRESHOLD:
        raise SpotifyResolutionError(
            f"Could not find this Spotify episode on YouTube. It may be a Spotify exclusive. "
            f"(best guess: '{yt_title}' on '{yt_channel}', confidence {confidence:.2f})"
        )

    video_id = result.get("id")
    if not video_id:
        raise SpotifyResolutionError("YouTube search returned no video id.")

    metadata = fetch_youtube_metadata(video_id)
    match_info = {
        "confidence": confidence,
        "spotify_title": sp_title,
        "spotify_show": sp_show,
        "yt_title": yt_title,
        "yt_channel": yt_channel,
    }
    return video_id, metadata, match_info
