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
import re
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
    if not it.get("price"):  # a photo from the control room has no price: the line (if any) instead
        if it.get("line"):
            d.text((70, y + 22), it["line"], font=_sans(40), fill=INK)
        return lay
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


# ---------------------------------------------------------------------------------------------
# The hook reel (the default since 12 Nov 2026): what makes reels spread in Indian fashion is a
# reason to stop in the first second, fast cuts and a comment keyword that gets a DM (ManyChat).
#   0.0-1.5s  the cheapest pick full screen, the trend in big bold type, "from ₹419" in yellow
#   1.1s each  the other picks: a punch-in zoom on a hard cut, a big price tag
#   1.8s      "Comment LINK" (ManyChat DMs the links), short so the reel loops
HOOK, CUT, OUTRO, PUNCH = 1.5, 1.1, 1.8, 7
YELLOW = (255, 216, 77)
MAGENTA = (200, 24, 110)
WHITE = (255, 255, 255)
SHADE = (20, 14, 18)


def _black(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / "Poppins-Black.ttf"), size)


def _rs_text(d, x, top, text, size, fill, center=False, stroke=0):
    """Bold type with a real ₹: Poppins has no rupee sign, so ₹ is drawn in Roboto Bold. All parts
    share Poppins' baseline. Returns the width."""
    big, rup = _black(size), _sans(int(size * 0.92))
    parts = [(p, rup if p == "₹" else big) for p in re.split(r"(₹)", text) if p]
    width = sum(d.textlength(p, font=f) for p, f in parts)
    x = x - width / 2 if center else x
    base = top + big.getmetrics()[0]
    for p, f in parts:
        d.text((x, base), p, font=f, fill=fill, anchor="ls", stroke_width=stroke, stroke_fill=SHADE)
        x += d.textlength(p, font=f)
    return width


def _gradient(top: bool, height: int, strength: int) -> Image.Image:
    """A dark fade from the top or bottom edge, so white type reads on any photo."""
    lay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(lay)
    for y in range(height):
        a = int(strength * (1 - y / height) ** 1.6)
        yy = y if top else H - 1 - y
        d.line((0, yy, W, yy), fill=SHADE + (a,))
    return lay


def _fit(d, text, size, max_w, max_lines=3, min_size=60):
    """Biggest bold size (down to min_size) at which text wraps into max_lines."""
    while size > min_size:
        lines = _wrap(d, text, _black(size), max_w)
        if len(lines) <= max_lines:
            return lines, size
        size -= 6
    return _wrap(d, text, _black(min_size), max_w)[:max_lines], min_size


def _chip(d, x, y, text, fill, ink, size=30, anchor_center=False):
    f = _sans(size)
    w = d.textlength(text, font=f) + size * 1.4
    if anchor_center:
        x -= w / 2
    d.rounded_rectangle((x, y, x + w, y + size * 1.9), radius=size, fill=fill)
    d.text((x + w / 2, y + size * 0.95), text, font=f, fill=ink, anchor="mm")
    return w


def _hook_layer(title: str, price_line: str) -> Image.Image:
    lay = _gradient(True, 900, 210)
    d = ImageDraw.Draw(lay)
    _chip(d, W / 2, 200, "TRENDING IN INDIA", MAGENTA, WHITE, 30, anchor_center=True)
    lines, size = _fit(d, title.upper(), 118, W - 120)
    y = 310
    for ln in lines:
        d.text((W / 2, y), ln, font=_black(size), fill=WHITE, anchor="mt", stroke_width=4, stroke_fill=SHADE)
        y += int(size * 1.08)
    if price_line:
        pl, ps = _fit(d, price_line, 96, W - 140, 2, 56)
        for ln in pl:
            _rs_text(d, W / 2, y + 26, ln, ps, YELLOW, center=True, stroke=4)
            y += int(ps * 1.25)
    return lay


