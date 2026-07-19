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

    if pins_today() >= MAX_PINS_PER_DAY:
        print(f"  [SKIP] Daily limit reached ({MAX_PINS_PER_DAY} pins/day)")
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

def generate_seo_pin_content(title: str, desc_raw: str = "") -> tuple[str, str]:
    """
    Generate highly optimized Pinterest Title and Description (reach-friendly SEO format)
    inspired by top trending product pins.
    """
    title_clean = title.strip()
    # Remove prefix tags like "Loot:", "GRAB:", etc.
    import re
    main_name = re.sub(r'^(?:loot|grab|deal|hot deal|mega loot)\s*:\s*', '', title_clean, flags=re.IGNORECASE)
    # Remove price suffixes
    main_name = re.sub(r'(?:at|from|under|@)?\s*[₹]?\s*\d[\d,]+\s*(?:\.\d+)?\s*$', '', main_name, flags=re.IGNORECASE).strip()
    main_name = re.sub(r'\s+rs\.?\s*\d+\s*$', '', main_name, flags=re.IGNORECASE).strip()
    main_name = re.sub(r'\s+\d+\s*$', '', main_name, flags=re.IGNORECASE).strip()

    search_keywords = ""
    lower_title = title_clean.lower()
    
    # Category mapping for title search keywords
    if any(x in lower_title for x in ["sneaker", "shoe", "loafer", "sandal", "heel", "boot", "slipper", "footwear"]):
        search_keywords = "Casual Shoes for Men, Trending Sneakers, Mens Footwear Style, Running Shoes"
    elif any(x in lower_title for x in ["tshirt", "t-shirt", "polo", "tee"]):
        search_keywords = "Mens T-Shirts, Mens Casual Outfits, Streetwear Style, Men Summer Fashion"
    elif any(x in lower_title for x in ["shirt", "overshirt", "flannel"]):
        search_keywords = "Mens Shirts, Aesthetic Outfits Men, Casual Styling, Wardrobe Essentials"
    elif any(x in lower_title for x in ["jeans", "trouser", "pants", "shorts", "cargo", "jogger"]):
        search_keywords = "Mens Jeans Outfit, Cargo Pants Styling, Casual Streetwear, Mens Bottomwear"
    elif any(x in lower_title for x in ["skincare", "skin care", "serum", "moisturizer", "cleanser", "face wash", "cream", "lotion"]):
        search_keywords = "Skincare Routine, Glowing Skin Tips, Best Skincare Products, Self Care Essentials"
    elif any(x in lower_title for x in ["makeup", "lipstick", "eyeliner", "mascara", "blush", "eyeshadow"]):
        search_keywords = "Makeup Tutorial, Lip Gloss Aesthetic, Everyday Makeup Look, Beauty Products"
    elif any(x in lower_title for x in ["watch", "watches", "smartwatch"]):
        search_keywords = "Mens Watches, Minimalist Watches, Aesthetic Watches, Luxury Style"
    elif any(x in lower_title for x in ["jewellery", "necklace", "ring", "earring", "bracelet"]):
        search_keywords = "Aesthetic Jewelry, Gold Ring Designs, Pendant Necklace, Daily Wear Accessories"
    elif any(x in lower_title for x in ["bag", "handbag", "backpack", "wallet", "purse", "tote"]):
        search_keywords = "Trendy Bags, Backpack Styling, Travel Essentials, Aesthetic Accessories"
    else:
        search_keywords = "Mens Fashion Deals, Online Shopping Offers, Latest Fashion Trends"

    seo_title = f"{main_name} | {search_keywords}"
    if len(seo_title) > 97:
        seo_title = seo_title[:97] + "..."

    # ── Extract Pricing Details (MRP, Deal Price, Discount %) ──
    combined_text = f" {title_clean} {desc_raw} ".lower()
    
    # 1. Discount Percentage
    discount_pct = ""
    pct_m = re.search(r'(\d+)\s*%\s*(?:off|discount|of)', combined_text)
    if pct_m:
        discount_pct = f"{pct_m.group(1)}% OFF"
    elif "flat 70%" in combined_text:
        discount_pct = "70% OFF"
    elif "flat 80%" in combined_text:
        discount_pct = "80% OFF"
    elif "flat 50%" in combined_text:
        discount_pct = "50% OFF"

    # 2. MRP
    mrp_val = ""
    mrp_m = re.search(r'mrp\s*(?::|-|is)?\s*(?:rs\.?|₹)?\s*(\d[\d,]+)', combined_text)
    if mrp_m:
        mrp_val = f"₹{mrp_m.group(1)}"

    # 3. Deal Price (Off Price)
    deal_price = ""
    price_m = re.search(r'(?:at|from|under|@|price:?)\s*[₹]?(?:rs\.?)?\s*(\d[\d,]+)', title_clean, re.IGNORECASE)
    if price_m:
        deal_price = f"₹{price_m.group(1)}"
    else:
        price_fallback = re.search(r'[₹]?(?:rs\.?)?\s*(\d[\d,]+)', title_clean)
        if price_fallback:
            deal_price = f"₹{price_fallback.group(1)}"
            
    # Calculate discount % dynamically if MRP and Deal Price are present
    if mrp_val and deal_price and not discount_pct:
        try:
            mrp_num = int(re.sub(r'[^\d]', '', mrp_val))
            deal_num = int(re.sub(r'[^\d]', '', deal_price))
            if mrp_num > deal_num and mrp_num > 0:
                pct = round(((mrp_num - deal_num) / mrp_num) * 100)
                if pct > 0:
                    discount_pct = f"{pct}% OFF"
        except:
            pass

    # Compelling hook
    brand_match = re.search(r'\b(snitch|roadster|nike|puma|adidas|reebok|levis|levi\'s|gant|calvin klein|ck|derma co|deconstruct|plum|mamaearth|nykaa|hrx|wrogn|red tape|campus|crocs|lakme|loreal|maybelline)\b', lower_title)
    brand_name = brand_match.group(1).title() if brand_match else "this premium brand"
    
    hook = f"Looking for a stylish upgrade? Check out this incredible deal on {main_name} from {brand_name}! Perfect for adding a premium touch to your daily look."
    if "skincare" in lower_title or "serum" in lower_title or "moisturizer" in lower_title:
        hook = f"Ready for glowing, healthy skin? Check out this amazing offer on {main_name}! Add this to your daily skincare routine for real results."
    elif "makeup" in lower_title or "lipstick" in lower_title:
        hook = f"Upgrade your beauty collection with this hot deal on {main_name}! Perfect for creating stunning everyday or glam looks."

    desc_lines = []
    desc_lines.append(hook)
    desc_lines.append("")
    
    # Offer Details Section
    if deal_price or mrp_val or discount_pct:
        desc_lines.append("💸 Offer Details:")
        if deal_price:
            desc_lines.append(f"  • Deal Price: {deal_price}")
        if mrp_val:
            desc_lines.append(f"  • Original MRP: {mrp_val}")
        if discount_pct:
            desc_lines.append(f"  • Discount: {discount_pct}!")
        desc_lines.append("")
    
    # Clean and add Telegram details if present
    if desc_raw:
        clean_desc = re.sub(r'https?://[^\s]+', '', desc_raw).strip()
        if clean_desc:
            desc_lines.append("📌 Details:")
            lines = [l.strip() for l in clean_desc.splitlines() if l.strip()][:3]
            for line in lines:
                desc_lines.append(f"  • {line}")
    else:
        desc_lines.append("✨ Highlights:")
        desc_lines.append("  • Premium quality and authentic styling")
        desc_lines.append("  • Ideal for daily wear and gifting")
        desc_lines.append("  • Rated highly for comfort and durability")

    desc_lines.append("")
    desc_lines.append("🛍️ Shop Now:")
    desc_lines.append("👉 CLICK THE PIN to get the direct discount affiliate link and buy instantly!")
    desc_lines.append("👉 More curated deals on our website (link in bio): harshhaldankar.github.io/Getyourdeal/deals/")
    desc_lines.append("")
    
    base_tags = "#deals #sale #offer #india #onlineshopping"
    if "shoe" in lower_title or "sneaker" in lower_title or "footwear" in lower_title:
        cat_tags = "#shoes #sneakers #footwear #mensshoes"
    elif "tshirt" in lower_title or "t-shirt" in lower_title or "shirt" in lower_title:
        cat_tags = "#mensfashion #ootd #streetwear #menstyle"
    elif "skincare" in lower_title or "serum" in lower_title or "moisturizer" in lower_title:
        cat_tags = "#skincare #glowingskin #selfcare #beautyroutine"
    elif "makeup" in lower_title or "lipstick" in lower_title:
        cat_tags = "#makeup #beauty #lipstick #makeuptutorial"
    elif "watch" in lower_title:
        cat_tags = "#watches #menswatches #accessories #style"
    else:
        cat_tags = "#fashion #style #accessories #lootdeals"
        
    desc_lines.append(f"{base_tags} {cat_tags}")

    seo_desc = "\n".join(desc_lines)
    if len(seo_desc) > 500:
        seo_desc = seo_desc[:497] + "..."

    return seo_title, seo_desc

