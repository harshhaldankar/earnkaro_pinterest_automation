"""
product_reel.py — 9:16 Instagram reel built around the product itself.

Each product photo fills the frame over a blurred copy of itself, with a slow push-in and
cross-fades between shots. Price, MRP, discount, product name and store sit in fixed bands;
the last 2 seconds show a "Link in bio" end card. Lo-fi track from assets/audio, faded in/out.

Frames are drawn with Pillow and piped to ffmpeg as raw RGB, so the only dependency beyond
Pillow is an ffmpeg binary (system ffmpeg or imageio-ffmpeg).
"""
import os
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline2.reel_generator import get_ffmpeg_cmd

W, H = 1080, 1920
FPS = 30
SHOT_SECONDS = 2.6          # per product photo
FADE_SECONDS = 0.4          # cross-fade between shots
END_CARD_SECONDS = 2.0
MIN_SECONDS = 8.0           # single-photo deals get extra crops of the same photo
AUDIO_DIR = Path("assets/audio")
FONT_PATHS = [
    "pipeline2/fonts/Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]

ACCENT = (255, 72, 66)      # discount pill
INK = (255, 255, 255)
MUTED = (225, 225, 225)


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


def _shots(photos: list) -> list:
    """(image, crop_box) per shot. One photo -> full view plus two tighter crops for motion."""
    shots = [(p, None) for p in photos]
    if len(photos) == 1:
        p = photos[0]
        w, h = p.size
        shots += [(p, (int(w * 0.08), int(h * 0.04), int(w * 0.92), int(h * 0.72))),
                  (p, (int(w * 0.10), int(h * 0.28), int(w * 0.90), int(h * 0.96)))]
    return shots


def _prepare_shot(img: Image.Image, box):
    """Blurred full-bleed background and a foreground photo sized to the photo area."""
    src = img.crop(box) if box else img
    bg = _cover(src, W, H).filter(ImageFilter.GaussianBlur(38))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.35)
    # Photo area sits between the price band (ends ~y=420) and the name band (starts y=H-380)
    max_w, max_h = int(W * 0.88), int(H * 0.49)
    scale = min(max_w / src.width, max_h / src.height)
    fg = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
    return bg, fg


def _overlay(title: str, store: str, price: str, mrp: str, discount: str) -> Image.Image:
    """Static text layer (RGBA): price band on top, product name and store at the bottom."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # Top: discount pill + price + struck MRP
    y = 150
    if discount:
        f = _font(64)
        txt = f"{discount} OFF"
        tw = d.textlength(txt, font=f)
        d.rounded_rectangle((70, y, 70 + tw + 60, y + 96), radius=48, fill=ACCENT)
        d.text((100, y + 14), txt, font=f, fill=INK)
        y += 130
    if price:
        f = _font(110)
        d.text((70, y), price, font=f, fill=INK, stroke_width=2, stroke_fill=(0, 0, 0))
        pw = d.textlength(price, font=f)
        if mrp:
            fm = _font(52)
            mx, my = 70 + pw + 30, y + 46
            d.text((mx, my), mrp, font=fm, fill=MUTED)
            mw = d.textlength(mrp, font=fm)
            d.line((mx, my + 30, mx + mw, my + 30), fill=MUTED, width=5)
    # Bottom: product name (max 2 lines) and store
    f = _font(58)
    lines = _wrap(d, title, f, W - 140, 2)
    by = H - 380
    for ln in lines:
        d.text((70, by), ln, font=f, fill=INK, stroke_width=2, stroke_fill=(0, 0, 0))
        by += 74
    if store:
        d.text((70, by + 14), f"on {store}", font=_font(46), fill=MUTED)
    return ov


def _end_card(bg: Image.Image, price: str, discount: str) -> Image.Image:
    card = bg.copy()
    d = ImageDraw.Draw(card)
    big = _font(96)
    line1 = f"{discount} OFF" if discount else "Deal of the day"
    line2 = f"now {price}" if price else ""
    for i, txt in enumerate((line1, line2)):
        if txt:
            tw = d.textlength(txt, font=big)
            d.text(((W - tw) / 2, H * 0.36 + i * 130), txt, font=big, fill=INK, stroke_width=3, stroke_fill=(0, 0, 0))
    cta = "Link in bio"  # no arrow glyph: Roboto/DejaVu render "↗" as a box
    f = _font(70)
    tw = d.textlength(cta, font=f)
    x0, y0 = (W - tw) / 2 - 60, H * 0.58
    d.rounded_rectangle((x0, y0, x0 + tw + 120, y0 + 130), radius=65, fill=(255, 255, 255))
    d.text((x0 + 60, y0 + 26), cta, font=f, fill=(20, 20, 20))
    return card


def create_product_reel(image_paths: list, out_path: str, title: str, price: str = "",
                        mrp: str = "", discount: str = "", store: str = "") -> str | None:
    """
    Render the reel. price/mrp are display strings ("₹2,159"), discount like "55%".
    Returns out_path, or None if there's no usable image or ffmpeg fails.
    """
    photos = []
    for p in image_paths[:4]:
        try:
            photos.append(Image.open(p).convert("RGB"))
        except Exception:
            continue
    if not photos:
        return None

    shots = [_prepare_shot(img, box) for img, box in _shots(photos)]
    overlay = _overlay(title, store, price, mrp, discount)
    shot_frames = int(SHOT_SECONDS * FPS)
    fade_frames = int(FADE_SECONDS * FPS)
    total_frames = max(int(MIN_SECONDS * FPS) - int(END_CARD_SECONDS * FPS), shot_frames * len(shots))
    per_shot = total_frames // len(shots)
    end_card = _end_card(shots[0][0], price, discount)
    end_frames = int(END_CARD_SECONDS * FPS)
    duration = (per_shot * len(shots) + end_frames) / FPS

    def frame_for(i: int, t: float) -> Image.Image:
        bg, fg = shots[i]
        zoom = 1.0 + 0.05 * t  # slow push-in over the shot
        fw, fh = int(fg.width * zoom), int(fg.height * zoom)
        f = bg.copy()
        f.paste(fg.resize((fw, fh), Image.BILINEAR), ((W - fw) // 2, int(H * 0.515 - fh / 2)))
        return f

    audio = sorted(AUDIO_DIR.glob("*.ogg")) if AUDIO_DIR.exists() else []
    cmd = [get_ffmpeg_cmd(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(random.choice(audio))]
        cmd += ["-filter_complex",
                f"[1:a]atrim=0:{duration:.2f},afade=t=in:st=0:d=0.6,afade=t=out:st={duration - 1.2:.2f}:d=1.2[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{duration:.2f}", out_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(len(shots)):
            for k in range(per_shot):
                frame = frame_for(i, k / per_shot)
                # Cross-fade into the next shot over its last fade_frames
                if i + 1 < len(shots) and k >= per_shot - fade_frames:
                    a = (k - (per_shot - fade_frames)) / float(fade_frames)
                    frame = Image.blend(frame, frame_for(i + 1, 0.0), a)
                frame.paste(overlay, (0, 0), overlay)
                proc.stdin.write(frame.tobytes())
        for k in range(end_frames):
            frame = end_card if k >= fade_frames else Image.blend(frame_for(len(shots) - 1, 1.0), end_card, k / fade_frames)
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
