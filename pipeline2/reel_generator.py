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

def center_text(draw, text, font, y, image_width=1080, fill=(0,0,0)):
    try:
        w = draw.textlength(text, font=font)
    except:
        w = len(text) * (font.size * 0.6)
    draw.text(((image_width - w) / 2, y), text, fill=fill, font=font)
    return w

def process_product_image(image_path):
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        new_h = int((1080 / w) * h)
        if new_h > 1000:
            new_h = 1000
            new_w = int((1000 / h) * w)
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            final_im = Image.new("RGB", (1080, new_h), (255, 255, 255))
            final_im.paste(im, ((1080 - new_w) // 2, 0))
            im = final_im
        else:
            im = im.resize((1080, new_h), Image.Resampling.LANCZOS)
        return im

def create_reel(image_path: str, title: str, price: str, mrp: str, discount: str) -> str:
    print(f"[ReelGen] Generating reel for {title[:30]}...")
    print(f"[ReelGen] Image path: {image_path} | Exists: {os.path.exists(image_path)}")

    # Ensure cache directory exists
    os.makedirs(CACHE_DIR, exist_ok=True)

    try:
        prod_im = process_product_image(image_path)
    except Exception as e:
        print(f"[ReelGen] Failed to process image: {e}")
        return ""

    frames_dir = CACHE_DIR / f"reel_frames_{os.path.basename(image_path)}"
    os.makedirs(frames_dir, exist_ok=True)
    
    font_title = get_font(70)
    font_price = get_font(140)
    font_mrp = get_font(100)
    font_cta = get_font(90)
    
    # Base setup
    base_frame = create_frame()
    y_offset = (1920 - prod_im.size[1]) // 2 - 100
    base_frame.paste(prod_im, (0, max(0, y_offset)))
    
    frame_files = []
    
    # Frame 1: Product image with title
    f1 = base_frame.copy()
    d1 = ImageDraw.Draw(f1)
    short_title = title[:40] + "..." if len(title) > 40 else title
    center_text(d1, short_title, font_title, 150, fill=(30, 41, 59))
    f1_path = frames_dir / "frame_01.jpg"
    f1.save(f1_path, "JPEG", quality=90)
    frame_files.extend([f1_path] * 2) # 2 seconds (assuming 1 fps for slideshow)
    
    # Frame 2: Original MRP with strikethrough
    f2 = f1.copy()
    d2 = ImageDraw.Draw(f2)
    mrp_y = 1920 - 400
    mrp_text = f"MRP: ₹{mrp}"
    w = center_text(d2, mrp_text, font_mrp, mrp_y, fill=(100, 116, 139))
    # Strikethrough
    line_y = mrp_y + 50
    start_x = (1080 - w) / 2
    d2.line([(start_x, line_y), (start_x + w, line_y)], fill=(239, 68, 68), width=10)
    f2_path = frames_dir / "frame_02.jpg"
    f2.save(f2_path, "JPEG", quality=90)
    frame_files.extend([f2_path] * 2)
    
    # Frame 3: Deal price with big discount
    f3 = base_frame.copy()
    d3 = ImageDraw.Draw(f3)
    center_text(d3, short_title, font_title, 150, fill=(30, 41, 59))
    price_y = 1920 - 450
    center_text(d3, f"Now Only ₹{price}!", font_price, price_y, fill=(22, 163, 74))
    
    if discount:
        disc_text = f" {discount}% OFF "
        dw = center_text(d3, disc_text, font_mrp, price_y - 150, fill=(255, 255, 255))
        dx = (1080 - dw) / 2
        dy = price_y - 150
        d3.rounded_rectangle([dx - 20, dy - 10, dx + dw + 20, dy + 120], radius=30, fill=(234, 179, 8))
        center_text(d3, disc_text, font_mrp, dy, fill=(0, 0, 0))
        
    f3_path = frames_dir / "frame_03.jpg"
    f3.save(f3_path, "JPEG", quality=90)
    frame_files.extend([f3_path] * 3)
    
    # Frame 4: 'Link in Bio' CTA
    f4 = f3.copy()
    d4 = ImageDraw.Draw(f4)
    d4.rectangle([0, 1920 - 200, 1080, 1920], fill=(0, 0, 0))
    center_text(d4, "🔗 LINK IN BIO TO SHOP", font_cta, 1920 - 150, fill=(255, 255, 255))
    f4_path = frames_dir / "frame_04.jpg"
    f4.save(f4_path, "JPEG", quality=90)
    # Make the last frame very long so the video doesn't end before the voiceover
    frame_files.extend([f4_path] * 20) # 20 seconds
    
    # Write concat list
    list_path = frames_dir / "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for path in frame_files:
            # use absolute forward slashes for ffmpeg even on windows
            f.write(f"file '{path.resolve().as_posix()}'\n")
            f.write(f"duration 1\n")
        if frame_files:
            f.write(f"file '{frame_files[-1].resolve().as_posix()}'\n")
            
    out_video = (CACHE_DIR / f"reel_{os.path.basename(image_path)}.mp4").resolve()
    audio_path = (CACHE_DIR / f"audio_{os.path.basename(image_path)}.mp3").resolve()
    
    # Generate Voiceover
    # e.g., "Incredible deal on Top Brand! Now only 499 rupees, 60 percent off! Link in bio to shop!"
    safe_title = title.replace('"', '').replace("'", "")
    clean_discount = discount.replace("%", " percent") if discount else ""
    tts_text = f"Incredible deal on {safe_title}! Now only {price} rupees. {clean_discount} off! Check the link in bio to shop before it sells out!"
    
    tts_cmd = [
        "edge-tts",
        "--text", tts_text,
        "--write-media", str(audio_path),
        "--voice", "en-IN-NeerjaNeural"
    ]
    try:
        tts_result = subprocess.run(tts_cmd, check=True, capture_output=True, text=True)
        print(f"[ReelGen] TTS generated: {audio_path}")
        has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
        if not has_audio:
            print("[ReelGen] TTS ran but audio file is empty or missing!")
    except Exception as e:
        print(f"[ReelGen] TTS failed: {e}")
        has_audio = False

    ffmpeg_bin = get_ffmpeg_cmd()
    if has_audio:
        ffmpeg_cmd = [
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-i", str(audio_path),
            "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_video)
        ]
    else:
        ffmpeg_cmd = [
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast",
            str(out_video)
        ]

    try:
        ffmpeg_result = subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        if os.path.exists(out_video) and os.path.getsize(out_video) > 0:
            print(f"[ReelGen] Successfully generated reel: {out_video} ({os.path.getsize(out_video)//1024}KB)")
            return str(out_video)
        else:
            print(f"[ReelGen] FFmpeg ran but output video is empty/missing!")
            return ""
    except subprocess.CalledProcessError as e:
        print(f"[ReelGen] FFmpeg failed (exit {e.returncode}):")
        print(f"[ReelGen] STDERR: {e.stderr[-800:] if e.stderr else 'none'}")
        return ""
    except Exception as e:
        print(f"[ReelGen] FFmpeg error: {e}")
        return ""
