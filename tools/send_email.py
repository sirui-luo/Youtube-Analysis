"""
Tool 7: send_email.py
Sends the weekly report email via Gmail API.
Non-critical: failure does not abort the pipeline.
"""

import base64
import json
import logging
import os
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


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


def build_html_body(
    presentation_url: str,
    spreadsheet_url: str,
    analysis_summary: dict,
    recommendations: list[str],
    week_str: str,
) -> str:
    total_videos = analysis_summary.get("total_videos_analyzed", 0)
    total_channels = analysis_summary.get("total_channels_found", 0)
    avg_engagement = analysis_summary.get("avg_engagement_rate", 0)
    top_topic = analysis_summary.get("top_topic", "N/A")
    date_range = analysis_summary.get("date_range", week_str)

    rec_items = "".join(f"<li>{r}</li>" for r in recommendations[:5])

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f5f5f7; margin: 0; padding: 20px; }}
    .container {{ max-width: 640px; margin: 0 auto; background: white;
                  border-radius: 12px; overflow: hidden; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }}
    .header {{ background: #16171e; padding: 32px 36px; }}
    .header h1 {{ color: white; margin: 0; font-size: 24px; font-weight: 700; }}
    .header p {{ color: #8899bb; margin: 6px 0 0; font-size: 14px; }}
    .kpis {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
             background: #eee; border-top: 1px solid #eee; }}
    .kpi {{ background: white; padding: 20px 24px; }}
    .kpi .value {{ font-size: 28px; font-weight: 700; color: #3a8ef5; }}
    .kpi .label {{ font-size: 12px; color: #888; margin-top: 2px; }}
    .body {{ padding: 28px 36px; }}
    .cta {{ display: inline-block; background: #3a8ef5; color: white; padding: 13px 28px;
            border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;
            margin: 6px 6px 6px 0; }}
    .cta.secondary {{ background: #f0f4ff; color: #3a8ef5; }}
    h2 {{ font-size: 16px; color: #1a1a2e; margin: 24px 0 10px; }}
    ul {{ padding-left: 18px; color: #444; line-height: 1.7; font-size: 14px; }}
    .footer {{ background: #f5f5f7; padding: 16px 36px; font-size: 12px; color: #999; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>AI YouTube Industry Report</h1>
      <p>Week of {week_str} &nbsp;•&nbsp; {date_range}</p>
    </div>

    <div class="kpis">
      <div class="kpi">
        <div class="value">{total_videos:,}</div>
        <div class="label">Videos Analyzed</div>
      </div>
      <div class="kpi">
        <div class="value">{total_channels:,}</div>
        <div class="label">Channels Tracked</div>
      </div>
      <div class="kpi">
        <div class="value">{avg_engagement:.1%}</div>
        <div class="label">Avg Engagement Rate</div>
      </div>
      <div class="kpi">
        <div class="value" style="font-size:18px">{top_topic.title()}</div>
        <div class="label">Top Trending Topic</div>
      </div>
    </div>

    <div class="body">
      <a href="{presentation_url}" class="cta">View Full Report (Google Slides)</a>
      <a href="{spreadsheet_url}" class="cta secondary">Raw Data (Google Sheets)</a>

      <h2>Key Recommendations This Week</h2>
      <ul>{rec_items}</ul>
    </div>

    <div class="footer">
      Automated by YouTube AI Analysis · Runs every Monday at 7 AM ·
      <a href="{spreadsheet_url}" style="color:#3a8ef5;">Data source</a>
    </div>
  </div>
</body>
</html>
"""


def send_message(gmail_service, sender: str, message_raw: str):
    encoded = base64.urlsafe_b64encode(message_raw.encode()).decode()
    gmail_service.users().messages().send(
        userId="me",
        body={"raw": encoded},
    ).execute()


def main(
    presentation_url: str = None,
    spreadsheet_url: str = None,
    analysis_summary: dict = None,
):
    # Load from files if not passed in
    if presentation_url is None:
        slides_path = os.path.join(config.TMP_DIR, "slides_output.json")
        if os.path.exists(slides_path):
            with open(slides_path) as f:
                presentation_url = json.load(f).get("presentation_url", "")

    if spreadsheet_url is None:
        if os.path.exists(config.SHEETS_OUTPUT_PATH):
            with open(config.SHEETS_OUTPUT_PATH) as f:
                spreadsheet_url = json.load(f).get("spreadsheet_url", "")

    if analysis_summary is None:
        if os.path.exists(config.ANALYSIS_PATH):
            with open(config.ANALYSIS_PATH) as f:
                data = json.load(f)
                analysis_summary = data.get("summary", {})
                recommendations = data.get("recommendations", [])
        else:
            analysis_summary = {}
            recommendations = []
    else:
        with open(config.ANALYSIS_PATH) as f:
            recommendations = json.load(f).get("recommendations", [])

    if not config.REPORT_RECIPIENT_EMAIL:
        raise ValueError("REPORT_RECIPIENT_EMAIL is not set in .env")
    if not config.REPORT_SENDER_EMAIL:
        raise ValueError("REPORT_SENDER_EMAIL is not set in .env")

    week_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"{config.REPORT_EMAIL_SUBJECT} — Week of {week_str}"

    html_body = build_html_body(
        presentation_url=presentation_url or "",
        spreadsheet_url=spreadsheet_url or "",
        analysis_summary=analysis_summary,
        recommendations=recommendations,
        week_str=week_str,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.REPORT_SENDER_EMAIL
    msg["To"] = config.REPORT_RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    creds = get_credentials()
    gmail_service = build("gmail", "v1", credentials=creds)

    try:
        send_message(gmail_service, config.REPORT_SENDER_EMAIL, msg.as_string())
        log.info(f"Email sent to {config.REPORT_RECIPIENT_EMAIL}")
        log.info(f"  Subject: {subject}")
    except HttpError as e:
        log.error(f"Gmail send failed: {e}")
        raise


if __name__ == "__main__":
    main()
