"""
editorial.py - the premium reel: a calm, magazine-style "edit" of a trend, made from product photos.

  create_editorial_reel(items, out_path, title, subtitle)

Same look as the pins: cream and pastel, Playfair serif, the photo does the work. No stickers,
no "% OFF" stamps. About 16 seconds:
  1. Title card   "TRENDING IN INDIA", the trend in serif, "6 picks under ₹1,000"
  2. One product per beat: full-frame photo (packshots on a pastel studio) with a slow push-in,
     soft cross-fades, and a cream caption band with the name, price and store
  3. End card     "Shop the edit", four photos, "Comment LINK · or tap the link in our bio"
"""
import math
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from trends.pins import _fill, _pastel
from trends.reel import AUDIO_DIR, FONT_DIR, get_ffmpeg_cmd, nice_cap

W, H, FPS = 1080, 1920, 30
INTRO, BEAT, FADE, END = 2.4, 2.0, 0.4, 2.8
CREAM = (250, 245, 240)
INK = (40, 32, 38)
MUTED = (118, 102, 110)
BAND = 400


def _serif(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / "PlayfairDisplay.ttf"), size)  # the variable font's Regular


def _sans(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / "Roboto-Bold.ttf"), size)


def _rs(v: float) -> str:
    return "₹{:,}".format(int(round(v)))


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _spaced(d, cx, y, text, font, fill, spacing=10):
    """Letter-spaced small caps, centred on cx."""
    widths = [d.textlength(c, font=font) for c in text]
    x = cx - (sum(widths) + spacing * (len(text) - 1)) / 2
    for c, w in zip(text, widths):
        d.text((x, y), c, font=font, fill=fill)
        x += w + spacing


def _wrap(d, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def _layer_fade(base: Image.Image, layer: Image.Image, a: float) -> Image.Image:
    """Composite an RGBA text layer at opacity a."""
    if a <= 0:
        return base
    if a < 1:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    out = base.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def _title_layer(title: str, subtitle: str) -> Image.Image:
    lay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(lay)
    _spaced(d, W / 2, 640, "TRENDING IN INDIA", _sans(30), MUTED, 9)
    d.line((W / 2 - 70, 712, W / 2 + 70, 712), fill=MUTED, width=2)
    f = _serif(118)
    lines = _wrap(d, title, f, W - 160)[:3]
    y = 770
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill=INK, anchor="mt")
        y += 140
    d.text((W / 2, y + 30), subtitle, font=_serif(54), fill=MUTED, anchor="mt")
    _spaced(d, W / 2, H - 150, "GET YOUR DEAL", _sans(24), MUTED, 8)
    return lay


def _caption_layer(it: dict, i: int, n: int) -> Image.Image:
    lay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(lay)
    for y in range(110):  # soft edge into the band
        d.line((0, H - BAND - 110 + y, W, H - BAND - 110 + y), fill=CREAM + (int(255 * (y / 110) ** 1.5),))
    d.rectangle((0, H - BAND, W, H), fill=CREAM + (255,))
    d.text((70, H - BAND + 30), f"{i:02d} / {n:02d}", font=_sans(28), fill=MUTED)
    d.text((W - 70, H - BAND + 30), it["store"].upper(), font=_sans(28), fill=MUTED, anchor="ra")
    f = _serif(72)
    lines = _wrap(d, it["label"], f, W - 140)[:2]
    y = H - BAND + 96
    for ln in lines:
        d.text((70, y), ln, font=f, fill=INK)
        y += 92
    price = _rs(it["price"])
    d.text((70, y + 22), price, font=_sans(46), fill=INK)
    if it.get("mrp") and it["mrp"] > it["price"]:
        x = 70 + d.textlength(price, font=_sans(46)) + 24
        mrp = _rs(it["mrp"])
        d.text((x, y + 30), mrp, font=_sans(34), fill=MUTED)
        mw = d.textlength(mrp, font=_sans(34))
        d.line((x, y + 52, x + mw, y + 52), fill=MUTED, width=3)
    return lay


