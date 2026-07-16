"""
EarnKaro Telegram -> Affiliate Link -> Website Pipeline
Monitors deal channels 24/7 and publishes deals automatically.
"""
import asyncio
import os
import re
import json

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Force UTF-8 output to avoid Windows cp1252 issues
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

API_ID   = int(os.getenv("TELEGRAM_API_ID", "0").strip())
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
SESSION  = os.getenv("TELEGRAM_SESSION", "").strip()

# Deal channels to monitor (IDs for private/joined channels)
CHANNEL_IDS = [
    -1001556007364,   # Loot Deals KS
    -1001631375324,   # Loot Deals KS 2.0
]

DOCS_DIR   = Path("docs/deals")
IMAGES_DIR = DOCS_DIR / "images"
DEALS_JSON = Path("deals_data.json")
MAX_DEALS  = 20

URL_PATTERN = re.compile(r'https?://[^\s\)\]\|]+')


# ----------------------------------------------------------------
# A: Extract deal info from Telegram message
# ----------------------------------------------------------------
async def extract_from_message(client, event):
    msg   = event.message
    text  = msg.text or msg.caption or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    urls = URL_PATTERN.findall(text)
    product_url = None
    for u in urls:
        if any(x in u for x in ["t.me", "telegram.me"]):
            continue
        product_url = u.rstrip(".,)")
        break

    if not product_url:
        return None

    title = lines[0][:80] if lines else "Hot Deal Alert"
    desc  = " ".join(lines[1:])[:200] if len(lines) > 1 else ""

    image_path = None
    if msg.photo or (msg.document and "image" in str(getattr(msg.document, "mime_type", ""))):
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        img_file = IMAGES_DIR / f"deal_{ts}.jpg"
        try:
            await client.download_media(msg, file=str(img_file))
            image_path = f"images/deal_{ts}.jpg"
            print(f"  [IMG] Image saved: {image_path}")
        except Exception as e:
            print(f"  [WARN] Image download failed: {e}")

    return {
        "product_url": product_url,
        "title": title,
        "desc": desc,
        "image_path": image_path,
        "timestamp": datetime.utcnow().isoformat(),
    }

# ----------------------------------------------------------------
# B: Generate affiliate link via EarnKaro API + Cookie Session
# ----------------------------------------------------------------
EARNKARO_SESSION_FILE = "earnkaro_session.json"

async def refresh_earnkaro_cookies():
    """Launch Playwright headless to log in and save cookies."""
    from playwright.async_api import async_playwright
    from workflow_1_website import login_to_earnkaro

    EARNKARO_EMAIL    = os.getenv("EARNKARO_EMAIL")
    EARNKARO_PASSWORD = os.getenv("EARNKARO_PASSWORD")
    if not EARNKARO_EMAIL or not EARNKARO_PASSWORD:
        print("  [WARN] EarnKaro credentials missing in .env")
        return None

    print("  [AUTH] Refreshing EarnKaro session cookies via Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await login_to_earnkaro(page)
            cookies = await page.context.cookies()
            Path(EARNKARO_SESSION_FILE).write_text(json.dumps(cookies), encoding="utf-8")
            print(f"  [AUTH] Successfully saved {len(cookies)} EarnKaro session cookies")
            await browser.close()
            return cookies
        except Exception as e:
            print(f"  [AUTH] Playwright login failed: {e}")
            await browser.close()
            return None

async def generate_affiliate_link(product_url):
    """
    Call EarnKaro API directly using saved session cookies.
    Extremely fast, resource-friendly, and bypasses browser popups.
    """
    import requests
    
    # Load or generate cookies
    cookies = None
    if Path(EARNKARO_SESSION_FILE).exists():
        try:
            cookies = json.loads(Path(EARNKARO_SESSION_FILE).read_text(encoding="utf-8"))
        except: pass
    
    if not cookies:
        cookies = await refresh_earnkaro_cookies()
        if not cookies:
            return None

    # Try calling API directly
    async def try_api_call(cookie_list):
        cookie_dict = {c["name"]: c["value"] for c in cookie_list}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://earnkaro.com/create-earn-link",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            resp = requests.post(
                "https://earnkaro.com/pps/user/makeearnlink",
                data={"deal_link": product_url, "platform": "web"},
                cookies=cookie_dict, headers=headers, timeout=12
            )
            result = resp.json()
            if result.get("code") == "success":
                return result.get("shared_link")
        except Exception as e:
            print(f"  [API ERR] {e}")
        return None

    # Try with existing cookies
    shared_link = await try_api_call(cookies)
    if shared_link:
        print(f"  [LINK] Created: {shared_link}")
        return shared_link

    # If failed, cookies might have expired. Refresh once and try again.
    print("  [LINK] Direct API failed. Retrying with fresh session...")
    fresh_cookies = await refresh_earnkaro_cookies()
    if fresh_cookies:
        shared_link = await try_api_call(fresh_cookies)
        if shared_link:
            print(f"  [LINK] Created after refresh: {shared_link}")
            return shared_link

    return None