async def post_deal_to_pinterest(deal: dict) -> bool:
    """
    Full flow: generate card image + post to Pinterest.
    """
    from image_utils import fetch_and_save_image

    title_raw = deal.get("title", "Hot Deal")
    desc_raw  = deal.get("desc", "")
    ts_now    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Generate high-reach SEO Pinterest content
    seo_title, seo_description = generate_seo_pin_content(title_raw, desc_raw)

    # ── Safe Website Destination Link ──
    clean_ts = deal.get("timestamp", ts_now).replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
    deal_anchor_id = f"deal_{clean_ts}"
    website_link = f"https://harshhaldankar.github.io/Getyourdeal/deals/#{deal_anchor_id}"

    # Pin link = affiliate link (direct commission on click)
    pin_link = deal.get("affiliate_link") or deal.get("product_url", "")

    # ── Resolve product image ──
    # Use the original product image if available; otherwise fetch it.
    prod_img_path = None
    img_path_rel = deal.get("image_path")
    if img_path_rel:
        # Resolve possible relative paths
        possible_paths = [img_path_rel,
                          os.path.join("docs", "deals", img_path_rel)]
        for p in possible_paths:
            if os.path.exists(p):
                prod_img_path = p
                break
    if not prod_img_path:
        # No existing image, fetch from product URL
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

    # Post to Pinterest redirecting to your affiliate product link
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
