# Get Your Deal · Trending Styles

Every week this finds what people in India are searching for on Pinterest, matches it with
products on Myntra and AJIO (through EarnKaro), and turns each trend into an idea page, pins
and a reel.

- Website: https://harshhaldankar.github.io/Getyourdeal/
- Pinterest: https://www.pinterest.com/getyourdeal45/
- This week's plan and pin progress: [PLAN.md](PLAN.md)

## How it works

```
Monday 7 AM IST          1 · Weekly trends  (.github/workflows/weekly_trends.yml)
  Pinterest India  ──►  this week's 6 trends ("wedding guest dress", "saree look", ...)
  EarnKaro         ──►  8 matching products per trend, plus "See all" links that never sell out
                   ──►  an idea page, 10 pins and a reel per trend; the website goes live

Every day 8 AM-10 PM     2 · Post pins  (.github/workflows/post_pins.yml)
  one pin an hour from the queue  ──►  Pinterest board for that trend  ──►  links to the idea page

Every week               Video kit  (https://harshhaldankar.github.io/Getyourdeal/kit/)
  2 hero products per trend, each with its photo and a ready Gemini (Veo) prompt
  you make the video in Gemini and upload it with the kit's button  ──►  inbox/<trend>-<n>/

Every day 7 PM IST       3 · Instagram reel  (.github/workflows/instagram.yml)
  the oldest video in inbox/  ──►  Instagram reel with its caption (official Graph API)
  The caption says "Comment LINK"; ManyChat DMs the link to everyone who comments.
```

## What you might do

| You want to | Do this |
|---|---|
| See this week's trends | Open [PLAN.md](PLAN.md) |
| Build this week's trends again now | Actions → **1 · Weekly trends** → Run workflow |
| Post a pin now | Actions → **2 · Post pins** → Run workflow |
| Make this week's videos | Open the [video kit](https://harshhaldankar.github.io/Getyourdeal/kit/) on your phone |
| Post a reel now | Actions → **3 · Instagram reel** → Run workflow (tick "force" if one went out today) |
| Drop a trend you don't like | Tell Claude, or delete it from `data/themes.json` and its pins from `data/queue.json` |
| Fix "Pinterest login expired" | Run `python refresh_pinterest_session.py`, log in, then paste `pinterest_session.json` into the `PINTEREST_SESSION_JSON` secret |

## Files

| Path | What it is |
|---|---|
| `trends/research.py` | Indian trends from Pinterest search suggestions and its India trending page |
| `trends/catalog.py` | EarnKaro: product catalogue and the link maker |
| `trends/build.py` | The weekly run, start to finish |
| `trends/pins.py`, `trends/reel.py` | Pin designs and the reel |
| `trends/site.py` | The website |
| `trends/post.py`, `trends/pinterest.py` | Posting pins |
| `trends/kit.py`, `trends/instagram.py` | The Gemini video kit; posting reels to Instagram |
| `inbox/` | Videos waiting for Instagram |
| `data/kit.json`, `data/ig_posted.json` | This week's kit, reels posted |
| `data/themes.json` | Every trend built so far |
| `data/queue.json`, `data/posted.json` | Pins waiting, pins posted |
| `docs/` | The website, copied to the Getyourdeal repo on each build |

## Secrets (repo Settings → Secrets → Actions)

`EARNKARO_EMAIL`, `EARNKARO_PASSWORD`, `PINTEREST_SESSION_JSON`, `WEBSITE_DEPLOY_TOKEN`, `AMAZON_AFFILIATE_TAG`,
`IG_USER_ID`, `IG_ACCESS_TOKEN` (Instagram: see "Instagram setup" below)

## Instagram setup (once)

Your Instagram must be a Business or Creator account linked to a Facebook Page.

1. developers.facebook.com → My Apps → **Create app** → use case "Other" → type **Business**.
2. In the app, add the **Instagram** product ("API setup with Facebook login").
3. Tools → **Graph API Explorer**: pick your app, then "Get User Access Token" with
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
   Approve your Page and Instagram account in the popup.
4. Click the ⓘ next to the token → **Open in Access Token Tool** → **Extend Access Token** → copy the long-lived token.
5. Back in the Explorer, paste that token and run
   `me/accounts?fields=name,access_token,instagram_business_account`.
   Your Page's `access_token` is **IG_ACCESS_TOKEN** (it doesn't expire);
   `instagram_business_account.id` is **IG_USER_ID**.
6. Add both as repo secrets, then Actions → **3 · Instagram reel** → Run workflow to check.