# ----------------------------------------------------------------
# C: Deals JSON persistence
# ----------------------------------------------------------------
def load_deals():
    if DEALS_JSON.exists():
        return json.loads(DEALS_JSON.read_text(encoding="utf-8"))
    return []

def save_deals(deals):
    DEALS_JSON.write_text(
        json.dumps(deals, indent=2, ensure_ascii=False), encoding="utf-8"
    )

# ----------------------------------------------------------------
# D: Rebuild the website HTML
# ----------------------------------------------------------------
CSS = """
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
  scroll-margin-top: 100px;
}
.deal-card:hover {
  transform: translateY(-6px); box-shadow: 0 24px 60px rgba(233,69,96,0.15); border-color: rgba(233,69,96,0.25);
}
.card-top {
  position: relative; height: 185px; display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.card-top::before {
  content: ''; position: absolute; inset: 0; opacity: 0.9;
  background: var(--banner-grad, linear-gradient(135deg, #1a0a18, #120e22));
}
.card-img {
  width: 100%; height: 100%; object-fit: cover; position: relative; z-index: 1;
}
.card-initial {
  position: relative; z-index: 1; font-size: 4.5rem; font-weight: 900; line-height: 1;
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

def get_store_name(text):
    t = text.lower()
    if "myntra" in t: return "Myntra"
    if "ajio" in t: return "Ajio"
    if "flipkart" in t: return "Flipkart"
    if "amazon" in t: return "Amazon"
    if "nykaa" in t: return "Nykaa"
    if "mamaearth" in t: return "Mamaearth"
    if "plum" in t: return "Plum Goodness"
    if "wow" in t: return "Wow Skin Science"
    if "croma" in t: return "Croma"
    if "oneplus" in t: return "OnePlus"
    if "axis" in t: return "Axis Bank"
    return "Hot Deal"

def get_category(store):
    s = store.lower()
    if s in ["myntra", "ajio"]: return "Fashion"
    if s in ["nykaa", "mamaearth", "wow", "plum"]: return "Beauty"
    if s in ["flipkart", "amazon", "oneplus", "croma"]: return "Electronics"
    if s == "axis": return "Finance"
    return "Shopping"

def extract_price(title):
    import re
    m = re.search(r'(?:at|from|@|rs\.?|inr)?\s*[₹]?\s*(\d[\d,]*)', title, re.IGNORECASE)
    if m: return f"₹{m.group(1).replace(',', '')}"
    return None

def rebuild_website(deals):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "deals.css").write_text(CSS, encoding="utf-8")

    cards_html = ""
    for idx, d in enumerate(deals[:MAX_DEALS]):
        link      = d.get("affiliate_link") or d.get("product_url", "#")
        title     = d.get("title", "Hot Deal").replace("<", "&lt;").replace(">", "&gt;")
        desc      = d.get("desc", "").replace("<", "&lt;").replace(">", "&gt;")
        ts        = d.get("timestamp", "")
        img_path  = d.get("image_path")
        
        # Unique HTML anchor ID
        clean_ts = ts.replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
        deal_anchor_id = f"deal_{clean_ts}"
        
        brand = get_store_name(title)
        cat = get_category(brand)
        emoji = CATEGORY_EMOJI.get(cat, "🛍️")
        grad = BANNER_GRADS[idx % len(BANNER_GRADS)]
        initial = brand[0].upper()
        
        price = extract_price(title)
        rate = f"Price: {price}" if price else "Verified Offer"
        angle = "Lowest Price Alert!" if price else "Limited Time Loot!"

        if img_path and (DOCS_DIR / img_path).exists():
            top_html = f'<img src="{img_path}" alt="{title}" class="card-img" loading="lazy">'
        else:
            top_html = f'<div class="card-initial">{initial}</div>'

        cards_html += f"""
  <article class="deal-card" id="{deal_anchor_id}">
    <div class="card-top" style="--banner-grad:{grad}">
      {top_html}
      <span class="card-rank-badge">#{idx+1}</span>
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
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Today's Live Deals — Get Your Deal</title>
  <meta name="description" content="Live affiliate deals pulled from top deal channels, updated dynamically."/>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="deals.css"/>
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
    <div class="hero-badge">🔄 Live Updates 24/7</div>
    <h1>Today's <span class="grad">Live Deals</span></h1>
    <p class="sub">Affiliate offers fetched automatically from top deal channels.</p>
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
    <p class="footer-copy">© 2026 Get Your Deal — Affiliate linksdisclosure: we earn a small commission at no extra cost to you.</p>
  </footer>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"  [WEB] Website rebuilt with {len(deals[:MAX_DEALS])} deals")

