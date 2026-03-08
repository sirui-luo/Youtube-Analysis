"""
Tool 4: analyze_trends.py
Pure-Python analysis — zero API calls.
Reads video_details.json + channel_stats.json, produces analysis.json.
"""

import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "this", "that", "you", "your", "how", "what",
    "why", "when", "i", "my", "we", "our", "its", "be", "are", "was", "were",
    "have", "has", "do", "does", "will", "can", "could", "would", "should",
    "from", "by", "as", "up", "out", "if", "about", "into", "through",
    "he", "she", "they", "them", "their", "all", "new", "get", "make",
    "use", "using", "made", "just", "like", "more", "not", "no", "so",
    "than", "then", "now", "s", "t", "re", "ve", "ll", "d",
}

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def top_videos_by_views(videos: list[dict], n: int) -> list[dict]:
    sorted_v = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)
    return [
        {
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_title": v["channel_title"],
            "view_count": v["view_count"],
            "engagement_rate": v["engagement_rate"],
            "format": v["format"],
            "published_at": v["published_at"],
            "thumbnail_url": v.get("thumbnail_url", ""),
        }
        for v in sorted_v[:n]
    ]


def top_videos_by_engagement(videos: list[dict], n: int) -> list[dict]:
    # Only consider videos with meaningful views (>500)
    eligible = [v for v in videos if v.get("view_count", 0) > 500]
    sorted_v = sorted(eligible, key=lambda v: v.get("engagement_rate", 0), reverse=True)
    return [
        {
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_title": v["channel_title"],
            "view_count": v["view_count"],
            "engagement_rate": v["engagement_rate"],
            "format": v["format"],
            "published_at": v["published_at"],
            "thumbnail_url": v.get("thumbnail_url", ""),
        }
        for v in sorted_v[:n]
    ]


def extract_keywords_from_titles(videos: list[dict]) -> list[dict]:
    """Tokenize titles, count unigrams and bigrams, excluding stopwords."""
    word_counter: Counter = Counter()
    bigram_counter: Counter = Counter()

    for v in videos:
        title = v.get("title", "").lower()
        # Remove punctuation
        title = re.sub(r"[^\w\s]", " ", title)
        words = [w for w in title.split() if w not in STOPWORDS and len(w) > 2]
        word_counter.update(words)
        # Bigrams
        for i in range(len(words) - 1):
            bigram_counter[(words[i], words[i + 1])] += 1

    # Merge: bigrams with count >= 2 take priority
    results = []
    for (w1, w2), count in bigram_counter.most_common(30):
        if count >= 2:
            results.append({"term": f"{w1} {w2}", "count": count})

    for word, count in word_counter.most_common(50):
        if count >= 2:
            results.append({"term": word, "count": count})

    # Deduplicate by term
    seen = {}
    for r in results:
        if r["term"] not in seen:
            seen[r["term"]] = r

    return sorted(seen.values(), key=lambda x: x["count"], reverse=True)[:20]


def top_channels_by_views(channels: list[dict], n: int) -> list[dict]:
    eligible = [c for c in channels if c.get("total_views", 0) > 0]
    sorted_c = sorted(eligible, key=lambda c: c.get("total_views", 0), reverse=True)
    return [
        {
            "channel_id": c["channel_id"],
            "channel_name": c["channel_name"],
            "subscriber_count": c["subscriber_count"],
            "total_views": c["total_views"],
            "videos_this_week": c.get("videos_this_week", 0),
            "uploads_per_week_estimate": c.get("uploads_per_week_estimate"),
        }
        for c in sorted_c[:n]
    ]


def format_breakdown(videos: list[dict]) -> dict:
    counts = Counter(v.get("format", "unknown") for v in videos)
    total = len(videos)
    result = {}
    for fmt in ["short", "mid", "long", "unknown"]:
        count = counts.get(fmt, 0)
        result[fmt] = {
            "count": count,
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        }
    return result


def upload_timing_analysis(videos: list[dict]) -> dict:
    """Returns best day, best hour, and per-day average view counts."""
    day_views: dict[str, list[int]] = {d: [] for d in DAY_ORDER}
    hour_counts: Counter = Counter()

    for v in videos:
        day = v.get("publish_day")
        hour = v.get("publish_hour")
        views = v.get("view_count", 0)
        if day and day in day_views:
            day_views[day].append(views)
        if hour is not None:
            hour_counts[hour] += 1

    day_avg_views = {}
    for day in DAY_ORDER:
        views_list = day_views[day]
        day_avg_views[day] = int(sum(views_list) / len(views_list)) if views_list else 0

    best_day = max(day_avg_views, key=day_avg_views.get) if day_avg_views else None
    best_hour = hour_counts.most_common(1)[0][0] if hour_counts else None

    return {
        "best_day": best_day,
        "best_hour": best_hour,
        "day_avg_views": day_avg_views,
        "hour_distribution": dict(sorted(hour_counts.items())),
    }


