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

Instagram                Make.com reads docs/reels.xml and posts each new reel.
                         The reel says "Comment LINK"; ManyChat DMs the link to everyone who comments.
```

## What you might do

| You want to | Do this |
|---|---|
| See this week's trends | Open [PLAN.md](PLAN.md) |
| Build this week's trends again now | Actions → **1 · Weekly trends** → Run workflow |
| Post a pin now | Actions → **2 · Post pins** → Run workflow |
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
| `data/themes.json` | Every trend built so far |
| `data/queue.json`, `data/posted.json` | Pins waiting, pins posted |
| `docs/` | The website, copied to the Getyourdeal repo on each build |

## Secrets (repo Settings → Secrets → Actions)

`EARNKARO_EMAIL`, `EARNKARO_PASSWORD`, `PINTEREST_SESSION_JSON`, `WEBSITE_DEPLOY_TOKEN`, `AMAZON_AFFILIATE_TAG`
