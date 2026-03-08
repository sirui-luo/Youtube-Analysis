# Weekly YouTube AI Report — Standard Operating Procedure

## Objective

Automatically generate a 10-slide Google Slides report every Monday analyzing the AI/AI-automation niche on YouTube. Email the report link to the configured recipient.

---

## Inputs Required

| Input | Location | Notes |
|-------|----------|-------|
| YouTube API key | `.env` → `YOUTUBE_API_KEY` | Already configured |
| Recipient email | `.env` → `REPORT_RECIPIENT_EMAIL` | Must be filled in |
| Sender email | `.env` → `REPORT_SENDER_EMAIL` | The authenticated Gmail |
| OAuth client | `credentials.json` (project root) | Download from Google Cloud |
| OAuth token | `token.json` (auto-generated) | Created on first run |

---

## Tool Sequence

Each tool reads from `.tmp/` and writes to `.tmp/`. Run automatically via `run_report.py`.

| Step | Tool | Input | Output | Quota |
|------|------|-------|--------|-------|
| 1 | `tools/search_youtube.py` | Config keywords + trending | `.tmp/videos_raw.json` | ~1,001 units |
| 2 | `tools/fetch_video_details.py` | `videos_raw.json` | `.tmp/video_details.json` | ~2 units |
| 3 | `tools/fetch_channel_stats.py` | `video_details.json` | `.tmp/channel_stats.json` | ~1 unit |
| 4 | `tools/analyze_trends.py` | `video_details.json`, `channel_stats.json` | `.tmp/analysis.json` | 0 (pure Python) |
| 5 | `tools/write_to_sheets.py` | `analysis.json` | Google Sheets + `.tmp/sheets_output.json` | — |
| 6 | `tools/create_slides.py` | `analysis.json`, `sheets_output.json` | Google Slides + `.tmp/slides_output.json` | — |
| 7 | `tools/send_email.py` | `analysis.json`, `slides_output.json`, `sheets_output.json` | Gmail sent | — |

**YouTube API quota budget**: ~1,004 units per run (10.04% of 10,000 daily limit). Plenty of headroom for re-runs and debugging.

---

## Normal Execution

```bash
cd "/Users/Lenovo/Downloads/Youtube Analysis"
python3 tools/run_report.py
```

All output is logged to both stdout and `.tmp/run_log_YYYY-MM-DD.txt`.

---

## Expected Outputs

After a successful run:

- `.tmp/videos_raw.json` — 50–150 raw video results
- `.tmp/video_details.json` — Full stats for each video (views, likes, comments, duration, format, engagement rate)
- `.tmp/channel_stats.json` — Stats for all unique channels discovered
- `.tmp/analysis.json` — All computed insights: top videos, trending topics, format breakdown, timing patterns, content gaps, recommendations
- `.tmp/sheets_output.json` — Spreadsheet ID and chart IDs (needed by create_slides.py)
- `.tmp/slides_output.json` — Presentation ID and URL
- `.tmp/run_log_YYYY-MM-DD.txt` — Full run log
- **Google Sheets** — Spreadsheet with 6 tabs + 5 charts (URL in log)
- **Google Slides** — 10-slide deck (URL in log and email)
- **Gmail** — Email sent to `REPORT_RECIPIENT_EMAIL` with stats + links

---

## Slide Deck Structure

| Slide | Title | Content |
|-------|-------|---------|
| 1 | Cover | Title, week date |
| 2 | Executive Summary | 4 KPIs: videos analyzed, channels, avg engagement, top topic |
| 3 | Top Trending Videos | Table of top 7 videos by views |
| 4 | Trending Topics & Keywords | Bar chart from Sheets |
| 5 | Top Channels in AI Niche | Bar chart from Sheets |
| 6 | Engagement Rate Analysis | Bar chart from Sheets |
| 7 | Content Format Breakdown | Pie chart (Shorts / Mid / Long) |
| 8 | Upload Timing Patterns | Column chart (avg views by day) |
| 9 | Content Opportunities | Bullet list of underserved topics |
| 10 | Recommendations | 5 actionable bullets based on this week's data |

---

## Error Handling

