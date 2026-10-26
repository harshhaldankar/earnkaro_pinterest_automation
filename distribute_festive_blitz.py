import asyncio
import os
import json
import shutil
import urllib.request
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from shared.board_classifier import classify_category
from telegram_watcher import load_deals, save_deals, rebuild_website
from rebuild_rss import rebuild_clean_rss
from pipeline2.deal_card_generator import create_aesthetic_studio_pin

FESTIVE_TAGS = "#DiwaliSale #MyntraFestive #DiwaliShopping #GreatIndianFestival #DealsIndia #FestiveLoot"

def enrich_deal(raw_title, detail_url):
    """Generates high-conversion festive headline, description, and board."""
    t = raw_title.strip()
    t_lower = t.lower()
    
    if any(k in t_lower for k in ["ethnic", "kurti", "libas", "pataudi"]):
        festive_title = f"Diwali Special – {t.title()}"
        desc = f"Upgrade your festive wardrobe with authentic designer ethnic styles from Myntra. Limited-time Diwali mega price drop! {FESTIVE_TAGS} #EthnicWear #DiwaliOutfit"
        board = "Women's Fashion Deals"
    elif any(k in t_lower for k in ["bedsheet", "pillow", "container", "clock"]):
        festive_title = f"Home Festive Glow – {t.title()}"
        desc = f"Transform your home for the festival of lights! Premium home & living essentials at unmissable discounts on Myntra. {FESTIVE_TAGS} #HomeDecor #DiwaliGifts"
        board = "Home & Kitchen Deals"
    elif "watch" in t_lower:
        festive_title = f"Luxury Loot – {t.title()}"
        desc = f"Make a bold statement this festive season. Premium branded wristwatches at unbelievable festival prices. {FESTIVE_TAGS} #WatchLover #MensFashion"
        board = "Men's Fashion Deals"
    elif any(k in t_lower for k in ["beauty", "makeup", "perfume", "lakme", "nivea", "parachute", "deo"]):
        festive_title = f"Festive Glam – {t.title()}"
        desc = f"Get festival-ready glowing skin and signature fragrances. Top-tier beauty & personal care picks heavily discounted on Myntra! {FESTIVE_TAGS} #FestiveGlam #BeautyDeals"
        board = "Beauty & Skincare Finds"
    elif any(k in t_lower for k in ["trolley", "backpack", "safari"]):
        festive_title = f"Festive Travel Loot – {t.title()}"
        desc = f"Heading home for the holidays? Grab durable premium luggage and travel bags at massive seasonal discounts. {FESTIVE_TAGS} #TravelGear #DiwaliTravel"
        board = "Hot Deals India"
    elif any(k in t_lower for k in ["bear house", "clothing", "shirt", "jeans"]):
        festive_title = f"Festive Style Drop – {t.title()}"
        desc = f"Sharp festive casuals and premium apparel. Steal the spotlight at Diwali parties with top brand collections on Myntra. {FESTIVE_TAGS} #MensWear"
        board = "Men's Fashion Deals"
    else:
        festive_title = f"Festive Dhamaka – {t.title()}"
        desc = f"Exclusive Myntra Super Seller deal curated for the festive shopping season. Grab before stock runs out! {FESTIVE_TAGS} #OnlineShopping"
        board = classify_category(t)
        
    return festive_title, desc, board

