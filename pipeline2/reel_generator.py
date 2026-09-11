"""
reel_generator.py — Generates dynamic, multi-shot UGC-style product video reels for Instagram:
- Multi-clip authentic UGC rhythm (Hook with handheld sway -> Product macro/interaction -> Aesthetic studio finish)
- Category-matched UGC creator hooks (Beauty, Fashion, Watches, Accessories)
- Smooth dynamic camera motion (handheld drift, breathing zoom, macro push-in)
- Zero clutter / no intrusive text during the product showcase
- Royalty-free, non-copyright lofi/chill background music with smooth fade-in/fade-out
- Clean, frosted 'LINK IN BIO ↗' badge in the final 1.5s
"""
import os
import re
import math
import random
import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pipeline2.config import CACHE_DIR
from pipeline2.deal_card_generator import get_font, create_aesthetic_studio_pin

AUDIO_DIR = Path("assets/audio")
UGC_DIR = Path("assets/ugc")

def get_ffmpeg_cmd() -> str:
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def select_ugc_hooks(title: str):
    """
    Selects creator hook & interaction images matching the deal's category.
    """
    t = title.lower()
    hook_img = None
    demo_img = None
    
    # 1. Beauty & Skincare
    if any(w in t for w in ["skin", "serum", "lotion", "cream", "hair", "dove", "tresemme", "loreal", "face", "shampoo", "glow", "moisturizer", "sunscreen", "lipstick", "makeup"]):
        h_candidate = UGC_DIR / "creator_beauty_hook.jpg"
        d_candidate = UGC_DIR / "creator_texture_demo.jpg"
        if h_candidate.exists():
            hook_img = str(h_candidate)
        if d_candidate.exists():
            demo_img = str(d_candidate)
            
    # 2. Fashion & Apparel
    elif any(w in t for w in ["dress", "shirt", "kurta", "saree", "jeans", "top", "t-shirt", "jacket", "hoodie", "trousers", "wear", "outfit", "kurti"]):
        h_candidate = UGC_DIR / "creator_fashion_hook.jpg"
        if h_candidate.exists():
            hook_img = str(h_candidate)
            
    # 3. Watches, Shoes & Lifestyle Accessories
    elif any(w in t for w in ["watch", "timepiece", "analog", "digital", "shoes", "sneakers", "boots", "wallet", "bag", "handbag", "perfume", "talgo"]):
        h_candidate = UGC_DIR / "creator_watch_hook.jpg"
        if h_candidate.exists():
            hook_img = str(h_candidate)
            
    return hook_img, demo_img

