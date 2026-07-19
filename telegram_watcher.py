"""
EarnKaro Telegram -> Affiliate Link -> Website Pipeline
Monitors deal channels 24/7 and publishes deals automatically.
"""
import asyncio
import os
import re
import json
import socket
import urllib.request
import urllib.error

# ── Dynamic DNS-over-HTTPS (DoH) Fallback Hook ──
_original_getaddrinfo = socket.getaddrinfo
_doh_cache = {}

def resolve_via_doh(host):
    if host in _doh_cache:
        return _doh_cache[host]
    
    # Try resolving via Cloudflare DoH using 1.1.1.1 directly to avoid nested lookups
    try:
        url = f"https://1.1.1.1/dns-query?name={host}&type=A"
        req = urllib.request.Request(url, headers={"accept": "application/dns-json", "Host": "cloudflare-dns.com"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
        if ips:
            _doh_cache[host] = ips
            print(f"[DoH Hook] Resolved {host} -> {ips} via Cloudflare")
            return ips
    except Exception:
        pass
        
    # Try Google DoH
    try:
        url = f"https://dns.google/resolve?name={host}&type=A"
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read().decode())
        ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
        if ips:
            _doh_cache[host] = ips
            print(f"[DoH Hook] Resolved {host} -> {ips} via Google")
            return ips
    except Exception:
        pass
        
    return None

def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror as e:
        if host not in ["cloudflare-dns.com", "dns.google", "1.1.1.1", "8.8.8.8"]:
            ips = resolve_via_doh(host)
            if ips:
                results = []
                for ip in ips:
                    p = int(port) if isinstance(port, (int, str)) and str(port).isdigit() else 0
                    results.append((socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (ip, p)))
                return results
        raise e

socket.getaddrinfo = custom_getaddrinfo

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

# Manual environment parsing to ensure .env overrides are fully loaded
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


API_ID   = int(os.getenv("TELEGRAM_API_ID", "0").strip())
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
SESSION  = os.getenv("TELEGRAM_SESSION", "").strip()

# Deal channels to monitor (IDs for private/joined channels)
CHANNEL_IDS = [
    -1001556007364,   # Loot Deals KS
    -1001631375324,   # Loot Deals KS 2.0
    -1001189049996,   # Deals India
    -1001233578753,   # Coupon Discount India
    -1001437398159,   # Loot Deals - Shopping Offers
    -1001183895874,   # Deals Are Here
    -1001280876789,   # LootDeal India
    -1001399724886,   # All India Offers
    -1001153803968,   # Freebies Deals & Coupons
    -1001234567890,   # EarnKaro Official
]

DOCS_DIR   = Path("docs/deals")
IMAGES_DIR = DOCS_DIR / "images"
DEALS_JSON = Path("deals_data.json")
MAX_DEALS  = 200

URL_PATTERN = re.compile(r'https?://[^\s\)\]\|]+')


def is_single_product_url(url: str) -> bool:
    """
    Verify if the URL points to a single product page.
    Returns False if it points to a category, search, or listing page showing multiple products.
    """
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Heuristic search filters
        if any(x in path for x in ["/search", "/category", "/collection", "/catalog", "/brands", "/s/"]):
            if "/p/" not in path: # Ajio products use /p/ but can have search queries in path
                return False
                
        # Myntra: Single products must contain '/buy' or path must be purely a digit ID
        if "myntra.com" in domain:
            clean_path = path.strip("/")
            if not clean_path.isdigit():
                if "/buy" not in path:
                    return False
                
        # Ajio: Single products must contain '/p/'
        elif "ajio.com" in domain:
            if "/p/" not in path:
                return False
                
        # Flipkart: Single products must contain '/p/'
        elif "flipkart.com" in domain:
            if "/p/" not in path:
                return False
                
        # Amazon: Single products must contain '/dp/' or '/gp/product/'
        elif "amazon.in" in domain or "amazon.com" in domain:
            if not any(x in path for x in ["/dp/", "/gp/product/"]):
                return False
    except:
        pass
    return True


# ── Target Category Filter ──
# Only process deals in fashion/lifestyle niches for Pinterest audience
ALLOWED_CATEGORIES = {
    # Fashion clothing & plurals
    "shirt", "shirts", "tshirt", "tshirts", "t-shirt", "t-shirts", "polo", "polos",
    "top", "tops", "blouse", "blouses", "kurta", "kurtas", "kurti", "kurtis",
    "dress", "dresses", "gown", "gowns", "saree", "sarees", "lehenga", "lehengas",
    "jacket", "jackets", "blazer", "blazers", "hoodie", "hoodies",
    "sweatshirt", "sweatshirts", "sweater", "sweaters", "cardigan", "cardigans",
    "coat", "coats", "puffer", "puffers", "tracksuit", "tracksuits",
    "jogger", "joggers", "jeans", "trouser", "trousers", "pants", "shorts",
    "cargo", "cargos", "chinos", "skirt", "skirts", "palazzo", "palazzos",
    "jumpsuit", "jumpsuits", "co-ord", "co-ords", "coord", "coords", "overshirt", "overshirts",
    "flannel", "flannels", "denim", "denims", "linen", "linens", "ethnic", "sherwani", "sherwanis",

    # Shoes / Footwear & plurals
    "shoes", "shoe", "sneaker", "sneakers", "running", "loafer", "loafers",
    "sandal", "sandals", "heels", "heel", "boots", "boot", "slipper", "slippers",
    "mule", "mules", "espadrille", "espadrilles", "flat", "flats",
    "oxford", "oxfords", "derby", "derbies", "brogue", "brogues",
    "trainer", "trainers", "footwear", "footwears", "samba", "jordan", "dunk", "dunks",
    "air max", "air force",

    # Skincare & plurals
    "skincare", "skin care", "serum", "serums", "moisturizer", "moisturizers",
    "moisturiser", "moisturisers", "sunscreen", "sunscreens", "spf", "cleanser", "cleansers",
    "face wash", "facewash", "facewashes", "toner", "toners", "retinol", "niacinamide",
    "vitamin c", "hyaluronic", "cream", "creams", "lotion", "lotions",
    "body wash", "bodywash", "body lotion", "body lotions", "face mask", "face masks",
    "sheet mask", "sheet masks", "exfoliant", "exfoliants", "scrub", "scrubs",

    # Makeup & plurals
    "makeup", "make up", "lipstick", "lipsticks", "lip gloss", "lip glosses",
    "lip balm", "lip balms", "foundation", "foundations", "concealer", "concealers",
    "mascara", "mascaras", "eyeliner", "eyeliners", "eye liner", "eye liners",
    "eyeshadow", "eyeshadows", "eye shadow", "eye shadows", "blush", "blushes",
    "bronzer", "bronzers", "highlighter", "highlighters", "primer", "primers",
    "compact", "compacts", "kajal", "kajals", "kohl", "nail polish", "nail polishes",
    "setting spray", "bb cream", "cc cream",

    # Jewellery & plurals
    "jewellery", "jewelry", "jewelleries", "jewelries", "necklace", "necklaces",
    "pendant", "pendants", "chain", "chains", "bracelet", "bracelets",
    "bangle", "bangles", "ring", "rings", "earring", "earrings", "studs",
    "hoop", "hoops", "anklet", "anklets", "brooch", "choker", "chokers",
    "mangalsutra", "gold", "silver", "diamond", "kundan", "pearl", "pearls", "gemstone",

    # Watches & plurals
    "watch", "watches", "smartwatch", "smartwatches", "smart watch", "smart watches",
    "chronograph", "chronographs", "analog", "digital watch", "digital watches", "wristwatch", "wristwatches",

    # Accessories & plurals
    "sunglasses", "sunglass", "shades", "belt", "belts", "wallet", "wallets",
    "purse", "purses", "clutch", "clutches", "handbag", "handbags", "hand bag", "hand bags",
    "tote", "totes", "sling bag", "sling bags", "crossbody", "backpack", "backpacks",
    "bag", "bags", "scarf", "scarves", "stole", "stoles", "cap", "caps", "hat", "hats",
    "beanie", "beanies", "hair band", "hairband", "hairbands", "scrunchie", "scrunchies",
    "perfume", "perfumes", "fragrance", "fragrances", "deodorant", "deodorants", "cologne", "colognes",

    # Popular Target Niche Brands (allows matching brand-only titles)
    "snitch", "roadster", "nike", "puma", "adidas", "reebok", "levis", "levi's",
    "gant", "calvin klein", "ck", "derma co", "deconstruct", "plum", "mamaearth",
    "nykaa", "cetaphil", "hrx", "wrogn", "red tape", "redtape", "campus", "crocs",
    "lakme", "loreal", "l'oreal", "maybelline", "biotique", "neutrogena", "nivea",
    "colorbar", "faces canada", "sugar cosmetics", "mcaffeine", "wow skin", "plum goodness"
}

# Categories to REJECT (even if they have price keywords)
REJECTED_CATEGORIES = {
    "phone", "mobile", "laptop", "tablet", "tv", "television",
    "refrigerator", "fridge", "washing machine", "ac", "air conditioner",
    "microwave", "oven", "router", "speaker", "headphone", "earphone",
    "earbuds", "charger", "power bank", "cable", "adapter",
    "credit card", "debit card", "loan", "insurance", "mutual fund",
    "sim", "recharge", "broadband", "wifi",
    "grocery", "rice", "dal", "oil", "sugar", "flour", "atta",
    "ghee", "milk", "butter", "cheese", "paneer",
    "medicine", "supplement", "protein", "vitamin",
}

def is_target_category(title: str, desc: str = "") -> bool:
    """
    Check if the deal belongs to our target fashion/lifestyle categories.
    Returns True only if the deal matches our niche.
    """
    # Normalize and convert to lowercase
    combined = f" {title} {desc} ".lower()
    combined_clean = re.sub(r'[^a-z0-9\- ]', ' ', combined)
    words = set(combined_clean.split())

    # First check rejections (whole words or exact phrases)
    for keyword in REJECTED_CATEGORIES:
        if " " in keyword:
            if keyword in combined_clean:
                return False
        else:
            if keyword in words:
                return False

    # Then check if any allowed keyword matches (whole words or exact phrases)
    for keyword in ALLOWED_CATEGORIES:
        if " " in keyword:
            if keyword in combined_clean:
                return True
        else:
            if keyword in words:
                return True

    return False

def is_target_url_category(url: str) -> bool:
    """
    Check retailer URL path for fashion/lifestyle category indicators.
    """
    path = url.lower()

    # Myntra & Ajio are 100% fashion/beauty/lifestyle platforms
    if "myntra.com" in path or "ajio.com" in path:
        return True

    # For Nykaa, Mamaearth, Plum — always fashion/beauty
    if any(x in path for x in ["nykaa.com", "mamaearth.in", "plumgoodness.com",
                                "buywow.in", "lorealparis.co.in"]):
        return True

    return True  # Default allow for unknown retailers — title filter already passed

def is_multi_brand_deal(title: str, url: str) -> bool:
    """
    Detect if the deal title or URL points to a multi-brand listing or deal,
    rather than a single specific product.
    """
    title_lower = title.lower()
    url_lower = url.lower()

    # 1. Check URL parameters for multiple brand filters
    # Ajio: :brand:GANT:brand:CK
    # Myntra: f=Brand:Nike::Brand:Puma
    brand_filters = ["brand:", "brand=", "brand%"]
    for bf in brand_filters:
        if url_lower.count(bf) > 1:
            print(f"  [REJECT] URL contains multiple brand filters ({bf})")
            return True

    # 2. Check if title contains multiple distinct popular brands
    known_brands = [
        "snitch", "roadster", "nike", "puma", "adidas", "reebok", "levis", "levi's",
        "gant", "calvin klein", "ck", "derma co", "deconstruct", "plum", "mamaearth",
        "nykaa", "cetaphil", "hrx", "wrogn", "red tape", "redtape", "campus", "crocs",
        "lakme", "loreal", "maybelline", "biotique", "neutrogena", "nivea"
    ]
    matched_brands = []
    for brand in known_brands:
        if " " in brand:
            if brand in title_lower:
                matched_brands.append(brand)
        else:
            if re.search(r'\b' + re.escape(brand) + r'\b', title_lower):
                matched_brands.append(brand)
                
    if len(matched_brands) > 1:
        print(f"  [REJECT] Title mentions multiple brands: {matched_brands}")
        return True

    # 3. Check for general multi-brand/multi-product keywords in title
    multi_keywords = [
        "multibrand", "multi-brand", "combo of", "pack of",
        "buy 1 get 1", "buy 2 get 1", "bogo", "flat 70% off on everything",
        "super savings store", "clearance sale on brands"
    ]
    if any(kw in title_lower for kw in multi_keywords):
        if "combo" in title_lower or "pack" in title_lower:
            pass
        else:
            print(f"  [REJECT] Title contains multi-brand/event keyword")
            return True

    return False


# ----------------------------------------------------------------
# A: Extract deal info from Telegram message
# ----------------------------------------------------------------
async def extract_from_message(client, msg):
    text  = msg.text or msg.caption or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    urls = URL_PATTERN.findall(text)
    candidate_urls = []
    for u in urls:
        if any(x in u for x in ["t.me", "telegram.me"]):
            continue
        candidate_urls.append(u.rstrip(".,)"))

    if not candidate_urls:
        return None

    title = lines[0][:80] if lines else "Hot Deal Alert"
    desc_raw = " ".join(lines[1:]) if len(lines) > 1 else ""
    
    # Strip any shortener/redirect links from description to prevent leakages
    desc_clean = re.sub(r'https?://[^\s]+', '', desc_raw)
    desc_clean = re.sub(r't\.me/[^\s]+', '', desc_clean)
    desc = re.sub(r'\s+', ' ', desc_clean).strip()[:200]

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
        "candidate_urls": candidate_urls,
        "title": title,
        "desc": desc,
        "image_path": image_path,
        "timestamp": datetime.utcnow().isoformat(),
    }

