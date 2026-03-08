"""
Tool 6: create_slides.py
Builds a 10-slide Google Slides presentation using charts from Sheets.
Output: prints presentation URL, returns {presentation_id, presentation_url}
"""

import json
import logging
import os
import sys
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

# EMU constants (1 inch = 914400 EMU)
INCH = 914400
SLIDE_W = 9144000   # 10 inches
SLIDE_H = 5143500   # 5.625 inches

# Color palette
WHITE = {"red": 1, "green": 1, "blue": 1}
DARK_BG = {"red": 0.09, "green": 0.09, "blue": 0.12}
ACCENT = {"red": 0.22, "green": 0.55, "blue": 0.95}
LIGHT_GREY = {"red": 0.95, "green": 0.95, "blue": 0.97}
TEXT_DARK = {"red": 0.1, "green": 0.1, "blue": 0.1}
TEXT_MUTED = {"red": 0.45, "green": 0.45, "blue": 0.5}


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
# Slide building helpers
# ---------------------------------------------------------------------------

def emu(inches: float) -> int:
    return int(inches * INCH)


def batch_update(slides_service, presentation_id: str, requests: list):
    if not requests:
        return
    return slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()


def add_slide(slides_service, presentation_id: str, index: int) -> str:
    """Add a blank slide at position index, return slide ID."""
    result = batch_update(slides_service, presentation_id, [{
        "createSlide": {
            "insertionIndex": index,
            "slideLayoutReference": {"predefinedLayout": "BLANK"},
        }
    }])
    return result["replies"][0]["createSlide"]["objectId"]


def set_slide_bg(slide_id: str, color: dict) -> dict:
    return {
        "updatePageProperties": {
            "objectId": slide_id,
            "pageProperties": {
                "pageBackgroundFill": {
                    "solidFill": {"color": {"rgbColor": color}}
                }
            },
            "fields": "pageBackgroundFill",
        }
    }


def add_text_box(
    slide_id: str,
    text: str,
    x: float, y: float, w: float, h: float,
    font_size: float = 18,
    bold: bool = False,
    color: dict = None,
    alignment: str = "START",
    element_id: str = None,
) -> list[dict]:
    if color is None:
        color = TEXT_DARK
    obj_id = element_id or f"tb_{slide_id}_{int(x*100)}_{int(y*100)}"
    requests = [
        {
            "createShape": {
                "objectId": obj_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width": {"magnitude": emu(w), "unit": "EMU"},
                        "height": {"magnitude": emu(h), "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": emu(x), "translateY": emu(y),
                        "unit": "EMU",
                    },
                },
            }
        },
        {
            "insertText": {
                "objectId": obj_id,
                "text": text,
                "insertionIndex": 0,
            }
        },
        {
            "updateTextStyle": {
                "objectId": obj_id,
                "style": {
                    "fontSize": {"magnitude": font_size, "unit": "PT"},
                    "bold": bold,
                    "foregroundColor": {"opaqueColor": {"rgbColor": color}},
                    "fontFamily": "Google Sans",
                },
                "fields": "fontSize,bold,foregroundColor,fontFamily",
            }
        },
        {
            "updateParagraphStyle": {
                "objectId": obj_id,
                "style": {"alignment": alignment},
                "fields": "alignment",
            }
        },
    ]
    return requests


def add_shape_rect(
    slide_id: str,
    x: float, y: float, w: float, h: float,
    fill_color: dict,
    element_id: str = None,
) -> list[dict]:
    obj_id = element_id or f"rect_{slide_id}_{int(x*100)}_{int(y*100)}"
    return [
        {
            "createShape": {
                "objectId": obj_id,
                "shapeType": "RECTANGLE",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width": {"magnitude": emu(w), "unit": "EMU"},
                        "height": {"magnitude": emu(h), "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1, "scaleY": 1,
                        "translateX": emu(x), "translateY": emu(y),
                        "unit": "EMU",
                    },
                },
            }
        },
        {
            "updateShapeProperties": {
                "objectId": obj_id,
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {"color": {"rgbColor": fill_color}}
                    },
                    "outline": {"outlineFill": {"solidFill": {"alpha": 0}}},
                },
                "fields": "shapeBackgroundFill,outline",
            }
        },
    ]


def embed_sheets_chart(
    slide_id: str,
    spreadsheet_id: str,
    chart_id: int,
    x: float, y: float, w: float, h: float,
) -> dict:
    return {
        "createSheetsChart": {
            "spreadsheetId": spreadsheet_id,
            "chartId": chart_id,
            "linkingMode": "LINKED",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": emu(w), "unit": "EMU"},
                    "height": {"magnitude": emu(h), "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": emu(x), "translateY": emu(y),
                    "unit": "EMU",
                },
            },
        }
    }