def _end_frame(photos: list, n: int) -> tuple:
    """(background with the photo grid, text layer)."""
    bg = _pastel(W, H, 1)
    canvas = bg.convert("RGBA")
    cw, ch, gap = 420, 525, 28
    x0, y0 = (W - 2 * cw - gap) // 2, 470
    shadow = Image.new("RGBA", (W, H))
    sd = ImageDraw.Draw(shadow)
    for k in range(min(4, len(photos))):
        x, y = x0 + (k % 2) * (cw + gap), y0 + (k // 2) * (ch + gap)
        sd.rectangle((x + 6, y + 14, x + cw + 6, y + ch + 14), fill=(80, 50, 70, 60))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    for k, p in enumerate(photos[:4]):
        x, y = x0 + (k % 2) * (cw + gap), y0 + (k // 2) * (ch + gap)
        canvas.paste((255, 255, 255, 255), (x - 8, y - 8, x + cw + 8, y + ch + 8))
        canvas.paste(_fill(p, cw, ch, k), (x, y))
    lay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(lay)
    _spaced(d, W / 2, 230, f"ALL {n} PICKS", _sans(30), MUTED, 9)
    d.text((W / 2, 290), "Shop the edit", font=_serif(104), fill=INK, anchor="mt")
    d.text((W / 2, 1620), "Comment LINK", font=_serif(76), fill=INK, anchor="mt")
    d.text((W / 2, 1730), "or tap the link in our bio", font=_sans(36), fill=MUTED, anchor="mt")
    return canvas.convert("RGB"), lay


def create_editorial_reel(items: list, out_path: str, title: str, subtitle: str = "", music: str = "lofi_chill") -> str | None:
    """items: [{img, label, price, mrp, store}] in the order to show (up to 6). Returns out_path or None."""
    items = [it for it in items if os.path.exists(it["img"])][:6]
    if len(items) < 3:
        return None
    n = len(items)
    subtitle = subtitle or f"{n} picks under {_rs(nice_cap(max(it['price'] for it in items)))}"
    shots = [_fill(it["img"], int(W * 1.08), int((H - BAND + 80) * 1.08), k) for k, it in enumerate(items)]
    captions = [_caption_layer(it, k + 1, n) for k, it in enumerate(items)]
    title_layer = _title_layer(title, subtitle)
    intro_bg = _pastel(W, H, 0)
    end_bg, end_layer = _end_frame([it["img"] for it in items], n)
    intro_n, beat_n, fade_n, end_n = (int(s * FPS) for s in (INTRO, BEAT, FADE, END))
    duration = (intro_n + beat_n * n + end_n) / FPS

    def beat_frame(k: int, t: float) -> Image.Image:
        """Product k at time t (0..1 of its beat): slow push-in on the photo, cream band below."""
        shot = shots[k]
        z = 1.0 + 0.06 * t
        bw, bh = shot.width / (1.08 * z), shot.height / (1.08 * z)
        box = ((shot.width - bw) / 2, (shot.height - bh) / 2 * 0.6, (shot.width + bw) / 2, (shot.height - bh) / 2 * 0.6 + bh)
        f = Image.new("RGB", (W, H), CREAM)
        f.paste(shot.resize((W, H - BAND + 80), Image.BILINEAR, box=box), (0, 0))
        return _layer_fade(f, captions[k], 1.0)

    def frames():
        last = None
        for i in range(intro_n):  # 1. title card fades up
            f = _layer_fade(intro_bg, title_layer, _ease(i / 18))
            last = f
            yield f
        for k in range(n):  # 2. products, cross-fading from whatever came before
            for i in range(beat_n):
                f = beat_frame(k, i / beat_n)
                if i < fade_n:
                    f = Image.blend(last, f, _ease(i / fade_n))
                yield f
            last = f
        for i in range(end_n):  # 3. end card
            f = _layer_fade(end_bg, end_layer, _ease((i - 6) / 14))
            if i < fade_n:
                f = Image.blend(last, f, _ease(i / fade_n))
            yield f

    track = AUDIO_DIR / f"{music}.ogg"
    cmd = [get_ffmpeg_cmd(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if track.exists():
        cmd += ["-i", str(track), "-filter_complex",
                f"[1:a]atrim=0:{duration:.2f},afade=t=in:st=0:d=0.6,afade=t=out:st={duration - 1.5:.2f}:d=1.5[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{duration:.2f}", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames():
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0 or not os.path.exists(out_path):
            print(f"  [EDIT] ffmpeg failed: {err[-300:]}")
            return None
    except (BrokenPipeError, OSError) as e:
        print(f"  [EDIT] ffmpeg pipe error: {e}")
        return None
    return out_path
