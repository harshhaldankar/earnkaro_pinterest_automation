# 🚀 EarnKaro Pinterest Automation — Setup Guide

> Multi-PC portable setup guide. Follow these steps on any new Windows PC.

---

## 📋 Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | https://python.org/downloads |
| Git | Latest | https://git-scm.com |
| ffmpeg | Latest | https://ffmpeg.org/download.html — add to PATH |
| Google Chrome | Latest | Used by Playwright |

---

## 1️⃣ Clone the Repository

```powershell
git clone https://github.com/harshhaldankar/earnkaro_pinterest_automation.git
cd earnkaro_pinterest_automation
```

---

## 2️⃣ Create Virtual Environment & Install Dependencies

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Install Playwright Browsers

```powershell
.venv\Scripts\python -m playwright install chromium
```

---

## 3️⃣ Configure Secrets (.env)

Create a `.env` file in the project root. **Never commit this file.**

```env
# ── Telegram ──────────────────────────────────────────────────
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=Itachi          # Name of your .session file

# Telegram channels to watch (comma-separated usernames)
TELEGRAM_CHANNELS=channel1,channel2,channel3

# ── EarnKaro ──────────────────────────────────────────────────
EARNKARO_EMAIL=your_email@gmail.com
EARNKARO_PASSWORD=your_password

# ── Pinterest ──────────────────────────────────────────────────
PINTEREST_EMAIL=your_pinterest_email
PINTEREST_PASSWORD=your_pinterest_password
PINTEREST_BOARD_NAME=GetYourDeal

# ── Instagram ─────────────────────────────────────────────────
INSTAGRAM_USERNAME=getyurdeal
INSTAGRAM_PASSWORD=your_instagram_password

# ── GitHub ────────────────────────────────────────────────────
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=harshhaldankar/Getyourdeal
GITHUB_BRANCH=master

# ── Gemini AI ─────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key

# ── Amazon Affiliate ──────────────────────────────────────────
AMAZON_AFFILIATE_TAG=your-tag-21
```

---

## 4️⃣ Transfer Session Files (from old PC)

These files are gitignored for security. Copy them manually via USB/cloud:

| File | Purpose |
|---|---|
| `earnkaro_session.session` | Telegram session (Itachi) |
| `pinterest_session.json` | Pinterest browser session |
| `instagrapi_session.json` | Instagram API session |

> **Tip**: Use Google Drive or a USB drive to transfer these. They expire if you don't transfer them — re-login if needed.

---

## 5️⃣ Re-authenticate Sessions (if starting fresh)

### Pinterest Session
```powershell
.venv\Scripts\python refresh_pinterest_session.py
```
This opens a browser — log in to Pinterest manually and it saves the session.

### Instagram Session
```powershell
.venv\Scripts\python refresh_instagram_session.py
```

### Telegram Session
```powershell
.venv\Scripts\python telegram_setup.py
```
Enter your phone number and the OTP received.

---

## 6️⃣ Verify Everything Works

```powershell
# Check Pinterest session is valid
.venv\Scripts\python -c "import asyncio; from pinterest_poster import check_session_health; print(asyncio.run(check_session_health()))"

# Check deals database
.venv\Scripts\python -c "import json; d=json.load(open('deals_data.json',encoding='utf-8')); print(f'{len(d)} deals, {sum(1 for x in d if not x.get(\"pinned\"))} unpinned')"
```

---

## 🗂️ Project Structure