# ---------------------------------------------------------------------------
# Slide builders
# ---------------------------------------------------------------------------

def build_slide_01_cover(service, pid, slide_id, analysis, week_str):
    reqs = [set_slide_bg(slide_id, DARK_BG)]
    # Accent bar
    reqs += add_shape_rect(slide_id, 0, 0, 0.15, 5.625, ACCENT, "accent_bar")
    # Title
    reqs += add_text_box(slide_id, "Fashion & Beauty\nYouTube Report",
                         0.4, 1.2, 7, 2, font_size=54, bold=True, color=WHITE, alignment="START")
    # Subtitle
    reqs += add_text_box(slide_id, f"Week of {week_str}  •  Fashion, Makeup & Beauty Niche",
                         0.4, 3.5, 8, 0.5, font_size=18, color={"red": 0.7, "green": 0.75, "blue": 0.85},
                         alignment="START")
    # Footer stat
    total = analysis["summary"]["total_videos_analyzed"]
    channels = analysis["summary"]["total_channels_found"]
    reqs += add_text_box(slide_id, f"{total} videos  •  {channels} channels analyzed",
                         0.4, 4.7, 8, 0.5, font_size=13, color={"red": 0.5, "green": 0.55, "blue": 0.65},
                         alignment="START")
    batch_update(service, pid, reqs)
    log.info("  Slide 1: Cover")


def build_slide_02_exec_summary(service, pid, slide_id, analysis):
    s = analysis["summary"]
    reqs = [set_slide_bg(slide_id, LIGHT_GREY)]
    reqs += add_text_box(slide_id, "Executive Summary", 0.4, 0.2, 9.2, 0.7,
                         font_size=28, bold=True, color=TEXT_DARK)
    reqs += add_shape_rect(slide_id, 0.4, 0.85, 9.2, 0.05, ACCENT)

    kpis = [
        ("Videos Analyzed", f"{s['total_videos_analyzed']:,}"),
        ("Channels Found", f"{s['total_channels_found']:,}"),
        ("Avg Engagement", f"{s['avg_engagement_rate']:.1%}"),
        ("Top Topic", s['top_topic'].title()),
    ]
    for i, (label, value) in enumerate(kpis):
        col = i % 2
        row = i // 2
        bx = 0.4 + col * 4.7
        by = 1.2 + row * 1.8
        reqs += add_shape_rect(slide_id, bx, by, 4.3, 1.5, WHITE, f"kpi_bg_{i}")
        reqs += add_text_box(slide_id, value, bx + 0.2, by + 0.15, 3.9, 0.8,
                             font_size=32, bold=True, color=ACCENT)
        reqs += add_text_box(slide_id, label, bx + 0.2, by + 1.0, 3.9, 0.4,
                             font_size=13, color=TEXT_MUTED)

    reqs += add_text_box(slide_id, f"Date range: {s['date_range']}",
                         0.4, 4.8, 9.2, 0.4, font_size=11, color=TEXT_MUTED)
    batch_update(service, pid, reqs)
    log.info("  Slide 2: Executive Summary")


def build_slide_03_top_videos(service, pid, slide_id, analysis):
    videos = analysis.get("top_videos_by_views", [])[:7]
    reqs = [set_slide_bg(slide_id, WHITE)]
    reqs += add_shape_rect(slide_id, 0, 0, 10, 0.9, DARK_BG)
    reqs += add_text_box(slide_id, "Top Trending Fashion & Beauty Videos This Week",
                         0.3, 0.1, 9.4, 0.7, font_size=24, bold=True, color=WHITE)
    reqs += add_text_box(slide_id, "Ranked by view count",
                         7.5, 0.25, 2, 0.4, font_size=11, color={"red": 0.6, "green": 0.65, "blue": 0.75})

    for i, v in enumerate(videos):
        y = 1.0 + i * 0.6
        # Row bg (alternating)
        if i % 2 == 0:
            reqs += add_shape_rect(slide_id, 0.2, y, 9.6, 0.55, LIGHT_GREY, f"row_bg_{i}")
        views_str = f"{v['view_count']:,}"
        eng_str = f"{v['engagement_rate']:.1%}"
        reqs += add_text_box(slide_id, f"{i+1}.", 0.25, y + 0.05, 0.4, 0.45,
                             font_size=12, bold=True, color=ACCENT)
        reqs += add_text_box(slide_id, v["title"][:65], 0.65, y + 0.05, 5.8, 0.45,
                             font_size=11, color=TEXT_DARK)
        reqs += add_text_box(slide_id, v["channel_title"][:30], 6.45, y + 0.05, 1.8, 0.45,
                             font_size=10, color=TEXT_MUTED)
        reqs += add_text_box(slide_id, views_str, 8.25, y + 0.05, 1.0, 0.45,
                             font_size=11, bold=True, color=TEXT_DARK, alignment="END")
        reqs += add_text_box(slide_id, eng_str, 9.25, y + 0.05, 0.7, 0.45,
                             font_size=10, color=ACCENT, alignment="END")

    # Header row
    reqs += add_text_box(slide_id, "Title", 0.65, 0.9, 5.8, 0.4, font_size=10,
                         bold=True, color=TEXT_MUTED)
    reqs += add_text_box(slide_id, "Channel", 6.45, 0.9, 1.8, 0.4, font_size=10,
                         bold=True, color=TEXT_MUTED)
    reqs += add_text_box(slide_id, "Views", 8.25, 0.9, 1.0, 0.4, font_size=10,
                         bold=True, color=TEXT_MUTED, alignment="END")
    reqs += add_text_box(slide_id, "Eng.", 9.25, 0.9, 0.7, 0.4, font_size=10,
                         bold=True, color=TEXT_MUTED, alignment="END")

    batch_update(service, pid, reqs)
    log.info("  Slide 3: Top Videos")


