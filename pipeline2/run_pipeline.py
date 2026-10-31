"""
Pipeline 2: EarnKaro top deals -> website -> Pinterest.

Reads EarnKaro's own category pages (every product is commission-eligible and comes with its
commission per sale), keeps the best niche deals, adds them to the website and pins them.
Replaces the old trend-scraping flow, which found 0 products from GitHub Actions
(Flipkart/AJIO returned nothing, Myntra served a captcha).
"""
import asyncio
import os
import re
import sys
from datetime import datetime, timezone

import requests

# Add project root to path for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# config.py auto-loads .env on import
import pipeline2.config

from shared.doh_resolver import patch_dns
patch_dns()

from pipeline2.earnkaro_top_deals import (
    fetch_earnkaro_deals, categories_for_this_run, is_good_deal, pick_top, deal_title, card_title, amazon_tagged,
)
from pipeline2.dedup_engine import is_duplicate, register_posted_deal
from pipeline2.earnkaro_top_deals import MIN_DISCOUNT
from shared.live_price import refresh_deals, resolve_store_url, check_myntra, check_amazon
from shared.board_classifier import site_section
from pipeline2.deal_card_generator import create_banner_pin

# Reuse P1 functions for website integration and Pinterest posting
from telegram_watcher import load_deals, save_deals, rebuild_website, push_to_github, MAX_DEALS

DEALS_PER_RUN = 5
# Of those, at most this many Amazon collections (EarnKaro's hand-picked Amazon category pages,
# linked with our own Associates tag). A collection can't sell out; single Amazon products can, and
# often can't be checked from GitHub, so they're skipped. Myntra products are posted only after a
# live stock check; AJIO blocks every check and EarnKaro's listing alone is often stale.
AMAZON_PER_RUN = 3
# Reels for the best deals only: 2 per run x 2 runs = MAX_INSTAGRAM_POSTS_PER_DAY (4), and each
# reel adds ~2 MB to the repo
REELS_PER_RUN = 2
IMAGES_DIR = os.path.join("docs", "deals", "images")
VIDEOS_DIR = os.path.join("docs", "deals", "videos")


def deal_id(timestamp: str) -> str:
    """Same id rebuild_rss.py uses to match a deal to reel_<id>.mp4."""
    ts = timestamp.replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
    return "deal_" + ts.split("+")[0].split("Z")[0]


def make_reel(deal: dict, d: dict) -> str | None:
    """Reel from all of the product's EarnKaro photos; returns the public video URL."""
    from pipeline2.product_reel import create_product_reel
    tmp_dir = os.path.join("cache", "reel_images")
    os.makedirs(tmp_dir, exist_ok=True)
    paths = [os.path.join("docs", "deals", deal.get("source_image") or deal["image_path"])]
    for i, url in enumerate(d.get("images", [])[1:4]):
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 5000:
                p = os.path.join(tmp_dir, f"{i}.jpg")
                with open(p, "wb") as f:
                    f.write(r.content)
                paths.append(p)
        except requests.RequestException:
            pass
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    name = f"reel_{deal_id(deal['timestamp'])}.mp4"
    from pinterest_poster import product_name
    price = f"₹{d['price']:,.0f}" if d["price"] else ""  # collections have no single price
    out = create_product_reel(paths, os.path.join(VIDEOS_DIR, name), title=product_name(deal["title"]),
                              price=price, mrp=f"₹{d['mrp']:,.0f}" if price and d["mrp"] > d["price"] else "",
                              discount=f"{d['discount']}%" if d["discount"] else "", store=d["store"])
    return f"https://harshhaldankar.github.io/Getyourdeal/deals/videos/{name}" if out else None


def download_image(url: str, deal_id: str) -> str | None:
    """Save the product image into the website; returns the docs/deals-relative path."""
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", deal_id)[:60]
    name = f"p2_{safe_id}.jpg"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 5000:
            print(f"  [SKIP] Image download failed ({r.status_code}, {len(r.content)} bytes)")
            return None
        os.makedirs(IMAGES_DIR, exist_ok=True)
        with open(os.path.join(IMAGES_DIR, name), "wb") as f:
            f.write(r.content)
        return f"images/{name}"
    except requests.RequestException as e:
        print(f"  [SKIP] Image download failed: {e}")
        return None