# ----------------------------------------------------------------
# B: Generate affiliate link via @ekconverter9bot Telegram Bot
# ----------------------------------------------------------------
EKBOT_USERNAME = "ekconverter9bot"
EKBOT_TIMEOUT  = 30  # seconds to wait for bot reply

async def generate_affiliate_link_via_bot(client, product_url: str) -> str | None:
    """
    Send the product URL to @ekconverter9bot on Telegram and wait for the
    converted affiliate link in the bot's reply. This replaces the heavy
    Playwright + cookie + API pipeline entirely.
    """
    try:
        from datetime import datetime, timezone
        start_time = datetime.now(timezone.utc)
        print(f"  [BOT] Sending URL to @{EKBOT_USERNAME}: {product_url[:70]}...")
        
        # Send the URL to the bot
        await client.send_message(EKBOT_USERNAME, product_url)
        
        # Wait for the bot's reply (poll with timeout)
        import time
        start = time.time()
        while time.time() - start < EKBOT_TIMEOUT:
            await asyncio.sleep(2)
            
            # Get last few messages from bot conversation
            messages = await client.get_messages(EKBOT_USERNAME, limit=3)
            for msg in messages:
                if not msg.text:
                    continue
                
                # Ignore messages sent before we initiated the request
                if msg.date < start_time:
                    continue

                text = msg.text
                # Fail fast if bot returns an error message
                if any(x in text.lower() for x in ["could not locate", "error", "failed", "verify if the seller", "invalid"]):
                    print(f"  [BOT] Bot conversion failed: {text.strip()}")
                    return None
                
                # The bot's reply will contain the converted affiliate link
                # Look for known EarnKaro short domains in the reply
                urls = re.findall(r'https?://[^\s]+', text)
                for url in urls:
                    url = url.rstrip(".,)")
                    if any(d in url for d in ["ekaro.in", "fktr.in", "ajiio.in",
                                               "myntr.it", "ajiio.store", "myntr.store",
                                               "bitli.in"]):
                        # Verify this isn't the URL we sent
                        if url != product_url:
                            print(f"  [BOT] Got affiliate link: {url}")
                            return url
        
        print(f"  [BOT] Timeout waiting for @{EKBOT_USERNAME} reply")
        return None
        
    except Exception as e:
        print(f"  [BOT] Error communicating with @{EKBOT_USERNAME}: {e}")
        return None

