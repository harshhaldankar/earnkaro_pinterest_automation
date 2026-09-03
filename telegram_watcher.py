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
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "").strip()

# Deal channels to monitor (IDs for private/joined channels, strings for public usernames)
CHANNEL_IDS = [
    -1001480964161,   # EarnKaro (Loot Deals & Offers) / realearnkaro
    "amazinglootsdealsoffers",
    "freekaamaalindia",
    "offerzone_deal",
    "cashkaro_official"
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

import re

def estimate_profit_tier(title: str, desc: str, url: str) -> str:
    """
    Analyzes the deal text and URL to estimate profit margins mathematically.
    Returns: 'Ultra-High', 'High', 'Medium', 'Low', or 'Unknown'.
    If 'Low', the deal yields 0-2% profit and should be rejected.
    """
    combined = f" {title} {desc} {url} ".lower()
    
    # 0% - 2% Profit Blacklist (Mobiles, Groceries, Gift Cards, Gold, etc)
    blacklist = r"\b(smartphone|mobile phone|iphone|galaxy s\d+|galaxy fold|galaxy flip|redmi note|iqoo|motorola razr|oneplus|poco|gift card|gold coin|silver coin|furniture|sofa|bed|grocery|macbook|ipad|airpods|airpod|credit card|debit card|loan|insurance|mutual fund|sim|recharge|broadband|wifi|medicine)\b"
    if re.search(blacklist, combined):
        return "Low"
        
    # >20% VIP Whitelist (Derma Co, Ounce Organics, etc)
    vip_list = r"\b(derma co|ounce organics|neuro|jivisa|adobe|n4n|nippon paint|nroute|indus astro|koparo|the moms co|ageeasy|nutriburst|strch|ramam|brillare|kerala ayurveda|house of koala|neuherbs|mcaffeine|beardo)\b"
    if re.search(vip_list, combined):
        return "Ultra-High"
        
    # 5% - 10% High Profit (Fashion, Beauty, Shoes, Myntra, Ajio)
    high_profit = r"\b(myntra|ajio|nykaa|mamaearth|plumgoodness|buywow|jeans|shirt|t-shirt|shoes|sneakers|watch|dress|kurta|saree|makeup|skincare|perfume|lipstick|beauty|kurti|footwear|heels)\b"
    if re.search(high_profit, combined):
        return "High"
        
    # 3.5% - 5% Medium Profit (Electronics, Home, Kitchen)
    mid_profit = r"\b(kitchen|appliance|refrigerator|washing machine|tv|television|laptop|earbuds|headphones|speaker|monitor|smartwatch|cookware|home decor)\b"
    if re.search(mid_profit, combined):
        return "Medium"
        
    return "Unknown"

def expand_url(url: str) -> str:
    """Follow redirects to find the ultimate destination URL (e.g. for bitli.in)."""
    import requests
    try:
        r = requests.head(url, allow_redirects=True, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 405:
            r = requests.get(url, allow_redirects=True, timeout=5, headers={'User-Agent': 'Mozilla/5.0'}, stream=True)
            r.close()
        return r.url
    except Exception:
        return url

def is_target_url_category(url: str) -> bool:
    """
    Check if the URL belongs to a high-profit EarnKaro partner.
    Supports expanding shorteners to check the final destination.
    """
    import urllib.parse
    expanded_url = expand_url(url).lower()
    unquoted_url = urllib.parse.unquote(expanded_url)
    
    # High-Profit Domains & known shorteners
    allowed = [
        "amazon", "amzn.to", 
        "flipkart", "fktr.in", "fkr.io", "fkrt.it", "fkrt.cc",
        "myntra", "myntr.it",
        "ajio", "ajiio.in", "ajiio.store",
        "nykaa", "mamaearth", "plumgoodness", "buywow", "lorealparis",
        "croma", "oneplus"
    ]
    return any(domain in unquoted_url for domain in allowed)

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
def clean_telegram_text(text: str) -> tuple[str, str]:
    """
    Cleans raw Telegram message text to extract a professional product title and description.
    Removes all URLs, competitor affiliate tags, prices-only lines, and generic buzzwords.
    """
    if not text:
        return "Hot Deal Alert", ""
        
    # 1. Strip all URLs, links, and affiliate tags
    text_clean = re.sub(r'https?://[^\s]+', '', text)
    text_clean = re.sub(r'www\.[^\s]+', '', text_clean)
    text_clean = re.sub(r't\.me/[^\s]+', '', text_clean)
    text_clean = re.sub(r'[?&](?:tag|affid|utm_[a-z]+)=[^&\s]+', '', text_clean)
    
    lines = [l.strip() for l in text_clean.splitlines() if l.strip()]
    if not lines:
        return "Hot Deal Alert", ""
        
    title = ""
    desc_lines = []
    ignore_phrases = {"loot", "deal", "hot deal", "mega loot", "grab", "buy now", "link below", "offer", "sale", "limited stock", "hurry", "deal alert", "loot alert", "loot offer", "price drop", "lowest price", "shop now", "link here", "link"}
    
    for line in lines:
        clean_line = re.sub(r'^[👉🔥⚡💥🚨✨🎉⭐*:\-\s]+|[👉🔥⚡💥🚨✨🎉⭐*:\-\s]+$', '', line).strip()
        clean_line = re.sub(r'^(?:buy now|shop now|link|get it here|shop here)\s*[:\-]?\s*$', '', clean_line, flags=re.IGNORECASE).strip()
        if not clean_line:
            continue
        if re.match(r'^(?:₹|rs\.?|inr|@|at)?\s*\d[\d,]*\s*(?:/-|/|rs|rupees)?$', clean_line, re.IGNORECASE):
            continue
        if clean_line.lower() in ignore_phrases or len(clean_line) < 4:
            continue
        if not title:
            title = clean_line[:95]
        else:
            desc_lines.append(clean_line)
            
    if not title:
        title = lines[0][:95] if lines else "Hot Deal Alert"
        
    desc = " ".join(desc_lines)
    desc = re.sub(r'\s{2,}', ' ', desc).strip()[:300]
    return title, desc

async def extract_from_message(client, msg):
    text = getattr(msg, 'text', '') or getattr(msg, 'caption', '') or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    urls = URL_PATTERN.findall(text)
    candidate_urls = []
    for u in urls:
        if any(x in u for x in ["t.me", "telegram.me"]):
            continue
        candidate_urls.append(u.rstrip(".,)"))

    if not candidate_urls:
        return None

    title, desc = clean_telegram_text(text)

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
        try:
            return json.loads(DEALS_JSON.read_text(encoding="utf-8"))
        except json.decoder.JSONDecodeError as e:
            print(f"  [WARN] deals_data.json is corrupted ({e}). Resetting database.")
            return []
    return []

def save_deals(deals):
    DEALS_JSON.write_text(
        json.dumps(deals, indent=2, ensure_ascii=False), encoding="utf-8"
    )

# ----------------------------------------------------------------
# D: Rebuild the website HTML
# ----------------------------------------------------------------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&family=Space+Grotesk:wght@400;600;700;900&display=swap');

:root {
  --bg: #ffffff;
  --surface: #f8f8f8;
  --border: #e8e8e8;
  --orange: #FF6B00;
  --orange-hover: #e05f00;
  --navy: #1a1a2e;
  --navy-muted: #6b7280;
  --green: #22c55e;
  --green-dark: #16a34a;
  --font-display: 'Space Grotesk', sans-serif;
  --font-body: 'DM Sans', sans-serif;
  --radius: 14px;
  --shadow: 0 2px 12px rgba(0,0,0,0.08);
  --shadow-hover: 0 8px 32px rgba(0,0,0,0.14);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--navy);
  line-height: 1.6;
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; text-decoration: none; }
img { max-width: 100%; display: block; }

/* Navbar */
.navbar {
  position: sticky; top: 0; z-index: 200;
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  padding: 0 5%;
  display: flex; align-items: center; justify-content: space-between;
  height: 62px;
}
.logo {
  font-family: var(--font-display);
  font-size: 1.4rem; font-weight: 900; letter-spacing: -0.5px;
  color: var(--navy); display: flex; align-items: center; gap: 4px;
}
.logo span { color: var(--orange); }
.nav-tag {
  font-family: var(--font-display);
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
  background: #fff3e8; color: var(--orange);
  padding: 4px 10px; border-radius: 20px; letter-spacing: 0.5px;
}

/* Hero Strip */
.page-hero {
  background: linear-gradient(135deg, var(--navy) 0%, #16213e 100%);
  padding: 52px 5% 44px;
  text-align: center;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(255,255,255,0.12);
  color: #fff; border: 1px solid rgba(255,255,255,0.2);
  font-size: 0.78rem; font-weight: 700; letter-spacing: 0.5px;
  padding: 6px 14px; border-radius: 20px; margin-bottom: 16px;
}
.hero-badge .dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
.page-hero h1 {
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 5vw, 3.2rem); font-weight: 900;
  color: #fff; letter-spacing: -1px; line-height: 1.1; margin-bottom: 10px;
}
.page-hero p { color: rgba(255,255,255,0.7); font-size: 1rem; }

/* Category Nav */
.category-nav {
  display: flex; gap: 10px; overflow-x: auto; padding: 14px 5%;
  background: var(--bg); border-bottom: 1px solid var(--border);
  scrollbar-width: none;
}
.category-nav::-webkit-scrollbar { display: none; }
.cat-btn {
  background: var(--surface); border: 1.5px solid var(--border);
  color: var(--navy-muted); font-family: var(--font-display);
  font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px;
  padding: 8px 18px; border-radius: 24px; cursor: pointer; white-space: nowrap;
  transition: all 0.18s; flex-shrink: 0;
}
.cat-btn:hover { border-color: var(--orange); color: var(--orange); }
.cat-btn.active { background: var(--orange); border-color: var(--orange); color: #fff; }

/* Deals Grid — 3-col desktop, 2-col tablet, 1-col mobile */
.deals-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  max-width: 1280px; margin: 32px auto; padding: 0 5% 40px;
}
@media (max-width: 900px) {
  .deals-grid { grid-template-columns: repeat(2, 1fr); gap: 14px; }
}
@media (max-width: 540px) {
  .deals-grid { grid-template-columns: 1fr; gap: 12px; margin: 20px auto; }
}

/* Deal Card */
.deal-card {
  position: relative;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  display: flex; flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: box-shadow 0.22s, transform 0.22s, border-color 0.22s;
  cursor: pointer;
}
.deal-card:hover {
  box-shadow: var(--shadow-hover);
  transform: translateY(-3px);
  border-color: #d0d0d0;
}

/* Image Container */
.card-top {
  position: relative;
  height: 240px;
  background: var(--surface);
  display: flex; align-items: center; justify-content: center;
  padding: 20px; overflow: hidden;
}
.card-img {
  width: 100%; height: 100%; object-fit: contain;
  transition: transform 0.28s;
}
.deal-card:hover .card-img { transform: scale(1.06); }

/* Discount Badge — bold orange pill (top-left) */
.badge-discount {
  position: absolute; top: 12px; left: 12px;
  background: var(--orange); color: #fff;
  font-family: var(--font-display); font-size: 0.78rem; font-weight: 900;
  padding: 5px 11px; border-radius: 20px;
  text-transform: uppercase; letter-spacing: 0.3px;
  box-shadow: 0 2px 8px rgba(255,107,0,0.35);
}

/* Freshness Badge */
.badge-fresh {
  position: absolute; top: 12px; right: 12px;
  background: rgba(255,255,255,0.95);
  color: var(--navy); font-size: 0.72rem; font-weight: 700;
  padding: 4px 9px; border-radius: 20px;
  border: 1px solid var(--border);
  backdrop-filter: blur(4px);
}

/* Card Body */
.card-body { padding: 16px; display: flex; flex-direction: column; flex: 1; gap: 10px; }
.card-store {
  font-family: var(--font-display); font-size: 0.72rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--navy-muted);
}
.card-title {
  font-size: 0.95rem; font-weight: 500; line-height: 1.45; color: var(--navy);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  flex: 1;
}
.price-row { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.deal-price {
  font-family: var(--font-display); font-size: 1.5rem; font-weight: 900;
  color: var(--green); letter-spacing: -0.5px;
}
.original-price { font-size: 0.88rem; color: var(--navy-muted); text-decoration: line-through; }

/* CTA Button — full width orange */
.btn-deal {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%; padding: 13px;
  background: var(--orange); color: #fff;
  font-family: var(--font-display); font-size: 0.9rem; font-weight: 700;
  letter-spacing: 0.3px; text-transform: uppercase;
  border-radius: 10px; border: none;
  transition: background 0.18s, transform 0.12s;
  cursor: pointer;
}
.btn-deal:hover { background: var(--orange-hover); transform: scale(0.98); }
.btn-deal .arrow { transition: transform 0.18s; }
.btn-deal:hover .arrow { transform: translateX(4px); }

/* ── Individual Deal Page ── */
.deal-page { max-width: 900px; margin: 0 auto; padding: 32px 5% 64px; }
.deal-page-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: start; }
@media (max-width: 680px) { .deal-page-grid { grid-template-columns: 1fr; gap: 24px; } }

