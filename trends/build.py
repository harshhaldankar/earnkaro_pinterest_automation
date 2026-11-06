"""
build.py - the weekly run: find this week's Indian trends and turn each into an idea.

  1. EarnKaro catalogue      every product EarnKaro lists (catalog.py)
  2. Trends                  this week's themes from Pinterest India, each with matching products (research.py)
  3. Shop-all links          Myntra and AJIO searches as EarnKaro links, an Amazon search with our tag
  4. Per theme               product photos, an idea page, 2 collage pins + 1 pin per product, a reel
  5. Queue                   pins go to data/queue.json; post.py posts one an hour
  6. Publish                 site, Instagram reels feed, PLAN.md; commit and put the site live

Run: python -m trends.build   (THEMES_PER_WEEK env var overrides the number of themes)
"""
import asyncio
import itertools
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from urllib.parse import quote, quote_plus

import requests
from dotenv import load_dotenv

load_dotenv(".env")

from shared.publish import commit_and_push, deploy_site
from trends import site
from trends.catalog import EarnKaroSession, amazon_search_link
from trends.pins import create_collage_pin, create_template_pin
from trends.reel import create_product_reel
from trends.research import BOARD_HOME, research

IST = timezone(timedelta(hours=5, minutes=30))
DATA = Path("data")
THEMES_FILE = DATA / "themes.json"
QUEUE_FILE = DATA / "queue.json"
PIN_IMAGES = DATA / "pin_images"
THEMES_PER_WEEK = int(os.getenv("THEMES_PER_WEEK", "6"))
NO_REPEAT_DAYS = 14


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def rs(v) -> str:
    return f"₹{v:,.0f}"


def download(url: str, out: Path) -> bool:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 5000:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
            return True
    except requests.RequestException:
        pass
    return False


def hashtags(th: dict) -> str:
    """'#WeddingGuestDress #Ethnic #Wedding ... #IndianFashion': the theme, a few search words, the niche."""
    words = {w for p in [th["phrase"]] + th["related"][:3] for w in p.split() if len(w) > 3 and w.isalpha()}
    tags = [th["title"].replace(" ", "").replace("'", "").replace("-", "")] + sorted(words)[:4]
    tags.append("HomeDecorIndia" if th["board"] == BOARD_HOME else "IndianFashion")
    return " ".join("#" + t[:1].upper() + t[1:] for t in dict.fromkeys(tags))


def pins_for(th: dict) -> list:
    """2 collage pins (products 1-4, 5-8) and one pin per product; all link to the idea page."""
    folder = Path("docs/ideas") / th["slug"]
    url = f"{site.SITE_URL}/ideas/{th['slug']}/"
    prods = th["products"]
    low, top_disc = min(p["price"] for p in prods), max(p["discount"] for p in prods)
    also = ", ".join(th["related"][:5])
    tags = hashtags(th)
    out = []
    for n, group in enumerate((range(0, 4), range(4, 8)), 1):
        imgs = [str(folder / f"p{i + 1}.jpg") for i in group if i < len(prods)]
        img = folder / "collage.jpg" if n == 1 else PIN_IMAGES / th["slug"] / "collage2.jpg"
        offer = f"{len(prods)} PICKS FROM {rs(low)}" if n == 1 else f"UP TO {top_disc}% OFF"
        if create_collage_pin(imgs, str(img), th["title"], offer):
            out.append({
                "id": f"{th['week']}:{th['slug']}:collage{n}", "image": str(img),
                "title": f"{th['title']}: {len(prods)} Picks from {rs(low)}"[:100],
                "description": (f"{th['title']} trending on Pinterest in India this week. {len(prods)} picks from {rs(low)} "
                                f"on Myntra and AJIO, with links to shop each one. People also search: {also}. {tags}")[:500],
                "link": url, "board": th["board"],
            })
    for i, p in enumerate(prods, 1):
        img = PIN_IMAGES / th["slug"] / f"pin{i}.jpg"
        offer = f"{rs(p['price'])}  ·  {p['discount']}% OFF" if p["discount"] else f"ONLY {rs(p['price'])}"
        pin, _ = create_template_pin(str(folder / f"p{i}.jpg"), str(img), headline=th["title"], offer=offer,
                                     store=p["store"])
        if pin:
            out.append({
                "id": f"{th['week']}:{th['slug']}:p{i}", "image": str(img),
                "title": f"{th['title']}: {p['brand']} {p['name'].replace(p['brand'], '').strip()}"[:90].rstrip() + f" {rs(p['price'])}",
                "description": (f"{p['name']} by {p['brand']}, {rs(p['price'])}" + (f" ({p['discount']}% off)" if p["discount"] else "")
                                + f" on {p['store']}. One of our {th['title'].lower()} picks, trending in India this week. "
                                  f"People also search: {also}. {tags}")[:500],
                "link": f"{url}#p{i}", "board": th["board"],
            })
    return out


def interleave(groups: list) -> list:
    """Round-robin across themes, so the pins of one theme are spread through the week."""
    out = []
    for row in itertools.zip_longest(*groups):
        out += [x for x in row if x]
    return out


