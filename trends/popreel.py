"""
popreel.py - the countdown reel: bold colour, moving type, a reason to watch to the end.

  create_pop_reel(items, out_path, title, subtitle)

About 10 seconds:
  1. Hook (1.3s)   every pick flashes past, "6 HEELS FOR WOMEN under ₹999", "WAIT FOR #1"
  2. Countdown     #6 ... #1 (the cheapest last): each pick is a photo card that slides in on its own
                   bright colour, the trend's name scrolls behind it, a yellow price sticker pops
  3. End card      "Comment LINK" (ManyChat DMs the links)
"""
import os

from PIL import Image, ImageDraw, ImageFilter

from trends.editorial import (FPS, H, INK, SHADE, W, WHITE, YELLOW, _black, _chip, _ease, _encode, _fit, _outro,
                              _rs, _rs_text, _sans)
from trends.pins import _fill
from trends.reel import nice_cap

COLORS = [(255, 94, 98), (124, 92, 255), (0, 176, 155), (255, 138, 0), (236, 64, 122), (30, 136, 229)]
HOOK, BEAT, LAST, OUTRO = 1.3, 1.1, 1.6, 1.8
CARD_W, CARD_H, CARD_Y = 780, 1020, 880   # photo size; the card's centre


def _mix(c, other, k):
    return tuple(int(a * (1 - k) + b * k) for a, b in zip(c, other))


def _marquee(title: str, color: tuple) -> tuple:
    """(strip, period): the title repeated in a lighter shade of the colour, to scroll behind the card."""
    f = _black(150)
    unit = title.upper() + "  ·  "
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    period = int(d.textlength(unit, font=f))
    reps = W // period + 3
    strip = Image.new("RGB", (period * reps, 190), color)
    ImageDraw.Draw(strip).text((0, 0), unit * reps, font=f, fill=_mix(color, WHITE, 0.16))
    return strip, period


def _card(path: str, k: int, tilt: float) -> Image.Image:
    """The photo as a white-framed card with rounded corners and a soft shadow, slightly tilted."""
    pad, b = 70, 16
    photo = _fill(path, CARD_W, CARD_H, k)
    c = Image.new("RGBA", (CARD_W + 2 * (pad + b), CARD_H + 2 * (pad + b)))
    sh = Image.new("RGBA", c.size)
    ImageDraw.Draw(sh).rounded_rectangle((pad + 10, pad + 28, c.width - pad + 10, c.height - pad + 28), radius=56, fill=(0, 0, 0, 110))
    c.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(c).rounded_rectangle((pad, pad, c.width - pad, c.height - pad), radius=56, fill=WHITE + (255,))
    mask = Image.new("L", photo.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, photo.width, photo.height), radius=42, fill=255)
    c.paste(photo, (pad + b, pad + b), mask)
    return c.rotate(tilt, expand=True, resample=Image.BICUBIC)


def _sticker(it: dict, best: bool) -> Image.Image | None:
    """Yellow price sticker: the price, the discount (or BEST DEAL on #1)."""
    if not it.get("price"):
        return None
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    price = _rs(it["price"])
    sub = "BEST DEAL" if best else f"{it['discount']}% OFF" if it.get("discount") else ""
    pw = _rs_text(probe, 0, 0, price, 120, INK)
    w, h = int(max(pw, probe.textlength(sub, font=_sans(44))) + 110), 290 if sub else 210
    s = Image.new("RGBA", (w + 40, h + 40))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((26, 30, w + 26, h + 30), radius=48, fill=(0, 0, 0, 70))
    d.rounded_rectangle((16, 16, w + 16, h + 16), radius=48, fill=YELLOW, outline=INK, width=8)
    _rs_text(d, 16 + w / 2, 30, price, 120, INK, center=True)
    if sub:
        tw = d.textlength(sub, font=_sans(44))
        d.rounded_rectangle((16 + w / 2 - tw / 2 - 26, 196, 16 + w / 2 + tw / 2 + 26, 268), radius=36, fill=INK)
        d.text((16 + w / 2, 232), sub, font=_sans(44), fill=YELLOW, anchor="mm")
    return s.rotate(-7, expand=True, resample=Image.BICUBIC)


def _pop(i: int, start: int) -> float:
    """Scale of a sticker popping in at frame `start`: 0 -> 1.18 -> 1."""
    t = (i - start) / 7
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 1.18 * _ease(t / 0.6) if t < 0.6 else 1.18 - 0.18 * (t - 0.6) / 0.4


def _texts(it: dict, rank: int, n: int, color: tuple) -> Image.Image:
    """Everything that doesn't move in a beat: progress bars, the rank, the name and store."""
    lay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(lay)
    seg = (W - 120 - 12 * (n - 1)) / n
    for j in range(n):  # story-style progress: n - rank + 1 of n shown
        x = 60 + j * (seg + 12)
        d.rounded_rectangle((x, 84, x + seg, 96), radius=6, fill=WHITE + ((255,) if j <= n - rank else (90,)))
    d.text((56, 130), f"#{rank}", font=_black(250), fill=WHITE, stroke_width=10, stroke_fill=_mix(color, SHADE, 0.55))
    label = it["label"] if len(it["label"]) <= 30 else it["label"][:29].rsplit(" ", 1)[0] + "…"
    d.text((70, 1468), label, font=_black(58), fill=WHITE, stroke_width=3, stroke_fill=_mix(color, SHADE, 0.55))
    sub = f"on {it['store']}" + (f"  ·  {it['line']}" if it.get("line") and not it.get("price") else "")
    d.text((72, 1556), sub, font=_sans(40), fill=WHITE)
    return lay


