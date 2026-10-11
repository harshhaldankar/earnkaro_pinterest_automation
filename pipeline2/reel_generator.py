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

def build_reel_info_overlay(title: str, price: str, mrp: str, discount: str, target_size=(1080, 1920)) -> Image.Image:
    """Pre-renders an elegant, editorial frosted deal card for the top of the video reel."""
    w, h = target_size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    
    clean_title = re.sub(r'[^\w\s%&\'\-]', '', title).strip()
    clean_title = re.sub(r'^(LOOT|DEAL|OFFER|HOT DEAL|MYNTRA LOOT|AJIO LOOT)\s*[:\-\s]*', '', clean_title, flags=re.IGNORECASE).strip()
    
    disc_text = ""
    if discount and str(discount).strip():
        d_val = str(discount).strip()
        disc_text = f"{d_val}% OFF" if "%" not in d_val else d_val
    else:
        m = re.search(r'((?:UPTO|FLAT|MIN)?\s*\d{1,2}%\s*(?:OFF)?)', title, re.IGNORECASE)
        if m:
            disc_text = m.group(1).strip().upper()
            
    price_text = ""
    if price and str(price).strip():
        p_clean = str(price).replace("₹", "").strip()
        price_text = f"₹{p_clean}"
        if mrp and str(mrp).strip() and str(mrp) != str(price):
            m_clean = str(mrp).replace("₹", "").strip()
            price_text += f"  (MRP: ₹{m_clean})"
            
    if disc_text and price_text:
        highlight_text = f"{disc_text}  •  {price_text}"
    elif disc_text:
        highlight_text = disc_text
    elif price_text:
        highlight_text = f"DEAL: {price_text}"
    else:
        highlight_text = "VERIFIED SPECIAL DROP"

    if len(clean_title) > 38:
        clean_title = clean_title[:36].strip() + "..."
        
    top_y = 120
    card_w = 980
    card_h = 190
    card_x = (w - card_w) // 2
    
    # Frosted dark container with smooth rounded corners
    d.rounded_rectangle([card_x, top_y, card_x + card_w, top_y + card_h], radius=34, fill=(15, 20, 28, 230))
    
    # "VERIFIED DEAL" pill badge
    font_badge = get_font(22)
    tag_text = "VERIFIED DEAL"
    tag_w = int(d.textlength(tag_text, font=font_badge)) + 30
    tag_h = 38
    d.rounded_rectangle([card_x + 36, top_y + 22, card_x + 36 + tag_w, top_y + 22 + tag_h], radius=19, fill=(225, 29, 72, 255))
    d.text((card_x + 51, top_y + 29), tag_text, font=font_badge, fill=(255, 255, 255, 255))
    
    # Deal Title (clean, bold, highly legible)
    font_title = get_font(40)
    d.text((card_x + 36, top_y + 74), clean_title.upper(), font=font_title, fill=(255, 255, 255, 255))
    
    # Highlight / Offer Text (Emerald green)
    font_high = get_font(34)
    d.text((card_x + 36, top_y + 130), highlight_text, font=font_high, fill=(52, 211, 153, 255))
    
    return overlay

