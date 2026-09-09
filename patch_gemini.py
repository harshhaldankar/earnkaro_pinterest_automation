
import sys

with open("telegram_watcher.py", "r", encoding="utf-8") as f:
    content = f.read()

gemini_code = """
async def enhance_deal_with_gemini(title, desc):
    import os
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return title, desc
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = f\"\"\"
        You are an expert Pinterest and Instagram aesthetic content creator. 
        Take this raw spammy e-commerce product title and description and rewrite them to be highly attractive, clean, and viral.

        Raw Title: {title}
        Raw Description: {desc}

        Rules:
        - Title must be minimalist, aesthetic, and sound human (Max 60 chars). No spammy SEO keywords.
        - Description must be a trendy, lifestyle description of why this product is amazing, followed by exactly 5 highly targeted Pinterest hashtags (e.g. #FashionInspo #MinimalistStyle).
        - DO NOT output Markdown. Output raw JSON only.

        Output EXACTLY in this JSON format:
        {{
            "title": "Aesthetic minimalist title",
            "desc": "Trendy description... #hashtag1 #hashtag2"
        }}
        \"\"\"
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        import json
        data = json.loads(text)
        return data.get("title", title), data.get("desc", desc)
    except Exception as e:
        print(f"  [WARN] Gemini enhancement failed: {e}")
        return title, desc
"""

if "enhance_deal_with_gemini" not in content:
    content = content.replace("def is_single_product_url(", gemini_code + "\n\ndef is_single_product_url(")

hook_code = """
    # AI Enhancement (New Step)
    print(f"  [AI] Enhancing deal title and description with Gemini...")
    new_title, new_desc = await enhance_deal_with_gemini(deal["title"], deal["desc"])
    deal["title"] = new_title
    deal["desc"] = new_desc

    # 2. Save database and rebuild website using the card image"""

if "Enhancing deal title and description" not in content:
    content = content.replace("# 2. Save database and rebuild website using the card image", hook_code)

with open("telegram_watcher.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully injected Gemini AI optimizer!")