def download_image(url, out_path):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp, open(out_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        return True
    except Exception as e:
        print(f"  [WARN] Image download failed ({url}): {e}", flush=True)
        return False

def push_and_deploy(commit_msg: str):
    """Pushes to both source repo and Getyourdeal live site."""
    print("\n" + "=" * 60, flush=True)
    print(f"[DEPLOY] Pushing commit: {commit_msg}", flush=True)
    print("=" * 60, flush=True)
    
    # 1. Source repo
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", "docs/", "deals_data.json"], check=True)
        if os.path.exists("pins_today.json"):
            subprocess.run(["git", "add", "pins_today.json"], check=True)
        res = subprocess.run(["git", "commit", "-m", commit_msg], capture_output=True, text=True)
        print(f"  [GIT] Commit result: {res.stdout.strip() or res.stderr.strip()}", flush=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print("  [GIT] Pushed to source repo successfully!", flush=True)
    except Exception as ge:
        print(f"  [GIT WARN] Source push notice: {ge}", flush=True)

    # 2. Deploy to Getyourdeal website repo
    token = os.getenv("WEBSITE_DEPLOY_TOKEN")
    if not token:
        print("  [DEPLOY] WEBSITE_DEPLOY_TOKEN not set. Skipped public site direct clone.", flush=True)
        return

    deploy_dir = "_website_deploy"
    try:
        if os.path.exists(deploy_dir):
            shutil.rmtree(deploy_dir, ignore_errors=True)
        repo = os.getenv("WEBSITE_REPO", "harshhaldankar/Getyourdeal")
        clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        print("  [DEPLOY] Cloning Getyourdeal website repo...", flush=True)
        subprocess.run(["git", "clone", "--depth", "1", clone_url, deploy_dir], check=True, capture_output=True)

        # Copy deals and docs
        print("  [DEPLOY] Syncing docs to live website repo...", flush=True)
        dest_deals = os.path.join(deploy_dir, "deals")
        if os.path.exists(dest_deals):
            shutil.rmtree(dest_deals, ignore_errors=True)
        shutil.copytree("docs/deals", dest_deals)

        for f in os.listdir("docs"):
            src_f = os.path.join("docs", f)
            if os.path.isfile(src_f) and f.endswith((".html", ".css", ".json", ".xml")):
                shutil.copy2(src_f, deploy_dir)

        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=deploy_dir, check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=deploy_dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=deploy_dir, check=True)
        diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=deploy_dir)
        if diff_res.returncode == 0:
            print("  [DEPLOY] No changes detected in public website repo.", flush=True)
        else:
            subprocess.run(["git", "commit", "-m", f"Festive update: {commit_msg}"], cwd=deploy_dir, check=True)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=deploy_dir, check=True)
            print("  ?? [DEPLOY SUCCESS] Live site deployed to harshhaldankar.github.io/Getyourdeal", flush=True)
    except Exception as de:
        print(f"  [DEPLOY WARN] Site deploy notice: {de}", flush=True)

