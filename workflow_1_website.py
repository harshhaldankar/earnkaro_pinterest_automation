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
    input_box = None
    # Use known EarnKaro selectors first, then fallbacks
    for sel in ["#deallink", "input[placeholder*='Paste' i]", "textarea[placeholder*='Paste' i]",
                "#txtLink", "#txtURL", "input[name='deallink']", "input[name='link']"]:
        try:
            await page.wait_for_selector(sel, timeout=5000)
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                input_box = el
                break
        except: pass

    if not input_box:
        await page.screenshot(path="debug_no_input.png", full_page=False)
        print("  [WARN] Input box not found - screenshot saved")
        return None

    try:
        await input_box.click()
        await asyncio.sleep(0.5)
        await input_box.fill("")
        await asyncio.sleep(0.5)
        await input_box.fill(store_url)
        await asyncio.sleep(1.5) # Crucial delay for React to register the input
        
        btn = None
        # Use class or text to find the generate button
        for sel in ["button.showdealpp", "button[id*='Btn']", "#btnMakeLink",
                    "button:has-text('PROFIT')", "button:has-text('Make')",
                    "button[type='submit']"]:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    btn = el
                    break
            except: pass

        if not btn: return None
        await btn.click()
        await asyncio.sleep(2.0)

        # Dismiss any popup/modal that EarnKaro shows (e.g. "Review Your Application")
        for close_sel in ["button.close", ".modal .close", "button[aria-label='Close']",
                          ".popup-close", "button:has-text('×')", ".btn-close",
                          "a.close", "[class*='close']", "button.swal2-close",
                          "span:has-text('×')", ".modal-header .close"]:
            try:
                el = await page.query_selector(close_sel)
                if el and await el.is_visible():
                    await el.click()
                    print("  [INFO] Dismissed popup")
                    await asyncio.sleep(1.0)
                    break
            except: pass

        # Also try pressing Escape to close any modal
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.0)

        # Poll for the result link, up to 15 seconds max
        for _ in range(30):
            await asyncio.sleep(0.5)
            # 1. Primary result box id="deallinkshorturl"
            el = await page.query_selector("#deallinkshorturl")
            if el:
                val = await el.get_attribute("value")
                if val and len(val) > 10 and "http" in val:
                    return val

            # 2. Fallback: any short URL in inputs
            all_inputs = await page.query_selector_all("input")
            for inp in all_inputs:
                val = await inp.get_attribute("value")
                if val and "http" in val and len(val) < 50 and store_url not in val:
                    return val

            # 3. Fallback: short URL visible in page text
            all_texts = await page.query_selector_all("div, p, span, a")
            for txt in all_texts:
                content = await txt.inner_text()
                if content and any(x in content for x in ["ekaro.in", "fktr.in", "bitli.in", "mynt.in"]):
                    urls = re.findall(r'https?://[^\s]+', content)
                    for u in urls:
                        if len(u) < 50: return u
    except: pass
    return None

