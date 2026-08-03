import asyncio
import os
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import async_playwright
import re

from shared.lock_manager import acquire_lock, release_lock
from pipeline2.config import INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_SESSION_FILE, MAX_INSTAGRAM_POSTS_PER_DAY
from pipeline2.trend_matcher import ProductDeal

IST = timezone(timedelta(hours=5, minutes=30))
IG_LOG = "ig_posts_today.json"

CAPTIONS = [
    "Steal this deal before it's gone! 😱🔥\n\nShop link in bio or story!\n{title}\n\nPrice drop: ₹{price} (was ₹{mrp})",
    "Massive {discount}% OFF on {title}! 🤯\n\nLink in bio to shop.\nOnly ₹{price} today!",
    "Deal of the day! ✨\n{title} is now just ₹{price}.\n\nCheck the link in our bio to grab yours! 🛍️",
    "Don't miss out on this! 🚨\n{title} at {discount}% OFF.\n\nLink is in the bio. Happy shopping! 💸",
    "Huge price drop alert! 📉\nGet {title} for ₹{price} (MRP: ₹{mrp}).\n\nLink in bio!",
    "Absolute steal! 🏃‍♀️💨\n{title} is {discount}% off today.\n\nShop via the link in our bio."
]

HASHTAG_SETS = [
    "#shopping #deals #india #sale #onlineshopping #discount",
    "#fashion #beauty #lifestyle #lootdeals #offers #style",
    "#trending #musthave #shopnow #dealalert #price_drop #shoppingonline"
]

PEAK_HOURS = [9, 12, 14, 18, 20, 21]

async def human_delay(min_s: float = 3.0, max_s: float = 8.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def human_type(element, text: str):
    for char in text:
        await element.type(char, delay=random.randint(30, 120))
        
def check_ig_limit() -> bool:
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        if Path(IG_LOG).exists():
            data = json.loads(Path(IG_LOG).read_text())
            count = sum(1 for p in data if p.get("date") == today)
            return count < MAX_INSTAGRAM_POSTS_PER_DAY
    except Exception:
        pass
    return True

def log_ig_post(title: str):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    data = []
    if Path(IG_LOG).exists():
        try:
            data = json.loads(Path(IG_LOG).read_text())
        except:
            pass
    data.append({"date": today, "title": title, "ts": datetime.now(IST).isoformat()})
    Path(IG_LOG).write_text(json.dumps(data, indent=2))

async def load_or_login(context):
    if Path(INSTAGRAM_SESSION_FILE).exists():
        try:
            cookies = json.loads(Path(INSTAGRAM_SESSION_FILE).read_text())
            await context.add_cookies(cookies)
            return True
        except: pass

    print("[Instagram P2] Logging in...")
    page = await context.new_page()
    try:
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        await human_delay(4, 7)
        
        await page.fill('input[name="username"]', INSTAGRAM_USERNAME)
        await human_delay(1, 3)
        await page.fill('input[name="password"]', INSTAGRAM_PASSWORD)
        await human_delay(1, 3)
        await page.click('button[type="submit"]')
        
        # Wait for home page to load
        await page.wait_for_selector('svg[aria-label="New post"]', timeout=30000)
        print("[Instagram P2] Login successful.")
        
        cookies = await context.cookies()
        Path(INSTAGRAM_SESSION_FILE).write_text(json.dumps(cookies))
        return True
    except Exception as e:
        print(f"[Instagram P2] Login failed: {e}")
        return False
    finally:
        await page.close()

async def post_to_instagram(deals: list[ProductDeal], image_paths: list[str]):
    """Posts a single image (for simplicity) or carousel if multiple."""
    if not deals or not image_paths:
        return False
        
    if not check_ig_limit():
        print("[Instagram P2] Daily limit reached. Skipping.")
        return False
        
    # Check peak hours (optional enforcement, could just bypass in Actions if scheduled correctly)
    current_hour = datetime.now(IST).hour
    if current_hour not in PEAK_HOURS:
        print(f"[Instagram P2] Current hour {current_hour} is not in peak hours. Proceeding anyway but note this.")

    deal = deals[0]
    image_path = image_paths[0]
    
    print(f"[Instagram P2] Posting: {deal.title[:50]}...")
    
    lock_file = None
    try:
        lock_file = acquire_lock("instagram.lock")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 414, "height": 896}, # Mobile viewport
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
            )
            
            if not await load_or_login(context):
                await browser.close()
                return False

            page = await context.new_page()
            
            # Go to home and random scroll to look human
            await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            await human_delay(3, 6)
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 300)")
                await human_delay(1, 2)
                
            # Click New Post (Plus icon)
            new_post_btn = page.locator('svg[aria-label="New post" i], svg[aria-label="New Post" i], svg[aria-label="Create" i], a[href*="/create"]').first
            if not await new_post_btn.count():
                new_post_btn = page.get_by_role("menuitem", name=re.compile("New post|Create", re.IGNORECASE)).first
                
            if await new_post_btn.count():
                async with page.expect_file_chooser() as fc_info:
                    await new_post_btn.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(os.path.abspath(image_path))
            else:
                print("[Instagram P2] Could not find New Post button.")
                await browser.close()
                return False
                
            await human_delay(4, 7)
            
            # Click Next twice (skip filters)
            for _ in range(2):
                next_btn = page.get_by_text("Next").first
                if not await next_btn.count():
                    next_btn = page.locator('div[role="button"]:has-text("Next")').first
                if await next_btn.count():
                    await next_btn.click()
                    await human_delay(2, 4)
            
            # Type caption
            caption_template = random.choice(CAPTIONS)
            caption_text = caption_template.format(
                title=deal.title, 
                price=deal.price, 
                mrp=deal.mrp, 
                discount=deal.discount_percent
            )
            caption_text += "\n\n" + random.choice(HASHTAG_SETS)
            
            caption_area = page.locator('div[aria-label="Write a caption..."]').first
            if await caption_area.count():
                await caption_area.click()
                await human_type(caption_area, caption_text)
                await human_delay(2, 4)
                
            # Share
            share_btn = page.get_by_text("Share").first
            if await share_btn.count():
                await share_btn.click()
                print("[Instagram P2] Share button clicked, waiting for upload...")
                await human_delay(10, 15)
                log_ig_post(deal.title)
            else:
                print("[Instagram P2] Share button not found.")
                
            cookies = await context.cookies()
            Path(INSTAGRAM_SESSION_FILE).write_text(json.dumps(cookies))
            
            await browser.close()
            return True
            
    except Exception as e:
        print(f"[Instagram P2] Error: {e}")
        return False
    finally:
        if lock_file:
            release_lock(lock_file)
