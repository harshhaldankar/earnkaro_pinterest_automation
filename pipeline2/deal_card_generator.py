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
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        try:
            urllib.request.urlretrieve(url, font_path)
        except Exception as e:
            print(f"[WARN] Failed to download font: {e}")
            return ImageFont.load_default()
    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()

def overlay_pricing_banner(image_path: str, deal_price: str, mrp_val: str, discount_pct: str, name_suffix: str) -> str:
    if not deal_price and not mrp_val and not discount_pct:
        return image_path
        
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGBA")
            width, height = im.size
            
            overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Banner height (16% of image height)
            banner_h = int(height * 0.16)
            banner_y = height - banner_h
            
            draw.rectangle([(0, banner_y), (width, height)], fill=(9, 9, 11, 235))
            
            price_size = max(16, int(banner_h * 0.35))
            label_size = max(11, int(banner_h * 0.22))
            
            price_font = get_font(price_size)
            mrp_font = get_font(label_size)
                
            margin = int(width * 0.05)
            center_y = banner_y + int(banner_h / 2)
            
            price_text = f"Rs. {deal_price}" if deal_price else ""
            price_w = draw.textlength(price_text, font=price_font) if hasattr(draw, "textlength") else (len(price_text) * (price_size * 0.6))
            draw.text((margin, center_y - int(price_size / 2)), price_text, fill=(74, 222, 128, 255), font=price_font)
            
            curr_x = margin + price_w + int(width * 0.04)
            if mrp_val:
                mrp_text = f"MRP: {mrp_val}"
                mrp_w = draw.textlength(mrp_text, font=mrp_font) if hasattr(draw, "textlength") else (len(mrp_text) * (label_size * 0.6))
                mrp_y = center_y - int(label_size / 2)
                draw.text((curr_x, mrp_y), mrp_text, fill=(156, 163, 175, 255), font=mrp_font)
                
                line_y = mrp_y + int(label_size / 2) + 1
                draw.line([(curr_x, line_y), (curr_x + mrp_w, line_y)], fill=(248, 113, 113, 255), width=max(2, int(banner_h * 0.03)))
                curr_x += mrp_w + int(width * 0.04)
                
            if discount_pct:
                pill_text = f" {discount_pct}% OFF "
                pill_w = draw.textlength(pill_text, font=price_font) if hasattr(draw, "textlength") else (len(pill_text) * (price_size * 0.6))
                pill_h = int(price_size * 1.3)
                pill_x = width - margin - int(pill_w) - 10
                pill_y = center_y - int(pill_h / 2)
                
                draw.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w + 10, pill_y + pill_h)], radius=int(pill_h / 2), fill=(244, 63, 94, 255))
                draw.text((pill_x + 5, pill_y + int(pill_h * 0.1)), pill_text, fill=(255, 255, 255, 255), font=price_font)
                
            combined = Image.alpha_composite(im, overlay)
            
            base_name = os.path.basename(image_path)
            out_path = CACHE_DIR / f"overlay_{name_suffix}_{base_name}"
            
            combined.convert("RGB").save(out_path, "JPEG", quality=95)
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
            font_path = None
            if not os.path.exists("Roboto-Bold.ttf"):
                import urllib.request
                try:
                    urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/apache/roboto/Roboto%5Bwdth%2Cwght%5D.ttf", "Roboto-Bold.ttf")
                except:
                    pass

            for path in [
                "Roboto-Bold.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf",
                "C:\\Windows\\Fonts\\segoeuib.ttf",
                "C:\\Windows\\Fonts\\verdana.ttf"
            ]:
                try:
                    font = ImageFont.truetype(path, 80)
                    break
                except:
                    continue
            else:
                font = ImageFont.load_default()
            
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
    
    pin_path = overlay_pricing_banner(local_image_path, str(deal.price), str(deal.mrp), str(deal.discount_percent), "pin")
    ig_square_path = generate_ig_square(local_image_path, str(deal.price), str(deal.mrp), str(deal.discount_percent))
    ig_story_path = generate_ig_story(local_image_path, str(deal.price), str(deal.mrp), str(deal.discount_percent))
    
    return {
        "pinterest": pin_path,
        "ig_square": ig_square_path,
        "ig_story": ig_story_path
    }

