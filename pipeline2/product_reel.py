"""
product_reel.py — fast, high-energy 9:16 Instagram reel built around the product itself.

Styled after an AI-generated (Veo) deal ad: a magenta set with twinkling sparkles, smooth
push-ins, a festival sale badge and a "GET THE DEAL" end card where a cursor taps LINK IN BIO.

Structure (about 9 seconds):
  1. Snap zoom   — the product card springs in on the magenta set; price strip and name
  2. Close-ups   — full-bleed cuts on detail crops (top half, bottom half, other photos)
  3. Sale badge  — a maroon-and-gold festival badge with the discount pops in, price below
  4. End card    — GET THE DEAL, the product, an arrow bouncing down, cursor taps LINK IN BIO

Frames are drawn with Pillow and piped to ffmpeg as raw RGB, so the only dependency beyond
Pillow is an ffmpeg binary (system ffmpeg or imageio-ffmpeg).
"""
import math
import os
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline2.reel_generator import get_ffmpeg_cmd

W, H = 1080, 1920
FPS = 30
SNAP_SECONDS = 1.3
CUT_SECONDS = 0.7           # per close-up
MAX_CUTS = 4
BADGE_SECONDS = 2.0
END_CARD_SECONDS = 3.0
AUDIO_DIR = Path("assets/audio")
FONT_DIR = Path("pipeline2/fonts")
FALLBACK_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]
FONT_FILES = {"sans": "Roboto-Bold.ttf", "display": "Poppins-Black.ttf", "serif": "PlayfairDisplay.ttf"}

PINK_TOP = (225, 0, 130)
PINK_BOTTOM = (255, 90, 175)
PINK_DEEP = (205, 20, 115)  # LINK IN BIO pill
MAROON = (120, 14, 55)
GOLD = (240, 190, 90)
YELLOW = (255, 214, 0)
INK = (255, 255, 255)
MUTED = (240, 240, 240)
DARK = (35, 18, 40)


def _font(size: int, kind: str = "sans") -> ImageFont.FreeTypeFont:
    paths = [FONT_DIR / FONT_FILES[kind], FONT_DIR / FONT_FILES["sans"], *FALLBACK_FONTS]
    for p in paths:
        if os.path.exists(p):
            f = ImageFont.truetype(str(p), size)
            if kind == "serif" and str(p).endswith("PlayfairDisplay.ttf"):
                f.set_variation_by_name("Bold")
            return f
    return ImageFont.load_default()


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale and centre-crop to exactly w x h."""
    scale = max(w / im.width, h / im.height)
    r = im.resize((max(w, int(im.width * scale + 0.5)), max(h, int(im.height * scale + 0.5))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def _clamp(t: float) -> float:
    return min(max(t, 0.0), 1.0)


def _ease_out(t: float) -> float:
    return 1 - (1 - _clamp(t)) ** 3


def _ease_in_out(t: float) -> float:
    t = _clamp(t)
    return 3 * t * t - 2 * t * t * t


def _overshoot(t: float) -> float:
    """0 -> ~1.15 -> 1 pop used for the card, badge and headline."""
    t = _clamp(t)
    c = 2.2
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def _wrap(draw, text: str, font, max_w: int, max_lines: int) -> list:
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and " ".join(lines) != text:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines


def _pink_set() -> Image.Image:
    """Magenta gradient with a soft glow in the middle."""
    grad = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        grad.putpixel((0, y), tuple(int(PINK_TOP[i] * (1 - t) + PINK_BOTTOM[i] * t) for i in range(3)))
    bg = grad.resize((W, H), Image.BILINEAR)
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.05, H * 0.25, W * 0.95, H * 0.75), fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return Image.composite(Image.new("RGB", (W, H), (255, 190, 225)), bg, glow)


def _sparkles(rng: random.Random, n: int = 34) -> list:
    return [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(8, 24), rng.uniform(0, math.tau)) for _ in range(n)]


def _draw_sparkles(frame: Image.Image, sparkles: list, t: float):
    """Four-point stars twinkling at their own phase."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for x, y, s, ph in sparkles:
        a = int(255 * (0.25 + 0.75 * abs(math.sin(t * 3.0 + ph))))
        r = s * (0.6 + 0.4 * abs(math.sin(t * 3.0 + ph)))
        d.polygon([(x, y - r), (x + r * 0.22, y - r * 0.22), (x + r, y), (x + r * 0.22, y + r * 0.22),
                   (x, y + r), (x - r * 0.22, y + r * 0.22), (x - r, y), (x - r * 0.22, y - r * 0.22)],
                  fill=(255, 255, 255, a))
    frame.paste(ov, (0, 0), ov)


