"""
reel_generator.py — Generates dynamic, cinematic UGC-style product video reels for Instagram:
- Smooth slow zoom-in & camera drift (dynamic motion, not a static photo)
- Zero clutter / no intrusive text during the product showcase
- Royalty-free, non-copyright lofi/chill background music (no voiceover)
- Clean 'LINK IN BIO ↗' badge at the end
"""
import os
import re
import random
import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pipeline2.config import CACHE_DIR
from pipeline2.deal_card_generator import get_font, create_aesthetic_studio_pin

AUDIO_DIR = Path("assets/audio")

def get_ffmpeg_cmd() -> str:
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def create_reel(image_path: str, title: str, price: str, mrp: str, discount: str, duration_sec: float = 6.0, fps: int = 30) -> str:
    print(f"[DynamicReel] Generating cinematic UGC reel for {title[:35]}...")
    os.makedirs(CACHE_DIR, exist_ok=True)
    frames_dir = CACHE_DIR / f"dyn_frames_{os.path.basename(image_path)}"
    if frames_dir.exists():
        shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir, exist_ok=True)

    try:
        # 1. High-res warm studio canvas
        hi_size = (1440, 2560)
        hi_canvas_path = frames_dir / "hi_canvas.jpg"
        create_aesthetic_studio_pin(image_path, str(hi_canvas_path), size=hi_size)
        
        with Image.open(hi_canvas_path) as im:
            hi_canvas = im.convert("RGB")
    except Exception as e:
        print(f"[DynamicReel] Failed to prepare studio image: {e}")
        return ""

    total_frames = int(duration_sec * fps)
    target_size = (1080, 1920)
    cta_start_frame = total_frames - int(1.5 * fps)
    font_cta = get_font(52)

    for i in range(total_frames):
        t = i / float(total_frames)
        # Smooth ease-in-out zoom from 1.0x to 1.14x
        zoom = 1.0 + (0.14 * (3 * t**2 - 2 * t**3))
        
        # Subtle horizontal & vertical drift
        drift_x = int(25 * (t - 0.5))
        drift_y = int(-35 * t)
        
        crop_w = int(target_size[0] / zoom)
        crop_h = int(target_size[1] / zoom)
        
        cx = (hi_size[0] // 2) + drift_x
        cy = (hi_size[1] // 2) + drift_y
        
        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(hi_size[0], x1 + crop_w)
        y2 = min(hi_size[1], y1 + crop_h)
        
        frame = hi_canvas.crop((x1, y1, x2, y2))
        frame = frame.resize(target_size, Image.Resampling.LANCZOS)
        
        # Subtle "LINK IN BIO ↗" badge during final 1.5s
        if i >= cta_start_frame:
            fade = min(1.0, (i - cta_start_frame) / (0.5 * fps))
            alpha = int(220 * fade)
            
            d_cta = ImageDraw.Draw(frame, "RGBA")
            badge_text = "LINK IN BIO ↗"
            try: tw = d_cta.textlength(badge_text, font=font_cta)
            except: tw = len(badge_text) * 26
            
            bx1 = (1080 - tw) / 2 - 35
            by1 = 1680 - 20
            bx2 = (1080 + tw) / 2 + 35
            by2 = 1680 + font_cta.size + 20
            
            d_cta.rounded_rectangle([bx1, by1, bx2, by2], radius=30, fill=(15, 23, 42, alpha))
            d_cta.text(((1080 - tw) / 2, 1680), badge_text, fill=(255, 255, 255, int(255 * fade)), font=font_cta)
            
        frame_path = frames_dir / f"f_{i:04d}.jpg"
        frame.save(frame_path, "JPEG", quality=90)

    list_path = frames_dir / "list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for i in range(total_frames):
            f.write(f"file 'f_{i:04d}.jpg'\n")

    # Select royalty-free non-copyright music
    tracks = list(AUDIO_DIR.glob("*.ogg")) + list(AUDIO_DIR.glob("*.mp3"))
    chosen_audio = random.choice(tracks) if tracks else None
    
    out_video = (CACHE_DIR / f"reel_{os.path.basename(image_path)}.mp4").resolve()
    ffmpeg_bin = get_ffmpeg_cmd()
    
    cmd = [
        ffmpeg_bin, "-y",
        "-r", str(fps),
        "-f", "concat", "-safe", "0", "-i", str(list_path.resolve())
    ]
    
    if chosen_audio and os.path.exists(chosen_audio):
        audio_start = random.randint(5, 25)
        af_filter = f"afade=t=in:ss=0:d=0.5,afade=t=out:st={duration_sec - 1.0}:d=1.0"
        cmd += [
            "-ss", str(audio_start),
            "-i", str(chosen_audio.resolve()),
            "-af", af_filter,
            "-c:a", "aac", "-b:a", "192k",
            "-shortest"
        ]
        
    cmd += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "22",
        str(out_video)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(out_video):
            print(f"[DynamicReel] Successfully generated reel: {out_video}")
            shutil.rmtree(frames_dir, ignore_errors=True)
            return str(out_video)
        return ""
    except Exception as e:
        print(f"[DynamicReel] FFmpeg error: {e}")
        return ""
