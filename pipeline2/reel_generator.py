import os
import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pipeline2.config import CACHE_DIR
from pipeline2.deal_card_generator import get_font

def get_ffmpeg_cmd() -> str:
    """Finds ffmpeg from system PATH or bundled imageio_ffmpeg binary."""
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def create_frame(size=(1080, 1920), bg_color=(245, 245, 245)):
    return Image.new("RGB", size, bg_color)

def center_text_with_bg(draw, text, font, y, image_width=1080, text_color=(255,255,255), bg_color=(0,0,0,150), padding=30, border_radius=20):
    try: w = draw.textlength(text, font=font)
    except: w = len(text) * (font.size * 0.5)
    
    x1, y1 = (image_width - w) / 2 - padding, y - padding
    x2, y2 = (image_width + w) / 2 + padding, y + font.size + padding
    draw.rounded_rectangle([x1, y1, x2, y2], radius=border_radius, fill=bg_color)
    draw.text(((image_width - w) / 2, y), text, fill=text_color, font=font)
    return w

def create_blurred_bg(image_path, size=(1080, 1920)):
    from PIL import ImageFilter
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        aspect, target_aspect = w / h, size[0] / size[1]
        if aspect > target_aspect:
            new_h = size[1]
            new_w = int(new_h * aspect)
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - size[0]) // 2
            im = im.crop((left, 0, left + size[0], size[1]))
        else:
            new_w = size[0]
            new_h = int(new_w / aspect)
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - size[1]) // 2
            im = im.crop((0, top, size[0], top + size[1]))
        blurred = im.filter(ImageFilter.GaussianBlur(radius=40))
        tint = Image.new("RGBA", size, (0, 0, 0, 120))
        return Image.alpha_composite(blurred.convert("RGBA"), tint).convert("RGB")

def process_product_image_transparent(image_path):
    from PIL import ImageFilter
    with Image.open(image_path) as im:
        im = im.convert("RGBA")
        w, h = im.size
        new_w, new_h = 900, int((900 / w) * h)
        if new_h > 1000:
            new_h, new_w = 1000, int((1000 / h) * w)
        im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        shadow = Image.new("RGBA", (im.width + 40, im.height + 40), (0,0,0,0))
        shadow.paste((0,0,0,100), (20, 20), mask=im.getchannel("A") if "A" in im.getbands() else None)
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        shadow.paste(im, (0,0), mask=im)
        return shadow

def create_reel(image_path: str, title: str, price: str, mrp: str, discount: str) -> str:
    print(f"[ReelGen] Generating UGC style reel for {title[:30]}...")
    os.makedirs(CACHE_DIR, exist_ok=True)
    frames_dir = CACHE_DIR / f"reel_frames_{os.path.basename(image_path)}"
    os.makedirs(frames_dir, exist_ok=True)

    try:
        bg_frame = create_blurred_bg(image_path)
        prod_im = process_product_image_transparent(image_path)
    except Exception as e:
        print(f"[ReelGen] Failed to process image: {e}")
        return ""

    font_hook, font_title, font_price, font_mrp, font_cta = get_font(75), get_font(60), get_font(120), get_font(70), get_font(85)
    y_offset = (1920 - prod_im.size[1]) // 2 - 50
    base_composite = bg_frame.copy()
    base_composite.paste(prod_im, ((1080 - prod_im.size[0]) // 2, y_offset), mask=prod_im)
    
    frame_files = []
    
    # Frame 1: Hook
    f1 = base_composite.copy()
    center_text_with_bg(ImageDraw.Draw(f1, "RGBA"), "POV: You found the ultimate deal", font_hook, 200, bg_color=(0,0,0,180))
    f1_path = frames_dir / "frame_01.jpg"
    f1.save(f1_path, "JPEG", quality=90)
    frame_files.extend([f1_path] * 2)
    
    # Frame 2: Product & MRP
    f2 = base_composite.copy()
    d2 = ImageDraw.Draw(f2, "RGBA")
    short_title = title[:35] + "..." if len(title) > 35 else title
    center_text_with_bg(d2, short_title, font_title, 200, bg_color=(0,0,0,150))
    mrp_y = 1920 - 450
    center_text_with_bg(d2, f"Normally Rs.{mrp}", font_mrp, mrp_y, bg_color=(50,50,50,200), text_color=(200,200,200))
    d2.line([(200, mrp_y + 40), (880, mrp_y + 40)], fill=(239, 68, 68, 255), width=12)
    f2_path = frames_dir / "frame_02.jpg"
    f2.save(f2_path, "JPEG", quality=90)
    frame_files.extend([f2_path] * 2)
    
    # Frame 3: Price Drop
    f3 = base_composite.copy()
    d3 = ImageDraw.Draw(f3, "RGBA")
    center_text_with_bg(d3, short_title, font_title, 200, bg_color=(0,0,0,150))
    price_y = 1920 - 500
    center_text_with_bg(d3, f"Now Only Rs.{price}", font_price, price_y, bg_color=(22, 163, 74, 230))
    if discount:
        center_text_with_bg(d3, f"{discount}% OFF", font_hook, price_y - 150, bg_color=(234, 179, 8, 255), text_color=(0,0,0))
    f3_path = frames_dir / "frame_03.jpg"
    f3.save(f3_path, "JPEG", quality=90)
    frame_files.extend([f3_path] * 2)
    
    # Frame 4: Link in Bio
    f4 = bg_frame.copy()
    d4 = ImageDraw.Draw(f4, "RGBA")
    center_text_with_bg(d4, "Don't miss out on this!", font_hook, 600, bg_color=(0,0,0,0))
    center_text_with_bg(d4, f"Rs.{price} (Was Rs.{mrp})", font_title, 720, bg_color=(0,0,0,0))
    center_text_with_bg(d4, " TAP LINK IN BIO TO BUY ", font_cta, 900, bg_color=(234, 179, 8, 255), text_color=(0,0,0), padding=40, border_radius=40)
    f4_path = frames_dir / "frame_04.jpg"
    f4.save(f4_path, "JPEG", quality=90)
    frame_files.extend([f4_path] * 3)
    
    list_path = frames_dir / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for path in frame_files:
            f.write(f"file '{path.resolve().as_posix()}'\nduration 1\n")
        if frame_files: f.write(f"file '{frame_files[-1].resolve().as_posix()}'\n")
            
    out_video = (CACHE_DIR / f"reel_{os.path.basename(image_path)}.mp4").resolve()
    audio_path = (CACHE_DIR / f"audio_{os.path.basename(image_path)}.mp3").resolve()
    
    safe_title = title.replace('"', '').replace("'", "")
    clean_discount = discount.replace("%", " percent") if discount else ""
    tts_text = f"Guys, stop scrolling! I just found this {safe_title} for an insane price. It originally goes for {mrp}, but right now you can grab it for just {price} rupees. That's {clean_discount} off! This will sell out fast, so tap the link in my bio to grab yours."
    
    try:
        subprocess.run(["edge-tts", "--text", tts_text, "--write-media", str(audio_path), "--voice", "en-IN-NeerjaNeural", "--rate", "+10%"], check=True, capture_output=True)
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
        if os.path.exists(out_video): return str(out_video)
        return ""
    except Exception as e:
        print(f"[ReelGen] FFmpeg error: {e}")
        return ""
