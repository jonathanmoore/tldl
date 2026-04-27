import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from .resolver import ResolutionError, find_youtube_match

log = logging.getLogger(__name__)

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
LOOKUP_LIMIT = 200

_SHOW_ID_RE = re.compile(r"/id(\d+)")


def _parse_apple_url(url: str) -> tuple[str, str]:
    """Returns (show_id, episode_track_id). Raises ResolutionError on a malformed URL."""
    m = _SHOW_ID_RE.search(url)
    if not m:
        raise ResolutionError(
            "Apple Podcasts URL is missing the show id (expected '/id<digits>')."
        )
    show_id = m.group(1)
    qs = parse_qs(urlparse(url).query)
    i_vals = qs.get("i", [])
    if not i_vals or not i_vals[0].isdigit():
        raise ResolutionError(
            "Apple Podcasts URL is missing the episode id ('?i=<digits>'). "
            "Pass an episode URL, not a show URL."
        )
    return show_id, i_vals[0]


def _itunes_lookup(show_id: str, episode_track_id: str) -> dict[str, Any]:
    """
    Hit the iTunes Lookup API for the show and find the target episode by trackId.
    Returns {"title": str, "show": str|None}.
    """
    try:
        r = httpx.get(
            ITUNES_LOOKUP_URL,
            params={"id": show_id, "entity": "podcastEpisode", "limit": LOOKUP_LIMIT},
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        raise ResolutionError(f"Failed to reach iTunes Lookup: {e}") from e
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    target_id = int(episode_track_id)

    show_name: str | None = None
    for item in results:
        if item.get("wrapperType") == "track" and item.get("trackId") == int(show_id):
            show_name = item.get("collectionName") or item.get("trackName")
            break

    for item in results:
        if item.get("wrapperType") != "podcastEpisode":
            continue
        if item.get("trackId") == target_id:
            return {
                "title": (item.get("trackName") or "").strip(),
                "show": (
                    item.get("collectionName") or show_name or ""
                ).strip() or None,
            }

    if data.get("resultCount", 0) >= LOOKUP_LIMIT:
        raise ResolutionError(
            f"Episode not found in the most recent {LOOKUP_LIMIT} episodes for this show. "
            "It may be too old to look up via the iTunes API."
        )
    raise ResolutionError(
        "Episode not found in iTunes Lookup results. The URL may be malformed "
        "or the episode may have been removed."
    )


def resolve_apple_to_youtube(
    apple_url: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Resolve an Apple Podcasts episode URL to a YouTube upload.
    Returns (video_id, yt_metadata, match_info).
    """
    show_id, episode_track_id = _parse_apple_url(apple_url)
    info = _itunes_lookup(show_id, episode_track_id)
    if not info["title"]:
        raise ResolutionError("iTunes Lookup returned no episode title.")
    return find_youtube_match(info["title"], info["show"])
