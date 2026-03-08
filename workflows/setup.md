# One-Time Setup Guide

## Prerequisites

- Python 3.8+ (you have 3.12.4 at `/opt/anaconda3/bin/python3`)
- A Google account (the one that will own the Sheets, Slides, and send Gmail)
- YouTube Data API v3 key — already in `.env`

---

## Step 1: Install Dependencies

```bash
cd "/Users/Lenovo/Downloads/Youtube Analysis"
pip3 install -r requirements.txt
```

Verify:
```bash
python3 -c "import googleapiclient; print('OK')"
```

---

## Step 2: Enable Google APIs in Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select the same project that has your YouTube Data API v3 key
3. Go to **APIs & Services → Enable APIs and Services**
4. Search and enable each of these:
   - **Google Sheets API**
   - **Google Slides API**
   - **Google Drive API**
   - **Gmail API**
   - (YouTube Data API v3 should already be enabled)

---

## Step 3: Create OAuth 2.0 Credentials

1. In Cloud Console: **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `YouTube Analysis Tool`
5. Click **Create**
6. Download the JSON file
7. Rename it to `credentials.json`
8. Place it at: `/Users/Lenovo/Downloads/Youtube Analysis/credentials.json`

---

## Step 4: Configure OAuth Consent Screen

1. In Cloud Console: **APIs & Services → OAuth consent screen**
2. User type: **External**
3. Fill in:
   - App name: `YouTube Analysis Tool`
   - User support email: your Gmail
   - Developer contact: your Gmail
4. Under **Scopes**, add these manually:
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/presentations`
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/gmail.send`
5. Under **Test users**, add your Gmail address
6. Save and continue

---

## Step 5: Configure .env

Open `.env` and fill in:

```
REPORT_RECIPIENT_EMAIL=your-email@gmail.com
REPORT_SENDER_EMAIL=your-gmail@gmail.com
```

The sender must be the Google account you'll authenticate with.
The recipient can be the same address or any email.

---

## Step 6: Run Initial OAuth Flow

This only needs to happen once. It opens your browser to authorize the app.

```bash
cd "/Users/Lenovo/Downloads/Youtube Analysis"
python3 tools/write_to_sheets.py
```

- A browser window opens → sign in → click **Allow**
- `token.json` is created in the project root automatically
- The script will create a test spreadsheet in your Drive — you can delete it

Verify token exists:
```bash
ls -la token.json
```

---

## Step 7: Test the First Data Run

Run all tools in sequence to verify the pipeline works end-to-end:

```bash
# Step 1: Search YouTube (API key only, no OAuth)
python3 tools/search_youtube.py
# Expected: .tmp/videos_raw.json created, 50+ videos shown in log

# Step 2: Fetch video details
python3 tools/fetch_video_details.py
# Expected: .tmp/video_details.json created

# Step 3: Fetch channel stats
python3 tools/fetch_channel_stats.py
# Expected: .tmp/channel_stats.json created

# Step 4: Analyze
python3 tools/analyze_trends.py
# Expected: .tmp/analysis.json created with recommendations

# Step 5: Create Sheets (browser may open for OAuth if token expired)
python3 tools/write_to_sheets.py
# Expected: Spreadsheet URL printed to console

# Step 6: Create Slides
python3 tools/create_slides.py
# Expected: Presentation URL printed to console

# Step 7: Send email
python3 tools/send_email.py
# Expected: Email received at REPORT_RECIPIENT_EMAIL

# Or run everything at once:
python3 tools/run_report.py
```

---

## Step 8: Set Up Weekly Scheduling (macOS launchd)

Create the plist:

```bash
cat > ~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.youtube-ai-report.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/anaconda3/bin/python3</string>
        <string>/Users/Lenovo/Downloads/Youtube Analysis/tools/run_report.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/Lenovo/Downloads/Youtube Analysis</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/Lenovo/Downloads/Youtube Analysis/.tmp/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/Lenovo/Downloads/Youtube Analysis/.tmp/launchd_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/anaconda3/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/Lenovo</string>
    </dict>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist
```

Verify:
```bash
launchctl list | grep youtube-ai-report
```

Test immediately (without waiting for Monday):
```bash
launchctl start com.youtube-ai-report.weekly
```

---

## Token Management

`token.json` contains a refresh token that is valid indefinitely. You only need to re-run the OAuth flow if:
- You delete `token.json`
- You revoke access in Google account security settings
- You add new API scopes

To force re-authentication:
```bash
python3 tools/run_report.py --reauth
```

---

## Disable / Re-enable Scheduling

```bash
# Disable
launchctl unload ~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.youtube-ai-report.weekly.plist
```
