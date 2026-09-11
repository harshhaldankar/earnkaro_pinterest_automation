import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pipeline2.trend_matcher import ProductDeal
from pipeline2.config import CACHE_DIR

def get_font(size: int):
    font_dir = os.path.join(os.path.dirname(__file__), "fonts")
    os.makedirs(font_dir, exist_ok=True)
    font_path = os.path.join(font_dir, "Roboto-Bold.ttf")
    
    if not os.path.exists(font_path):
        print(f"[CardGen] Downloading Roboto-Bold.ttf...")
        url = "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Bold.ttf"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp, open(font_path, "wb") as f:
                f.write(resp.read())
        except Exception as e:
            print(f"[WARN] Failed to download font: {e}")
            fallback_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            print(f"[CardGen] Using system fallback font: {fallback_font}")
            if os.path.exists(fallback_font):
                try:
                    return ImageFont.truetype(fallback_font, size)
                except:
                    pass
            return ImageFont.load_default()
            
    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()


def overlay_pricing_banner(image_path: str, deal_price: str, mrp_val: str, discount_pct: str, name_suffix: str) -> str:
    import os
    import re
    from PIL import Image, ImageDraw, ImageFilter
    from pipeline2.config import CACHE_DIR
    
    if not deal_price and not mrp_val and not discount_pct:
        return image_path
        
    try:
        size = (1080, 1920)
        
        # 1. Background: blurred ambient version of image
        with Image.open(image_path) as im:
            im_rgb = im.convert("RGB")
            w, h = im_rgb.size
            aspect, target_aspect = w / h, size[0] / size[1]
            if aspect > target_aspect:
                new_h = size[1]
                new_w = int(new_h * aspect)
                bg = im_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - size[0]) // 2
                bg = bg.crop((left, 0, left + size[0], size[1]))
            else:
                new_w = size[0]
                new_h = int(new_w / aspect)
                bg = im_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
                top = (new_h - size[1]) // 2
                bg = bg.crop((0, top, size[0], top + size[1]))
                
            blurred = bg.filter(ImageFilter.GaussianBlur(radius=45))
            overlay_dark = Image.new("RGBA", size, (10, 10, 15, 140))
            canvas = Image.alpha_composite(blurred.convert("RGBA"), overlay_dark)

        # 2. Product container card in center
        with Image.open(image_path) as im:
            im_rgba = im.convert("RGBA")
            pw, ph = im_rgba.size
            max_box = 860
            scale = min(max_box / pw, max_box / ph)
            nw, nh = int(pw * scale), int(ph * scale)
            prod = im_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
            
            card_pad = 25
            card_w, card_h = nw + card_pad * 2, nh + card_pad * 2
            card_bg = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 250))
            card_bg.paste(prod, (card_pad, card_pad), mask=prod if "A" in prod.getbands() else None)
            
            shadow_w, shadow_h = card_w + 40, card_h + 40
            shadow = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
            draw_s = ImageDraw.Draw(shadow)
            draw_s.rounded_rectangle([15, 15, shadow_w - 15, shadow_h - 15], radius=35, fill=(0, 0, 0, 120))
            shadow = shadow.filter(ImageFilter.GaussianBlur(18))
            
            cx = (1080 - card_w) // 2
            cy = 340 + (860 - card_h) // 2
            canvas.paste(shadow, (cx - 20, cy - 20), mask=shadow)
            canvas.paste(card_bg, (cx, cy), mask=card_bg)

        draw = ImageDraw.Draw(canvas, "RGBA")

        def draw_pill(text, font, y_center, text_color, bg_color, pad_x=45, pad_y=22, radius=30):
            try: tw = draw.textlength(text, font=font)
            except: tw = len(text) * (font.size * 0.5)
            th = font.size
            x1 = (1080 - tw) / 2 - pad_x
            y1 = y_center - th / 2 - pad_y
            x2 = (1080 + tw) / 2 + pad_x
            y2 = y_center + th / 2 + pad_y
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=bg_color)
            draw.text(((1080 - tw) / 2, y_center - th / 2), text, fill=text_color, font=font)
            return x1, y1, x2, y2

        font_title = get_font(56)
        font_disc = get_font(65)
        font_price = get_font(95)
        font_mrp = get_font(50)
        font_cta = get_font(48)

        clean_title = re.sub(r'^[^\w]+', '', name_suffix).strip()
        if len(clean_title) > 32:
            clean_title = clean_title[:30] + "..."
        draw_pill(clean_title, font_title, 180, (255, 255, 255, 255), (15, 23, 42, 220), pad_x=40, pad_y=20, radius=35)

        if discount_pct:
            draw_pill(f"LIMITED DEAL • {discount_pct}% OFF", font_disc, 1360, (15, 23, 42, 255), (250, 204, 21, 255), pad_x=40, pad_y=18, radius=30)

        if deal_price:
            draw_pill(f"Now Just ₹{deal_price}", font_price, 1500, (255, 255, 255, 255), (22, 163, 74, 245), pad_x=55, pad_y=22, radius=35)

        if mrp_val:
            mrp_text = f"Original Price: ₹{mrp_val}"
            x1, y1, x2, y2 = draw_pill(mrp_text, font_mrp, 1630, (203, 213, 225, 255), (30, 41, 59, 200), pad_x=30, pad_y=15, radius=25)
            draw.line([x1 + 25, 1630, x2 - 25, 1630], fill=(239, 68, 68, 255), width=6)

        draw_pill("TAP TO SHOP THIS DEAL ->", font_cta, 1770, (255, 255, 255, 230), (0, 0, 0, 160), pad_x=35, pad_y=16, radius=25)

        base_name = os.path.basename(image_path)
        out_path = CACHE_DIR / f"ugc_card_{base_name}"
        canvas.convert("RGB").save(out_path, "JPEG", quality=95)
        return str(out_path)
    except Exception as e:
        print(f"  [WARN] Failed to overlay pricing banner: {e}")
        return image_path


