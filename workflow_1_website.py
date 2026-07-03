import asyncio
import os
import json
import re
import time
import shutil
import requests
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from playwright.async_api import async_playwright

load_dotenv()

EARNKARO_EMAIL    = os.getenv("EARNKARO_EMAIL")
EARNKARO_PASSWORD = os.getenv("EARNKARO_PASSWORD")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")

# Known brand websites for fallback link generation
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
    "amazon":    "https://www.amazon.in",
    "meesho":    "https://www.meesho.com",
}

FALLBACK_STORES = [
    {"brand": "Myntra",               "rate": "Up to 8.50% Profit",   "website": "https://www.myntra.com",    "category": "Fashion"},
    {"brand": "Ajio",                 "rate": "Up to 10.00% Profit",  "website": "https://www.ajio.com",      "category": "Fashion"},
    {"brand": "Flipkart",             "rate": "Up to 7.00% Profit",   "website": "https://www.flipkart.com",  "category": "Electronics"},
    {"brand": "Mamaearth",            "rate": "Flat 12.00% Profit",   "website": "https://mamaearth.in",      "category": "Beauty"},
    {"brand": "Nykaa",                "rate": "Up to 6.00% Profit",   "website": "https://www.nykaa.com",     "category": "Beauty"},
    {"brand": "Axis Bank Credit Card","rate": "Flat Rs 2,500 Profit", "website": "https://www.axisbank.com",  "category": "Finance"},
    {"brand": "Wow Skin Science",     "rate": "Flat 15.00% Profit",   "website": "https://www.buywow.in",     "category": "Beauty"},
    {"brand": "Plum Goodness",        "rate": "Flat 12.50% Profit",   "website": "https://plumgoodness.com",  "category": "Beauty"},
    {"brand": "Croma",                "rate": "Up to 4.50% Profit",   "website": "https://www.croma.com",     "category": "Electronics"},
    {"brand": "OnePlus",              "rate": "Up to 3.00% Profit",   "website": "https://www.oneplus.in",    "category": "Electronics"},
]

# Brand category emoji mapping
CATEGORY_EMOJI = {
    "Fashion": "👗", "Electronics": "📱", "Beauty": "💄",
    "Finance": "💳", "Shopping": "🛒", "Food": "🍕",
    "Travel": "✈️", "Health": "💊",
}

# ─────────────────────────────────────────────────
# STEP 1 — EarnKaro Login & Scraping via Playwright
# ─────────────────────────────────────────────────

async def login_to_earnkaro(page):
    print("  Logging into EarnKaro...")
    await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
    await asyncio.sleep(5)

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

    for sel in ["#pwd", "input[type='password']", "input[name='password']", "input[placeholder*='password' i]"]:
        try:
            await page.wait_for_selector(sel, timeout=8000)
            await page.fill(sel, EARNKARO_PASSWORD)
            break
        except: continue

    for sel in ["#btnLayoutSignupPass", "button[type='submit']", "button:has-text('Login')", "button:has-text('Sign in')", ".btn-login"]:
        try:
            await page.click(sel, timeout=5000)
            break
        except: continue

    await asyncio.sleep(6)
    print("  Login complete.")

async def extract_stores_from_page(page):
    """Parse the EarnKaro partners page to extract brand + profit rate."""
    cards = []
    try:
        elements = await page.query_selector_all("div, li")
        for el in elements:
            text = await el.inner_text()
            if not text: continue
            text_lower = text.lower()
            if "%" not in text: continue
            if not ("profit" in text_lower or "commission" in text_lower or "earn" in text_lower):
                continue

            img = await el.query_selector("img")
            brand_name = None
            if img:
                alt = await img.get_attribute("alt")
                if alt and 1 < len(alt.strip()) < 40 and not any(x in alt.lower() for x in ["earnkaro", "logo", "banner", "google"]):
                    brand_name = alt.strip()

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not brand_name and lines:
                candidate = lines[0]
                if len(candidate) < 35 and not any(x in candidate.lower() for x in ["profit", "earn", "commission", "off", "rs"]):
                    brand_name = candidate

            profit_rate = None
            for line in lines:
                if "%" in line and ("profit" in line.lower() or "commission" in line.lower() or "earn" in line.lower()):
                    profit_rate = line.strip()
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

    except Exception as e:
        print(f"  Extraction error: {e}")

    seen, unique = set(), []
    for c in cards:
        if c["brand"].lower() not in seen:
            seen.add(c["brand"].lower())
            unique.append(c)
    return unique

