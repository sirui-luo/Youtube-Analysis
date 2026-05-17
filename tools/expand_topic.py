"""
Tool: expand_topic.py
Uses Claude API to expand a user topic into YouTube search keywords.
Falls back to simple expansion if ANTHROPIC_API_KEY is not set.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def expand_topic(topic: str) -> list[str]:
    """Expand a topic string into a list of YouTube search keywords."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — using simple keyword expansion")
        return _simple_expand(topic)

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        prompt = f"""Generate 10 YouTube search keywords for the topic: "{topic}"

Rules:
- Each keyword should be a specific search phrase someone would type on YouTube
- Mix different angles: tutorials, inspiration, ideas, vlogs, tips, routines
- Keep each keyword 2-5 words
- Make them natural and search-friendly
- Return ONLY a JSON array of strings, nothing else

Example output:
["keyword one", "keyword two", "keyword three"]"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()
        keywords = json.loads(text)
        log.info(f"Claude expanded '{topic}' into {len(keywords)} keywords")
        return keywords[:12]

    except Exception as e:
        log.warning(f"Claude expansion failed ({e}) — falling back to simple expansion")
        return _simple_expand(topic)


def _simple_expand(topic: str) -> list[str]:
    """Fallback: append common suffixes to the topic."""
    suffixes = [
        "",
        "tutorial",
        "ideas",
        "inspiration",
        "2025",
        "for beginners",
        "tips",
        "routine",
        "review",
        "guide",
    ]
    keywords = []
    for s in suffixes:
        kw = f"{topic} {s}".strip()
        keywords.append(kw)
    return keywords
