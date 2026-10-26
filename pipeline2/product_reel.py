"""
product_reel.py — fast, high-energy 9:16 Instagram reel built around the product itself.

Structure (about 9 seconds):
  1. Snap zoom   — the product slams in from 1.8x with a white flash; name and price strip
  2. Jump cuts   — quick punch-in cuts on detail crops (top half, bottom half, other photos)
  3. Badge pan   — the camera pans across the full-bleed photo while a sale badge pops in
  4. End card    — bold "LINK IN BIO" with an arrow bouncing downward

Frames are drawn with Pillow and piped to ffmpeg as raw RGB, so the only dependency beyond
Pillow is an ffmpeg binary (system ffmpeg or imageio-ffmpeg).
"""
import math
import os
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from pipeline2.reel_generator import get_ffmpeg_cmd

W, H = 1080, 1920
FPS = 30
SNAP_SECONDS = 1.2
CUT_SECONDS = 0.65          # per jump cut
MAX_CUTS = 5
PAN_SECONDS = 2.2
END_CARD_SECONDS = 2.4
AUDIO_DIR = Path("assets/audio")
FONT_PATHS = [
    "pipeline2/fonts/Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]

ACCENT = (255, 45, 85)      # discount pill, end-card gradient top
ACCENT_2 = (255, 140, 0)    # end-card gradient bottom
BADGE = (255, 214, 0)
INK = (255, 255, 255)
MUTED = (235, 235, 235)
DARK = (20, 20, 20)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale and centre-crop to exactly w x h."""
    scale = max(w / im.width, h / im.height)
    r = im.resize((max(w, int(im.width * scale + 0.5)), max(h, int(im.height * scale + 0.5))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def _ease_out(t: float) -> float:
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def _ease_in_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 3 * t * t - 2 * t * t * t


def _overshoot(t: float) -> float:
    """0 -> ~1.15 -> 1 pop used for badges and the CTA."""
    t = min(max(t, 0.0), 1.0)
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


def _backdrop(src: Image.Image) -> Image.Image:
    """Blurred, saturated full-bleed copy of the photo."""
    bg = _cover(src, W, H).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Color(bg).enhance(1.6)
    return Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.30)


def _fit(src: Image.Image, max_w: int, max_h: int) -> Image.Image:
    scale = min(max_w / src.width, max_h / src.height)
    return src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)


def _detail_crops(photos: list) -> list:
    """Jump-cut shots: top and bottom detail of the main photo, then the other photos."""
    main = photos[0]
    w, h = main.size
    crops = [main.crop((int(w * 0.06), int(h * 0.05), int(w * 0.94), int(h * 0.55))),
             main.crop((int(w * 0.10), int(h * 0.42), int(w * 0.90), int(h * 0.95)))]
    crops += photos[1:]
    return crops[:MAX_CUTS]


def _price_strip(price: str, mrp: str, discount: str) -> Image.Image:
    """Top band: discount pill, price, struck MRP."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x, y = 70, 130
    if discount:
        f = _font(60)
        txt = f"{discount} OFF"
        tw = d.textlength(txt, font=f)
        d.rounded_rectangle((x, y, x + tw + 56, y + 92), radius=46, fill=ACCENT)
        d.text((x + 28, y + 13), txt, font=f, fill=INK)
        x += tw + 90
    if price:
        f = _font(96)
        d.text((x, y - 8), price, font=f, fill=INK, stroke_width=4, stroke_fill=(0, 0, 0))
        if mrp:
            pw = d.textlength(price, font=f)
            fm = _font(46)
            mx, my = x + pw + 24, y + 30
            if mx + d.textlength(mrp, font=fm) < W - 40:
                d.text((mx, my), mrp, font=fm, fill=MUTED, stroke_width=2, stroke_fill=(0, 0, 0))
                d.line((mx, my + 27, mx + d.textlength(mrp, font=fm), my + 27), fill=MUTED, width=5)
    return ov


def _name_band(title: str, store: str) -> Image.Image:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = _font(60)
    lines = _wrap(d, title, f, W - 140, 2)
    y = H - 360
    for ln in lines:
        d.text((70, y), ln, font=f, fill=INK, stroke_width=3, stroke_fill=(0, 0, 0))
        y += 76
    if store:
        d.text((70, y + 12), f"on {store}", font=_font(48), fill=BADGE, stroke_width=2, stroke_fill=(0, 0, 0))
    return ov


def _badge(discount: str) -> Image.Image:
    """Yellow starburst with the discount, slightly tilted."""
    size = 560
    b = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    c, spikes = size / 2, 18
    pts = []
    for i in range(spikes * 2):
        r = (size * 0.48) if i % 2 == 0 else (size * 0.40)
        a = math.pi * i / spikes
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=BADGE, outline=DARK, width=8)
    top = discount or "SALE"
    f1, f2 = _font(170 if len(top) <= 3 else 130), _font(96)
    tw = d.textlength(top, font=f1)
    d.text((c - tw / 2, c - 150), top, font=f1, fill=ACCENT, stroke_width=5, stroke_fill=DARK)
    tw = d.textlength("OFF", font=f2)
    d.text((c - tw / 2, c + 40), "OFF", font=f2, fill=DARK)
    return b.rotate(12, resample=Image.BICUBIC)


