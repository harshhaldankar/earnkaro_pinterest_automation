"""
pinterest.py - posts one pin to Pinterest through a logged-in browser (no API access needed).

  post_pin(image_path, title, description, link, board_name) -> bool
  check_session_health() -> bool

Uses pinterest_session.json (cookies). Posts only 7 AM - 11 PM IST, at most MAX_PINS_PER_DAY a day
(counted in pins_today.json). A board that doesn't exist yet is created.
"""
import asyncio, os, json, random, re, sys, socket, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from shared.doh_resolver import patch_dns
from shared.lock_manager import acquire_lock, release_lock
patch_dns()

load_dotenv()

# Manual environment parsing to ensure .env overrides are fully loaded
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


PINTEREST_EMAIL    = os.getenv("PINTEREST_EMAIL", "")
PINTEREST_PASSWORD = os.getenv("PINTEREST_PASSWORD", "")
SESSION_FILE       = "pinterest_session.json"
PINS_LOG           = "pins_today.json"
MAX_PINS_PER_DAY   = 15
IST                = timezone(timedelta(hours=5, minutes=30))

# ✅ BUG FIX: human_delay was called but never defined — caused NameError crash on every run
async def human_delay(min_s: float, max_s: float):
    """Wait a random human-like duration between min_s and max_s seconds."""
    await asyncio.sleep(random.uniform(min_s, max_s))

# ── Helpers ────────────────────────────────────────────────────────────────

def is_posting_hours():
    """Check IST time between 7 AM and 11 PM."""
    now_hour = datetime.now(IST).hour
    return 7 <= now_hour < 23

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

async def check_session_health():
    """Check if Pinterest session cookies are expired."""
    try:
        session_file = Path(SESSION_FILE)
        if not session_file.exists():
            print("[AUTH] Pinterest session file not found.")
            return False
            
        cookies = json.loads(session_file.read_text())
        
        # Critical authentication cookies: _auth and _pinterest_sess
        keys_to_check = ["_auth", "_pinterest_sess"]
        
        current_time = datetime.now(timezone.utc).timestamp()
        
        soonest_expiry = float('inf')
        
        for cookie in cookies:
            name = cookie.get("name")
            if name in keys_to_check:
                # _auth cookie value must be "1" (authenticated)
                if name == "_auth" and str(cookie.get("value", "")).strip() not in ["1", "true", "True"]:
                    print("[AUTH] Pinterest session _auth cookie is not logged in. Run: python refresh_pinterest_session.py")
                    return False
                expires = cookie.get("expires", -1)
                if expires != -1:
                    if expires < current_time:
                        print(f"[AUTH] Pinterest session EXPIRED ({name}). Run: python refresh_pinterest_session.py")
                        return False
                    if expires < soonest_expiry:
                        soonest_expiry = expires
                        
        if soonest_expiry != float('inf'):
            expiry_date = datetime.fromtimestamp(soonest_expiry, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"[AUTH] Pinterest session valid. Expires: {expiry_date}")
        else:
            print("[AUTH] Pinterest session valid. Expires: Unknown")
            
        return True
    except Exception as e:
        print(f"[AUTH] Error checking session health: {e}")
        return False

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

# Removed ensure_board_exists since it's hardcoded and unused directly

# ── Main: Post a pin ───────────────────────────────────────────────────────
async def post_pin(image_path: str, title: str, description: str, link: str, board_name: str, ignore_posting_hours: bool = False) -> bool:
    """
    Upload a deal card as a Pinterest pin.
    Returns True if successful.
    """
    if pins_today() >= MAX_PINS_PER_DAY: print('[PIN] Daily limit reached'); return False
    if not ignore_posting_hours and os.getenv("IGNORE_POSTING_HOURS", "").lower() not in ["1", "true"] and not is_posting_hours():
        print(f"  [SKIP] Outside posting hours (7 AM-11 PM IST)")
        return False

    if not os.path.exists(image_path):
        print(f"  [ERR] Image not found: {image_path}")
        return False

    print(f"  [PIN] Posting to Pinterest: {title[:50]}...")

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

                is_video = image_path.lower().endswith((".mp4", ".mov", ".m4v"))
                if file_input:
                    await file_input.set_input_files(os.path.abspath(image_path))
                    print(f"  [PIN] {'Video' if is_video else 'Image'} uploaded")
                    await asyncio.sleep(6)
                    if is_video:  # Pinterest processes a video before it can be published (up to ~3 min)
                        for _ in range(36):
                            btn = page.get_by_role("button", name="Publish").first
                            try:
                                if await btn.count() and await btn.is_enabled():
                                    break
                            except Exception:
                                pass
                            await asyncio.sleep(5)
                        print("  [PIN] Video processed")
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
                        await board_search.first.fill(board_name)
                        await asyncio.sleep(2)
                
                    # Check if board already exists in the search list
                    board_option = page.get_by_text(board_name, exact=True).first
                    try:
                        await board_option.wait_for(timeout=3000)
                        await board_option.click(force=True)
                        print(f"  [PIN] Board '{board_name}' selected!")
                    except Exception:
                        # Create board if not found
                        print(f"  [PIN] Board '{board_name}' not found in dropdown, creating...")
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
                                print(f"  [PIN] Board '{board_name}' created!")
                            else:
                                print("  [WARN] Board name input not found")
                        except Exception as e:
                            print(f"  [WARN] Create board step failed: {e}")
                            # Fix 4: Fallback — try to select "Hot Deals India" so the pin still gets posted
                            try:
                                await board_search.first.fill("Hot Deals India")
                                await asyncio.sleep(2)
                                fallback_option = page.get_by_text("Hot Deals India", exact=True).first
                                await fallback_option.wait_for(timeout=3000)
                                await fallback_option.click(force=True)
                                print(f"  [PIN] Fell back to 'Hot Deals India' board")
                            except Exception as fe:
                                print(f"  [WARN] Board fallback also failed: {fe}")
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

                await asyncio.sleep(25 if is_video else 8)  # a video pin keeps uploading after the click
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
    finally:
        if lock_file:
            release_lock(lock_file)