def write_reels_feed(themes: list):
    items = []
    for th in themes[:20]:
        reel = Path("docs/ideas") / th["slug"] / "reel.mp4"
        if not reel.exists():
            continue
        url = f"{site.SITE_URL}/ideas/{th['slug']}/"
        caption = (f"{th['title']} 🔥 {len(th['products'])} picks from {rs(min(p['price'] for p in th['products']))} "
                   f"trending in India this week. Comment LINK and we'll DM you the links! {hashtags(th)}")
        items.append(f"""  <item>
    <title>{escape(th['title'])}</title>
    <link>{url}</link>
    <guid isPermaLink="false">{escape(th['week'] + ':' + th['slug'])}</guid>
    <pubDate>{format_datetime(datetime.fromisoformat(th['built_at']))}</pubDate>
    <description>{escape(caption)}</description>
    <enclosure url="{url}reel.mp4" type="video/mp4" length="{reel.stat().st_size}"/>
  </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Get Your Deal reels</title>
  <link>{site.SITE_URL}/</link>
  <description>One reel per trending idea, for Instagram.</description>
{chr(10).join(items)}
</channel>
</rss>
"""
    Path("docs/reels.xml").write_text(feed, encoding="utf-8")


def write_plan(themes: list, queue: list):
    """PLAN.md: this week's themes and pin progress, readable on GitHub."""
    posted = {p["id"] for p in load(DATA / "posted.json", [])}
    latest = themes[0]["week"] if themes else ""
    rows = []
    for th in [t for t in themes if t["week"] == latest]:
        mine = [q for q in queue if q["id"].startswith(f"{th['week']}:{th['slug']}:")]
        done = sum(q["id"] in posted for q in mine)
        rows.append(f"| [{th['title']}]({site.SITE_URL}/ideas/{th['slug']}/) | {th['board']} | {len(th['products'])} | {done} of {len(mine)} | {', '.join(th['related'][:3])} |")
    Path("PLAN.md").write_text(f"""# This week's plan

Week of **{latest}**. Built automatically every Monday from what people in India search on Pinterest.

| Idea | Pinterest board | Products | Pins posted | Also searched |
|---|---|---|---|---|
{chr(10).join(rows) or '| No ideas yet | | | | |'}

Pins go out one an hour, 8 AM to 10 PM IST. Website: {site.SITE_URL}/
To skip an idea, delete its row from `data/themes.json` before the pins go out, or tell Claude.
""", encoding="utf-8")


async def main() -> int:
    now = datetime.now(IST)
    week = now.strftime("%Y-%m-%d")
    themes = load(THEMES_FILE, [])
    recent = {tuple(t["key"].split(":")) for t in themes
              if datetime.fromisoformat(t["built_at"]) > now - timedelta(days=NO_REPEAT_DAYS)}

    async with EarnKaroSession() as ek:
        catalog = await ek.products()
        new = await research(catalog, recent, THEMES_PER_WEEK)
        for th in new:
            q = th["phrase"]
            th["shop_links"] = [(label, link) for label, link in (
                ("See all on Myntra", await ek.make_link(f"https://www.myntra.com/{quote(q.replace(' ', '-'))}?rawQuery={quote_plus(q)}")),
                ("See all on AJIO", await ek.make_link(f"https://www.ajio.com/search/?text={quote_plus(q)}")),
                ("Search on Amazon", amazon_search_link(q)),
            ) if link]
    if not new:
        print("[Build] No themes with enough products this week.")
        return 1

    queue = load(QUEUE_FILE, [])
    new_pins = []
    for th in new:
        th.update(week=week, built_at=now.isoformat())
        folder = Path("docs/ideas") / th["slug"]
        kept = []  # photos are numbered p1, p2... in the order of the products that downloaded
        for p in th["products"]:
            if download(p["image"], folder / f"p{len(kept) + 1}.jpg"):
                kept.append(p)
        th["products"] = kept
        for stale in folder.glob("p*.jpg"):
            if int(stale.stem[1:]) > len(kept):
                stale.unlink()
        if len(kept) < 4:
            print(f"[Build] {th['title']}: only {len(kept)} photos downloaded; skipped")
            continue
        pins = pins_for(th)
        reel = create_product_reel([str(folder / f"p{i}.jpg") for i in range(1, 5)], str(folder / "reel.mp4"),
                                   title=th["title"], price=rs(min(p["price"] for p in kept)),
                                   discount=f"{max(p['discount'] for p in kept)}%", store="Myntra & AJIO", price_word="From")
        print(f"[Build] {th['title']}: {len(kept)} products, {len(pins)} pins, reel {'ok' if reel else 'failed'}")
        new_pins.append(pins)
        themes = [t for t in themes if t["slug"] != th["slug"]]
        themes.insert(0, th)

    queue += interleave(new_pins)
    save(THEMES_FILE, themes)
    save(QUEUE_FILE, queue)
    site.rebuild(themes)
    write_reels_feed(themes)
    write_plan(themes, queue)
    print(f"[Build] {sum(len(p) for p in new_pins)} pins queued")

    if os.getenv("PUBLISH", "1") == "1":
        commit_and_push(f"Weekly trends: {', '.join(t['title'] for t in themes if t['week'] == week)}",
                        ["data", "docs", "PLAN.md"])
        deploy_site(f"Weekly trends {week}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
