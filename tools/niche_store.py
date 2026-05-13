"""
Tool: niche_store.py
File-based persistence for saved niches and their cached analysis results.
All operations are synchronous file I/O — no API calls.
"""

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NICHES_FILE = os.path.join(_ROOT, "niches.json")
NICHES_DIR = os.path.join(_ROOT, ".tmp", "niches")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read() -> dict:
    if not os.path.exists(NICHES_FILE):
        return {"niches": []}
    with open(NICHES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(data: dict):
    with open(NICHES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _analysis_path(niche_id: str) -> str:
    return os.path.join(NICHES_DIR, niche_id, "analysis.json")


def _extract_summary(result: dict) -> dict:
    s = result.get("summary", {})
    kw = result.get("trending_keywords", [])
    channels = result.get("top_channels", [])
    top_videos = result.get("top_videos_by_views", [])
    return {
        "top_keyword": kw[0]["term"] if kw else "",
        "total_videos": s.get("total_videos_analyzed", 0),
        "top_channel": channels[0]["channel_name"] if channels else (
            top_videos[0]["channel_title"] if top_videos else ""
        ),
        "avg_engagement_rate": s.get("avg_engagement_rate", 0),
        "date_range": s.get("date_range", ""),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_analysis(niche_id: str, result: dict):
    path = _analysis_path(niche_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_niches() -> list:
    """Return all niches (index only, no full analysis data)."""
    return _read().get("niches", [])


def get_niche(niche_id: str) -> dict | None:
    """Return a single niche by ID, or None if not found."""
    return next((n for n in list_niches() if n["id"] == niche_id), None)


def save_niche(name: str, result: dict) -> dict:
    """
    Create a new niche, persist the analysis result, return the niche object.
    Uses the provided result as the initial cache (card is never empty).
    """
    niche_id = str(uuid.uuid4())
    now = _now()
    niche = {
        "id": niche_id,
        "name": name,
        "created_at": now,
        "last_refreshed": now,
        "refreshing": False,
        "summary": _extract_summary(result),
    }
    data = _read()
    data["niches"].append(niche)
    _write(data)
    _write_analysis(niche_id, result)
    log.info(f"Saved niche '{name}' as {niche_id}")
    return niche


def get_niche_result(niche_id: str) -> dict | None:
    """Return the full cached analysis for a niche, or None if not found."""
    path = _analysis_path(niche_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_niche(niche_id: str, result: dict) -> dict:
    """Refresh cache, update summary and last_refreshed, clear refreshing flag."""
    data = _read()
    for niche in data["niches"]:
        if niche["id"] == niche_id:
            niche["last_refreshed"] = _now()
            niche["refreshing"] = False
            niche["summary"] = _extract_summary(result)
            _write(data)
            _write_analysis(niche_id, result)
            log.info(f"Updated niche {niche_id}")
            return niche
    raise KeyError(f"Niche {niche_id} not found")


def rename_niche(niche_id: str, new_name: str) -> dict:
    """Rename a niche. Returns the updated niche object."""
    data = _read()
    for niche in data["niches"]:
        if niche["id"] == niche_id:
            niche["name"] = new_name.strip()
            _write(data)
            return niche
    raise KeyError(f"Niche {niche_id} not found")


def delete_niche(niche_id: str):
    """Remove a niche from the index and delete its analysis file."""
    data = _read()
    data["niches"] = [n for n in data["niches"] if n["id"] != niche_id]
    _write(data)
    niche_dir = os.path.join(NICHES_DIR, niche_id)
    if os.path.exists(niche_dir):
        shutil.rmtree(niche_dir)
    log.info(f"Deleted niche {niche_id}")


def reorder_niches(ordered_ids: list):
    """Rewrite niches in the given id order."""
    data = _read()
    index = {n["id"]: n for n in data["niches"]}
    data["niches"] = [index[i] for i in ordered_ids if i in index]
    _write(data)


def set_refreshing(niche_id: str, flag: bool):
    """Set the refreshing flag on a niche (used to show spinner on dashboard)."""
    data = _read()
    for niche in data["niches"]:
        if niche["id"] == niche_id:
            niche["refreshing"] = flag
            _write(data)
            return
    raise KeyError(f"Niche {niche_id} not found")
