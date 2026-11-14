"""
build.py - the weekly run: find this week's Indian trends and turn each into an idea.

  1. EarnKaro catalogue      every product EarnKaro lists (catalog.py)
  2. Trends                  this week's themes from Pinterest India, each with matching products (research.py)
  3. Shop-all links          Myntra and AJIO searches as EarnKaro links, an Amazon search with our tag;
                             each product's button is a store search for that style (see relink)
  4. Per theme               product photos, an idea page, 2 collage pins + 1 pin per product, a reel
  5. Queue                   pins go to data/queue.json; post.py posts one an hour
  6. Publish                 site, Instagram reels feed, PLAN.md; commit and put the site live

Run: python -m trends.build   (THEMES_PER_WEEK env var overrides the number of themes)
     python -m trends.build --relink   redo the product buttons of the current ideas and publish
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
from trends.analytics import board_weights, fetch_async, report_md
from trends.kit import build_kit
from trends.pins import create_moodboard_pin, create_natural_pin
from trends.editorial import create_editorial_reel
from trends.reel import nice_cap, short_label
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
    filler = {"ideas", "aesthetic", "guest", "looks", "look", "women", "girls", "teenagers", "home", "bedroom",
              "outfits", "outfit", "wear", "wall", "simple", "latest", "style", "styles", "trendy", "with", "dress", "wedding"}
    words = {w for p in [th["phrase"]] + th["related"][:3] for w in p.split()
             if len(w) > 3 and w.isalpha() and w.lower() not in filler}
    tags = [th["title"].replace(" ", "").replace("'", "").replace("-", "")] + sorted(words)[:3]
    if th["board"] == BOARD_HOME:
        tags += ["HomeDecorIndia", "HomeDecorIdeas", "MyntraFinds"]
    elif "Beauty" in th["board"]:
        tags += ["MakeupIndia", "AffordableMakeup", "MyntraFinds"]
    else:
        tags += ["IndianFashion", "AffordableFashion", "MyntraFinds", "AjioFinds"]
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
        sub = f"{len(prods)} picks from {rs(low)}" if n == 1 else f"Up to {top_disc}% off on Myntra & AJIO"
        if create_moodboard_pin(imgs, str(img), th["title"], sub, seed=n):
            out.append({
                "id": f"{th['week']}:{th['slug']}:collage{n}", "image": img.as_posix(),
                "title": f"{th['title']}: {len(prods)} Picks from {rs(low)}"[:100],
                "description": (f"{th['title']} trending on Pinterest in India this week. {len(prods)} picks from {rs(low)} "
                                f"on Myntra and AJIO, with links to shop each one. People also search: {also}. {tags}")[:500],
                "link": url, "board": th["board"],
            })
    for i, p in enumerate(prods, 1):
        img = PIN_IMAGES / th["slug"] / f"pin{i}.jpg"
        line = f"{short_label(p['name'], p['brand'])} · {rs(p['price'])} on {p['store']}"
        pin = create_natural_pin(str(folder / f"p{i}.jpg"), str(img), th["title"], line, seed=i)
        if pin:
            out.append({
                "id": f"{th['week']}:{th['slug']}:p{i}", "image": img.as_posix(),
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


def reel_picks(th: dict) -> list:
    """The 6 cheapest products, which the reel counts through (photos are docs/ideas/<slug>/p1.jpg...)."""
    items = [dict(img=f"docs/ideas/{th['slug']}/p{i}.jpg", brand=p["brand"], label=short_label(p["name"], p["brand"]),
                  price=p["price"], mrp=p["mrp"], discount=p["discount"], store=p["store"])
             for i, p in enumerate(th["products"], 1)]
    return sorted(items, key=lambda x: x["price"])[:6]


def reel_for(th: dict):
    """The premium editorial reel (trends/editorial.py); Instagram posts one a day when no Gemini video is waiting."""
    return create_editorial_reel(reel_picks(th), str(Path("docs/ideas") / th["slug"] / "reel.mp4"), th["title"])


def reel_caption(th: dict) -> str:
    picks = reel_picks(th)
    verb = ("goes in your home" if th["board"] == BOARD_HOME else
            "would you try" if "Beauty" in th["board"] else "would you wear")
    return (f"{th['title']} under {rs(nice_cap(max(p['price'] for p in picks)))} 🔥\n\n"
            f"{len(picks)} picks people in India are searching for right now, from {rs(picks[0]['price'])}.\n"
            f"Which one {verb}? Tell us 1-{len(picks)} 👇\n\n"
            f"Comment LINK and we'll DM you every link 💌\n"
            f"Or tap the link in our bio 🔗\n"
            f"Save this for later ✨\n\n{hashtags(th)}")


def write_reels_feed(themes: list):
    """docs/reels.xml for Make.com's Instagram scenario, which reads <video_url> (kept from the old feed)."""
    items = []
    for th in themes[:20]:
        reel = Path("docs/ideas") / th["slug"] / "reel.mp4"
        if not reel.exists():
            continue
        url = f"{site.SITE_URL}/ideas/{th['slug']}/"
        caption = reel_caption(th)
        items.append(f"""  <item>
    <title>{escape(th['title'])}</title>
    <link>{url}</link>
    <guid isPermaLink="false">{escape(th['week'] + ':' + th['slug'])}</guid>
    <pubDate>{format_datetime(datetime.fromisoformat(th['built_at']))}</pubDate>
    <description>{escape(caption)}</description>
    <video_url>{url}reel.mp4</video_url>
    <cover_url>{url}collage.jpg</cover_url>
    <enclosure url="{url}reel.mp4" type="video/mp4" length="{reel.stat().st_size}"/>
    <media:content url="{url}reel.mp4" medium="video" type="video/mp4"/>
  </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Get Your Deal reels</title>
  <link>{site.SITE_URL}/</link>
  <description>One reel per trending idea, for Instagram.</description>
{chr(10).join(items)}
</channel>
</rss>
"""
    Path("docs/reels.xml").write_text(feed, encoding="utf-8")


def _latest_report():
    files = sorted(Path("data/analytics").glob("*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def write_plan(themes: list, queue: list, report: dict = None):
    """PLAN.md: this week's themes and pin progress, readable on GitHub."""
    posted = {p["id"] for p in load(DATA / "posted.json", [])}
    latest = themes[0]["week"] if themes else ""
    rows = []
    for th in [t for t in themes if t["week"] == latest]:
        mine = [q for q in queue if q["id"].startswith(f"{th['week']}:{th['slug']}:")]
        done = sum(q["id"] in posted for q in mine)
        rows.append(f"| [{th['title']}]({site.SITE_URL}/ideas/{th['slug']}/) | {th['board']} | {len(th['products'])} | {done} of {len(mine)} | {', '.join(th['related'][:3])} |")
    Path("PLAN.md").write_text(f"""# This week's plan

Week of **{latest}**. Built automatically every Monday from what people in India search on Pinterest,
weighted by how our own boards did (Pinterest Analytics, read at the start of the run).

## Last 30 days on Pinterest

{report_md(report) if report else report_md(_latest_report())}
## This week's ideas

| Idea | Pinterest board | Products | Pins posted | Also searched |
|---|---|---|---|---|
{chr(10).join(rows) or '| No ideas yet | | | | |'}

Pins go out one an hour, 8 AM to 10 PM IST. Website: {site.SITE_URL}/
To skip an idea, delete its row from `data/themes.json` before the pins go out, or tell Claude.
""", encoding="utf-8")


def store_search(store: str, q: str) -> str:
    """A store's search page for q ('' for stores we don't search)."""
    if store == "Myntra":
        return f"https://www.myntra.com/{quote(q.lower().replace(' ', '-'))}?rawQuery={quote_plus(q)}"
    if store == "AJIO":
        return f"https://www.ajio.com/search/?text={quote_plus(q)}"
    return ""


async def relink(ek, th: dict):
    """EarnKaro's catalogue lists old items (Myntra photos from 2017-2020) that are mostly sold out,
    so each product's button opens the store's search for that exact style instead: the item if it
    is still sold, and similar ones in stock. The tracked link earns on whatever is bought."""
    done = 0
    for p in th["products"]:
        p.setdefault("item_link", p["link"])
        q = " ".join(p["name"].replace("&", " ").split()[:9])
        url = store_search(p["store"], q)
        link = await ek.make_link(url) if url else ""
        if link:
            p["link"], p["search"] = link, q
            done += 1
    print(f"[Build] {th['title']}: {done} of {len(th['products'])} product buttons now open a store search")


async def main() -> int:
    now = datetime.now(IST)
    week = now.strftime("%Y-%m-%d")
    themes = load(THEMES_FILE, [])
    # The workflow has a backup trigger (GitHub skips scheduled runs): build once a week only
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if os.getenv("ONLY_IF_NOT_BUILT") == "1" and themes and datetime.fromisoformat(themes[0]["built_at"]) >= week_start:
        print(f"[Build] This week's ideas were already built on {themes[0]['week']}; nothing to do.")
        return 0
    recent = {tuple(t["key"].split(":")) for t in themes
              if datetime.fromisoformat(t["built_at"]) > now - timedelta(days=NO_REPEAT_DAYS)}

    report = await fetch_async()  # last 30 days on Pinterest: steers which boards get more trends
    weights = board_weights(report)
    if weights:
        print(f"[Build] Board weights from analytics: {weights}")
    async with EarnKaroSession() as ek:
        catalog = await ek.products()
        new = await research(catalog, recent, THEMES_PER_WEEK, board_weights=weights)
        for th in new:
            q = th["phrase"]
            th["shop_links"] = [(label, link) for label, link in (
                ("See all on Myntra", await ek.make_link(store_search("Myntra", q))),
                ("See all on AJIO", await ek.make_link(store_search("AJIO", q))),
                ("Search on Amazon", amazon_search_link(q)),
            ) if link]
            await relink(ek, th)
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
        reel = reel_for(th)
        print(f"[Build] {th['title']}: {len(kept)} products, {len(pins)} pins, reel {'ok' if reel else 'failed'}")
        new_pins.append(pins)
        themes = [t for t in themes if t["slug"] != th["slug"]]
        themes.insert(0, th)

    queue += interleave(new_pins)
    save(THEMES_FILE, themes)
    save(QUEUE_FILE, queue)
    site.rebuild(themes)
    write_reels_feed(themes)
    build_kit(themes)
    write_plan(themes, queue, report)
    print(f"[Build] {sum(len(p) for p in new_pins)} pins queued")

    if os.getenv("PUBLISH", "1") == "1":
        if not commit_and_push(f"Weekly trends: {', '.join(t['title'] for t in themes if t['week'] == week)}",
                               ["data", "docs", "PLAN.md"]):
            print("[Build] Couldn't save this week's build to GitHub; not putting the website live.")
            return 1  # a red run, so the dashboard and GitHub's email flag it
        deploy_site(f"Weekly trends {week}")
        from trends.weekly import KIT_FILE, notify
        notify(load(KIT_FILE, {}))  # GitHub tells the owner the week's kit is ready to make
    return 0


def rebuild_reels() -> int:
    """python -m trends.build --reels : redo every current reel and the feed (no EarnKaro needed)."""
    themes = load(THEMES_FILE, [])
    for th in themes:
        if (Path("docs/ideas") / th["slug"]).exists():
            print(f"[Reels] {th['title']}: {'ok' if reel_for(th) else 'failed'}")
    write_reels_feed(themes)
    build_kit(themes)
    return 0


async def relink_current() -> int:
    """python -m trends.build --relink : product buttons of the ideas still being pinned become store
    searches (one EarnKaro login), then the site is rebuilt and published."""
    themes = load(THEMES_FILE, [])
    cutoff = datetime.now(IST) - timedelta(days=21)
    todo = [t for t in themes if datetime.fromisoformat(t["built_at"]) > cutoff
            and not all(p.get("search") for p in t["products"])]
    if todo:
        async with EarnKaroSession() as ek:
            for th in todo:
                await relink(ek, th)
    save(THEMES_FILE, themes)
    site.rebuild(themes)
    if os.getenv("PUBLISH", "1") == "1":
        if not commit_and_push("Product buttons open in-stock store searches", ["data", "docs"]):
            return 1
        deploy_site("Product buttons open in-stock store searches")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(rebuild_reels() if "--reels" in sys.argv
             else asyncio.run(relink_current()) if "--relink" in sys.argv else asyncio.run(main()))
