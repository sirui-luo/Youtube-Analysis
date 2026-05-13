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

# ---------------------------------------------------------------------------
# Title formula detection — hook type patterns
# ---------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    "^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF\u2700-\u27BF]"
)

_HOOK_PATTERNS = [
    (
        "Number Hook",
        "[number] [keyword] [benefit/topic]",
        lambda t: bool(re.search(r"(?<![a-z])\d+\s+\w", t, re.IGNORECASE))
            or bool(re.match(r"^\d+", t.strip())),
    ),
    (
        "Question Hook",
        "How/Why/What [topic]? or [topic]?",
        lambda t: "?" in t
            or bool(re.match(r"^(how|why|what|when|which|is|are|do|does|can|should|would|will)\b", t, re.IGNORECASE)),
    ),
    (
        "POV / First-Person",
        "POV: [scenario] or I/My [action/thing]",
        lambda t: bool(re.match(r"^(pov\s*:|i\s+|my\s+|we\s+)", t, re.IGNORECASE)),
    ),
    (
        "Curiosity Gap",
        "The [secret/truth] about [topic] / Nobody talks about...",
        lambda t: bool(re.search(
            r"\b(nobody|secret|truth about|honest|changed everything|real reason|you didn'?t know|never told|they don'?t want)\b",
            t, re.IGNORECASE,
        )),
    ),
    (
        "List / Roundup",
        "Best/Top/Ultimate [number] [things]",
        lambda t: bool(re.match(r"^(best|top|ultimate|every|all the)\b", t, re.IGNORECASE)),
    ),
    (
        "Challenge / Experiment",
        "I tried [X] for [Y days] / [X] Challenge",
        lambda t: bool(re.search(
            r"\b(challenge|i tried|i tested|tested|experiment|for \d+\s*(days?|weeks?|months?))\b",
            t, re.IGNORECASE,
        )),
    ),
    (
        "GRWM / Day-in-Life",
        "GRWM: [context] / Day in my life [detail]",
        lambda t: bool(re.search(
            r"\b(grwm|get ready with me|day in my life|week in my life|come with me|vlog)\b",
            t, re.IGNORECASE,
        )),
    ),
    (
        "Emoji-Led",
        "[emoji] [topic] [emoji]",
        lambda t: bool(_EMOJI_RE.match(t.strip())),
    ),
]


def title_formula_analysis(videos: list[dict], top_n: int = 20, return_n: int = 5) -> list[dict]:
    """
    Detect hook-type patterns in the top_n videos by views.
    Returns the top return_n patterns ranked by avg_views.
    Each video may match multiple patterns; each match is counted independently.
    Non-ASCII-only titles (likely non-English) are not excluded — patterns still apply.
    """
    candidates = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)[:top_n]

    # bucket: hook_type -> list of (views, engagement, title, video_id)
    buckets: dict[str, list] = {name: [] for name, _, _ in _HOOK_PATTERNS}

    for v in candidates:
        title = v.get("title", "")
        views = v.get("view_count", 0)
        eng = v.get("engagement_rate", 0)
        vid_id = v.get("video_id", "")
        for name, _, matcher in _HOOK_PATTERNS:
            try:
                if matcher(title):
                    buckets[name].append((views, eng, title, vid_id))
            except Exception:
                pass

    results = []
    for name, template, _ in _HOOK_PATTERNS:
        entries = buckets[name]
        if not entries:
            continue
        avg_views = int(sum(e[0] for e in entries) / len(entries))
        avg_eng = round(sum(e[1] for e in entries) / len(entries), 4)
        best = max(entries, key=lambda e: e[0])
        results.append({
            "hook_type": name,
            "template_hint": template,
            "count": len(entries),
            "avg_views": avg_views,
            "avg_engagement": avg_eng,
            "example_title": best[2],
            "example_views": best[0],
            "example_video_id": best[3],
        })

    return sorted(results, key=lambda x: x["avg_views"], reverse=True)[:return_n]


def top_videos_by_views(videos: list[dict], n: int, min_duration: int = None) -> list[dict]:
    _min = min_duration if min_duration is not None else config.MIN_DURATION_FOR_TOP
    videos = [v for v in videos if (v.get("duration_seconds") or 0) > _min]
    sorted_v = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)
    return [
        {
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_id": v.get("channel_id", ""),
            "channel_title": v["channel_title"],
            "view_count": v["view_count"],
            "engagement_rate": v["engagement_rate"],
            "format": v["format"],
            "published_at": v["published_at"],
            "thumbnail_url": v.get("thumbnail_url", ""),
            "description": v.get("description", ""),
        }
        for v in sorted_v[:n]
    ]


