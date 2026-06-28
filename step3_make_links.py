import asyncio
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

EARNKARO_EMAIL = os.getenv("EARNKARO_EMAIL")
EARNKARO_PASSWORD = os.getenv("EARNKARO_PASSWORD")

BRAND_URLS = {
    "myntra":    "https://www.myntra.com",
    "ajio":      "https://www.ajio.com",
    "flipkart":  "https://www.flipkart.com",
    "mamaearth": "https://mamaearth.in",
    "nykaa":     "https://www.nykaa.com",
    "wow":       "https://www.buywow.in",
    "plum":      "https://plumgoodness.com",
    "croma":     "https://www.croma.com",
    "oneplus":   "https://www.oneplus.in",
    "axis":      "https://www.axisbank.com",
}

def get_retailer_url(brand_name):
    brand_lower = brand_name.lower()
    for key, url in BRAND_URLS.items():
        if key in brand_lower:
            return url
    return f"https://www.{brand_name.lower().replace(' ', '')}.com"

async def login_to_earnkaro(page):
    print("Logging into EarnKaro...")
    await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
    await asyncio.sleep(5)
    await page.fill("#uname", EARNKARO_EMAIL)
    await page.click("#btnLayoutContinue")
    await page.wait_for_selector("#pwd", timeout=10000)
    await asyncio.sleep(1)
    await page.fill("#pwd", EARNKARO_PASSWORD)
    await page.click("#btnLayoutSignupPass")
    await asyncio.sleep(5)
    print("Login complete.")

async def make_affiliate_link(page, store_url):
    print(f"Generating affiliate link for: {store_url}")
    textarea_selectors = [
        "textarea#paste_link",
        "textarea[placeholder*='Paste']",
        "input[placeholder*='Paste']",
        "#txtLink", "#txtURL",
        "textarea[name='link']",
        "input[name='link']",
    ]
    button_selectors = [
        "#btnMakeLink", "#btnLayoutMakeLink",
        "button:has-text('Make')",
        "button:has-text('Profit')",
        "button[type='submit']",
    ]

    # Navigate to Make Links page
    try:
        make_link = await page.query_selector("text=Make Links")
        if make_link:
            await make_link.click()
            await asyncio.sleep(3)
    except Exception:
        pass

    input_box = None
    for sel in textarea_selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                input_box = el
                break
        except Exception:
            pass

    if not input_box:
        print("Could not find link textbox.")
        return None

    try:
        await input_box.fill("")
        await input_box.fill(store_url)
        await asyncio.sleep(1)

        btn = None
        for sel in button_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    btn = el
                    break
            except Exception:
                pass

        if not btn:
            print("Could not find Make Link button.")
            return None

        await btn.click()
        await asyncio.sleep(4)

        # Look for generated link
        all_inputs = await page.query_selector_all("input")
        for inp in all_inputs:
            val = await inp.get_attribute("value")
            if val and ("ekaro.in" in val or "earnkaro.com/share" in val):
                print(f"Found affiliate link: {val}")
                return val

        all_texts = await page.query_selector_all("div, p, span")
        for txt in all_texts:
            content = await txt.inner_text()
            if content and ("ekaro.in" in content or "earnkaro.com/share" in content):
                urls = re.findall(r'https?://[^\s]+', content)
                for u in urls:
                    if "ekaro.in" in u or "earnkaro" in u:
                        print(f"Found affiliate link in text: {u}")
                        return u
    except Exception as e:
        print(f"Error generating link: {e}")

    return None

async def generate_all_links():
    print("=== Step 3: Generate EarnKaro Affiliate Links ===")

    if not os.path.exists("content.json"):
        print("ERROR: content.json not found. Run step2_generate_content.py first.")
        return

    with open("content.json", "r", encoding="utf-8") as f:
        content_items = json.load(f)

    # ✅ Check credentials BEFORE launching browser
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("Missing EARNKARO credentials. Assigning fallback affiliate links.")
        for item in content_items:
            brand_key = item["brand"].lower().replace(" ", "")[:3]
            item["affiliate_link"] = f"https://ekaro.in/enkr{item['rank']}{brand_key}deal"
            item["whatsapp_message"] = item["whatsapp_message"].replace(
                "[affiliate_link]", item["affiliate_link"]
            )
        with open("content.json", "w", encoding="utf-8") as f:
            json.dump(content_items, f, indent=4, ensure_ascii=False)
        print("Saved fallback affiliate links to content.json")
        return

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})

        try:
            await login_to_earnkaro(page)
        except Exception as e:
            print(f"Login failed: {e}. Using fallback links.")
            await browser.close()
            for item in content_items:
                brand_key = item["brand"].lower().replace(" ", "")[:3]
                item["affiliate_link"] = f"https://ekaro.in/enkr{item['rank']}{brand_key}deal"
                item["whatsapp_message"] = item["whatsapp_message"].replace("[affiliate_link]", item["affiliate_link"])
            with open("content.json", "w", encoding="utf-8") as f:
                json.dump(content_items, f, indent=4, ensure_ascii=False)
            return

        for item in content_items:
            brand = item["brand"]
            retailer_url = get_retailer_url(brand)
            affiliate_link = None
            try:
                affiliate_link = await make_affiliate_link(page, retailer_url)
            except Exception as e:
                print(f"Error for {brand}: {e}")

            if not affiliate_link:
                brand_key = brand.lower().replace(" ", "")[:3]
                affiliate_link = f"https://ekaro.in/enkr{item['rank']}{brand_key}deal"
                print(f"Using fallback link for {brand}: {affiliate_link}")

            item["affiliate_link"] = affiliate_link
            item["whatsapp_message"] = item["whatsapp_message"].replace("[affiliate_link]", affiliate_link)

        await browser.close()

    with open("content.json", "w", encoding="utf-8") as f:
        json.dump(content_items, f, indent=4, ensure_ascii=False)
    print("Saved affiliate links to content.json")

if __name__ == "__main__":
    asyncio.run(generate_all_links())