async def main():
    print("=" * 70, flush=True)
    print("  ?? FESTIVE BLITZ: MYNTRA SUPER SELLERS OMNICHANNEL DISTRIBUTION", flush=True)
    print("=" * 70, flush=True)

    scraped_file = Path("earnkaro_super_sellers_scraped.json")
    if not scraped_file.exists():
        print("? Scraped file earnkaro_super_sellers_scraped.json not found!", flush=True)
        return

    cards = json.loads(scraped_file.read_text(encoding="utf-8"))
    print(f"Loaded {len(cards)} verified Myntra Super Seller deals.", flush=True)

    os.makedirs("docs/deals/images", exist_ok=True)
    os.makedirs("docs/deals/videos", exist_ok=True)

    existing_deals = load_deals()
    existing_links = {d.get("affiliate_link") for d in existing_deals if d.get("affiliate_link")}
    existing_titles = {d.get("title") for d in existing_deals if d.get("title")}

    new_deals_to_add = []
    reels_generated_count = 0

    for i, c in enumerate(cards, 1):
        raw_title = c.get("title", "")
        img_url = c.get("image_url", "")
        aff_link = c.get("affiliate_link", "")
        detail_url = c.get("detail_url", "")

        if not aff_link or not img_url:
            continue

        festive_title, festive_desc, target_board = enrich_deal(raw_title, detail_url)

        if aff_link in existing_links or festive_title in existing_titles:
            print(f"[{i}/{len(cards)}] [SKIP - Already Exists] {festive_title[:50]}", flush=True)
            continue

        print(f"\n[{i}/{len(cards)}] Processing: {festive_title}", flush=True)
        print(f"  Board: {target_board}", flush=True)
        print(f"  Affiliate: {aff_link}", flush=True)

        ts_now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"_{i:02d}"
        local_img_name = f"festive_myntra_{ts_now}.jpg"
        local_img_path = os.path.join("docs", "deals", "images", local_img_name)

        # 1. Download image
        ok = download_image(img_url, local_img_path)
        if not ok or not os.path.exists(local_img_path):
            print("  [SKIP] Failed to download banner image.", flush=True)
            continue

        # 2. Build high-end aesthetic studio pin for Pinterest
        studio_pin_name = f"pin_{local_img_name}"
        studio_pin_path = os.path.join("docs", "deals", "images", studio_pin_name)
        clean_pin = create_aesthetic_studio_pin(local_img_path, studio_pin_path, title=festive_title)
        final_img_path = studio_pin_name if (clean_pin and os.path.exists(clean_pin)) else local_img_name
        print(f"  ? [STUDIO PIN] Created: images/{final_img_path}", flush=True)

        # 3. Generate video reel for top 4 festive highlights (Instagram Reels)
        reel_url = ""
        is_reel_eligible = reels_generated_count < 4 and any(k in festive_title.lower() for k in [
            "ethnic", "libas", "pataudi", "watch", "bedsheet", "trolley"
        ])

        if is_reel_eligible:
            try:
                from pipeline2.reel_generator import create_reel, get_ffmpeg_cmd
                subprocess.run([get_ffmpeg_cmd(), "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("  [REEL] Rendering dynamic festive video reel...", flush=True)
                reel_path = create_reel(
                    local_img_path,
                    festive_title,
                    price="Hot Loot",
                    mrp="Special",
                    discount="Festive",
                    duration_sec=6.0,
                    fps=15
                )
                if reel_path and os.path.exists(reel_path):
                    reel_name = f"reel_festive_{ts_now}.mp4"
                    dest_reel_path = os.path.join("docs", "deals", "videos", reel_name)
                    shutil.copy(reel_path, dest_reel_path)
                    reel_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/videos/{reel_name}"
                    reels_generated_count += 1
                    print(f"  ?? [REEL OK] Generated: {reel_url}", flush=True)
            except Exception as re_err:
                print(f"  [WARN] Reel generation notice: {re_err}", flush=True)

        deal_record = {
            "title": festive_title,
            "desc": festive_desc,
            "image_path": f"images/{final_img_path}",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "affiliate_link": aff_link,
            "product_url": detail_url,
            "pinned": False,
            "board": target_board,
            "video_url": reel_url,
            "pipeline": "Festive Super Sellers"
        }

        new_deals_to_add.append(deal_record)

    print("\n" + "=" * 70, flush=True)
    print(f"Processed {len(new_deals_to_add)} NEW festive deals (with {reels_generated_count} video reels).", flush=True)
    print("=" * 70, flush=True)

    if not new_deals_to_add:
        print("No new deals to insert. Rebuilding site and RSS.", flush=True)
        rebuild_website(existing_deals)
        rebuild_clean_rss()
        return

    all_deals = new_deals_to_add + existing_deals
    all_deals = all_deals[:160]
    save_deals(all_deals)
    print(f"Updated deals_data.json with {len(all_deals)} total deals.", flush=True)

    # Rebuild website
    print("\n[WEB] Rebuilding Dribbble-style website...", flush=True)
    rebuild_website(all_deals)

    # Rebuild RSS feed
    print("\n[RSS] Rebuilding clean RSS feed with Media RSS & enclosures...", flush=True)
    rebuild_clean_rss()

    # Commit & Deploy
    push_and_deploy(f"Festive Blitz: {len(new_deals_to_add)} Myntra Super Sellers live")

if __name__ == "__main__":
    asyncio.run(main())
