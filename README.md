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
  the oldest Gemini video in inbox/, or else the next of this week's editorial reels
  (trends/editorial.py, made on Monday)  ──►  Instagram reel with its caption (official Graph API)
  So a reel goes out every day even when you make no videos.
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
| `trends/pins.py`, `trends/editorial.py` | Pin designs and the premium editorial reel |
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

## Instagram setup (once; done 2026-11-07)

What worked for @getyurdeal (Professional account in the "Getyurdeal" business portfolio):

1. business.facebook.com/settings → Accounts → Instagram accounts: @getyurdeal must be in the portfolio.
   Its ID there (1784…) is **IG_USER_ID**.
2. developers.facebook.com → app **getyurdeal** → Instagram → **API setup with Unified login** →
   "Generate access tokens" → pick @getyurdeal → **Generate token**: that's **IG_ACCESS_TOKEN**
   (a business System User token with instagram_content_publish).
3. Actions → **3 · Instagram reel** → Run workflow: the log says "OK: posting as @getyurdeal".

If posting ever stops with a token error, repeat step 2 and update the secret.
(Instagram-login tokens starting with "IG" also work; those last 60 days and each run renews them.)
