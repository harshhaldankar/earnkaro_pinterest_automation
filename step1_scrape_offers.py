import asyncio
import os
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

EARNKARO_EMAIL = os.getenv("EARNKARO_EMAIL")
EARNKARO_PASSWORD = os.getenv("EARNKARO_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FALLBACK_STORES = [
    {"brand": "Myntra",               "rate": "Up to 8.50% Profit",   "url": ""},
    {"brand": "Ajio",                 "rate": "Up to 10.00% Profit",  "url": ""},
    {"brand": "Flipkart",             "rate": "Up to 7.00% Profit",   "url": ""},
    {"brand": "Mamaearth",            "rate": "Flat 12.00% Profit",   "url": ""},
    {"brand": "Nykaa",                "rate": "Up to 6.00% Profit",   "url": ""},
    {"brand": "Axis Bank Credit Card","rate": "Flat Rs 2,500 Profit", "url": ""},
    {"brand": "Wow Skin Science",     "rate": "Flat 15.00% Profit",   "url": ""},
    {"brand": "Plum Goodness",        "rate": "Flat 12.50% Profit",   "url": ""},
    {"brand": "Croma",                "rate": "Up to 4.50% Profit",   "url": ""},
    {"brand": "OnePlus",              "rate": "Up to 3.00% Profit",   "url": ""},
]

async def login_to_earnkaro(page):
    print("Navigating to EarnKaro login page...")
    await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
    await asyncio.sleep(5)

    # Fill email - try multiple selectors
    print("Filling email/username...")
    for sel in ["#uname", "input[type='email']", "input[name='email']", "input[placeholder*='email' i]", "input[placeholder*='mobile' i]"]:
        try:
            await page.wait_for_selector(sel, timeout=5000)
            await page.fill(sel, EARNKARO_EMAIL)
            print(f"  Filled email using: {sel}")
            break
        except Exception:
            continue

    # Click continue/next button
    for sel in ["#btnLayoutContinue", "button[type='submit']", "button:has-text('Continue')", "button:has-text('Next')"]:
        try:
            await page.click(sel, timeout=5000)
            print(f"  Clicked continue using: {sel}")
            break
        except Exception:
            continue

    await asyncio.sleep(3)

    # Fill password - try multiple selectors
    print("Filling password...")
    for sel in ["#pwd", "input[type='password']", "input[name='password']", "input[placeholder*='password' i]"]:
        try:
            await page.wait_for_selector(sel, timeout=8000)
            await page.fill(sel, EARNKARO_PASSWORD)
            print(f"  Filled password using: {sel}")
            break
        except Exception:
            continue

    # Click login/submit button
    for sel in ["#btnLayoutSignupPass", "button[type='submit']", "button:has-text('Login')",
                "button:has-text('Sign in')", "input[type='submit']", ".btn-login"]:
        try:
            await page.click(sel, timeout=5000)
            print(f"  Clicked login using: {sel}")
            break
        except Exception:
            continue

    print("Waiting for navigation post-login...")
    await asyncio.sleep(6)
    print("Login complete.")

async def extract_stores_from_page(page):
    cards = []
    for selector in ["div", "li", "a"]:
        try:
            elements = await page.query_selector_all(selector)
            for el in elements:
                text = await el.inner_text()
                if not text:
                    continue
                text_lower = text.lower()
                if "%" in text and ("profit" in text_lower or "commission" in text_lower or "earn" in text_lower):
                    img = await el.query_selector("img")
                    brand_name = None
                    if img:
                        alt = await img.get_attribute("alt")
                        if alt and len(alt.strip()) > 1 and not any(x in alt.lower() for x in ["earnkaro", "logo", "banner", "google"]):
                            brand_name = alt.strip()
                        else:
                            src = await img.get_attribute("src")
                            if src:
                                brand_name = src.split("/")[-1].split("-")[0].split(".")[0].capitalize()
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    if not brand_name and lines:
                        potential_brand = lines[0]
                        if len(potential_brand) < 30 and not any(x in potential_brand.lower() for x in ["profit", "earn", "commission", "off", "rs"]):
                            brand_name = potential_brand
                    profit_rate = None
                    for line in lines:
                        if "%" in line and ("profit" in line.lower() or "commission" in line.lower() or "earn" in line.lower()):
                            profit_rate = line
                            break
                    href = await el.get_attribute("href") or ""
                    if brand_name and profit_rate and len(brand_name) < 50:
                        cards.append({"brand": brand_name, "rate": profit_rate, "url": href})
        except Exception:
            pass
    seen = set()
    unique_cards = []
    for c in cards:
        key = (c["brand"].lower(), c["rate"].lower())
        if key not in seen:
            seen.add(key)
            unique_cards.append(c)
    return unique_cards

