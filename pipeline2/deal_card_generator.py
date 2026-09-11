"""
deal_card_generator.py — Generates aesthetic minimalist studio pins for Pinterest
and clean square cards for Instagram, matching high-end editorial accounts (like https://pin.it/2Z0pS86U5).
"""
import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pipeline2.config import CACHE_DIR

def get_font(size: int):
    font_paths = [
        "Roboto-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    return ImageFont.load_default()

def create_aesthetic_studio_pin(product_img_path: str, out_path: str, size=(1080, 1440)) -> str:
    """
    Transforms any product image into the warm, minimalist studio aesthetic:
    - Warm neutral beige/sand plaster background
    - Soft natural diagonal sunlight & shadow
    - Product centered with realistic contact drop shadow
    - ZERO spammy text or banners on the image
    """
    try:
        # 1. Warm cream/sand studio background
        bg = Image.new("RGB", size, (232, 222, 208)) # warm sand beige
        
        # Soft diagonal sunlight wash at top-left
        sun_wash = Image.new("RGBA", size, (255, 248, 235, 0))
        d_sun = ImageDraw.Draw(sun_wash)
        d_sun.ellipse([-200, -200, 800, 800], fill=(255, 250, 240, 60))
        sun_wash = sun_wash.filter(ImageFilter.GaussianBlur(120))
        
        # Soft window shadow diagonal across background
        window_shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        d_win = ImageDraw.Draw(window_shadow)
        d_win.polygon([(-100, 100), (400, -100), (1200, 800), (700, 1000)], fill=(0, 0, 0, 25))
        d_win.polygon([(-100, 700), (600, 100), (1400, 1000), (700, 1600)], fill=(0, 0, 0, 20))
        window_shadow = window_shadow.filter(ImageFilter.GaussianBlur(80))
        
        canvas = bg.convert("RGBA")
        canvas = Image.alpha_composite(canvas, sun_wash)
        canvas = Image.alpha_composite(canvas, window_shadow)

        # 2. Place Product cleanly
        with Image.open(product_img_path) as im:
            prod = im.convert("RGBA")
            pw, ph = prod.size
            
            target_w = 900
            target_h = int(ph * (target_w / pw))
            if target_h > 1200:
                target_h = 1200
                target_w = int(pw * (target_h / ph))
                
            prod = prod.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # Soft contact drop shadow beneath product
            shadow = Image.new("RGBA", (target_w + 60, target_h + 60), (0, 0, 0, 0))
            if "A" in prod.getbands():
                shadow.paste((40, 30, 20, 80), (30, 35), mask=prod.getchannel("A"))
            else:
                d_s = ImageDraw.Draw(shadow)
                d_s.ellipse([20, target_h - 20, target_w + 40, target_h + 50], fill=(40, 30, 20, 90))
            shadow = shadow.filter(ImageFilter.GaussianBlur(25))
            
            pos_x = (size[0] - target_w) // 2
            pos_y = (size[1] - target_h) // 2
            
            canvas.paste(shadow, (pos_x - 30, pos_y - 25), mask=shadow)
            canvas.paste(prod, (pos_x, pos_y), mask=prod if "A" in prod.getbands() else None)

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        final = canvas.convert("RGB")
        final.save(out_path, "JPEG", quality=95)
        return out_path
    except Exception as e:
        print(f"  [WARN] Failed to create aesthetic studio pin: {e}")
        return product_img_path

def overlay_pricing_banner(image_path: str, deal_price: str, mrp_val: str, discount_pct: str, name_suffix: str) -> str:
    """Redirects to aesthetic studio pin creation (no ugly discount pills)."""
    base_name = os.path.basename(image_path)
    out_path = str(CACHE_DIR / f"studio_pin_{base_name}")
    return create_aesthetic_studio_pin(image_path, out_path)
