import sys
import os
import json
import time

# Force UTF-8 output so emoji in print() don't crash on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import re
import requests
import io
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter

load_dotenv()

PINTEREST_EMAIL      = os.getenv("PINTEREST_EMAIL")
PINTEREST_PASSWORD   = os.getenv("PINTEREST_PASSWORD")
PINTEREST_BOARD_NAME = os.getenv("PINTEREST_BOARD_NAME", "Deals")

# ── Known brand OG/hero image sources ─────────────────────────────────────────
BRAND_FALLBACK_IMAGES = {
    "myntra":    "https://constant.myntassets.com/web/assets/img/MyntraLogo_lite.png",
    "ajio":      "https://assets.ajio.com/static/img/Ajio-Logo.jpg",
    "flipkart":  "https://static-assets-web.flixcart.com/batman-returns/batman-returns/p/images/flipkart-logo-2.png",
    "mamaearth": "https://mamaearth.in/cdn/shop/files/logo.png",
    "nykaa":     "https://adn-static1.nykaa.com/nykdesignstudio-images/pub/media/logo/stores/1/Nykaa_Logo.png",
    "axis":      "https://www.axisbank.com/images/default-source/progress-with-us_new/axis-bank-logo.png",
    "wow":       "https://www.buywow.in/cdn/shop/files/wow-logo.png",
    "plum":      "https://www.plumgoodness.com/cdn/shop/files/logo.png",
    "croma":     "https://media.croma.com/image/upload/v1637759004/Croma%20Assets/CMS/Category%20Banners/2021/Electronics/Laptops.png",
    "oneplus":   "https://image01.oneplus.net/epublic/202306/05/1685960280000.png",
}

BRAND_COLORS = {
    "myntra":    (255, 63,  108),
    "ajio":      (44,  62,  80),
    "flipkart":  (40,  116, 240),
    "mamaearth": (76,  175, 80),
    "nykaa":     (252, 39,  121),
    "axis":      (128, 0,   32),
    "wow":       (180, 140, 30),
    "plum":      (108, 92,  231),
    "croma":     (0,   180, 180),
    "oneplus":   (230, 10,  10),
}

PIN_W, PIN_H = 1000, 1500

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_brand_key(brand_name):
    bl = brand_name.lower()
    for key in BRAND_COLORS:
        if key in bl:
            return key
    return None

def get_brand_color(brand_name):
    key = get_brand_key(brand_name)
    return BRAND_COLORS.get(key, (80, 40, 120))

def get_font(size=40, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_wrapped_text(draw, text, font, fill, canvas_w, max_w, y, shadow=True):
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        if draw.textlength(test, font=font) <= max_w:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (canvas_w - w) / 2
        bbox = draw.textbbox((x, y), line, font=font)
        line_h = bbox[3] - bbox[1]
        if shadow:
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 140))
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h + 14
    return y

