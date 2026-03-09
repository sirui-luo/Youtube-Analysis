"""
Tool 1: search_youtube.py
Searches YouTube by keyword and fetches videos from seed channels.
Output: .tmp/videos_raw.json
Quota cost: ~1,500 units (15 keywords × 100 + seed channel lookups)
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def build_youtube_client():
    if not config.YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY is not set in .env")
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def search_by_keyword(youtube, keyword: str, published_after: str) -> list[dict]:
    """Search videos by keyword published after a given ISO timestamp."""
    try:
        response = youtube.search().list(
            q=keyword,
            part="snippet",
            type="video",
            order="viewCount",
            publishedAfter=published_after,
            maxResults=config.MAX_RESULTS_PER_KEYWORD,
            relevanceLanguage="en",
        ).execute()
    except HttpError as e:
        log.warning(f"search.list failed for keyword '{keyword}': {e}")
        return []

    results = []
    for item in response.get("items", []):
        snippet = item["snippet"]
        results.append({
            "video_id": item["id"]["videoId"],
            "title": snippet["title"],
            "channel_id": snippet["channelId"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "source_keyword": keyword,
            "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
        })

    log.info(f"  '{keyword}' → {len(results)} videos")
    return results


def resolve_channel_id(youtube, handle: str) -> str | None:
    """Search for a channel by name/handle and return its channel ID."""
    try:
        response = youtube.search().list(
            q=handle,
            part="snippet",
            type="channel",
            maxResults=1,
        ).execute()
        items = response.get("items", [])
        if items:
            channel_id = items[0]["snippet"]["channelId"]
            channel_title = items[0]["snippet"]["title"]
            log.info(f"  Resolved '{handle}' → {channel_title} ({channel_id})")
            return channel_id
        log.warning(f"  Could not resolve channel handle: '{handle}'")
        return None
    except HttpError as e:
        log.warning(f"  Channel search failed for '{handle}': {e}")
        return None


def fetch_seed_channel_videos(youtube, channel_id: str, published_after: str) -> list[dict]:
    """Fetch recent videos from a specific channel."""
    try:
        response = youtube.search().list(
            channelId=channel_id,
            part="snippet",
            type="video",
            order="date",
            publishedAfter=published_after,
            maxResults=config.MAX_RESULTS_PER_SEED_CHANNEL,
        ).execute()
    except HttpError as e:
        log.warning(f"  Seed channel fetch failed for {channel_id}: {e}")
        return []

    results = []
    for item in response.get("items", []):
        snippet = item["snippet"]
        results.append({
            "video_id": item["id"]["videoId"],
            "title": snippet["title"],
            "channel_id": snippet["channelId"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "source_keyword": "_seed_channel",
            "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
        })

    log.info(f"  Seed channel {channel_id} → {len(results)} videos")
    return results


def is_relevant(title: str) -> bool:
    """Return False if the title contains any blocklisted term."""
    title_lower = title.lower()
    for term in config.TITLE_BLOCKLIST:
        if term.lower() in title_lower:
            return False
    return True


def deduplicate(videos: list[dict]) -> list[dict]:
    seen = {}
    for v in videos:
        vid = v["video_id"]
        if vid not in seen:
            seen[vid] = v
    return list(seen.values())


def main():
    os.makedirs(config.TMP_DIR, exist_ok=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=config.LOOKBACK_DAYS)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    log.info(f"Searching YouTube (last {config.LOOKBACK_DAYS} days, after {published_after})")

    youtube = build_youtube_client()

    all_videos = []

    # Keyword search
    for keyword in config.KEYWORDS:
        results = search_by_keyword(youtube, keyword, published_after)
        all_videos.extend(results)

    # Seed channel fetch
    if config.SEED_CHANNEL_HANDLES:
        log.info("Fetching seed channel videos...")
        for handle in config.SEED_CHANNEL_HANDLES:
            channel_id = resolve_channel_id(youtube, handle)
            if channel_id:
                results = fetch_seed_channel_videos(youtube, channel_id, published_after)
                all_videos.extend(results)

    # Deduplicate then apply title blocklist
    unique_videos = deduplicate(all_videos)
    before = len(unique_videos)
    unique_videos = [v for v in unique_videos if is_relevant(v["title"])]
    filtered = before - len(unique_videos)
    if filtered:
        log.info(f"  Filtered out {filtered} irrelevant videos via blocklist")

    log.info(f"Total unique videos collected: {len(unique_videos)}")

    if len(unique_videos) < 10:
        log.warning(f"Only {len(unique_videos)} videos found — check keywords or API key")

    output = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": config.LOOKBACK_DAYS,
        "published_after": published_after,
        "total_videos": len(unique_videos),
        "videos": unique_videos,
    }

    with open(config.VIDEOS_RAW_PATH, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Saved to {config.VIDEOS_RAW_PATH}")
    return output


if __name__ == "__main__":
    main()
