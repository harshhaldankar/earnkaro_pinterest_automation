"""
formula.py - "outfit formula" designs: a few catalogue items laid out as one look, on a clean
cream board, each numbered and labelled. A new image that exists nowhere else, and an idea
("Haldi outfit formula") rather than a price list, which is what gets saved on Pinterest.

  create_formula_pin(items, out, title, subtitle)        1000x1500 Pinterest pin
  create_formula_slide(items, out, title, subtitle, k, n) 1080x1350 Instagram carousel slide
  create_cover_slide(items, out, title, subtitle)         the carousel's first slide
items: [{img, label, price, store}] (2-4), in the order worn: top, bottom, shoes, bag.
"""
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from trends.pins import _font, _on_white

CREAM = (250, 245, 240)
INK = (40, 32, 38)
MUTED = (120, 104, 112)
MAGENTA = (200, 24, 110)


def _rs(v) -> str:
    return "₹{:,}".format(int(round(v)))


def _cutout(path: str, w: int, h: int) -> Image.Image:
    """The item on cream: packshots are trimmed and multiplied in (white becomes cream, no box);
    model photos become a rounded card."""
    im = Image.open(path).convert("RGB")
    out = Image.new("RGB", (w, h), CREAM)
    if _on_white(im):
        box = Image.eval(im.convert("L"), lambda v: 255 if v < 235 else 0).getbbox()
        if box:
            im = im.crop((max(0, box[0] - 10), max(0, box[1] - 10), min(im.width, box[2] + 10), min(im.height, box[3] + 10)))
        s = min(w * 0.9 / im.width, h * 0.9 / im.height)
        p = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        x, y = (w - p.width) // 2, (h - p.height) // 2
        shadow = Image.new("L", (w, h), 0)
        ImageDraw.Draw(shadow).ellipse((x + p.width * 0.15, y + p.height * 0.94, x + p.width * 0.85, y + p.height * 1.03), fill=60)
        out = Image.composite(Image.new("RGB", (w, h), (170, 150, 160)), out, shadow.filter(ImageFilter.GaussianBlur(18)))
        out.paste(ImageChops.multiply(out.crop((x, y, x + p.width, y + p.height)), p), (x, y))
        return out
    s = max(w * 0.92 / im.width, h * 0.92 / im.height)
    p = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    cw, ch = int(w * 0.92), int(h * 0.92)
    p = p.crop(((p.width - cw) // 2, int((p.height - ch) * 0.25), (p.width - cw) // 2 + cw, int((p.height - ch) * 0.25) + ch))
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw, ch), radius=36, fill=255)
    out.paste(p, ((w - cw) // 2, (h - ch) // 2), mask)
    return out


def _badge(d, x, y, n):
    d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=MAGENTA)
    d.text((x, y), str(n), font=_font("Roboto-Bold.ttf", 30), fill=(255, 255, 255), anchor="mm")


def _board(W, H, items, title, subtitle, top, bottom_text):
    """The shared layout: title, items in a 2x2 (or 2x1) grid with numbers and labels, a footer."""
    c = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(c)
    d.text((W / 2, 70), "OUTFIT FORMULA", font=_font("Roboto-Bold.ttf", 26), fill=MAGENTA, anchor="mm")
    f = _font("PlayfairDisplay.ttf", 74 if len(title) < 22 else 60)
    d.text((W / 2, 140), title, font=f, fill=INK, anchor="mm")
    if subtitle:
        d.text((W / 2, 212), subtitle, font=_font("Roboto-Bold.ttf", 30), fill=MUTED, anchor="mm")
    n = len(items)
    cols = 2
    rows = (n + 1) // 2
    gap, pad = 30, 70
    cw = (W - 2 * pad - gap) // cols
    avail = H - top - 150
    ch = min(int(cw * 1.05), (avail - gap * (rows - 1)) // rows - 70)
    for k, it in enumerate(items):
        x = pad + (k % cols) * (cw + gap)
        if n % 2 and k == n - 1:
            x = (W - cw) // 2
        y = top + (k // cols) * (ch + 70 + gap)
        c.paste(_cutout(it["img"], cw, ch), (x, y))
        _badge(d, x + 30, y + 30, k + 1)
        d.text((x + cw / 2, y + ch + 22), it["label"], font=_font("Roboto-Bold.ttf", 28), fill=INK, anchor="mm")
        d.text((x + cw / 2, y + ch + 54), f"{_rs(it['price'])} · {it['store']}", font=_font("Roboto-Bold.ttf", 22), fill=MUTED, anchor="mm")
    d.line((pad, H - 96, W - pad, H - 96), fill=(225, 215, 220), width=2)
    d.text((W / 2, H - 58), bottom_text, font=_font("Roboto-Bold.ttf", 24), fill=MUTED, anchor="mm")
    return c


BEIGE = (246, 233, 212)


def _window_light(w: int, h: int) -> Image.Image:
    """Warm beige with soft diagonal window-light bands and a floor shadow, like a styled flat-lay photo."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    bands = np.sin((x + 0.9 * y) / 170.0) * 0.5 + 0.5          # diagonal light stripes
    bands = np.clip((bands - 0.55) * 3, 0, 1)                   # mostly beige, a few bright bands
    base = np.array(BEIGE, float)[None, None, :]
    light = base * (1 + 0.07 * bands[..., None])
    floor = np.clip((y - h * 0.86) / (h * 0.14), 0, 1)[..., None]  # darker floor at the bottom
    arr = light * (1 - 0.08 * floor)
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return im.filter(ImageFilter.GaussianBlur(22))


def _item_rgba(path: str, w: int, h: int, seed: int = 0) -> Image.Image:
    """The item with its white background removed (packshots) or as a soft-edged card (model photos)."""
    im = Image.open(path).convert("RGB")
    if _on_white(im):
        a = np.asarray(im).astype(int)
        box = Image.eval(im.convert("L"), lambda v: 255 if v < 235 else 0).getbbox() or (0, 0, im.width, im.height)
        im = im.crop(box)
        a = np.asarray(im).astype(int)
        white = (a.min(axis=2) > 232)
        alpha = Image.fromarray(np.where(white, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
        rgba = im.convert("RGBA")
        rgba.putalpha(alpha)
    else:
        rgba = im.convert("RGBA")
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width, im.height), radius=int(min(im.size) * 0.08), fill=255)
        rgba.putalpha(mask)
    s = min(w / rgba.width, h / rgba.height)
    return rgba.resize((max(1, int(rgba.width * s)), max(1, int(rgba.height * s))), Image.LANCZOS)


def _drop(c: Image.Image, item: Image.Image, x: int, y: int, tilt: float = 0):
    if tilt:
        item = item.rotate(tilt, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", c.size)
    sh.paste((60, 40, 30, 110), (x + 18, y + 26, x + 18 + item.width, y + 26 + item.height), item.getchannel("A"))
    c.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    c.alpha_composite(item, (x, y))


def create_combo_pin(items, out, keyword="LINK", price=None, W=1080, H=1350):
    """The 'COMMENT OUTFIT' style: items laid out on warm beige with window light, a big serif
    headline and the combo price. items: 2-4 [{img, ...}] worn order (top, bottom, shoes, bag)."""
    c = _window_light(W, H).convert("RGBA")
    d = ImageDraw.Draw(c)
    f = _font("PlayfairDisplay.ttf", 118)
    a, b = "COMMENT ", keyword.upper()
    wa, wb = d.textlength(a, font=f), d.textlength(b, font=f)
    x0 = (W - wa - wb) / 2
    d.text((x0, 60), a, font=f, fill=(20, 16, 18))
    d.text((x0 + wa, 60), b, font=f, fill=(120, 20, 24))
    total = price if price is not None else sum(i["price"] for i in items)
    sub = f"(  FULL OUTFIT COMBO AT JUST  {_rs(total)}/-  )"
    d.text((W / 2, 215), sub, font=_font("Roboto-Bold.ttf", 34), fill=(70, 60, 60), anchor="mm")
    n = len(items)
    top = 290
    area_h = H - top - 60
    big = [_item_rgba(i["img"], int(W * 0.46), int(area_h * 0.62), k) for k, i in enumerate(items)]
    # layout: 1 top-left (tilted), 2 tall right, 3 bottom-left, 4 small bottom-centre
    if n >= 1:
        _drop(c, big[0], 60, top + 10, tilt=4)
    if n >= 2:
        it = _item_rgba(items[1]["img"], int(W * 0.44), int(area_h * 0.92))
        _drop(c, it, W - it.width - 60, top + 40, tilt=-3)
    if n >= 3:
        it = _item_rgba(items[2]["img"], int(W * 0.40), int(area_h * 0.30))
        _drop(c, it, 80, H - it.height - 70)
    if n >= 4:
        it = _item_rgba(items[3]["img"], int(W * 0.26), int(area_h * 0.26))
        _drop(c, it, int(W * 0.40), H - it.height - 60, tilt=6)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c.convert("RGB").save(out, "JPEG", quality=92)
    return out


def create_formula_pin(items, out, title, subtitle=""):
    total = sum(i["price"] for i in items)
    sub = subtitle or " + ".join(i["label"].split()[-1].lower() for i in items) + f" · whole look {_rs(total)}"
    c = _board(1000, 1500, items, title, sub, 270, "Save this for later  ·  links on getyourdeal")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c.save(out, "JPEG", quality=92)
    return out


def create_formula_slide(items, out, title, subtitle, k, n):
    c = _board(1080, 1350, items, title, subtitle, 260, f"{k} / {n}  ·  swipe  >>" if k < n else "Comment  LINK  and we DM you every link")
    c.save(out, "JPEG", quality=92)
    return out


def create_cover_slide(photos, out, title, subtitle):
    """First slide: big title, the looks' photos as a strip at the bottom."""
    W, H = 1080, 1350
    c = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(c)
    d.text((W / 2, 150), "SAVE THIS", font=_font("Roboto-Bold.ttf", 30), fill=MAGENTA, anchor="mm")
    y = 230
    for ln in title.split("\n"):
        d.text((W / 2, y), ln, font=_font("PlayfairDisplay.ttf", 104), fill=INK, anchor="mt")
        y += 125
    d.text((W / 2, y + 20), subtitle, font=_font("Roboto-Bold.ttf", 36), fill=MUTED, anchor="mt")
    n = min(4, len(photos))
    cw = (W - 60 - 20 * (n - 1)) // n
    for i, p in enumerate(photos[:n]):
        c.paste(_cutout(p, cw, int(cw * 1.25)), (30 + i * (cw + 20), H - int(cw * 1.25) - 120))
    d.text((W / 2, H - 60), "swipe  >>", font=_font("Roboto-Bold.ttf", 30), fill=MUTED, anchor="mm")
    c.save(out, "JPEG", quality=92)
    return out
