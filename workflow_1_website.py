import asyncio
import os
import json
import re
import shutil
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from playwright.async_api import async_playwright

load_dotenv()

EARNKARO_EMAIL = os.getenv("EARNKARO_EMAIL")
EARNKARO_PASSWORD = os.getenv("EARNKARO_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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

FALLBACK_STORES = [
    {"brand": "Myntra",               "rate": "Up to 8.50% Profit",   "website": "https://www.myntra.com"},
    {"brand": "Ajio",                 "rate": "Up to 10.00% Profit",  "website": "https://www.ajio.com"},
    {"brand": "Flipkart",             "rate": "Up to 7.00% Profit",   "website": "https://www.flipkart.com"},
    {"brand": "Mamaearth",            "rate": "Flat 12.00% Profit",   "website": "https://mamaearth.in"},
    {"brand": "Nykaa",                "rate": "Up to 6.00% Profit",   "website": "https://www.nykaa.com"},
    {"brand": "Axis Bank Credit Card","rate": "Flat Rs 2,500 Profit", "website": "https://www.axisbank.com"},
    {"brand": "Wow Skin Science",     "rate": "Flat 15.00% Profit",   "website": "https://www.buywow.in"},
    {"brand": "Plum Goodness",        "rate": "Flat 12.50% Profit",   "website": "https://plumgoodness.com"},
    {"brand": "Croma",                "rate": "Up to 4.50% Profit",   "website": "https://www.croma.com"},
    {"brand": "OnePlus",              "rate": "Up to 3.00% Profit",   "website": "https://www.oneplus.in"},
]

# ---------------------------------------------------------
# 1. PLAYWRIGHT SCRAPING & LINK GENERATION
# ---------------------------------------------------------

async def login_to_earnkaro(page):
    print("Navigating to EarnKaro login page...")
    await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
    await asyncio.sleep(5)

    print("Filling email/username...")
    for sel in ["#uname", "input[type='email']", "input[name='email']", "input[placeholder*='email' i]", "input[placeholder*='mobile' i]"]:
        try:
            await page.wait_for_selector(sel, timeout=5000)
            await page.fill(sel, EARNKARO_EMAIL)
            break
        except: continue

    for sel in ["#btnLayoutContinue", "button[type='submit']", "button:has-text('Continue')", "button:has-text('Next')"]:
        try:
            await page.click(sel, timeout=5000)
            break
        except: continue

    await asyncio.sleep(3)
    print("Filling password...")
    for sel in ["#pwd", "input[type='password']", "input[name='password']", "input[placeholder*='password' i]"]:
        try:
            await page.wait_for_selector(sel, timeout=8000)
            await page.fill(sel, EARNKARO_PASSWORD)
            break
        except: continue

    for sel in ["#btnLayoutSignupPass", "button[type='submit']", "button:has-text('Login')", "button:has-text('Sign in')", "input[type='submit']", ".btn-login"]:
        try:
            await page.click(sel, timeout=5000)
            break
        except: continue

    print("Waiting for navigation post-login...")
    await asyncio.sleep(6)
    print("Login complete.")

async def extract_stores_from_page(page):
    cards = []
    try:
        elements = await page.query_selector_all("div, li, a")
        for el in elements:
            text = await el.inner_text()
            if not text: continue
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
                        if src: brand_name = src.split("/")[-1].split("-")[0].split(".")[0].capitalize()
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
                if brand_name and profit_rate and len(brand_name) < 50:
                    website = ""
                    for key, url in BRAND_URLS.items():
                        if key in brand_name.lower():
                            website = url
                            break
                    if not website:
                        website = f"https://www.{brand_name.lower().replace(' ', '')}.com"
                    cards.append({"brand": brand_name, "rate": profit_rate, "website": website})
    except: pass
    
    seen = set()
    unique = []
    for c in cards:
        if c["brand"].lower() not in seen:
            seen.add(c["brand"].lower())
            unique.append(c)
    return unique

async def make_affiliate_link(page, store_url):
    print(f"  Generating link for {store_url}...")
    # Wait for the input box to be visible
    input_box = None
    for sel in ["textarea#paste_link", "textarea[placeholder*='Paste']", "input[placeholder*='Paste']", "#txtLink", "#txtURL", "textarea[name='link']", "input[name='link']"]:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                input_box = el
                break
        except: pass

    if not input_box: return None

    try:
        await input_box.click()
        await asyncio.sleep(0.5)
        await input_box.fill("")
        await asyncio.sleep(0.5)
        await input_box.fill(store_url)
        await asyncio.sleep(1.5) # Crucial delay for React to register the input
        
        btn = None
        for sel in ["#btnMakeLink", "#btnLayoutMakeLink", "button:has-text('Make')", "button:has-text('Profit')", "button[type='submit']"]:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    btn = el
                    break
            except: pass

        if not btn: return None
        await btn.click()
        await asyncio.sleep(1.0)
        
        # Fast poll for the result, up to 15 seconds max
        for _ in range(30):
            await asyncio.sleep(0.5)
            all_inputs = await page.query_selector_all("input")
            for inp in all_inputs:
                val = await inp.get_attribute("value")
                if val and ("ekaro.in" in val or "earnkaro.com/share" in val):
                    return val

            all_texts = await page.query_selector_all("div, p, span")
            for txt in all_texts:
                content = await txt.inner_text()
                if content and ("ekaro.in" in content or "earnkaro.com/share" in content):
                    urls = re.findall(r'https?://[^\s]+', content)
                    for u in urls:
                        if "ekaro.in" in u or "earnkaro" in u: return u
    except: pass
    return None

async def run_scraper():
    print("=== STEP 1: SCRAPING EARNKARO ===")
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("Missing EarnKaro credentials. Returning fallback data.")
        return FALLBACK_STORES

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        try:
            await login_to_earnkaro(page)
            print("Checking stores...")
            await page.goto("https://earnkaro.com/our-partners", wait_until="domcontentloaded")
            await asyncio.sleep(4)
            stores = await extract_stores_from_page(page)
            
            if not stores:
                print("No stores found, using fallbacks.")
                stores = FALLBACK_STORES
        except Exception as e:
            print(f"Scraping failed: {e}. Using fallbacks.")
            stores = FALLBACK_STORES
        
        await browser.close()
        return stores

async def generate_links_for_top_10(top_offers):
    print("=== STEP 3: GENERATING AFFILIATE LINKS ===")
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("Missing credentials. Generating dummy links.")
        for item in top_offers:
            key = item["brand"].lower().replace(" ", "")[:4]
            item["affiliate_link"] = f"https://ekaro.in/enkr_{key}_deal"
        return top_offers

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        try:
            await login_to_earnkaro(page)
            
            # Navigate to Make Links section just ONCE
            print("  Opening Make Links tab...")
            try:
                make_link = await page.query_selector("text=Make Links")
                if make_link:
                    await make_link.click()
                    await asyncio.sleep(3)
                else:
                    await page.goto("https://earnkaro.com/make-links", wait_until="domcontentloaded")
                    await asyncio.sleep(3)
            except: pass

            for item in top_offers:
                link = await make_affiliate_link(page, item["website"])
                if link:
                    item["affiliate_link"] = link
                else:
                    key = item["brand"].lower().replace(" ", "")[:4]
                    item["affiliate_link"] = f"https://ekaro.in/enkr_{key}_deal"
        except Exception as e:
            print(f"Link generation failed: {e}")
            for item in top_offers:
                if "affiliate_link" not in item:
                    item["affiliate_link"] = f"https://ekaro.in/enkr_fallback"
        
        await browser.close()
        return top_offers

# ---------------------------------------------------------
# 2. GEMINI CONTENT GENERATION
# ---------------------------------------------------------

def rank_and_curate_with_gemini(stores):
    print("=== STEP 2: CURATING DEALS WITH GEMINI 2.0 ===")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
You are an expert Indian affiliate marketer. I have scraped these offers from EarnKaro:
{json.dumps(stores[:20], indent=2)}

Select the TOP 10 best offers (highest profit / most popular).
For each offer, write engaging content for a website deals page.

Return ONLY a valid JSON array with exactly 10 objects. Each object must have:
- "rank": integer (1 to 10)
- "brand": string (brand name)
- "rate": string (profit rate)
- "website": string (original website URL)
- "category": string (e.g. Fashion, Electronics, Beauty)
- "title": string (catchy SEO title, max 60 chars)
- "description": string (persuasive 2-3 sentence description emphasizing the deal)
- "angle": string (very short 3-5 word hook, e.g. "Save Big on Myntra")
"""
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = re.sub(r"```json\s*|```", "", resp.text).strip()
        data = json.loads(text)
        print("Gemini generated top 10 successfully.")
        return data
    except Exception as e:
        print(f"Gemini failed: {e}. Using fallback.")
        fallbacks = []
        for i, s in enumerate(stores[:10], 1):
            fallbacks.append({
                "rank": i,
                "brand": s["brand"],
                "rate": s["rate"],
                "website": s.get("website", ""),
                "category": "Shopping",
                "title": f"Huge Savings on {s['brand']}",
                "description": f"Don't miss out on this amazing {s['rate']} opportunity on {s['brand']}.",
                "angle": "Limited Time Offer!"
            })
        return fallbacks

# ---------------------------------------------------------
# 3. WEBSITE GENERATION (HTML & CSS)
# ---------------------------------------------------------

def generate_website(offers):
    print("=== STEP 4: GENERATING WEBSITE HTML ===")
    DOCS_DIR = "docs"
    DEALS_DIR = os.path.join(DOCS_DIR, "deals")
    
    # 1. Use the unzipped 'getyourdeal_website' template provided by the user
    TEMPLATE_DIR = "getyourdeal_website"
    
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
        
    if os.path.exists(TEMPLATE_DIR):
        shutil.copytree(TEMPLATE_DIR, DOCS_DIR)
    else:
        os.makedirs(DOCS_DIR, exist_ok=True)
        
    os.makedirs(DEALS_DIR, exist_ok=True)

    # 2. Generate robust CSS to fix UI bugs directly in the deals/ folder
    css = """
/* Reset & Base */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { 
  font-family: 'Outfit', sans-serif; 
  background-color: #0b0c10; 
  color: #c5c6c7; 
  line-height: 1.6;
}

/* Navbar */
.navbar {
  position: fixed; top: 0; width: 100%; z-index: 1000;
  background: rgba(11, 12, 16, 0.95);
  padding: 1rem 5%;
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid #1f2833;
}
.logo { font-size: 1.5rem; font-weight: 800; color: #66fcf1; text-decoration: none; }
.nav-links a { 
  color: #c5c6c7; text-decoration: none; margin-left: 1.5rem; font-weight: 600; 
}
.nav-links a:hover, .nav-links a.active { color: #66fcf1; }

/* Hero Section */
.deals-hero {
  padding: 120px 5% 40px;
  text-align: center;
}
.deals-hero h1 {
  font-size: 3rem; color: #fff; font-weight: 800; margin-bottom: 10px;
}
.gradient-text {
  background: linear-gradient(90deg, #66fcf1, #45a29e);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.badge {
  display: inline-block; background: #1f2833; color: #45a29e;
  padding: 5px 15px; border-radius: 20px; font-size: 0.9rem; font-weight: 600;
  margin-bottom: 15px;
}

/* DEALS GRID - This fixes the broken layout! */
.deals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 2rem;
  max-width: 1200px;
  margin: 0 auto 80px auto;
  padding: 0 5%;
}

.deal-card {
  background: #1f2833;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  border: 1px solid #2a3644;
}
.deal-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 25px rgba(102, 252, 241, 0.1);
}

.card-img-wrap {
  width: 100%;
  height: 200px; /* Fixed height for uniformity */
  background: #0b0c10;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #2a3644;
}

.brand-placeholder {
  font-size: 4rem;
  font-weight: 800;
  color: #45a29e;
  opacity: 0.8;
}

.card-rank {
  position: absolute; top: 10px; left: 10px;
  background: #66fcf1; color: #0b0c10; font-weight: 800;
  padding: 4px 12px; border-radius: 20px; font-size: 0.9rem;
}
.card-cat {
  position: absolute; top: 10px; right: 10px;
  background: rgba(0,0,0,0.6); color: #fff; font-size: 0.8rem;
  padding: 4px 10px; border-radius: 20px; border: 1px solid #45a29e;
}

.card-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.card-brand { color: #fff; font-size: 1.4rem; font-weight: 800; margin-bottom: 0.5rem; }
.card-rate {
  display: inline-block;
  background: rgba(69, 162, 158, 0.15); color: #66fcf1;
  padding: 5px 12px; border-radius: 8px; font-weight: 700; font-size: 0.9rem;
  margin-bottom: 1rem; border: 1px solid rgba(102, 252, 241, 0.3);
}

.card-angle { color: #45a29e; font-style: italic; font-weight: 600; margin-bottom: 0.5rem; font-size: 0.95rem; }
.card-title { color: #fff; font-weight: 700; margin-bottom: 0.5rem; font-size: 1.1rem; }
.card-desc { color: #c5c6c7; font-size: 0.9rem; margin-bottom: 1.5rem; flex-grow: 1; }

.btn-deal {
  display: block; width: 100%; text-align: center;
  background: #66fcf1; color: #0b0c10; text-decoration: none;
  padding: 12px; border-radius: 8px; font-weight: 800;
  transition: background 0.3s ease;
}
.btn-deal:hover { background: #45a29e; color: #fff; }

.footer {
  text-align: center; padding: 2rem; background: #0b0c10;
  border-top: 1px solid #1f2833; margin-top: auto;
}
.footer-links a { color: #45a29e; margin: 0 10px; text-decoration: none; }
"""
    with open(os.path.join(DEALS_DIR, "deals.css"), "w", encoding="utf-8") as f:
        f.write(css)

    # 3. Generate HTML Cards
    cards_html = ""
    for item in offers:
        brand = item.get("brand", "Unknown")
        cards_html += f"""
        <article class="deal-card">
            <div class="card-img-wrap">
                <div class="brand-placeholder">{brand[0].upper()}</div>
                <span class="card-rank">#{item.get('rank', '-')}</span>
                <span class="card-cat">{item.get('category', 'Deal')}</span>
            </div>
            <div class="card-body">
                <h3 class="card-brand">{brand}</h3>
                <div class="card-rate">{item.get('rate', 'High Profit')}</div>
                <p class="card-angle">"{item.get('angle', 'Save Big')}"</p>
                <p class="card-title">{item.get('title', 'Great Deal')}</p>
                <p class="card-desc">{item.get('description', '')}</p>
                <a href="{item.get('affiliate_link', '#')}" target="_blank" rel="noopener" class="btn-deal">🛍️ Get This Deal</a>
            </div>
        </article>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Today's Best Deals</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="deals.css" />
</head>
<body>
  <nav class="navbar">
    <a href="../index.html" class="logo">🛍️ Get Your Deal</a>
    <div class="nav-links">
      <a href="../index.html">Home</a>
      <a href="./index.html" class="active">Today's Deals</a>
    </div>
  </nav>

  <div class="deals-hero">
    <div class="badge">🔄 Auto-updated by AI</div>
    <h1>Today's <span class="gradient-text">Top {len(offers)} Deals</span></h1>
    <p>Last updated: {datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")}</p>
  </div>

  <main class="deals-grid">
    {cards_html}
  </main>

  <footer class="footer">
    <div class="footer-links">
      <a href="../privacy.html">Privacy Policy</a>
      <a href="../terms.html">Terms of Service</a>
    </div>
    <p style="margin-top: 10px; font-size: 0.85rem;">© 2024 Get Your Deal. Affiliate links disclosure: we earn a commission at no extra cost to you.</p>
  </footer>
</body>
</html>"""

    with open(os.path.join(DEALS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Website HTML and CSS generated successfully!")

# ---------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------
async def main():
    print("Starting Website Pipeline...")
    
    stores = await run_scraper()
    top_offers = rank_and_curate_with_gemini(stores)
    top_offers = await generate_links_for_top_10(top_offers)
    
    generate_website(top_offers)
    
    print("\n=== PIPELINE COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
