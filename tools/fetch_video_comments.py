"""
Tool 5b: fetch_video_comments.py
Fetches top comments for the top N videos from analysis.json.
Output: .tmp/video_comments.json
Quota cost: 1 unit per video (commentThreads.list)
"""

import json
import logging
import os
import sys

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


def fetch_top_comments(youtube, video_id: str, max_comments: int = 5) -> list[str]:
    """Return top comment texts for a video, ordered by relevance."""
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            order="relevance",
            maxResults=max_comments,
            textFormat="plainText",
        ).execute()
    except HttpError as e:
        # Comments may be disabled on some videos
        log.warning(f"  Comments unavailable for {video_id}: {e}")
        return []

    comments = []
    for item in response.get("items", []):
        text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
        comments.append(text.strip())

    return comments


def main(work_dir=None):
    _work_dir = work_dir or config.TMP_DIR
    _analysis_path = os.path.join(_work_dir, "analysis.json")
    _output_path = os.path.join(_work_dir, "video_comments.json")

    if not os.path.exists(_analysis_path):
        raise FileNotFoundError(f"Missing {_analysis_path} — run analyze_trends.py first")

    with open(_analysis_path) as f:
        analysis = json.load(f)

    top_videos = analysis.get("top_videos_by_views", [])[:config.TOP_N_DEEP]

    if not top_videos:
        log.warning("No top videos found in analysis.json")
        return {"comments": {}}

    youtube = build_youtube_client()
    comments_map = {}

    log.info(f"Fetching top comments for {len(top_videos)} videos...")
    for v in top_videos:
        video_id = v["video_id"]
        comments = fetch_top_comments(youtube, video_id, max_comments=5)
        comments_map[video_id] = comments
        log.info(f"  {video_id} → {len(comments)} comments")

    output = {
        "fetched_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "total_videos": len(comments_map),
        "comments": comments_map,
    }

    with open(_output_path, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Saved to {_output_path}")
    return output


if __name__ == "__main__":
    main()