async def make_affiliate_link_api(session_cookies, store_url):
    """Call EarnKaro API directly using session cookies. Fast & popup-free."""
    import requests
    cookie_dict = {c["name"]: c["value"] for c in session_cookies}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://earnkaro.com/create-earn-link",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        resp = requests.post(
            "https://earnkaro.com/pps/user/makeearnlink",
            data={"deal_link": store_url, "platform": "web"},
            cookies=cookie_dict, headers=headers, timeout=15
        )
        result = resp.json()
        if result.get("code") == "success":
            link = result.get("shared_link", "")
            print(f"  [API] {store_url} -> {link}")
            return link
        else:
            print(f"  [API] Error: {result}")
            return None
    except Exception as e:
        print(f"  [API] Request failed: {e}")
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
            print("Checking stores on dashboard...")
            # EarnKaro removed /our-partners, the best deals are now on the dashboard
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
        page    = await browser.new_page(viewport={"width": 1280, "height": 800})

        try:
            await login_to_earnkaro(page)

            # Capture session cookies for direct API calls
            cookies = await page.context.cookies()
            print(f"  [AUTH] Captured {len(cookies)} session cookies")

            print("  [INFO] Generating affiliate links via API...")
            for item in top_offers:
                store_url = item.get("website", "")
                if not store_url or "http" not in store_url:
                    continue

                link = await make_affiliate_link_api(cookies, store_url)
                if link:
                    item["affiliate_link"] = link
                else:
                    key = item["brand"].lower().replace(" ", "")[:4]
                    item["affiliate_link"] = f"https://ekaro.in/enkr_{key}_deal"

        except Exception as e:
            print(f"Link generation failed: {e}")
            for item in top_offers:
                if "affiliate_link" not in item:
                    item["affiliate_link"] = "https://ekaro.in/enkr_fallback"

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
        
        # Add retry logic for 429 Rate Limit errors
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                break # Success! Break out of the retry loop
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    if attempt < max_retries - 1:
                        print(f"Gemini API rate limit hit. Waiting 45 seconds before retrying (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(45)
                    else:
                        print("Gemini API rate limit hit. Max retries exceeded.")
                        raise e
                else:
                    raise e
                    
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

CATEGORY_EMOJI = {
    "Fashion": "👗", "Electronics": "📱", "Beauty": "💄",
    "Finance": "💳", "Shopping": "🛍️", "Food": "🍕",
    "Travel": "✈️", "Health": "💊",
}

BANNER_GRADS = [
    "linear-gradient(135deg, #1a0a18, #2d1040)",
    "linear-gradient(135deg, #0a1628, #1a0a3a)",
    "linear-gradient(135deg, #0a1a10, #0d2a1c)",
    "linear-gradient(135deg, #1a1000, #2a1a00)",
    "linear-gradient(135deg, #1a0010, #2a001a)",
]

def generate_website(offers):
    print("=== STEP 4: GENERATING WEBSITE HTML ===")
    DOCS_DIR = "docs"
    DEALS_DIR = os.path.join(DOCS_DIR, "deals")
    TEMPLATE = "getyourdeal_website"

    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)

    if os.path.exists(TEMPLATE):
        shutil.copytree(TEMPLATE, DOCS_DIR)
    else:
        os.makedirs(DOCS_DIR, exist_ok=True)

    os.makedirs(DEALS_DIR, exist_ok=True)

    css = """
/* Reset & Base */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: 'Outfit', sans-serif;
  background: #070b14; color: #dde6f0; line-height: 1.65; min-height: 100vh;
}
a { color: inherit; text-decoration: none; }

/* Navbar */
.navbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100; padding: 16px 5%;
  background: rgba(7,11,20,0.85); backdrop-filter: blur(18px);
  border-bottom: 1px solid rgba(255,255,255,0.07);
  display: flex; align-items: center; justify-content: space-between;
}
.logo {
  font-size: 1.25rem; font-weight: 800; letter-spacing: -0.3px; display: flex; align-items: center; gap: 8px;
  background: linear-gradient(135deg, #e94560, #7c3aed); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.nav-links { display: flex; gap: 28px; font-size: 0.9rem; font-weight: 600; }
.nav-links a { color: #8a9bb0; transition: color 0.2s; }
.nav-links a:hover, .nav-links a.active { color: #fff; }

/* Page Hero */
.page-hero {
  padding: 130px 5% 60px; text-align: center;
  background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(233,69,96,0.12), transparent);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(233,69,96,0.12); border: 1px solid rgba(233,69,96,0.3);
  color: #e94560; font-size: 0.82rem; font-weight: 700;
  padding: 6px 18px; border-radius: 50px; margin-bottom: 20px; letter-spacing: 0.5px;
}
.page-hero h1 { font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 800; letter-spacing: -2px; color: #fff; margin-bottom: 12px; }
.grad { background: linear-gradient(135deg, #e94560, #7c3aed); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.page-hero .sub { color: #8a9bb0; font-size: 1rem; max-width: 460px; margin: 0 auto 10px; }
.page-hero .ts  { color: #5a6a7a; font-size: 0.82rem; }

/* Deals Grid */
.deals-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 24px;
  max-width: 1280px; margin: 56px auto 80px; padding: 0 5%;
}

/* Deal Card */
.deal-card {
  background: #0e1623; border: 1px solid rgba(255,255,255,0.07); border-radius: 20px;
  display: flex; flex-direction: column; overflow: hidden;
  transition: transform 0.3s, box-shadow 0.3s;
}
.deal-card:hover {
  transform: translateY(-6px); box-shadow: 0 24px 60px rgba(233,69,96,0.15); border-color: rgba(233,69,96,0.25);
}
.card-top {
  position: relative; height: 110px; display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.card-top::before {
  content: ''; position: absolute; inset: 0; opacity: 0.9;
  background: var(--banner-grad, linear-gradient(135deg, #1a0a18, #120e22));
}
.card-initial {
  position: relative; z-index: 1; font-size: 3.5rem; font-weight: 900; line-height: 1;
  color: rgba(255,255,255,0.12); letter-spacing: -4px; user-select: none;
}
.card-rank-badge {
  position: absolute; top: 12px; left: 14px; z-index: 2;
  background: rgba(0,0,0,0.55); backdrop-filter: blur(8px);
  color: #fff; font-size: 0.75rem; font-weight: 700;
  padding: 3px 10px; border-radius: 50px; border: 1px solid rgba(255,255,255,0.12);
}
.card-cat-badge {
  position: absolute; top: 12px; right: 14px; z-index: 2; font-size: 0.72rem; font-weight: 700;
  padding: 3px 10px; border-radius: 50px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); color: #c5d0de;
}
.card-body { padding: 20px 22px 22px; display: flex; flex-direction: column; flex: 1; }
.card-brand { font-size: 1.25rem; font-weight: 800; color: #fff; margin-bottom: 8px; }
.card-rate-pill {
  display: inline-block; align-self: flex-start;
  background: rgba(233,69,96,0.1); border: 1px solid rgba(233,69,96,0.3);
  color: #e94560; font-size: 0.8rem; font-weight: 700;
  padding: 4px 14px; border-radius: 50px; margin-bottom: 12px;
}
.card-angle { color: #f59e0b; font-style: italic; font-size: 0.88rem; font-weight: 600; margin-bottom: 6px; }
.card-title { color: #c5d0de; font-size: 0.9rem; font-weight: 600; margin-bottom: 6px; }
.card-desc { color: #6b7f94; font-size: 0.83rem; line-height: 1.5; flex: 1; margin-bottom: 18px; }
.btn-deal {
  display: block; text-align: center; width: 100%;
  background: linear-gradient(135deg, #e94560, #7c3aed); color: #fff; font-weight: 700; font-size: 0.9rem;
  padding: 11px 18px; border-radius: 12px; transition: opacity 0.2s, transform 0.2s; box-shadow: 0 4px 20px rgba(233,69,96,0.3);
}
.btn-deal:hover { opacity: 0.88; transform: translateY(-1px); }

/* Footer */
.footer { background: #070b14; border-top: 1px solid rgba(255,255,255,0.06); padding: 36px 5%; text-align: center; }
.footer-links { display: flex; gap: 28px; justify-content: center; margin-bottom: 14px; }
.footer-links a { color: #5a6a7a; font-size: 0.85rem; transition: color 0.2s; }
.footer-links a:hover { color: #dde6f0; }
.footer-copy { color: #3a4a5a; font-size: 0.78rem; }
@media (max-width: 600px) {
  .deals-grid { grid-template-columns: 1fr; padding: 0 4%; }
  .nav-links { gap: 16px; font-size: 0.82rem; }
}
"""
    with open(os.path.join(DEALS_DIR, "deals.css"), "w", encoding="utf-8") as f:
        f.write(css)

    cards_html = ""
    for idx, item in enumerate(offers):
        brand = item.get("brand", "Unknown")
        rate = item.get("rate", "High Profit")
        rank = item.get("rank", idx + 1)
        cat = item.get("category", "Shopping")
        title = item.get("title", f"Best {brand} Deals")
        desc = item.get("description", "")
        angle = item.get("angle", "Save Big")
        link = item.get("affiliate_link", "#")
        emoji = CATEGORY_EMOJI.get(cat, "🛍️")
        grad = BANNER_GRADS[idx % len(BANNER_GRADS)]
        initial = brand[0].upper()

        cards_html += f"""
  <article class="deal-card">
    <div class="card-top" style="--banner-grad:{grad}">
      <div class="card-initial">{initial}</div>
      <span class="card-rank-badge">#{rank}</span>
      <span class="card-cat-badge">{emoji} {cat}</span>
    </div>
    <div class="card-body">
      <div class="card-brand">{brand}</div>
      <span class="card-rate-pill">💰 {rate}</span>
      <p class="card-angle">"{angle}"</p>
      <p class="card-title">{title}</p>
      <p class="card-desc">{desc}</p>
      <a href="{link}" target="_blank" rel="noopener noreferrer" class="btn-deal">
        🛍️ Get This Deal
      </a>
    </div>
  </article>"""

    now_str = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Today's Top Deals — Get Your Deal</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="deals.css" />
</head>
<body>
  <nav class="navbar">
    <a href="../" class="logo">🛍️ Get Your Deal</a>
    <div class="nav-links">
      <a href="../">Home</a>
      <a href="./" class="active">Today's Deals</a>
      <a href="../privacy.html">Privacy</a>
    </div>
  </nav>

  <header class="page-hero">
    <div class="hero-badge">🔄 Auto-updated Daily</div>
    <h1>Today's <span class="grad">Top {len(offers)} Deals</span></h1>
    <p class="sub">Hand-picked affiliate offers on India's top brands — curated by AI every day.</p>
    <p class="ts">Last updated: {now_str}</p>
  </header>

  <main class="deals-grid">
{cards_html}
  </main>

  <footer class="footer">
    <div class="footer-links">
      <a href="../">Home</a>
      <a href="../privacy.html">Privacy Policy</a>
      <a href="../terms.html">Terms of Service</a>
      <a href="mailto:Carrercurve@gmail.com">Contact</a>
    </div>
    <p class="footer-copy">© 2024 Get Your Deal — Affiliate links disclosure: we earn a small commission at no extra cost to you.</p>
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
