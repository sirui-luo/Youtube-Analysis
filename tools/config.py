import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# YouTube search parameters
# ---------------------------------------------------------------------------
KEYWORDS = [
    "AI automation",
    "artificial intelligence",
    "ChatGPT",
    "Claude AI",
    "LLM",
    "AI agents",
    "AI tools",
    "prompt engineering",
    "AI for business",
    "machine learning",
]

MAX_RESULTS_PER_KEYWORD = 10   # YouTube search.list max 50; keep low for quota
LOOKBACK_DAYS = 7              # Only include videos published in the last N days
TRENDING_REGION_CODE = "US"
TRENDING_CATEGORY_ID = "28"    # YouTube category 28 = Science & Technology
TRENDING_MAX_RESULTS = 50

# ---------------------------------------------------------------------------
# Analysis parameters
# ---------------------------------------------------------------------------
SHORT_MAX_DURATION = 60        # Shorts: <= 60 seconds
MID_MAX_DURATION = 600         # Mid-form: <= 10 minutes; Long: > 10 minutes
TOP_N = 10                     # Top N videos/channels to surface in reports
MIN_GAP_THRESHOLD = 3          # Keywords with fewer results are flagged as gaps

# ---------------------------------------------------------------------------
# Email / output config
# ---------------------------------------------------------------------------
REPORT_RECIPIENT_EMAIL = os.getenv("REPORT_RECIPIENT_EMAIL")
REPORT_SENDER_EMAIL = os.getenv("REPORT_SENDER_EMAIL")
REPORT_EMAIL_SUBJECT = os.getenv("REPORT_EMAIL_SUBJECT", "AI YouTube Industry Report")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID") or None
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

VIDEOS_RAW_PATH = os.path.join(TMP_DIR, "videos_raw.json")
VIDEO_DETAILS_PATH = os.path.join(TMP_DIR, "video_details.json")
CHANNEL_STATS_PATH = os.path.join(TMP_DIR, "channel_stats.json")
ANALYSIS_PATH = os.path.join(TMP_DIR, "analysis.json")
SHEETS_OUTPUT_PATH = os.path.join(TMP_DIR, "sheets_output.json")

# ---------------------------------------------------------------------------
# Google OAuth scopes
# ---------------------------------------------------------------------------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
]