async def scrape_all_partners():
    # ✅ Check credentials BEFORE launching browser
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("Missing EARNKARO_EMAIL or EARNKARO_PASSWORD. Using fallback brands.")
        return FALLBACK_STORES

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})

        try:
            await login_to_earnkaro(page)
        except Exception as e:
            print(f"Login failed: {e}. Using fallback brands.")
            await browser.close()
            return FALLBACK_STORES

        target_urls = [
            "https://earnkaro.com/our-partners",
            "https://earnkaro.com/stores",
            "https://earnkaro.com/partners",
            "https://earnkaro.com/retailer-rates",
            "https://earnkaro.com/",
        ]
        all_scraped_stores = []
        for url in target_urls:
            try:
                print(f"Checking: {url}")
                await page.goto(url, wait_until="domcontentloaded")
                await asyncio.sleep(4)
                stores = await extract_stores_from_page(page)
                print(f"Found {len(stores)} stores at {url}")
                all_scraped_stores.extend(stores)
            except Exception as e:
                print(f"Error scraping {url}: {e}")

        await browser.close()

        # Deduplicate
        seen = set()
        final_stores = []
        for s in all_scraped_stores:
            key = s["brand"].lower()
            if key not in seen:
                seen.add(key)
                final_stores.append(s)

        if not final_stores:
            print("No stores scraped from site. Using fallback brands.")
            return FALLBACK_STORES

        print(f"Total unique stores: {len(final_stores)}")
        return final_stores

def rank_offers_with_gemini(stores):
    print("Calling Gemini 1.5 Flash to rank top 10 offers...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""
You are an expert affiliate marketer specializing in the Indian market.
Here is a list of available brands and their profit/commission rates from EarnKaro:
{json.dumps(stores, indent=2)}

Select and rank the TOP 10 offers with the highest earning potential for a general Indian audience.
Consider brand popularity, commission rate, and impulse-buy virality.

Return ONLY a valid JSON array with these fields per item:
- "rank" (integer 1-10)
- "brand" (string)
- "rate" (string)
- "category" (string, e.g. Fashion / Beauty / Electronics / Finance / Health)
- "target_audience" (string)
- "why" (string)
"""
        response = model.generate_content(prompt)
        text_clean = re.sub(r"```json\s*|```", "", response.text).strip()
        top_offers = json.loads(text_clean)
        print("Gemini ranked offers successfully.")
        for o in top_offers:
            print(f"  Rank {o['rank']}: {o['brand']} — {o['rate']}")
        return top_offers
    except Exception as e:
        print(f"Gemini API error: {e}. Using local fallback ranking.")
        fallback_offers = []
        for i, s in enumerate(stores[:10], 1):
            fallback_offers.append({
                "rank": i,
                "brand": s["brand"],
                "rate": s["rate"],
                "category": "General E-commerce",
                "target_audience": "General Indian audience",
                "why": "Local fallback ranking.",
            })
        return fallback_offers

async def main():
    print("=== Step 1: Scrape EarnKaro & Rank Offers ===")
    stores = await scrape_all_partners()
    top_offers = rank_offers_with_gemini(stores)
    with open("offers.json", "w", encoding="utf-8") as f:
        json.dump(top_offers, f, indent=4, ensure_ascii=False)
    print(f"Saved {len(top_offers)} offers to offers.json")

if __name__ == "__main__":
    asyncio.run(main())
