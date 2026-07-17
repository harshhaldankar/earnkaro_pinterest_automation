"""
deal_card.py — Generates viral, high-converting Pinterest deal cards (1000x1500px).
Designed to stop the scroll and drive clicks.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, re, math

# Store-specific brand colors
STORE_THEMES = {
    "flipkart": {"bg1": (251, 162, 0),    "bg2": (220, 120, 0),   "accent": (255, 255, 255), "badge": (35, 47, 62)},
    "myntra":   {"bg1": (255, 45, 85),    "bg2": (180, 0, 60),    "accent": (255, 255, 255), "badge": (255, 255, 255)},
    "ajio":     {"bg1": (18, 18, 18),     "bg2": (40, 20, 60),    "accent": (255, 215, 0),   "badge": (255, 215, 0)},
    "amazon":   {"bg1": (255, 153, 0),    "bg2": (200, 100, 0),   "accent": (35, 47, 62),    "badge": (35, 47, 62)},
    "nykaa":    {"bg1": (252, 70, 107),   "bg2": (180, 20, 70),   "accent": (255, 255, 255), "badge": (255, 255, 255)},
    "mamaearth":{"bg1": (76, 153, 0),     "bg2": (40, 100, 0),    "accent": (255, 255, 255), "badge": (255, 255, 255)},
    "boat":     {"bg1": (20, 20, 20),     "bg2": (50, 0, 80),     "accent": (0, 230, 180),   "badge": (0, 230, 180)},
    "puma":     {"bg1": (20, 20, 20),     "bg2": (60, 0, 0),      "accent": (255, 60, 0),    "badge": (255, 60, 0)},
    "default":  {"bg1": (15, 15, 35),     "bg2": (60, 20, 120),   "accent": (255, 255, 255), "badge": (255, 80, 120)},
}

W, H = 1000, 1500


def _get_theme(link="", title=""):
    txt = (link + title).lower()
    for store, t in STORE_THEMES.items():
        if store in txt:
            return t, store.title()
    return STORE_THEMES["default"], "Get Your Deal"


def _draw_gradient(img, color1, color2):
    """Draw a rich diagonal gradient background."""
    pix = img.load()
    for y in range(H):
        for x in range(W):
            t = (x / W * 0.3 + y / H * 0.7)
            r = int(color1[0] + (color2[0] - color1[0]) * t)
            g = int(color1[1] + (color2[1] - color1[1]) * t)
            b = int(color1[2] + (color2[2] - color1[2]) * t)
            pix[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _try_font(size, bold=True):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
    return ImageFont.load_default()


def _extract_price(title):
    """Extract sale price, skipping discount percentages like '80% off'."""
    # Remove percentage patterns first so they don't confuse the regex
    cleaned = re.sub(r'\d+\s*%\s*off', '', title, flags=re.IGNORECASE)
    cleaned = re.sub(r'upto\s*\d+\s*%', '', cleaned, flags=re.IGNORECASE)
    # Now find price with explicit marker
    m = re.search(r'(?:at|@|rs\.?|inr|for)\s*[₹]?\s*(\d[\d,]+)', cleaned, re.IGNORECASE)
    if m:
        num = m.group(1).replace(',', '')
        if int(num) >= 10:
            return f"Rs.{num}"
    # Or Rs. symbol directly
    m = re.search(r'[₹]\s*(\d[\d,]+)', cleaned)
    if m:
        num = m.group(1).replace(',', '')
        if int(num) >= 10:
            return f"Rs.{num}"
    return None


def _extract_discount(title):
    m = re.search(r'(\d+)\s*%\s*off', title, re.IGNORECASE)
    if m:
        return f"{m.group(1)}% OFF"
    for kw in ["upto 90%", "upto 80%", "upto 70%", "upto 60%", "upto 50%"]:
        if kw in title.lower():
            return kw.upper()
    return None


def _draw_rounded_rect(draw, xy, radius, fill, outline=None, width=2):
    x1, y1, x2, y2 = xy
    # Clamp radius so it never exceeds half the rect size
    radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
    if radius < 1:
        draw.rectangle([x1, y1, x2, y2], fill=fill)
        return
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
    draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
    draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
    draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)


def _wrap_text(text, font, max_width, draw):
    """Smart word wrap that respects pixel width."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def generate_deal_card(title: str, affiliate_link: str, desc: str = "",
                       out_path: str = "deal_card.png",
                       product_img_path: str = None) -> str:
    """
    Generate a viral, scroll-stopping Pinterest deal card.
    Card layout (top to bottom):
      - Product photo (full-bleed, 55% of height)
      - Discount badge (overlapping photo bottom)
      - Brand strip
      - Deal title (large, bold)
      - Price pill
      - CTA button "GET THIS DEAL"
      - Website branding footer
    """
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)

    theme, store_name = _get_theme(affiliate_link, title)
    bg1    = theme["bg1"]
    bg2    = theme["bg2"]
    accent = theme["accent"]
    badge_color = theme["badge"]

    # ── Canvas ──────────────────────────────────────────────────────────────
    img = Image.new("RGB", (W, H), bg1)
    _draw_gradient(img, bg1, bg2)
    draw = ImageDraw.Draw(img)

    PHOTO_H = 700   # height for product image area
    TEXT_Y  = PHOTO_H + 20

    # ── Product photo area ──────────────────────────────────────────────────
    photo_placed = False
    if product_img_path and os.path.exists(product_img_path):
        try:
            prod = Image.open(product_img_path).convert("RGB")
            # Fill the full width, crop to square from center then scale to PHOTO_H
            pw, ph = prod.size
            side = min(pw, ph)
            left = (pw - side) // 2
            top  = (ph - side) // 2
            prod = prod.crop((left, top, left + side, top + side))
            prod = prod.resize((W, PHOTO_H), Image.LANCZOS)
            # Darken bottom edge so text is readable
            grad_overlay = Image.new("RGBA", (W, PHOTO_H), (0, 0, 0, 0))
            go_draw = ImageDraw.Draw(grad_overlay)
            for y in range(PHOTO_H):
                alpha = int(180 * (y / PHOTO_H) ** 2)
                go_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
            img.paste(prod, (0, 0))
            img.paste(Image.new("RGB", (W, PHOTO_H)), (0, 0), grad_overlay)
            photo_placed = True
        except Exception as e:
            print(f"  [CARD] Product image compose failed: {e}")

    if not photo_placed:
        # Pattern fill — abstract geometric when no photo
        for i in range(0, W, 60):
            opacity = 30 + (i % 3) * 10
            draw.rectangle([i, 0, i + 30, PHOTO_H],
                           fill=tuple(min(255, c + opacity) for c in bg1))
        # Big emoji placeholder
        em_font = _try_font(220)
        draw.text((W//2, PHOTO_H//2), "🛍️", font=em_font, anchor="mm", fill=(*accent, 60))

    # ── Discount badge (overlapping photo/text boundary) ────────────────────
    discount = _extract_discount(title)
    if discount:
        badge_w, badge_h = 340, 80
        bx = 40
        by = PHOTO_H - badge_h // 2
        _draw_rounded_rect(draw, [bx, by, bx + badge_w, by + badge_h], 40, fill=(255, 50, 80))
        font_badge = _try_font(42)
        draw.text((bx + badge_w // 2, by + badge_h // 2), discount,
                  font=font_badge, fill=(255, 255, 255), anchor="mm")

    # ── Store name badge ─────────────────────────────────────────────────────
    font_store = _try_font(36)
    store_badge_text = f"  {store_name.upper()}  "
    sb_bbox = draw.textbbox((0, 0), store_badge_text, font=font_store)
    sb_w = sb_bbox[2] - sb_bbox[0] + 20
    _draw_rounded_rect(draw, [W - sb_w - 40, PHOTO_H - 50, W - 40, PHOTO_H + 30], 20,
                       fill=badge_color)
    draw.text((W - sb_w // 2 - 40, PHOTO_H - 10), store_badge_text,
              font=font_store, fill=bg1, anchor="mm")

    # ── Deal title ────────────────────────────────────────────────────────────
    font_title = _try_font(62)
    font_title_sm = _try_font(52)
    clean_title = re.sub(r'https?://\S+', '', title).strip()
    clean_title = re.sub(r'[^\x00-\x7F]+', '', clean_title).strip()  # strip emoji for PIL compat
    if not clean_title:
        clean_title = title[:60]

    lines = _wrap_text(clean_title, font_title, W - 80, draw)
    if len(lines) > 3:
        lines = _wrap_text(clean_title, font_title_sm, W - 80, draw)
        font_title = font_title_sm

    ty = TEXT_Y + 30
    for line in lines[:3]:
        draw.text((W // 2, ty), line, font=font_title, fill=accent, anchor="mm",
                  stroke_width=2, stroke_fill=(*bg1, 120))
        ty += 76

    # ── Price pill ────────────────────────────────────────────────────────────
    price = _extract_price(title)
    if price:
        py = ty + 20
        font_price = _try_font(58)
        price_bbox = draw.textbbox((0, 0), price, font=font_price)
        pw2 = price_bbox[2] - price_bbox[0] + 60
        ph2 = price_bbox[3] - price_bbox[1] + 28
        px1 = (W - pw2) // 2
        _draw_rounded_rect(draw, [px1, py, px1 + pw2, py + ph2], 30, fill=badge_color)
        draw.text((W // 2, py + ph2 // 2), price,
                  font=font_price, fill=bg1 if badge_color != accent else accent, anchor="mm")
        ty = py + ph2 + 20

    # ── Description (optional, small) ────────────────────────────────────────
    if desc and ty < H - 280:
        font_desc = _try_font(34, bold=False)
        clean_desc = re.sub(r'[^\x00-\x7F]+', '', desc).strip()[:100]
        desc_lines = _wrap_text(clean_desc, font_desc, W - 100, draw)
        for dl in desc_lines[:2]:
            draw.text((W // 2, ty + 10), dl, font=font_desc,
                      fill=tuple(min(255, c + 80) for c in bg2), anchor="mm")
            ty += 46
        ty += 10

    # ── CTA Button ────────────────────────────────────────────────────────────
    cta_y = max(ty + 30, H - 220)
    cta_w, cta_h = 700, 95
    cx = (W - cta_w) // 2
    _draw_rounded_rect(draw, [cx, cta_y, cx + cta_w, cta_y + cta_h], 48, fill=accent)
    font_cta = _try_font(48)
    draw.text((W // 2, cta_y + cta_h // 2), "GET THIS DEAL  ->",
              font=font_cta, fill=bg1, anchor="mm")

    # ── Footer branding ───────────────────────────────────────────────────────
    footer_y = H - 85
    draw.rectangle([0, footer_y, W, H], fill=(0, 0, 0, 100))
    font_footer = _try_font(32, bold=False)
    draw.text((W // 2, footer_y + 42), "getyourdeal.in  |  Verified Deals Daily",
              font=font_footer, fill=(180, 180, 200), anchor="mm")

    # ── Save ──────────────────────────────────────────────────────────────────
    img.save(out_path, "PNG", quality=95)
    print(f"  [CARD] Saved Pinterest card: {out_path}")
    return out_path
