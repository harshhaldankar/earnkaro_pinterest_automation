"""
pins.py - the Get Your Deal pin designs (1000x1500, cream with a pink arch, magenta sticker).

  create_template_pin   one product: photo, offer sticker ("₹549 · 63% OFF"), headline, store
  create_collage_pin    a theme: 4 products in a grid, headline, sticker ("8 PICKS UNDER ₹999")

Orange Amazon sale banners get the product cut out of the banner; any other image is framed.
"""
import os
import re
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(__file__), "fonts")
W, H = 1000, 1500
CREAM = (248, 241, 233)
ARCH = (246, 214, 228)
MAGENTA = (200, 24, 110)
INK = (34, 24, 30)
MUTED = (120, 100, 110)
ARCH_BOX = (110, 150, 890, 1060)


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _hsv(im):
    a = np.asarray(im.convert("HSV")).astype(int)
    return a[..., 0] * 360 // 255, a[..., 1], a[..., 2]


def is_orange_banner(path: str) -> bool:
    """Amazon's festival banners: mostly flat, fully saturated orange around the edges."""
    with Image.open(path) as im:
        small = im.convert("RGB").resize((60, 60))
    hue, sat, val = _hsv(small)
    edge = np.concatenate([hue[0], hue[-1], hue[:, 0], hue[:, -1]]), \
        np.concatenate([sat[0], sat[-1], sat[:, 0], sat[:, -1]])
    return float(((edge[0] >= 8) & (edge[0] <= 55) & (edge[1] > 205)).mean()) > 0.6