def create_reel(
    image_path: str,
    title: str,
    price: str = "",
    mrp: str = "",
    discount: str = "",
    duration_sec: float = 7.0,
    fps: int = 30
) -> str:
    """
    Renders an authentic, dynamic UGC-style Instagram Reel (9:16 vertical, 1080x1920)
    focused on the ACTUAL PRODUCT with editorial deal info overlays:
    - Top Frosted Deal Card: Verified tag, clear product title, discount % / price highlight
    - Clip 1 (0 to 2.5s): Smooth handheld breathing & slow push-in zoom on the real product
    - Clip 2 (2.5 to 5.0s): Macro focus & horizontal pan exploring product details
    - Clip 3 (5.0 to 7.0s): Hero studio presentation with animated 'TAP LINK IN BIO ↗' badge
    - Non-copyright royalty-free upbeat/lofi background music
    """
    safe_title = title[:40].encode("ascii", "replace").decode("ascii")
    print(f"[DynamicReel] Generating product reel with deal info for: {safe_title}...")
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
        create_aesthetic_studio_pin(image_path, str(hi_canvas_path), size=hi_size, title=title)
        with Image.open(hi_canvas_path) as im:
            product_studio_img = im.convert("RGB")
    except Exception as e:
        print(f"[DynamicReel] Studio pin error, falling back to base image: {e}")
        with Image.open(image_path) as im:
            product_studio_img = im.convert("RGB").resize(hi_size, Image.Resampling.LANCZOS)

    # 2. Build pre-rendered deal info overlay
    overlay_info = build_reel_info_overlay(title, price, mrp, discount, (target_w, target_h))

    frame_idx = 0
    total_frames = int(duration_sec * fps)
    
    n_clip1_frames = int(2.5 * fps)
    n_clip2_frames = int(2.5 * fps)
    n_clip3_frames = total_frames - (n_clip1_frames + n_clip2_frames)

    # ── CLIP 1: PRODUCT HERO INTRO (Slow push-in & handheld sway) ──
    base1 = product_studio_img.resize((1500, 2666), Image.Resampling.LANCZOS)
    for i in range(n_clip1_frames):
        t = i / float(n_clip1_frames)
        drift_x = int(12 * math.sin(t * 6.0))
        drift_y = int(8 * math.cos(t * 5.0))
        zoom = 1.0 + (0.05 * (3 * t**2 - 2 * t**3))
        
        cw = int(target_w / zoom)
        ch = int(target_h / zoom)
        cx = (base1.width // 2) + drift_x
        cy = (base1.height // 2) + drift_y
        
        x1 = max(0, min(base1.width - cw, cx - cw // 2))
        y1 = max(0, min(base1.height - ch, cy - ch // 2))
        
        f = base1.crop((x1, y1, x1 + cw, y1 + ch)).resize((target_w, target_h), Image.Resampling.LANCZOS)
        f = Image.alpha_composite(f.convert("RGBA"), overlay_info).convert("RGB")
        f.save(frames_dir / f"f_{frame_idx:04d}.jpg", "JPEG", quality=90)
        frame_idx += 1

    # ── CLIP 2: MACRO DETAIL EXPLORATION (Subtle pan & push) ──
    base2 = product_studio_img.resize((1580, 2808), Image.Resampling.LANCZOS)
    for i in range(n_clip2_frames):
        t = i / float(n_clip2_frames)
        zoom = 1.06 + (0.08 * math.sin(t * math.pi))
        pan_x = int(28 * (t - 0.5))
        
        cw = int(target_w / zoom)
        ch = int(target_h / zoom)
        cx = (base2.width // 2) + pan_x
        cy = (base2.height // 2)
        
        x1 = max(0, min(base2.width - cw, cx - cw // 2))
        y1 = max(0, min(base2.height - ch, cy - ch // 2))
        
        f = base2.crop((x1, y1, x1 + cw, y1 + ch)).resize((target_w, target_h), Image.Resampling.LANCZOS)
        f = Image.alpha_composite(f.convert("RGBA"), overlay_info).convert("RGB")
        f.save(frames_dir / f"f_{frame_idx:04d}.jpg", "JPEG", quality=90)
        frame_idx += 1

    # ── CLIP 3: HERO REVEAL & CALL TO ACTION BADGE ──
    base3 = product_studio_img.resize((1440, 2560), Image.Resampling.LANCZOS)
    cta_start_t = 0.25  # Fades in over the final ~1.5s
    for i in range(n_clip3_frames):
        t = i / float(n_clip3_frames)
        zoom = 1.0 + (0.04 * t)
        
        cw = int(target_w / zoom)
        ch = int(target_h / zoom)
        cx = base3.width // 2
        cy = base3.height // 2
        
        x1 = max(0, min(base3.width - cw, cx - cw // 2))
        y1 = max(0, min(base3.height - ch, cy - ch // 2))
        
        f = base3.crop((x1, y1, x1 + cw, y1 + ch)).resize((target_w, target_h), Image.Resampling.LANCZOS)
        f_rgba = Image.alpha_composite(f.convert("RGBA"), overlay_info)
        
        # Link in Bio CTA badge fades in smoothly at the bottom
        if t >= cta_start_t:
            badge_fade = min(1.0, (t - cta_start_t) / 0.35)
            cta_overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            d_cta = ImageDraw.Draw(cta_overlay)
            
            badge_text = "TAP LINK IN BIO ↗"
            try:
                tw = d_cta.textlength(badge_text, font=font_cta)
            except Exception:
                tw = len(badge_text) * 24
                
            box_w = tw + 70
            box_h = 76
            bx1 = (target_w - box_w) / 2
            by1 = 1660
            bx2 = bx1 + box_w
            by2 = by1 + box_h
            
            pill_alpha = int(235 * badge_fade)
            text_alpha = int(255 * badge_fade)
            d_cta.rounded_rectangle([bx1, by1, bx2, by2], radius=38, fill=(15, 20, 28, pill_alpha))
            d_cta.text(((target_w - tw) / 2, by1 + 14), badge_text, fill=(255, 255, 255, text_alpha), font=font_cta)
            f_rgba = Image.alpha_composite(f_rgba, cta_overlay)
            
        f = f_rgba.convert("RGB")
        f.save(frames_dir / f"f_{frame_idx:04d}.jpg", "JPEG", quality=90)
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