def find_content_gaps(videos: list[dict]) -> list[str]:
    """
    Keywords from config that appear in fewer than MIN_GAP_THRESHOLD video titles.
    Low title presence = low competition = content opportunity.
    """
    title_counts: Counter = Counter()
    for v in videos:
        title = v.get("title", "").lower()
        for kw in config.KEYWORDS:
            if kw.lower() in title:
                title_counts[kw] += 1

    gaps = []
    for kw in config.KEYWORDS:
        if title_counts.get(kw, 0) < config.MIN_GAP_THRESHOLD:
            gaps.append(kw)

    return gaps


def generate_recommendations(
    videos: list[dict],
    timing: dict,
    fmt_breakdown: dict,
    gaps: list[str],
    top_keywords: list[dict],
) -> list[str]:
    recs = []

    # Best upload day
    if timing.get("best_day"):
        day = timing["best_day"]
        avg = timing["day_avg_views"].get(day, 0)
        recs.append(
            f"Upload on {day} — it has the highest average view count "
            f"({avg:,} views/video) among fashion & beauty content this week."
        )

    # Best upload hour
    if timing.get("best_hour") is not None:
        hour = timing["best_hour"]
        ampm = f"{hour % 12 or 12}{'AM' if hour < 12 else 'PM'} UTC"
        recs.append(f"Schedule uploads around {ampm} — most fashion & beauty videos are published then.")

    # Shorts underrepresented
    short_pct = fmt_breakdown.get("short", {}).get("pct", 0)
    if short_pct < 20:
        recs.append(
            f"Shorts are underrepresented ({short_pct}% of content). "
            "Adding 2–3 short clips per week could increase reach and discoverability."
        )

    # Dominant format
    dominant = max(
        ["short", "mid", "long"],
        key=lambda f: fmt_breakdown.get(f, {}).get("pct", 0),
    )
    dominant_pct = fmt_breakdown.get(dominant, {}).get("pct", 0)
    if dominant_pct > 50:
        label = {"short": "Short-form (<1 min)", "mid": "Mid-form (1–10 min)", "long": "Long-form (>10 min)"}[dominant]
        recs.append(
            f"{label} content dominates ({dominant_pct}% of top videos). "
            "This is the format your audience is watching most."
        )

    # Top trending keyword
    if top_keywords:
        top_kw = top_keywords[0]["term"]
        top_cnt = top_keywords[0]["count"]
        recs.append(
            f'"{top_kw}" appears in {top_cnt} video titles this week — '
            "consider covering this topic if you haven't recently."
        )

    # Content gaps
    if gaps:
        gap_str = ", ".join(f'"{g}"' for g in gaps[:3])
        recs.append(
            f"Underserved topics this week: {gap_str}. "
            "Low competition + existing search demand = content opportunity."
        )

    return recs


def main():
    for path, name in [
        (config.VIDEO_DETAILS_PATH, "video_details.json — run fetch_video_details.py first"),
        (config.CHANNEL_STATS_PATH, "channel_stats.json — run fetch_channel_stats.py first"),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {path} — {name}")

    with open(config.VIDEO_DETAILS_PATH) as f:
        video_data = json.load(f)
    with open(config.CHANNEL_STATS_PATH) as f:
        channel_data = json.load(f)

    videos = video_data["videos"]
    channels = channel_data["channels"]

    if len(videos) < 10:
        log.warning(f"Only {len(videos)} videos — analysis may be sparse")

    log.info(f"Analyzing {len(videos)} videos and {len(channels)} channels...")

    top_by_views = top_videos_by_views(videos, config.TOP_N)
    top_by_engagement = top_videos_by_engagement(videos, config.TOP_N)
    trending_keywords = extract_keywords_from_titles(videos)
    top_channels = top_channels_by_views(channels, config.TOP_N)
    fmt_breakdown = format_breakdown(videos)
    timing = upload_timing_analysis(videos)
    gaps = find_content_gaps(videos)
    recommendations = generate_recommendations(
        videos, timing, fmt_breakdown, gaps, trending_keywords
    )

    total_views = sum(v.get("view_count", 0) for v in videos)
    avg_engagement = (
        round(sum(v.get("engagement_rate", 0) for v in videos) / len(videos), 4)
        if videos else 0
    )
    top_topic = trending_keywords[0]["term"] if trending_keywords else "N/A"

    # Date range
    dates = [v["published_at"][:10] for v in videos if v.get("published_at")]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "N/A"

    analysis = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_videos_analyzed": len(videos),
            "total_channels_found": len(channels),
            "date_range": date_range,
            "total_views_in_dataset": total_views,
            "avg_engagement_rate": avg_engagement,
            "top_topic": top_topic,
        },
        "top_videos_by_views": top_by_views,
        "top_videos_by_engagement": top_by_engagement,
        "trending_keywords": trending_keywords,
        "top_channels": top_channels,
        "format_breakdown": fmt_breakdown,
        "upload_timing": timing,
        "content_gaps": gaps,
        "recommendations": recommendations,
    }

    with open(config.ANALYSIS_PATH, "w") as f:
        json.dump(analysis, f, indent=2)

    log.info(f"Analysis complete. Saved to {config.ANALYSIS_PATH}")
    log.info(f"  Top topic: {top_topic}")
    log.info(f"  Recommendations: {len(recommendations)}")
    log.info(f"  Content gaps: {gaps}")
    return analysis


if __name__ == "__main__":
    main()