def top_videos_by_engagement(videos: list[dict], n: int, min_duration: int = None) -> list[dict]:
    # Only consider videos with meaningful views (>500) and minimum duration
    _min = min_duration if min_duration is not None else config.MIN_DURATION_FOR_TOP
    eligible = [v for v in videos if v.get("view_count", 0) > 500 and (v.get("duration_seconds") or 0) > _min]
    sorted_v = sorted(eligible, key=lambda v: v.get("engagement_rate", 0), reverse=True)
    return [
        {
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_id": v.get("channel_id", ""),
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


def relevance_filter(videos: list[dict], keywords: list[str]) -> list[dict]:
    """
    Drop videos whose titles share no significant tokens with the search keywords.
    Prevents YouTube returning off-topic results (e.g. Bollywood vlogs for 'NYC vlog').
    """
    kw_tokens = {
        word
        for kw in keywords
        for word in re.sub(r"[^\w\s]", " ", kw.lower()).split()
        if word not in STOPWORDS and len(word) > 2
    }
    if not kw_tokens:
        return videos

    filtered = []
    for v in videos:
        title_words = set(re.sub(r"[^\w\s]", " ", v.get("title", "").lower()).split())
        if title_words & kw_tokens:
            filtered.append(v)

    removed = len(videos) - len(filtered)
    if removed:
        log.info(f"Relevance filter removed {removed} off-topic videos")
    return filtered


def video_length_stats(videos: list[dict]) -> dict:
    """
    Median and average duration for non-short videos (>60s).
    Returns seconds so the frontend can format as it likes.
    """
    durations = sorted(
        v["duration_seconds"] for v in videos
        if v.get("duration_seconds") and v["duration_seconds"] > config.SHORT_MAX_DURATION
    )
    if not durations:
        return {"median_seconds": None, "avg_seconds": None, "sample_size": 0}
    mid = len(durations) // 2
    median = (
        durations[mid] if len(durations) % 2
        else (durations[mid - 1] + durations[mid]) // 2
    )
    avg = int(sum(durations) / len(durations))
    return {"median_seconds": median, "avg_seconds": avg, "sample_size": len(durations)}


def rising_channels(videos: list[dict], channels: list[dict], n: int = 5) -> list[dict]:
    """
    Channels punching above their weight: views-this-week / subscriber_count.
    High ratio = small channel getting outsized reach = opportunity signal.
    Excludes channels with hidden subscriber counts or fewer than 1,000 subscribers.
    """
    sub_map = {
        c["channel_id"]: c["subscriber_count"]
        for c in channels
        if c.get("subscriber_count") and c["subscriber_count"] >= 1000
    }
    name_map = {c["channel_id"]: c["channel_name"] for c in channels}

    # Sum views this week per channel from our dataset
    views_map: dict[str, int] = {}
    for v in videos:
        cid = v.get("channel_id", "")
        views_map[cid] = views_map.get(cid, 0) + v.get("view_count", 0)

    results = []
    for cid, week_views in views_map.items():
        sub_count = sub_map.get(cid)
        if not sub_count:
            continue
        ratio = round(week_views / sub_count, 3)
        results.append({
            "channel_id": cid,
            "channel_name": name_map.get(cid, ""),
            "subscriber_count": sub_count,
            "views_this_week": week_views,
            "view_to_sub_ratio": ratio,
        })

    return sorted(results, key=lambda x: x["view_to_sub_ratio"], reverse=True)[:n]


def find_content_gaps(videos: list[dict], keywords: list[str] = None) -> list[str]:
    """
    Keywords that appear in fewer than MIN_GAP_THRESHOLD video titles.
    Low title presence = low competition = content opportunity.
    """
    _keywords = keywords or config.KEYWORDS
    title_counts: Counter = Counter()
    for v in videos:
        title = v.get("title", "").lower()
        for kw in _keywords:
            if kw.lower() in title:
                title_counts[kw] += 1

    gaps = []
    for kw in _keywords:
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


def main(work_dir=None, keywords=None, min_duration=None):
    _work_dir = work_dir or config.TMP_DIR
    _video_details_path = os.path.join(_work_dir, "video_details.json")
    _channel_stats_path = os.path.join(_work_dir, "channel_stats.json")
    _analysis_path = os.path.join(_work_dir, "analysis.json")

    for path, name in [
        (_video_details_path, "video_details.json — run fetch_video_details.py first"),
        (_channel_stats_path, "channel_stats.json — run fetch_channel_stats.py first"),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {path} — {name}")

    with open(_video_details_path) as f:
        video_data = json.load(f)
    with open(_channel_stats_path) as f:
        channel_data = json.load(f)

    videos = video_data["videos"]
    channels = channel_data["channels"]

    _keywords_for_gaps = keywords or config.KEYWORDS
    videos = relevance_filter(videos, _keywords_for_gaps)

    if len(videos) < 10:
        log.warning(f"Only {len(videos)} videos — analysis may be sparse")

    log.info(f"Analyzing {len(videos)} videos and {len(channels)} channels...")

    top_by_views = top_videos_by_views(videos, config.TOP_N, min_duration=min_duration)
    top_by_engagement = top_videos_by_engagement(videos, config.TOP_N, min_duration=min_duration)
    trending_keywords = extract_keywords_from_titles(videos)
    top_channels = top_channels_by_views(channels, config.TOP_N)
    fmt_breakdown = format_breakdown(videos)
    timing = upload_timing_analysis(videos)
    length_stats = video_length_stats(videos)
    rising = rising_channels(videos, channels, config.TOP_N)
    title_formulas = title_formula_analysis(videos)
    gaps = find_content_gaps(videos, _keywords_for_gaps)
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
            "median_video_length_seconds": length_stats["median_seconds"],
            "avg_video_length_seconds": length_stats["avg_seconds"],
        },
        "search_keywords": _keywords_for_gaps,
        "top_videos_by_views": top_by_views,
        "top_videos_by_engagement": top_by_engagement,
        "trending_keywords": trending_keywords,
        "top_channels": top_channels,
        "rising_channels": rising,
        "title_formulas": title_formulas,
        "format_breakdown": fmt_breakdown,
        "upload_timing": timing,
        "content_gaps": gaps,
        "recommendations": recommendations,
    }

    with open(_analysis_path, "w") as f:
        json.dump(analysis, f, indent=2)

    log.info(f"Analysis complete. Saved to {_analysis_path}")
    log.info(f"  Top topic: {top_topic}")
    log.info(f"  Recommendations: {len(recommendations)}")
    log.info(f"  Content gaps: {gaps}")
    return analysis


if __name__ == "__main__":
    main()