def build_chart_slide(service, pid, slide_id, title, subtitle,
                      spreadsheet_id, chart_id, bg=LIGHT_GREY):
    reqs = [set_slide_bg(slide_id, bg)]
    reqs += add_shape_rect(slide_id, 0, 0, 10, 0.9, DARK_BG)
    reqs += add_text_box(slide_id, title, 0.3, 0.1, 8, 0.7, font_size=24,
                         bold=True, color=WHITE)
    reqs += add_text_box(slide_id, subtitle, 0.3, 0.9, 9.4, 0.4, font_size=12,
                         color=TEXT_MUTED)
    batch_update(service, pid, reqs)

    if chart_id is not None:
        try:
            batch_update(service, pid, [
                embed_sheets_chart(slide_id, spreadsheet_id, chart_id,
                                   x=0.3, y=1.35, w=9.4, h=4.15)
            ])
            log.info(f"  Chart embedded (chart_id={chart_id})")
        except HttpError as e:
            log.warning(f"  Could not embed chart {chart_id}: {e}")
            reqs2 = add_text_box(slide_id, "[Chart could not be loaded — open Google Sheets for data]",
                                 0.5, 2.5, 9, 1, font_size=16, color=TEXT_MUTED, alignment="CENTER")
            batch_update(service, pid, reqs2)
    else:
        reqs2 = add_text_box(slide_id, "[Chart not available — check Sheets for data]",
                             0.5, 2.5, 9, 1, font_size=16, color=TEXT_MUTED, alignment="CENTER")
        batch_update(service, pid, reqs2)


def build_slide_09_opportunities(service, pid, slide_id, analysis):
    gaps = analysis.get("content_gaps", [])
    reqs = [set_slide_bg(slide_id, WHITE)]
    reqs += add_shape_rect(slide_id, 0, 0, 10, 0.9, DARK_BG)
    reqs += add_text_box(slide_id, "Content Opportunities", 0.3, 0.1, 9.4, 0.7,
                         font_size=24, bold=True, color=WHITE)
    reqs += add_text_box(slide_id, "Keywords with fewer than 3 videos this week = low competition topics",
                         0.3, 0.9, 9.4, 0.4, font_size=12, color=TEXT_MUTED)

    if gaps:
        for i, gap in enumerate(gaps):
            y = 1.45 + i * 0.65
            reqs += add_shape_rect(slide_id, 0.3, y, 0.5, 0.45, ACCENT, f"dot_{i}")
            reqs += add_text_box(slide_id, gap.title(), 0.95, y + 0.04, 8.5, 0.45,
                                 font_size=15, color=TEXT_DARK)
    else:
        reqs += add_text_box(slide_id, "All tracked keywords have good coverage this week.",
                             0.5, 2.5, 9, 0.6, font_size=16, color=TEXT_MUTED, alignment="CENTER")

    batch_update(service, pid, reqs)
    log.info("  Slide 9: Content Opportunities")


