import logging
import re
from typing import Any

import httpx

from .resolver import ResolutionError, find_youtube_match

log = logging.getLogger(__name__)

OEMBED_URL = "https://open.spotify.com/oembed"
_SHOW_RE = re.compile(r" by ([^\"<]+)")


def _oembed(spotify_url: str) -> dict[str, Any]:
    try:
        r = httpx.get(
            OEMBED_URL,
            params={"url": spotify_url},
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        raise ResolutionError(f"Failed to reach Spotify oEmbed: {e}") from e
    if r.status_code == 404:
        raise ResolutionError("Spotify episode not found or private.")
    r.raise_for_status()
    data = r.json()
    title = (data.get("title") or "").strip()
    if not title:
        raise ResolutionError("Spotify oEmbed returned no episode title.")
    show: str | None = None
    html = data.get("html") or ""
    m = _SHOW_RE.search(html)
    if m:
        show = m.group(1).strip()
    else:
        log.warning("Could not parse show name from Spotify oEmbed html for %s", spotify_url)
    return {"title": title, "show": show}


def resolve_spotify_to_youtube(
    spotify_url: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Returns (video_id, yt_metadata, match_info).
    Raises ResolutionError when no acceptable YouTube match is found.
    """
    info = _oembed(spotify_url)
    return find_youtube_match(info["title"], info["show"])


def fetch_spotify_episode_info(spotify_url: str) -> dict[str, Any]:
    """
    Returns the normalized info we can extract from Spotify's oEmbed endpoint.
    Spotify exposes much less than YouTube/Apple — title and show name are all
    we get reliably without authenticated API access.
    """
    info = _oembed(spotify_url)
    return {
        "title": info["title"],
        "show": info["show"],
        "source_url": spotify_url,
    }
