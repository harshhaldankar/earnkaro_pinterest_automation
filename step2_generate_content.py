import json
import os
import re
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_marketing_content():
    print("=== Step 2: Generate Pinterest & WhatsApp Content ===")

    if not os.path.exists("offers.json"):
        print("ERROR: offers.json not found. Run step1_scrape_offers.py first.")
        return

    with open("offers.json", "r", encoding="utf-8") as f:
        offers = json.load(f)

    if not offers:
        print("ERROR: offers.json is empty.")
        return

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
You are a friendly deal-sharing expert in India who creates content for Pinterest and WhatsApp.

For each offer below, write creative Hinglish content:
{json.dumps(offers, indent=2)}

Return ONLY a valid JSON array. Each item must have ALL the original fields PLUS:
- "pinterest_title": SEO-optimized, max 100 chars
- "pinterest_description": helpful + hashtags, max 500 chars
- "keywords": list of exactly 5 keyword strings
- "whatsapp_message": Hinglish (Hindi + English mix), emoji-heavy, friendly tone, max 150 words, include placeholder [affiliate_link]
- "angle": 4-6 word hook for pin image (e.g. "Branded Kurtas Under 499")

Important: Return strictly valid JSON only. No markdown.
"""
        response = model.generate_content(prompt)
        text_clean = re.sub(r"```json\s*|```", "", response.text).strip()
        content_results = json.loads(text_clean)
        print("Gemini generated content successfully.")

    except Exception as e:
        print(f"Gemini API error: {e}. Using fallback content.")
        content_results = []
        for o in offers:
            brand = o["brand"]
            rate = o["rate"]
            content_results.append({
                **o,
                "pinterest_title": f"Best deals on {brand} - Save up to {rate}!",
                "pinterest_description": (
                    f"Amazing {brand} deals! Get {rate} on your purchase via EarnKaro affiliate links. "
                    f"Start saving today on top Indian brands. "
                    f"#deals #india #{brand.lower().replace(' ', '')} #shopping #earnkaro"
                ),
                "keywords": [brand.lower(), "deals", "india", "shopping", "earnkaro"],
                "whatsapp_message": (
                    f"🔥 Yaar sun! {brand} par ekdum mast offer aa gaya hai! 😍\n"
                    f"Tum {rate} earn kar sakte ho apne purchases pe! 💰\n"
                    f"Abhi check karo aur dosto ko bhi batao! 👇\n"
                    f"[affiliate_link] 🎁✨"
                ),
                "angle": f"Save Big on {brand}!",
            })

    with open("content.json", "w", encoding="utf-8") as f:
        json.dump(content_results, f, indent=4, ensure_ascii=False)
    print(f"Saved content for {len(content_results)} offers to content.json")

if __name__ == "__main__":
    generate_marketing_content()