**Check the log first:**
```bash
cat ".tmp/run_log_$(date +%Y-%m-%d).txt" | grep ERROR
```

**Common errors and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `quotaExceeded` | YouTube API daily limit hit (10,000 units) | Wait until midnight PT and re-run |
| `YOUTUBE_API_KEY is not set` | Missing .env entry | Add key to `.env` |
| `token has been expired or revoked` | OAuth token stale | Run `python3 tools/run_report.py --reauth` |
| `Missing .tmp/videos_raw.json` | Step 1 failed | Run `python3 tools/search_youtube.py` manually |
| `FileNotFoundError: credentials.json` | OAuth setup not done | Follow `workflows/setup.md` Step 3 |
| `HttpError 403` on Sheets/Slides | API not enabled in Cloud Console | Enable the API in Google Cloud Console |
| `No module named 'googleapiclient'` | Dependencies not installed | Run `pip3 install -r requirements.txt` |
| `REPORT_RECIPIENT_EMAIL is not set` | Missing .env entry | Add email to `.env` |

**Re-running from a specific step:**

If Step 5 (Sheets) fails but Steps 1–4 succeeded, you don't need to re-collect data:
```bash
python3 tools/write_to_sheets.py   # re-run step 5
python3 tools/create_slides.py     # re-run step 6
python3 tools/send_email.py        # re-run step 7
```

`.tmp/` files from steps 1–4 are preserved between runs.

---

## Scheduling

This workflow runs automatically every Monday at 7:00 AM local time via macOS launchd.

```bash
# Check status
launchctl list | grep youtube-ai-report

# Trigger manual run immediately
launchctl start com.youtube-ai-report.weekly

# Disable scheduling
launchctl unload ~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist
```

Launchd logs:
- `.tmp/launchd_stdout.log`
- `.tmp/launchd_stderr.log`

---

## Updating Configuration

**Change search keywords** → Edit `KEYWORDS` list in `tools/config.py`

**Change number of results per keyword** → Edit `MAX_RESULTS_PER_KEYWORD` in `tools/config.py`

**Change lookback window** → Edit `LOOKBACK_DAYS` in `tools/config.py` (default: 7)

**Change recipient email** → Edit `REPORT_RECIPIENT_EMAIL` in `.env`

**Change report schedule** → Edit the `StartCalendarInterval` section of the launchd plist at `~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist`, then reload with `launchctl unload ... && launchctl load ...`

No restart needed — config changes take effect on the next run.

---

## Quality Checks

Before considering a run successful:

- [ ] `.tmp/analysis.json` contains `total_videos_analyzed` ≥ 20
- [ ] `analysis.json` has at least 1 recommendation and at least 3 trending keywords
- [ ] Google Sheets URL is accessible, all 6 tabs visible, charts rendering in Keywords/Channels/Engagement/Format/Timing tabs
- [ ] Google Slides has all 10 slides; charts on slides 4–8 are embedded (not placeholders)
- [ ] Email received at recipient address with working Slides and Sheets links
- [ ] `run_log_YYYY-MM-DD.txt` shows no ERROR-level lines

---

## Known Limitations

- **Search order**: `search.list` with `order=viewCount` does not perfectly rank by views — it's a YouTube estimate. Actual view counts are confirmed in Step 2 via `videos.list`.
- **Shorts detection**: Videos ≤60 seconds are classified as Shorts. Some YouTube Shorts are longer; this is a heuristic.
- **Channel upload frequency**: Estimated from (total video count / weeks since channel creation). Does not reflect recent cadence — treat as a rough indicator.
- **Trending tab**: Includes Science & Technology trending videos from the US which may include non-AI content. The keyword analysis downstream filters relevance via title tokenization.
- **Chart embedding**: Google Slides charts are linked to Sheets. If the Sheets is deleted, charts become broken images. Don't delete the weekly Sheets if you want the Slides to stay current.
- **Gmail sender**: Must send from the authenticated Google account. If `REPORT_SENDER_EMAIL` doesn't match the authenticated account, the send will fail with a 403.

---

## Self-Improvement Log

_Document fixes, discoveries, and improvements here as you encounter them._

| Date | Issue | Fix Applied |
|------|-------|-------------|
| — | — | — |
