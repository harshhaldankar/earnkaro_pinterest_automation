"""
deal_card.py — Generates professional, brand-style Pinterest deal cards (1000x1500px).
Design inspired by Indian e-commerce brand banners:
  - Bold offer text on the left
  - Real product image on the right (on a styled platform)
  - Brand-color gradient background
  - Clean, premium look
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, re

W, H = 1000, 1500

STORE_THEMES = {
    "flipkart": {"bg1": (43,  130, 229), "bg2": (21, 60,  140), "accent": (255,255,255), "badge": (255, 200, 0)},
    "myntra":   {"bg1": (255, 45,  85),  "bg2": (150, 0,  50),  "accent": (255,255,255), "badge": (255,255,255)},
    "ajio":     {"bg1": (20,  20,  20),  "bg2": (60,  10, 80),  "accent": (255,215,0),   "badge": (255,215,0)},
    "amazon":   {"bg1": (255, 153, 0),   "bg2": (180, 80,  0),  "accent": (35, 47,  62), "badge": (35, 47, 62)},
    "nykaa":    {"bg1": (220, 30,  90),  "bg2": (140,  0, 50),  "accent": (255,255,255), "badge": (255,200,220)},
    "mamaearth":{"bg1": (56,  142, 60),  "bg2": (27,  94, 32),  "accent": (255,255,255), "badge": (255,245,157)},
    "boat":     {"bg1": (20,  20,  20),  "bg2": (40,   0, 80),  "accent": (0, 230, 180), "badge": (0, 230, 180)},
    "puma":     {"bg1": (20,  20,  20),  "bg2": (80,   0,  0),  "accent": (255,60,   0), "badge": (255, 60,  0)},
    "default":  {"bg1": (190, 30,  45),  "bg2": (100,  0, 20),  "accent": (255,255,255), "badge": (255,235,100)},
}


def _theme(link="", title=""):
    txt = (link + title).lower()
    for store, t in STORE_THEMES.items():
        if store in txt:
            return t, store.title()
    return STORE_THEMES["default"], "GetYourDeal"


def _font(size, bold=True):
    paths = [
        ("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        ("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def _gradient(draw, x1, y1, x2, y2, c1, c2, vertical=True):
    """Draw a gradient rectangle."""
    steps = (y2 - y1) if vertical else (x2 - x1)
    for i in range(steps):
        t = i / max(steps, 1)
        r = int(c1[0] + (c2[0]-c1[0]) * t)
        g = int(c1[1] + (c2[1]-c1[1]) * t)
        b = int(c1[2] + (c2[2]-c1[2]) * t)
        if vertical:
            draw.line([(x1, y1+i), (x2, y1+i)], fill=(r, g, b))
        else:
            draw.line([(x1+i, y1), (x1+i, y2)], fill=(r, g, b))


def _wrap(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textbbox((0,0), test, font=font)[2] <= max_w:
            cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    return lines


def _price(title):
    clean = re.sub(r'\d+\s*%\s*off', '', title, flags=re.IGNORECASE)
    clean = re.sub(r'upto\s*\d+\s*%', '', clean, flags=re.IGNORECASE)
    m = re.search(r'(?:at|@|rs\.?|inr|for)\s*[₹]?\s*(\d[\d,]+)', clean, re.IGNORECASE)
    if m:
        n = m.group(1).replace(',','')
        if int(n) >= 10: return f"Rs.{n}"
    m = re.search(r'[₹]\s*(\d[\d,]+)', clean)
    if m:
        n = m.group(1).replace(',','')
        if int(n) >= 10: return f"Rs.{n}"
    return None


def _discount(title):
    m = re.search(r'(\d+)\s*%\s*off', title, re.IGNORECASE)
    if m: return f"{m.group(1)}% OFF"
    for k in ["buy 1 get 1", "buy1get1", "bogo"]:
        if k in title.lower(): return "BUY 1\nGET 1 FREE"
    for k in ["upto 90%", "upto 80%", "upto 70%", "upto 60%", "upto 50%", "flat 90", "flat 80", "flat 70", "flat 60", "flat 50"]:
        if k.lower() in title.lower():
            pct = re.search(r'(\d+)', k).group(1)
            return f"UPTO {pct}% OFF"
    return "HOT DEAL"


def _rounded_rect(draw, xy, r, fill):
    x1, y1, x2, y2 = xy
    r = min(r, (x2-x1)//2, (y2-y1)//2)
    if r < 2:
        draw.rectangle(xy, fill=fill); return
    draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
    draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)
    for cx, cy in [(x1, y1), (x2-2*r, y1), (x1, y2-2*r), (x2-2*r, y2-2*r)]:
        draw.ellipse([cx, cy, cx+2*r, cy+2*r], fill=fill)


def generate_deal_card(title: str, affiliate_link: str, desc: str = "",
                       out_path: str = "deal_card.png",
                       product_img_path: str = None) -> str:
    """
    Generate a brand-banner style Pinterest card.
    Layout:
      - Full-bleed brand-color gradient background (like Conscious Chemist reference)
      - TOP STRIP: site branding
      - LEFT half: Offer text — big discount, brand, short tagline
      - RIGHT half: Product image on a circular platform glow
      - BOTTOM: Price + CTA button
    """
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)

    theme, store = _theme(affiliate_link, title)
    bg1, bg2 = theme["bg1"], theme["bg2"]
    acc, badge = theme["accent"], theme["badge"]

    # ── Canvas + gradient background ───────────────────────────────────────
    img = Image.new("RGB", (W, H), bg1)
    draw = ImageDraw.Draw(img)
    _gradient(draw, 0, 0, W, H, bg1, bg2)

    # Diagonal accent strip (like the red/gold diagonal in brand banners)
    from PIL import ImageDraw as ID
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon([(W//2, 0), (W, 0), (W, H//2)],
               fill=(*tuple(min(255,c+30) for c in bg1), 40))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Top branding strip ──────────────────────────────────────────────────
    strip_h = 90
    draw.rectangle([0, 0, W, strip_h], fill=(0, 0, 0, 60))
    f_brand = _font(38, bold=True)
    draw.text((W//2, strip_h//2), "getyourdeal.in  •  Verified Deals Daily",
              font=f_brand, fill=(*acc, 200), anchor="mm")

    # ── Offer text area (left 55%) ──────────────────────────────────────────
    TEXT_X    = 55
    TEXT_W    = 540
    TEXT_TOP  = strip_h + 60

    # Discount headline
    disc = _discount(title)
    disc_lines = disc.split("\n")

    f_disc_big = _font(130, bold=True)
    f_disc_sm  = _font(90,  bold=True)
    f_disc = f_disc_big if len(disc_lines) == 1 and len(disc_lines[0]) <= 10 else f_disc_sm

    ty = TEXT_TOP
    for line in disc_lines:
        bbox = draw.textbbox((0,0), line, font=f_disc)
        lw = bbox[2] - bbox[0]
        # Shadow
        draw.text((TEXT_X+3, ty+3), line, font=f_disc, fill=(0,0,0,80))
        draw.text((TEXT_X, ty),     line, font=f_disc, fill=acc)
        ty += (bbox[3]-bbox[1]) + 8

    ty += 18

    # "on Brand Name" line
    clean_title = re.sub(r'[^\x00-\x7F]+', '', title).strip()
    brand_line  = f"on {store}" if store != "GetYourDeal" else ""

    # Try to extract brand from title (first 2 capitalised words)
    words = clean_title.split()
    cap_words = [w for w in words[:4] if w and w[0].isupper()]
    if cap_words and store == "GetYourDeal":
        brand_line = "on " + " ".join(cap_words[:2])

    if brand_line:
        f_on = _font(52, bold=False)
        draw.text((TEXT_X, ty), brand_line, font=f_on, fill=(*acc, 210))
        bbox = draw.textbbox((0,0), brand_line, font=f_on)
        ty += (bbox[3]-bbox[1]) + 20

    # Short title tagline (max 2 lines)
    short = re.sub(r'(?:flat|upto|at|from|@|off|\d+%)\s*', '', clean_title, flags=re.IGNORECASE).strip()
    short = short[:80]
    f_tag = _font(42, bold=False)
    tag_lines = _wrap(short, f_tag, TEXT_W, draw)
    for line in tag_lines[:2]:
        draw.text((TEXT_X, ty), line, font=f_tag, fill=(*acc, 170))
        bbox = draw.textbbox((0,0), line, font=f_tag)
        ty += (bbox[3]-bbox[1]) + 6

    # ── Product image (right 50%, vertically centered) ──────────────────────
    IMG_X   = 490
    IMG_Y   = strip_h + 30
    IMG_W   = W - IMG_X - 20
    IMG_H   = H - strip_h - 350    # leave room for CTA at bottom

    if product_img_path and os.path.exists(product_img_path):
        try:
            prod = Image.open(product_img_path).convert("RGBA")

            # Crop to square from centre
            pw, ph = prod.size
            side = min(pw, ph)
            prod = prod.crop(((pw-side)//2, (ph-side)//2, (pw+side)//2, (ph+side)//2))
            prod = prod.resize((IMG_W, IMG_H), Image.LANCZOS)

            # Circular glow halo behind product
            glow = Image.new("RGBA", (IMG_W+60, IMG_H+60), (0,0,0,0))
            gd   = ImageDraw.Draw(glow)
            gd.ellipse([0, 0, IMG_W+60, IMG_H+60],
                       fill=(*tuple(min(255,c+80) for c in bg1), 80))
            glow = glow.filter(ImageFilter.GaussianBlur(30))
            img.paste(glow.convert("RGB"), (IMG_X-30, IMG_Y-30),
                      glow.split()[3])

            # Paste product
            if prod.mode == "RGBA":
                img.paste(prod, (IMG_X, IMG_Y), prod.split()[3])
            else:
                img.paste(prod, (IMG_X, IMG_Y))

            # Platform ellipse at bottom of product
            plat_y = IMG_Y + IMG_H - 30
            for i, (pal, alp) in enumerate([
                ((*badge, 120), 40),
                ((*badge, 80),  25),
            ]):
                ew = IMG_W - i*40
                eh = 50 - i*10
                ex = IMG_X + (IMG_W - ew)//2
                draw.ellipse([ex, plat_y+i*8, ex+ew, plat_y+i*8+eh],
                             fill=tuple((*badge[:3], alp)))

        except Exception as e:
            print(f"  [CARD] Product image error: {e}")
            # Draw placeholder circle
            draw.ellipse([IMG_X+40, IMG_Y+40, IMG_X+IMG_W-40, IMG_Y+IMG_H-40],
                         fill=(*tuple(min(255,c+40) for c in bg1),))
            draw.text((IMG_X+IMG_W//2, IMG_Y+IMG_H//2), "🛍️",
                      font=_font(120), anchor="mm", fill=acc)

    # ── Divider line ────────────────────────────────────────────────────────
    div_y = H - 310
    draw.rectangle([40, div_y, W-40, div_y+2],
                   fill=(*acc[:3], 60))

    # ── Price pill ───────────────────────────────────────────────────────────
    price = _price(title)
    btn_y = div_y + 20
    if price:
        f_price = _font(64, bold=True)
        pb = draw.textbbox((0,0), price, font=f_price)
        pw2 = pb[2]-pb[0]+60; ph2 = pb[3]-pb[1]+24
        px  = (W - pw2) // 2
        _rounded_rect(draw, [px, btn_y, px+pw2, btn_y+ph2], 32, badge)
        price_text_color = bg1 if sum(badge[:3]) > 380 else acc
        draw.text((W//2, btn_y+ph2//2), price,
                  font=f_price, fill=price_text_color, anchor="mm")
        btn_y += ph2 + 22

    # ── CTA Button ───────────────────────────────────────────────────────────
    cta_w, cta_h = 720, 105
    cx = (W - cta_w) // 2
    # Outer glow
    for g in range(8, 0, -1):
        _rounded_rect(draw, [cx-g, btn_y-g, cx+cta_w+g, btn_y+cta_h+g],
                      52+g, (*acc[:3], 15))
    _rounded_rect(draw, [cx, btn_y, cx+cta_w, btn_y+cta_h], 52, acc)
    f_cta = _font(52, bold=True)
    draw.text((W//2, btn_y+cta_h//2), "GRAB THIS DEAL  →",
              font=f_cta, fill=bg1, anchor="mm")

    img.save(out_path, "PNG", quality=95)
    print(f"  [CARD] Saved: {out_path}")
    return out_path
