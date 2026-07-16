"""
pinterest_poster.py — Posts deal cards to Pinterest automatically.
Features:
- Logs in with saved session (avoids re-login every time)
- Creates "Hot Deals India" board if it doesn't exist
- Human-like random delays between actions
- Max 10 pins per day limit
- Only posts 9 AM – 9 PM IST
"""
import asyncio, os, json, random, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

PINTEREST_EMAIL    = os.getenv("PINTEREST_EMAIL", "")
PINTEREST_PASSWORD = os.getenv("PINTEREST_PASSWORD", "")
BOARD_NAME         = "Hot Deals India"
SESSION_FILE       = "pinterest_session.json"
PINS_LOG           = "pins_today.json"
MAX_PINS_PER_DAY   = 10
IST                = timezone(timedelta(hours=5, minutes=30))

# ── Helpers ────────────────────────────────────────────────────────────────

def is_posting_hours():
    """Only post 9 AM – 9 PM IST."""
    now = datetime.now(IST)
    return 9 <= now.hour < 21

def pins_today():
    """Count how many pins posted today."""
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        data = json.loads(Path(PINS_LOG).read_text())
        return sum(1 for p in data if p.get("date") == today)
    except:
        return 0

def log_pin(title):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        data = json.loads(Path(PINS_LOG).read_text())
    except:
        data = []
    data.append({"date": today, "title": title, "ts": datetime.now(IST).isoformat()})
    Path(PINS_LOG).write_text(json.dumps(data, indent=2))

# ── Pinterest session management ───────────────────────────────────────────
async def load_or_login(context):
    """Load saved cookies or do a fresh login."""
    if Path(SESSION_FILE).exists():
        cookies = json.loads(Path(SESSION_FILE).read_text())
        await context.add_cookies(cookies)
        print("  [AUTH] Loaded Pinterest session from file")
        return True

    print("  [AUTH] No session found - logging in...")
    page = await context.new_page()
    try:
        await page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded")
        await human_delay(2, 4)

        await page.fill('input[id="email"]', PINTEREST_EMAIL)
        await human_delay(0.5, 1.5)
        await page.fill('input[id="password"]', PINTEREST_PASSWORD)
        await human_delay(0.5, 1.5)
        await page.click('button[type="submit"]')
        await asyncio.sleep(15)  # Pinterest Business accounts take longer to redirect

        # Save session cookies
        cookies = await context.cookies()
        Path(SESSION_FILE).write_text(json.dumps(cookies))
        print("  [AUTH] Pinterest login successful, session saved")
        return True
    except Exception as e:
        print(f"  [ERR] Pinterest login failed: {e}")
        return False
    finally:
        await page.close()

async def ensure_board_exists(page):
    """Check if 'Hot Deals India' board exists, create it if not."""
    try:
        await page.goto(f"https://www.pinterest.com/{PINTEREST_EMAIL.split('@')[0]}/",
                        wait_until="domcontentloaded")
        await asyncio.sleep(3)
        content = await page.content()
        if BOARD_NAME.lower() in content.lower():
            print(f"  [BOARD] '{BOARD_NAME}' already exists")
            return True

        # Create board
        print(f"  [BOARD] Creating '{BOARD_NAME}'...")
        await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Click + button
        plus_btn = await page.query_selector('[data-test-id="header-create-button"]')
        if not plus_btn:
            plus_btn = await page.query_selector('button[aria-label="Create"]')
        if plus_btn:
            await plus_btn.click()
            await human_delay(1, 2)

            # Click "Create board"
            create_board = await page.query_selector('[data-test-id="create-board"]')
            if create_board:
                await create_board.click()
                await human_delay(1, 2)
                name_input = await page.query_selector('input[id="boardEditName"]')
                if name_input:
                    await name_input.fill(BOARD_NAME)
                    await human_delay(0.5, 1)
                    create_btn = await page.query_selector('[data-test-id="board-create-button"]')
                    if create_btn:
                        await create_btn.click()
                        await asyncio.sleep(3)
                        print(f"  [BOARD] Created '{BOARD_NAME}'")
                        return True
    except Exception as e:
        print(f"  [WARN] Board check failed: {e}")
    return True  # Continue even if board check fails

