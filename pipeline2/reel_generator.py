"""
reel_generator.py — Generates viral UGC-style product video reels for Instagram
following the high-converting format of @ugcvideosai:
- Warm aesthetic presentation
- Hook: "Stop scrolling! Aesthetic find under ₹{price} ✨"
- Product showcase & price reveal
- Viral CTA: "Comment 'LINK' for direct DM! 📩"
- Voiceover via edge-tts (Indian accent)
"""
import os
import re
import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pipeline2.config import CACHE_DIR
from pipeline2.deal_card_generator import get_font, create_aesthetic_studio_pin

def get_ffmpeg_cmd() -> str:
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def center_text_with_bg(draw, text, font, y, image_width=1080, text_color=(255,255,255), bg_color=(20, 20, 25, 200), padding=30, border_radius=25):
    try: w = draw.textlength(text, font=font)
    except: w = len(text) * (font.size * 0.5)
    
    x1 = (image_width - w) / 2 - padding
    y1 = y - padding
    x2 = (image_width + w) / 2 + padding
    y2 = y + font.size + padding
    draw.rounded_rectangle([x1, y1, x2, y2], radius=border_radius, fill=bg_color)
    draw.text(((image_width - w) / 2, y), text, fill=text_color, font=font)
    return w

def create_reel(image_path: str, title: str, price: str, mrp: str, discount: str) -> str:
    print(f"[ReelGen] Generating @ugcvideosai style reel for {title[:35]}...")
    os.makedirs(CACHE_DIR, exist_ok=True)
    frames_dir = CACHE_DIR / f"reel_frames_{os.path.basename(image_path)}"
    os.makedirs(frames_dir, exist_ok=True)

    try:
        # Create base aesthetic 9:16 background
        base_pin_path = frames_dir / "base_pin.jpg"
        create_aesthetic_studio_pin(image_path, str(base_pin_path), size=(1080, 1920))
        base_im = Image.open(base_pin_path).convert("RGB")
    except Exception as e:
        print(f"[ReelGen] Failed to prepare base image: {e}")
        return ""

    font_hook = get_font(65)
    font_sub = get_font(52)
    font_price = get_font(85)
    font_cta = get_font(62)
    
    frame_files = []
    
    # ── Frame 1: Hook ("Stop scrolling! Aesthetic find under ₹...") ──
    f1 = base_im.copy()
    d1 = ImageDraw.Draw(f1, "RGBA")
    center_text_with_bg(d1, "STOP SCROLLING ✨", font_hook, 180, bg_color=(20, 20, 25, 230), text_color=(255, 255, 255))
    hook_sub = f"Aesthetic Must-Have Under ₹{price}!" if price else "Aesthetic Fashion Drop!"
    center_text_with_bg(d1, hook_sub, font_sub, 280, bg_color=(20, 20, 25, 200), text_color=(250, 204, 21))
    f1_path = frames_dir / "frame_01.jpg"
    f1.save(f1_path, "JPEG", quality=92)
    frame_files.extend([f1_path] * 2) # 2 seconds
    
    # ── Frame 2: Product Title & Quality Highlight ──
    f2 = base_im.copy()
    d2 = ImageDraw.Draw(f2, "RGBA")
    short_title = title[:35] + "..." if len(title) > 35 else title
    center_text_with_bg(d2, short_title, font_sub, 180, bg_color=(20, 20, 25, 220), text_color=(255, 255, 255))
    if discount:
        center_text_with_bg(d2, f"🔥 FLAT {discount}% OFF TODAY", font_hook, 270, bg_color=(239, 68, 68, 240), text_color=(255, 255, 255))
    f2_path = frames_dir / "frame_02.jpg"
    f2.save(f2_path, "JPEG", quality=92)
    frame_files.extend([f2_path] * 2) # 2 seconds
    
    # ── Frame 3: Price Drop Reveal ──
    f3 = base_im.copy()
    d3 = ImageDraw.Draw(f3, "RGBA")
    price_text = f"Now Only ₹{price}!" if price else "Price Dropped!"
    center_text_with_bg(d3, price_text, font_price, 180, bg_color=(22, 163, 74, 240), text_color=(255, 255, 255))
    if mrp:
        center_text_with_bg(d3, f"Original Price: ₹{mrp}", font_sub, 300, bg_color=(30, 41, 59, 210), text_color=(203, 213, 225))
    f3_path = frames_dir / "frame_03.jpg"
    f3.save(f3_path, "JPEG", quality=92)
    frame_files.extend([f3_path] * 2) # 2 seconds
    
    # ── Frame 4: Viral Call To Action (Comment "LINK" for DM) ──
    f4 = base_im.copy()
    d4 = ImageDraw.Draw(f4, "RGBA")
    # Soft dark scrim over product for CTA clarity
    overlay = Image.new("RGBA", (1080, 1920), (10, 10, 15, 140))
    f4 = Image.alpha_composite(f4.convert("RGBA"), overlay).convert("RGB")
    d4 = ImageDraw.Draw(f4, "RGBA")
    center_text_with_bg(d4, "WANT THE DIRECT LINK? 🛍️", font_hook, 750, bg_color=(0, 0, 0, 0), text_color=(255, 255, 255))
    center_text_with_bg(d4, " COMMENT \"LINK\" BELOW ", font_cta, 880, bg_color=(234, 179, 8, 255), text_color=(15, 23, 42), padding=35, border_radius=35)
    center_text_with_bg(d4, "I will send it straight to your DM! 📩", font_sub, 1030, bg_color=(0, 0, 0, 0), text_color=(240, 240, 240))
    f4_path = frames_dir / "frame_04.jpg"
    f4.save(f4_path, "JPEG", quality=92)
    frame_files.extend([f4_path] * 3) # 3 seconds
    
    list_path = frames_dir / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for path in frame_files:
            f.write(f"file '{path.resolve().as_posix()}'\nduration 1\n")
        if frame_files: f.write(f"file '{frame_files[-1].resolve().as_posix()}'\n")
            
    out_video = (CACHE_DIR / f"reel_{os.path.basename(image_path)}.mp4").resolve()
    audio_path = (CACHE_DIR / f"audio_{os.path.basename(image_path)}.mp3").resolve()
    
    # Engaging conversational voiceover script (like @ugcvideosai)
    clean_title = re.sub(r'[^\w\s]', '', title[:40]).strip()
    clean_price = price.replace(",", "") if price else ""
    tts_text = f"Stop scrolling! If you are looking for an aesthetic find, I just found this {clean_title} on sale for only {clean_price} rupees! Comment LINK below and I will send the direct link straight to your D M before it sells out!"
    
    try:
        subprocess.run(["edge-tts", "--text", tts_text, "--write-media", str(audio_path), "--voice", "en-IN-NeerjaNeural", "--rate", "+12%"], check=True, capture_output=True)
        has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
    except Exception as e:
        print(f"[ReelGen] TTS failed: {e}")
        has_audio = False

    ffmpeg_bin = get_ffmpeg_cmd()
    cmd = [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path)]
    if has_audio: cmd += ["-i", str(audio_path)]
    cmd += ["-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "fast"]
    if has_audio: cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd.append(str(out_video))

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(out_video):
            print(f"[ReelGen] Successfully created reel: {out_video}")
            return str(out_video)
        return ""
    except Exception as e:
        print(f"[ReelGen] FFmpeg error: {e}")
        return ""
