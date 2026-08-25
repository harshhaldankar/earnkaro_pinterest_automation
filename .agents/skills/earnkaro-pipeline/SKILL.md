---
name: earnkaro-pipeline
description: >-
  Use this skill to understand the architecture, data flow, and deployment strategy of the EarnKaro Pinterest & Instagram automation pipeline. Essential when modifying the deal generation, Reels creation, or Make.com RSS logic.
---

# EarnKaro Pipeline Architecture

This project is a fully automated affiliate marketing pipeline that scrapes deals and distributes them via an RSS feed to a Make.com scenario (which then posts to Instagram and Pinterest). It explicitly avoids logging into social media directly via Playwright to prevent bans.

## System Components

1. **Pipeline 1 (Manual Telegram Deals)**
   - Location: `telegram_watcher.py`
   - Role: Listens to the user's Telegram channel. When the user drops a deal link, it generates a Deal Card and an AI Reel.
   
2. **Pipeline 2 (Automated Trending Deals)**
   - Location: `pipeline2/run_pipeline.py`
   - Role: Scrapes Google Trends, finds high-discount (>=50%) deals on Amazon/Flipkart, and generates Deal Cards and AI Reels.

3. **Content Engine**
   - **Reels**: `pipeline2/reel_generator.py` uses `edge-tts` (AI voiceover) and `ffmpeg` to create vertical `.mp4` videos.
   - **Cards**: Generated via Pillow (`image_utils.py` / `telegram_watcher.py`).

4. **Distribution Hub (RSS)**
   - Location: `pipeline2/rss_generator.py`
   - Role: Outputs an XML feed (`docs/deals/rss.xml`) hosted on GitHub Pages.
   - **Make.com Setup**: 
     - Pinterest module uses the `<image_url>` to post static Deal Cards.
     - Instagram module uses the `<enclosure>` to post Reels, filtered by the `<instagram_eligible>true</instagram_eligible>` tag to throttle volume.

## Key Developer Rules
- **NEVER** re-introduce Playwright or direct Selenium logins for Instagram/Pinterest. This causes immediate IP bans. Always route output through the RSS generator.
- **Volume Control**: Pipeline 2 limits itself to 10 deals for Pinterest, but strictly tags only 2 deals per run as `instagram_eligible=True` to avoid Instagram spam filters.
- **Website URLs**: The RSS feed's `<link>` tag points to the GitHub Pages website anchor (e.g. `https://harshhaldankar.github.io/Getyourdeal/#deal_timestamp`) rather than the raw EarnKaro link. This protects the Pinterest account from affiliate bans and drives SEO traffic.
- **Testing**: Before pushing to `master`, always test locally by running `python pipeline2/run_pipeline.py` to verify ffmpeg and edge-tts generate the media correctly.
