import os
from PIL import Image, ImageDraw, ImageFont
from pipeline2.trend_matcher import ProductDeal
from pipeline2.config import CACHE_DIR

def overlay_pricing_banner(image_path: str, deal_price: str, mrp_val: str, discount_pct: str, name_suffix: str) -> str:
    """
    Overlay a premium pricing banner onto the bottom of the product image using Pillow.
    Draws the Deal Price, original MRP (crossed out), and discount percentage pill.
    """
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
            
            # Draw semi-transparent dark zinc-950 bottom banner background
            draw.rectangle(
                [(0, banner_y), (width, height)],
                fill=(9, 9, 11, 235)
            )
            
            font_path = None
            for path in [
                "C:\\Windows\\Fonts\\arialbd.ttf",
                "C:\\Windows\\Fonts\\segoeuib.ttf",
                "C:\\Windows\\Fonts\\verdana.ttf"
            ]:
                if os.path.exists(path):
                    font_path = path
                    break
                    
            price_size = max(16, int(banner_h * 0.35))
            label_size = max(11, int(banner_h * 0.22))
            
            if font_path:
                price_font = ImageFont.truetype(font_path, price_size)
                mrp_font_path = font_path.replace("bd.ttf", ".ttf").replace("b.ttf", ".ttf")
                if not os.path.exists(mrp_font_path):
                    mrp_font_path = font_path
                mrp_font = ImageFont.truetype(mrp_font_path, label_size)
            else:
                price_font = ImageFont.load_default()
                mrp_font = ImageFont.load_default()
                
            margin = int(width * 0.05)
            center_y = banner_y + int(banner_h / 2)
            
            # Draw Deal Price
            price_text = f"Rs. {deal_price}" if deal_price else ""
            price_w = draw.textlength(price_text, font=price_font) if hasattr(draw, "textlength") else (len(price_text) * (price_size * 0.6))
            draw.text(
                (margin, center_y - int(price_size / 2)),
                price_text,
                fill=(74, 222, 128, 255),
                font=price_font
            )
            
            # Draw MRP
            curr_x = margin + price_w + int(width * 0.04)
            if mrp_val:
                mrp_text = f"MRP: {mrp_val}"
                mrp_w = draw.textlength(mrp_text, font=mrp_font) if hasattr(draw, "textlength") else (len(mrp_text) * (label_size * 0.6))
                mrp_y = center_y - int(label_size / 2)
                draw.text(
                    (curr_x, mrp_y),
                    mrp_text,
                    fill=(156, 163, 175, 255),
                    font=mrp_font
                )
                
                # Strike-through line
                line_y = mrp_y + int(label_size / 2) + 1
                draw.line(
                    [(curr_x, line_y), (curr_x + mrp_w, line_y)],
                    fill=(248, 113, 113, 255),
                    width=max(2, int(banner_h * 0.03))
                )
                curr_x += mrp_w + int(width * 0.04)
                
            # Draw Discount Pill
            if discount_pct:
                pill_text = f" {discount_pct}% OFF "
                pill_w = draw.textlength(pill_text, font=price_font) if hasattr(draw, "textlength") else (len(pill_text) * (price_size * 0.6))
                pill_h = int(price_size * 1.3)
                pill_x = width - margin - int(pill_w) - 10
                pill_y = center_y - int(pill_h / 2)
                
                draw.rounded_rectangle(
                    [(pill_x, pill_y), (pill_x + pill_w + 10, pill_y + pill_h)],
                    radius=int(pill_h / 2),
                    fill=(244, 63, 94, 255)
                )
                draw.text(
                    (pill_x + 5, pill_y + int(pill_h * 0.1)),
                    pill_text,
                    fill=(255, 255, 255, 255),
                    font=price_font
                )
                
            combined = Image.alpha_composite(im, overlay)
            
            base_name = os.path.basename(image_path)
            out_path = CACHE_DIR / f"overlay_{name_suffix}_{base_name}"
            
            combined.convert("RGB").save(out_path, "JPEG", quality=95)
            print(f"  [CardGen] Generated overlay banner: {out_path}")
            return str(out_path)
    except Exception as e:
        print(f"  [WARN] Failed to overlay pricing banner: {e}")
        return image_path

def generate_deal_cards(deal: ProductDeal, local_image_path: str) -> dict:
    """
    Generates optimized deal cards for different platforms.
    For Pipeline 2, we now use the cleaner overlay banner style from Pipeline 1.
    """
    print(f"[CardGen] Generating clean overlay cards for: {deal.title}")
    
    # Just apply the clean 16% bottom overlay over the raw image!
    overlay_path = overlay_pricing_banner(
        local_image_path, 
        str(deal.price), 
        str(deal.mrp), 
        str(deal.discount_percent), 
        "pin"
    )
    
    return {
        "pinterest": overlay_path,
        "ig_square": overlay_path,
        "ig_story": overlay_path
    }
