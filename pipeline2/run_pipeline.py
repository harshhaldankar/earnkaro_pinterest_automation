import asyncio
import sys
import os
import time
import signal
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError

# Add project root to path for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# config.py auto-loads on import
import pipeline2.config

from shared.doh_resolver import patch_dns
patch_dns()

from shared.lock_manager import acquire_lock, release_lock
from pipeline2.pinterest_trending import scrape_pinterest_trending
from pipeline2.trend_matcher import match_trends_to_products
from pipeline2.profit_filter import filter_by_profit
from pipeline2.dedup_engine import dedup_against_all, register_posted_deal
from pipeline2.affiliate_linker import generate_affiliate_link
from pipeline2.image_fetcher import fetch_and_validate_image
from pipeline2.deal_card_generator import generate_deal_cards
from pipeline2.pinterest_multi_board import post_to_pinterest
from pipeline2.instagram_poster import post_to_instagram
from shared.board_classifier import classify_category

# Reuse P1 functions for website integration
from telegram_watcher import load_deals, save_deals, rebuild_website, push_to_github, MAX_DEALS

async def main():
    print("=" * 60)
    print("[Pipeline 2] Starting Autonomous Trending Arbitrage Pipeline")
    print("=" * 60)

    # 1. Initialize Telethon for EarnKaro Bot
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = os.getenv("TELEGRAM_SESSION")
    
    if not api_id or not api_hash or not session:
        print("[Pipeline 2] FATAL: Missing Telegram API credentials in .env")
        return
        
    # Try connecting with retry logic to handle AuthKeyDuplicatedError
    MAX_RETRIES = 3
    client = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[Pipeline 2] Connecting to Telegram (attempt {attempt}/{MAX_RETRIES})...")
            client = TelegramClient(StringSession(session), int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                print("[Pipeline 2] FATAL: Telegram session invalid/expired.")
                await client.disconnect()
                return
            print("[Pipeline 2] Connected to Telegram.")
            break  # Success — exit retry loop
        except AuthKeyDuplicatedError:
            print(f"[Pipeline 2] AuthKeyDuplicatedError on attempt {attempt}. A previous run may still be active.")
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            client = None
            if attempt < MAX_RETRIES:
                wait_secs = 30 * attempt  # 30s, 60s, 90s backoff
                print(f"[Pipeline 2] Waiting {wait_secs}s before retry...")
                await asyncio.sleep(wait_secs)
            else:
                print("[Pipeline 2] FATAL: Could not connect after all retries. Regenerate TELEGRAM_SESSION secret.")
                return
        except Exception as e:
            print(f"[Pipeline 2] Unexpected error connecting to Telegram: {e}")
            return
    
    if client is None:
        print("[Pipeline 2] FATAL: Client failed to initialize.")
        return

    # 2. Get Trending Keywords
    trends = await scrape_pinterest_trending()
    if not trends:
        print("[Pipeline 2] No trends found. Exiting.")
        return
        
    # 3. Match Trends to Products
    deals = await match_trends_to_products(trends)
    if not deals:
        print("[Pipeline 2] No products found matching trends. Exiting.")
        return
        
    # 4. Filter by Profit
    profitable_deals = filter_by_profit(deals)
    
    # 5. Deduplicate against Pipeline 1 and past runs
    unique_deals = dedup_against_all(profitable_deals)
    
    if not unique_deals:
        print("[Pipeline 2] No unique profitable deals found. Exiting.")
        return
        
    posted_deals_count = 0

    for deal in unique_deals:
        try:
            print(f"\n[Pipeline 2] Processing: {deal.title}")
        
            try:
                affiliate_url = await asyncio.wait_for(
                    generate_affiliate_link(client, deal), 
                    timeout=30  # 30-second timeout per link
                )
            except asyncio.TimeoutError:
                print(f"  ***Linker*** Timeout generating affiliate link (exceeded 30s)")
                continue
            except Exception as e:
                print(f"  ***Linker*** Error: {e}")
                continue
            if not affiliate_url:
                print(f"  [SKIP] Failed to generate affiliate link.")
                continue
            deal.affiliate_url = affiliate_url
        
            # 7. Fetch & Validate Image
            local_img = await fetch_and_validate_image(deal)
            if not local_img:
                print(f"  [SKIP] Failed to fetch or validate image.")
                continue
            
            # 8. Generate Deal Cards
            cards = generate_deal_cards(deal, local_img)
            pin_card = cards.get("pinterest")
            ig_card = cards.get("ig_square")
        
            if not pin_card or not os.path.exists(pin_card):
                print(f"  [SKIP] Failed to generate Pinterest card.")
                continue
            
            # Ensure it has a high discount for high conversion
            try:
                if float(deal.discount_percent) < 50:
                    print(f"  [SKIP] Discount too low ({deal.discount_percent}%). Seeking highly trending massive deals (>= 50%).")
                    continue
            except:
                pass
            
            # 9. Copy Deal Card to Website
            import shutil
            website_img_name = f"p2_{os.path.basename(pin_card)}"
            website_img_path = os.path.join("docs", "deals", "images", website_img_name)
            os.makedirs(os.path.dirname(website_img_path), exist_ok=True)
            shutil.copy(pin_card, website_img_path)
            
            website_img_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/images/{website_img_name}"
            
            # 10. Generate Reel (Only for the first 2 top-tier deals for Instagram)
            reel_url = ""
            is_instagram = posted_deals_count < 2
            
            if is_instagram:
                try:
                    import subprocess
                    from pipeline2.reel_generator import create_reel, get_ffmpeg_cmd
                    subprocess.run([get_ffmpeg_cmd(), "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    reel_path = create_reel(
                        local_img, 
                        str(deal.title), 
                        str(deal.price), 
                        str(deal.mrp), 
                        str(deal.discount_percent)
                    )
                    if reel_path and os.path.exists(reel_path):
                        # Copy to docs to make it public
                        website_video_name = f"reel_p2_{os.path.basename(reel_path)}"
                        website_video_path = os.path.join("docs", "deals", "videos", website_video_name)
                        os.makedirs(os.path.dirname(website_video_path), exist_ok=True)
                        shutil.copy(reel_path, website_video_path)
                        reel_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/videos/{website_video_name}"
                        print(f"  [SUCCESS] Reel generated: {reel_url}")
                except Exception as e:
                    print(f"  [SKIP] Reel generation skipped: {e}")
                    
                # Post directly to Instagram via instagrapi
                try:
                    ig_media = reel_path if (reel_path and os.path.exists(reel_path)) else ig_card
                    post_type = "reel" if (reel_path and os.path.exists(reel_path)) else "feed"
                    if ig_media and os.path.exists(ig_media):
                        print(f"  [INSTAGRAM] Posting {post_type} to Instagram: {deal.title[:50]}...")
                        await post_to_instagram([deal], [ig_media], post_type=post_type)
                except Exception as e:
                    print(f"  [INSTAGRAM WARN] Direct Instagram post failed: {e}")
                
            from datetime import datetime, timezone
            ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                
            clean_ts = ts_now.replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
            deal_anchor_id = f"deal_{clean_ts}"
            website_deal_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{deal_anchor_id}/"
            
            # 11. Add to RSS Feed
            from pipeline2.rss_generator import add_deal_to_rss
            from shared.board_classifier import classify_category
            board_name = classify_category(deal.title)
            desc = f"Trending {deal.category} deal! Get it now at ₹{deal.price} (was ₹{deal.mrp}). {deal.discount_percent}% OFF."
            add_deal_to_rss(
                title=deal.title,
                website_url=website_deal_url,
                video_url=reel_url,
                description=desc,
                image_url=website_img_url,
                instagram_eligible=bool(reel_url),
                affiliate_link=deal.affiliate_url,
                category=board_name,
                board=board_name
            )
        
            # 12. Register in Dedup Engine & Add to Website Database
            register_posted_deal(deal.product_url, pipeline=2, boards=["RSS Feed"])
            posted_deals_count += 1
        
            website_deal = {
                "title": deal.title,
                "desc": desc,
                "image_path": f"images/{website_img_name}",
                "timestamp": ts_now,
                "affiliate_link": deal.affiliate_url,
                "product_url": deal.product_url,
                "pinned": True,
                "pipeline": 2
            }
        
            db = load_deals()
            db.insert(0, website_deal)
            db = db[:MAX_DEALS]
            save_deals(db)
            rebuild_website(db)
                
            # Limit to 10 successful deals per run for Pinterest/Website (but only 2 go to Instagram)
            if posted_deals_count >= 10:
                print("[Pipeline 2] Reached run limit of 10 deals.")
                break

        except asyncio.CancelledError:
            print(f"  [ERROR] Processing cancelled for {deal.title}")
            break
        except Exception as e:
            print(f"  [ERROR] Unexpected error processing {deal.title}: {e}")
            continue

    if posted_deals_count > 0:
        push_to_github(f"Pipeline 2: Added {posted_deals_count} trending deals & Reels")
        
    await client.disconnect()
    print("=" * 60)
    print(f"[Pipeline 2] Finished. Successfully processed {posted_deals_count} deals.")
    print("=" * 60)


async def main_with_timeout():
    """Wrap main with timeout to prevent hanging tasks"""
    try:
        # Set a 15-minute timeout for the entire pipeline
        await asyncio.wait_for(main(), timeout=900)
    except asyncio.TimeoutError:
        print("[Pipeline 2] ERROR: Pipeline exceeded 15-minute timeout. Exiting gracefully.")
        sys.exit(1)
    except asyncio.CancelledError:
        print("[Pipeline 2] ERROR: Pipeline was cancelled. Cleaning up...")
        sys.exit(1)
    except Exception as e:
        print(f"[Pipeline 2] ERROR: Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main_with_timeout())
    except KeyboardInterrupt:
        print("[Pipeline 2] Pipeline interrupted by user.")
        sys.exit(1)