async def main() -> int:
    print("=" * 60)
    print("[Pipeline 2] EarnKaro Top Deals -> Pinterest")
    print("=" * 60)

    cats = categories_for_this_run()
    print(f"[Pipeline 2] Categories this run: {', '.join(cats)}")
    try:
        products = await fetch_earnkaro_deals(cats)
    except Exception as e:
        print(f"[Pipeline 2] FATAL: Could not read EarnKaro: {e}")
        return 1
    if not products:
        print("[Pipeline 2] FATAL: EarnKaro returned no products (login or page format changed?)")
        return 1

    # Myntra products (stock must be confirmed live) and EarnKaro's hand-picked Amazon cards
    myntra = [d for d in products if not d.get("kind") and is_good_deal(d) and not is_duplicate(d["link"])
              and "myntra" in d["store"].lower()]
    amazon = [d for d in products if d.get("kind") == "collection" and not is_duplicate(d["link"])
              and site_section(card_title(d))[0] != "more"]
    # Extra candidates so a failed image download or a live-check rejection doesn't leave the run short
    picks = amazon + pick_top(myntra, 40, per_category=3)
    print(f"[Pipeline 2] {len(products)} products: {len(myntra)} new Myntra deals, {len(amazon)} new Amazon collections; "
          f"posting up to {DEALS_PER_RUN} ({AMAZON_PER_RUN} Amazon)")

    db = load_deals()
    # Re-check everything posted in the last 14 days (both pipelines): live price, stock, expiry
    stats = refresh_deals(db, {p["id"].lower(): p for p in products})
    print(f"[Refresh] {stats['checked']} recent deals checked: {stats['updated']} price updates, "
          f"{stats['ended']} ended, {stats['unknown']} couldn't be checked")
    refreshed = stats["updated"] or stats["ended"]

    new_deals = []
    posted_per_section = {}
    amazon_posted = 0
    myntra_unreachable = 0
    now = lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for d in picks:
        if len(new_deals) >= DEALS_PER_RUN:
            break
        kind = d.get("kind")
        if kind and amazon_posted >= AMAZON_PER_RUN:
            continue
        if not kind and myntra_unreachable >= 3:
            continue  # Myntra blocks checks from here; don't keep asking
        title = card_title(d) if kind else deal_title(d)
        section = site_section(title)[0]
        if posted_per_section.get(section, 0) >= 2:  # keep boards varied
            continue
        store_url = resolve_store_url(d["link"])
        if not store_url:
            print(f"  [SKIP] Couldn't resolve the store link — {d['name'][:50]}")
            continue
        verified = False
        if kind == "collection":
            store_url = amazon_tagged(store_url)
        elif kind == "product":
            live = check_amazon(store_url)
            if live and not live["in_stock"]:
                print(f"  [SKIP] Amazon: out of stock — {d['name'][:50]}")
                continue
            if live:
                verified = True
                if live["price"] != d["price"]:
                    print(f"  [LIVE] Amazon price ₹{d['price']:.0f} on the card -> ₹{live['price']}")
                    d.update(price=float(live["price"]))
                    if live["mrp"]:
                        d.update(mrp=float(live["mrp"]))
                    d.update(discount=round((1 - d["price"] / d["mrp"]) * 100) if d["mrp"] > d["price"] else 0)
                    title = card_title(d)
            # No answer from Amazon: EarnKaro featuring the card right now is the signal (6 of 7 such
            # cards were in stock at the card price on Oct 31); it ends when the card is taken down
        elif not kind:
            # EarnKaro's listing still shows sold-out Myntra items at their old sale price
            # (33 of 46 posted Oct 27-30 were out of stock). Confirm live before posting.
            live = check_myntra(store_url)
            if live is None:
                myntra_unreachable += 1
                print(f"  [SKIP] Myntra stock check unavailable, not posting unverified — {d['name'][:50]}")
                continue
            myntra_unreachable = 0
            if not live["in_stock"] or live["discount"] < MIN_DISCOUNT:
                print(f"  [SKIP] Live check: {'out of stock' if not live['in_stock'] else str(live['discount']) + '% off now'} — {d['name'][:50]}")
                continue
            if live["price"] != d["price"]:
                print(f"  [LIVE] Price ₹{d['price']:.0f} on EarnKaro -> ₹{live['price']} on Myntra")
            d.update(price=float(live["price"]), mrp=float(live["mrp"]), discount=live["discount"])
            title = deal_title(d)
            verified = True
        d["store_url"] = store_url
        print(f"\n[Pipeline 2] {title}  (earn ₹{d['commission']:.0f}/sale)")
        image_path = download_image(d["image"], d["id"])
        if not image_path:
            continue
        deal = {
            "title": title,
            "desc": (f"{d['discount']}% off on {d['store']}: ₹{d['price']:,.0f} (MRP ₹{d['mrp']:,.0f})." if d["price"]
                     else f"{d['name']} on {d['store']}."),
            "image_path": image_path,
            # Unique per deal: the timestamp becomes the deal page URL
            "timestamp": now(),
            # Amazon collections link straight to Amazon with our own tag; the rest via EarnKaro
            "affiliate_link": store_url if kind == "collection" else d["link"],
            "product_url": store_url if kind == "collection" else d["link"],
            "earnkaro_id": d["id"].lower(),
            "mrp": f"{d['mrp']:.0f}" if d["mrp"] else "",
            "discount_percent": d["discount"],
            "commission": d["commission"],
            "store_url": store_url,
            "pinned": False,
            "pipeline": 2,
        }
        if verified:
            deal["price_checked_at"] = now()
        if kind == "collection":
            # Collection cards are wide banners: pin and site get the full-width banner layout,
            # the reel keeps the plain banner
            src = os.path.join(IMAGES_DIR, os.path.basename(image_path))
            if create_banner_pin(src, src.replace(".jpg", "_pin.jpg")):
                deal["source_image"] = image_path
                deal["image_path"] = image_path.replace(".jpg", "_pin.jpg")
        if kind:
            deal["last_listed_at"] = now()
            amazon_posted += 1
        db.insert(0, deal)
        new_deals.append((deal, d))
        posted_per_section[section] = posted_per_section.get(section, 0) + 1

    if not new_deals:
        print("[Pipeline 2] Nothing new to post this run.")
        if refreshed:
            save_deals(db)
            rebuild_website(db)
            push_to_github(f"Pipeline 2: refreshed prices ({stats['updated']} updated, {stats['ended']} ended)")
        return 0

    # Instagram reels: product-photo deals first, then Amazon collections (made from their banner)
    for deal, d in sorted(new_deals, key=lambda x: bool(x[1].get("kind")))[:REELS_PER_RUN]:
        try:
            url = make_reel(deal, d)
            if url:
                deal["video_url"] = url
                print(f"  [REEL] {url}")
        except Exception as e:
            print(f"  [REEL WARN] Reel failed for {deal['title'][:50]}: {e}")

    db = db[:MAX_DEALS]
    save_deals(db)
    rebuild_website(db)  # deal pages must exist: each pin links to its deal page

    pinned = 0
    try:
        from pinterest_poster import post_deal_to_pinterest, check_session_health
        if not await check_session_health():
            print("[PINTEREST] Session DEAD — run: python refresh_pinterest_session.py")
        else:
            for deal, d in new_deals:
                try:
                    if await post_deal_to_pinterest(deal):
                        deal["pinned"] = True
                        pinned += 1
                        print(f"  [OK] Pinned: {deal['title'][:60]}")
                        await asyncio.sleep(8)  # human-like delay between pins
                    else:
                        print(f"  [SKIP] Could not pin (daily limit or posting hours?): {deal['title'][:60]}")
                except Exception as e:
                    print(f"  [ERR] Pin failed: {e}")
    except Exception as e:
        print(f"[PINTEREST WARN] Pinterest posting block failed: {e}")

    # Register only after the deal is live on the site, so a failed run can retry it
    for deal, d in new_deals:
        register_posted_deal(d["link"], pipeline=2, boards=["Pinterest"] if deal["pinned"] else [])
    save_deals(db)

    try:
        from rebuild_rss import rebuild_clean_rss
        rebuild_clean_rss()
    except Exception as e:
        print(f"[RSS Rebuild WARN] {e}")

    push_to_github(f"Pipeline 2: {len(new_deals)} EarnKaro top deals, {pinned} pinned")
    print("=" * 60)
    print(f"[Pipeline 2] Finished: {len(new_deals)} deals added, {pinned} pinned.")
    print("=" * 60)
    return 0


async def main_with_timeout() -> int:
    """Wrap main with a timeout so a hung browser can't block the shared CI queue"""
    try:
        return await asyncio.wait_for(main(), timeout=1500)
    except asyncio.TimeoutError:
        print("[Pipeline 2] ERROR: Pipeline exceeded 25-minute timeout.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main_with_timeout()))