# ----------------------------------------------------------------
# E: Push to GitHub Pages
# ----------------------------------------------------------------
def push_to_github(deal_title):
    try:
        subprocess.run(["git", "add", "docs/", "deals_data.json"], check=True, capture_output=True)
        msg = f"Live deal: {deal_title[:60]}"
        subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        print("  [PUSH] Pushed to GitHub Pages!")
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] Git push failed: {e.stderr.decode() if e.stderr else str(e)}")

# ----------------------------------------------------------------
# MAIN: Telegram watcher
# ----------------------------------------------------------------
async def main():
    print("=" * 60, flush=True)
    print("[START] EarnKaro Telegram Deal Watcher", flush=True)
    print(f"[INFO]  Monitoring {len(CHANNEL_IDS)} channels", flush=True)
    print("=" * 60, flush=True)

    session = StringSession(SESSION) if SESSION else "earnkaro_session"
    client  = TelegramClient(session, API_ID, API_HASH)

    await client.connect()
    if not await client.is_user_authorized():
        print("[AUTH] Not authorized - please run telegram_setup.py first")
        return

    me = await client.get_me()
    print(f"[OK]   Logged in as: {me.first_name}", flush=True)

    @client.on(events.NewMessage(chats=CHANNEL_IDS))
    async def on_new_deal(event):
        print(f"\n{'='*60}")
        print(f"[NEW]  Message at {datetime.utcnow().strftime('%H:%M:%S UTC')}")

        deal_info = await extract_from_message(client, event)
        if not deal_info:
            print("  [SKIP] No product URL found")
            return

        print(f"  [URL]  {deal_info['product_url']}")
        print(f"  [TITLE] {deal_info['title']}")

        # Expand short URL before generating affiliate link
        product_url = deal_info["product_url"]
        try:
            import requests as _req
            r = _req.get(product_url, allow_redirects=True, timeout=10,
                        headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            if r.url and r.url != product_url and "chrome-error" not in r.url:
                product_url = r.url
                print(f"  [EXP]  -> {product_url[:70]}")
        except: pass

        # Generate affiliate link
        affiliate_link = await generate_affiliate_link(product_url)

        deal = {
            **deal_info,
            "affiliate_link": affiliate_link or deal_info["product_url"],
        }

        # ── Ensure product image exists (download fallback if missing) ──
        if not deal.get("image_path"):
            ts_now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            fallback_name = f"fallback_{ts_now}.jpg"
            fallback_disk_path = os.path.join("docs", "deals", "images", fallback_name)
            try:
                from image_utils import fetch_and_save_image
                fetched = fetch_and_save_image(deal["title"], fallback_disk_path)
                if fetched and os.path.exists(fetched):
                    deal["image_path"] = f"images/{fallback_name}"
            except Exception as e:
                print(f"  [WARN] Image fetcher error: {e}")

        deals = load_deals()
        deals.insert(0, deal)
        deals = deals[:MAX_DEALS]
        save_deals(deals)

        rebuild_website(deals)
        push_to_github(deal["title"])
        print(f"[DONE]  Deal is LIVE on your website!")

        # Post to Pinterest with random buffer delay (30-120 min between posts)
        try:
            import random as _rand
            from pinterest_poster import post_deal_to_pinterest, pins_today, MAX_PINS_PER_DAY, is_posting_hours
            if is_posting_hours() and pins_today() < MAX_PINS_PER_DAY:
                delay_min = _rand.randint(30, 120)
                print(f"  [PIN]  Queued for Pinterest in {delay_min} min (buffer)")
                await asyncio.sleep(delay_min * 60)
                pinned = await post_deal_to_pinterest(deal)
                if pinned:
                    print(f"  [PIN]  Posted to Pinterest!")
                else:
                    print(f"  [PIN]  Pinterest post skipped/failed")
            else:
                print(f"  [PIN]  Skipped Pinterest (outside hours or daily limit reached)")
        except Exception as e:
            print(f"  [PIN]  Pinterest error: {e}")

    print("\n[LISTENING] Watching for new deals (Ctrl+C to stop)...\n", flush=True)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
