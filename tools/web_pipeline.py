"""
Tool: web_pipeline.py
Orchestrates the analysis pipeline for a user-supplied topic.
Used by the FastAPI web app — does NOT touch Google Sheets/Slides/Notion/email.
Each run uses an isolated job directory under .tmp/jobs/{job_id}/.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

log = logging.getLogger(__name__)


def _generate_title_suggestions(topic: str, keywords: list, formulas: list) -> list:
    """
    Single Claude Haiku call — generates one suggested title per detected formula.
    Returns a flat list of title strings. Non-critical: caller catches all exceptions.
    """
    from anthropic import Anthropic
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not formulas:
        return []

    client = Anthropic(api_key=api_key)
    n = len(formulas)

    formulas_str = "\n".join(
        f"{i + 1}. {f['hook_type']}: template \"{f['template_hint']}\" "
        f"— example: \"{f['example_title']}\""
        for i, f in enumerate(formulas)
    )
    kw_terms = [k["term"] if isinstance(k, dict) else k for k in keywords[:5]]
    keywords_str = ", ".join(kw_terms)

    prompt = f"""You are an expert YouTube title writer. Generate exactly {n} YouTube video titles for the topic "{topic}".

Trending keywords in this niche: {keywords_str}

Use each of these proven title formulas (one title per formula, strictly in order):
{formulas_str}

Rules:
- Each title must clearly follow its formula's structure
- Each title must be relevant to "{topic}"
- Incorporate trending keywords naturally where they fit
- Titles should be compelling and click-worthy
- Return ONLY a valid JSON array of {n} title strings, no explanation, no markdown

Example format: ["Title 1", "Title 2", "Title 3"]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    return json.loads(raw)


def run_web_pipeline(topic: str, job_id: str, progress_callback=None) -> dict:
    """
    Run the 5-step analysis pipeline for a user topic.

    Args:
        topic: User-supplied topic string (e.g. "home gym setup")
        job_id: Unique ID for this run — determines temp directory
        progress_callback: Optional callable(step: str, message: str)

    Returns:
        analysis dict (same shape as analysis.json)
    """
    from expand_topic import expand_topic
    import search_youtube
    import fetch_video_details
    import fetch_channel_stats
    import analyze_trends
    import fetch_video_comments

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work_dir = os.path.join(project_root, ".tmp", "jobs", job_id)
    os.makedirs(work_dir, exist_ok=True)

    def progress(step: str, message: str):
        log.info(f"[{step}] {message}")
        if progress_callback:
            progress_callback(step, message)

    # Step 1: Expand topic → keywords
    progress("expand", f"Expanding \"{topic}\" into search keywords...")
    keywords = expand_topic(topic)
    progress("expand", f"Generated {len(keywords)} keywords")

    # Step 2: Search YouTube
    progress("search", f"Searching YouTube for {len(keywords)} keywords...")
    result = search_youtube.main(keywords=keywords, work_dir=work_dir)
    n_videos = result.get("total_videos", 0)
    progress("search", f"Found {n_videos} videos")

    # Step 3: Fetch video details
    progress("details", f"Fetching stats for {n_videos} videos...")
    fetch_video_details.main(work_dir=work_dir)
    progress("details", "Video details fetched")

    # Step 4: Fetch channel stats
    progress("channels", "Fetching channel statistics...")
    fetch_channel_stats.main(work_dir=work_dir)
    progress("channels", "Channel stats fetched")

    # Step 5: Analyze
    progress("analyze", "Analyzing trends and generating insights...")
    analysis = analyze_trends.main(work_dir=work_dir, keywords=keywords, min_duration=180)

    # Step 6: Fetch comments for top videos
    progress("comments", "Fetching top comments for top videos...")
    try:
        comments_data = fetch_video_comments.main(work_dir=work_dir)
        comments_map = comments_data.get("comments", {})
        # Attach comments directly to each top video in the analysis
        for v in analysis.get("top_videos_by_views", []):
            v["comments"] = comments_map.get(v["video_id"], [])
    except Exception as e:
        log.warning(f"Comment fetching failed (non-critical): {e}")

    # Step 7: Generate title suggestions
    progress("titles", "Generating title suggestions...")
    try:
        suggestions = _generate_title_suggestions(
            topic,
            analysis.get("trending_keywords", []),
            analysis.get("title_formulas", []),
        )
        analysis["title_suggestions"] = suggestions
        progress("titles", f"Generated {len(suggestions)} title suggestions")
    except Exception as e:
        log.warning(f"Title suggestion generation failed (non-critical): {e}")
        analysis["title_suggestions"] = []

    progress("done", "Analysis complete!")

    return analysis