def fetch_og_image(brand_name):
    """Fetch OG/hero image from brand website via <meta property='og:image'>"""
    brand_urls = {
        "myntra":    "https://www.myntra.com",
        "ajio":      "https://www.ajio.com",
        "flipkart":  "https://www.flipkart.com",
        "mamaearth": "https://mamaearth.in",
        "nykaa":     "https://www.nykaa.com",
        "wow":       "https://www.buywow.in",
        "plum":      "https://plumgoodness.com",
        "croma":     "https://www.croma.com",
        "oneplus":   "https://www.oneplus.in",
        "axis":      "https://www.axisbank.com",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    key = get_brand_key(brand_name)
    site_url = brand_urls.get(key, "") if key else ""

    if site_url:
        try:
            r = requests.get(site_url, headers=headers, timeout=10)
            og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', r.text)
            if not og_match:
                og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', r.text)
            if og_match:
                img_url = og_match.group(1).strip()
                if not img_url.startswith("http"):
                    img_url = site_url.rstrip("/") + "/" + img_url.lstrip("/")
                img_r = requests.get(img_url, headers=headers, timeout=10)
                img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
                print(f"  ✅ OG image fetched for {brand_name}: {img_url[:60]}")
                return img
        except Exception as e:
            print(f"  ⚠️ OG fetch failed for {brand_name}: {e}")

    # Try known fallback URL
    if key and key in BRAND_FALLBACK_IMAGES:
        try:
            img_r = requests.get(BRAND_FALLBACK_IMAGES[key], headers=headers, timeout=8)
            img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
            print(f"  ✅ Fallback image fetched for {brand_name}")
            return img
        except Exception as e:
            print(f"  ⚠️ Fallback fetch failed for {brand_name}: {e}")

    return None

def make_background(brand_name, product_img=None):
    """Create pin background: product image if available, else gradient."""
    color = get_brand_color(brand_name)
    bg = Image.new("RGB", (PIN_W, PIN_H), color)

    if product_img:
        # Smart crop/resize to fill the upper 65% of the pin
        img_zone_h = int(PIN_H * 0.65)
        aspect = product_img.width / product_img.height
        if aspect > (PIN_W / img_zone_h):
            new_h = img_zone_h
            new_w = int(new_h * aspect)
        else:
            new_w = PIN_W
            new_h = int(new_w / aspect)
        product_img = product_img.resize((new_w, new_h), Image.LANCZOS)
        # Centre crop
        cx = (new_w - PIN_W) // 2
        cy = (new_h - img_zone_h) // 2
        product_img = product_img.crop((cx, cy, cx + PIN_W, cy + img_zone_h))
        # Subtle blur for depth
        blurred = product_img.filter(ImageFilter.GaussianBlur(radius=1))
        bg.paste(blurred, (0, 0))

    # Bottom gradient overlay (brand color → transparent) for text legibility
    grad = Image.new("RGBA", (PIN_W, PIN_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grad)
    gradient_start = int(PIN_H * 0.45)
    for y in range(gradient_start, PIN_H):
        alpha = int(255 * ((y - gradient_start) / (PIN_H - gradient_start)) ** 0.7)
        r, g, b = color
        draw.line([(0, y), (PIN_W, y)], fill=(r, g, b, min(alpha, 255)))
    bg.paste(grad, (0, 0), grad)

    # Top dark fade for logo area
    top_fade = Image.new("RGBA", (PIN_W, 200), (0, 0, 0, 0))
    top_draw = ImageDraw.Draw(top_fade)
    for y in range(200):
        alpha = int(180 * (1 - y / 200))
        top_draw.line([(0, y), (PIN_W, y)], fill=(0, 0, 0, alpha))
    bg.paste(top_fade, (0, 0), top_fade)

    return bg

def create_pin_image(item):
    brand = item["brand"]
    rate  = item["rate"]
    title = item.get("pinterest_title", f"Best deals on {brand}!")
    angle = item.get("angle", f"Save Big on {brand}!")
    color = get_brand_color(brand)

    print(f"  → Fetching product image for {brand}...")
    product_img = fetch_og_image(brand)

    bg   = make_background(brand, product_img)
    draw = ImageDraw.Draw(bg)

    f_brand  = get_font(54, True)
    f_badge  = get_font(34, True)
    f_angle  = get_font(44, False)
    f_title  = get_font(38, True)
    f_cta    = get_font(36, True)
    f_small  = get_font(24, False)

    # ── Top bar: brand logo area ──────────────────────────────────────────
    bw = draw.textlength(brand.upper(), font=f_brand)
    bx = (PIN_W - bw) / 2
    # Shadow
    draw.text((bx + 3, 43), brand.upper(), font=f_brand, fill=(0, 0, 0, 160))
    draw.text((bx, 40), brand.upper(), font=f_brand, fill=(255, 255, 255))

    # ── Commission badge ──────────────────────────────────────────────────
    badge = f"  **  {rate.upper()}  **  "
    bdw   = draw.textlength(badge, font=f_badge)
    bx2, by2 = (PIN_W - bdw) / 2, 118
    draw.rounded_rectangle(
        [(bx2 - 8, by2 - 6), (bx2 + bdw + 8, by2 + 54)],
        radius=12, fill=(255, 255, 255, 230)
    )
    draw.text((bx2, by2 + 4), badge, font=f_badge, fill=color)

    # ── Middle: angle hook + title ────────────────────────────────────────
    text_top = int(PIN_H * 0.60)

    y = draw_wrapped_text(draw, f'"{angle}"', f_angle, (255, 255, 200), PIN_W, PIN_W - 120, text_top)
    y += 12
    y = draw_wrapped_text(draw, title, f_title, (255, 255, 255), PIN_W, PIN_W - 140, y)

    # ── Divider line ──────────────────────────────────────────────────────
    lx = (PIN_W - 360) / 2
    draw.line([(lx, y + 20), (lx + 360, y + 20)], fill=(255, 255, 255, 120), width=2)

    # ── CTA ───────────────────────────────────────────────────────────────
    cta = ">>  CLICK LINK FOR DEAL  <<"
    cw  = draw.textlength(cta, font=f_cta)
    cx, cy = (PIN_W - cw) / 2, PIN_H - 220

    draw.rounded_rectangle(
        [(cx - 24, cy - 14), (cx + cw + 24, cy + 58)],
        radius=30,
        fill=None,
        outline=(255, 255, 255),
        width=3
    )
    draw.text((cx + 2, cy + 2), cta, font=f_cta, fill=(0, 0, 0, 100))
    draw.text((cx, cy), cta, font=f_cta, fill=(255, 255, 255))

    # ── Footer watermark ──────────────────────────────────────────────────
    wm = "GetYourDeal.in"
    ww = draw.textlength(wm, font=f_small)
    draw.text(((PIN_W - ww) / 2, PIN_H - 80), wm, font=f_small, fill=(255, 255, 255, 140))

    # ── Border ────────────────────────────────────────────────────────────
    draw.rectangle([(0, 0), (PIN_W - 1, PIN_H - 1)], outline=(255, 255, 255, 60), width=6)

    os.makedirs("pins", exist_ok=True)
    path = f"pins/pin_{item['rank']}_{brand.lower().replace(' ', '_')}.jpg"
    bg.save(path, "JPEG", quality=92)
    print(f"  ✅ Saved: {path}")
    return path

# ── Pinterest Playwright poster ───────────────────────────────────────────────

def login_to_pinterest(page, email, password):
    print("Logging into Pinterest...")
    page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded")
    time.sleep(5)
    if "login" not in page.url:
        print("Already logged in.")
        return True
    for sel in ["#email", "input[name='id']", "input[type='email']"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(email)
                break
        except Exception:
            pass
    for sel in ["#password", "input[name='password']", "input[type='password']"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(password)
                break
        except Exception:
            pass
    for sel in ["button[type='submit']", "button:has-text('Log in')"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                break
        except Exception:
            pass
    time.sleep(8)
    if "login" in page.url:
        print("Pinterest login failed.")
        return False
    print("Pinterest login successful!")
    return True

def post_pin_playwright(page, image_path, item, board_name):
    print(f"  → Posting pin: {item['brand']}")
    try:
        page.goto("https://www.pinterest.com/pin-creation-tool/", wait_until="domcontentloaded")
        time.sleep(5)

        file_input = page.query_selector("input[type='file']")
        if not file_input:
            print("  ⚠️ File input not found.")
            return None
        file_input.set_input_files(os.path.abspath(image_path))
        time.sleep(5)

        for sel in [
            "input[placeholder*='title' i]", "textarea[placeholder*='title' i]",
            "[data-test-id='pin-builder-title'] input",
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(item["pinterest_title"][:100])
                break

        for sel in [
            "div[contenteditable='true']", "div[role='textbox']",
            "textarea[placeholder*='description' i]",
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                try:
                    el.fill(item["pinterest_description"][:500])
                except Exception:
                    el.type(item["pinterest_description"][:500])
                break

        for sel in [
            "input[placeholder*='link' i]", "input[placeholder*='destination' i]",
            "input[placeholder*='url' i]",
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(item["affiliate_link"])
                break

        for sel in [
            "[data-test-id='board-dropdown-select-button']",
            "button:has-text('Choose a board')",
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                time.sleep(2)
                for s2 in ["input[placeholder*='Search' i]", "input[placeholder*='board' i]"]:
                    inp = page.query_selector(s2)
                    if inp and inp.is_visible():
                        inp.fill(board_name)
                        time.sleep(2)
                        opt = page.query_selector(f"div[role='option']:has-text('{board_name}')")
                        if not opt:
                            opt = page.query_selector(f"div:has-text('{board_name}')")
                        if opt:
                            opt.click()
                        break
                break

        for sel in [
            "button:has-text('Publish')", "button:has-text('Save')",
            "[data-test-id='publish-button']",
        ]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                break
        else:
            print("  ⚠️ Publish button not found.")
            return None

        time.sleep(10)
        for sel in ["a:has-text('See your Pin')", "a:has-text('View Pin')"]:
            link = page.query_selector(sel)
            if link:
                href = link.get_attribute("href") or ""
                if href.startswith("/"):
                    href = "https://www.pinterest.com" + href
                print(f"  ✅ Pin URL: {href}")
                return href
        return f"https://www.pinterest.com/pin/posted_{item['rank']}"
    except Exception as e:
        print(f"  ⚠️ Error posting pin for {item['brand']}: {e}")
        return None

# ── Main ──────────────────────────────────────────────────────────────────────

def run_pinterest_pipeline():
    print("=== Step 4: Create Product Pin Images & Post to Pinterest ===")

    if not os.path.exists("content.json"):
        print("ERROR: content.json not found. Run step3_make_links.py first.")
        return

    with open("content.json", "r", encoding="utf-8") as f:
        content_items = json.load(f)

    print(f"\n📸 Generating {len(content_items)} product pin images...")
    for item in content_items:
        item["pin_image_path"] = create_pin_image(item)

    if not PINTEREST_EMAIL or not PINTEREST_PASSWORD:
        print("\n⚠️ No Pinterest credentials — skipping upload.")
        for item in content_items:
            item["pin_url"] = f"https://www.pinterest.com/pin/mock_{item['rank']}"
    else:
        from playwright.sync_api import sync_playwright
        print("\n📌 Posting pins to Pinterest...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            if login_to_pinterest(page, PINTEREST_EMAIL, PINTEREST_PASSWORD):
                for item in content_items:
                    pin_url = post_pin_playwright(page, item["pin_image_path"], item, PINTEREST_BOARD_NAME)
                    item["pin_url"] = pin_url or f"https://www.pinterest.com/pin/failed_{item['rank']}"
            else:
                for item in content_items:
                    item["pin_url"] = f"https://www.pinterest.com/pin/login_failed_{item['rank']}"
            browser.close()

    with open("content.json", "w", encoding="utf-8") as f:
        json.dump(content_items, f, indent=4, ensure_ascii=False)
    print("\n✅ Pinterest pipeline complete. content.json updated with pin URLs.")

if __name__ == "__main__":
    run_pinterest_pipeline()
