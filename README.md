# YouTube Analysis

https://private-user-images.githubusercontent.com/209253223/593567447-ca843045-d4ec-4031-9808-82a6ca3e4e41.MOV?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Nzg5NTI2OTgsIm5iZiI6MTc3ODk1MjM5OCwicGF0aCI6Ii8yMDkyNTMyMjMvNTkzNTY3NDQ3LWNhODQzMDQ1LWQ0ZWMtNDAzMS05ODA4LTgyYTZjYTNlNGU0MS5NT1Y_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjYwNTE2JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI2MDUxNlQxNzI2MzhaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT0wMjc5NTZmOThhZjk0OWU2M2YwOGQ0MTdmMWMzZmU5M2ZjMjhlMTM0MTY1NzJiMDdlODg1OWRmN2FkYjg0MTY3JlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCZyZXNwb25zZS1jb250ZW50LXR5cGU9dmlkZW8lMkZxdWlja3RpbWUifQ.7oH3aADuZDRTdqNMkwPAjuSdxWHMTywEGVUAtg940BM

A full-stack YouTube research and content intelligence tool built on the **WAT framework** (Workflows · Agents · Tools). Enter any niche topic and get a complete analysis — top channels, trending videos, engagement metrics, content gaps — delivered as a Google Slides deck, Sheets report, or interactive web report.

---

## Features

- **Niche Analysis** — search any topic, pull top videos and channels, surface trends and content gaps
- **Web App** — browser-based UI to run analyses, view reports, and generate posts without touching the CLI
- **Post Generator** — turn top-performing videos into LinkedIn/Twitter post drafts with one click
- **Niche Dashboard** — save niches, cache reports, refresh on demand, drag to reorder
- **Google Slides export** — auto-generated pitch deck with charts, top videos, and key insights
- **Google Sheets export** — structured data output with clickable video links
- **Notion integration** — write reports directly to a Notion database

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| Frontend | Vanilla JS · HTML/CSS (no framework) |
| Data | YouTube Data API v3 |
| Exports | Google Slides API · Google Sheets API · Notion API |
| Auth | Google OAuth 2.0 |

---

## Project Structure

```
├── app.py                  # FastAPI web app — all routes
├── tools/
│   ├── web_pipeline.py     # End-to-end analysis pipeline (web)
│   ├── search_youtube.py   # YouTube search + video metadata
│   ├── fetch_video_details.py
│   ├── fetch_channel_stats.py
│   ├── fetch_video_comments.py
│   ├── analyze_trends.py   # Trend detection + content gap analysis
│   ├── expand_topic.py     # Topic expansion via LLM
│   ├── generate_post.py    # Social post generation
│   ├── create_slides.py    # Google Slides builder
│   ├── write_to_sheets.py  # Google Sheets exporter
│   ├── write_to_notion.py  # Notion integration
│   ├── niche_store.py      # Niche persistence (file-based cache)
│   ├── run_report.py       # CLI report runner
│   └── config.py           # Shared config + env vars
├── templates/
│   ├── index.html          # Homepage / search
│   ├── report.html         # Analysis report view
│   ├── create_post.html    # Post generator
│   └── dashboard.html      # Saved niches dashboard
├── static/
│   └── style.css
├── workflows/              # Markdown SOPs for each task
└── .tmp/                   # Intermediate files (gitignored)
```

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/sirui-luo/Youtube-Analysis.git
cd Youtube-Analysis
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
YOUTUBE_API_KEY=your_youtube_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
NOTION_API_KEY=your_notion_api_key        # optional
NOTION_DATABASE_ID=your_notion_db_id      # optional
```

### 4. Set up Google OAuth (for Slides / Sheets export)

- Download `credentials.json` from Google Cloud Console
- Place it in the project root
- On first run, a browser window will open to authorize — `token.json` is saved automatically

### 5. Run the web app

```bash
uvicorn app:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## WAT Architecture

This project follows the **WAT framework** — a clean separation between probabilistic AI reasoning and deterministic code execution:

- **Workflows** (`workflows/`) — Markdown SOPs defining what to do and how
- **Agent** — Claude orchestrates tool calls, handles errors, improves the system
- **Tools** (`tools/`) — Python scripts that do the actual work (API calls, data transforms, file I/O)

---

## API Keys Required

| Key | Where to get it |
|---|---|
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/) → YouTube Data API v3 |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |
| Google OAuth | Google Cloud Console → OAuth 2.0 credentials |
| `NOTION_API_KEY` | [notion.so/my-integrations](https://www.notion.so/my-integrations) (optional) |
