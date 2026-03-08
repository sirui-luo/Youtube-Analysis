"""
Tool 5: write_to_sheets.py
Creates a Google Spreadsheet with data + 5 embedded charts.
Output: .tmp/sheets_output.json (contains spreadsheet_id, chart_ids)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_credentials():
    creds = None
    if os.path.exists(config.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.TOKEN_PATH, config.GOOGLE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Missing {config.CREDENTIALS_PATH} — download from Google Cloud Console"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CREDENTIALS_PATH, config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


# ---------------------------------------------------------------------------
# Sheets helpers
# ---------------------------------------------------------------------------

def create_spreadsheet(service, title: str) -> dict:
    body = {
        "properties": {"title": title},
        "sheets": [
            {"properties": {"title": tab, "index": i}}
            for i, tab in enumerate([
                "Top Videos", "Keywords", "Channels", "Engagement", "Format", "Timing"
            ])
        ],
    }
    result = service.spreadsheets().create(body=body).execute()
    return result


def get_sheet_id(spreadsheet: dict, sheet_title: str) -> int:
    for sheet in spreadsheet.get("sheets", []):
        if sheet["properties"]["title"] == sheet_title:
            return sheet["properties"]["sheetId"]
    raise ValueError(f"Sheet '{sheet_title}' not found")


def write_rows(service, spreadsheet_id: str, range_name: str, values: list[list], formula: bool = False):
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED" if formula else "RAW",
        body={"values": values},
    ).execute()


def add_chart(service, spreadsheet_id: str, chart_spec: dict) -> int:
    """Add a chart via batchUpdate. Returns chart ID."""
    result = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addChart": {"chart": chart_spec}}]},
    ).execute()
    return result["replies"][0]["addChart"]["chart"]["chartId"]


def make_bar_chart(
    sheet_id: int,
    title: str,
    data_range_sheet_id: int,
    header_row: int,
    data_start_row: int,
    data_end_row: int,
    label_col: int,
    value_col: int,
    anchor_row: int,
    anchor_col: int,
    bar_direction: str = "HORIZONTAL",
) -> dict:
    return {
        "spec": {
            "title": title,
            "basicChart": {
                "chartType": "BAR" if bar_direction == "HORIZONTAL" else "COLUMN",
                "legendPosition": "NO_LEGEND",
                "axis": [
                    {"position": "BOTTOM_AXIS", "title": ""},
                    {"position": "LEFT_AXIS", "title": ""},
                ],
                "domains": [{
                    "domain": {
                        "sourceRange": {
                            "sources": [{
                                "sheetId": data_range_sheet_id,
                                "startRowIndex": data_start_row,
                                "endRowIndex": data_end_row,
                                "startColumnIndex": label_col,
                                "endColumnIndex": label_col + 1,
                            }]
                        }
                    }
                }],
                "series": [{
                    "series": {
                        "sourceRange": {
                            "sources": [{
                                "sheetId": data_range_sheet_id,
                                "startRowIndex": data_start_row,
                                "endRowIndex": data_end_row,
                                "startColumnIndex": value_col,
                                "endColumnIndex": value_col + 1,
                            }]
                        }
                    },
                    "targetAxis": "LEFT_AXIS" if bar_direction == "COLUMN" else "BOTTOM_AXIS",
                }],
            },
        },
        "position": {
            "overlayPosition": {
                "anchorCell": {
                    "sheetId": sheet_id,
                    "rowIndex": anchor_row,
                    "columnIndex": anchor_col,
                },
                "widthPixels": 600,
                "heightPixels": 371,
            }
        },
    }


def make_pie_chart(
    sheet_id: int,
    title: str,
    data_range_sheet_id: int,
    data_start_row: int,
    data_end_row: int,
    label_col: int,
    value_col: int,
    anchor_row: int,
    anchor_col: int,
) -> dict:
    return {
        "spec": {
            "title": title,
            "pieChart": {
                "legendPosition": "RIGHT_LEGEND",
                "pieHole": 0.4,
                "domain": {
                    "sourceRange": {
                        "sources": [{
                            "sheetId": data_range_sheet_id,
                            "startRowIndex": data_start_row,
                            "endRowIndex": data_end_row,
                            "startColumnIndex": label_col,
                            "endColumnIndex": label_col + 1,
                        }]
                    }
                },
                "series": {
                    "sourceRange": {
                        "sources": [{
                            "sheetId": data_range_sheet_id,
                            "startRowIndex": data_start_row,
                            "endRowIndex": data_end_row,
                            "startColumnIndex": value_col,
                            "endColumnIndex": value_col + 1,
                        }]
                    }
                },
            },
        },
        "position": {
            "overlayPosition": {
                "anchorCell": {
                    "sheetId": sheet_id,
                    "rowIndex": anchor_row,
                    "columnIndex": anchor_col,
                },
                "widthPixels": 500,
                "heightPixels": 371,
            }
        },
    }


# ---------------------------------------------------------------------------
# Tab population
# ---------------------------------------------------------------------------

def populate_top_videos(service, spreadsheet_id, sheet_id, analysis):
    rows = [["Title", "Channel", "Views", "Engagement Rate", "Format", "Published"]]
    for v in analysis.get("top_videos_by_views", []):
        video_url = f"https://www.youtube.com/watch?v={v['video_id']}"
        channel_url = f"https://www.youtube.com/channel/{v.get('channel_id', '')}"
        rows.append([
            f'=HYPERLINK("{video_url}", "{v["title"].replace(chr(34), chr(39))}")',
            f'=HYPERLINK("{channel_url}", "{v["channel_title"].replace(chr(34), chr(39))}")',
            v["view_count"],
            v["engagement_rate"],
            v["format"],
            v["published_at"][:10],
        ])
    write_rows(service, spreadsheet_id, "Top Videos!A1", rows, formula=True)
    log.info("  Top Videos tab written")


def populate_keywords(service, spreadsheet_id, sheet_id, analysis) -> int:
    kws = analysis.get("trending_keywords", [])[:15]
    rows = [["Keyword / Topic", "Mentions in Titles"]]
    for k in kws:
        rows.append([k["term"], k["count"]])
    write_rows(service, spreadsheet_id, "Keywords!A1", rows)

    chart_id = None
    try:
        chart_spec = make_bar_chart(
            sheet_id=sheet_id,
            title="Trending Topics This Week",
            data_range_sheet_id=sheet_id,
            header_row=0,
            data_start_row=1,
            data_end_row=len(rows),
            label_col=0,
            value_col=1,
            anchor_row=0,
            anchor_col=3,
        )
        chart_id = add_chart(service, spreadsheet_id, chart_spec)
        log.info(f"  Keywords bar chart created (id={chart_id})")
    except HttpError as e:
        log.warning(f"  Keywords chart failed: {e}")

    return chart_id


def populate_channels(service, spreadsheet_id, sheet_id, analysis) -> int:
    channels = analysis.get("top_channels", [])[:10]
    rows = [["Channel", "Total Views", "Subscribers", "Videos This Week"]]
    for c in channels:
        rows.append([
            c["channel_name"],
            c["total_views"],
            c["subscriber_count"] if c["subscriber_count"] is not None else "Hidden",
            c["videos_this_week"],
        ])
    write_rows(service, spreadsheet_id, "Channels!A1", rows)

    chart_id = None
    try:
        chart_spec = make_bar_chart(
            sheet_id=sheet_id,
            title="Top Channels by Total Views",
            data_range_sheet_id=sheet_id,
            header_row=0,
            data_start_row=1,
            data_end_row=len(rows),
            label_col=0,
            value_col=1,
            anchor_row=0,
            anchor_col=5,
            bar_direction="HORIZONTAL",
        )
        chart_id = add_chart(service, spreadsheet_id, chart_spec)
        log.info(f"  Channels bar chart created (id={chart_id})")
    except HttpError as e:
        log.warning(f"  Channels chart failed: {e}")

    return chart_id


def populate_engagement(service, spreadsheet_id, sheet_id, analysis) -> int:
    videos = analysis.get("top_videos_by_engagement", [])[:10]
    rows = [["Video Title (truncated)", "Engagement Rate (%)"]]
    for v in videos:
        rows.append([
            v["title"][:50],
            round(v["engagement_rate"] * 100, 2),
        ])
    write_rows(service, spreadsheet_id, "Engagement!A1", rows)

    chart_id = None
    try:
        chart_spec = make_bar_chart(
            sheet_id=sheet_id,
            title="Top Videos by Engagement Rate",
            data_range_sheet_id=sheet_id,
            header_row=0,
            data_start_row=1,
            data_end_row=len(rows),
            label_col=0,
            value_col=1,
            anchor_row=0,
            anchor_col=3,
            bar_direction="HORIZONTAL",
        )
        chart_id = add_chart(service, spreadsheet_id, chart_spec)
        log.info(f"  Engagement bar chart created (id={chart_id})")
    except HttpError as e:
        log.warning(f"  Engagement chart failed: {e}")

    return chart_id


def populate_format(service, spreadsheet_id, sheet_id, analysis) -> int:
    fmt = analysis.get("format_breakdown", {})
    label_map = {"short": "Shorts (≤60s)", "mid": "Mid-form (1–10 min)", "long": "Long-form (>10 min)"}
    rows = [["Format", "Video Count"]]
    for key, label in label_map.items():
        count = fmt.get(key, {}).get("count", 0)
        if count > 0:
            rows.append([label, count])
    write_rows(service, spreadsheet_id, "Format!A1", rows)

    chart_id = None
    try:
        chart_spec = make_pie_chart(
            sheet_id=sheet_id,
            title="Content Format Breakdown",
            data_range_sheet_id=sheet_id,
            data_start_row=1,
            data_end_row=len(rows),
            label_col=0,
            value_col=1,
            anchor_row=0,
            anchor_col=3,
        )
        chart_id = add_chart(service, spreadsheet_id, chart_spec)
        log.info(f"  Format pie chart created (id={chart_id})")
    except HttpError as e:
        log.warning(f"  Format chart failed: {e}")

    return chart_id


def populate_timing(service, spreadsheet_id, sheet_id, analysis) -> int:
    timing = analysis.get("upload_timing", {})
    day_avgs = timing.get("day_avg_views", {})
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rows = [["Day", "Avg Views"]]
    for day in day_order:
        rows.append([day, day_avgs.get(day, 0)])
    write_rows(service, spreadsheet_id, "Timing!A1", rows)

    chart_id = None
    try:
        chart_spec = make_bar_chart(
            sheet_id=sheet_id,
            title="Avg Views by Upload Day",
            data_range_sheet_id=sheet_id,
            header_row=0,
            data_start_row=1,
            data_end_row=len(rows),
            label_col=0,
            value_col=1,
            anchor_row=0,
            anchor_col=3,
            bar_direction="COLUMN",
        )
        chart_id = add_chart(service, spreadsheet_id, chart_spec)
        log.info(f"  Timing column chart created (id={chart_id})")
    except HttpError as e:
        log.warning(f"  Timing chart failed: {e}")

    return chart_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(config.ANALYSIS_PATH):
        raise FileNotFoundError(
            f"Missing {config.ANALYSIS_PATH} — run analyze_trends.py first"
        )

    with open(config.ANALYSIS_PATH) as f:
        analysis = json.load(f)

    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    week_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"Fashion & Beauty YouTube Report — Week of {week_str}"

    log.info(f"Creating spreadsheet: '{title}'")
    spreadsheet = create_spreadsheet(service, title)
    spreadsheet_id = spreadsheet["spreadsheetId"]
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    log.info(f"Spreadsheet created: {spreadsheet_url}")

    # Get sheet IDs for each tab
    sheet_ids = {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in spreadsheet.get("sheets", [])
    }

    # Populate each tab (small sleep between chart requests to avoid rate limits)
    populate_top_videos(service, spreadsheet_id, sheet_ids["Top Videos"], analysis)
    time.sleep(1)
    kw_chart_id = populate_keywords(service, spreadsheet_id, sheet_ids["Keywords"], analysis)
    time.sleep(1)
    ch_chart_id = populate_channels(service, spreadsheet_id, sheet_ids["Channels"], analysis)
    time.sleep(1)
    eng_chart_id = populate_engagement(service, spreadsheet_id, sheet_ids["Engagement"], analysis)
    time.sleep(1)
    fmt_chart_id = populate_format(service, spreadsheet_id, sheet_ids["Format"], analysis)
    time.sleep(1)
    tim_chart_id = populate_timing(service, spreadsheet_id, sheet_ids["Timing"], analysis)

    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": spreadsheet_url,
        "sheet_ids": sheet_ids,
        "chart_ids": {
            "keywords_bar": kw_chart_id,
            "channels_bar": ch_chart_id,
            "engagement_bar": eng_chart_id,
            "format_pie": fmt_chart_id,
            "timing_bar": tim_chart_id,
        },
    }

    with open(config.SHEETS_OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Sheets output saved to {config.SHEETS_OUTPUT_PATH}")
    print(f"\nSpreadsheet URL: {spreadsheet_url}\n")
    return output


if __name__ == "__main__":
    main()
