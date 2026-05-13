"""
Tool 3: fetch_channel_stats.py
Fetches stats for all unique channels found in video_details.json.
Output: .tmp/channel_stats.json
Quota cost: ~1 unit
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

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


def chunk_list(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_channel_batch(youtube, channel_ids: list[str]) -> list[dict]:
    try:
        response = youtube.channels().list(
            part="snippet,statistics",
            id=",".join(channel_ids),
        ).execute()
    except HttpError as e:
        log.warning(f"channels.list batch failed: {e}")
        return []
    return response.get("items", [])


def parse_channel_item(item: dict, video_counts: dict) -> dict:
    cid = item["id"]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})

    subscriber_hidden = stats.get("hiddenSubscriberCount", False)
    subscriber_count = None if subscriber_hidden else int(stats.get("subscriberCount", 0))

    total_views = int(stats.get("viewCount", 0))
    video_count = int(stats.get("videoCount", 0))

    published_at = snippet.get("publishedAt", "")
    try:
        created = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        weeks_alive = max((datetime.now(timezone.utc) - created).days / 7, 1)
        uploads_per_week = round(video_count / weeks_alive, 2)
    except (ValueError, AttributeError):
        uploads_per_week = None

    return {
        "channel_id": cid,
        "channel_name": snippet.get("title", ""),
        "subscriber_count": subscriber_count,
        "subscriber_hidden": subscriber_hidden,
        "total_views": total_views,
        "video_count": video_count,
        "created_at": published_at,
        "uploads_per_week_estimate": uploads_per_week,
        "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
        "videos_this_week": video_counts.get(cid, 0),
    }


def main(work_dir=None):
    _work_dir = work_dir or config.TMP_DIR
    _input_path = os.path.join(_work_dir, "video_details.json")
    _output_path = os.path.join(_work_dir, "channel_stats.json")

    if not os.path.exists(_input_path):
        raise FileNotFoundError(
            f"Missing {_input_path} — run fetch_video_details.py first"
        )

    with open(_input_path) as f:
        data = json.load(f)

    videos = data["videos"]

    # Count how many videos this week per channel (for ranking)
    video_counts: dict[str, int] = {}
    seen_channels: dict[str, str] = {}  # channel_id -> channel_name
    for v in videos:
        cid = v["channel_id"]
        video_counts[cid] = video_counts.get(cid, 0) + 1
        seen_channels[cid] = v.get("channel_title", "")

    channel_ids = list(seen_channels.keys())
    log.info(f"Fetching stats for {len(channel_ids)} unique channels...")

    youtube = build_youtube_client()
    channel_stats = []

    for batch in chunk_list(channel_ids, 50):
        items = fetch_channel_batch(youtube, batch)
        for item in items:
            parsed = parse_channel_item(item, video_counts)
            channel_stats.append(parsed)

    log.info(f"Fetched stats for {len(channel_stats)} channels")

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_channels": len(channel_stats),
        "channels": channel_stats,
    }

    with open(_output_path, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Saved to {_output_path}")
    return output


if __name__ == "__main__":
    main()
