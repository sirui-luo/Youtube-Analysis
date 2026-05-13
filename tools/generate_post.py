"""
Tool: generate_post.py
Uses Claude Vision API to generate a platform-native social post caption
and suggest a photo ordering based on uploaded photos + reference video titles.
"""

import base64
import io
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 4 * 1024 * 1024   # 4 MB — well under Claude's 5 MB limit
MAX_DIMENSION = 1568                  # Claude's recommended max dimension


def _compress_image_b64(b64_str: str) -> str:
    """
    Resize and re-encode a base64 image so it stays under MAX_IMAGE_BYTES.
    Returns a new base64 string (JPEG).
    """
    from PIL import Image

    raw = base64.b64decode(b64_str)
    if len(raw) <= MAX_IMAGE_BYTES:
        return b64_str  # Already small enough

    img = Image.open(io.BytesIO(raw)).convert("RGB")

    # Scale down if either dimension exceeds MAX_DIMENSION
    w, h = img.size
    if max(w, h) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Binary-search for a JPEG quality that fits
    quality = 85
    for _ in range(6):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_IMAGE_BYTES:
            break
        quality -= 12

    log.info(f"Compressed image: {len(raw)//1024}KB → {buf.tell()//1024}KB (q={quality})")
    return base64.b64encode(buf.getvalue()).decode()


def main(
    photos_b64: list,
    video_titles: list,
    user_ideas: str,
    platform: str,
    tone: str = "",
    rednote_style: str = "图文",
) -> dict:
    """
    Generate a social post caption and suggested photo order.

    Args:
        photos_b64: List of base64-encoded image strings (JPEG/PNG)
        video_titles: List of reference YouTube video titles (may be empty)
        user_ideas: Free-text ideas from the user (may be empty)
        platform: "instagram" or "rednote"
        tone: Instagram tone — "Aesthetic", "Engagement", or "Casual" (ignored for rednote)
        rednote_style: "图文" (structured) or "种草" (casual recommendation)

    Returns:
        {
            "caption": str,
            "photo_order": [int, ...],   # indices in suggested display order
            "photo_notes": [str, ...]    # one-line note per slot in suggested order
        }
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    n = len(photos_b64)

    # Build the prompt
    ref_section = ""
    if video_titles:
        lines = []
        for v in video_titles:
            if isinstance(v, dict):
                line = f"- {v.get('title', '')}"
                desc = (v.get('description') or "").strip()
                if desc:
                    line += f"\n  Description: {desc}"
            else:
                line = f"- {v}"
            lines.append(line)
        ref_section = f"\n\nReference videos the user found inspiring:\n" + "\n".join(lines)

    ideas_section = ""
    if user_ideas.strip():
        ideas_section = f"\n\nUser's ideas / vibe notes: {user_ideas.strip()}"

    if platform == "rednote":
        style_desc = (
            "图文 style (photo essay): structured format with punchy title + 正文 paragraphs + 📌 tips + #话题标签"
            if rednote_style == "图文"
            else "种草 style (lifestyle recommendation): casual, conversational, emoji-rich, product/experience recommendation format"
        )
        prompt = f"""You are a top 小红书 (RedNote/Xiaohongshu) content creator. Generate a viral post from {n} uploaded photos.

Platform: 小红书 (RedNote)
Style: {style_desc}

Language rules:
- Write primarily in Chinese (Mandarin)
- Keep fashion/lifestyle terminology in English (e.g. "quiet luxury", "GRWM", "soft girl", "aesthetic", "outfit", "vibe")
- Use natural Chinese internet slang, puns, and humor where appropriate{ref_section}{ideas_section}

The user has uploaded {n} photos (labeled Photo 1 through Photo {n}).

Your task:
1. Select ONLY the photos that work well together for a cohesive post — drop any that are blurry, redundant, or hurt the visual story. You do NOT have to use all photos.
2. Suggest the best display order for the selected photos (for visual storytelling and maximum engagement)
3. Write a platform-native title (≤25 Chinese characters, punchy hook-style, matches the post style) and body separately
4. Give a one-line note for each selected photo slot explaining why it's included and placed there

Return ONLY valid JSON in this exact format (no markdown, no explanation outside the JSON):
{{
  "title": "小红书标题，≤25字，吸引眼球",
  "body": "完整的小红书帖子正文内容（不含标题）",
  "photo_order": [0-based indices of SELECTED photos in display order — may be fewer than {n}, e.g. [2, 0, 1]],
  "photo_notes": [one short English note per selected slot, e.g. ["strong opener", "mid story", "satisfying close"]]
}}

