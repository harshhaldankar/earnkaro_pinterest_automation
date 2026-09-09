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
    from PIL import ImageFilter
    if not deal_price and not mrp_val and not discount_pct:
        return image_path
        
    try:
        def center_text_with_bg(draw, text, font, y, image_width=1080, text_color=(255,255,255), bg_color=(0,0,0,150), padding=30, border_radius=20):
            try: w = draw.textlength(text, font=font)
            except: w = len(text) * (font.size * 0.5)
            x1, y1 = (image_width - w) / 2 - padding, y - padding
            x2, y2 = (image_width + w) / 2 + padding, y + font.size + padding
            draw.rounded_rectangle([x1, y1, x2, y2], radius=border_radius, fill=bg_color)
            draw.text(((image_width - w) / 2, y), text, fill=text_color, font=font)
            return w

        # Create aesthetic blurred background 1080x1920
        size = (1080, 1920)
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            aspect, target_aspect = w / h, size[0] / size[1]
            if aspect > target_aspect:
                new_h = size[1]
                new_w = int(new_h * aspect)
                bg_im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - size[0]) // 2
                bg_im = bg_im.crop((left, 0, left + size[0], size[1]))
            else:
                new_w = size[0]
                new_h = int(new_w / aspect)
                bg_im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                top = (new_h - size[1]) // 2
                bg_im = bg_im.crop((0, top, size[0], top + size[1]))
            blurred = bg_im.filter(ImageFilter.GaussianBlur(radius=40))
            tint = Image.new("RGBA", size, (0, 0, 0, 120))
            bg_frame = Image.alpha_composite(blurred.convert("RGBA"), tint).convert("RGB")
            
        # Process product image
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
            prod_im = shadow
            
        font_hook, font_title, font_price, font_mrp, font_cta = get_font(75), get_font(60), get_font(120), get_font(70), get_font(85)
        y_offset = (1920 - prod_im.size[1]) // 2 - 50
        base_composite = bg_frame.copy()
        base_composite.paste(prod_im, ((1080 - prod_im.size[0]) // 2, y_offset), mask=prod_im)
        
        d3 = ImageDraw.Draw(base_composite, "RGBA")
        
        # Product & MRP
        short_title = name_suffix[:35] + "..." if len(name_suffix) > 35 else name_suffix
        center_text_with_bg(d3, short_title, font_title, 200, bg_color=(0,0,0,150))
        mrp_y = 1920 - 450
        center_text_with_bg(d3, f"Normally Rs.{mrp_val}", font_mrp, mrp_y, bg_color=(50,50,50,200), text_color=(200,200,200))
        d3.line([(200, mrp_y + 40), (880, mrp_y + 40)], fill=(239, 68, 68, 255), width=12)
        
        # Price Drop
        price_y = 1920 - 500
        center_text_with_bg(d3, f"Now Only Rs.{deal_price} 🔥", font_price, price_y, bg_color=(22, 163, 74, 230))
        if discount_pct:
            center_text_with_bg(d3, f"{discount_pct}% OFF", font_hook, price_y - 150, bg_color=(234, 179, 8, 255), text_color=(0,0,0))
            
        import os
        base_name = os.path.basename(image_path)
        out_path = CACHE_DIR / f"overlay_{name_suffix[:15]}_{base_name}"
        
        base_composite.convert("RGB").save(out_path, "JPEG", quality=90)
        return str(out_path)
    except Exception as e:
        print(f"  [WARN] Failed to generate UGC aesthetic card: {e}")
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