def _card(src: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Photo with rounded corners, a white border and a soft drop shadow (RGBA)."""
    scale = min(max_w / src.width, max_h / src.height)
    ph = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
    border, pad, radius = 12, 50, 40
    cw, ch = ph.width + 2 * border, ph.height + 2 * border
    out = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("L", out.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle((pad, pad + 18, pad + cw, pad + ch + 18), radius=radius, fill=120)
    out.paste(Image.new("RGBA", out.size, (60, 0, 30, 255)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(22)))
    frame = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=radius, fill=255)
    out.paste(Image.new("RGBA", (cw, ch), (255, 255, 255, 255)), (pad, pad), frame)
    mask = Image.new("L", ph.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=radius - border, fill=255)
    out.paste(ph, (pad + border, pad + border), mask)
    return out


def _paste_center(frame: Image.Image, im: Image.Image, cx: float, cy: float, scale: float = 1.0):
    if scale <= 0.02:
        return
    if abs(scale - 1.0) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    frame.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def _detail_crops(photos: list) -> list:
    """Close-up shots: top and bottom detail of the main photo, then the other photos."""
    main = photos[0]
    w, h = main.size
    crops = [main.crop((int(w * 0.06), int(h * 0.04), int(w * 0.94), int(h * 0.56))),
             main.crop((int(w * 0.08), int(h * 0.44), int(w * 0.92), int(h * 0.96)))]
    crops += photos[1:]
    return crops[:MAX_CUTS]


def _price_strip(price: str, mrp: str, discount: str) -> Image.Image:
    """Top band: discount pill, price, struck MRP."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x, y = 70, 130
    if discount:
        f = _font(60, "display")
        txt = f"{discount} OFF"
        tw = d.textlength(txt, font=f)
        d.rounded_rectangle((x, y, x + tw + 56, y + 96), radius=48, fill=YELLOW, outline=DARK, width=5)
        d.text((x + 28, y + 8), txt, font=f, fill=DARK)
        x += tw + 90
    if price:
        f = _font(96, "display")
        d.text((x, y - 22), price, font=f, fill=INK, stroke_width=6, stroke_fill=DARK)
        if mrp:
            pw = d.textlength(price, font=f)
            fm = _font(46)
            mx, my = x + pw + 24, y + 30
            if mx + d.textlength(mrp, font=fm) < W - 40:
                d.text((mx, my), mrp, font=fm, fill=MUTED, stroke_width=3, stroke_fill=DARK)
                d.line((mx, my + 27, mx + d.textlength(mrp, font=fm), my + 27), fill=MUTED, width=5)
    return ov


def _name_band(title: str, store: str) -> Image.Image:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = _font(58)
    lines = _wrap(d, title, f, W - 140, 2)
    y = H - 330
    for ln in lines:
        d.text((70, y), ln, font=f, fill=INK, stroke_width=4, stroke_fill=DARK)
        y += 74
    if store:
        d.text((70, y + 10), f"on {store}", font=_font(48), fill=YELLOW, stroke_width=3, stroke_fill=DARK)
    return ov


def _star(cx: float, cy: float, r: float, inner: float) -> list:
    """Eight-point star: two squares rotated 45 degrees apart."""
    pts = []
    for i in range(16):
        rad = r if i % 2 == 0 else r * inner
        a = math.pi * i / 8 - math.pi / 2
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts


def _badge(discount: str) -> Image.Image:
    """Maroon-and-gold festival badge with the discount and a LIVE NOW ribbon."""
    size = 900
    b = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    c = size / 2
    d.polygon(_star(c, c - 20, 400, 0.86), fill=GOLD)
    d.polygon(_star(c, c - 20, 372, 0.86), fill=MAROON)
    for i in range(48):  # marquee dots inside the rim
        a = math.tau * i / 48
        x, y = c + 300 * math.cos(a), c - 20 + 300 * math.sin(a)
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=GOLD)
    lines = [("Mega Deal", _font(96, "serif")), (f"{discount} OFF" if discount else "Deal of", _font(150, "serif"))]
    if not discount:
        lines.append(("the Day", _font(110, "serif")))
    y = c - 230
    for txt, f in lines:
        tw = d.textlength(txt, font=f)
        d.text((c - tw / 2, y), txt, font=f, fill=GOLD, stroke_width=2, stroke_fill=(90, 8, 40))
        y += f.size * 1.15
    # Ribbon
    rw, rh, ry = 600, 120, c + 200
    d.polygon([(c - rw / 2 - 60, ry + 20), (c - rw / 2 + 10, ry + 20), (c - rw / 2 + 10, ry + rh + 20),
               (c - rw / 2 - 60, ry + rh + 20), (c - rw / 2 - 25, ry + rh / 2 + 20)], fill=(190, 140, 60))
    d.polygon([(c + rw / 2 + 60, ry + 20), (c + rw / 2 - 10, ry + 20), (c + rw / 2 - 10, ry + rh + 20),
               (c + rw / 2 + 60, ry + rh + 20), (c + rw / 2 + 25, ry + rh / 2 + 20)], fill=(190, 140, 60))
    d.rectangle((c - rw / 2, ry, c + rw / 2, ry + rh), fill=GOLD)
    f = _font(72, "display")
    tw = d.textlength("LIVE NOW", font=f)
    d.text((c - tw / 2, ry + 12), "LIVE NOW", font=f, fill=MAROON)
    return b