CRITICAL JSON RULE: Never use bare double-quote characters (") inside string values — they break JSON parsing. Replace any quoted phrase with 「」brackets instead (e.g. 「我没怎么搭」的感觉 NOT "我没怎么搭"的感觉)."""

    else:  # instagram
        tone_desc = {
            "Aesthetic": "minimalist and aesthetic — 1-3 short poetic sentences, subtle emojis or none, clean and aspirational. Every sentence must start with a capital letter. Use 15-20 niche hashtags at the end.",
            "Engagement": "vlogger/blogger style — warm, personal, like you're telling a friend about your day. Natural flow, not stiff. Hook in the first line, a short personal story or observation, then a genuine CTA (a question or 'save this'). 1-2 emojis max. Every sentence must start with a capital letter. Use 20-30 hashtags at the end mixing broad and niche.",
            "Casual": "casual and conversational — chill, fun, like a text from a friend. Short sentences, relaxed energy, 1-2 emojis. Every sentence must start with a capital letter. Use 15-20 hashtags at the end.",
        }.get(tone, "authentic and platform-native. Every sentence starts with a capital letter. Use 15-20 hashtags.")

        prompt = f"""You are a top Instagram content creator. Generate a viral post from {n} uploaded photos.

Platform: Instagram
Tone: {tone_desc}

Caption rules:
- Every sentence must begin with a capital letter
- Hashtags go at the very end of the caption, after a line break
- Use the number of hashtags specified in the tone description above{ref_section}{ideas_section}

The user has uploaded {n} photos (labeled Photo 1 through Photo {n}).

Your task:
1. Select ONLY the photos that work well together for a cohesive carousel — drop any that are blurry, off-topic, redundant, or hurt the visual story. You do NOT have to use all photos.
2. Suggest the best carousel order for the selected photos (hook on slide 1, build story, strong closer)
3. Write a short cover slide text (5-10 words, hook-style — curiosity gap, number, or POV — suitable as text overlay on the first photo)
4. Write a platform-native English caption matching the tone (hashtags at the very end)
5. Give a one-line note for each selected photo slot explaining why it's included and placed there

Return ONLY valid JSON in this exact format (no markdown, no explanation outside the JSON):
{{
  "cover_slide_text": "5-10 word hook for text overlay on slide 1",
  "caption": "Full Instagram caption with hashtags at the end",
  "photo_order": [0-based indices of SELECTED photos in display order — may be fewer than {n}, e.g. [0, 2, 1]],
  "photo_notes": [one short note per selected slot, e.g. ["strong hook", "build story", "satisfying close"]]
}}

CRITICAL JSON RULE: Never use bare double-quote characters (") inside string values — they break JSON parsing. Use single quotes or rephrase instead."""

    # Compress photos that exceed Claude's 5MB limit
    photos_b64 = [_compress_image_b64(b) for b in photos_b64]

    # Build multi-modal message content
    content = []

    # 1. Reference video thumbnails (visual style signal)
    ref_thumbs = [v for v in video_titles if isinstance(v, dict) and v.get("thumbnail_url")]
    if ref_thumbs:
        content.append({"type": "text", "text": "Thumbnails of reference videos trending in this niche — study their visual style, color palette, and aesthetic:"})
        for v in ref_thumbs:
            content.append({"type": "text", "text": f"- {v.get('title', '')}"})
            content.append({
                "type": "image",
                "source": {"type": "url", "url": v["thumbnail_url"]},
            })

    # 2. User's uploaded photos
    for i, b64 in enumerate(photos_b64):
        content.append({"type": "text", "text": f"Photo {i + 1}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            }
        })

    # 3. The instruction prompt
    content.append({"type": "text", "text": prompt})

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": content}],
    )

    raw = message.content[0].text.strip()
    log.info(f"generate_post raw response length: {len(raw)}")

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    # Attempt 1: direct parse
    # Attempt 2: escape literal control characters inside JSON string values
    # Attempt 3: extract first {...} block in case of leading/trailing junk
    import re

    def _json_candidates(text):
        """Yield the full text, then the first {...} block found within it."""
        yield text
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            yield m.group(0)

    def _escape_string_contents(m):
        s = m.group(0)
        s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return s

    result = None
    for candidate in _json_candidates(raw):
        for text in [candidate, re.sub(r'"(?:[^"\\]|\\.)*"', _escape_string_contents, candidate, flags=re.DOTALL)]:
            try:
                result = json.loads(text)
                break
            except json.JSONDecodeError:
                continue
        if result is not None:
            break

    if result is None:
        # Final fallback: json_repair handles unescaped quotes and other common model mistakes
        try:
            from json_repair import repair_json
            result = json.loads(repair_json(raw))
            log.info("json_repair fallback succeeded")
        except Exception:
            raise ValueError(f"Could not parse JSON from model response: {raw[:200]}")

    # Validate and fill defaults
    if "photo_order" not in result or len(result["photo_order"]) == 0:
        result["photo_order"] = list(range(n))
    if "photo_notes" not in result or len(result["photo_notes"]) == 0:
        result["photo_notes"] = [""] * len(result["photo_order"])

    # RedNote: normalise to caption field for backwards compat; keep title + body too
    if platform == "rednote":
        if "body" in result and "caption" not in result:
            result["caption"] = result["body"]
    # Instagram: cover_slide_text is optional — no default needed

    return result
