import os
from PIL import Image, ImageDraw, ImageFont
from pipeline2.trend_matcher import ProductDeal
from pipeline2.config import CACHE_DIR

def _get_font(size: int):
    # Try to load standard fonts, fallback to default
    for path in [
        "C:\\Windows\\Fonts\\segoeuib.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\verdana.ttf"
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def _draw_banner(draw, width, height, text_title, text_price, text_mrp, text_discount):
    banner_h = int(height * 0.25)
    banner_y = height - banner_h
    
    # Background gradient or solid
    draw.rectangle([(0, banner_y), (width, height)], fill=(9, 9, 11, 245))
    
    font_title = _get_font(int(height * 0.035))
    font_price = _get_font(int(height * 0.05))
    font_mrp = _get_font(int(height * 0.025))
    
    margin = int(width * 0.05)
    
    # Title (truncate if too long)
    draw.text((margin, banner_y + int(banner_h * 0.1)), text_title[:50], fill=(255, 255, 255, 255), font=font_title)
    
    # Price
    price_y = banner_y + int(banner_h * 0.4)
    price_str = f"Rs. {text_price}"
    draw.text((margin, price_y), price_str, fill=(74, 222, 128, 255), font=font_price)
    
    price_w = draw.textlength(price_str, font=font_price) if hasattr(draw, "textlength") else len(price_str) * int(height * 0.05 * 0.6)
    
    # MRP
    mrp_x = margin + int(price_w) + int(width * 0.05)
    mrp_y = price_y + int(height * 0.025)
    mrp_str = f"MRP: Rs. {text_mrp}"
    draw.text((mrp_x, mrp_y), mrp_str, fill=(156, 163, 175, 255), font=font_mrp)
    
    mrp_w = draw.textlength(mrp_str, font=font_mrp) if hasattr(draw, "textlength") else len(mrp_str) * int(height * 0.025 * 0.6)
    # Strikethrough
    draw.line([(mrp_x, mrp_y + int(height * 0.0125)), (mrp_x + mrp_w, mrp_y + int(height * 0.0125))], fill=(248, 113, 113, 255), width=max(2, int(height * 0.005)))
    
    # Discount Badge
    pill_text = f" {text_discount}% OFF "
    pill_w = draw.textlength(pill_text, font=font_price) if hasattr(draw, "textlength") else len(pill_text) * int(height * 0.05 * 0.6)
    pill_h = int(height * 0.06)
    pill_x = width - margin - int(pill_w) - 20
    pill_y = price_y
    
    draw.rounded_rectangle([(pill_x, pill_y), (pill_x + pill_w + 20, pill_y + pill_h)], radius=int(pill_h / 2), fill=(244, 63, 94, 255))
    draw.text((pill_x + 10, pill_y + int(pill_h * 0.05)), pill_text, fill=(255, 255, 255, 255), font=font_price)
    
    # CTA
    font_cta = _get_font(int(height * 0.025))
    draw.text((margin, banner_y + int(banner_h * 0.8)), "SHOP NOW (Link in Bio/Pin)", fill=(204, 255, 0, 255), font=font_cta)

def _generate_card(deal: ProductDeal, image_path: str, width: int, height: int, name_suffix: str) -> str:
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGBA")
            
            # Resize image to fit canvas while maintaining aspect ratio
            img_ratio = im.width / im.height
            canvas_ratio = width / height
            
            if img_ratio > canvas_ratio:
                # Image is wider
                new_w = width
                new_h = int(width / img_ratio)
            else:
                new_h = int(height * 0.75) # leave room for banner
                new_w = int(new_h * img_ratio)
                
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
            
            # Paste image centered horizontally
            paste_x = (width - new_w) // 2
            paste_y = (int(height * 0.75) - new_h) // 2
            canvas.paste(im, (paste_x, paste_y))
            
            draw = ImageDraw.Draw(canvas)
            _draw_banner(draw, width, height, deal.title, deal.price, deal.mrp, deal.discount_percent)
            
            out_path = CACHE_DIR / f"{deal.retailer.lower()}_{deal.title[:10].replace(' ', '_')}_{name_suffix}.jpg"
            canvas.convert("RGB").save(out_path, "JPEG", quality=90)
            return str(out_path)
    except Exception as e:
        print(f"[CardGen] Failed to generate {name_suffix} card: {e}")
        return image_path

def generate_deal_cards(deal: ProductDeal, local_image_path: str) -> dict:
    """
    Generates optimized deal cards for different platforms.
    Returns a dict with paths to the generated images.
    """
    print(f"[CardGen] Generating cards for: {deal.title}")
    
    return {
        "pinterest": _generate_card(deal, local_image_path, 1000, 1500, "pin"),
        "ig_square": _generate_card(deal, local_image_path, 1080, 1080, "sq"),
        "ig_story": _generate_card(deal, local_image_path, 1080, 1920, "story")
    }
