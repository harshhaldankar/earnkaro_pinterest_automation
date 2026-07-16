"""
deal_card.py — Generates branded Pinterest deal cards (1000x1500px, 2:3 ratio).
No product images scraped. 100% copyright-safe generated graphics.
"""
from PIL import Image, ImageDraw, ImageFont
import os, textwrap, math, re

# Store-specific color themes
STORE_THEMES = {
    "flipkart": {"bg": (250, 165, 0),    "accent": (255, 255, 255), "text": (30, 30, 30)},
    "myntra":   {"bg": (255, 60, 90),    "accent": (255, 255, 255), "text": (255, 255, 255)},
    "ajio":     {"bg": (20, 20, 20),     "accent": (255, 215, 0),   "text": (255, 255, 255)},
    "amazon":   {"bg": (255, 153, 0),    "accent": (35, 47, 62),    "text": (35, 47, 62)},
    "nykaa":    {"bg": (252, 70, 107),   "accent": (255, 255, 255), "text": (255, 255, 255)},
    "default":  {"bg": (67, 56, 202),    "accent": (255, 255, 255), "text": (255, 255, 255)},
}

W, H = 1000, 1500

def get_theme(affiliate_link="", title=""):
    txt = (affiliate_link + title).lower()
    for store, theme in STORE_THEMES.items():
        if store in txt:
            return theme, store.title()
    return STORE_THEMES["default"], "GetYourDeal"