def _arrow(d: ImageDraw.ImageDraw, cx: float, top: float, color):
    """Downward arrow: shaft and head."""
    d.rectangle((cx - 22, top, cx + 22, top + 120), fill=color)
    d.polygon([(cx - 85, top + 105), (cx + 85, top + 105), (cx, top + 210)], fill=color)


def _gradient(src: Image.Image) -> Image.Image:
    grad = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        grad.putpixel((0, y), tuple(int(ACCENT[i] * (1 - t) + ACCENT_2[i] * t) for i in range(3)))
    grad = grad.resize((W, H), Image.BILINEAR)
    return Image.blend(_backdrop(src), grad, 0.72)


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
    main_bg = _backdrop(main)
    main_fg = _fit(main, int(W * 0.90), int(H * 0.56))
    cuts = [(_backdrop(c), _fit(c, int(W * 0.94), int(H * 0.60))) for c in _detail_crops(photos)]
    pan_src = _cover(main, int(W * 1.35), H)
    strip, name, badge = _price_strip(price, mrp, discount), _name_band(title, store), _badge(discount)
    end_bg = _gradient(main)
    white = Image.new("RGB", (W, H), (255, 255, 255))

    snap_n, cut_n, pan_n, end_n = (int(s * FPS) for s in (SNAP_SECONDS, CUT_SECONDS, PAN_SECONDS, END_CARD_SECONDS))
    duration = (snap_n + cut_n * len(cuts) + pan_n + end_n) / FPS

    def place(bg, fg, zoom, dx=0, dy=0):
        f = bg.copy()
        fw, fh = int(fg.width * zoom), int(fg.height * zoom)
        f.paste(fg.resize((fw, fh), Image.BILINEAR), ((W - fw) // 2 + dx, int(H * 0.52 - fh / 2) + dy))
        return f

    def flash(f, k, n=4, strength=0.55):
        return Image.blend(f, white, strength * (1 - k / n)) if k < n else f

    def frames():
        # 1. Snap zoom
        for k in range(snap_n):
            zoom = 1.8 - 0.8 * _ease_out(k / 8) + 0.03 * (k / snap_n)
            f = flash(place(main_bg, main_fg, zoom), k, 5, 0.85)
            f.paste(strip, (0, 0), strip)
            if k >= 8:
                f.paste(name, (0, 0), name)
            yield f
        # 2. Jump cuts: punch-in plus a short shake on each cut
        for bg, fg in cuts:
            for k in range(cut_n):
                zoom = 1.18 - 0.18 * _ease_out(k / 6) + 0.04 * (k / cut_n)
                dx, dy = (rng.randint(-14, 14), rng.randint(-14, 14)) if k < 4 else (0, 0)
                f = flash(place(bg, fg, zoom, dx, dy), k, 3, 0.4)
                f.paste(strip, (0, 0), strip)
                yield f
        # 3. Pan across the full-bleed photo while the badge pops in
        for k in range(pan_n):
            x = int((pan_src.width - W) * _ease_in_out(k / pan_n))
            f = pan_src.crop((x, 0, x + W, H))
            s = _overshoot((k - 6) / 12) if k >= 6 else 0
            if s > 0.02:
                bw = int(badge.width * s)
                b = badge.resize((bw, bw), Image.BILINEAR)
                f.paste(b, (W - bw - 40 + (badge.width - bw) // 2 - 0, 220 + (badge.width - bw) // 2), b)
            if k >= 14 and price:
                d = ImageDraw.Draw(f)
                fp = _font(130)
                d.text((70, H - 420), f"Only {price}", font=fp, fill=INK, stroke_width=6, stroke_fill=(0, 0, 0))
            yield f
        # 4. End card: bold CTA with a bouncing downward arrow
        big, sub = _font(150), _font(64)
        line2 = " · ".join(x for x in (price, f"{discount} OFF" if discount else "") if x)
        for k in range(end_n):
            f = end_bg.copy()
            d = ImageDraw.Draw(f)
            s = _overshoot(k / 10)
            for i, txt in enumerate(("LINK", "IN BIO")):
                fnt = _font(max(10, int(150 * s)))
                tw = d.textlength(txt, font=fnt)
                d.text(((W - tw) / 2, H * 0.27 + i * 175 * s), txt, font=fnt, fill=INK,
                       stroke_width=7, stroke_fill=DARK)
            if line2 and k >= 8:
                tw = d.textlength(line2, font=sub)
                d.rounded_rectangle(((W - tw) / 2 - 40, H * 0.50, (W + tw) / 2 + 40, H * 0.50 + 104),
                                    radius=52, fill=INK)
                d.text(((W - tw) / 2, H * 0.50 + 16), line2, font=sub, fill=DARK)
            if k >= 6:
                bounce = 45 * abs(math.sin(k / FPS * math.pi * 2.2))
                _arrow(d, W / 2, H * 0.62 + bounce, INK)
            yield flash(f, k, 4, 0.7)

    audio = sorted(AUDIO_DIR.glob("*upbeat*.ogg")) or sorted(AUDIO_DIR.glob("*.ogg")) if AUDIO_DIR.exists() else []
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
