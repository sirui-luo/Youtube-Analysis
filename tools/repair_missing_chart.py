"""
Tool: repair_missing_chart.py
Adds missing charts from sheets_output.json (where chart_id is null) to
the existing spreadsheet. Updates sheets_output.json in place.
Run this when write_to_sheets.py chart creation fails, then re-run create_slides.py.
"""

import json
import logging
import os
import sys
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from write_to_sheets import (
    get_credentials,
    populate_timing,
    populate_keywords,
    populate_channels,
    populate_engagement,
    populate_format,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CHART_REPAIRERS = {
    "timing_bar": populate_timing,
    "keywords_bar": populate_keywords,
    "channels_bar": populate_channels,
    "engagement_bar": populate_engagement,
    "format_pie": populate_format,
}


def main():
    if not os.path.exists(config.SHEETS_OUTPUT_PATH):
        raise FileNotFoundError(f"Missing {config.SHEETS_OUTPUT_PATH}")
    if not os.path.exists(config.ANALYSIS_PATH):
        raise FileNotFoundError(f"Missing {config.ANALYSIS_PATH}")

    with open(config.SHEETS_OUTPUT_PATH) as f:
        sheets_out = json.load(f)
    with open(config.ANALYSIS_PATH) as f:
        analysis = json.load(f)

    spreadsheet_id = sheets_out["spreadsheet_id"]
    sheet_ids = sheets_out["sheet_ids"]
    chart_ids = sheets_out["chart_ids"]

    missing = {k: v for k, v in chart_ids.items() if v is None}
    if not missing:
        log.info("No missing charts — nothing to repair.")
        return sheets_out

    log.info(f"Missing charts: {list(missing.keys())}")

    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    tab_map = {
        "timing_bar": "Timing",
        "keywords_bar": "Keywords",
        "channels_bar": "Channels",
        "engagement_bar": "Engagement",
        "format_pie": "Format",
    }

    for chart_key in missing:
        tab_name = tab_map[chart_key]
        sheet_id = sheet_ids[tab_name]
        repairer = CHART_REPAIRERS[chart_key]
        log.info(f"Repairing {chart_key} on tab '{tab_name}' (sheet_id={sheet_id})...")
        time.sleep(2)
        try:
            new_chart_id = repairer(service, spreadsheet_id, sheet_id, analysis)
            if new_chart_id is not None:
                chart_ids[chart_key] = new_chart_id
                log.info(f"  {chart_key} repaired: chart_id={new_chart_id}")
            else:
                log.warning(f"  {chart_key} still failed — chart ID is still null")
        except Exception as e:
            log.error(f"  {chart_key} repair failed: {e}")

    sheets_out["chart_ids"] = chart_ids
    with open(config.SHEETS_OUTPUT_PATH, "w") as f:
        json.dump(sheets_out, f, indent=2)

    log.info(f"sheets_output.json updated: {config.SHEETS_OUTPUT_PATH}")
    print(f"\nRepaired chart_ids: {json.dumps(chart_ids, indent=2)}\n")
    return sheets_out


if __name__ == "__main__":
    main()