def create_pop_reel(items: list, out_path: str, title: str, subtitle: str = "", music: str = "lofi_upbeat") -> str | None:
    """items: [{img, label, price, mrp, discount, store}] (or {img, label, line, store} without prices),
    cheapest first (up to 6): shown as a countdown ending on the cheapest. subtitle overrides the
    yellow hook line. Returns out_path or None."""
    items = [it for it in items if os.path.exists(it["img"])][:6]
    if len(items) < 3:
        return None
    n = len(items)
    order = list(reversed(items))  # #n first, #1 (the cheapest) last
    prices = [it["price"] for it in items if it.get("price")]
    hook_line = subtitle or (f"under {_rs(nice_cap(max(prices)))}" if prices else items[0].get("line", ""))
    cards = [_card(it["img"], k, (-3, 3)[k % 2]) for k, it in enumerate(order)]
    stickers = [_sticker(it, k == n - 1) for k, it in enumerate(order)]
    strips = [_marquee(title, COLORS[k % len(COLORS)]) for k in range(n)]
    texts = [_texts(it, n - k, n, COLORS[k % len(COLORS)]) for k, it in enumerate(order)]
    outro = _outro([it["img"] for it in items], n)

    hook_lay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(hook_lay)
    _chip(d, W / 2, 150, "TRENDING IN INDIA", (200, 24, 110), WHITE, 32, anchor_center=True)
    lines, size = _fit(d, f"{n} {title}".upper(), 112, W - 110, 3)
    y = 250
    for ln in lines:
        d.text((W / 2, y), ln, font=_black(size), fill=WHITE, anchor="mt", stroke_width=5, stroke_fill=SHADE)
        y += int(size * 1.06)
    if hook_line:
        pl, ps = _fit(d, hook_line, 104, W - 140, 2, 56)
        for ln in pl:
            _rs_text(d, W / 2, y + 16, ln, ps, YELLOW, center=True, stroke=5)
            y += int(ps * 1.2)
    tw = d.textlength("WAIT FOR #1", font=_black(64))
    d.rounded_rectangle((W / 2 - tw / 2 - 44, 1500, W / 2 + tw / 2 + 44, 1622), radius=61, fill=YELLOW)
    d.text((W / 2, 1561), "WAIT FOR #1", font=_black(64), fill=INK, anchor="mm")
    hook_scale = 0.74  # smaller cards in the hook, so the words lead
    hook_cards = [c.resize((int(c.width * hook_scale), int(c.height * hook_scale)), Image.BILINEAR) for c in cards]

    hook_n, beat_n, last_n, out_n = (int(s * FPS) for s in (HOOK, BEAT, LAST, OUTRO))
    duration = (hook_n + beat_n * (n - 1) + last_n + out_n) / FPS

    def beat(k: int, i: int, g: int) -> Image.Image:
        color = COLORS[k % len(COLORS)]
        f = Image.new("RGB", (W, H), color)
        strip, period = strips[k]
        for r in range(9):  # the title scrolling behind, rows alternating direction
            off = (g * 7 + r * 137) % period
            x = -off if r % 2 == 0 else off - period
            f.paste(strip, (x, 60 + r * 205))
        f = f.convert("RGBA")
        side = 1 if k % 2 == 0 else -1
        slide = (1 - _ease(i / 8)) * W * side  # the card slides in, alternating sides
        drift = int((i / FPS) * 14)            # then keeps drifting up a little
        c = cards[k]
        f.alpha_composite(c, (int(W / 2 - c.width / 2 + slide), CARD_Y - c.height // 2 - drift), ) if abs(slide) < W else None
        f.alpha_composite(texts[k])
        s, sc = stickers[k], _pop(i, 7)
        if s is not None and sc > 0:
            ss = s if sc == 1.0 else s.resize((max(1, int(s.width * sc)), max(1, int(s.height * sc))), Image.BILINEAR)
            f.alpha_composite(ss, (int(W - 60 - s.width / 2 - ss.width / 2), int(1290 - ss.height / 2)))
        if i < 2:  # a white flash on the cut
            f = Image.blend(f, Image.new("RGBA", (W, H), WHITE + (255,)), 0.55 - 0.3 * i)
        return f.convert("RGB")

    def frames():
        g = 0
        for i in range(hook_n):  # 1. every pick flashes past (4 frames each) under the words
            k = (i // 4) % n
            f = Image.new("RGBA", (W, H), COLORS[k % len(COLORS)] + (255,))
            c = hook_cards[k]
            f.alpha_composite(c, (W // 2 - c.width // 2, 1070 - c.height // 2))
            f.alpha_composite(hook_lay)
            yield f.convert("RGB")
        for k in range(n):  # 2. the countdown
            for i in range(last_n if k == n - 1 else beat_n):
                g += 1
                yield beat(k, i, g)
        last = beat(n - 1, last_n - 1, g)
        for i in range(out_n):  # 3. the call to comment
            yield outro if i >= 4 else Image.blend(last, outro, (i + 1) / 5)

    return _encode(frames(), duration, out_path, music)
