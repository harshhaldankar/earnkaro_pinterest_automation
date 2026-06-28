# EarnKaro Pinterest Affiliate Automation 🛍️

A fully automated pipeline that scrapes top affiliate deals from EarnKaro, generates AI-ranked content, creates professional Pinterest pin images with real brand visuals, posts them to Pinterest, and auto-updates a live deals website — all running on GitHub Actions twice daily.

## Pipeline Flow

```
Step 1 → Scrape EarnKaro + AI rank top 10 offers     → offers.json
Step 2 → Generate Pinterest titles + Hinglish copy    → content.json
Step 3 → Generate EarnKaro affiliate links            → content.json (updated)
Step 4 → Fetch brand images + create pin JPEGs        → pins/*.jpg
Step 5 → Post pins to Pinterest via Playwright        → pin URLs saved
Step 6 → Send Telegram notification with deals
Step 7 → Generate & deploy deals website              → docs/deals.html
```

## Setup

### 1. Add GitHub Secrets

Go to your repo → `Settings → Secrets and variables → Actions` and add:

| Secret | Description |
|---|---|
| `EARNKARO_EMAIL` | Your EarnKaro login email |
| `EARNKARO_PASSWORD` | Your EarnKaro password |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `PINTEREST_EMAIL` | Your Pinterest email |
| `PINTEREST_PASSWORD` | Your Pinterest password |
| `PINTEREST_BOARD_NAME` | Pinterest board name (e.g. `Deals`) |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram channel/group ID |

### 2. Enable GitHub Pages

Go to `Settings → Pages → Source: Deploy from branch → main → /docs`

Your live URLs:
- `https://yourusername.github.io/repo-name/` — Home page
- `https://yourusername.github.io/repo-name/deals.html` — Auto-updated deals
- `https://yourusername.github.io/repo-name/privacy.html` — Privacy Policy *(use this for Pinterest API app)*

### 3. Enable Pinterest API

Register at [developers.pinterest.com](https://developers.pinterest.com) and use your GitHub Pages Privacy Policy URL.

## Files

| File | Purpose |
|---|---|
| `step1_scrape_offers.py` | Scrape EarnKaro + Gemini AI ranking |
| `step2_generate_content.py` | Generate Pinterest + WhatsApp copy |
| `step3_make_links.py` | Generate affiliate links via EarnKaro |
| `poster_pinterest.py` | Create pin images + post to Pinterest |
| `poster_telegram.py` | Send deals to Telegram |
| `generate_website.py` | Build deals.html for GitHub Pages |
| `site/` | Static website files (index, privacy, terms) |
| `.github/workflows/daily_affiliate.yml` | GitHub Actions workflow |

## Schedule

Runs automatically at **8:00 AM IST** and **7:00 PM IST** every day.
Can also be triggered manually via `Actions → Run workflow`.
