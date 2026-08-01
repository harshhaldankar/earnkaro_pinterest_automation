import asyncio
import os
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

from shared.lock_manager import acquire_lock, release_lock
from pipeline2.config import PINTEREST_EMAIL, PINTEREST_PASSWORD, PINTEREST_SESSION_FILE, PINS_LOG_P2, MAX_PINS_PER_DAY_P2
from pipeline2.trend_matcher import ProductDeal

IST = timezone(timedelta(hours=5, minutes=30))

async def human_delay(min_s: float = 8.0, max_s: float = 15.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

def check_daily_limit() -> bool:
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        if Path(PINS_LOG_P2).exists():
            data = json.loads(Path(PINS_LOG_P2).read_text())
            count = sum(1 for p in data if p.get("date") == today)
            return count < MAX_PINS_PER_DAY_P2
    except Exception:
        pass
    return True

def log_pin(title: str, board_name: str):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    data = []
    if Path(PINS_LOG_P2).exists():
        try:
            data = json.loads(Path(PINS_LOG_P2).read_text())
        except:
            pass
    data.append({"date": today, "title": title, "board": board_name, "ts": datetime.now(IST).isoformat()})
    Path(PINS_LOG_P2).write_text(json.dumps(data, indent=2))

async def load_or_login(context):
    if Path(PINTEREST_SESSION_FILE).exists():
        try:
            cookies = json.loads(Path(PINTEREST_SESSION_FILE).read_text())
            await context.add_cookies(cookies)
            return True
        except:
            pass

    print("[Pinterest P2] Logging in...")
    page = await context.new_page()
    try:
        await page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded")
        await human_delay(2, 4)
        await page.fill('input[id="email"]', PINTEREST_EMAIL)
        await human_delay(1, 2)
        await page.fill('input[id="password"]', PINTEREST_PASSWORD)
        await human_delay(1, 2)
        await page.click('button[type="submit"]')
        await asyncio.sleep(15)
        
        cookies = await context.cookies()
        Path(PINTEREST_SESSION_FILE).write_text(json.dumps(cookies))
        return True
    except Exception as e:
        print(f"[Pinterest P2] Login failed: {e}")
        return False
    finally:
        await page.close()

async def post_to_pinterest(deal: ProductDeal, board_name: str, pin_image_path: str):
    if not check_daily_limit():
        print("[Pinterest P2] Daily limit reached. Skipping.")
        return False

    print(f"[Pinterest P2] Posting to '{board_name}': {deal.title[:50]}...")
    
    lock_file = None
    try:
        lock_file = acquire_lock("pinterest.lock")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--enable-features=DnsOverHttps",
                    "--dns-over-https-templates=https://cloudflare-dns.com/dns-query"
                ]
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 900})
            
            if not await load_or_login(context):
                await browser.close()
                return False

            page = await context.new_page()
            
            await page.goto("https://in.pinterest.com/pin-creation-tool/", wait_until="domcontentloaded")
            await asyncio.sleep(8)
            
            # Upload Image
            file_input = await page.query_selector('input[type="file"]')
            if not file_input:
                upload_area = await page.query_selector('[data-test-id="storyboard-upload-section"]')
                if upload_area:
                    await upload_area.click(force=True)
                    await asyncio.sleep(1)
                file_input = await page.query_selector('input[type="file"]')
                
            if file_input:
                await file_input.set_input_files(os.path.abspath(pin_image_path))
                await asyncio.sleep(6)
            else:
                print("[Pinterest P2] File input not found.")
                await browser.close()
                return False
                
            # Title
            title_str = f"{deal.title} — ₹{deal.price} (MRP ₹{deal.mrp}) | {deal.discount_percent}% OFF"
            try:
                title_loc = page.get_by_placeholder("Tell everyone what your Pin is about", exact=False).first
                await title_loc.click(force=True, timeout=3000)
                await page.keyboard.type(title_str[:100])
            except Exception: pass
            await asyncio.sleep(1)
            
            # Description
            desc_str = f"Get {deal.discount_percent}% OFF on {deal.title}. Now at ₹{deal.price}! Shop the latest trends. #deals #shopping #fashion #india"
            try:
                desc_loc = page.locator('[aria-label="Describe your Pin"]').first
                if not await desc_loc.count():
                    desc_loc = page.get_by_text("Describe your Pin", exact=False).first
                await desc_loc.click(force=True, timeout=3000)
                await page.keyboard.type(desc_str[:500])
            except Exception: pass
            await asyncio.sleep(1)
            
            # Link
            pin_link = deal.affiliate_url or deal.product_url
            try:
                link_loc = page.get_by_placeholder("Add a link", exact=False).first
                await link_loc.click(force=True, timeout=3000)
                await page.keyboard.type(pin_link)
            except Exception: pass
            await asyncio.sleep(2)
            
            # Board Selection
            board_btn = page.locator('[data-test-id="board-dropdown-select-button"]')
            if not await board_btn.count():
                board_btn = page.get_by_text("Choose a board")
                
            if await board_btn.count():
                await board_btn.first.click(force=True)
                await asyncio.sleep(2)
                
                board_search = page.locator('input[placeholder="Search"]')
                if not await board_search.count():
                    board_search = page.locator('[data-test-id="board-search-input"]')
                    
                if await board_search.count():
                    await board_search.first.fill(board_name)
                    await asyncio.sleep(2)
                    
                board_option = page.get_by_text(board_name, exact=True).first
                try:
                    await board_option.wait_for(timeout=3000)
                    await board_option.click(force=True)
                except Exception:
                    # Create board
                    create_btn = page.get_by_text("Create board").first
                    try:
                        await create_btn.wait_for(timeout=5000)
                        await create_btn.click(force=True)
                        await asyncio.sleep(3)
                        
                        name_input = page.locator('input[id="boardEditName"]').first
                        if not await name_input.count():
                            name_input = page.locator('input[placeholder*="board name" i]').first
                            
                        if await name_input.count():
                            await name_input.click(force=True)
                            await asyncio.sleep(0.5)
                            await page.keyboard.type(board_name)
                            await asyncio.sleep(1)
                            
                            create_confirm = page.locator('[data-test-id="board-create-button"]').first
                            if not await create_confirm.count():
                                create_confirm = page.get_by_role("button", name="Create").first
                            
                            await create_confirm.wait_for(timeout=5000)
                            await create_confirm.click(force=True)
                            await asyncio.sleep(4)
                    except Exception as e:
                        print(f"[Pinterest P2] Create board failed: {e}")
            
            # Publish
            publish_btn = page.get_by_role("button", name="Publish").first
            try:
                await publish_btn.click(force=True, timeout=5000)
            except Exception:
                try:
                    publish_btn = page.locator('[data-test-id="board-dropdown-save-button"]').first
                    await publish_btn.click(force=True, timeout=5000)
                except Exception as e:
                    print(f"[Pinterest P2] Publish failed: {e}")
                    await browser.close()
                    return False
                    
            await human_delay(8, 15) # Wait for it to settle
            
            log_pin(deal.title, board_name)
            
            cookies = await context.cookies()
            Path(PINTEREST_SESSION_FILE).write_text(json.dumps(cookies))
            
            await browser.close()
            return True
            
    except Exception as e:
        print(f"[Pinterest P2] Error: {e}")
        return False
    finally:
        if lock_file:
            release_lock(lock_file)
