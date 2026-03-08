"""
Tool 1: search_youtube.py
Searches YouTube by keyword and fetches trending videos.
Output: .tmp/videos_raw.json
Quota cost: ~1,001 units (10 keywords × 100 + 1 trending)
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


def fetch_trending_videos(youtube) -> list[dict]:
    """Fetch most popular videos in Science & Technology (US)."""
    try:
        response = youtube.videos().list(
            part="snippet",
            chart="mostPopular",
            regionCode=config.TRENDING_REGION_CODE,
            videoCategoryId=config.TRENDING_CATEGORY_ID,
            maxResults=config.TRENDING_MAX_RESULTS,
        ).execute()
    except HttpError as e:
        log.warning(f"Trending fetch failed: {e}")
        return []

    results = []
    for item in response.get("items", []):
        snippet = item["snippet"]
        results.append({
            "video_id": item["id"],
            "title": snippet["title"],
            "channel_id": snippet["channelId"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "source_keyword": "_trending",
            "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
        })

    log.info(f"  Trending → {len(results)} videos")
    return results


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
    for keyword in config.KEYWORDS:
        results = search_by_keyword(youtube, keyword, published_after)
        all_videos.extend(results)

    trending = fetch_trending_videos(youtube)
    all_videos.extend(trending)

    unique_videos = deduplicate(all_videos)
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