.deal-image-box {
  background: var(--surface); border: 1.5px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
  position: relative; aspect-ratio: 1/1;
  display: flex; align-items: center; justify-content: center; padding: 28px;
}
.deal-image-box img { object-fit: contain; width: 100%; height: 100%; }
.deal-page-badge {
  position: absolute; top: 14px; left: 14px;
  background: var(--orange); color: #fff;
  font-family: var(--font-display); font-size: 1rem; font-weight: 900;
  padding: 6px 14px; border-radius: 20px;
  box-shadow: 0 2px 8px rgba(255,107,0,0.35);
}

.deal-info { display: flex; flex-direction: column; gap: 18px; }
.deal-info-store {
  font-family: var(--font-display); font-size: 0.78rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--orange);
}
.deal-info-title {
  font-family: var(--font-display); font-size: 1.4rem; font-weight: 900;
  line-height: 1.3; color: var(--navy);
}
.deal-info-desc { font-size: 0.95rem; color: var(--navy-muted); line-height: 1.65; }

.deal-price-block {
  background: var(--surface); border: 1.5px solid var(--border);
  border-radius: 12px; padding: 18px 20px;
  display: flex; flex-direction: column; gap: 6px;
}
.deal-price-label { font-size: 0.8rem; color: var(--navy-muted); font-weight: 600; }
.deal-price-main {
  font-family: var(--font-display); font-size: 2.2rem; font-weight: 900;
  color: var(--green); letter-spacing: -1px;
}
.deal-price-mrp { font-size: 0.9rem; color: var(--navy-muted); text-decoration: line-through; }
.deal-price-save { font-size: 0.85rem; color: var(--green); font-weight: 700; }

