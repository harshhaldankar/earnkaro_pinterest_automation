"""
poster_pinterest.py
━━━━━━━━━━━━━━━━━━
Posts affiliate deal pins to Pinterest using the OFFICIAL API v5.
NO browser automation. NO password. NO security warnings.

Requires ONE secret set in GitHub Actions (or .env locally):
  PINTEREST_ACCESS_TOKEN  →  generated from Pinterest Developer Dashboard
  PINTEREST_BOARD_ID      →  your board's numeric ID (see instructions below)

How to get your tokens (one-time setup):
  1. Go to https://developers.pinterest.com/apps/
  2. Open your app → scroll to bottom → "Generate Access Token"
  3. Tick ALL scopes: boards:read, pins:read, pins:write
  4. Click Generate → copy the token
  5. To get your Board ID: go to https://api.pinterest.com/v5/boards
     using your token (run: python poster_pinterest.py --list-boards)
"""
import sys
import os
import json
import time
import re
import io
import base64
import requests
import traceback
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime

# ── Force UTF-8 output so emoji in print() don't crash on Windows ──────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Config ──────────────────────────────────────────────────────────────────
PIN_W, PIN_H = 1000, 1500
FONT_DIR     = os.path.join(os.path.dirname(__file__), "fonts")
CONTENT_FILE = "content.json"

# Brand colour palette fallbacks
BRAND_COLOURS = {
    "myntra":      "#FF3F6C",
    "nykaa":       "#FC2779",
    "flipkart":    "#2874F0",
    "ajio":        "#1A1A1A",
    "mamaearth":   "#4CAF50",
    "wow":         "#1565C0",
    "plum":        "#7B1FA2",
    "croma":       "#1A3C8E",
    "oneplus":     "#F5010C",
    "axis":        "#97144D",
    "amazon":      "#FF9900",
    "default":     "#E94560",
}

def brand_colour(name: str) -> str:
    key = name.lower()
    for k, v in BRAND_COLOURS.items():
        if k in key:
            return v
    return BRAND_COLOURS["default"]