def create_reel(
    image_path: str,
    title: str,
    price: str,
    mrp: str,
    discount: str,
    duration_sec: float = 7.5,
    fps: int = 30
) -> str:
    """
    Renders an authentic, dynamic UGC-style Instagram Reel (9:16 vertical, 1080x1920)
    matching the user-approved creator format:
    - Clip 1 (0 to 2.8s): The Hook (handheld smartphone camera sway & breathing)
    - Clip 2 (2.8 to 5.2s): Product Showcase & Macro Texture (slow push-in zoom)
    - Clip 3 (5.2 to 7.5s): Warm Aesthetic Studio Finish + 'LINK IN BIO ↗' badge
    """
    print(f"[DynamicReel] Generating multi-shot UGC reel for: {title[:40]}...")
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', os.path.basename(image_path))
    frames_dir = CACHE_DIR / f"ugc_frames_{clean_name}"
    if frames_dir.exists():
        shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    target_w, target_h = 1080, 1920
    font_cta = get_font(48)

    # 1. Prepare high-res aesthetic studio canvas for the actual product
    hi_size = (1440, 2560)
    hi_canvas_path = frames_dir / "studio_canvas.jpg"
    try:
        create_aesthetic_studio_pin(image_path, str(hi_canvas_path), size=hi_size)
        with Image.open(hi_canvas_path) as im:
            product_studio_img = im.convert("RGB")
    except Exception as e:
        print(f"[DynamicReel] Studio pin error, falling back to base image: {e}")
        with Image.open(image_path) as im:
            product_studio_img = im.convert("RGB").resize(hi_size, Image.Resampling.LANCZOS)

    # 2. Select category-specific creator hooks if available
    hook_img_path, demo_img_path = select_ugc_hooks(title)
    
    frame_idx = 0
    total_frames = int(duration_sec * fps)
    
    n_hook_frames = int(2.8 * fps)       # 0.0s - 2.8s (84 frames)
    n_demo_frames = int(2.4 * fps)       # 2.8s - 5.2s (72 frames)
    n_hero_frames = total_frames - (n_hook_frames + n_demo_frames) # 5.2s - 7.5s (69 frames)

    # ── CLIP 1: THE HOOK (Handheld smartphone camera motion) ──
    if hook_img_path and os.path.exists(hook_img_path):
        with Image.open(hook_img_path) as im:
            hook_base = im.convert("RGB").resize((1180, 2100), Image.Resampling.LANCZOS)
    else:
        # Fallback to product with dynamic handheld motion
        hook_base = product_studio_img.resize((1580, 2800), Image.Resampling.LANCZOS)

    for i in range(n_hook_frames):
        t = i / float(n_hook_frames)
        # Realistic handheld micro-shake & gentle sway
        drift_x = int(14 * math.sin(t * 7.5) + 5 * math.sin(t * 18.2))
        drift_y = int(10 * math.cos(t * 6.2) + 4 * math.cos(t * 14.7))
        zoom = 1.0 + (0.04 * math.sin(t * math.pi))
        
        cw = int(target_w / zoom)
        ch = int(target_h / zoom)
        cx = (hook_base.width // 2) + drift_x
        cy = (hook_base.height // 2) + drift_y
        
        x1 = max(0, min(hook_base.width - cw, cx - cw // 2))
        y1 = max(0, min(hook_base.height - ch, cy - ch // 2))
        
        f = hook_base.crop((x1, y1, x1 + cw, y1 + ch)).resize((target_w, target_h), Image.Resampling.LANCZOS)
        f.save(frames_dir / f"f_{frame_idx:04d}.jpg", "JPEG", quality=92)
        frame_idx += 1

    # ── CLIP 2: PRODUCT INTERACTION / MACRO TEXTURE ──
    if demo_img_path and os.path.exists(demo_img_path):
        with Image.open(demo_img_path) as im:
            demo_base = im.convert("RGB").resize((1200, 2133), Image.Resampling.LANCZOS)
    else:
        # Dynamic macro zoom into product details
        demo_base = product_studio_img.resize((1500, 2666), Image.Resampling.LANCZOS)

    for i in range(n_demo_frames):
        t = i / float(n_demo_frames)
        # Smooth ease-in-out macro push-in (1.0x to 1.14x)
        zoom = 1.0 + (0.14 * (0.5 - 0.5 * math.cos(t * math.pi)))
        cw = int(target_w / zoom)
        ch = int(target_h / zoom)
        cx = demo_base.width // 2
        cy = (demo_base.height // 2) + int(-30 * t)
        
        x1 = max(0, min(demo_base.width - cw, cx - cw // 2))
        y1 = max(0, min(demo_base.height - ch, cy - ch // 2))
        
        f = demo_base.crop((x1, y1, x1 + cw, y1 + ch)).resize((target_w, target_h), Image.Resampling.LANCZOS)
        f.save(frames_dir / f"f_{frame_idx:04d}.jpg", "JPEG", quality=92)
        frame_idx += 1

    # ── CLIP 3: AESTHETIC STUDIO HERO & LINK IN BIO CTA ──
    hero_base = product_studio_img.resize((1160, 2062), Image.Resampling.LANCZOS)
    cta_start_t = 0.35  # Fades in over the last ~1.5 seconds

    for i in range(n_hero_frames):
        t = i / float(n_hero_frames)
        # Slow cinematic pedestal zoom (1.0x to 1.06x)
        zoom = 1.0 + (0.06 * t)
        cw = int(target_w / zoom)
        ch = int(target_h / zoom)
        cx = hero_base.width // 2
        cy = hero_base.height // 2
        
        x1 = max(0, min(hero_base.width - cw, cx - cw // 2))
        y1 = max(0, min(hero_base.height - ch, cy - ch // 2))
        
        f = hero_base.crop((x1, y1, x1 + cw, y1 + ch)).resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Link in Bio badge fades in smoothly
        if t >= cta_start_t:
            badge_fade = min(1.0, (t - cta_start_t) / 0.35)
            overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            d = ImageDraw.Draw(overlay)
            
            badge_text = "LINK IN BIO ↗"
            try:
                tw = d.textlength(badge_text, font=font_cta)
            except Exception:
                tw = len(badge_text) * 24
                
            box_w = tw + 70
            box_h = 76
            bx1 = (target_w - box_w) / 2
            by1 = 1660
            bx2 = bx1 + box_w
            by2 = by1 + box_h
            
            pill_alpha = int(225 * badge_fade)
            text_alpha = int(255 * badge_fade)
            d.rounded_rectangle([bx1, by1, bx2, by2], radius=38, fill=(24, 24, 27, pill_alpha))
            d.text(((target_w - tw) / 2, by1 + 14), badge_text, fill=(255, 255, 255, text_alpha), font=font_cta)
            
            f_rgba = f.convert("RGBA")
            f = Image.alpha_composite(f_rgba, overlay).convert("RGB")
            
        f.save(frames_dir / f"f_{frame_idx:04d}.jpg", "JPEG", quality=92)
        frame_idx += 1

    # Compile frames list
    list_path = frames_dir / "list.txt"
    with open(list_path, "w", encoding="utf-8") as lst:
        for idx in range(frame_idx):
            lst.write(f"file 'f_{idx:04d}.jpg'\n")

    # Audio track selection
    tracks = list(AUDIO_DIR.glob("*.ogg")) + list(AUDIO_DIR.glob("*.mp3"))
    chosen_audio = random.choice(tracks) if tracks else None
    
    out_video = (CACHE_DIR / f"ugc_reel_{clean_name}.mp4").resolve()
    ffmpeg_bin = get_ffmpeg_cmd()
    
    cmd = [
        ffmpeg_bin, "-y",
        "-r", str(fps),
        "-f", "concat", "-safe", "0", "-i", str(list_path.resolve())
    ]
    
    total_duration = frame_idx / float(fps)
    if chosen_audio and os.path.exists(chosen_audio):
        audio_start = random.randint(3, 20)
        af_filter = f"afade=t=in:ss=0:d=0.4,afade=t=out:st={total_duration - 1.2}:d=1.2"
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
        print(f"[DynamicReel] Compiling {frame_idx} UGC frames ({total_duration:.1f}s)...")
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if os.path.exists(out_video) and os.path.getsize(out_video) > 10000:
            print(f"[DynamicReel] SUCCESS! Generated UGC Reel: {out_video} ({os.path.getsize(out_video)} bytes)")
            shutil.rmtree(frames_dir, ignore_errors=True)
            return str(out_video)
        return ""
    except Exception as e:
        print(f"[DynamicReel] FFmpeg compile error: {e}")
        return ""