# ── Main: Post a pin ───────────────────────────────────────────────────────
async def post_pin(image_path: str, title: str, description: str, link: str) -> bool:
    """
    Upload a deal card as a Pinterest pin.
    Returns True if successful.
    """
    if not is_posting_hours():
        print(f"  [SKIP] Outside posting hours (9 AM-9 PM IST)")
        return False

    if pins_today() >= MAX_PINS_PER_DAY:
        print(f"  [SKIP] Daily limit reached ({MAX_PINS_PER_DAY} pins/day)")
        return False

    if not os.path.exists(image_path):
        print(f"  [ERR] Image not found: {image_path}")
        return False

    print(f"  [PIN] Posting to Pinterest: {title[:50]}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        logged_in = await load_or_login(context)
        if not logged_in:
            await browser.close()
            return False

        page = await context.new_page()

        try:
            # Navigate to pin creation
            await page.goto("https://in.pinterest.com/pin-creation-tool/", wait_until="domcontentloaded")
            await asyncio.sleep(8)

            # Upload image
            file_input = await page.query_selector('input[type="file"]')
            if not file_input:
                # Try clicking upload area
                upload_area = await page.query_selector('[data-test-id="storyboard-upload-section"]')
                if upload_area:
                    await upload_area.click(force=True)
                    await asyncio.sleep(1)
                file_input = await page.query_selector('input[type="file"]')

            if file_input:
                await file_input.set_input_files(os.path.abspath(image_path))
                print("  [PIN] Image uploaded")
                await asyncio.sleep(6)
            else:
                print("  [WARN] File input not found")
                await browser.close()
                return False

            # Fill title
            try:
                title_loc = page.get_by_placeholder("Tell everyone what your Pin is about", exact=False).first
                await title_loc.click(force=True, timeout=3000)
                await page.keyboard.type(title[:100])
                print("  [PIN] Title filled")
            except Exception as e:
                print(f"  [WARN] Title fail: {e}")

            await asyncio.sleep(1)

            # Fill description
            try:
                desc_loc = page.locator('[aria-label="Describe your Pin"]').first
                if not await desc_loc.count():
                    desc_loc = page.get_by_text("Describe your Pin", exact=False).first
                await desc_loc.click(force=True, timeout=3000)
                await page.keyboard.type(description[:500])
                print("  [PIN] Description filled")
            except Exception as e:
                print(f"  [WARN] Description fail: {e}")

            await asyncio.sleep(1)

            # Fill destination link
            try:
                link_loc = page.get_by_placeholder("Add a link", exact=False).first
                await link_loc.click(force=True, timeout=3000)
                await page.keyboard.type(link)
                print("  [PIN] Link filled")
            except Exception as e:
                print(f"  [WARN] Link fail: {e}")

            await asyncio.sleep(2)

            # Select board
            print("  [PIN] Handling board selection...")
            board_btn = page.locator('[data-test-id="board-dropdown-select-button"]')
            if not await board_btn.count():
                board_btn = page.get_by_text("Choose a board")
            
            if await board_btn.count():
                await board_btn.first.click(force=True)
                await asyncio.sleep(2)
                
                # Type board name in search box to filter
                board_search = page.locator('input[placeholder="Search"]')
                if not await board_search.count():
                    board_search = page.locator('[data-test-id="board-search-input"]')
                
                if await board_search.count():
                    await board_search.first.fill(BOARD_NAME)
                    await asyncio.sleep(2)
                
                # Check if board already exists in the search list
                board_option = page.get_by_text(BOARD_NAME, exact=True).first
                try:
                    await board_option.wait_for(timeout=3000)
                    await board_option.click(force=True)
                    print(f"  [PIN] Board '{BOARD_NAME}' selected!")
                except Exception:
                    # Create board if not found
                    print(f"  [PIN] Board '{BOARD_NAME}' not found in dropdown, creating...")
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
                            await page.keyboard.type(BOARD_NAME)
                            await asyncio.sleep(1)
                            
                            create_confirm = page.locator('[data-test-id="board-create-button"]').first
                            if not await create_confirm.count():
                                create_confirm = page.get_by_role("button", name="Create").first
                            
                            await create_confirm.wait_for(timeout=5000)
                            await create_confirm.click(force=True)
                            await asyncio.sleep(4)
                            print(f"  [PIN] Board '{BOARD_NAME}' created!")
                        else:
                            print("  [WARN] Board name input not found")
                    except Exception as e:
                        print(f"  [WARN] Create board step failed: {e}")
            else:
                print("  [WARN] Board dropdown button not found")

            # Publish
            print("  [PIN] Publishing...")
            publish_btn = page.get_by_role("button", name="Publish").first
            try:
                await publish_btn.click(force=True, timeout=5000)
                print("  [PIN] Published!")
            except Exception as e:
                print(f"  [WARN] Standard publish click failed: {e}")
                try:
                    publish_btn = page.locator('[data-test-id="board-dropdown-save-button"]').first
                    await publish_btn.click(force=True, timeout=5000)
                    print("  [PIN] Published via save-button locator!")
                except Exception as e2:
                    print(f"  [ERR] Fallback publish click failed: {e2}")
                    await browser.close()
                    return False

            await asyncio.sleep(8)
            log_pin(title)
            
            # Save updated cookies
            cookies = await context.cookies()
            Path(SESSION_FILE).write_text(json.dumps(cookies))
            await browser.close()
            return True

        except Exception as e:
            print(f"  [ERR] Pinterest post failed: {e}")
            await browser.close()
            return False

async def post_deal_to_pinterest(deal: dict) -> bool:
    """
    Full flow: generate card image + post to Pinterest.
    Called by telegram_watcher after publishing to website.
    """
    from deal_card import generate_deal_card
    from image_utils import fetch_and_save_image

    title    = deal.get("title", "Hot Deal")
    desc_raw = deal.get("desc", "")
    ts_now   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Generate a unique HTML anchor ID for this deal
    clean_ts = deal.get("timestamp", ts_now).replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
    deal_anchor_id = f"deal_{clean_ts}"
    
    # ── Safe Website Destination Link ──
    website_link = f"https://harshhaldankar.github.io/Getyourdeal/deals/#{deal_anchor_id}"

    # Pinterest description with hashtags
    price = ""
    import re
    m = re.search(r'(?:at|from)?\s*[₹]?\s*(\d[\d,]+)', title, re.IGNORECASE)
    if m: price = f"₹{m.group(1)}"

    description = (
        f"🔥 {title}\n"
        f"{'💰 ' + price + ' only!' if price else ''}\n\n"
        f"✅ Verified deal — view details and get it here:\n"
        f"👉 {website_link}\n\n"
        f"#deals #sale #offer #shopping #india #lootdeals #flipkart #myntra"
    )

    # ── Resolve product image or fetch fallback ──
    product_img = deal.get("image_path")
    prod_disk_path = None
    if product_img:
        if os.path.exists(product_img):
            prod_disk_path = product_img
        elif os.path.exists(os.path.join("docs", "deals", product_img)):
            prod_disk_path = os.path.join("docs", "deals", product_img)

    if not prod_disk_path:
        fallback_name = f"fallback_{ts_now}.jpg"
        fallback_disk_path = os.path.join("docs", "deals", "images", fallback_name)
        print(f"  [PIN] Product image missing from Telegram. Fetching fallback from search...")
        fetched = fetch_and_save_image(title, fallback_disk_path)
        if fetched and os.path.exists(fetched):
            prod_disk_path = fetched
            # Save the fallback image relative path in the deal dictionary so it updates on the website
            deal["image_path"] = f"images/{fallback_name}"

    # Generate card image
    card_img_path = f"pinterest_cards/card_{ts_now}.png"
    generate_deal_card(
        title=title, 
        affiliate_link=deal.get("affiliate_link", ""), 
        desc=desc_raw, 
        out_path=card_img_path,
        product_img_path=prod_disk_path
    )

    # Post to Pinterest with the spam-safe website link
    success = await post_pin(
        image_path=card_img_path,
        title=title[:100],
        description=description,
        link=website_link
    )
    return success


if __name__ == "__main__":
    # Quick test
    async def test():
        result = await post_deal_to_pinterest({
            "title": "New Balance Running Shoes at 2550",
            "affiliate_link": "https://fktr.in/vqJzKYG",
            "desc": "70% off on premium running shoes!"
        })
        print(f"Posted: {result}")
    asyncio.run(test())
