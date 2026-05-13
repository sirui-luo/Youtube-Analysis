import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# YouTube search parameters
# ---------------------------------------------------------------------------
KEYWORDS = [
    "quiet luxury outfit",
    "capsule wardrobe women",
    "minimalist fashion outfit",
    "clean girl aesthetic outfit",
    "old money aesthetic fashion",
    "outfit of the day women",
    "affordable luxury fashion",
    "get ready with me aesthetic",
    "spring outfit ideas women 2025",
    "natural makeup tutorial women",
    "everyday makeup look",
    "female lifestyle vlog",
    "feminine style inspiration",
    "french girl style outfit",
    "elevated basics outfit",
]

# Seed channels: well-known creators in this niche.
# Use YouTube channel handles (the @name part of their URL).
# The tool will resolve these to channel IDs and fetch their recent uploads.
SEED_CHANNEL_HANDLES = [
    # --- Channels you follow ---
    "via li",               # minimalist fashion / lifestyle
    "mai pham",             # fashion / female lifestyle

    # --- Quiet luxury / old money / elevated basics ---
    "bliss foster",         # quiet luxury, old money aesthetic
    "lydia elise millen",   # luxury fashion & lifestyle
    "tamara kalinic",       # elevated fashion / luxury lifestyle
    "stephanie sterjovski", # capsule wardrobe, elevated basics

    # --- Minimalist / clean girl aesthetic ---
    "jenny mustard",        # minimalist lifestyle & fashion
    "rachel nguyen",        # minimalist fashion / slow living
    "adenorah",             # French girl style, minimalist

    # --- Natural makeup / beauty / GRWM ---
    "hindash",              # natural / editorial makeup tutorials
    "beauty within",        # skincare & natural beauty

    # --- Female lifestyle vlog / outfit of the day ---
    "clothesencounters",    # Jenn Im — fashion / lifestyle vlog
    "bestdressed",          # Ashley — fashion / thrifting / lifestyle
    "elana jadallah",       # lifestyle & fashion
]

# Title blocklist: videos whose titles contain any of these terms are discarded.
TITLE_BLOCKLIST = [
    "gaming", "minecraft", "fortnite", "cooking", "recipe", "baking",
    "workout", "gym", "fitness", "bodybuilding", "weight loss",
    "sports", "football", "basketball", "soccer",
    "tech review", "unboxing tech", "iphone", "android",
    "baby", "pregnancy", "kids", "children", "prank",
    "horror", "scary", "asmr", "mukbang",
]

MAX_RESULTS_PER_KEYWORD = 10   # YouTube search.list max 50; keep low for quota
MAX_RESULTS_PER_SEED_CHANNEL = 10  # Recent videos to fetch per seed channel
LOOKBACK_DAYS = 7              # Only include videos published in the last N days
TRENDING_REGION_CODE = "US"
TRENDING_CATEGORY_ID = "26"    # YouTube category 26 = Howto & Style (disabled — too noisy)
TRENDING_MAX_RESULTS = 50

# ---------------------------------------------------------------------------
# Analysis parameters
# ---------------------------------------------------------------------------
SHORT_MAX_DURATION = 60        # Shorts: <= 60 seconds
MID_MAX_DURATION = 600         # Mid-form: <= 10 minutes; Long: > 10 minutes
TOP_N = 10                     # Top N videos/channels to surface in reports
MIN_GAP_THRESHOLD = 3          # Keywords with fewer results are flagged as gaps
MIN_DURATION_FOR_TOP = 300     # Only surface videos longer than this (seconds) in top lists

# ---------------------------------------------------------------------------
# Email / output config
# ---------------------------------------------------------------------------
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
TOP_N_DEEP = 10           # Videos to fetch comments + push to Notion

REPORT_RECIPIENT_EMAIL = os.getenv("REPORT_RECIPIENT_EMAIL")
REPORT_SENDER_EMAIL = os.getenv("REPORT_SENDER_EMAIL")
REPORT_EMAIL_SUBJECT = os.getenv("REPORT_EMAIL_SUBJECT", "Fashion & Beauty YouTube Industry Report")
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
VIDEO_COMMENTS_PATH = os.path.join(TMP_DIR, "video_comments.json")

# ---------------------------------------------------------------------------
# Google OAuth scopes
# ---------------------------------------------------------------------------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
]