def _headline() -> Image.Image:
    """'GET THE DEAL' with accent ticks, slightly tilted like a sticker."""
    f = _font(132, "display")
    im = Image.new("RGBA", (1040, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    a, b = "GET THE ", "DEAL"
    total = d.textlength(a + b, font=f)
    x = (im.width - total) / 2
    d.text((x, 60), a, font=f, fill=INK, stroke_width=9, stroke_fill=DARK)
    d.text((x + d.textlength(a, font=f), 60), b, font=f, fill=YELLOW, stroke_width=9, stroke_fill=DARK)
    for dx, dy, ang in ((-70, 30, -150), (-50, 0, -115), (-20, -10, -80)):  # ticks, top-left
        r1, r2 = 26, 62
        ax, ay = x + dx + 40, 80 + dy
        rad = math.radians(ang)
        d.line((ax + r1 * math.cos(rad), ay + r1 * math.sin(rad), ax + r2 * math.cos(rad), ay + r2 * math.sin(rad)),
               fill=YELLOW, width=10)
    return im.rotate(4, resample=Image.BICUBIC, expand=True)


def _arrow(d: ImageDraw.ImageDraw, cx: float, top: float):
    """Downward outlined arrow: shaft and head."""
    pts = [(cx - 26, top), (cx + 26, top), (cx + 26, top + 80), (cx + 70, top + 80),
           (cx, top + 160), (cx - 70, top + 80), (cx - 26, top + 80)]
    d.polygon(pts, fill=INK, outline=DARK, width=7)


def _cursor(d: ImageDraw.ImageDraw, x: float, y: float):
    """Mouse pointer with its tip at (x, y)."""
    pts = [(0, 0), (0, 74), (18, 57), (32, 88), (45, 82), (31, 52), (55, 52)]
    d.polygon([(x + px, y + py) for px, py in pts], fill=INK, outline=DARK, width=5)


def create_product_reel(image_paths: list, out_path: str, title: str, price: str = "",
                        mrp: str = "", discount: str = "", store: str = "") -> str | None:
    """
    Render the reel. price/mrp are display strings ("₹2,159"), discount like "55%".
    Returns out_path, or None if there's no usable image or ffmpeg fails.
    """
    photos, seen = [], set()
    for p in image_paths[:5]:
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        key = im.resize((16, 16)).tobytes()  # EarnKaro sometimes repeats the main shot
        if key not in seen:
            seen.add(key)
            photos.append(im)
    if not photos:
        return None

    rng = random.Random(title)
    main = photos[0]
    pink = _pink_set()
    sparkles = _sparkles(rng)
    hero = _card(main, int(W * 0.80), int(H * 0.52))
    end_card = _card(main, int(W * 0.74), int(H * 0.41))
    closeups = [_cover(c, int(W * 1.12), int(H * 1.12)) for c in _detail_crops(photos)]
    strip, name, badge, headline = (_price_strip(price, mrp, discount), _name_band(title, store),
                                    _badge(discount), _headline())

    snap_n, cut_n, badge_n, end_n = (int(s * FPS) for s in (SNAP_SECONDS, CUT_SECONDS, BADGE_SECONDS, END_CARD_SECONDS))
    duration = (snap_n + cut_n * len(closeups) + badge_n + end_n) / FPS

    def frames():
        t_abs = 0.0
        # 1. Snap zoom: the card springs in on the magenta set
        for k in range(snap_n):
            t_abs += 1 / FPS
            f = pink.copy()
            _draw_sparkles(f, sparkles, t_abs)
            _paste_center(f, hero, W / 2, H * 0.52, 0.35 + 0.65 * _overshoot(k / 11) + 0.04 * (k / snap_n))
            f.paste(strip, (0, 0), strip)
            if k >= 10:
                f.paste(name, (0, 0), name)
            yield f
        # 2. Close-ups: full-bleed with a smooth push-in and drift
        for i, big in enumerate(closeups):
            drift = 1 if i % 2 == 0 else -1
            for k in range(cut_n):
                t_abs += 1 / FPS
                z = 1.0 + 0.10 * _ease_in_out(k / cut_n)
                ww, hh = big.width / (1.12 * z) * 1.0, big.height / (1.12 * z)
                cx = big.width / 2 + drift * 30 * (k / cut_n)
                box = (cx - ww / 2, (big.height - hh) / 2, cx + ww / 2, (big.height + hh) / 2)
                f = big.resize((W, H), Image.BILINEAR, box=box)
                f.paste(strip, (0, 0), strip)
                yield f
        # 3. Festival badge with the discount, price underneath
        fp, fm = _font(120, "display"), _font(60)
        for k in range(badge_n):
            t_abs += 1 / FPS
            f = pink.copy()
            _draw_sparkles(f, sparkles, t_abs)
            wobble = badge.rotate(3 * math.sin(k / FPS * 2.4), resample=Image.BILINEAR)
            _paste_center(f, wobble, W / 2, H * 0.40, 0.9 * _overshoot(k / 12))
            if k >= 12 and price:
                d = ImageDraw.Draw(f)
                txt = f"Only {price}"
                tw = d.textlength(txt, font=fp)
                y = H * 0.70 + 40 * (1 - _ease_out((k - 12) / 8))
                d.text(((W - tw) / 2, y), txt, font=fp, fill=INK, stroke_width=8, stroke_fill=DARK)
                if mrp:
                    mt = f"MRP {mrp}"
                    mw = d.textlength(mt, font=fm)
                    d.text(((W - mw) / 2, y + 170), mt, font=fm, fill=MUTED, stroke_width=3, stroke_fill=DARK)
                    d.line(((W - mw) / 2, y + 205, (W + mw) / 2, y + 205), fill=MUTED, width=5)
            yield f
        # 4. End card: GET THE DEAL, the product, arrow, cursor taps LINK IN BIO
        fpill = _font(64, "display")
        pill_txt = "LINK IN BIO"
        tap_at, cursor_from = int(1.6 * FPS), int(0.9 * FPS)
        for k in range(end_n):
            t_abs += 1 / FPS
            f = pink.copy()
            _draw_sparkles(f, sparkles, t_abs)
            _paste_center(f, headline, W / 2, H * 0.15, _overshoot(k / 10))
            _paste_center(f, end_card, W / 2, H * 0.45, _overshoot((k - 4) / 10))
            d = ImageDraw.Draw(f)
            if k >= 8:
                _arrow(d, W / 2, H * 0.675 + 24 * abs(math.sin(k / FPS * math.pi * 2.0)))
            # Pill presses in when the cursor taps it
            press = 0.92 if tap_at <= k < tap_at + 5 else 1.0
            tw = d.textlength(pill_txt, font=fpill)
            pw, ph = (tw + 130) * press, 130 * press
            px, py = W / 2, H * 0.81
            tip = px + (tw + 130) / 2 - 45  # tap the pill's right end, clear of the text
            if k >= 8:
                d.rounded_rectangle((px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2), radius=ph / 2,
                                    fill=PINK_DEEP, outline=INK, width=8)
                fp2 = _font(int(64 * press), "display")
                tw2 = d.textlength(pill_txt, font=fp2)
                d.text((px - tw2 / 2, py - ph / 2 + 22 * press), pill_txt, font=fp2, fill=INK)
            if k >= tap_at:  # ripple from the tap
                r = 30 + (k - tap_at) * 14
                if r < 260:
                    d.ellipse((tip - r, py - r, tip + r, py + r), outline=INK,
                              width=max(2, 10 - (k - tap_at) // 2))
            if k >= cursor_from:
                p = _ease_out((k - cursor_from) / (tap_at - cursor_from))
                _cursor(d, W * 0.95 + (tip - W * 0.95) * p, H * 0.97 + (py - 10 - H * 0.97) * p)
            yield f

    audio = (sorted(AUDIO_DIR.glob("*upbeat*.ogg")) or sorted(AUDIO_DIR.glob("*.ogg"))) if AUDIO_DIR.exists() else []
    cmd = [get_ffmpeg_cmd(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(random.choice(audio))]
        cmd += ["-filter_complex",
                f"[1:a]atrim=0:{duration:.2f},afade=t=in:st=0:d=0.2,afade=t=out:st={duration - 1.0:.2f}:d=1.0[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{duration:.2f}", out_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames():
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0 or not os.path.exists(out_path):
            print(f"  [REEL] ffmpeg failed: {err[-300:]}")
            return None
    except (BrokenPipeError, OSError) as e:
        print(f"  [REEL] ffmpeg pipe error: {e} {proc.stderr.read().decode(errors='ignore')[-300:]}")
        return None
    return out_path
