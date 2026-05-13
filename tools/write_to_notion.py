"""
Tool 8: write_to_notion.py
Writes top video research data to a Notion database.
One row per top video with title, channel, views, engagement, description, top comments, tags.
Adds a "Week" date field so records from different report runs are distinguishable.

Requirements:
  - NOTION_API_KEY in .env (Notion integration token)
  - NOTION_DATABASE_ID in .env (target database ID from the Notion page URL)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from notion_client import Client
from notion_client.errors import APIResponseError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MAX_RICH_TEXT = 2000  # Notion rich_text property character limit


def get_notion_client() -> Client:
    if not config.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is not set in .env")
    return Client(auth=config.NOTION_API_KEY)


def truncate(text: str, limit: int = MAX_RICH_TEXT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def ensure_database_schema(notion: Client, database_id: str):
    """
    Ensure the database has all required properties.
    Adds any missing ones via a PATCH to the database.

    Note: Notion's newer 'data_sources' database format does not expose
    'properties' in the retrieve response. In that case we still attempt
    the update — if the database is classic-style it will work; if not,
    a clear ValueError is raised so the user knows to recreate the database.
    """
    db = notion.databases.retrieve(database_id=database_id)

    if "properties" not in db:
        # New-style Notion database (data_sources format) — not supported by
        # the properties API. Instruct user to use a classic Table database.
        raise ValueError(
            "Your Notion database uses Notion's newer 'data_sources' format, "
            "which does not expose schema via the API.\n"
            "Fix: Delete the current database, open a Notion page, type /table, "
            "select 'Table - Full page', share it with your integration, "
            "and update NOTION_DATABASE_ID in .env with the new database ID."
        )

    existing = set(db["properties"].keys())

    needed = {
        "YouTube URL": {"url": {}},
        "Channel": {"rich_text": {}},
        "Channel URL": {"url": {}},
        "Views": {"number": {"format": "number_with_commas"}},
        "Engagement Rate": {"number": {"format": "percent"}},
        "Format": {"select": {"options": [
            {"name": "short", "color": "green"},
            {"name": "mid", "color": "yellow"},
            {"name": "long", "color": "blue"},
            {"name": "unknown", "color": "gray"},
        ]}},
        "Published": {"date": {}},
        "Duration (s)": {"number": {"format": "number"}},
        "Source Keyword": {"select": {}},
        "Tags": {"multi_select": {}},
        "Description": {"rich_text": {}},
        "Top Comments": {"rich_text": {}},
        "Thumbnail URL": {"url": {}},
        "Week": {"date": {}},
    }

    missing = {k: v for k, v in needed.items() if k not in existing}
    if missing:
        log.info(f"  Adding {len(missing)} missing properties to database...")
        notion.databases.update(database_id=database_id, properties=missing)
    else:
        log.info("  Database schema is up to date")


def build_page_properties(video: dict, comments: list[str], week_date: str) -> dict:
    """Build the Notion page properties dict for one video row."""
    video_url = f"https://www.youtube.com/watch?v={video['video_id']}"
    channel_url = f"https://www.youtube.com/channel/{video.get('channel_id', '')}"

    comments_text = truncate(" ‖ ".join(comments)) if comments else ""
    description_text = truncate(video.get("description", ""))

    # Tags: first 5, strip whitespace
    tags = [{"name": t.strip()} for t in (video.get("tags") or [])[:5] if t.strip()]

    published = video.get("published_at", "")
    published_date = published[:10] if published else None

    source_kw = video.get("source_keyword", "") or ""

    props = {
        "Name": {
            "title": [{"text": {"content": truncate(video.get("title", ""), 2000)}}]
        },
        "YouTube URL": {"url": video_url},
        "Channel": {
            "rich_text": [{"text": {"content": video.get("channel_title", "")}}]
        },
        "Channel URL": {"url": channel_url},
        "Views": {"number": video.get("view_count", 0)},
        "Engagement Rate": {"number": round(video.get("engagement_rate", 0), 4)},
        "Format": {"select": {"name": video.get("format", "unknown")}},
        "Duration (s)": {"number": video.get("duration_seconds") or 0},
        "Thumbnail URL": {"url": video.get("thumbnail_url") or None},
        "Week": {"date": {"start": week_date}},
    }

    if published_date:
        props["Published"] = {"date": {"start": published_date}}

    if source_kw:
        props["Source Keyword"] = {"select": {"name": source_kw[:100]}}

    if tags:
        props["Tags"] = {"multi_select": tags}

    if description_text:
        props["Description"] = {
            "rich_text": [{"text": {"content": description_text}}]
        }

    if comments_text:
        props["Top Comments"] = {
            "rich_text": [{"text": {"content": comments_text}}]
        }

    return props


def main():
    for path, name in [
        (config.ANALYSIS_PATH, "analysis.json — run analyze_trends.py first"),
        (config.VIDEO_DETAILS_PATH, "video_details.json — run fetch_video_details.py first"),
        (config.VIDEO_COMMENTS_PATH, "video_comments.json — run fetch_video_comments.py first"),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {path} — {name}")

    if not config.NOTION_DATABASE_ID:
        raise ValueError("NOTION_DATABASE_ID is not set in .env")

    with open(config.ANALYSIS_PATH) as f:
        analysis = json.load(f)
    with open(config.VIDEO_DETAILS_PATH) as f:
        video_data = json.load(f)
    with open(config.VIDEO_COMMENTS_PATH) as f:
        comments_data = json.load(f)

    # Build lookup maps
    details_map = {v["video_id"]: v for v in video_data["videos"]}
    comments_map = comments_data.get("comments", {})

    top_videos = analysis.get("top_videos_by_views", [])[:config.TOP_N_DEEP]
    week_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    notion = get_notion_client()
    database_id = config.NOTION_DATABASE_ID

    log.info(f"Connecting to Notion database {database_id}...")
    ensure_database_schema(notion, database_id)

    log.info(f"Writing {len(top_videos)} videos to Notion...")
    success = 0
    for v in top_videos:
        vid_id = v["video_id"]
        # Merge analysis entry with full details (description, tags, etc.)
        full_video = {**v, **details_map.get(vid_id, {})}
        comments = comments_map.get(vid_id, [])

        props = build_page_properties(full_video, comments, week_date)
        try:
            notion.pages.create(
                parent={"database_id": database_id},
                properties=props,
            )
            log.info(f"  ✓ {full_video.get('title', vid_id)[:60]}")
            success += 1
        except APIResponseError as e:
            log.warning(f"  ✗ Failed to write {vid_id}: {e}")

    log.info(f"Notion: {success}/{len(top_videos)} rows written to database")
    return {"rows_written": success, "database_id": database_id}


if __name__ == "__main__":
    main()
