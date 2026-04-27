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


def _parse_show_id(url: str) -> str:
    m = _SHOW_ID_RE.search(url)
    if not m:
        raise ResolutionError(
            "Apple Podcasts URL is missing the show id (expected '/id<digits>')."
        )
    return m.group(1)


def _parse_apple_url(url: str) -> tuple[str, str]:
    """Returns (show_id, episode_track_id). Raises ResolutionError on a malformed URL."""
    show_id = _parse_show_id(url)
    qs = parse_qs(urlparse(url).query)
    i_vals = qs.get("i", [])
    if not i_vals or not i_vals[0].isdigit():
        raise ResolutionError(
            "Apple Podcasts URL is missing the episode id ('?i=<digits>'). "
            "Pass an episode URL, not a show URL."
        )
    return show_id, i_vals[0]


def _itunes_fetch(show_id: str, limit: int) -> tuple[list[dict[str, Any]], int]:
    """Hit iTunes Lookup. Returns (results, requested_limit) so callers can detect cap-hit."""
    try:
        r = httpx.get(
            ITUNES_LOOKUP_URL,
            params={"id": show_id, "entity": "podcastEpisode", "limit": limit},
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as e:
        raise ResolutionError(f"Failed to reach iTunes Lookup: {e}") from e
    r.raise_for_status()
    return r.json().get("results") or [], limit


def _show_name_from_results(
    results: list[dict[str, Any]], show_id: str
) -> str | None:
    show_id_int = int(show_id)
    for item in results:
        if item.get("wrapperType") == "track" and item.get("trackId") == show_id_int:
            return item.get("collectionName") or item.get("trackName")
    return None


def _episode_to_info(item: dict[str, Any], show_name: str | None) -> dict[str, Any]:
    """Normalize an iTunes podcastEpisode dict into our shape."""
    release = (item.get("releaseDate") or "").split("T")[0] or None
    duration_ms = item.get("trackTimeMillis")
    duration_s = int(duration_ms / 1000) if duration_ms else None
    show_id = item.get("collectionId")
    track_id = item.get("trackId")
    episode_url = (
        f"https://podcasts.apple.com/us/podcast/id{show_id}?i={track_id}"
        if show_id and track_id
        else None
    )
    return {
        "title": (item.get("trackName") or "").strip(),
        "show": (item.get("collectionName") or show_name or "").strip() or None,
        "release_date": release,
        "duration": duration_s,
        "description": (item.get("description") or "").strip() or None,
        "audio_url": item.get("episodeUrl"),
        "episode_url": episode_url,
        "track_id": track_id,
        "show_id": show_id,
    }


def _itunes_lookup(show_id: str, episode_track_id: str) -> dict[str, Any]:
    """Find a single episode by trackId. Returns {"title", "show"}."""
    results, _ = _itunes_fetch(show_id, LOOKUP_LIMIT)
    target_id = int(episode_track_id)
    show_name = _show_name_from_results(results, show_id)

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

    if len(results) >= LOOKUP_LIMIT:
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


def fetch_apple_episode_info(apple_url: str) -> dict[str, Any]:
    """
    Resolve an Apple Podcasts episode URL to a normalized info dict (no YouTube fetch).
    """
    show_id, episode_track_id = _parse_apple_url(apple_url)
    target_id = int(episode_track_id)
    results, _ = _itunes_fetch(show_id, LOOKUP_LIMIT)
    show_name = _show_name_from_results(results, show_id)

    for item in results:
        if item.get("wrapperType") != "podcastEpisode":
            continue
        if item.get("trackId") == target_id:
            info = _episode_to_info(item, show_name)
            info["source_url"] = apple_url
            return info

    if len(results) >= LOOKUP_LIMIT:
        raise ResolutionError(
            f"Episode not found in the most recent {LOOKUP_LIMIT} episodes for this show."
        )
    raise ResolutionError("Episode not found in iTunes Lookup results.")


def list_apple_episodes(show_url: str, limit: int) -> dict[str, Any]:
    """
    List recent episodes for an Apple Podcasts show URL.
    Returns {"show", "show_id", "source_url", "episodes": [info_dict, ...]}.
    """
    show_id = _parse_show_id(show_url)
    fetch_count = min(max(limit + 1, 1), LOOKUP_LIMIT)
    results, _ = _itunes_fetch(show_id, fetch_count)
    show_name = _show_name_from_results(results, show_id)

    episodes = [
        _episode_to_info(item, show_name)
        for item in results
        if item.get("wrapperType") == "podcastEpisode"
    ]
    if not episodes:
        raise ResolutionError("No episodes found for this show.")

    return {
        "show": show_name,
        "show_id": int(show_id),
        "source_url": show_url,
        "episodes": episodes[:limit],
    }
