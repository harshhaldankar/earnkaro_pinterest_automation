"""
deal_card.py — Generates professional, brand-style Pinterest deal cards (1000x1500px).
Design inspired by the user's reference image:
  - Pastel blue-to-pink gradient background
  - "Brand new" script text + "SALE" bold text at the top
  - Product image cropped inside a perfect hexagon frame with soft glow
  - Diagonal price tag label (e.g., "Price - 599/-") at the bottom-right of the hexagon
  - "DISCOUNTS UP TO XX% OFF" at the bottom
  - "SHOP NOW" pastel blue button
  - "OUR WEBSITE LINK ON THE BIO" branding footer
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, re, math

W, H = 1000, 1500

def _font(size, bold=True, italic=False, script=False):
    # Try script fonts for "Brand new"
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
    return "60% OFF"  # standard fallback


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
    Generate a Pinterest card that matches the user's reference image exactly.
    """
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)

    # ── Colors matching the reference image ────────────────────────────────
    # Background: pastel blue (top) to pastel pink (bottom)
    bg_top  = (210, 230, 255)
    bg_bot  = (255, 205, 230)
    
    # ── Canvas ─────────────────────────────────────────────────────────────
    img = Image.new("RGB", (W, H), bg_top)
    draw = ImageDraw.Draw(img)
    _gradient(draw, 0, 0, W, H, bg_top, bg_bot)

    # ── Top Text: "Brand new SALE" ─────────────────────────────────────────
    # "Brand new" in script/handwriting style
    f_brand_new = _font(85, bold=False, script=True)
    draw.text((W // 2, 130), "Brand new", font=f_brand_new, fill=(30, 30, 40), anchor="mm")

    # "SALE" in large bold sans-serif
    f_sale = _font(100, bold=True)
    draw.text((W // 2, 240), "SALE", font=f_sale, fill=(20, 20, 30), anchor="mm")

    # ── Center Hexagon geometry ─────────────────────────────────────────────
    cx, cy = W // 2, 630
    r = 290  # Hexagon radius

    # Pointy left/right, flat top/bottom hexagon vertices
    vertices = []
    for a in [0, 60, 120, 180, 240, 300]:
        rad = math.radians(a)
        vertices.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))

    # Draw soft purple hexagon background/glow behind the frame
    glow_vertices = []
    glow_r = r + 15
    for a in [0, 60, 120, 180, 240, 300]:
        rad = math.radians(a)
        glow_vertices.append((cx + glow_r * math.cos(rad), cy + glow_r * math.sin(rad)))

    # Draw a soft purple hexagon backdrop shape
    draw.polygon(glow_vertices, fill=(215, 210, 255))

    # ── Crop & paste product image inside Hexagon ──────────────────────────
    photo_placed = False
    if product_img_path and os.path.exists(product_img_path):
        try:
            prod = Image.open(product_img_path).convert("RGB")
            
            # Bounding box dimensions for the regular hexagon
            hex_w = int(2 * r)
            hex_h = int(2 * r * math.sin(math.radians(60)))
            
            # Crop image to match hexagon bounding box aspect ratio
            pw, ph = prod.size
            img_aspect = pw / ph
            target_aspect = hex_w / hex_h
            
            if img_aspect > target_aspect:
                new_w = int(ph * target_aspect)
                left = (pw - new_w) // 2
                prod = prod.crop((left, 0, left + new_w, ph))
            else:
                new_h = int(pw / target_aspect)
                top = (ph - new_h) // 2
                prod = prod.crop((0, top, pw, top + new_h))
                
            prod = prod.resize((hex_w, hex_h), Image.LANCZOS)

            # Create hexagon mask (transparent background with white hexagon)
            mask = Image.new("L", (W, H), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.polygon(vertices, fill=255)

            # Paste product image using mask
            # Offset placement to center it on (cx, cy)
            paste_x = cx - hex_w // 2
            paste_y = cy - hex_h // 2
            
            # Crop product image to match mask coordinate space
            prod_full = Image.new("RGB", (W, H), (215, 210, 255))
            prod_full.paste(prod, (paste_x, paste_y))
            
            img.paste(prod_full, (0, 0), mask)
            photo_placed = True
        except Exception as e:
            print(f"  [CARD] Hexagon image crop fail: {e}")

    if not photo_placed:
        # Fallback bag emoji if image fails
        f_emoji = _font(150, bold=False)
        draw.text((cx, cy), "🛍️", font=f_emoji, fill=(20, 20, 30, 80), anchor="mm")

    # Draw the main hexagon outline frame
    draw.polygon(vertices, outline=(160, 150, 230), width=8)

    # ── Diagonal Price Tag (bottom-right edge of hexagon) ──────────────────
    price_val = _price(title)
    if price_val:
        price_text = f"Price - {price_val}/-"
        f_tag = _font(34, bold=True)
        
        # Calculate text bounding box to make a perfect fitting tag
        # Create a temp transparent layer to draw the angled label
        tag_w, tag_h = 320, 75
        tag_layer = Image.new("RGBA", (tag_w, tag_h), (0, 0, 0, 0))
        tl_draw = ImageDraw.Draw(tag_layer)
        
        # Draw soft purple background tag pill
        _rounded_rect(tl_draw, [0, 0, tag_w, tag_h], 20, fill=(215, 210, 255))
        tl_draw.text((tag_w // 2, tag_h // 2), price_text, font=f_tag, fill=(20, 20, 30), anchor="mm")
        
        # Rotate tag by 30 degrees (matches the bottom-right slant of the hexagon)
        rotated_tag = tag_layer.rotate(-30, expand=True, resample=Image.BICUBIC)
        
        # Paste at bottom-right edge of the hexagon
        px = cx + int(r * math.cos(math.radians(30))) - 100
        py = cy + int(r * math.sin(math.radians(30))) - 90
        img.paste(rotated_tag, (px, py), rotated_tag)

    # ── Bottom Section: Discounts, Shop Now, and Branding ──────────────────
    # "DISCOUNTS UP TO XX% OFF" text
    disc_text = f"DISCOUNTS UP TO {_discount(title)}"
    f_disc = _font(48, bold=True)
    draw.text((W // 2, 1050), disc_text, font=f_disc, fill=(30, 30, 45), anchor="mm")

    # "SHOP NOW" Button (Pastel Blue)
    btn_w, btn_h = 440, 95
    btn_x1 = (W - btn_w) // 2
    btn_y1 = 1130
    _rounded_rect(draw, [btn_x1, btn_y1, btn_x1 + btn_w, btn_y1 + btn_h], 15, fill=(180, 195, 255))
    
    f_btn = _font(46, bold=True)
    draw.text((W // 2, btn_y1 + btn_h // 2), "SHOP NOW", font=f_btn, fill=(20, 20, 30), anchor="mm")

    # "OUR WEBSITE LINK ON THE BIO" branding footer
    f_footer = _font(34, bold=True)
    draw.text((W // 2, 1330), "OUR WEBSITE LINK ON THE BIO", font=f_footer, fill=(80, 80, 100), anchor="mm")

    # ── Save ───────────────────────────────────────────────────────────────
    img.save(out_path, "PNG", quality=95)
    print(f"  [CARD] Saved brand-style card: {out_path}")
    return out_path
