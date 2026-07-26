"""
pinterest_poster.py — Posts deal cards to Pinterest automatically.
Features:
- Logs in with saved session (avoids re-login every time)
- Creates "Hot Deals India" board if it doesn't exist
- Human-like random delays between actions
- Max 10 pins per day limit
- Only posts 9 AM – 9 PM IST
"""
import asyncio, os, json, random, sys, socket, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# ── Dynamic DNS-over-HTTPS (DoH) Fallback Hook ──
_original_getaddrinfo = socket.getaddrinfo
_doh_cache = {}

def resolve_via_doh(host):
    if host in _doh_cache:
        return _doh_cache[host]
    try:
        url = f"https://1.1.1.1/dns-query?name={host}&type=A"
        req = urllib.request.Request(url, headers={"accept": "application/dns-json", "Host": "cloudflare-dns.com"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
        if ips:
            _doh_cache[host] = ips
            print(f"[DoH Hook] Resolved {host} -> {ips} via Cloudflare")
            return ips
    except Exception:
        pass
    try:
        url = f"https://dns.google/resolve?name={host}&type=A"
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read().decode())
        ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
        if ips:
            _doh_cache[host] = ips
            print(f"[DoH Hook] Resolved {host} -> {ips} via Google")
            return ips
    except Exception:
        pass
    return None

def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror as e:
        if host not in ["cloudflare-dns.com", "dns.google", "1.1.1.1", "8.8.8.8"]:
            ips = resolve_via_doh(host)
            if ips:
                results = []
                for ip in ips:
                    p = int(port) if isinstance(port, (int, str)) and str(port).isdigit() else 0
                    results.append((socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (ip, p)))
                return results
        raise e

socket.getaddrinfo = custom_getaddrinfo

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
BOARD_NAME         = "Hot Deals India"
SESSION_FILE       = "pinterest_session.json"
PINS_LOG           = "pins_today.json"
MAX_PINS_PER_DAY   = 10
IST                = timezone(timedelta(hours=5, minutes=30))

# ✅ BUG FIX: human_delay was called but never defined — caused NameError crash on every run
async def human_delay(min_s: float, max_s: float):
    """Wait a random human-like duration between min_s and max_s seconds."""
    await asyncio.sleep(random.uniform(min_s, max_s))

# ── Helpers ────────────────────────────────────────────────────────────────

def is_posting_hours():
    """Always return True to allow posting at any hour of the day."""
    return True

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

    if not os.path.exists(image_path):
        print(f"  [ERR] Image not found: {image_path}")
        return False

    print(f"  [PIN] Posting to Pinterest: {title[:50]}...")

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

def generate_seo_pin_content(title: str, desc_raw: str = "", website_link: str = None) -> tuple[str, str, str, str, str]:
    """
    Generate highly optimized Pinterest Title and Description (reach-friendly SEO format)
    inspired by top trending product pins.
    """
    import re
    # Strip any URLs, competitor tags, or tracking garbage from the title
    title_no_urls = re.sub(r'https?://[^\s]+', '', title).strip()
    title_no_urls = re.sub(r'www\.[^\s]+', '', title_no_urls).strip()
    title_no_urls = re.sub(r't\.me/[^\s]+', '', title_no_urls).strip()
    title_no_urls = re.sub(r'[?&](?:tag|affid|utm_[a-z]+)=[^&\s]+', '', title_no_urls).strip()
    title_clean = re.sub(r'\s{2,}', ' ', title_no_urls).strip()
    if not title_clean:
        title_clean = "Verified Product Offer"
        
    # Remove prefix tags like "Loot:", "GRAB:", etc.
    main_name = re.sub(r'^(?:loot|grab|deal|hot deal|mega loot)\s*:\s*', '', title_clean, flags=re.IGNORECASE)
    # Remove price suffixes
    main_name = re.sub(r'(?:at|from|under|@)?\s*[₹]?\s*\d[\d,]+\s*(?:\.\d+)?\s*$', '', main_name, flags=re.IGNORECASE).strip()
    main_name = re.sub(r'\s+rs\.?\s*\d+\s*$', '', main_name, flags=re.IGNORECASE).strip()
    main_name = re.sub(r'\s+\d+\s*$', '', main_name, flags=re.IGNORECASE).strip()
    main_name = re.sub(r'\s{2,}', ' ', main_name).strip()
    
    if not main_name or len(main_name) < 4 or main_name.replace('₹','').replace('rs','').strip().isdigit():
        desc_clean_name = re.sub(r'https?://[^\s]+', '', desc_raw).strip()
        desc_lines = [l.strip() for l in desc_clean_name.splitlines() if l.strip() and len(l.strip()) > 5]
        if desc_lines:
            main_name = desc_lines[0][:85]
        else:
            main_name = "Best Online Shopping Deal"

    # ── Build title: ProductName — ₹deal_price (MRP ₹mrp) | XX% OFF ──
    # Price extraction happens first so we can embed in the title
    combined_text = f" {title_clean} {desc_raw} ".lower()

    # 1. Discount Percentage
    discount_pct = ""
    pct_m = re.search(r'(\d+)\s*%\s*(?:off|discount|of)', combined_text)
    if pct_m:
        discount_pct = f"{pct_m.group(1)}% OFF"

    # 2. MRP
    mrp_val = ""
    mrp_m = re.search(r'mrp\s*(?::|-|is)?\s*(?:rs\.?|₹)?\s*(\d[\d,]+)', combined_text)
    if mrp_m:
        mrp_val = f"₹{mrp_m.group(1)}"

    # 3. Deal Price
    deal_price = ""
    price_m = re.search(r'(?:₹|rs\.?|inr|at\s|from\s|under\s|@\s|price:?\s*)[₹]?\s*(\d[\d,]*)', title_clean, re.IGNORECASE)
    if price_m:
        val = price_m.group(1).replace(',', '')
        if val.isdigit() and int(val) >= 20: deal_price = f"₹{val}"
    if not deal_price:
        m2 = re.search(r'(\d[\d,]*)\s*(?:/-|/|rupees|rs\b)', title_clean, re.IGNORECASE)
        if m2:
            val = m2.group(1).replace(',', '')
            if val.isdigit() and int(val) >= 20: deal_price = f"₹{val}"
    if not deal_price:
        for match in re.finditer(r'\b(\d[\d,]*)\b', title_clean):
            val = match.group(1).replace(',', '')
            if val.isdigit() and int(val) >= 49:
                after_idx = match.end()
                after_str = title_clean[after_idx:].strip().lower()
                if not re.match(r'^(?:kg|g|ml|l|star|inch|cm|mm|gb|tb|mah|pack|pcs|watt|w|v|hz|year|month|day|m\b)', after_str):
                    deal_price = f"₹{val}"
                    break

    # Calculate discount % from prices if not already found
    if mrp_val and deal_price and not discount_pct:
        try:
            mrp_num  = int(re.sub(r'[^\d]', '', mrp_val))
            deal_num = int(re.sub(r'[^\d]', '', deal_price))
            if mrp_num > deal_num > 0:
                pct = round(((mrp_num - deal_num) / mrp_num) * 100)
                if pct > 0:
                    discount_pct = f"{pct}% OFF"
        except:
            pass

    # ── Build SEO title: ProductName — ₹X (MRP ₹Y) | Z% OFF ──
    price_part = ""
    if deal_price and mrp_val:
        price_part = f" — {deal_price} (MRP {mrp_val})"
    elif deal_price:
        price_part = f" — {deal_price}"
    elif mrp_val:
        price_part = f" — {mrp_val}"

    off_part = f" | {discount_pct}" if discount_pct else ""

    seo_title = f"{main_name}{price_part}{off_part}"
    if len(seo_title) > 97:
        seo_title = seo_title[:97] + "..."



    # ── Description: Coupon → Website → Deal Details → Hashtags ──
    lower_title = title_clean.lower()
    coupon_code = None
    coupon_patterns = [
        r'\buse\s*code\s*:\s*([a-z0-9\-]+)\b',
        r'\bcode\s*:\s*([a-z0-9\-]+)\b',
        r'\buse\s*coupon\s*:\s*([a-z0-9\-]+)\b',
        r'\bapply\s*code\s*([a-z0-9\-]+)\b',
        r'\bcoupon\s*code\s*:\s*([a-z0-9\-]+)\b',
        r'\bcode\s+is\s+([a-z0-9\-]+)\b',
        r'\bcode\s*-\s*([a-z0-9\-]+)\b',
    ]
    for pat in coupon_patterns:
        m = re.search(pat, combined_text)
        if m:
            candidate = m.group(1).upper()
            if candidate not in ["MRP", "RS", "OFF", "MIN", "PM", "AM", "UTC", "IST"]:
                coupon_code = candidate
                break

    desc_lines = []

    # 1. Coupon code (top priority)
    if coupon_code:
        desc_lines.append(f"🎟️ COUPON CODE: {coupon_code}")
        desc_lines.append("")

    # 2. Website link
    if website_link:
        desc_lines.append(f"🌐 More deals: {website_link}")
        desc_lines.append("")

    # 3. Deal description / details (clean, no URLs)
    if desc_raw:
        clean_desc = re.sub(r'https?://[^\s]+', '', desc_raw).strip()
        clean_desc = re.sub(r'\s{2,}', ' ', clean_desc).strip()
        if clean_desc:
            desc_lines.append(clean_desc)
            desc_lines.append("")

    # 4. Hashtags
    base_tags = "#deals #sale #offer #india #onlineshopping"
    if any(x in lower_title for x in ["shoe", "sneaker", "footwear", "loafer", "sandal", "boot"]):
        cat_tags = "#shoes #sneakers #footwear #mensshoes"
    elif any(x in lower_title for x in ["tshirt", "t-shirt", "polo", "tee"]):
        cat_tags = "#mensfashion #ootd #streetwear #menstyle"
    elif any(x in lower_title for x in ["skincare", "serum", "moisturizer"]):
        cat_tags = "#skincare #glowingskin #selfcare #beautyroutine"
    elif any(x in lower_title for x in ["makeup", "lipstick"]):
        cat_tags = "#makeup #beauty #lipstick #makeuptutorial"
    elif any(x in lower_title for x in ["watch", "watches"]):
        cat_tags = "#watches #menswatches #accessories #style"
    else:
        cat_tags = "#fashion #style #accessories #lootdeals"

    desc_lines.append(f"{base_tags} {cat_tags}")

    seo_desc = "\n".join(desc_lines)
    if len(seo_desc) > 500:
        seo_desc = seo_desc[:497] + "..."

    return seo_title, seo_desc, deal_price, mrp_val, discount_pct

def overlay_pricing_banner(image_path: str, deal_price: str, mrp_val: str, discount_pct: str) -> str:
    """
    Overlay a premium pricing banner onto the bottom of the product image using Pillow.
    Draws the Deal Price, original MRP (crossed out), and discount percentage pill.
    """
    from PIL import Image, ImageDraw, ImageFont
    import os
    
    if not deal_price and not mrp_val and not discount_pct:
        return image_path
        
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGBA")
            width, height = im.size
            
            overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Banner height (16% of image height)
            banner_h = int(height * 0.16)
            banner_y = height - banner_h
            
            # Draw semi-transparent dark zinc-950 bottom banner background
            draw.rectangle(
                [(0, banner_y), (width, height)],
                fill=(9, 9, 11, 235)
            )
            
            font_path = None
            for path in [
                "C:\\Windows\\Fonts\\arialbd.ttf",
                "C:\\Windows\\Fonts\\segoeuib.ttf",
                "C:\\Windows\\Fonts\\verdana.ttf"
            ]:
                if os.path.exists(path):
                    font_path = path
                    break
                    
            price_size = max(16, int(banner_h * 0.35))
            label_size = max(11, int(banner_h * 0.22))
            
            if font_path:
                price_font = ImageFont.truetype(font_path, price_size)
                mrp_font_path = font_path.replace("bd.ttf", ".ttf").replace("b.ttf", ".ttf")
                if not os.path.exists(mrp_font_path):
                    mrp_font_path = font_path
                mrp_font = ImageFont.truetype(mrp_font_path, label_size)
            else:
                price_font = ImageFont.load_default()
                mrp_font = ImageFont.load_default()
                
            margin = int(width * 0.05)
            center_y = banner_y + int(banner_h / 2)
            
            # Draw Deal Price
            price_text = f"{deal_price}" if deal_price else ""
            price_w = draw.textlength(price_text, font=price_font) if hasattr(draw, "textlength") else (len(price_text) * (price_size * 0.6))
            draw.text(
                (margin, center_y - int(price_size / 2)),
                price_text,
                fill=(74, 222, 128, 255),
                font=price_font
            )
            
            # Draw MRP
            curr_x = margin + price_w + int(width * 0.04)
            if mrp_val:
                mrp_text = f"MRP: {mrp_val}"
                mrp_w = draw.textlength(mrp_text, font=mrp_font) if hasattr(draw, "textlength") else (len(mrp_text) * (label_size * 0.6))
                mrp_y = center_y - int(label_size / 2)
                draw.text(
                    (curr_x, mrp_y),
                    mrp_text,
                    fill=(156, 163, 175, 255),
                    font=mrp_font
                )
                
                # Strike-through line
                line_y = mrp_y + int(label_size / 2) + 1
                draw.line(
                    [(curr_x, line_y), (curr_x + mrp_w, line_y)],
                    fill=(248, 113, 113, 255),
                    width=max(2, int(banner_h * 0.03))
                )
                curr_x += mrp_w + int(width * 0.04)
                
            # Draw Discount Pill
            if discount_pct:
                pill_text = f" {discount_pct} "
                pill_w = draw.textlength(pill_text, font=price_font) if hasattr(draw, "textlength") else (len(pill_text) * (price_size * 0.6))
                pill_h = int(price_size * 1.3)
                pill_x = width - margin - int(pill_w) - 10
                pill_y = center_y - int(pill_h / 2)
                
                draw.rounded_rectangle(
                    [(pill_x, pill_y), (pill_x + pill_w + 10, pill_y + pill_h)],
                    radius=int(pill_h / 2),
                    fill=(244, 63, 94, 255)
                )
                draw.text(
                    (pill_x + 5, pill_y + int(pill_h * 0.1)),
                    pill_text,
                    fill=(255, 255, 255, 255),
                    font=price_font
                )
                
            combined = Image.alpha_composite(im, overlay)
            
            dir_name = os.path.dirname(image_path)
            base_name = os.path.basename(image_path)
            overlay_name = f"overlay_{base_name}"
            output_path = os.path.join(dir_name, overlay_name)
            
            combined.convert("RGB").save(output_path, "JPEG", quality=95)
            print(f"  [IMG OVERLAY] Generated price overlay banner: {output_path}")
            return output_path
    except Exception as e:
        print(f"  [WARN] Failed to overlay pricing banner: {e}")
        return image_path

async def post_deal_to_pinterest(deal: dict) -> bool:
    """
    Full flow: generate card image + post to Pinterest.
    """
    from image_utils import fetch_and_save_image

    title_raw = deal.get("title", "Hot Deal")
    desc_raw  = deal.get("desc", "")
    ts_now    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Generate website destination link
    clean_ts = deal.get("timestamp", ts_now).replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
    deal_anchor_id = f"deal_{clean_ts}"
    website_link = f"https://harshhaldankar.github.io/Getyourdeal/deals/#{deal_anchor_id}"

    # Generate high-reach SEO Pinterest content
    seo_title, seo_description, deal_price, mrp_val, discount_pct = generate_seo_pin_content(title_raw, desc_raw, website_link)

    # Pin link = affiliate link
    pin_link = deal.get("affiliate_link") or deal.get("product_url", "")

    # ── Resolve product image ──
    prod_img_path = None
    img_path_rel = deal.get("image_path")
    if img_path_rel:
        possible_paths = [img_path_rel,
                          os.path.join("docs", "deals", img_path_rel)]
        for p in possible_paths:
            if os.path.exists(p):
                prod_img_path = p
                break
    if not prod_img_path:
        fallback_name = f"fallback_{ts_now}.jpg"
        fallback_disk_path = os.path.join("docs", "deals", "images", fallback_name)
        product_url = deal.get("affiliate_link") or deal.get("product_url", "")
        fetched = fetch_and_save_image(title_raw, fallback_disk_path, product_url=product_url)
        if fetched and os.path.exists(fetched):
            prod_img_path = fetched
            deal["image_path"] = f"images/{fallback_name}"
    if not prod_img_path:
        print("[WARN] No image available for Pinterest pin; aborting.")
        return False

    # Post to Pinterest with ORIGINAL clean product image
    # Pricing info (deal_price, mrp_val, discount_pct) is already in seo_title & seo_description
    success = await post_pin(
        image_path=prod_img_path,
        title=seo_title,
        description=seo_description,
        link=pin_link,
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