.btn-deal-page {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 16px 24px; width: 100%;
  background: var(--orange); color: #fff;
  font-family: var(--font-display); font-size: 1.05rem; font-weight: 900;
  text-transform: uppercase; letter-spacing: 0.5px;
  border-radius: 12px; border: none;
  cursor: pointer; text-decoration: none;
  transition: background 0.18s, transform 0.12s;
  box-shadow: 0 4px 16px rgba(255,107,0,0.35);
}
.btn-deal-page:hover { background: var(--orange-hover); transform: scale(0.98); }

/* Breadcrumb */
.breadcrumb {
  display: flex; align-items: center; gap: 8px;
  padding: 16px 5%; font-size: 0.82rem; color: var(--navy-muted);
  border-bottom: 1px solid var(--border);
}
.breadcrumb a { color: var(--orange); }

/* More Deals Section */
.more-deals-section { padding: 48px 5%; background: var(--surface); margin-top: 40px; }
.more-deals-section h2 {
  font-family: var(--font-display); font-size: 1.4rem; font-weight: 900;
  color: var(--navy); margin-bottom: 24px;
}
.more-deals-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 680px) { .more-deals-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; } }
@media (max-width: 380px) { .more-deals-grid { grid-template-columns: 1fr; } }

/* Footer */
.footer {
  background: var(--navy); color: rgba(255,255,255,0.6);
  padding: 32px 5%; text-align: center;
  font-size: 0.82rem; line-height: 1.8;
}
.footer a { color: var(--orange); }
.footer strong { color: #fff; }
"""

CATEGORY_EMOJI = {
    "Fashion & Bags": "🎒", "Electronics & Tech": "⚡", "Beauty & Health": "✨",
    "Automotive": "🏍️", "Books & Study": "📚", "Finance": "💳",
    "Loot Deals": "🔥", "Fashion": "👗", "Electronics": "📱", "Beauty": "💄", "Shopping": "🛍️"
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

def get_category(store, text=""):
    import re
    t = text.lower()
    # 1. Electronics & Tech / Appliances first!
    if re.search(r'\b(laptop|phone|mobile|earbud|headphone|headset|earphone|speaker|bluetooth|wireless|tv|television|monitor|keyboard|mouse|charger|powerbank|cable|cooler|cpu|gpu|ram|ssd|camera|smartwatch|watch|led|lamp|washing machine|refrigerator|fridge|microwave|oven|mixer|grinder|samsung|apple|redmi|realme|boat|noise|sony)\b', t):
        return "Electronics & Tech"
    # 2. Fashion & Bags
    if re.search(r'\b(bag|backpack|duffel|luggage|suitcase|wallet|belt|shoe|shoes|sneaker|sneakers|sandal|sandals|slipper|slippers|shirt|tshirt|hoodie|jacket|pant|pants|trouser|trousers|jeans|saree|kurta|lehenga|dress|bra|clovia|gear|aristocrat|skybags|safari|puma|adidas|nike|roadster|myntra|ajio)\b', t):
        return "Fashion & Bags"
    # 3. Beauty & Health / Nutrition
    if re.search(r'\b(shampoo|conditioner|cleanser|serum|moisturizer|moisturiser|sunscreen|spf|soap|facewash|wash|perfume|deodorant|cream|lotion|lipstick|makeup|protein|creatine|whey|avvatar|vitamin|supplement|naturali|nykaa|mamaearth|plum|wow)\b', t):
        return "Beauty & Health"
    # 4. Automotive
    if re.search(r'\b(helmet|riding|bike|car|motorcycle|scooter|tyre|tire|ranger|vega|studds)\b', t):
        return "Automotive"
    # 5. Books & Study
    if re.search(r'\b(book|books|novel|pen|pencil|stationery)\b', t):
        return "Books & Study"

    # 6. Fall back to store name
    s = store.lower()
    if s in ["myntra", "ajio"]: return "Fashion & Bags"
    if s in ["nykaa", "mamaearth", "wow", "plum"]: return "Beauty & Health"
    if s in ["oneplus", "croma"]: return "Electronics & Tech"
    if s == "axis": return "Finance"
    return "Loot Deals"

def extract_price(title):
    import re
    t = title.replace('â‚¹', '₹').replace('Ã¢â€šÂ¹', '₹').replace('Rs.', '₹').replace('Rs ', '₹ ').replace('INR ', '₹ ')
    # 1. Look for explicit price indicators with word boundaries around keywords
    m = re.search(r'(?:₹|rs\.?|inr|\bat\b|\bfrom\b|\bunder\b|@|\bprice:?\b|\bonly\b|\bmrp\b|\bcost\b|\bnow\b)\s*[₹]?\s*(\d[\d,]*)', t, re.IGNORECASE)
    if m:
        val = m.group(1).replace(',', '')
        if val.isdigit() and int(val) >= 20: return f"₹{val}"
    # 2. Look for trailing price indicators like '/-' or 'rs'
    m2 = re.search(r'(\d[\d,]*)\s*(?:/-|/|\brupees\b|\brs\b|\binr\b|\bonly\b)', t, re.IGNORECASE)
    if m2:
        val = m2.group(1).replace(',', '')
        if val.isdigit() and int(val) >= 20: return f"₹{val}"
    return None

# ── Helper: Freshness Badge ──
def _freshness_badge(timestamp_str):
    """Return a freshness badge HTML string based on hours since posting, or '' if stale."""
    try:
        posted = datetime.fromisoformat(timestamp_str)
        hours = (datetime.utcnow() - posted).total_seconds() / 3600
        if hours < 1:
            return '<span class="badge-fresh">🔥 Just Posted</span>'
        elif hours < 6:
            h = int(hours)
            return f'<span class="badge-fresh">⚡ {h}h ago</span>'
        elif hours < 24:
            return '<span class="badge-fresh">📦 Today</span>'
    except Exception:
        pass
    return ""

# ── Helper: Affiliate link for a deal ──
def _deal_link(d, utm_medium="deal_card"):
    """Build the outbound link from a deal dict, with UTM params."""
    raw = d.get("affiliate_link") or d.get("product_url", "#")
    if not raw or raw == "#":
        return "#"
    sep = "&" if "?" in raw else "?"
    return f"{raw}{sep}utm_source=website&utm_medium={utm_medium}&utm_campaign=getyourdeal"

# ── Individual Deal Page writer ──
_GA4_PLACEHOLDER = "<!-- GA4_PLACEHOLDER -->"

def _write_deal_page(d, deal_anchor_id, more_deals):
    """Write an individual deal page matching Dribbble Shot 25042708."""
    import dribbble_template
    dribbble_template.write_single_deal_page(d, deal_anchor_id, more_deals)

def rebuild_website(deals):
    """Rebuild the website with Dribbble Shot 25042708 design."""
    import dribbble_template
    dribbble_template.rebuild_dribbble_website(deals)


# ----------------------------------------------------------------
# E: Push to GitHub Pages
# ----------------------------------------------------------------
def push_to_github(deal_title):
    try:
        # Generate the latest analytics dashboard before pushing
        try:
            from analytics import generate_dashboard
            generate_dashboard()
        except Exception as e:
            print(f"  [WARN] Dashboard generation failed: {e}")

        # Configure git user identity to prevent commit errors in CI environment
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], capture_output=True)

        # 1. Update the local source repository (docs/, deals_data.json, pins_today.json, analytics.json)
        # ✅ BUG FIX: Include pins_today.json so the daily pin count persists across cloud runs
        files_to_add = ["docs/", "deals_data.json"]
        if os.path.exists("pins_today.json"):
            files_to_add.append("pins_today.json")
        if os.path.exists("analytics.json"):
            files_to_add.append("analytics.json")
            
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
            import stat
            def _force_remove(func, path, exc_info):
                """onerror handler: remove read-only attribute then retry on Windows"""
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            try:
                shutil.rmtree(deploy_dir, onerror=_force_remove)
            except Exception as rm_err:
                print(f"  [WARN] Could not clean old deploy dir: {rm_err}")

        token = os.getenv("WEBSITE_DEPLOY_TOKEN")
        if not token:
            print("  [PUSH] WEBSITE_DEPLOY_TOKEN not set; CI workflow Step 3 will handle deployment.")
            return
        repo = os.getenv("WEBSITE_REPO", "harshhaldankar/Getyourdeal")
        clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"

        print("  [PUSH] Cloning Getyourdeal website repo for deployment...")
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

        # Remove deals from target .gitignore if present
        gi_path = os.path.join(deploy_dir, ".gitignore")
        if os.path.exists(gi_path):
            with open(gi_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(gi_path, "w", encoding="utf-8") as f:
                for line in lines:
                    if "deals" not in line:
                        f.write(line)

        # Commit and push changes
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=deploy_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=deploy_dir, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=deploy_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "--force", "deals/deals.css", "deals/index.html"], cwd=deploy_dir, check=True, capture_output=True)
        
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

def get_clean_url(url: str) -> str:
    """Extracts the raw un-monetized URL to send to EarnKaro bot."""
    import urllib.parse
    expanded = expand_url(url)
    parsed = urllib.parse.urlparse(expanded)
    qs = urllib.parse.parse_qs(parsed.query)

    # Extract destination from 'dl' parameter (used by linkredirect.in / bitli.in)
    if 'dl' in qs:
        return qs['dl'][0]

    # For Flipkart affiliate links, strip out existing affiliate parameters just to be safe
    if 'flipkart.com' in parsed.netloc:
        qs_clean = {k: v for k, v in qs.items() if not k.lower().startswith('aff')}
        clean_query = urllib.parse.urlencode(qs_clean, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=clean_query))

    return expanded

EARNKARO_USER_ID = "5382823"

def resolve_tracked_affiliate_link(short_url: str) -> str:
    """
    Resolves fktr.in / ajiio.in EarnKaro short links into a direct deep link
    that bypasses the linkredirect.in intermediate splash page, while preserving
    EarnKaro commission tracking (affExtParam2=EARNKARO_USER_ID).

    This fixes the pipeline where:
      fktr.in → linkredirect.in splash page (JS-only redirect, breaks in-app browsers)
      → Flipkart web (attribution may be lost on app switch)

    After this fix:
      → dl.flipkart.com/?affid=growthte&affExtParam2=5382823  (tracked deep link, opens app on mobile)
    """
    import urllib.parse

    try:
        expanded = expand_url(short_url)
        parsed = urllib.parse.urlparse(expanded)
        qs = urllib.parse.parse_qs(parsed.query)

        # linkredirect.in has the deep link in the 'dl' query param
        # and the EarnKaro user ID in the 'id' query param
        if 'dl' in qs:
            dl_url = qs['dl'][0]
            earnkaro_id = qs.get('id', [EARNKARO_USER_ID])[0]

            # Re-attach EarnKaro tracking to the deep link
            dl_parsed = urllib.parse.urlparse(dl_url)
            dl_qs = urllib.parse.parse_qs(dl_parsed.query)

            # Remove any existing competitor aff params and re-inject ours
            dl_qs = {k: v for k, v in dl_qs.items() if not k.lower().startswith('aff')}
            dl_qs['affid'] = ['growthte']
            dl_qs['affExtParam2'] = [earnkaro_id]

            new_query = urllib.parse.urlencode(dl_qs, doseq=True)
            direct_link = urllib.parse.urlunparse(dl_parsed._replace(query=new_query))
            print(f"  [LINK] Resolved deep link (bypasses splash page): {direct_link[:80]}")
            return direct_link

    except Exception as e:
        print(f"  [WARN] Could not resolve tracked deep link for {short_url}: {e}")

    # Fallback to original short link
    return short_url

def generate_amazon_affiliate_link(url: str) -> str:
    """
    Takes an Amazon URL and appends the user's AMAZON_AFFILIATE_TAG.
    Removes any existing competitor tags first.
    """
    import urllib.parse
    
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    
    # ALWAYS remove existing competitor tags
    if 'tag' in qs:
        del qs['tag']
        
    if not AMAZON_AFFILIATE_TAG:
        print("  [WARN] AMAZON_AFFILIATE_TAG is missing from .env. Returning clean (non-affiliate) link.")
    else:
        # Inject our tag
        qs['tag'] = [AMAZON_AFFILIATE_TAG]
        
    clean_query = urllib.parse.urlencode(qs, doseq=True)
    web_url = urllib.parse.urlunparse(parsed._replace(query=clean_query))

    # Extract the ASIN from the URL path for the smart redirect page
    # Amazon path format: /dp/ASIN or /gp/product/ASIN
    import re
    asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', parsed.path)
    if asin_match:
        asin = asin_match.group(1)
        # Route through our GitHub Pages smart redirect page
        # This tries amzn:// URI scheme (opens Amazon App) and falls back to web
        go_url = f"https://harshhaldankar.github.io/Getyourdeal/go/?asin={asin}"
        return go_url

    # No ASIN found (non-standard URL), return direct web link
    return web_url

# ----------------------------------------------------------------
# MAIN: Telegram watcher
# ----------------------------------------------------------------
async def process_single_message(client, msg):
    from analytics import log_deal
    text = getattr(msg, 'text', '') or getattr(msg, 'caption', '') or ""
    print(f"\n{'='*60}")
    print(f"[CHECK] Message ID {msg.id} at {msg.date}")

    deal_info = await extract_from_message(client, msg)
    if not deal_info or not deal_info.get("candidate_urls"):
        print("  [SKIP] No product URL found")
        log_deal("Unknown", "SKIPPED", "No product URL found")
        return False

    # Check if already processed (by title)
    deals = load_deals()
    existing_titles = {d.get("title") for d in deals if d.get("title")}
    if deal_info["title"] in existing_titles:
        print("  [SKIP] Deal already exists on website (by title)")
        log_deal(deal_info['title'], "SKIPPED", "Already exists on website")
        return False

    print(f"  [NEW]  {deal_info['title']}")

    # ── Category Filter: Only process fashion/lifestyle deals ──
    # Bypass category filter if URL belongs to a trusted fashion/beauty store
    is_trusted_store = False
    for url in deal_info["candidate_urls"]:
        url_lower = url.lower()
        if any(domain in url_lower for domain in ["myntra.com", "ajio.com", "nykaa.com", "mamaearth.in", 
                                                  "plumgoodness.com", "buywow.in", "sugarcosmetics.com", 
                                                  "lakmeindia.com", "thedermaco.com", "zivame.com", 
                                                  "clovia.com", "snitch.co.in", "westside.com"]):
            is_trusted_store = True
            break

    # Profitability Engine filtering
    profit_tier = estimate_profit_tier(deal_info["title"], deal_info.get("desc", ""), "\n".join(deal_info["candidate_urls"]))
    deal_info["profit_tier"] = profit_tier
    
    # Extract numerical price and discount
    price_str = extract_price(deal_info["title"])
    price_val = int(price_str.replace("₹", "").replace(",", "")) if price_str else 0
    
    import re
    disc_match = re.search(r'(\d+)\s*%', deal_info["title"] + " " + deal_info.get("desc", ""))
    discount_val = int(disc_match.group(1)) if disc_match else 0
    
    if discount_val == 0:
        # try to extract price and MRP from text using patterns like 'Rs.XXX' or '₹XXX'
        mrp_m = re.search(r'(?:mrp|worth)\s*(?::|-|is)?\s*(?:rs\.?|₹)?\s*(\d[\d,]*)', deal_info["title"] + " " + deal_info.get("desc", ""), re.IGNORECASE)
        if mrp_m and price_val > 0:
            mrp_val = int(mrp_m.group(1).replace(",", ""))
            if mrp_val > price_val:
                discount_val = int(((mrp_val - price_val) / mrp_val) * 100)
    
    if discount_val < 20 or (price_val > 5000 and discount_val < 30):
        print(f"  [SKIP] Rejected Deal '{deal_info['title'][:50]}' - Reason: Discount Filter (Price: ₹{price_val}, Discount: {discount_val}%)")
        from analytics import log_deal
        log_deal(deal_info['title'], "SKIPPED", "Discount Filter", profit_tier)
        return False

    # Try each candidate URL until one succeeds
    affiliate_link = None
    final_product_url = None
    
    for candidate_url in deal_info["candidate_urls"]:
        print(f"  [TRY] Testing URL: {candidate_url}")
        
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

        # Get the clean, un-monetized URL to send to the bot
        clean_url = get_clean_url(product_url)
        print(f"  [CLEAN] Unmasked URL to send to bot: {clean_url[:80]}...")
        
        # Check against global deduplication index (Pipeline 1 vs Pipeline 2)
        try:
            from pipeline2.dedup_engine import is_duplicate
            if is_duplicate(clean_url):
                print(f"  [DEDUP] Skipping deal! URL was already posted by a pipeline: {clean_url[:60]}")
                continue
        except ImportError:
            pass

        # Intercept Amazon links to generate locally (bypass EarnKaro bot)
        is_amazon = "amazon.in" in clean_url.lower() or "amazon.com" in clean_url.lower()
        if is_amazon:
            converted = generate_amazon_affiliate_link(clean_url)
            print(f"  [AMAZON] Generated local affiliate link: {converted[:60]}...")
        else:
            # Generate affiliate link via @ekconverter9bot
            import asyncio
            for attempt in range(3):
                converted = await generate_affiliate_link_via_bot(client, clean_url)
                if converted:
                    break
                print(f"  [TRY] Bot conversion failed on attempt {attempt+1}. Retrying in 10s...")
                await asyncio.sleep(10)
            
        if converted:
            # Verify it's not the channel owner's link (sanity check on link format)
            earnkaro_domains = ["ekaro.in", "fktr.in", "ajiio.in", "myntr.it",
                                "amzn.to", "nykaa.com", "flipkart.com", "ajio.com", "amazon.in", "amazon.com"]
            is_valid = any(d in converted.lower() for d in earnkaro_domains)
            if is_valid:
                # If it's an EarnKaro short link, resolve it to a direct deep link
                # This bypasses the linkredirect.in splash page that breaks in-app browsers
                ek_short_domains = ["fktr.in", "ajiio.in", "myntr.it", "ekaro.in"]
                if any(d in converted.lower() for d in ek_short_domains):
                    resolved = resolve_tracked_affiliate_link(converted)
                    affiliate_link = resolved if resolved else converted
                else:
                    affiliate_link = converted
                final_product_url = product_url
                print(f"  [LINK] Verified affiliate link: {affiliate_link[:60]}")
                break
            else:
                print(f"  [WARN] Converted link '{converted[:50]}' is not a valid EarnKaro/Amazon link.")
        else:
            print("  [TRY] Bot conversion failed for this URL. Trying next URL in message if available.")

    if not affiliate_link:
        print("  [WARN] No candidate URLs could be converted to EarnKaro affiliate links for this deal.")
        log_deal(deal_info['title'], "LIVE_NO_AFFILIATE", "EarnKaro bot conversion failed")
        affiliate_link = final_product_url

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
    has_valid_image = True
    if not deal.get("image_path"):
        ts_now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fallback_name = f"fallback_{ts_now}.jpg"
        fallback_disk_path = os.path.join("docs", "deals", "images", fallback_name)
        try:
            from image_utils import fetch_and_save_image
            fetched = fetch_and_save_image(deal["title"], fallback_disk_path, product_url=final_product_url, price_val=price_str)
            if fetched and os.path.exists(fetched):
                deal["image_path"] = f"images/{fallback_name}"
            else:
                print(f"  [PIN GATING] No valid high-quality product image found for '{deal['title']}'. Gating deal.")
                deal["image_path"] = ""
                deal["pinned"] = True
                has_valid_image = False
        except Exception as e:
            print(f"  [WARN] Image fetcher error: {e}")
            deal["image_path"] = ""
            deal["pinned"] = True
            has_valid_image = False
    else:
        # Verify that Telegram message image downloaded successfully
        local_img = os.path.join("docs", "deals", deal["image_path"])
        if not os.path.exists(local_img):
            print(f"  [WARN] Telegram image downloaded path does not exist on disk: {local_img}")
            deal["image_path"] = ""
            deal["pinned"] = True
            has_valid_image = False

    if not has_valid_image:
        print("  [REJECT] Deal has no valid image. Skipping entirely.")
        log_deal(deal['title'], "SKIPPED", "No Real Photo (Image Fetch/Validation Failed)")
        return False

    # 2. Save database and rebuild website using the card image
    deals = load_deals()
    deals.insert(0, deal)
    deals = deals[:MAX_DEALS]
    save_deals(deals)

    rebuild_website(deals)
    push_to_github(deal["title"])
    print(f"[DONE]  Deal with card banner is LIVE on your website!")

    # 4. Generate Reel and add to RSS for Make.com distribution
    try:
        from pipeline2.reel_generator import create_reel
        from pipeline2.rss_generator import add_deal_to_rss
        import shutil
        
        # In P1, deal["image_path"] is relative to docs folder (e.g. "images/filename.jpg")
        local_img = os.path.join("docs", "deals", deal["image_path"]) if not deal["image_path"].startswith("deals") else os.path.join("docs", deal["image_path"])
        if not os.path.exists(local_img):
            local_img = os.path.join("docs", deal["image_path"])
            
        reel_path = create_reel(
            local_img,
            str(deal["title"]),
            str(deal_info.get("price", "")),
            str(deal_info.get("mrp", "")),
            str(deal_info.get("discount", ""))
        )
        
        if reel_path and os.path.exists(reel_path):
            website_video_name = f"reel_p1_{os.path.basename(reel_path)}"
            website_video_path = os.path.join("docs", "deals", "videos", website_video_name)
            os.makedirs(os.path.dirname(website_video_path), exist_ok=True)
            shutil.copy(reel_path, website_video_path)
            reel_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/videos/{website_video_name}"
            
            website_img_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{deal['image_path']}"
            
            clean_ts = deal["timestamp"].replace("-", "").replace(":", "").replace(".", "").replace("T", "_")
            deal_anchor_id = f"deal_{clean_ts}"
            website_deal_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/index.html#{deal_anchor_id}"
            
            add_deal_to_rss(
                title=deal["title"],
                website_url=website_deal_url,
                video_url=reel_url,
                description=deal["desc"],
                image_url=website_img_url,
                affiliate_link=deal.get("affiliate_link", "")
            )
            print(f"  [RSS] Added P1 deal to RSS with AI Reel!")
            log_deal(deal['title'], "POSTED_ALL", "Added to Website & RSS", profit_tier=deal_info.get('profit_tier', 'Unknown'))
        else:
            print(f"  [RSS] Reel generation failed — skipping RSS entry (no video for Make.com)")
            log_deal(deal['title'], "WEBSITE_ONLY", "No reel generated — skipped RSS", profit_tier=deal_info.get('profit_tier', 'Unknown'))
            
    except Exception as e:
        print(f"  [RSS] Error adding to RSS: {e}")
        log_deal(deal['title'], "WEBSITE_ONLY", f"RSS error: {e}", profit_tier=deal_info.get('profit_tier', 'Unknown'))
        
    # Register in global dedup index
    try:
        from pipeline2.dedup_engine import register_posted_deal
        register_posted_deal(final_product_url, pipeline=1)
    except ImportError:
        pass

    return has_valid_image

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

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("[AUTH] Not authorized - please run telegram_setup.py first")
            return

        me = await client.get_me()
        print(f"[OK]   Logged in to Telegram as: {me.first_name}", flush=True)
    except Exception as e:
        error_msg = str(e)
        if "AuthKeyDuplicatedError" in error_msg or "authorization key" in error_msg.lower():
            print("[FATAL] Telegram session is being used from multiple IPs simultaneously.", flush=True)
            print("  This commonly happens in CI/CD when the same session secret is reused across runs.", flush=True)
            print("  Fix: Generate a fresh session via `python telegram_setup.py` and update TELEGRAM_SESSION secret.", flush=True)
        else:
            print(f"[FATAL] Telegram connection failed: {e}", flush=True)
        return

    # Clean up expired/out-of-stock deals from website database
    cleanup_expired_deals()

    # Fetch last 80 messages from monitored channels to ensure we scan deep enough
    processed_count = 0
    for channel_id in CHANNEL_IDS:
        print(f"\n[FETCH] Reading messages from channel: {channel_id}")
        try:
            messages = await client.get_messages(channel_id, limit=80)
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
            if not deal.get("image_path"):
                print(f"  [SYNC] Skipped pinning '{deal.get('title')}' — no valid image path.")
                deal["pinned"] = True
                sync_updated = True
                continue
                
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
        rebuild_website(deals)
        print("[SYNC] Completed. All existing deals are already pinned. Rebuilt website with active deals.")
    print("=" * 60 + "\n")

    print(f"\n[FINISHED] Processed {processed_count} new deals during this run.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