def cut_out_banner_product(path: str, x_from: float = 0.42):
    """RGBA product from an orange banner. The left side holds Amazon's text, so only the
    right-hand part is used; the orange background and the lights are made transparent."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.crop((int(w * x_from), 0, w, h))
    im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
    hue, sat, val = _hsv(im)
    orange = (hue >= 8) & (hue <= 55) & (sat > 205) & (val > 170)
    glow = (val > 225) & (hue >= 15) & (hue <= 65) & (sat > 60)
    # Background = orange connected to the banner's edge, so orange-ish skin or fabric inside stays.
    # (.copy(): floodfill doesn't write to an image that shares numpy's buffer)
    bg = Image.fromarray(((orange | glow) * 255).astype("uint8")).copy()
    edge_pts = [(x, 0) for x in range(0, bg.width, 6)] + [(x, bg.height - 1) for x in range(0, bg.width, 6)] + \
               [(0, y) for y in range(0, bg.height, 6)] + [(bg.width - 1, y) for y in range(0, bg.height, 6)]
    for pt in edge_pts:
        if bg.getpixel(pt) == 255:
            ImageDraw.floodfill(bg, pt, 128)
    keep = np.asarray(bg) != 128
    # Solid patches of the exact banner orange enclosed by the product (between two models)
    pure = Image.fromarray(((orange & (sat > 240) & (val > 235)) * 255).astype("uint8"))
    keep &= ~(np.asarray(pure.filter(ImageFilter.MinFilter(15)).filter(ImageFilter.MaxFilter(17))) > 0)
    mask = Image.fromarray((keep * 255).astype("uint8")).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))

    # Keep only large connected parts (the products), not strings of lights
    small = np.asarray(mask.resize((mask.width // 6, mask.height // 6), Image.BOX)) > 128
    seen = np.zeros_like(small)
    big = np.zeros_like(small)
    for y in range(small.shape[0]):
        for x in range(small.shape[1]):
            if not small[y, x] or seen[y, x]:
                continue
            comp, q = [], deque([(y, x)])
            seen[y, x] = True
            while q:
                cy, cx = q.popleft()
                comp.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < small.shape[0] and 0 <= nx < small.shape[1] and small[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(comp) > small.size * 0.004:
                for cy, cx in comp:
                    big[cy, cx] = True
    big_mask = Image.fromarray((big * 255).astype("uint8")).resize(mask.size, Image.NEAREST).filter(ImageFilter.MaxFilter(9))
    alpha = Image.fromarray(np.minimum(np.asarray(mask), np.asarray(big_mask)).astype("uint8")).filter(ImageFilter.GaussianBlur(1.2))
    bbox = alpha.getbbox()
    if not bbox or (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 0.05 * alpha.width * alpha.height:
        return None
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out.crop(bbox)


def _framed(path: str):
    """A product photo as a rounded, framed card."""
    photo = Image.open(path).convert("RGB")
    s = min(660 / photo.width, 800 / photo.height)
    photo = photo.resize((max(1, int(photo.width * s)), max(1, int(photo.height * s))), Image.LANCZOS)
    pad = 14
    card = Image.new("RGBA", (photo.width + 2 * pad, photo.height + 2 * pad), (0, 0, 0, 0))
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=30, fill=255)
    card.paste((255, 255, 255, 255), (0, 0), m)
    pm = Image.new("L", photo.size, 0)
    ImageDraw.Draw(pm).rounded_rectangle([0, 0, photo.width - 1, photo.height - 1], radius=20, fill=255)
    card.paste(photo, (pad, pad), pm)
    return card


def offer_text(price=None, discount=None, name: str = "") -> str:
    """Sticker text: '₹1,169 · 75% OFF', 'UNDER ₹799', 'MIN 70% OFF', 'UP TO 90% OFF'."""
    def num(v):
        try:
            return float(re.sub(r"[^\d.]", "", str(v)) or 0)
        except ValueError:
            return 0
    p, d = num(price), int(num(discount))
    if p and d:
        return f"₹{p:,.0f}  ·  {d}% OFF"
    if p:
        return f"ONLY ₹{p:,.0f}"
    band = re.search(r"(under|below|starting at|from)\s*(?:rs\.?|₹)\s*([\d,]+)", name, re.I)
    if band:
        return f"{band.group(1).upper()} ₹{band.group(2)}"
    kind = re.search(r"\b(min(?:imum)?|up\s*to|upto|flat)\b\.?\s*(\d+)\s*%", name, re.I)
    if kind:
        word = {"min": "MIN", "minimum": "MIN", "flat": "FLAT"}.get(kind.group(1).lower(), "UP TO")
        return f"{word} {kind.group(2)}% OFF"
    if d:
        return f"{d}% OFF"
    return "DEAL ALERT"


def clean_headline(text: str) -> str:
    """Name for the pin: no emoji, no model codes ('DK11421-5'), no discount wording that the
    sticker already shows ('upto 80% Discount')."""
    text = re.sub(r"[\U00010000-\U0010FFFF☀-➿⬀-⯿️]", "", text)
    text = re.sub(r"\s*\b(?:at\s+)?(?:min(?:imum)?|up\s*to|upto|flat)\s*\d+\s*%\s*(?:off|discount)\b", "", text, flags=re.I)
    words = [w for w in text.split()
             if not (len(w) >= 6 and re.search(r"\d", w) and re.search(r"[A-Z]", w) and not re.search(r"[a-z]", w))]
    return " ".join(words).strip(" -–|,:")


def _headline_lines(draw, text, max_w=860):
    """One line if it fits at a readable size, otherwise two lines at a fixed size, the second
    one cut with an ellipsis when the name is very long."""
    for size in range(76, 59, -4):
        if draw.textlength(text, font=_font("PlayfairDisplay.ttf", size)) <= max_w:
            return [text], size
    size = 58
    f = _font("PlayfairDisplay.ttf", size)
    words, first = text.split(), []
    while words and draw.textlength(" ".join(first + words[:1]), font=f) <= max_w:
        first.append(words.pop(0))
    if not first:
        first = [words.pop(0)]
    rest = " ".join(words)
    if draw.textlength(rest, font=f) > max_w:
        while rest and draw.textlength(rest + "…", font=f) > max_w:
            rest = rest.rsplit(" ", 1)[0] if " " in rest else rest[:-1]
        rest = rest.rstrip(",–-&: ") + "…"
    return [" ".join(first)] + ([rest] if rest else []), size


def create_template_pin(img_path: str, out_path: str, headline: str, offer: str, store: str = "",
                        clean_path: str = None):
    """Write the pin to out_path. With clean_path, also writes the product on the plain background
    without text (for reels). Returns (out_path, clean_path or None), or (None, None) on failure."""
    try:
        product = cut_out_banner_product(img_path) if is_orange_banner(img_path) else None
        cutout = product is not None
        if not cutout:
            product = _framed(img_path)

        c = Image.new("RGB", (W, H), CREAM)
        arch = Image.new("L", (W, H), 0)
        ImageDraw.Draw(arch).rounded_rectangle(ARCH_BOX, radius=390, fill=255)
        c.paste(Image.new("RGB", (W, H), ARCH), (0, 0), arch.filter(ImageFilter.GaussianBlur(2)))

        p = product
        s = min((700 if cutout else 720) / p.width, 820 / p.height)
        p = p.resize((max(1, int(p.width * s)), max(1, int(p.height * s))), Image.LANCZOS)
        x = (W - p.width) // 2
        y = 1040 - p.height if cutout else (ARCH_BOX[1] + ARCH_BOX[3]) // 2 - p.height // 2
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shadow.paste((60, 20, 40, 90 if cutout else 70), (x + 10, y + 22), p.getchannel("A"))
        c = Image.alpha_composite(c.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(22)))
        c.paste(p, (x, y), p)

        if clean_path:
            clean = c.convert("RGB").crop((60, 110, 940, 1090))
            clean.save(clean_path, "JPEG", quality=92)

        d = ImageDraw.Draw(c)
        d.rounded_rectangle([60, 56, 330, 106], radius=25, fill=INK)
        d.text((195, 81), "GET YOUR DEAL", font=_font("Poppins-Black.ttf", 22), fill=CREAM, anchor="mm")

        size = 74
        while size > 40 and d.textlength(offer, font=_font("Poppins-Black.ttf", size)) > 780:
            size -= 4
        f = _font("Poppins-Black.ttf", size)
        tw = d.textlength(offer, font=f)
        d.rounded_rectangle([(W - tw) / 2 - 34, 1095, (W + tw) / 2 + 34, 1205], radius=22, fill=MAGENTA)
        d.text((W / 2, 1152), offer, font=f, fill="white", anchor="mm")

        lines, hsize = _headline_lines(d, clean_headline(headline) or headline.strip())
        hf = _font("PlayfairDisplay.ttf", hsize)
        if len(lines) == 1:
            d.text((W / 2, 1290), lines[0], font=hf, fill=INK, anchor="mm")
            store_y = 1385
        else:
            d.text((W / 2, 1270), lines[0], font=hf, fill=INK, anchor="mm")
            d.text((W / 2, 1270 + hsize + 8), lines[1], font=hf, fill=INK, anchor="mm")
            store_y = 1270 + 2 * hsize + 50
        if store:
            d.text((W / 2, store_y), f"on {store}", font=_font("Poppins-Black.ttf", 30), fill=MUTED, anchor="mm")

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        c.convert("RGB").save(out_path, "JPEG", quality=90)
        return out_path, clean_path
    except Exception as e:
        print(f"  [WARN] Pin template failed: {e}")
        return None, None


def _cover(path: str, w: int, h: int):
    """Photo cropped to fill w x h (product photos are portrait; keep the top, where the product is)."""
    im = Image.open(path).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    left = (im.width - w) // 2
    top = min((im.height - h) // 2, round(im.height * 0.08)) if im.height > h else 0
    return im.crop((left, top, left + w, top + h))


def create_collage_pin(img_paths: list, out_path: str, headline: str, offer: str, footer: str = "Shop every look on Get Your Deal"):
    """Theme pin: headline at the top, 4 product photos in a 2x2 grid, offer sticker, footer."""
    try:
        photos = [p for p in img_paths if p and os.path.exists(p)][:4]
        if len(photos) < 4:
            return None
        c = Image.new("RGB", (W, H), CREAM)
        d = ImageDraw.Draw(c)
        d.rounded_rectangle([60, 56, 330, 106], radius=25, fill=INK)
        d.text((195, 81), "GET YOUR DEAL", font=_font("Poppins-Black.ttf", 22), fill=CREAM, anchor="mm")

        lines, hsize = _headline_lines(d, clean_headline(headline) or headline.strip())
        hf = _font("PlayfairDisplay.ttf", hsize)
        y = 175
        for line in lines:
            d.text((W / 2, y), line, font=hf, fill=INK, anchor="mm")
            y += hsize + 8
        grid_top = y + 10

        gap, margin = 18, 60
        cw = (W - 2 * margin - gap) // 2
        ch = min(round(cw * 1.25), (1250 - grid_top - gap) // 2)
        canvas = c.convert("RGBA")
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        boxes = [(margin + (i % 2) * (cw + gap), grid_top + (i // 2) * (ch + gap)) for i in range(4)]
        for x, yy in boxes:
            sd.rounded_rectangle([x, yy + 10, x + cw, yy + ch + 10], radius=26, fill=(60, 20, 40, 60))
        canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(16)))
        mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=26, fill=255)
        for (x, yy), p in zip(boxes, photos):
            canvas.paste(_cover(p, cw, ch), (x, yy), mask)
        d = ImageDraw.Draw(canvas)

        sy = grid_top + 2 * ch + gap + 40
        size = 64
        while size > 40 and d.textlength(offer, font=_font("Poppins-Black.ttf", size)) > 780:
            size -= 4
        f = _font("Poppins-Black.ttf", size)
        tw = d.textlength(offer, font=f)
        d.rounded_rectangle([(W - tw) / 2 - 34, sy, (W + tw) / 2 + 34, sy + 96], radius=22, fill=MAGENTA)
        d.text((W / 2, sy + 48), offer, font=f, fill="white", anchor="mm")
        d.text((W / 2, min(H - 50, sy + 150)), footer, font=_font("Poppins-Black.ttf", 28), fill=MUTED, anchor="mm")

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        canvas.convert("RGB").save(out_path, "JPEG", quality=90)
        return out_path
    except Exception as e:
        print(f"  [WARN] Collage pin failed: {e}")
        return None


# ---------------------------------------------------------------------------------------------
# Natural designs (Nov 2026): the photo does the work, like an editorial or mood-board pin.
# No stickers or "% OFF"; a quiet serif title and the price in small type.
# ---------------------------------------------------------------------------------------------
PASTELS = [((250, 228, 236), (226, 236, 250)),   # blush -> powder blue
           ((246, 232, 250), (228, 248, 240)),   # lavender -> mint
           ((252, 238, 226), (246, 228, 238))]   # peach -> blush
SOFT_INK = (40, 32, 38)


def _on_white(im: Image.Image) -> bool:
    """True for packshots on a white background (makeup, shoes, decor), not model photos."""
    a = np.asarray(im.convert("L").resize((60, 80)), dtype=np.int16)
    edge = np.concatenate([a[:4].ravel(), a[-4:].ravel(), a[:, :4].ravel(), a[:, -4:].ravel()])
    return float((edge > 238).mean()) > 0.85


def _pastel(w: int, h: int, seed: int) -> Image.Image:
    top, bottom = PASTELS[seed % len(PASTELS)]
    g = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top) * (1 - g) + np.array(bottom) * g).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, w, axis=1), "RGB")


def _studio(im: Image.Image, w: int, h: int, seed: int) -> Image.Image:
    """A white-background packshot on a pastel studio: multiply turns the white into the pastel,
    then a soft shadow under the product."""
    bg = _pastel(w, h, seed)
    box = Image.eval(im.convert("L"), lambda v: 255 if v < 235 else 0).getbbox()
    if box:  # trim the packshot's white padding so the product, not the padding, fills the frame
        pad = 12
        im = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
    s = min(w * 0.70 / im.width, h * 0.62 / im.height)
    p = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    x, y = (w - p.width) // 2, int(h * 0.44 - p.height / 2)
    shadow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(shadow).ellipse((x + p.width * 0.18, y + p.height * 0.96, x + p.width * 0.82, y + p.height * 1.04),
                                   fill=70)
    bg = Image.composite(Image.new("RGB", (w, h), (150, 120, 135)), bg, shadow.filter(ImageFilter.GaussianBlur(28)))
    patch = bg.crop((x, y, x + p.width, y + p.height))
    from PIL import ImageChops
    bg.paste(ImageChops.multiply(patch, p), (x, y))
    return bg


def _fill(path: str, w: int, h: int, seed: int = 0) -> Image.Image:
    im = Image.open(path).convert("RGB")
    return _studio(im, w, h, seed) if _on_white(im) else _cover(path, w, h)


def create_natural_pin(img_path: str, out_path: str, title: str, line: str = "", seed: int = 0):
    """One product: full-bleed photo (or pastel studio), soft fade at the bottom with a serif
    title and one small line ("Black Banarasi Saree · ₹827 on Myntra")."""
    try:
        band = 300  # the photo keeps the top; title and price sit on a cream band below it
        c = Image.new("RGBA", (W, H), (250, 245, 240, 255))
        c.paste(_fill(img_path, W, H - band + 40, seed), (0, 0))
        fade = Image.new("RGBA", (W, 90))
        fd = ImageDraw.Draw(fade)
        for y in range(90):
            fd.line((0, y, W, y), fill=(250, 245, 240, int(255 * y / 90)))
        c.alpha_composite(fade, (0, H - band - 50))
        d = ImageDraw.Draw(c)
        lines, size = _headline_lines(d, clean_headline(title) or title.strip(), max_w=860)
        hf = _font("PlayfairDisplay.ttf", size + 6)
        y = H - band + 40 + (40 if len(lines) == 1 else 0)
        for ln in lines:
            d.text((W / 2, y), ln, font=hf, fill=SOFT_INK, anchor="mm")
            y += size + 14
        if line:
            f = _font("Roboto-Bold.ttf", 34)
            while d.textlength(line, font=f) > 880 and f.size > 22:
                f = _font("Roboto-Bold.ttf", f.size - 2)
            d.text((W / 2, y + 26), line, font=f, fill=(95, 80, 88), anchor="mm")
        d.text((W / 2, H - 46), "getyourdeal", font=_font("Roboto-Bold.ttf", 22), fill=(150, 130, 140), anchor="mm")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        c.convert("RGB").save(out_path, "JPEG", quality=90)
        return out_path
    except Exception as e:
        print(f"  [WARN] Natural pin failed: {e}")
        return None


def create_moodboard_pin(img_paths: list, out_path: str, title: str, subtitle: str = "", seed: int = 0):
    """A theme: serif title on a cream band, 4 photos edge to edge in a 2x2 mood board."""
    try:
        photos = [p for p in img_paths if p and os.path.exists(p)][:4]
        if len(photos) < 4:
            return None
        c = Image.new("RGB", (W, H), (250, 245, 240))
        d = ImageDraw.Draw(c)
        lines, size = _headline_lines(d, clean_headline(title) or title.strip(), max_w=880)
        hf = _font("PlayfairDisplay.ttf", size + 4)
        y = 95
        for ln in lines:
            d.text((W / 2, y), ln, font=hf, fill=SOFT_INK, anchor="mm")
            y += size + 12
        if subtitle:
            d.text((W / 2, y + 8), subtitle, font=_font("Roboto-Bold.ttf", 32), fill=(110, 92, 102), anchor="mm")
            y += 50
        top, gap = int(y + 30), 8
        cw, ch = (W - gap) // 2, (H - top - gap) // 2
        for i, p in enumerate(photos):
            c.paste(_fill(p, cw, ch, seed + i), ((i % 2) * (cw + gap), top + (i // 2) * (ch + gap)))
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        c.save(out_path, "JPEG", quality=90)
        return out_path
    except Exception as e:
        print(f"  [WARN] Mood board pin failed: {e}")
        return None