def _cut_layer(it: dict, k: int, n: int, title: str) -> Image.Image:
    lay = _gradient(True, 360, 150)
    lay.alpha_composite(_gradient(False, 760, 230))
    d = ImageDraw.Draw(lay)
    d.text((W / 2, 120), title, font=_black(50), fill=WHITE, anchor="mt", stroke_width=2, stroke_fill=SHADE)
    _chip(d, 60, 210, f"{k} / {n}", (255, 255, 255, 230), INK, 26)
    y = H - 520
    label = it["label"] if len(it["label"]) <= 34 else it["label"][:33].rsplit(" ", 1)[0] + "…"
    d.text((70, y), label, font=_sans(46), fill=WHITE, stroke_width=2, stroke_fill=SHADE)
    if it.get("price"):
        price = _rs(it["price"])
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        pw = _rs_text(probe, 0, 0, price, 110, INK)
        d.rounded_rectangle((60, y + 80, 60 + pw + 70, y + 80 + 170), radius=28, fill=WHITE)
        _rs_text(d, 95, y + 80 + 12, price, 110, INK)
        x = 60 + pw + 100
        if it.get("mrp") and it["mrp"] > it["price"]:
            mrp = _rs(it["mrp"])
            d.text((x, y + 120), mrp, font=_sans(46), fill=(235, 225, 230))
            mw = d.textlength(mrp, font=_sans(46))
            d.line((x, y + 150, x + mw, y + 150), fill=(235, 225, 230), width=4)
            if it.get("discount"):
                _chip(d, x, y + 185, f"{it['discount']}% OFF", YELLOW, INK, 30)
    elif it.get("line"):
        _rs_text(d, 70, y + 90, it["line"], 72, YELLOW, stroke=3)
    d.text((70, H - 150), f"on {it['store']}", font=_sans(36), fill=(235, 225, 230))
    return lay


def _outro(photos: list, n: int) -> Image.Image:
    """Brand gradient (magenta -> plum -> indigo, as the control room), the picks as a small fan,
    and the comment keyword."""
    import numpy as np
    g = np.linspace(0, 1, H)[:, None, None]
    stops = [np.array(c, float) for c in ((200, 24, 110), (122, 31, 115), (42, 63, 143))]
    arr = np.where(g < 0.55, stops[0] * (1 - g / 0.55) + stops[1] * (g / 0.55),
                   stops[1] * (1 - (g - 0.55) / 0.45) + stops[2] * ((g - 0.55) / 0.45))
    bg = Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")
    fan = photos[:3]
    for k, p in enumerate(fan):  # up to three picks, fanned out at the bottom (one sits in the middle)
        slot = k if len(fan) == 3 else 1 if len(fan) == 1 else (0, 2)[k]
        card = Image.new("RGBA", (300, 380), WHITE + (255,))
        card.paste(_fill(p, 280, 360, k), (10, 10))
        card = card.rotate((-8, 0, 8)[slot], expand=True, resample=Image.BICUBIC)
        bg.alpha_composite(card, (int(W / 2 - card.width / 2 + (slot - 1) * 290), 1500 - (40 if slot == 1 else 0)))
    d = ImageDraw.Draw(bg)
    d.text((W / 2, 330), "Want the link?" if n == 1 else "Want the links?", font=_black(82), fill=WHITE, anchor="mt")
    d.text((W / 2, 500), "Comment", font=_black(130), fill=WHITE, anchor="mt")
    f = _black(190)
    tw = d.textlength("LINK", font=f)
    d.rounded_rectangle((W / 2 - tw / 2 - 50, 680, W / 2 + tw / 2 + 50, 930), radius=40, fill=YELLOW)
    d.text((W / 2, 805), "LINK", font=f, fill=INK, anchor="mm")
    d.text((W / 2, 1010), "and we'll DM you the link" if n == 1 else f"and we'll DM you all {n}", font=_sans(52), fill=WHITE, anchor="mt")
    d.text((W / 2, 1100), "or tap the link in our bio", font=_sans(40), fill=(240, 225, 238), anchor="mt")
    return bg.convert("RGB")