async def resolve_final_retailer_url(url):
    """
    Trace JavaScript-based redirection for EarnKaro short codes
    (like ajiio.store, fktr.in, ekaro.in) to retrieve the raw retailer link.
    """
    import urllib.parse
    import requests
    
    current_url = url
    # 1. Follow initial HTTP redirects
    try:
        r = requests.get(url, allow_redirects=True, timeout=8,
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, stream=True)
        if r.url:
            current_url = r.url
    except Exception as e:
        print(f"  [EXPAND] Redirect trace failed: {e}")

    # 2. Extract Javascript redirection destination URL if it's an EarnKaro domain
    parsed = urllib.parse.urlparse(current_url)
    netloc = parsed.netloc.lower()
    if any(x in netloc for x in ["ajiio.store", "fktr.in", "ekaro.in", "myntr.it", "myntr.store"]):
        path_parts = [p for p in parsed.path.split("/") if p.strip()]
        if path_parts:
            short_code = path_parts[-1]
            api_url = f"https://{netloc}/api/redirection/generate-redirect-url-in-app-redirection"
            payload = {
                "short_code": short_code,
                "referrer": "",
                "is_in_app": False,
                "is_telegram": False,
                "is_ios": False,
                "is_android": False,
                "is_youtube": False,
                "is_instagram": False,
                "intent": None
            }
            try:
                resp = requests.post(api_url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                if resp.status_code == 200:
                    res_json = resp.json()
                    redirect_url = res_json.get("redirect_url")
                    if redirect_url:
                        if "redirect=" in redirect_url:
                            target = redirect_url.split("redirect=")[1]
                            target = urllib.parse.unquote(target)
                            print(f"  [EXPAND] Resolved Javascript redirect: {target[:70]}...")
                            return target
                        elif "url=" in redirect_url:
                            target = redirect_url.split("url=")[1]
                            target = urllib.parse.unquote(target)
                            print(f"  [EXPAND] Resolved Javascript redirect: {target[:70]}...")
                            return target
                        return redirect_url
            except Exception as e:
                print(f"  [EXPAND] JS API extraction failed: {e}")
                
    return current_url

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
  position: relative; height: 480px; display: flex; align-items: center; justify-content: center; overflow: hidden;
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
    # Get first deal image for OG preview if available
    og_image = "https://harshhaldankar.github.io/Getyourdeal/deals/images/og_banner.jpg"
    if deals and deals[0].get("image_path"):
        og_image = f"https://harshhaldankar.github.io/Getyourdeal/deals/{deals[0]['image_path']}"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Today's Live Deals — Get Your Deal</title>
  <meta name="description" content="Hand-picked live affiliate deals from top Indian deal channels, updated every 15 minutes. Save big on fashion, electronics, beauty and more!"/>
  <!-- ✅ Open Graph tags for rich WhatsApp/Facebook/Twitter previews -->
  <meta property="og:type"        content="website"/>
  <meta property="og:site_name"   content="Get Your Deal"/>
  <meta property="og:title"       content="🔥 Today's Top Deals — Get Your Deal"/>
  <meta property="og:description" content="Live affiliate deals pulled from top deal channels. Updated every 15 mins!"/>
  <meta property="og:url"         content="https://harshhaldankar.github.io/Getyourdeal/deals/"/>
  <meta property="og:image"       content="{og_image}"/>
  <meta property="og:image:width"  content="1200"/>
  <meta property="og:image:height" content="630"/>
  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image"/>
  <meta name="twitter:title"       content="🔥 Today's Top Deals — Get Your Deal"/>
  <meta name="twitter:description" content="Live deals updated every 15 mins. Shop smart, save big!"/>
  <meta name="twitter:image"       content="{og_image}"/>
  <!-- SEO -->
  <meta name="keywords" content="deals, offers, coupons, shopping, india, flipkart, myntra, amazon, ajio, loot deals, discount"/>
  <link rel="canonical" href="https://harshhaldankar.github.io/Getyourdeal/deals/"/>
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
        # Configure git user identity to prevent commit errors in CI environment
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], capture_output=True)

        # 1. Update the local source repository (docs/, deals_data.json, pins_today.json)
        # ✅ BUG FIX: Include pins_today.json so the daily pin count persists across cloud runs
        files_to_add = ["docs/", "deals_data.json"]
        if os.path.exists("pins_today.json"):
            files_to_add.append("pins_today.json")
        subprocess.run(["git", "add"] + files_to_add, check=True, capture_output=True)
        msg = f"Live deal: {deal_title[:60]}"
        result = subprocess.run(["git", "commit", "-m", msg], capture_output=True)
        if result.returncode != 0:
            print("  [PUSH] Nothing to commit.")
            return
        # ✅ BUG FIX: Use pull --rebase before push to prevent race condition conflicts
        subprocess.run(["git", "pull", "--rebase", "origin", "master"], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        print("  [PUSH] Pushed to source repo successfully!")
    except Exception as e:
        print(f"  [WARN] Git push to source repo failed: {e}")

    try:
        # 2. Deploy directly to Getyourdeal public site repository
        import shutil
        deploy_dir = "_website_deploy"
        if os.path.exists(deploy_dir):
            try: shutil.rmtree(deploy_dir)
            except: pass

        print("  [PUSH] Cloning Getyourdeal website repo for deployment...")
        token = os.getenv("WEBSITE_DEPLOY_TOKEN")
        repo = os.getenv("WEBSITE_REPO", "harshhaldankar/Getyourdeal")
        if token:
            clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        else:
            clone_url = f"https://github.com/{repo}.git"

        subprocess.run(["git", "clone", clone_url, deploy_dir], check=True, capture_output=True)

        # Copy everything from docs/ into the cloned repo root
        for item in os.listdir("docs"):
            s = os.path.join("docs", item)
            d = os.path.join(deploy_dir, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    try: shutil.rmtree(d)
                    except: pass
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        # Remove deals.css and deals.html from target .gitignore if present
        gi_path = os.path.join(deploy_dir, ".gitignore")
        if os.path.exists(gi_path):
            with open(gi_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(gi_path, "w", encoding="utf-8") as f:
                for line in lines:
                    if "deals.css" not in line and "deals.html" not in line:
                        f.write(line)

        # Commit and push changes
        subprocess.run(["git", "add", "-A"], cwd=deploy_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "--force", "deals/deals.css"], cwd=deploy_dir, check=True, capture_output=True)
        
        # Check if there are changes before committing
        st = subprocess.run(["git", "status", "--porcelain"], cwd=deploy_dir, capture_output=True, text=True)
        if st.stdout.strip():
            subprocess.run(["git", "commit", "-m", f"🤖 Live watcher update: {deal_title[:60]}"], cwd=deploy_dir, check=True, capture_output=True)
            subprocess.run(["git", "push"], cwd=deploy_dir, check=True, capture_output=True)
            print("  [PUSH] Successfully deployed update to Getyourdeal website!")
        else:
            print("  [PUSH] No website changes to deploy.")

        # Clean up deployment folder
        try: shutil.rmtree(deploy_dir)
        except: pass
    except Exception as e:
        print(f"  [WARN] Git deploy to public website failed: {e}")

# ----------------------------------------------------------------
# MAIN: Telegram watcher
# ----------------------------------------------------------------
async def process_single_message(client, msg):
    text  = msg.text or msg.caption or ""
    print(f"\n{'='*60}")
    print(f"[CHECK] Message ID {msg.id} at {msg.date}")

    deal_info = await extract_from_message(client, msg)
    if not deal_info or not deal_info.get("candidate_urls"):
        print("  [SKIP] No product URL found")
        return False

    # Check if already processed (by title)
    deals = load_deals()
    existing_titles = {d.get("title") for d in deals if d.get("title")}
    if deal_info["title"] in existing_titles:
        print("  [SKIP] Deal already exists on website (by title)")
        return False

    print(f"  [NEW]  {deal_info['title']}")

    # ── Category Filter: Only process fashion/lifestyle deals ──
    if not is_target_category(deal_info["title"], deal_info.get("desc", "")):
        print(f"  [SKIP] Deal '{deal_info['title'][:50]}' is not in target fashion/lifestyle category")
        return False

    # Try each candidate URL until one succeeds
    affiliate_link = None
    final_product_url = None
    
    for candidate_url in deal_info["candidate_urls"]:
        print(f"  [TRY] Testing URL: {candidate_url}")
        
        # 1. Skip Amazon links immediately since EarnKaro doesn't support them
        if "amazon.in" in candidate_url.lower() or "amazon.com" in candidate_url.lower():
            print("  [SKIP] Skipping Amazon link (not supported by EarnKaro)")
            continue

        # Check if this URL is already processed
        existing_urls = {d.get("product_url") for d in deals if d.get("product_url")}
        if candidate_url in existing_urls:
            print("  [SKIP] URL already processed previously")
            continue

        # Expand short URL via HTTP redirects
        product_url = candidate_url
        try:
            import requests as _req
            r = _req.get(product_url, allow_redirects=True, timeout=10,
                        headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            if r.url and r.url != product_url and "chrome-error" not in r.url:
                product_url = r.url
                print(f"  [EXP]  -> {product_url[:70]}")
        except: pass

        # Resolve JS-based redirects (ajiio.store, fktr.in etc.)
        orig_id = extract_product_id(product_url)
        product_url = await resolve_final_retailer_url(product_url)
        print(f"  [EXP]  Final retailer URL: {product_url[:80]}")

        # Verify that the ID did not change (detects out-of-stock category redirects, e.g. redirected to Saree page)
        if orig_id:
            final_id = extract_product_id(product_url)
            if not final_id or final_id != orig_id:
                print(f"  [SKIP] Product ID changed from {orig_id} to {final_id} (Redirected to another product/category)")
                continue

        # Double check if the resolved product url is Amazon (in case the short link redirected to Amazon)
        if "amazon.in" in product_url.lower() or "amazon.com" in product_url.lower():
            print("  [SKIP] Skipping resolved Amazon link")
            continue

        # Reject listing pages that show multiple products
        if not is_single_product_url(product_url):
            print(f"  [REJECT] Skipping category/search listing page to only allow single products: {product_url[:60]}")
            continue

        # Reject multi-brand listing deals/pages
        if is_multi_brand_deal(deal_info["title"], product_url):
            print(f"  [REJECT] Skipping multi-brand listing page or deal: {product_url[:60]}")
            continue

        # Verify URL-based category if available
        if not is_target_url_category(product_url):
            print(f"  [SKIP] URL category not in fashion/lifestyle niche")
            continue

        # Generate affiliate link via @ekconverter9bot
        converted = await generate_affiliate_link_via_bot(client, product_url)
        if converted:
            # Verify it's not the channel owner's link (sanity check on link format)
            earnkaro_domains = ["ekaro.in", "fktr.in", "ajiio.in", "myntr.it",
                                "amzn.to", "nykaa.com", "flipkart.com", "ajio.com"]
            is_valid = any(d in converted for d in earnkaro_domains)
            if is_valid:
                affiliate_link = converted
                final_product_url = product_url
                print(f"  [LINK] Verified affiliate link: {affiliate_link[:60]}")
                break
            else:
                print(f"  [WARN] Converted link '{converted[:50]}' is not a valid EarnKaro link.")
        else:
            print("  [TRY] Bot conversion failed for this URL. Trying next URL in message if available.")

    if not affiliate_link:
        print("  [REJECT] No candidate URLs could be converted to EarnKaro affiliate links for this deal.")
        return False

    deal = {
        "title": deal_info["title"],
        "desc": deal_info["desc"],
        "image_path": deal_info["image_path"],
        "timestamp": deal_info["timestamp"],
        "affiliate_link": affiliate_link,
        "product_url": final_product_url,
        "pinned": False,
    }
    print(f"  [LINK] Affiliate link confirmed: {affiliate_link[:60]}")

    # 1. Ensure product image exists (download fallback if missing)
    if not deal.get("image_path"):
        ts_now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fallback_name = f"fallback_{ts_now}.jpg"
        fallback_disk_path = os.path.join("docs", "deals", "images", fallback_name)
        try:
            from image_utils import fetch_and_save_image
            fetched = fetch_and_save_image(deal["title"], fallback_disk_path, product_url=product_url)
            if fetched and os.path.exists(fetched):
                deal["image_path"] = f"images/{fallback_name}"
        except Exception as e:
            print(f"  [WARN] Image fetcher error: {e}")

    # 2. Bypass card banner generation: use product photo directly for realism.
    print(f"  [CARD] Card banner generation bypassed to use original product photo.")

    # 3. Save database and rebuild website using the card image
    deals = load_deals()
    deals.insert(0, deal)
    deals = deals[:MAX_DEALS]
    save_deals(deals)

    rebuild_website(deals)
    push_to_github(deal["title"])
    print(f"[DONE]  Deal with card banner is LIVE on your website!")

    # 4. Post to Pinterest immediately
    try:
        from pinterest_poster import post_deal_to_pinterest, is_posting_hours
        if is_posting_hours():
            print(f"  [PIN]  Posting to Pinterest...")
            pinned = await post_deal_to_pinterest(deal)
            if pinned:
                print(f"  [PIN]  Posted to Pinterest!")
                # Update pinned status in local database
                deals = load_deals()
                if deals and deals[0]["title"] == deal["title"]:
                    deals[0]["pinned"] = True
                    save_deals(deals)
            else:
                print(f"  [PIN]  Pinterest post skipped/failed")
        else:
            print(f"  [PIN]  Skipped Pinterest (outside posting hours)")
    except Exception as e:
        print(f"  [PIN]  Pinterest error: {e}")

    return True

def extract_product_id(url: str) -> str | None:
    """
    Extract the unique product identifier (numeric ID or Amazon ASIN) from the URL.
    """
    import re
    url_lower = url.lower()
    
    # 1. Amazon ASIN: /dp/ASIN or /gp/product/ASIN
    if "amazon.in" in url_lower or "amazon.com" in url_lower:
        m = re.search(r'/(?:dp|gp/product)/([a-z0-9]{10})', url_lower)
        if m: return m.group(1)
        
    # 2. Myntra Product ID: numeric sequence before /buy or at the end of path
    if "myntra.com" in url_lower:
        m = re.search(r'/(\d{5,12})(?:/buy|$|\?)', url_lower)
        if m: return m.group(1)

    # 3. Ajio Product ID: numeric sequence, e.g. /469607649_blue
    if "ajio.com" in url_lower:
        m = re.search(r'/(\d{8,15})(?:_|$|\?)', url_lower)
        if m: return m.group(1)
        
    # 4. Generic Product ID: any 6+ digit number in path
    m = re.search(r'/(\d{6,15})(?:/|$|\?|\.)', url_lower)
    if m: return m.group(1)
    
    return None

def is_deal_active(product_url: str) -> bool:
    """
    Check if the product is still in stock and available at the retailer.
    Scans the product page HTML for common 'out of stock' or 'sold out' indicators.
    Also verifies that the product URL has not redirected to a different item/category page.
    """
    if not product_url or not product_url.startswith("http"):
        return True # Default safe if no URL

    import requests
    from urllib.parse import urlparse
    
    parsed = urlparse(product_url)
    domain = parsed.netloc.lower()
    orig_id = extract_product_id(product_url)

    try:
        # Browser-like headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        # Load the page (follow redirects)
        r = requests.get(product_url, headers=headers, timeout=10, allow_redirects=True)
        if r.status_code == 404:
            print(f"  [STOCK] Product URL returned 404 (Deal Over): {product_url[:60]}")
            return False
            
        final_url = r.url
        # If the original product ID is missing in the final redirected URL, it means
        # the product was deleted/sold out and redirected to a generic page (e.g. a Saree page)
        if orig_id:
            final_id = extract_product_id(final_url)
            if not final_id or final_id != orig_id:
                print(f"  [STOCK] Product ID changed from {orig_id} to {final_id} (Redirected to another product/category - Deal Over): {product_url[:60]}")
                return False

        html = r.text.lower()

        # Common Out of Stock / Sold Out text markers for Indian e-commerce sites
        out_of_stock_markers = [
            "out of stock",
            "sold out",
            "currently unavailable",
            "item is temporarily unavailable",
            "product is no longer available",
            "not available for purchase",
            "outofstock",
            "product sold out",
        ]
        
        # Ajio specific out of stock indicators
        if "ajio.com" in domain:
            if "out of stock" in html or "out-of-stock" in html or "sold out" in html:
                print(f"  [STOCK] Ajio product is Out of Stock: {product_url[:60]}")
                return False

        # Myntra out-of-stock check via HTML text is DISABLED:
        # Myntra renders stock status via JavaScript — plain HTTP requests always
        # return 200 with an HTML shell that looks like OOS. We rely on 404 and
        # product-ID redirect detection above instead.
        # (HTML text check removed to prevent false positive deal deletions)

        # Flipkart specific indicators
        if "flipkart.com" in domain:
            if "sold out" in html or "currently unavailable" in html or "out of stock" in html:
                print(f"  [STOCK] Flipkart product is Out of Stock: {product_url[:60]}")
                return False

        # General fall-back check for any retail domain
        for marker in out_of_stock_markers:
            if marker in html:
                print(f"  [STOCK] Found stock warning marker '{marker}' on page (Deal Over)")
                return False

        return True

    except Exception as e:
        print(f"  [STOCK WARN] Failed to verify stock status for {domain}: {e}")
        return True # Keep deal if page request fails to avoid false positive deletions

def cleanup_expired_deals():
    """
    Load all active deals, check if they are still in stock,
    and remove the expired ones from deals_data.json.
    Deals younger than 48 hours are always kept (Myntra JS pages cause false OOS via plain HTTP).
    """
    from datetime import timezone
    print("\n" + "=" * 60)
    print("[STOCK CHECK] Verifying stock status of existing deals...")
    print("=" * 60)

    deals = load_deals()
    active_deals = []
    removed_count = 0
    now_utc = datetime.utcnow()

    for deal in deals:
        url   = deal.get("product_url")
        title = deal.get("title", "Unknown Deal")

        # ── Age protection: never auto-remove deals < 48 hours old ──
        # Myntra product pages require JavaScript to render stock status.
        # Plain HTTP requests always return 200 but the HTML lacks stock JSON,
        # causing false positives on every run. Protect young deals to avoid this.
        deal_ts_str = deal.get("timestamp", "")
        deal_age_hours = 999  # default: treat as old if no timestamp
        if deal_ts_str:
            try:
                # Timestamp may be ISO format or datetime string
                deal_dt = datetime.fromisoformat(deal_ts_str.replace("Z", "+00:00").replace("+00:00", ""))
                deal_age_hours = (now_utc - deal_dt).total_seconds() / 3600
            except Exception:
                pass

        if deal_age_hours < 48:
            print(f"  [KEEP] Deal is < 48h old ({deal_age_hours:.1f}h), skipping stock check: {title}")
            active_deals.append(deal)
            continue

        if url:
            is_active = is_deal_active(url)
            if is_active:
                active_deals.append(deal)
            else:
                print(f"  [REMOVED] Expired/Out-of-stock deal deleted: {title}")
                removed_count += 1
        else:
            active_deals.append(deal)

    if removed_count > 0:
        save_deals(active_deals)
        rebuild_website(active_deals)
        print(f"[STOCK CHECK] Completed. Removed {removed_count} expired deals.")
    else:
        print("[STOCK CHECK] Completed. All existing deals are still in stock!")
    print("=" * 60 + "\n")

async def main():
    print("=" * 60, flush=True)
    print("[START] EarnKaro Telegram Curation Runner (One-Shot)", flush=True)
    print(f"[INFO]  Monitoring {len(CHANNEL_IDS)} channels", flush=True)
    print("=" * 60, flush=True)

    session = StringSession(SESSION) if SESSION else "earnkaro_session"
    client  = TelegramClient(session, API_ID, API_HASH)

    await client.connect()
    if not await client.is_user_authorized():
        print("[AUTH] Not authorized - please run telegram_setup.py first")
        return

    me = await client.get_me()
    print(f"[OK]   Logged in to Telegram as: {me.first_name}", flush=True)

    # Clean up expired/out-of-stock deals from website database
    cleanup_expired_deals()

    # Fetch last 15 messages from monitored channels
    processed_count = 0
    for channel_id in CHANNEL_IDS:
        print(f"\n[FETCH] Reading messages from channel: {channel_id}")
        try:
            messages = await client.get_messages(channel_id, limit=15)
            # Process in chronological order (oldest first) so they post in correct sequence
            for msg in reversed(messages):
                success = await process_single_message(client, msg)
                if success:
                    processed_count += 1
                    # Avoid spamming by processing max 5 new deals per run
                    if processed_count >= 5:
                        print("\n[LIMIT] Processed limit of 5 deals. Stopping this run.")
                        break
            if processed_count >= 5:
                break
        except Exception as e:
            print(f"  [WARN] Failed to read channel {channel_id}: {e}")

    # ── Sync Unpinned Deals to Pinterest ──
    print("\n" + "=" * 60)
    print("[SYNC] Checking for unpinned deals to post to Pinterest...")
    print("=" * 60)
    
    from pinterest_poster import post_deal_to_pinterest
    
    deals = load_deals()
    sync_updated = False
    
    for deal in deals:
        if not deal.get("pinned", False):
            print(f"  [SYNC] Attempting to pin: {deal.get('title')}")
            pinned = await post_deal_to_pinterest(deal)
            if pinned:
                deal["pinned"] = True
                sync_updated = True
                print(f"  [SYNC] Successfully pinned: {deal.get('title')}")
                await asyncio.sleep(5)
            else:
                print(f"  [SYNC] Failed/Skipped pinning for: {deal.get('title')}")
                
    if sync_updated:
        save_deals(deals)
        rebuild_website(deals)
        push_to_github("Sync Pinterest board database")
        print("[SYNC] Completed. Database and site updated.")
    else:
        print("[SYNC] Completed. All existing deals are already pinned!")
    print("=" * 60 + "\n")

    print(f"\n[FINISHED] Processed {processed_count} new deals during this run.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
