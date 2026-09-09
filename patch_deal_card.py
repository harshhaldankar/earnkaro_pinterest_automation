
import sys

with open("pipeline2/deal_card_generator.py", "r", encoding="utf-8") as f:
    content = f.read()

new_overlay_code = """
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
        center_text_with_bg(d3, f"Now Only Rs.{deal_price} \U0001F525", font_price, price_y, bg_color=(22, 163, 74, 230))
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
"""

# replace the old function with the new one using regex or split
import re
new_content = re.sub(r"def overlay_pricing_banner\(.*?\).*?def generate_ig_square", new_overlay_code + "\n\ndef generate_ig_square", content, flags=re.DOTALL)

with open("pipeline2/deal_card_generator.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Successfully injected UGC deal card generator!")