def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ── Image helpers ────────────────────────────────────────────────────────────
def load_font(size: int, bold: bool = False):
    """Load a font, falling back to default if not found."""
    candidates = []
    if bold:
        candidates = [
            os.path.join(FONT_DIR, "Outfit-Bold.ttf"),
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/Arial Bold.ttf",
        ]
    else:
        candidates = [
            os.path.join(FONT_DIR, "Outfit-Regular.ttf"),
            "C:/Windows/Fonts/arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def fetch_product_image(brand: str, website: str) -> Image.Image | None:
    """Try to grab the brand OG image or a fallback image."""
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    # Try OG image from brand homepage
    if website:
        try:
            resp = requests.get(website, headers=HEADERS, timeout=8)
            matches = re.findall(
                r'<meta\s+(?:property=["\']og:image["\']\s+content|content=["\']([^"\']+)["\']\s+property=["\']og:image)["\']?\s*(?:content=["\']([^"\']+)["\'])?',
                resp.text, re.IGNORECASE
            )
            for m in matches:
                url = m[1] or m[0]
                if url and url.startswith("http"):
                    r2 = requests.get(url, headers=HEADERS, timeout=8)
                    img = Image.open(io.BytesIO(r2.content)).convert("RGBA")
                    print(f"  OG image fetched for {brand}: {url[:80]}")
                    return img
        except Exception as e:
            print(f"  OG fetch failed for {brand}: {e}")

    # Fallback: coloured gradient with brand initial
    colour = hex_to_rgb(brand_colour(brand))
    img = Image.new("RGBA", (PIN_W, 900))
    draw = ImageDraw.Draw(img)
    for y in range(900):
        blend = y / 900
        r = int(colour[0] * (1 - blend * 0.4))
        g = int(colour[1] * (1 - blend * 0.4))
        b = int(colour[2] * (1 - blend * 0.4))
        draw.line([(0, y), (PIN_W, y)], fill=(r, g, b, 255))
    f = load_font(350, bold=True)
    letter = brand[0].upper()
    draw.text((PIN_W//2, 450), letter, font=f, fill=(255,255,255,30), anchor="mm")
    print(f"  Using gradient fallback for {brand}")
    return img

def create_pin_image(item: dict) -> bytes | None:
    """Create a branded Pinterest pin image and return JPEG bytes."""
    brand    = item.get("brand", "Brand")
    rate     = item.get("rate", "Great Deal")
    title    = item.get("pinterest_title", "")
    angle    = item.get("angle", "")
    website  = item.get("website", "")
    colour   = brand_colour(brand)
    rgb      = hex_to_rgb(colour)

    print(f"  Creating pin for {brand}...")

    # ── Canvas ────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (PIN_W, PIN_H), (15, 15, 25, 255))
    draw   = ImageDraw.Draw(canvas)

    # ── Product image (top 60%) ───────────────────────────────────────────
    img_h  = int(PIN_H * 0.60)
    prod   = fetch_product_image(brand, website)
    if prod:
        prod = prod.convert("RGBA")
        # Resize to fill width
        ratio = PIN_W / prod.width
        new_h = int(prod.height * ratio)
        prod  = prod.resize((PIN_W, max(new_h, img_h)), Image.LANCZOS)
        prod  = prod.crop((0, 0, PIN_W, img_h))
        canvas.paste(prod, (0, 0), prod)

    # ── Gradient overlay (brand colour fade from mid to bottom) ───────────
    overlay = Image.new("RGBA", (PIN_W, PIN_H), (0, 0, 0, 0))
    odraw   = ImageDraw.Draw(overlay)
    for y in range(img_h - 100, PIN_H):
        t = (y - (img_h - 100)) / (PIN_H - (img_h - 100))
        a = int(t * 255)
        odraw.line([(0, y), (PIN_W, y)], fill=(rgb[0], rgb[1], rgb[2], a))
    canvas = Image.alpha_composite(canvas, overlay)
    draw   = ImageDraw.Draw(canvas)

    # ── Dark header strip ─────────────────────────────────────────────────
    for y in range(200):
        t = 1 - (y / 200)
        a = int(t * 180)
        draw.line([(0, y), (PIN_W, y)], fill=(10, 10, 20, a))

    # ── Load fonts ────────────────────────────────────────────────────────
    f_brand = load_font(68, bold=True)
    f_badge = load_font(34, bold=True)
    f_angle = load_font(42, bold=False)
    f_title = load_font(52, bold=True)
    f_cta   = load_font(42, bold=True)
    f_wm    = load_font(28, bold=False)

    # ── Brand name ────────────────────────────────────────────────────────
    bw = draw.textlength(brand.upper(), font=f_brand)
    bx = (PIN_W - bw) / 2
    draw.text((bx + 2, 42), brand.upper(), font=f_brand, fill=(0, 0, 0, 120))
    draw.text((bx, 40), brand.upper(), font=f_brand, fill=(255, 255, 255))

    # ── Commission badge ──────────────────────────────────────────────────
    badge = f"  **  {rate.upper()}  **  "
    bdw   = draw.textlength(badge, font=f_badge)
    bx2, by2 = (PIN_W - bdw) / 2, 118
    draw.rounded_rectangle(
        [bx2 - 6, by2 - 6, bx2 + bdw + 6, by2 + 44],
        radius=20, fill=(255, 255, 255, 230)
    )
    draw.text((bx2, by2), badge, font=f_badge, fill=colour)

    # ── Angle hook ────────────────────────────────────────────────────────
    y = img_h - 60
    if angle:
        aw = draw.textlength(f'"{angle}"', font=f_angle)
        ax = (PIN_W - aw) / 2
        draw.text((ax, y), f'"{angle}"', font=f_angle, fill=(255, 240, 150))
        y += 60

    # ── Title ─────────────────────────────────────────────────────────────
    words = title.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textlength(test, font=f_title) < PIN_W - 80:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    y += 20
    for line in lines[:3]:
        lw = draw.textlength(line, font=f_title)
        draw.text(((PIN_W - lw) / 2, y), line, font=f_title, fill=(255, 255, 255))
        y += 68

    # ── Divider ───────────────────────────────────────────────────────────
    lx = (PIN_W - 360) / 2
    draw.line([(lx, y + 20), (lx + 360, y + 20)], fill=(255, 255, 255, 120), width=2)

    # ── CTA ───────────────────────────────────────────────────────────────
    cta = ">>  CLICK LINK FOR DEAL  <<"
    cw  = draw.textlength(cta, font=f_cta)
    cx, cy = (PIN_W - cw) / 2, PIN_H - 220
    draw.rounded_rectangle(
        [cx - 20, cy - 14, cx + cw + 20, cy + 56],
        radius=35, outline=(255, 255, 255, 200), width=3
    )
    draw.text((cx, cy), cta, font=f_cta, fill=(255, 255, 255))

    # ── Watermark ─────────────────────────────────────────────────────────
    wm  = "GetYourDeal.in"
    wmw = draw.textlength(wm, font=f_wm)
    draw.text(((PIN_W - wmw) / 2, PIN_H - 60), wm, font=f_wm, fill=(255, 255, 255, 140))

    # ── Convert to JPEG bytes ─────────────────────────────────────────────
    rgb_canvas = canvas.convert("RGB")
    buf = io.BytesIO()
    rgb_canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue()

def save_pin_image(jpg_bytes: bytes, filename: str) -> str:
    """Save pin image locally and return path."""
    os.makedirs("pins", exist_ok=True)
    path = os.path.join("pins", filename)
    with open(path, "wb") as f:
        f.write(jpg_bytes)
    print(f"  Saved: {path}")
    return path

# ── Pinterest API ────────────────────────────────────────────────────────────
class PinterestAPI:
    BASE = "https://api.pinterest.com/v5"

    def __init__(self, access_token: str):
        self.token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def get_boards(self):
        """List all boards for the authenticated user."""
        resp = requests.get(f"{self.BASE}/boards", headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def find_board_id(self, board_name: str) -> str | None:
        """Find board ID by name (case-insensitive)."""
        data = self.get_boards()
        for board in data.get("items", []):
            if board["name"].lower() == board_name.lower():
                return board["id"]
        return None

    def create_pin(self, board_id: str, title: str, description: str,
                   link: str, jpg_bytes: bytes) -> dict:
        """Upload a pin image as base64 and create a pin."""
        b64 = base64.b64encode(jpg_bytes).decode()
        body = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:500],
            "link": link,
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/jpeg",
                "data": b64
            }
        }
        resp = requests.post(
            f"{self.BASE}/pins",
            headers=self.headers,
            json=body,
            timeout=30
        )
        if resp.status_code not in (200, 201):
            print(f"  API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        return resp.json()

# ── Main pipeline ────────────────────────────────────────────────────────────
def list_boards_mode():
    """Helper mode: list all boards so user can find their Board ID."""
    token = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip()
    if not token:
        print("Set PINTEREST_ACCESS_TOKEN environment variable first.")
        return
    api = PinterestAPI(token)
    data = api.get_boards()
    print("\nYour Pinterest Boards:")
    print("-" * 50)
    for b in data.get("items", []):
        print(f"  Name: {b['name']}")
        print(f"  ID:   {b['id']}")
        print()

def upload_to_imgbb(jpg_bytes: bytes, name: str) -> str | None:
    """Upload image to imgbb (free hosting) and return public URL."""
    api_key = os.getenv("IMGBB_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        b64 = base64.b64encode(jpg_bytes).decode()
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "name": name, "image": b64},
            timeout=30
        )
        if resp.status_code == 200:
            url = resp.json()["data"]["url"]
            print(f"  Uploaded to imgbb: {url}")
            return url
    except Exception as e:
        print(f"  imgbb upload failed: {e}")
    return None

def post_via_makecom(webhook_url: str, image_url: str, title: str,
                     description: str, link: str) -> bool:
    """Send pin data to Make.com webhook which posts to Pinterest."""
    try:
        payload = {
            "image_url":   image_url,
            "title":       title[:100],
            "description": description[:500],
            "link":        link
        }
        resp = requests.post(webhook_url, json=payload, timeout=15)
        if resp.status_code in (200, 201, 204):
            print(f"  Sent to Make.com webhook OK")
            return True
        else:
            print(f"  Make.com webhook error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"  Make.com webhook failed: {e}")
    return False

def run_pinterest_pipeline():
    print("=== Step 4: Create Product Pin Images & Post to Pinterest ===")

    # ── List boards mode ──────────────────────────────────────────────────
    if "--list-boards" in sys.argv:
        list_boards_mode()
        return

    # ── Load content ──────────────────────────────────────────────────────
    if not os.path.exists(CONTENT_FILE):
        print(f"  {CONTENT_FILE} not found. Run step2 first.")
        return
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        content_items = json.load(f)

    # ── Pinterest credentials ─────────────────────────────────────────────
    access_token  = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip()
    board_name    = os.getenv("PINTEREST_BOARD_NAME", "").strip()
    board_id      = os.getenv("PINTEREST_BOARD_ID", "").strip()
    makecom_url   = os.getenv("MAKECOM_WEBHOOK_URL", "").strip()
    imgbb_key     = os.getenv("IMGBB_API_KEY", "").strip()

    use_api     = bool(access_token)
    use_makecom = bool(makecom_url and imgbb_key)
    skip_upload = not (use_api or use_makecom)

    if skip_upload:
        print("  No credentials found — generating images only (no upload).")
    elif use_makecom and not use_api:
        print("  Using Make.com webhook to post pins (API write access not available).")
    elif use_api:
        print("  Using Pinterest API v5 to post pins directly.")
        api = PinterestAPI(access_token)
        if not board_id and board_name:
            print(f"  Looking up board ID for '{board_name}'...")
            board_id = api.find_board_id(board_name)
            if board_id:
                print(f"  Found board ID: {board_id}")
            else:
                print(f"  Board '{board_name}' not found — falling back to Make.com.")
                use_api = False
        if use_api and not board_id:
            print("  No board ID — falling back to Make.com.")
            use_api = False

    print(f"\n  Generating {len(content_items)} product pin images...")
    posted, failed = 0, 0

    for item in content_items:
        brand    = item.get("brand", "Brand")
        rank     = item.get("rank", 0)
        slug     = brand.lower().replace(" ", "_")
        filename = f"pin_{rank}_{slug}.jpg"

        try:
            jpg_bytes = create_pin_image(item)
            if jpg_bytes is None:
                print(f"  Skipping {brand}: image creation failed.")
                failed += 1
                continue

            # Save locally
            path = save_pin_image(jpg_bytes, filename)
            item["pin_image_path"] = path

            if skip_upload:
                item.setdefault("pin_url", "#")
                continue

            title    = item.get("pinterest_title", brand)
            desc     = item.get("pinterest_description", "")
            aff_link = item.get("affiliate_link", "https://earnkaro.com")

            # ── Try Pinterest API directly ────────────────────────────────
            if use_api:
                try:
                    print(f"  Uploading via API: {brand}...")
                    result = api.create_pin(
                        board_id=board_id,
                        title=title, description=desc,
                        link=aff_link, jpg_bytes=jpg_bytes
                    )
                    pin_url = f"https://www.pinterest.com/pin/{result.get('id', '')}/"
                    item["pin_url"] = pin_url
                    print(f"  Posted: {pin_url}")
                    posted += 1
                    time.sleep(2)
                    continue
                except Exception as api_err:
                    err_str = str(api_err)
                    if "403" in err_str or "insufficient" in err_str.lower() or "scope" in err_str.lower():
                        print(f"  API write access denied (trial mode) — switching to Make.com.")
                        use_api = False   # stop trying API for remaining items
                    else:
                        raise

            # ── Fall back to Make.com webhook ─────────────────────────────
            if use_makecom:
                print(f"  Uploading image to imgbb for {brand}...")
                img_url = upload_to_imgbb(jpg_bytes, filename)
                if img_url:
                    ok = post_via_makecom(makecom_url, img_url, title, desc, aff_link)
                    if ok:
                        item["pin_url"] = "#makecom-posted"
                        posted += 1
                        time.sleep(1)
                        continue
                print(f"  Make.com posting failed for {brand}.")
                failed += 1
                item.setdefault("pin_url", "#")
            else:
                item.setdefault("pin_url", "#")
                failed += 1

        except Exception as e:
            print(f"  Error for {brand}: {e}")
            traceback.print_exc()
            failed += 1
            item.setdefault("pin_url", "#")

    # Save updated content.json
    with open(CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(content_items, f, ensure_ascii=False, indent=2)

    print(f"\n  Done! Posted {posted}/{len(content_items)} pins. Failed: {failed}")
    print("  Pinterest pipeline complete. content.json updated.")

if __name__ == "__main__":
    run_pinterest_pipeline()
