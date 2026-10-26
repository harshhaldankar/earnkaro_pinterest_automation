"""
deal_card_generator.py — Generates aesthetic minimalist studio & flat-lay pins for Pinterest
and clean square cards for Instagram, matching high-end editorial accounts.
- Fashion & Apparel: Clean top-down aerial flat-lay on off-white textured concrete with realistic 3D drop shadow
- Skincare & Beauty: Warm travertine stone / linen aesthetic with organic window shadows
- Watches & Lifestyle: Warm neutral studio plaster with soft diffused lighting
- ZERO spammy text, banners, discount pills, or checkout screenshots
"""
import os
import re
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pipeline2.config import CACHE_DIR

def get_font(size: int):
    font_paths = [
        "Roboto-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def extract_product_photo(img_path: str, out_path: str, block: int = 8, min_width: int = 600) -> str | None:
    """
    Crop a store screenshot (what Telegram deal posts usually carry) down to its main product photo,
    so Pipeline 1 pins look like Pipeline 2's clean product shots.

    Store UI is near-white with thin text; product photos are large solid blocks. The image is split
    into `block`-px cells, a cell counts as "content" when most of its pixels aren't near-white, and
    the largest connected group of content cells is taken as the product photo.
    Returns out_path, or None when no convincing photo region is found (caller keeps its fallback).
    """
    im = Image.open(img_path).convert("RGB")
    w, h = im.size
    gw, gh = max(1, w // block), max(1, h // block)
    # 255 = near-white pixel; box-downscaling turns that into the near-white fraction per cell
    white = im.convert("L").point(lambda v: 255 if v > 242 else 0).resize((gw, gh), Image.BOX)
    px = white.load()
    content = [[px[x, y] < 100 for x in range(gw)] for y in range(gh)]

    seen = [[False] * gw for _ in range(gh)]
    best = None  # (cells, x0, y0, x1, y1)
    for sy in range(gh):
        for sx in range(gw):
            if not content[sy][sx] or seen[sy][sx]:
                continue
            stack, cells = [(sx, sy)], 0
            x0, y0, x1, y1 = sx, sy, sx, sy
            seen[sy][sx] = True
            while stack:
                x, y = stack.pop()
                cells += 1
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < gw and 0 <= ny < gh and content[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if best is None or cells > best[0]:
                best = (cells, x0, y0, x1, y1)

    if not best:
        return None
    cells, x0, y0, x1, y1 = best
    bw, bh = (x1 - x0 + 1) * block, (y1 - y0 + 1) * block
    area_share = (bw * bh) / float(w * h)
    fill = cells / float((x1 - x0 + 1) * (y1 - y0 + 1))
    # Reject specks, ragged shapes (text clusters) and banner strips
    if area_share < 0.06 or fill < 0.7 or not (0.45 <= bw / float(bh) <= 1.6):
        return None

    crop = im.crop((x0 * block, y0 * block, min(w, (x1 + 1) * block), min(h, (y1 + 1) * block)))
    if crop.width < min_width:
        scale = min_width / float(crop.width)
        crop = crop.resize((min_width, int(crop.height * scale)), Image.LANCZOS)
    crop.save(out_path, "JPEG", quality=92)
    return out_path


def create_aesthetic_studio_pin(product_img_path: str, out_path: str, size=(1080, 1440), title: str = "") -> str:
    """
    Transforms any product image into a high-end, commercial-ready studio or flat-lay pin:
    - Apparel: Top-down aerial flat-lay on matte off-white concrete with realistic 3D edge shadows
    - Beauty/Skincare: Warm cream/sand travertine backdrop with soft window sunlight shadows
    - Lifestyle/Watches: Warm minimalist studio background with soft contact shadow
    - ZERO spammy text, banners, or discount pills
    """
    try:
        t = title.lower()
        is_apparel = any(w in t for w in [
            "t-shirt", "tshirt", "shirt", "hoodie", "jacket", "dress", "jeans", "top",
            "kurti", "kurta", "saree", "pants", "trouser", "sweatshirt", "wear", "apparel"
        ])
        is_beauty = any(w in t for w in [
            "serum", "lotion", "cream", "skin", "hair", "dove", "tresemme", "loreal",
            "glow", "moisturizer", "sunscreen", "lipstick", "perfume", "beauty"
        ])

        if is_apparel:
            # ── 1A. Fashion Flat-Lay Backdrop: Clean off-white textured concrete ──
            bg = Image.new("RGB", size, (241, 239, 235))
            
            # Subtle diffused overhead studio light
            light = Image.new("RGBA", size, (0, 0, 0, 0))
            d_light = ImageDraw.Draw(light)
            d_light.ellipse([-150, -150, size[0] + 150, size[1] // 2], fill=(255, 255, 255, 60))
            light = light.filter(ImageFilter.GaussianBlur(120))
            
            canvas = bg.convert("RGBA")
            canvas = Image.alpha_composite(canvas, light)
            shadow_color = (25, 25, 30, 75)
            shadow_blur = 30
            shadow_offset = (0, 18)
        elif is_beauty:
            # ── 1B. Beauty & Skincare: Warm neutral sand/travertine stone backdrop ──
            bg = Image.new("RGB", size, (234, 226, 215))
            
            # Soft diagonal sunlight wash
            sun_wash = Image.new("RGBA", size, (0, 0, 0, 0))
            d_sun = ImageDraw.Draw(sun_wash)
            d_sun.ellipse([-200, -200, 900, 900], fill=(255, 252, 245, 75))
            sun_wash = sun_wash.filter(ImageFilter.GaussianBlur(130))
            
            # Soft organic window tree branch shadow
            window_shadow = Image.new("RGBA", size, (0, 0, 0, 0))
            d_win = ImageDraw.Draw(window_shadow)
            d_win.polygon([(-100, 150), (450, -100), (1250, 750), (750, 950)], fill=(0, 0, 0, 26))
            d_win.polygon([(-80, 750), (650, 150), (1450, 950), (750, 1550)], fill=(0, 0, 0, 20))
            window_shadow = window_shadow.filter(ImageFilter.GaussianBlur(85))
            
            canvas = bg.convert("RGBA")
            canvas = Image.alpha_composite(canvas, sun_wash)
            canvas = Image.alpha_composite(canvas, window_shadow)
            shadow_color = (40, 30, 20, 85)
            shadow_blur = 28
            shadow_offset = (20, 25)
        else:
            # ── 1C. Watches / Footwear / General: Warm minimalist studio plaster ──
            bg = Image.new("RGB", size, (232, 224, 214))
            sun_wash = Image.new("RGBA", size, (0, 0, 0, 0))
            d_sun = ImageDraw.Draw(sun_wash)
            d_sun.ellipse([-150, -150, 850, 850], fill=(255, 250, 240, 65))
            sun_wash = sun_wash.filter(ImageFilter.GaussianBlur(120))
            
            window_shadow = Image.new("RGBA", size, (0, 0, 0, 0))
            d_win = ImageDraw.Draw(window_shadow)
            d_win.polygon([(-100, 100), (400, -100), (1200, 800), (700, 1000)], fill=(0, 0, 0, 24))
            window_shadow = window_shadow.filter(ImageFilter.GaussianBlur(80))
            
            canvas = bg.convert("RGBA")
            canvas = Image.alpha_composite(canvas, sun_wash)
            canvas = Image.alpha_composite(canvas, window_shadow)
            shadow_color = (35, 25, 20, 80)
            shadow_blur = 25
            shadow_offset = (15, 20)

        # ── 2. Place Product Cleanly & Apply Realistic 3D Contact/Drop Shadow ──
        with Image.open(product_img_path) as im:
            prod = im.convert("RGBA")
            pw, ph = prod.size
            
            # Optimal scaling to fill ~75-80% of canvas
            max_w = int(size[0] * 0.82)
            max_h = int(size[1] * 0.82)
            
            scale = min(max_w / float(pw), max_h / float(ph))
            target_w = int(pw * scale)
            target_h = int(ph * scale)
            
            prod = prod.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # Create drop shadow
            pad = shadow_blur * 2
            shadow = Image.new("RGBA", (target_w + pad * 2, target_h + pad * 2), (0, 0, 0, 0))
            
            has_alpha = False
            if "A" in prod.getbands():
                # Check if alpha is actually masking something
                extrema = prod.getchannel("A").getextrema()
                if extrema[0] < 250:
                    has_alpha = True
                    
            if has_alpha:
                alpha_mask = prod.getchannel("A")
                shadow.paste(shadow_color, (pad + shadow_offset[0], pad + shadow_offset[1]), mask=alpha_mask)
            else:
                d_s = ImageDraw.Draw(shadow)
                # Realistic soft drop shadow bounding the product box
                d_s.rectangle(
                    [pad + shadow_offset[0], pad + shadow_offset[1], 
                     pad + target_w + shadow_offset[0], pad + target_h + shadow_offset[1]],
                    fill=shadow_color
                )
                
            shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
            
            pos_x = (size[0] - target_w) // 2
            pos_y = (size[1] - target_h) // 2
            
            # Composite shadow then product
            canvas.paste(shadow, (pos_x - pad, pos_y - pad), mask=shadow)
            canvas.paste(prod, (pos_x, pos_y), mask=prod.getchannel("A") if has_alpha else None)

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        final = canvas.convert("RGB")
        final.save(out_path, "JPEG", quality=95)
        return out_path
    except Exception as e:
        print(f"  [WARN] Failed to create aesthetic studio pin: {e}")
        return product_img_path

def generate_deal_cards(deal, local_img: str) -> dict:
    """
    Generates high-res Pinterest pin (1080x1440) and Instagram square card (1080x1080)
    for a given deal, applying the appropriate flat-lay / studio aesthetic.
    """
    base_name = os.path.basename(local_img)
    pin_path = str(CACHE_DIR / f"pin_aesthetic_{base_name}")
    ig_path = str(CACHE_DIR / f"ig_square_{base_name}")
    
    title = getattr(deal, "title", "") if hasattr(deal, "title") else str(deal.get("title", "") if isinstance(deal, dict) else "")
    
    create_aesthetic_studio_pin(local_img, pin_path, size=(1080, 1440), title=title)
    create_aesthetic_studio_pin(local_img, ig_path, size=(1080, 1080), title=title)
    
    return {
        "pinterest": pin_path,
        "ig_square": ig_path
    }

def overlay_pricing_banner(image_path: str, deal_price: str, mrp_val: str, discount_pct: str, name_suffix: str) -> str:
    """Redirects to aesthetic studio pin creation (no ugly discount pills)."""
    base_name = os.path.basename(image_path)
    out_path = str(CACHE_DIR / f"studio_pin_{base_name}")
    return create_aesthetic_studio_pin(image_path, out_path)