def generate_ig_square(image_path: str, deal_price: str, mrp_val: str, discount_pct: str) -> str:
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            # 1080x1080
            bg = Image.new("RGB", (1080, 1080), (255, 255, 255))
            
            # center crop and resize
            im = ImageOps.fit(im, (1080, 1080), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            bg.paste(im, (0, 0))
            
            base_name = os.path.basename(image_path)
            temp_path = CACHE_DIR / f"temp_sq_{base_name}"
            bg.save(temp_path, "JPEG", quality=95)
            
            return overlay_pricing_banner(str(temp_path), deal_price, mrp_val, discount_pct, "ig_square")
    except Exception as e:
        print(f"  [WARN] Failed to generate ig square: {e}")
        return image_path

def generate_ig_story(image_path: str, deal_price: str, mrp_val: str, discount_pct: str) -> str:
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            # 1080x1920
            bg = Image.new("RGB", (1080, 1920), (245, 245, 245))
            
            # Resize image to fit width, maintaining aspect ratio
            w, h = im.size
            new_h = int((1080 / w) * h)
            im = im.resize((1080, new_h), Image.Resampling.LANCZOS)
            
            # Paste in center
            y_offset = (1920 - new_h) // 2
            bg.paste(im, (0, y_offset))
            
            draw = ImageDraw.Draw(bg)
            
            # Big deal price
            price_font = get_font(120)
            price_text = f"₹{deal_price}"
            try:
                price_w = draw.textlength(price_text, font=price_font)
            except:
                price_w = len(price_text) * 70
            
            draw.text(((1080 - price_w) // 2, 100), price_text, fill=(220, 38, 38), font=price_font)
            font = get_font(80)
            
            if discount_pct:
                disc_font = font
                disc_text = f"{discount_pct}% OFF!"
                try:
                    disc_w = draw.textlength(disc_text, font=disc_font)
                except:
                    disc_w = len(disc_text) * 45
                
                # Draw pill
                px = (1080 - disc_w - 60) // 2
                py = 250
                draw.rounded_rectangle([px, py, px + disc_w + 60, py + 120], radius=40, fill=(234, 179, 8))
                draw.text((px + 30, py + 15), disc_text, fill=(0, 0, 0), font=disc_font)
                
            # Swipe up CTA
            cta_font = get_font(70)
            cta_text = "SWIPE UP FOR DEAL ⬆️"
            try:
                cta_w = draw.textlength(cta_text, font=cta_font)
            except:
                cta_w = len(cta_text) * 40
                
            draw.rectangle([0, 1920 - 150, 1080, 1920], fill=(0, 0, 0))
            draw.text(((1080 - cta_w) // 2, 1920 - 120), cta_text, fill=(255, 255, 255), font=cta_font)
            
            base_name = os.path.basename(image_path)
            out_path = CACHE_DIR / f"story_{base_name}"
            bg.save(out_path, "JPEG", quality=95)
            
            return str(out_path)
    except Exception as e:
        print(f"  [WARN] Failed to generate ig story: {e}")
        return image_path

def generate_deal_cards(deal: ProductDeal, local_image_path: str) -> dict:
    print(f"[CardGen] Generating optimized cards for: {deal.title}")
    
    # Use clean, pristine product photo for Pinterest (avoids ugly black banner/bars that cut off products)
    pin_path = local_image_path
    ig_square_path = generate_ig_square(local_image_path, str(deal.price), str(deal.mrp), str(deal.discount_percent))
    ig_story_path = generate_ig_story(local_image_path, str(deal.price), str(deal.mrp), str(deal.discount_percent))
    
    return {
        "pinterest": pin_path,
        "ig_square": ig_square_path,
        "ig_story": ig_story_path
    }

