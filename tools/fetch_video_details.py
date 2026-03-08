"""
Tool 2: fetch_video_details.py
Fetches full stats for each video ID from videos_raw.json.
Output: .tmp/video_details.json
Quota cost: ~2 units per 100 videos
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def build_youtube_client():
    if not config.YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY is not set in .env")
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def chunk_list(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def parse_duration(iso_duration: str):
    """Convert ISO 8601 duration (PT4M33S) to total seconds."""
    if not iso_duration:
        return None
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, iso_duration)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def classify_format(duration_seconds) -> str:
    if duration_seconds is None:
        return "unknown"
    if duration_seconds <= config.SHORT_MAX_DURATION:
        return "short"
    if duration_seconds <= config.MID_MAX_DURATION:
        return "mid"
    return "long"


def fetch_batch(youtube, video_ids: list[str]) -> list[dict]:
    try:
        response = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids),
        ).execute()
    except HttpError as e:
        log.warning(f"videos.list batch failed: {e}")
        return []
    return response.get("items", [])


def parse_video_item(item: dict, source_map: dict, thumbnail_map: dict) -> dict:
    vid_id = item["id"]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    details = item.get("contentDetails", {})

    published_at = snippet.get("publishedAt", "")
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        publish_day = DAY_NAMES[dt.weekday()]
        publish_hour = dt.hour
    except (ValueError, AttributeError):
        publish_day = None
        publish_hour = None

    duration_seconds = parse_duration(details.get("duration", ""))
    view_count = int(stats.get("viewCount", 0))
    like_count = int(stats.get("likeCount", 0))
    comment_count = int(stats.get("commentCount", 0))

    engagement_rate = (
        round((like_count + comment_count) / view_count, 4)
        if view_count > 0 else 0.0
    )

    return {
        "video_id": vid_id,
        "title": snippet.get("title", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at": published_at,
        "publish_day": publish_day,
        "publish_hour": publish_hour,
        "duration_seconds": duration_seconds,
        "format": classify_format(duration_seconds),
        "view_count": view_count,
        "like_count": like_count,
        "comment_count": comment_count,
        "engagement_rate": engagement_rate,
        "thumbnail_url": thumbnail_map.get(vid_id, snippet.get("thumbnails", {}).get("medium", {}).get("url", "")),
        "tags": snippet.get("tags", []),
        "category_id": snippet.get("categoryId", ""),
        "source_keyword": source_map.get(vid_id, ""),
    }


def main():
    if not os.path.exists(config.VIDEOS_RAW_PATH):
        raise FileNotFoundError(
            f"Missing {config.VIDEOS_RAW_PATH} — run search_youtube.py first"
        )

    with open(config.VIDEOS_RAW_PATH) as f:
        raw = json.load(f)

    videos_raw = raw["videos"]
    video_ids = [v["video_id"] for v in videos_raw]
    source_map = {v["video_id"]: v.get("source_keyword", "") for v in videos_raw}
    thumbnail_map = {v["video_id"]: v.get("thumbnail_url", "") for v in videos_raw}

    log.info(f"Fetching details for {len(video_ids)} videos...")

    youtube = build_youtube_client()
    video_details = []

    for batch in chunk_list(video_ids, 50):
        items = fetch_batch(youtube, batch)
        for item in items:
            parsed = parse_video_item(item, source_map, thumbnail_map)
            video_details.append(parsed)

    log.info(f"Fetched details for {len(video_details)} videos")

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_videos": len(video_details),
        "videos": video_details,
    }

    with open(config.VIDEO_DETAILS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Saved to {config.VIDEO_DETAILS_PATH}")
    return output


if __name__ == "__main__":
    main()