def draw_gradient(draw, w, h, color1, color2):
    """Draw a top-to-bottom gradient."""
    for y in range(h):
        t  = y / h
        r  = int(color1[0] + (color2[0] - color1[0]) * t)
        g  = int(color1[1] + (color2[1] - color1[1]) * t)
        b  = int(color1[2] + (color2[2] - color1[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

def darken(color, factor=0.6):
    return tuple(int(c * factor) for c in color)

def try_font(size):
    """Load a font, falling back to default."""
    attempts = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in attempts:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: pass
    return ImageFont.load_default()

def extract_price(title):
    """Try to pull a price from the deal title."""
    m = re.search(r'(?:at|from|@|rs\.?|inr)?\s*[₹]?\s*(\d[\d,]*)', title, re.IGNORECASE)
    if m:
        return f"₹{m.group(1).replace(',', '')}"
    return None

def generate_deal_card(title: str, affiliate_link: str, desc: str = "", out_path: str = "deal_card.png", product_img_path: str = None) -> str:
    """
    Create a branded Pinterest-optimised deal card (1000x1500).
    Returns the saved file path.
    """
    theme, store_name = get_theme(affiliate_link, title)
    bg   = theme["bg"]
    acc  = theme["accent"]
    txt  = theme["text"]
    dark = darken(bg, 0.55)

    img  = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Gradient background
    draw_gradient(draw, W, H, bg, dark)

    # ── Top section: store badge ──────────────────────────────────
    badge_h = 140
    draw.rectangle([0, 0, W, badge_h], fill=(255, 255, 255, 200))
    font_badge = try_font(54)
    draw.text((W//2, badge_h//2), "* GetYourDeal *", font=font_badge,
              fill=(50, 50, 50), anchor="mm")

    # ── Accent strip ──────────────────────────────────────────────
    draw.rectangle([0, badge_h, W, badge_h + 8], fill=acc)

    # ── Central card (white rounded rect) ────────────────────────
    card_top, card_bot = 190, 1050
    card_pad = 50
    draw.rounded_rectangle([card_pad, card_top, W-card_pad, card_bot],
                           radius=30, fill=(255, 255, 255))

    # ── Deal label ────────────────────────────────────────────────
    font_tag = try_font(32)
    tag_text = f"HOT {store_name.upper()} DEAL"
    draw.rectangle([card_pad, card_top, W-card_pad, card_top+60], fill=bg)
    draw.text((W//2, card_top+30), tag_text, font=font_tag,
              fill=acc, anchor="mm")

    # ── Product icon / placeholder or actual image ────────────────
    has_image = False
    if product_img_path and os.path.exists(product_img_path):
        try:
            prod_img = Image.open(product_img_path)
            # Center crop to square
            w, h = prod_img.size
            min_dim = min(w, h)
            prod_img = prod_img.crop(((w - min_dim) // 2, (h - min_dim) // 2, (w + min_dim) // 2, (h + min_dim) // 2))
            prod_img = prod_img.resize((360, 360), Image.Resampling.LANCZOS)
            
            # Center of the card is W // 2 = 500
            # Paste at y = card_top + 80 = 270. Goes up to 630
            img.paste(prod_img, (500 - 180, card_top + 80))
            
            # Border
            draw.rectangle([500 - 180 - 1, card_top + 80 - 1, 500 + 180 + 1, card_top + 80 + 360 + 1], outline=bg, width=2)
            has_image = True
        except Exception as e:
            print(f"  [IMG DRAW] Failed to paste product image: {e}")

    if not has_image:
        icon_cx, icon_cy = W//2, card_top + 200
        icon_r = 120
        draw.ellipse([icon_cx-icon_r, icon_cy-icon_r, icon_cx+icon_r, icon_cy+icon_r],
                     fill=bg)
        font_icon = try_font(70)
        draw.text((icon_cx, icon_cy), "DEAL", font=font_icon, fill=acc, anchor="mm")

    # ── Product title ─────────────────────────────────────────────
    font_title = try_font(44)
    font_small = try_font(30)
    wrapped = textwrap.wrap(title, width=28)
    ty = card_top + 470 if has_image else card_top + 360
    for line in wrapped[:3]:
        draw.text((W//2, ty), line, font=font_title, fill=(30, 30, 30), anchor="mm")
        ty += 56

    # ── Price highlight ───────────────────────────────────────────
    price = extract_price(title)
    if price:
        px, py = W//2, ty + 30
        pw, ph = 260, 70
        draw.rounded_rectangle([px-pw//2, py-ph//2, px+pw//2, py+ph//2],
                               radius=35, fill=bg)
        font_price = try_font(46)
        draw.text((px, py), price, font=font_price, fill=acc, anchor="mm")
        ty = py + 70

    # ── Description ───────────────────────────────────────────────
    if desc:
        ty += 20
        font_desc = try_font(28)
        for line in textwrap.wrap(desc, width=36)[:3]:
            draw.text((W//2, ty), line, font=font_desc, fill=(80, 80, 80), anchor="mm")
            ty += 40

    # ── CTA button ────────────────────────────────────────────────
    btn_y = card_bot - 90
    draw.rounded_rectangle([card_pad+40, btn_y-30, W-card_pad-40, btn_y+30],
                           radius=30, fill=bg)
    font_cta = try_font(34)
    draw.text((W//2, btn_y), ">> Get This Deal Now! <<", font=font_cta,
              fill=acc, anchor="mm")

    # ── Bottom section ────────────────────────────────────────────
    font_footer = try_font(28)
    draw.text((W//2, card_bot + 60),
              "[ Verified Affiliate Deal ]",
              font=font_footer, fill=(220, 220, 220), anchor="mm")
    draw.text((W//2, card_bot + 110),
              "No extra cost to you!",
              font=font_footer, fill=(180, 180, 180), anchor="mm")

    # Hashtags
    font_hash = try_font(24)
    tags = "#deals #sale #offer #shopping #india"
    draw.text((W//2, H - 80), tags, font=font_hash, fill=(160, 160, 200), anchor="mm")
    draw.text((W//2, H - 40), "getyourdeal | affiliate | lootdeals",
              font=font_hash, fill=(130, 130, 170), anchor="mm")

    # Save
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    img.save(out_path, "PNG", quality=95)
    print(f"  [IMG] Deal card saved: {out_path}")
    return out_path


if __name__ == "__main__":
    # Quick test
    path = generate_deal_card(
        title="New Balance Running Shoes at 2550",
        affiliate_link="https://fktr.in/vqJzKYG",
        desc="70% off on premium running shoes!",
        out_path="test_card.png"
    )
    print(f"Generated: {path}")