def create_hook_reel(items: list, out_path: str, title: str, subtitle: str = "", music: str = "lofi_upbeat") -> str | None:
    """items: [{img, label, price, mrp, discount, store}] (or {img, label, line, store} without prices),
    cheapest first (up to 6). subtitle overrides the yellow hook line. Returns out_path or None."""
    items = [it for it in items if os.path.exists(it["img"])][:6]
    if len(items) < 3:
        return None
    n = len(items)
    prices = [it["price"] for it in items if it.get("price")]
    hook_line = subtitle or (f"from just {_rs(min(prices))}" if prices else items[0].get("line", ""))
    Z = 1.12
    shots = [_fill(it["img"], int(W * Z), int(H * Z), k) for k, it in enumerate(items)]
    hook_layer = _hook_layer(title, hook_line)
    cut_layers = [_cut_layer(it, k + 1, n, title) for k, it in enumerate(items)]
    outro = _outro([it["img"] for it in items], n)
    hook_n, cut_n, out_n = (int(s * FPS) for s in (HOOK, CUT, OUTRO))
    duration = (hook_n + cut_n * (n - 1) + out_n) / FPS

    def shot_frame(k: int, i: int, total: int) -> Image.Image:
        """A punch-in (zoomed in, easing out over PUNCH frames), then a slow push."""
        shot = shots[k]
        z = 1.0 + 0.10 * (1 - _ease(i / PUNCH)) + 0.03 * (i / total)  # 1.10 -> 1.0, then up to 1.03
        bw, bh = shot.width / (Z * z), shot.height / (Z * z)
        box = ((shot.width - bw) / 2, (shot.height - bh) / 2, (shot.width + bw) / 2, (shot.height + bh) / 2)
        return shot.resize((W, H), Image.BILINEAR, box=box)

    def frames():
        for i in range(hook_n):  # 1. the hook: the cheapest pick, type pops in over 4 frames
            yield _layer_fade(shot_frame(0, i, hook_n), hook_layer, min(1.0, (i + 1) / 4))
        for k in range(1, n):  # 2. hard cuts with a punch-in
            for i in range(cut_n):
                yield _layer_fade(shot_frame(k, i, cut_n), cut_layers[k], min(1.0, (i + 2) / 4))
        for i in range(out_n):  # 3. the call to comment
            yield outro if i >= 3 else Image.blend(shot_frame(n - 1, cut_n, cut_n), outro, (i + 1) / 4)

    return _encode(frames(), duration, out_path, music)


def _encode(frames, duration: float, out_path: str, music: str) -> str | None:
    track = AUDIO_DIR / f"{music}.ogg"
    cmd = [get_ffmpeg_cmd(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if track.exists():
        cmd += ["-i", str(track), "-filter_complex",
                f"[1:a]atrim=0:{duration:.2f},afade=t=in:st=0:d=0.2,afade=t=out:st={duration - 0.8:.2f}:d=0.8[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{duration:.2f}", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0 or not os.path.exists(out_path):
            print(f"  [REEL] ffmpeg failed: {err[-300:]}")
            return None
    except (BrokenPipeError, OSError) as e:
        print(f"  [REEL] ffmpeg pipe error: {e}")
        return None
    return out_path


def create_editorial_reel(items: list, out_path: str, title: str, subtitle: str = "", music: str = "lofi_chill") -> str | None:
    """items: [{img, label, price, mrp, store}] in the order to show (up to 6). Returns out_path or None."""
    items = [it for it in items if os.path.exists(it["img"])][:6]
    if len(items) < 3:
        return None
    n = len(items)
    subtitle = subtitle or (f"{n} picks under {_rs(nice_cap(max(it['price'] for it in items)))}"
                            if all(it.get("price") for it in items) else f"{n} looks")
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