async def run_scraper():
    print("=== STEP 1: SCRAPING EARNKARO ===")
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("  Missing credentials — using fallback data.")
        return FALLBACK_STORES

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await login_to_earnkaro(page)
            await page.goto("https://earnkaro.com/our-partners", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            stores = await extract_stores_from_page(page)
            if not stores:
                print("  No stores extracted — using fallback data.")
                stores = FALLBACK_STORES
            else:
                print(f"  Scraped {len(stores)} stores from EarnKaro.")
        except Exception as e:
            print(f"  Scraping failed ({e}) — using fallback data.")
            stores = FALLBACK_STORES
        await browser.close()
    return stores

# ─────────────────────────────────────────────────
# STEP 2 — Gemini AI Content Curation
# ─────────────────────────────────────────────────

def rank_and_curate_with_gemini(stores):
    print("=== STEP 2: CURATING DEALS WITH GEMINI ===")
    if not GEMINI_API_KEY:
        print("  No Gemini API key — using fallback curation.")
        return _fallback_curation(stores)
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""You are an expert Indian affiliate marketer. Here are EarnKaro offers:
{json.dumps(stores[:15], indent=2)}

Pick the TOP 10 offers. Return ONLY a valid JSON array (no markdown) with exactly 10 objects, each having:
- "rank": int (1-10)
- "brand": str
- "rate": str (profit rate)
- "website": str (original URL)
- "category": str (Fashion / Electronics / Beauty / Finance / Shopping)
- "title": str (catchy deal title, max 60 chars)
- "description": str (2 sentences, persuasive)
- "angle": str (3-5 word hook)
"""
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                text = re.sub(r"```json\s*|```", "", resp.text).strip()
                data = json.loads(text)
                print(f"  Gemini returned {len(data)} curated deals.")
                return data
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait = 60 if attempt == 0 else 90
                    print(f"  Rate limit hit — waiting {wait}s (attempt {attempt+1}/3)...")
                    time.sleep(wait)
                else:
                    raise e
        print("  Max retries exceeded — using fallback curation.")
        return _fallback_curation(stores)
    except Exception as e:
        print(f"  Gemini failed: {e} — using fallback curation.")
        return _fallback_curation(stores)

def _fallback_curation(stores):
    result = []
    for i, s in enumerate(stores[:10], 1):
        result.append({
            "rank": i, "brand": s["brand"], "rate": s["rate"],
            "website": s.get("website", ""), "category": s.get("category", "Shopping"),
            "title": f"Best {s['brand']} Deals Today — {s['rate']}",
            "description": f"Shop on {s['brand']} and earn {s['rate']} cashback via EarnKaro affiliate link. Limited time offer — grab it now!",
            "angle": f"Save on {s['brand']}",
        })
    return result

# ─────────────────────────────────────────────────
# STEP 3 — Affiliate Link Generation (EarnKaro API)
# ─────────────────────────────────────────────────

def get_earnkaro_token():
    """Login to EarnKaro via REST API to get a bearer token."""
    try:
        resp = requests.post(
            "https://api.earnkaro.com/api/v2/login",
            json={"email": EARNKARO_EMAIL, "password": EARNKARO_PASSWORD},
            timeout=15
        )
        data = resp.json()
        token = (data.get("data") or {}).get("token") or data.get("token")
        if token:
            print(f"  EarnKaro API login successful.")
            return token
    except Exception as e:
        print(f"  EarnKaro API login failed: {e}")
    return None

def make_affiliate_link_api(token, url):
    """Use EarnKaro REST API to generate an affiliate link."""
    try:
        resp = requests.post(
            "https://api.earnkaro.com/api/v2/get-affiliate-link",
            json={"url": url},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        data = resp.json()
        link = (data.get("data") or {}).get("short_url") or data.get("short_url") or data.get("link")
        return link
    except Exception as e:
        print(f"  Link API error for {url}: {e}")
    return None

def generate_links_for_top_10(top_offers):
    print("=== STEP 3: GENERATING AFFILIATE LINKS ===")
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("  Missing credentials — using placeholder links.")
        for item in top_offers:
            key = item["brand"].lower().replace(" ", "")[:5]
            item["affiliate_link"] = f"https://ekaro.in/enkr_{key}"
        return top_offers

    token = get_earnkaro_token()

    for item in top_offers:
        brand = item["brand"]
        website = item.get("website", "")
        link = None

        if token and website:
            link = make_affiliate_link_api(token, website)

        if link:
            print(f"  ✓ {brand}: {link}")
            item["affiliate_link"] = link
        else:
            # Fallback: use EarnKaro deep-link URL format
            encoded = requests.utils.quote(website, safe="")
            fallback = f"https://ekaro.in/?url={encoded}"
            print(f"  ✗ {brand}: using fallback link")
            item["affiliate_link"] = fallback

    return top_offers

# ─────────────────────────────────────────────────
# STEP 4 — Website Generation (HTML + CSS)
# ─────────────────────────────────────────────────

DEALS_CSS = """
/* ── RESET ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }

body {
  font-family: 'Outfit', sans-serif;
  background: #070b14;
  color: #dde6f0;
  line-height: 1.65;
  min-height: 100vh;
}
a { color: inherit; text-decoration: none; }

/* ── NAVBAR ── */
.navbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  padding: 16px 5%;
  background: rgba(7,11,20,0.85);
  backdrop-filter: blur(18px);
  border-bottom: 1px solid rgba(255,255,255,0.07);
  display: flex; align-items: center; justify-content: space-between;
}
.logo {
  font-size: 1.25rem; font-weight: 800; letter-spacing: -0.3px;
  display: flex; align-items: center; gap: 8px;
  background: linear-gradient(135deg, #e94560, #7c3aed);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.nav-links { display: flex; gap: 28px; font-size: 0.9rem; font-weight: 600; }
.nav-links a { color: #8a9bb0; transition: color 0.2s; }
.nav-links a:hover, .nav-links a.active { color: #fff; }

/* ── PAGE HERO ── */
.page-hero {
  padding: 130px 5% 60px;
  text-align: center;
  background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(233,69,96,0.12), transparent);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(233,69,96,0.12);
  border: 1px solid rgba(233,69,96,0.3);
  color: #e94560; font-size: 0.82rem; font-weight: 700;
  padding: 6px 18px; border-radius: 50px; margin-bottom: 20px;
  letter-spacing: 0.5px;
}
.page-hero h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 800; letter-spacing: -2px;
  color: #fff; margin-bottom: 12px;
}
.grad { background: linear-gradient(135deg, #e94560, #7c3aed); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.page-hero .sub { color: #8a9bb0; font-size: 1rem; max-width: 460px; margin: 0 auto 10px; }
.page-hero .ts  { color: #5a6a7a; font-size: 0.82rem; }

/* ── DEALS GRID ── */
.deals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 24px;
  max-width: 1280px;
  margin: 56px auto 80px;
  padding: 0 5%;
}

/* ── DEAL CARD ── */
.deal-card {
  background: #0e1623;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 20px;
  display: flex; flex-direction: column;
  overflow: hidden;
  transition: transform 0.3s, box-shadow 0.3s;
}
.deal-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 24px 60px rgba(233,69,96,0.15);
  border-color: rgba(233,69,96,0.25);
}

/* Card Top Banner */
.card-top {
  position: relative;
  height: 110px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.card-top::before {
  content: '';
  position: absolute; inset: 0;
  background: var(--banner-grad, linear-gradient(135deg, #1a0a18, #120e22));
  opacity: 0.9;
}
.card-initial {
  position: relative; z-index: 1;
  font-size: 3.5rem; font-weight: 900;
  line-height: 1;
  color: rgba(255,255,255,0.12);
  letter-spacing: -4px;
  user-select: none;
}
.card-rank-badge {
  position: absolute; top: 12px; left: 14px; z-index: 2;
  background: rgba(0,0,0,0.55); backdrop-filter: blur(8px);
  color: #fff; font-size: 0.75rem; font-weight: 700;
  padding: 3px 10px; border-radius: 50px;
  border: 1px solid rgba(255,255,255,0.12);
}
.card-cat-badge {
  position: absolute; top: 12px; right: 14px; z-index: 2;
  font-size: 0.72rem; font-weight: 700;
  padding: 3px 10px; border-radius: 50px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  color: #c5d0de;
}

/* Card Body */
.card-body { padding: 20px 22px 22px; display: flex; flex-direction: column; flex: 1; }
.card-brand { font-size: 1.25rem; font-weight: 800; color: #fff; margin-bottom: 8px; }
.card-rate-pill {
  display: inline-block; align-self: flex-start;
  background: rgba(233,69,96,0.1);
  border: 1px solid rgba(233,69,96,0.3);
  color: #e94560; font-size: 0.8rem; font-weight: 700;
  padding: 4px 14px; border-radius: 50px; margin-bottom: 12px;
}
.card-angle {
  color: #f59e0b; font-style: italic; font-size: 0.88rem;
  font-weight: 600; margin-bottom: 6px;
}
.card-title { color: #c5d0de; font-size: 0.9rem; font-weight: 600; margin-bottom: 6px; }
.card-desc { color: #6b7f94; font-size: 0.83rem; line-height: 1.5; flex: 1; margin-bottom: 18px; }

/* CTA Button */
.btn-deal {
  display: block; text-align: center; width: 100%;
  background: linear-gradient(135deg, #e94560, #7c3aed);
  color: #fff; font-weight: 700; font-size: 0.9rem;
  padding: 11px 18px; border-radius: 12px;
  transition: opacity 0.2s, transform 0.2s;
  box-shadow: 0 4px 20px rgba(233,69,96,0.3);
}
.btn-deal:hover { opacity: 0.88; transform: translateY(-1px); }

/* ── FOOTER ── */
.footer {
  background: #070b14;
  border-top: 1px solid rgba(255,255,255,0.06);
  padding: 36px 5%; text-align: center;
}
.footer-links { display: flex; gap: 28px; justify-content: center; margin-bottom: 14px; }
.footer-links a { color: #5a6a7a; font-size: 0.85rem; transition: color 0.2s; }
.footer-links a:hover { color: #dde6f0; }
.footer-copy { color: #3a4a5a; font-size: 0.78rem; }

/* ── RESPONSIVE ── */
@media (max-width: 600px) {
  .deals-grid { grid-template-columns: 1fr; padding: 0 4%; }
  .nav-links { gap: 16px; font-size: 0.82rem; }
}
"""

# Gradient palette for card banners (cycles through deals)
BANNER_GRADS = [
    "linear-gradient(135deg, #1a0a18, #2d1040)",
    "linear-gradient(135deg, #0a1628, #1a0a3a)",
    "linear-gradient(135deg, #0a1a10, #0d2a1c)",
    "linear-gradient(135deg, #1a1000, #2a1a00)",
    "linear-gradient(135deg, #1a0010, #2a001a)",
    "linear-gradient(135deg, #001428, #001a3a)",
    "linear-gradient(135deg, #1a0808, #2a1212)",
    "linear-gradient(135deg, #081420, #0a1a2a)",
    "linear-gradient(135deg, #100a1a, #1a0f28)",
    "linear-gradient(135deg, #001218, #002020)",
]

def generate_website(offers):
    print("=== STEP 4: GENERATING WEBSITE HTML ===")
    DOCS_DIR   = "docs"
    DEALS_DIR  = os.path.join(DOCS_DIR, "deals")
    TEMPLATE   = "getyourdeal_website"

    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)

    if os.path.exists(TEMPLATE):
        shutil.copytree(TEMPLATE, DOCS_DIR)
    else:
        os.makedirs(DOCS_DIR, exist_ok=True)

    os.makedirs(DEALS_DIR, exist_ok=True)

    # Write CSS
    with open(os.path.join(DEALS_DIR, "deals.css"), "w", encoding="utf-8") as f:
        f.write(DEALS_CSS)

    # Build deal cards
    cards_html = ""
    for idx, item in enumerate(offers):
        brand    = item.get("brand", "Unknown")
        rate     = item.get("rate", "High Profit")
        rank     = item.get("rank", idx + 1)
        cat      = item.get("category", "Shopping")
        title    = item.get("title", f"Best {brand} Deals")
        desc     = item.get("description", "")
        angle    = item.get("angle", "Save Big")
        link     = item.get("affiliate_link", "#")
        emoji    = CATEGORY_EMOJI.get(cat, "🛒")
        grad     = BANNER_GRADS[idx % len(BANNER_GRADS)]
        initial  = brand[0].upper()

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

    # Build full HTML
    now_str = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Today's Top Deals — Get Your Deal</title>
  <meta name="description" content="Hand-picked affiliate deals updated daily on Myntra, Nykaa, Flipkart & more." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
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

    print("  Website HTML and CSS generated successfully!")

# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────

async def main():
    print("Starting Website Pipeline...")
    stores     = await run_scraper()
    top_offers = rank_and_curate_with_gemini(stores)
    top_offers = generate_links_for_top_10(top_offers)   # now sync (REST API)
    generate_website(top_offers)
    print("\n=== PIPELINE COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
