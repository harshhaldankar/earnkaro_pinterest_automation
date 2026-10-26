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
    fetch_earnkaro_deals, categories_for_this_run, is_good_deal, pick_top, deal_title,
)
from pipeline2.dedup_engine import is_duplicate, register_posted_deal
from pipeline2.earnkaro_top_deals import MIN_DISCOUNT
from shared.live_price import refresh_deals, resolve_store_url, check_myntra

# Reuse P1 functions for website integration and Pinterest posting
from telegram_watcher import load_deals, save_deals, rebuild_website, push_to_github, MAX_DEALS

DEALS_PER_RUN = 5
# Only post products whose stock and price we can check live (Myntra). AJIO blocks every check,
# and EarnKaro's listing alone is often stale.
VERIFIED_STORES_ONLY = True
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
    paths = [os.path.join("docs", "deals", deal["image_path"])]
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
    name_only = re.sub(r"\s*@\s*₹.*$", "", deal["title"])
    out = create_product_reel(paths, os.path.join(VIDEOS_DIR, name), title=name_only,
                              price=f"₹{d['price']:,.0f}", mrp=f"₹{d['mrp']:,.0f}" if d["mrp"] > d["price"] else "",
                              discount=f"{d['discount']}%", store=d["store"])
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

    fresh = [d for d in products if is_good_deal(d) and not is_duplicate(d["link"])]
    if VERIFIED_STORES_ONLY:
        fresh = [d for d in fresh if "myntra" in d["store"].lower()]
    # Extra candidates so a failed image download or a live-check rejection doesn't leave the run short
    picks = pick_top(fresh, 40, per_category=3)
    print(f"[Pipeline 2] {len(products)} products, {len(fresh)} new good deals, posting up to {DEALS_PER_RUN}")

    db = load_deals()
    # Re-check everything posted in the last 14 days (both pipelines): live price, stock, expiry
    stats = refresh_deals(db, {p["id"].lower(): p for p in products})
    print(f"[Refresh] {stats['checked']} recent deals checked: {stats['updated']} price updates, "
          f"{stats['ended']} ended, {stats['unknown']} couldn't be checked")
    refreshed = stats["updated"] or stats["ended"]

    new_deals = []
    posted_per_cat = {}
    for d in picks:
        if len(new_deals) >= DEALS_PER_RUN:
            break
        if posted_per_cat.get(d["category_path"], 0) >= 2:  # keep boards varied
            continue
        # EarnKaro's listing still shows sold-out items at their old sale price (7 of 10 Myntra
        # deals posted on Oct 25-26 were out of stock a day later). Confirm live before posting.
        store_url = resolve_store_url(d["link"])
        if not store_url or "myntra.com" not in store_url:
            if VERIFIED_STORES_ONLY:
                print(f"  [SKIP] Can't verify stock on {d['store']} (blocks checks) — {d['name'][:50]}")
                continue
        else:
            live = check_myntra(store_url)
            if live is None:
                print(f"  [WARN] Myntra live check unavailable; using EarnKaro data — {d['name'][:50]}")
            elif not live["in_stock"] or live["discount"] < MIN_DISCOUNT:
                print(f"  [SKIP] Live check: {'out of stock' if not live['in_stock'] else str(live['discount']) + '% off now'} — {d['name'][:50]}")
                continue
            else:
                if live["price"] != d["price"]:
                    print(f"  [LIVE] Price ₹{d['price']:.0f} on EarnKaro -> ₹{live['price']} on Myntra")
                d.update(price=float(live["price"]), mrp=float(live["mrp"]), discount=live["discount"])
        d["store_url"] = store_url
        title = deal_title(d)
        print(f"\n[Pipeline 2] {title}  (earn ₹{d['commission']:.0f}/sale)")
        image_path = download_image(d["image"], d["id"])
        if not image_path:
            continue
        deal = {
            "title": title,
            "desc": f"{d['discount']}% off on {d['store']}: ₹{d['price']:,.0f} (MRP ₹{d['mrp']:,.0f}).",
            "image_path": image_path,
            # Unique per deal: the timestamp becomes the deal page URL
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "affiliate_link": d["link"],
            "product_url": d["link"],
            "mrp": f"{d['mrp']:.0f}",
            "discount_percent": d["discount"],
            "commission": d["commission"],
            "store_url": d.get("store_url"),
            "price_checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "pinned": False,
            "pipeline": 2,
        }
        db.insert(0, deal)
        new_deals.append((deal, d))
        posted_per_cat[d["category_path"]] = posted_per_cat.get(d["category_path"], 0) + 1

    if not new_deals:
        print("[Pipeline 2] Nothing new to post this run.")
        if refreshed:
            save_deals(db)
            rebuild_website(db)
            push_to_github(f"Pipeline 2: refreshed prices ({stats['updated']} updated, {stats['ended']} ended)")
        return 0

    # Instagram reels for the top deals (picks are ranked best-first); RSS marks them instagram_eligible
    for deal, d in new_deals[:REELS_PER_RUN]:
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