def build_slide_10_recommendations(service, pid, slide_id, analysis):
    recs = analysis.get("recommendations", [])
    reqs = [set_slide_bg(slide_id, DARK_BG)]
    reqs += add_shape_rect(slide_id, 0, 0, 0.15, 5.625, ACCENT, "left_bar")
    reqs += add_text_box(slide_id, "Recommendations for Your Channel",
                         0.4, 0.15, 9.2, 0.7, font_size=24, bold=True, color=WHITE)
    reqs += add_text_box(slide_id, "Based on this week's fashion & beauty niche analysis",
                         0.4, 0.8, 9.2, 0.4, font_size=13,
                         color={"red": 0.55, "green": 0.6, "blue": 0.7})

    for i, rec in enumerate(recs[:5]):
        y = 1.3 + i * 0.78
        reqs += add_text_box(slide_id, f"{i + 1}", 0.4, y, 0.45, 0.55,
                             font_size=20, bold=True, color=ACCENT, alignment="CENTER")
        reqs += add_text_box(slide_id, rec, 1.0, y + 0.04, 8.6, 0.65,
                             font_size=13, color=WHITE)

    batch_update(service, pid, reqs)
    log.info("  Slide 10: Recommendations")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(spreadsheet_id: str = None, chart_ids: dict = None):
    for path in [config.ANALYSIS_PATH, config.SHEETS_OUTPUT_PATH]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing {path} — run write_to_sheets.py first"
            )

    with open(config.ANALYSIS_PATH) as f:
        analysis = json.load(f)
    with open(config.SHEETS_OUTPUT_PATH) as f:
        sheets_out = json.load(f)

    if spreadsheet_id is None:
        spreadsheet_id = sheets_out["spreadsheet_id"]
    if chart_ids is None:
        chart_ids = sheets_out.get("chart_ids", {})

    creds = get_credentials()
    slides_service = build("slides", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Delete previous presentation if one exists
    slides_output_path = os.path.join(config.TMP_DIR, "slides_output.json")
    if os.path.exists(slides_output_path):
        with open(slides_output_path) as f:
            prev = json.load(f)
        prev_id = prev.get("presentation_id")
        if prev_id:
            try:
                drive_service.files().delete(fileId=prev_id).execute()
                log.info(f"Deleted previous presentation: {prev_id}")
            except HttpError as e:
                log.warning(f"Could not delete previous presentation {prev_id}: {e}")

    week_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    pres_title = f"Fashion & Beauty YouTube Report — Week of {week_str}"

    log.info(f"Creating presentation: '{pres_title}'")
    presentation = slides_service.presentations().create(
        body={"title": pres_title}
    ).execute()
    pid = presentation["presentationId"]

    # Delete the default blank slide
    default_slide_id = presentation["slides"][0]["objectId"]

    # Add all 10 slides (they'll be inserted at indices 0-9 after deleting default)
    slide_ids = []
    for i in range(10):
        sid = add_slide(slides_service, pid, i)
        slide_ids.append(sid)

    # Delete the original default slide (now at index 10)
    batch_update(slides_service, pid, [{"deleteObject": {"objectId": default_slide_id}}])

    log.info("Building slides...")
    build_slide_01_cover(slides_service, pid, slide_ids[0], analysis, week_str)
    build_slide_02_exec_summary(slides_service, pid, slide_ids[1], analysis)
    build_slide_03_top_videos(slides_service, pid, slide_ids[2], analysis)

    build_chart_slide(slides_service, pid, slide_ids[3],
                      "Trending Topics & Keywords",
                      "Most frequently mentioned terms in fashion & beauty video titles this week",
                      spreadsheet_id, chart_ids.get("keywords_bar"))

    build_chart_slide(slides_service, pid, slide_ids[4],
                      "Top Channels in Fashion & Beauty Niche",
                      "Ranked by total channel view count",
                      spreadsheet_id, chart_ids.get("channels_bar"))

    build_chart_slide(slides_service, pid, slide_ids[5],
                      "Engagement Rate Analysis",
                      "Top videos by (likes + comments) / views",
                      spreadsheet_id, chart_ids.get("engagement_bar"))

    build_chart_slide(slides_service, pid, slide_ids[6],
                      "Content Format Breakdown",
                      "Distribution of Shorts vs mid-form vs long-form fashion & beauty content",
                      spreadsheet_id, chart_ids.get("format_pie"))

    build_chart_slide(slides_service, pid, slide_ids[7],
                      "Upload Timing Patterns",
                      "Average views by day of week for fashion & beauty content",
                      spreadsheet_id, chart_ids.get("timing_bar"))

    build_slide_09_opportunities(slides_service, pid, slide_ids[8], analysis)
    build_slide_10_recommendations(slides_service, pid, slide_ids[9], analysis)

    # Move to Drive folder if configured
    if config.GOOGLE_DRIVE_FOLDER_ID:
        try:
            drive_service.files().update(
                fileId=pid,
                addParents=config.GOOGLE_DRIVE_FOLDER_ID,
                removeParents="root",
                fields="id, parents",
            ).execute()
            log.info(f"Moved presentation to Drive folder {config.GOOGLE_DRIVE_FOLDER_ID}")
        except HttpError as e:
            log.warning(f"Could not move to Drive folder: {e}")

    presentation_url = f"https://docs.google.com/presentation/d/{pid}/edit"
    log.info(f"Presentation complete: {presentation_url}")
    print(f"\nPresentation URL: {presentation_url}\n")

    result = {"presentation_id": pid, "presentation_url": presentation_url}

    # Save for use by send_email.py
    slides_output_path = os.path.join(config.TMP_DIR, "slides_output.json")
    with open(slides_output_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    main()
