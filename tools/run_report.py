"""
Tool 8: run_report.py — Master Orchestrator
Runs the full weekly YouTube AI report pipeline in sequence.
Usage:
  python3 tools/run_report.py           # normal run
  python3 tools/run_report.py --reauth  # force re-authentication
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import search_youtube
import fetch_video_details
import fetch_channel_stats
import analyze_trends
import write_to_sheets
import create_slides
import send_email
import fetch_video_comments
import write_to_notion


def setup_logging():
    os.makedirs(config.TMP_DIR, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = os.path.join(config.TMP_DIR, f"run_log_{today}.txt")

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return logging.getLogger("run_report"), log_path


def run_step(log, step_name: str, func, *args, **kwargs):
    log.info(f"{'='*60}")
    log.info(f"STEP: {step_name}")
    log.info(f"{'='*60}")
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = round(time.time() - start, 1)
    log.info(f"  ✓ {step_name} completed in {elapsed}s")
    return result


def handle_reauth():
    if os.path.exists(config.TOKEN_PATH):
        os.remove(config.TOKEN_PATH)
        print(f"Removed {config.TOKEN_PATH} — OAuth flow will re-run on next API call")
    else:
        print("No token.json found — OAuth will run fresh on first API call")


def main():
    parser = argparse.ArgumentParser(description="Run the weekly YouTube AI report pipeline")
    parser.add_argument("--reauth", action="store_true",
                        help="Force re-authentication by deleting token.json")
    args = parser.parse_args()

    if args.reauth:
        handle_reauth()

    log, log_path = setup_logging()

    log.info("")
    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║       Weekly YouTube AI Industry Report              ║")
    log.info(f"║       {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}                            ║")
    log.info("╚══════════════════════════════════════════════════════╝")
    log.info("")

    # Validate required config
    if not config.YOUTUBE_API_KEY:
        log.error("YOUTUBE_API_KEY is not set in .env — aborting")
        sys.exit(1)

    total_start = time.time()

    # ── Critical steps (abort on failure) ───────────────────────────────
    try:
        run_step(log, "1. Search YouTube", search_youtube.main)
    except Exception as e:
        log.error(f"Step 1 failed: {e}", exc_info=True)
        sys.exit(1)

    try:
        run_step(log, "2. Fetch Video Details", fetch_video_details.main)
    except Exception as e:
        log.error(f"Step 2 failed: {e}", exc_info=True)
        sys.exit(1)

    try:
        run_step(log, "3. Fetch Channel Stats", fetch_channel_stats.main)
    except Exception as e:
        log.error(f"Step 3 failed: {e}", exc_info=True)
        sys.exit(1)

    try:
        run_step(log, "4. Analyze Trends", analyze_trends.main)
    except Exception as e:
        log.error(f"Step 4 failed: {e}", exc_info=True)
        sys.exit(1)

    try:
        sheets_result = run_step(log, "5. Write to Google Sheets", write_to_sheets.main)
    except Exception as e:
        log.error(f"Step 5 failed: {e}", exc_info=True)
        sys.exit(1)

    try:
        run_step(log, "5b. Fetch Video Comments", fetch_video_comments.main)
    except Exception as e:
        log.error(f"Step 5b failed: {e}", exc_info=True)
        sys.exit(1)

    try:
        slides_result = run_step(
            log, "6. Create Google Slides", create_slides.main,
            spreadsheet_id=sheets_result["spreadsheet_id"],
            chart_ids=sheets_result["chart_ids"],
        )
    except Exception as e:
        log.error(f"Step 6 failed: {e}", exc_info=True)
        sys.exit(1)

    # ── Non-critical step (log failure, don't abort) ─────────────────────
    try:
        with open(config.ANALYSIS_PATH) as f:
            analysis_data = json.load(f)
        run_step(
            log, "7. Send Email", send_email.main,
            presentation_url=slides_result["presentation_url"],
            spreadsheet_url=sheets_result["spreadsheet_url"],
            analysis_summary=analysis_data["summary"],
        )
    except Exception as e:
        log.warning(f"Step 7 (email) failed — report still available via URLs below: {e}")

    try:
        run_step(log, "8. Write to Notion", write_to_notion.main)
    except Exception as e:
        log.warning(f"Step 8 (Notion) failed — check NOTION_API_KEY and NOTION_DATABASE_ID in .env: {e}")

    total_elapsed = round(time.time() - total_start, 1)

    log.info("")
    log.info("╔══════════════════════════════════════════════════════╗")
    log.info("║   REPORT COMPLETE                                    ║")
    log.info("╚══════════════════════════════════════════════════════╝")
    log.info(f"  Total time: {total_elapsed}s")
    log.info(f"  Slides:     {slides_result['presentation_url']}")
    log.info(f"  Sheets:     {sheets_result['spreadsheet_url']}")
    log.info(f"  Log file:   {log_path}")
    log.info("")


if __name__ == "__main__":
    main()