```
earnkaro_pinterest_automation/
│
├── .env                        # ← YOUR SECRETS (never commit)
├── .gitignore
├── requirements.txt
├── deals_data.json             # Master deal database
│
├── telegram_watcher.py         # Pipeline 1: Telegram → Deals → Pinterest
├── pinterest_poster.py         # Playwright Pinterest posting
├── post_pinterest_backlog.py   # Catch-up: post queued deals manually
├── workflow_1_website.py       # Website builder
│
├── pipeline2/                  # Pipeline 2: EarnKaro top deals
│   ├── run_pipeline.py         # Orchestrator: pick top deals → website → Pinterest
│   ├── earnkaro_top_deals.py   # Reads EarnKaro category pages (needs EarnKaro login)
│   ├── dedup_engine.py         # Never post the same product twice (both pipelines)
│   ├── deal_card_generator.py
│   └── ...
│
├── shared/                     # Shared utilities
│   ├── board_classifier.py
│   ├── rate_limiter.py
│   └── ...
│
├── scrape_all_earnkaro_super_sellers.py  # EarnKaro scraper
├── distribute_festive_blitz.py           # Omnichannel distributor
├── broadcast_festive_telegram.py         # Telegram broadcast
│
├── .github/workflows/          # GitHub Actions automations
│   ├── deals_automation.yml    # Runs Pipeline 1 every 5 hours
│   └── trending_deals.yml      # Runs Pipeline 2 twice daily
│
└── docs/                       # GitHub Pages website
    ├── index.html
    ├── rss.xml                 # RSS feed (Make.com reads this)
    └── deals/
        ├── images/             # Deal pin images
        └── videos/             # Deal reels
```

---

## 🔄 How the Automation Works

```
Pipeline 1 (every 5h)                      Pipeline 2 (08:30 & 20:30 IST)
Telegram deal channels                     EarnKaro category pages (8 per run, rotating)
      ↓  niche prefilter                         ↓  ≥50% off, ≤ ₹15k, ranked by commission × discount
telegram_watcher.py → EarnKaro bot link    run_pipeline.py → top 5, one per category
      ↓                                          ↓
      └──────────────→ deals_data.json ←────────┘
                             ↓
          Website rebuilt + live.json (old pages show live deals) → GitHub Pages
                             ↓
          Pinterest (Playwright, shared 15 pins/day cap, 7 AM–11 PM IST)
                             ↓
          RSS feed → Make.com (optional)
```

Both workflows share the `telegram-session` concurrency group so they never run at the same
time (Telegram revokes a session used from two IPs at once).

---

## ▶️ Manual Operations

### Post Pinterest Backlog
```powershell
# Post next 10 pending deals
.venv\Scripts\python post_pinterest_backlog.py --limit 10

# Force post even outside 9AM-9PM window
.venv\Scripts\python post_pinterest_backlog.py --limit 5 --force

# Dry run (preview without posting)
.venv\Scripts\python post_pinterest_backlog.py --limit 10 --dry-run
```

### Broadcast to Telegram Channel
```powershell
.venv\Scripts\python broadcast_festive_telegram.py --limit 5 --channel "CHANNEL_USERNAME"
```

### Rebuild RSS Feed
```powershell
.venv\Scripts\python -c "from workflow_1_website import rebuild_clean_rss; rebuild_clean_rss()"
```

---

## 🌐 Live Links

| Resource | URL |
|---|---|
| Website / RSS | https://harshhaldankar.github.io/Getyourdeal/ |
| RSS Feed | https://harshhaldankar.github.io/Getyourdeal/rss.xml |
| Pinterest | https://in.pinterest.com/getyourdeal45/ |
| Instagram | https://www.instagram.com/getyurdeal/ |
| Source Repo | https://github.com/harshhaldankar/earnkaro_pinterest_automation |

---

## ❗ Known Issues & Tips

- **ffmpeg must be on PATH** for reel video generation. Install and restart terminal.
- **Pinterest session expires ~1 year** — run `refresh_pinterest_session.py` to renew.
- **GitHub PAT must have `repo` scope** (not `workflow` scope) for normal pushes.
- **Posting hours**: Pinterest auto-posts only 9AM–9PM IST. Use `--force` flag to override.
- **`deals_data.json` uses UTF-8** — always open with `encoding='utf-8'` in Python.
