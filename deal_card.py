"""
deal_card.py — Generates professional, highly attractive Pinterest deal cards (1000x1500px).
Features 4 distinct, gorgeous design styles selected dynamically (based on title hash)
to keep the Pinterest feed varied, custom-styled, and scroll-stopping!
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, re, math, hashlib

W, H = 1000, 1500

def _font(size, bold=True, italic=False, script=False):
    # Font candidate paths depending on Windows/Linux
    if script:
        paths = [
            "C:/Windows/Fonts/Gabriola.ttf",
            "C:/Windows/Fonts/segoepr.ttf", # Segoe Print
            "C:/Windows/Fonts/segoesc.ttf", # Segoe Script
            "C:/Windows/Fonts/lhandw.ttf",  # Lucida Handwriting
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        ]
    else:
        paths = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def _gradient(draw, x1, y1, x2, y2, c1, c2):
    """Draw a vertical gradient background."""
    steps = y2 - y1
    for i in range(steps):
        t = i / max(steps, 1)
        r = int(c1[0] + (c2[0]-c1[0]) * t)
        g = int(c1[1] + (c2[1]-c1[1]) * t)
        b = int(c1[2] + (c2[2]-c1[2]) * t)
        draw.line([(x1, y1+i), (x2, y1+i)], fill=(r, g, b))


def _price(title):
    clean = re.sub(r'\d+\s*%\s*off', '', title, flags=re.IGNORECASE)
    clean = re.sub(r'upto\s*\d+\s*%', '', clean, flags=re.IGNORECASE)
    m = re.search(r'(?:at|@|rs\.?|inr|for)\s*[₹]?\s*(\d[\d,]+)', clean, re.IGNORECASE)
    if m:
        n = m.group(1).replace(',','')
        if int(n) >= 10: return n
    m = re.search(r'[₹]\s*(\d[\d,]+)', clean)
    if m:
        n = m.group(1).replace(',','')
        if int(n) >= 10: return n
    return None


def _discount(title):
    m = re.search(r'(\d+)\s*%\s*off', title, re.IGNORECASE)
    if m: return f"{m.group(1)}% OFF"
    for k in ["buy 1 get 1", "buy1get1", "bogo"]:
        if k in title.lower(): return "50% OFF"
    for k in ["upto 90%", "upto 80%", "upto 70%", "upto 60%", "upto 50%", "flat 90", "flat 80", "flat 70", "flat 60", "flat 50"]:
        if k.lower() in title.lower():
            pct = re.search(r'(\d+)', k).group(1)
            return f"{pct}% OFF"
    return "60% OFF"


def _rounded_rect(draw, xy, r, fill):
    x1, y1, x2, y2 = xy
    r = min(r, (x2-x1)//2, (y2-y1)//2)
    if r < 2:
        draw.rectangle(xy, fill=fill); return
    draw.rectangle([x1+r, y1, x2-r, y2], fill=fill)
    draw.rectangle([x1, y1+r, x2, y2-r], fill=fill)
    for cx, cy in [(x1, y1), (x2-2*r, y1), (x1, y2-2*r), (x2-2*r, y2-2*r)]:
        draw.ellipse([cx, cy, cx+2*r, cy+2*r], fill=fill)


def _crop_and_resize_to_mask(prod_img, mask_w, mask_h):
    """Crop and resize product image to fit a given bounding box aspect ratio."""
    pw, ph = prod_img.size
    img_aspect = pw / ph
    target_aspect = mask_w / mask_h
    
    if img_aspect > target_aspect:
        new_w = int(ph * target_aspect)
        left = (pw - new_w) // 2
        cropped = prod_img.crop((left, 0, left + new_w, ph))
    else:
        new_h = int(pw / target_aspect)
        top = (ph - new_h) // 2
        cropped = prod_img.crop((0, top, pw, top + new_h))
        
    return cropped.resize((mask_w, mask_h), Image.LANCZOS)


def generate_deal_card(title: str, affiliate_link: str, desc: str = "",
                       out_path: str = "deal_card.png",
                       product_img_path: str = None) -> str:
    """
    Generates a high-converting Pinterest deal card using one of 4 dynamic styles
    selected deterministically via a hash of the deal's title.
    """
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)

    # Pick style ID (0 to 3) based on the title hash
    style_id = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16) % 4

    # Extract price and discount
    price_val = _price(title)
    discount_val = _discount(title)

    # Load product image if present
    prod = None
    if product_img_path and os.path.exists(product_img_path):
        try:
            prod = Image.open(product_img_path).convert("RGB")
        except: pass

    # =========================================================================
    # STYLE 0: Hexagon Pastel (The classic Slanted Label style)
    # =========================================================================
    if style_id == 0:
        bg_top  = (210, 230, 255)
        bg_bot  = (255, 205, 230)
        img = Image.new("RGB", (W, H), bg_top)
        draw = ImageDraw.Draw(img)
        _gradient(draw, 0, 0, W, H, bg_top, bg_bot)

        # Header
        draw.text((W // 2, 130), "Brand new", font=_font(85, script=True), fill=(30, 30, 40), anchor="mm")
        draw.text((W // 2, 240), "SALE", font=_font(100, bold=True), fill=(20, 20, 30), anchor="mm")

        # Hexagon Geometry
        cx, cy, r = W // 2, 630, 290
        vertices = []
        for a in [0, 60, 120, 180, 240, 300]:
            rad = math.radians(a)
            vertices.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))

        # Hexagon Background glow
        glow_vertices = []
        glow_r = r + 15
        for a in [0, 60, 120, 180, 240, 300]:
            rad = math.radians(a)
            glow_vertices.append((cx + glow_r * math.cos(rad), cy + glow_r * math.sin(rad)))
        draw.polygon(glow_vertices, fill=(215, 210, 255))

        # Paste Product
        if prod:
            hex_w, hex_h = int(2 * r), int(2 * r * math.sin(math.radians(60)))
            resized = _crop_and_resize_to_mask(prod, hex_w, hex_h)
            mask = Image.new("L", (W, H), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.polygon(vertices, fill=255)
            prod_full = Image.new("RGB", (W, H), (215, 210, 255))
            prod_full.paste(resized, (cx - hex_w // 2, cy - hex_h // 2))
            img.paste(prod_full, (0, 0), mask)
        else:
            draw.text((cx, cy), "🛍️", font=_font(150, bold=False), fill=(20, 20, 30, 80), anchor="mm")

        # Hexagon outline
        draw.polygon(vertices, outline=(160, 150, 230), width=8)

        # Slanted Price Tag
        if price_val:
            tag_w, tag_h = 320, 75
            tag_layer = Image.new("RGBA", (tag_w, tag_h), (0, 0, 0, 0))
            tl_draw = ImageDraw.Draw(tag_layer)
            _rounded_rect(tl_draw, [0, 0, tag_w, tag_h], 20, fill=(215, 210, 255))
            tl_draw.text((tag_w // 2, tag_h // 2), f"Price - {price_val}/-", font=_font(34, bold=True), fill=(20, 20, 30), anchor="mm")
            rotated_tag = tag_layer.rotate(-30, expand=True, resample=Image.BICUBIC)
            px = cx + int(r * math.cos(math.radians(30))) - 100
            py = cy + int(r * math.sin(math.radians(30))) - 90
            img.paste(rotated_tag, (px, py), rotated_tag)

        # Footer
        draw.text((W // 2, 1050), f"DISCOUNTS UP TO {discount_val}", font=_font(48, bold=True), fill=(30, 30, 45), anchor="mm")
        _rounded_rect(draw, [(W - 440)//2, 1130, (W + 440)//2, 1225], 15, fill=(180, 195, 255))
        draw.text((W // 2, 1177), "SHOP NOW", font=_font(46, bold=True), fill=(20, 20, 30), anchor="mm")
        draw.text((W // 2, 1330), "OUR WEBSITE LINK ON THE BIO", font=_font(34, bold=True), fill=(80, 80, 100), anchor="mm")

    # =========================================================================
    # STYLE 1: Retro Circle Glow (Warm Sunset Theme)
    # =========================================================================
    elif style_id == 1:
        bg_top  = (255, 245, 235)  # Cream
        bg_bot  = (255, 210, 190)  # Soft Coral
        img = Image.new("RGB", (W, H), bg_top)
        draw = ImageDraw.Draw(img)
        _gradient(draw, 0, 0, W, H, bg_top, bg_bot)

        # Header
        draw.text((W // 2, 140), "LIMITED OFFER", font=_font(45, bold=True), fill=(250, 110, 80), anchor="mm")
        draw.text((W // 2, 230), "TOP DEALS", font=_font(95, bold=True), fill=(40, 30, 30), anchor="mm")

        # Circle Geometry
        cx, cy, r = W // 2, 630, 290
        
        # Soft Circle Backdrop Glow
        draw.ellipse([cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20], fill=(255, 225, 210))

        # Paste Product
        if prod:
            circ_w = circ_h = int(2 * r)
            resized = _crop_and_resize_to_mask(prod, circ_w, circ_h)
            mask = Image.new("L", (W, H), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
            prod_full = Image.new("RGB", (W, H), (255, 225, 210))
            prod_full.paste(resized, (cx - r, cy - r))
            img.paste(prod_full, (0, 0), mask)
        else:
            draw.text((cx, cy), "🏷️", font=_font(150, bold=False), fill=(250, 110, 80, 80), anchor="mm")

        # Circle Border Frame
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 130, 100), width=8)

        # Horizontal Price Tag overlapping the bottom center of the circle
        if price_val:
            tag_w, tag_h = 340, 75
            tag_x1 = (W - tag_w) // 2
            tag_y1 = cy + r - 35
            _rounded_rect(draw, [tag_x1, tag_y1, tag_x1 + tag_w, tag_y1 + tag_h], 20, fill=(250, 110, 80))
            draw.text((W // 2, tag_y1 + tag_h // 2), f"ONLY Rs.{price_val}", font=_font(36, bold=True), fill=(255, 255, 255), anchor="mm")

        # Footer
        draw.text((W // 2, 1050), f"FLAT {discount_val} DISCOUNT", font=_font(46, bold=True), fill=(40, 30, 30), anchor="mm")
        _rounded_rect(draw, [(W - 440)//2, 1130, (W + 440)//2, 1225], 15, fill=(40, 30, 30))
        draw.text((W // 2, 1177), "GRAB IT NOW", font=_font(44, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((W // 2, 1330), "VISIT THE LINK IN BIO", font=_font(34, bold=True), fill=(120, 100, 100), anchor="mm")

    # =========================================================================
    # STYLE 2: Elegant Polaroid Square (Clean Lavendar/Deep Slate Theme)
    # =========================================================================
    elif style_id == 2:
        bg_top  = (225, 220, 240)  # Soft Lavender
        bg_bot  = (175, 170, 200)  # Lavender Gray
        img = Image.new("RGB", (W, H), bg_top)
        draw = ImageDraw.Draw(img)
        _gradient(draw, 0, 0, W, H, bg_top, bg_bot)

        # Header
        draw.text((W // 2, 130), "TRENDING NOW", font=_font(42, bold=True), fill=(100, 80, 150), anchor="mm")
        draw.text((W // 2, 220), "MEGA OFFER", font=_font(90, bold=True), fill=(40, 30, 60), anchor="mm")

        # Polaroid Square Geometry
        sq_w, sq_h = 580, 580
        cx, cy = W // 2, 620
        sq_x1, sq_y1 = cx - sq_w // 2, cy - sq_h // 2
        
        # Soft shadow behind Polaroid square
        draw.rectangle([sq_x1 - 10, sq_y1 - 10, sq_x1 + sq_w + 10, sq_y1 + sq_h + 10], fill=(160, 150, 185))
        draw.rectangle([sq_x1, sq_y1, sq_x1 + sq_w, sq_y1 + sq_h], fill=(255, 255, 255))

        # Paste Product
        if prod:
            resized = _crop_and_resize_to_mask(prod, sq_w - 40, sq_h - 40)
            img.paste(resized, (sq_x1 + 20, sq_y1 + 20))
        else:
            draw.text((cx, cy), "🎁", font=_font(150, bold=False), fill=(100, 80, 150, 80), anchor="mm")

        # Hanger Price Tag on the corner
        if price_val:
            tag_w, tag_h = 240, 70
            tag_layer = Image.new("RGBA", (tag_w, tag_h), (0, 0, 0, 0))
            tl_draw = ImageDraw.Draw(tag_layer)
            _rounded_rect(tl_draw, [0, 0, tag_w, tag_h], 15, fill=(100, 80, 150))
            tl_draw.text((tag_w // 2, tag_h // 2), f"Rs.{price_val}", font=_font(34, bold=True), fill=(255, 255, 255), anchor="mm")
            # Rotate tag slightly to hang organically
            rotated_tag = tag_layer.rotate(15, expand=True, resample=Image.BICUBIC)
            img.paste(rotated_tag, (sq_x1 - 40, sq_y1 - 30), rotated_tag)

        # Footer
        draw.text((W // 2, 1050), f"SAVE {discount_val} TODAY", font=_font(46, bold=True), fill=(40, 30, 60), anchor="mm")
        _rounded_rect(draw, [(W - 440)//2, 1130, (W + 440)//2, 1225], 15, fill=(100, 80, 150))
        draw.text((W // 2, 1177), "VIEW DEAL", font=_font(44, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((W // 2, 1330), "WEBSITE LINK IN BIO", font=_font(34, bold=True), fill=(100, 95, 120), anchor="mm")

    # =========================================================================
    # STYLE 3: Modern Mint Rounded (Sleek Clean Mint Theme)
    # =========================================================================
    else:
        bg_top  = (230, 255, 240)  # Light Mint
        bg_bot  = (180, 230, 200)  # Soft Green Mint
        img = Image.new("RGB", (W, H), bg_top)
        draw = ImageDraw.Draw(img)
        _gradient(draw, 0, 0, W, H, bg_top, bg_bot)

        # Header
        draw.text((W // 2, 130), "DEAL OF THE DAY", font=_font(42, bold=True), fill=(30, 140, 90), anchor="mm")
        draw.text((W // 2, 220), "SUPER SALE", font=_font(90, bold=True), fill=(20, 60, 40), anchor="mm")

        # Rounded Rectangle Geometry
        cx, cy = W // 2, 620
        rw, rh = 560, 560
        rx1, ry1 = cx - rw // 2, cy - rh // 2

        # Outer rounded frame
        _rounded_rect(draw, [rx1 - 10, ry1 - 10, rx1 + rw + 10, ry1 + rh + 10], 40, fill=(210, 250, 225))

        # Paste Product
        if prod:
            resized = _crop_and_resize_to_mask(prod, rw, rh)
            # Use a rounded mask
            mask = Image.new("L", (W, H), 0)
            mask_draw = ImageDraw.Draw(mask)
            _rounded_rect(mask_draw, [rx1, ry1, rx1 + rw, ry1 + rh], 30, fill=255)
            prod_full = Image.new("RGB", (W, H), (210, 250, 225))
            prod_full.paste(resized, (rx1, ry1))
            img.paste(prod_full, (0, 0), mask)
        else:
            draw.text((cx, cy), "💚", font=_font(150, bold=False), fill=(30, 140, 90, 80), anchor="mm")

        _rounded_rect(draw, [rx1, ry1, rx1 + rw, ry1 + rh], 30, fill=None)

        # Top-Right hanging badge for Price
        if price_val:
            tag_w, tag_h = 240, 75
            tag_x1 = rx1 + rw - 200
            tag_y1 = ry1 - 30
            _rounded_rect(draw, [tag_x1, tag_y1, tag_x1 + tag_w, tag_y1 + tag_h], 20, fill=(30, 140, 90))
            draw.text((tag_x1 + tag_w // 2, tag_y1 + tag_h // 2), f"Rs.{price_val}", font=_font(34, bold=True), fill=(255, 255, 255), anchor="mm")

        # Footer
        draw.text((W // 2, 1050), f"UP TO {discount_val} SAVINGS", font=_font(46, bold=True), fill=(20, 60, 40), anchor="mm")
        _rounded_rect(draw, [(W - 440)//2, 1130, (W + 440)//2, 1225], 20, fill=(30, 140, 90))
        draw.text((W // 2, 1177), "SHOP THE SALE", font=_font(44, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((W // 2, 1330), "VISIT THE LINK IN OUR BIO", font=_font(34, bold=True), fill=(70, 100, 80), anchor="mm")

    # Save
    img.save(out_path, "PNG", quality=95)
    print(f"  [CARD] Saved Style {style_id} card: {out_path}")
    return out_path
