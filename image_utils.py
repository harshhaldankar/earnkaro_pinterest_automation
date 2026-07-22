"""
image_utils.py  High-quality product image fetcher.

Priority chain for every deal:
  1. Scrape actual product photo from retailer page (og:image)  gives the REAL product image
  2. Match a curated high-converting lifestyle photo by keyword (60+ categories)
  3. Official brand logo via Clearbit API
  4. Safe generic shopping fallback photo
"""
import os
import re
import requests
from urllib.parse import urlparse
from PIL import Image

# 
# 1. Retailer OG Image Scraper
# 

# Browser-like headers that work on most Indian e-commerce sites
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _extract_og_image(html: str) -> str | None:
    """Extract og:image or twitter:image URL from HTML."""
    patterns = [
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
        r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']twitter:image["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            if url.startswith("http") and len(url) > 10:
                return url
    return None


def _amazon_image_from_asin(url: str) -> str | None:
    """
    Amazon blocks og:image scraping. Instead, extract the ASIN from the URL
    and hit the official Amazon CDN which is publicly accessible.
    """
    # Pattern: /dp/ASIN or /gp/product/ASIN
    m = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
    if not m:
        return None
    asin = m.group(1)
    # Amazon's product image endpoint  works without auth
    api_url = f"https://www.amazon.in/dp/{asin}"
    try:
        r = requests.get(api_url, headers=_HEADERS, timeout=10)
        if r.status_code == 200:
            # Look for the main product image in landing-image or imgTagWrapper
            patterns = [
                r'"hiRes":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"',
                r'"large":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"',
                r'id="landingImage"[^>]+src="([^"]+)"',
                r'id="imgTagWrapperId"[^>]+.*?src="([^"]+)"',
            ]
            for pat in patterns:
                im = re.search(pat, r.text, re.DOTALL)
                if im:
                    img_url = im.group(1).strip()
                    if img_url.startswith("http"):
                        return img_url
    except Exception as e:
        print(f"  [IMG] Amazon ASIN scrape failed: {e}")
    return None


def _flipkart_image(url: str) -> str | None:
    """Flipkart has og:image that works with simple requests."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        if r.status_code == 200:
            img = _extract_og_image(r.text)
            if img and "rukminim" in img:  # Flipkart CDN domain
                # Upgrade to higher resolution
                img = re.sub(r'\{resolution\}', '832', img)
                return img
            if img:
                return img
    except Exception as e:
        print(f"  [IMG] Flipkart scrape failed: {e}")
    return None


def _scrape_with_playwright(product_url: str) -> str | None:
    """
    Generic stealth Playwright image scraper — works for any JS-rendered site
    (Ajio, Myntra, H&M, etc.) when plain requests-based scraping fails.

    Strategy:
      1. Launch Chromium with stealth flags (hides webdriver fingerprint)
      2. Wait for full JS render (networkidle)
      3. Return og:image meta if valid
      4. Otherwise pick the largest img on the page by naturalWidth * naturalHeight
    """
    import subprocess, sys, tempfile, os

    # Build the subprocess script as a plain string (no f-string tricks inside)
    url_repr = repr(product_url)
    lines = [
        "import sys, time",
        "from playwright.sync_api import sync_playwright",
        f"product_url = {url_repr}",
        "try:",
        "    with sync_playwright() as p:",
        "        browser = p.chromium.launch(",
        "            headless=True,",
        "            args=[",
        "                '--disable-blink-features=AutomationControlled',",
        "                '--no-sandbox',",
        "                '--disable-dev-shm-usage',",
        "            ]",
        "        )",
        "        ctx = browser.new_context(",
        "            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',",
        "            viewport={'width': 1280, 'height': 800},",
        "            locale='en-IN',",
        "            extra_http_headers={'Accept-Language': 'en-IN,en;q=0.9'},",
        "        )",
        "        page = ctx.new_page()",
        "        page.add_init_script(\"Object.defineProperty(navigator, 'webdriver', {get: () => undefined})\")",
        "        page.goto(product_url, timeout=35000, wait_until='domcontentloaded')",
        "        time.sleep(4)",
        "        result = ''",
        "        try:",
        "            og = page.locator('meta[property=\"og:image\"]').first",
        "            if og.count():",
        "                val = og.get_attribute('content') or ''",
        "                if val.startswith('http') and len(val) > 20:",
        "                    result = val",
        "        except: pass",
        "        if not result:",
        "            try:",
        "                js = '''() => {",
        "                    const imgs = Array.from(document.querySelectorAll('img'));",
        "                    let best = null, bestArea = 0;",
        "                    for (const img of imgs) {",
        "                        const src = img.src || img.getAttribute('src') || '';",
        "                        if (!src.startsWith('http')) continue;",
        "                        const w = img.naturalWidth || 0;",
        "                        const h = img.naturalHeight || 0;",
        "                        const area = w * h;",
        "                        if (w >= 200 && h >= 200 && area > bestArea) {",
        "                            bestArea = area;",
        "                            best = src;",
        "                        }",
        "                    }",
        "                    return best || '';",
        "}'''",
        "                result = page.evaluate(js) or ''",
        "            except: pass",
        "        browser.close()",
        "        if result:",
        "            print(result)",
        "except Exception as e:",
        "    pass",
    ]
    script = "\n".join(lines)

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(script)
            tmp = f.name
        res = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=55
        )
        out = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else ""
        if out and out.startswith("http"):
            return out
    except Exception as e:
        print(f"  [IMG] Universal Playwright scraper error: {e}")
    finally:
        if tmp and os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass
    return None



def _myntra_image(url: str) -> str | None:
    """Extract high-resolution product image from Myntra API or HTML CDN assets."""
    m = re.search(r'/(\d{5,12})(?:/buy|$|\?|\s)', url)
    if not m:
        m = re.search(r'myntra\.com/.*?/(\d{5,12})', url)
    if not m:
        m = re.search(r'(\d{5,12})', url)
    if m:
        style_id = m.group(1)
        api_url = f"https://www.myntra.com/gateway/v2/product/{style_id}"
        try:
            r = requests.get(api_url, headers=_HEADERS, timeout=8)
            if r.status_code == 200:
                data = r.json()
                media = data.get("style", {}).get("media", {})
                albums = media.get("albums", [])
                for album in albums:
                    images = album.get("images", [])
                    for img in images:
                        src = img.get("imageURL") or img.get("src")
                        if src:
                            return src
        except Exception:
            pass

        try:
            r = requests.get(url, headers=_HEADERS, timeout=8)
            if r.status_code == 200:
                imgs = re.findall(r'https://assets\.myntassets\.com/[^\s"\'\\]+', r.text)
                for img in imgs:
                    if any(x in img for x in ["/assets/images/", "/h_1440", "/h_720"]):
                        clean_img = re.sub(r'^https://assets\.myntassets\.com/h_\d+,w_\d+,c_fill,g_auto/', 'https://assets.myntassets.com/', img)
                        return clean_img
        except Exception:
            pass
    return None


def scrape_product_image(product_url: str) -> str | None:
    """
    Try to get the actual product image from the retailer URL.
    Returns the image URL string, or None if scraping fails.
    """
    if not product_url or not product_url.startswith("http"):
        return None

    parsed = urlparse(product_url)
    domain = parsed.netloc.lower()

    print(f"  [IMG] Scraping product image from: {domain}")

    try:
        #  Myntra 
        if "myntra.com" in domain:
            img = _myntra_image(product_url)
            if img:
                print(f"  [IMG] Got Myntra product image [OK]")
                return img

        #  Amazon India 
        elif "amazon.in" in domain or "amazon.com" in domain:
            img = _amazon_image_from_asin(product_url)
            if img:
                print(f"  [IMG] Got Amazon product image [OK]")
                return img

        #  Flipkart 
        elif "flipkart.com" in domain:
            img = _flipkart_image(product_url)
            if img:
                print(f"  [IMG] Got Flipkart product image")
                return img

        #  All other sites: try plain requests og:image first (fast path) 
        else:
            r = requests.get(product_url, headers=_HEADERS, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                img = _extract_og_image(r.text)
                if img:
                    print(f"  [IMG] Got og:image from {domain}")
                    return img

    except Exception as e:
        print(f"  [IMG] Requests scrape failed for {domain}: {e}")

    # Universal Playwright fallback (works for Ajio, Myntra, H&M and any JS-rendered site)
    print(f"  [IMG] Requests failed for {domain} – trying universal Playwright scraper...")
    img = _scrape_with_playwright(product_url)
    if img:
        print(f"  [IMG] Got image via universal Playwright scraper for {domain}")
        return img

    return None




# CURATED_IMAGES removed to prevent hardcoded stock photos

BRAND_DOMAINS = {
    "myntra":    "myntra.com",
    "ajio":      "ajio.com",
    "flipkart":  "flipkart.com",
    "amazon":    "amazon.in",
    "nykaa":     "nykaa.com",
    "mamaearth": "mamaearth.in",
    "wow":       "buywow.in",
    "plum":      "plumgoodness.com",
    "croma":     "croma.com",
    "oneplus":   "oneplus.in",
    "puma":      "puma.com",
    "nike":      "nike.com",
    "adidas":    "adidas.co.in",
    "boat":      "boat-lifestyle.com",
    "lakme":     "lakmeindia.com",
    "loreal":    "loreal-paris.co.in",
    "himalaya":  "himalayawellness.com",
    "nivea":     "niveaindia.in",
    "fogg":      "foggdeodorant.com",
    "park avenue":"parkavenue.in",
}


def get_brand_domain(text: str) -> str | None:
    """Find the brand domain matching the deal text."""
    txt = text.lower()
    for brand, domain in BRAND_DOMAINS.items():
        if brand in txt:
            return domain
    return None


def clean_query(title: str) -> str:
    """Strip price terms and noise for a clean product search query."""
    txt = title.lower()
    txt = re.sub(r'[^\x00-\x7F]+', '', txt)
    txt = re.sub(r'(?:at|from|@|rs\.?|inr)?\s*₹?\s*\d+[\d,]*\s*(?:only)?', ' ', txt, flags=re.IGNORECASE)
    bad_words = {"at", "from", "rs", "inr", "only", "hot", "deal", "loot", "verified",
                 "affiliate", "link", "buy", "grab", "now", "save", "off", "free", "flat", "upto"}
    words = [w.strip() for w in txt.split() if w.strip() and w.strip() not in bad_words]
    return " ".join(words)


# 
# 3. Main Entry Point
# 

def _download_image(url: str, out_path: str) -> bool:
    """Download and validate an image from a URL."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12, stream=True)
        if r.status_code != 200:
            return False
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        with Image.open(out_path) as im:
            w, h = im.size
            if w < 80 or h < 80:  # reject tiny/broken images
                raise ValueError(f"Image too small: {w}x{h}")
            im.verify()
        return True
    except Exception as e:
        if os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
        return False


def is_relevant_url(url: str, query: str) -> bool:
    """Validate if search result image URL is relevant to the query to avoid random mocks/spam."""
    url_lower = url.lower()
    query_lower = query.lower()
    
    # 1. Reject obvious non-product spam domains or generic placeholders
    blacklist = ["slideshare", "vecteezy", "pinterest", "facebook", "dreamstime", "shutterstock", 
                 "stockcake", "depositphotos", "alamy", "gettyimages", "123rf", "istockphoto", "slides",
                 "lyrics", "chord", "guitar", "song", "inside-games", "publicdomainpictures"]
    if any(b in url_lower for b in blacklist):
        return False
        
    # 1.5. If the URL is from the official retailer CDN, it is 100% relevant!
    trust_cdns = ["myntassets.com", "ajio.com", "rukminim", "media-amazon.com"]
    if any(cdn in url_lower for cdn in trust_cdns):
        return True
        
    # 2. Extract brand keywords from query
    brands = ["nike", "puma", "adidas", "levi", "gant", "derma", "hm", "zara", "roadster", "hrx"]
    matched_brands = [b for b in brands if b in query_lower]
    
    # If a specific brand is in the query, the URL should contain that brand keyword
    if matched_brands:
        for brand in matched_brands:
            if brand == "levi":
                clean_url = url_lower.replace("clevis", "")
                if "levi" in clean_url:
                    return True
            elif brand in url_lower:
                return True
        return False
        
    # 3. Otherwise, check if at least one noun/descriptive word from the query is in the URL
    query_words = [w for w in re.findall(r'[a-z0-9]+', query_lower) if len(w) > 3]
    if query_words:
        ignore = ["combo", "pack", "free", "sale", "deals", "loot", "best", "only", "with", "flat"]
        filtered_words = [w for w in query_words if w not in ignore]
        if filtered_words:
            return any(word in url_lower for word in filtered_words)
            
    return True


def validate_image_relevance(image_path: str, title: str) -> bool:
    """Use Gemini Vision API (via gemini-flash-lite-latest) to validate if image is a relevant product photo."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  [GEMINI] No API key configured, skipping validation.")
        return True
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        im = Image.open(image_path)
        prompt = f"""
You are a high-accuracy product image validator.
Product Title: "{title}"

Analyze the provided image and determine if it represents a real product photo for the product mentioned in the title.

Instructions:
1. Identify the primary category of the product in the title (e.g., shoes, shirt, pants, watch, sunglasses, skincare).
2. Identify the product shown in the image.
3. If the image does not show the specific category of product mentioned in the title (e.g., it shows a t-shirt/clothing when the title is for shoes/sneakers, or vice-versa), answer: NO.
4. If the image is a stock placeholder, generic shop/open sign, text-only sheet, song lyrics, or unrelated diagram, answer: NO.
5. If the image shows the actual product (or a model wearing/using the specific product category mentioned in the title), answer: YES.

Answer with ONLY "YES" or "NO". Do not write any other explanation or text.
"""
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=[prompt, im]
        )
        ans = response.text.strip().upper()
        print(f"  [GEMINI VALIDATION] Result for '{title}': {ans}")
        return "YES" in ans
    except Exception as e:
        print(f"  [GEMINI VALIDATION] Error during validation: {e}")
        return True


def search_product_image_via_search_engines(query: str, target_domain: str = "") -> list[str]:
    """
    Search Bing & Yahoo for the query and look for image URLs.
    Returns a list of candidate image URLs, sorted with CDN domains prioritized.
    """
    from urllib.parse import quote_plus
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    candidates = []
    
    # 1. Try Bing Images
    bing_url = f"https://www.bing.com/images/search?q={quote_plus(query)}"
    try:
        r = requests.get(bing_url, headers=headers, timeout=10)
        if r.status_code == 200:
            urls = re.findall(r'murl&quot;:&quot;(http[^&]+)&quot;', r.text)
            if not urls:
                urls = re.findall(r'"murl":"(http[^"]+)"', r.text)
            
            for u in urls:
                if u.lower().endswith(('.jpg', '.jpeg', '.png')) and u not in candidates:
                    if is_relevant_url(u, query):
                        candidates.append(u)
    except Exception as e:
        print(f"  [IMG FETCH] Bing search failed: {e}")
        
    # 2. Try Yahoo Images
    if len(candidates) < 5:
        yahoo_url = f"https://images.search.yahoo.com/search/images?p={quote_plus(query)}"
        try:
            r = requests.get(yahoo_url, headers=headers, timeout=10)
            if r.status_code == 200:
                urls = re.findall(r'"iurl":"(http[^"]+)"', r.text)
                if not urls:
                    urls = re.findall(r'imgurl=&quot;(http[^&]+)&quot;', r.text)
                    
                for u in urls:
                    if u.lower().endswith(('.jpg', '.jpeg', '.png')) and u not in candidates:
                        if is_relevant_url(u, query):
                            candidates.append(u)
        except Exception as e:
            print(f"  [IMG FETCH] Yahoo search failed: {e}")
            
    # Sort candidates to prioritize target CDN domains if target_domain is set
    if target_domain and candidates:
        short_domain = target_domain.replace("www.", "").split(".")[0]
        cdn_matches = []
        if "myntra" in short_domain:
            cdn_matches = ["myntassets.com"]
        elif "ajio" in short_domain:
            cdn_matches = ["ajio.com"]
        elif "flipkart" in short_domain:
            cdn_matches = ["rukminim"]
            
        def sort_key(url):
            url_lower = url.lower()
            for i, match in enumerate(cdn_matches):
                if match in url_lower:
                    return i
            return len(cdn_matches)
            
        candidates.sort(key=sort_key)
        
    return candidates


def generate_pinterest_deal_card(title: str, out_path: str, product_url: str = None) -> str:
    """
    Generate a dynamic, high-converting vertical Pinterest deal pin card (1000 x 1500 px)
    customized specifically for this deal title, brand, and price.
    """
    w, h = 1000, 1500
    img = Image.new("RGB", (w, h), (18, 18, 24))
    draw = ImageDraw.Draw(img)
    
    # 1. Dynamic gradient based on hash of title
    title_hash = sum(ord(c) for c in title)
    hues = [
        ((20, 20, 30), (45, 20, 60)),     # Royal Purple
        ((15, 25, 35), (20, 60, 80)),     # Deep Ocean Teal
        ((25, 18, 20), (70, 25, 35)),     # Crimson Red
        ((20, 25, 20), (30, 70, 40)),     # Emerald Forest
        ((25, 22, 15), (75, 55, 20)),     # Warm Amber Gold
    ]
    bg_start, bg_end = hues[title_hash % len(hues)]
    
    for y in range(h):
        r = int(bg_start[0] + (y / h) * (bg_end[0] - bg_start[0]))
        g = int(bg_start[1] + (y / h) * (bg_end[1] - bg_start[1]))
        b = int(bg_start[2] + (y / h) * (bg_end[2] - bg_start[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b))
        
    # Top banner bar
    draw.rectangle([60, 80, 940, 180], fill=(255, 45, 85))
    
    try:
        font_large = ImageFont.truetype("arial.ttf", 60)
        font_med = ImageFont.truetype("arial.ttf", 42)
        font_price = ImageFont.truetype("arial.ttf", 52)
    except:
        font_large = font_med = font_price = ImageFont.load_default()
        
    draw.text((120, 110), "HOT LOOT DEAL ALERT", fill=(255, 255, 255), font=font_med)
    
    # Brand Card container
    draw.rounded_rectangle([60, 240, 940, 1220], radius=30, fill=(30, 32, 44), outline=(70, 75, 100), width=3)
    
    # Extract price from title
    m_price = re.search(r'(?:at|from|@|rs\.?|inr)?\s*[₹]?\s*(\d[\d,]*)', title, re.IGNORECASE)
    price_val = m_price.group(1).replace(',', '') if m_price else None
    
    # Extract brand domain & try downloading brand logo
    domain = None
    if product_url:
        parsed = urlparse(product_url)
        domain = parsed.netloc.lower().replace("www.", "")
    if not domain:
        domain = get_brand_domain(title)
        
    dir_name = os.path.dirname(out_path) or "."
    logo_file = os.path.join(dir_name, "temp_logo.png")
    if domain:
        logo_url = f"https://logo.clearbit.com/{domain}?size=300"
        try:
            r = requests.get(logo_url, timeout=4)
            if r.status_code == 200:
                with open(logo_file, "wb") as f:
                    f.write(r.content)
                logo = Image.open(logo_file).convert("RGBA")
                logo.thumbnail((260, 260))
                img.paste(logo, (370, 300), logo)
                try: os.remove(logo_file)
                except: pass
        except: pass
        
    # Draw Title text (clean non-latin1 characters)
    clean_title = re.sub(r'[^\x00-\x7F]+', '', title)
    words = clean_title.split()
    lines = []
    curr = []
    for word in words:
        curr.append(word)
        if len(" ".join(curr)) > 20:
            curr.pop()
            lines.append(" ".join(curr))
            curr = [word]
    if curr:
        lines.append(" ".join(curr))
        
    y_text = 600
    for line in lines[:4]:
        draw.text((100, y_text), line, fill=(255, 255, 255), font=font_large)
        y_text += 80
        
    # Draw Price Pill
    if price_val:
        draw.rounded_rectangle([100, 1020, 900, 1140], radius=20, fill=(40, 167, 69))
        draw.text((140, 1050), f"SPECIAL PRICE: Rs {price_val}", fill=(255, 255, 255), font=font_price)
    else:
        draw.rounded_rectangle([100, 1020, 900, 1140], radius=20, fill=(40, 167, 69))
        draw.text((140, 1050), "VERIFIED DISCOUNT OFFER", fill=(255, 255, 255), font=font_price)
        
    # Call to action button at bottom
    draw.rounded_rectangle([60, 1280, 940, 1420], radius=30, fill=(255, 45, 85))
    draw.text((220, 1325), "CLICK TO GET THIS DEAL", fill=(255, 255, 255), font=font_large)
    
    img.save(out_path, quality=95)
    print(f"  [IMG FETCH] Generated high-converting Pinterest deal card: {out_path}")
    return out_path


def fetch_and_save_image(title: str, out_path: str = "docs/deals/images/fallback.jpg",
                         product_url: str = None) -> str | None:
    """
    Full image resolution priority chain:
      1. Scrape actual product photo from retailer page (og:image / product CDN)
      1.5 Search engine fallback (Bing/Yahoo) with Gemini Vision validation
      2. Dynamic high-converting Pinterest deal pin card (tailored to deal title, price, brand)
    """
    dir_name = os.path.dirname(out_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    #  Step 1: Actual product image from retailer 
    if product_url:
        img_url = scrape_product_image(product_url)
        if img_url:
            if _download_image(img_url, out_path):
                if validate_image_relevance(out_path, title):
                    print(f"  [IMG FETCH] Real product image saved & validated: {out_path}")
                    return out_path
                else:
                    if os.path.exists(out_path):
                        try: os.remove(out_path)
                        except: pass

    #  Step 1.5: Search engine fallback
    query = ""
    target_domain = ""

    if product_url:
        from urllib.parse import urlparse
        parsed = urlparse(product_url)
        target_domain = parsed.netloc.lower()
        path_parts = [p for p in parsed.path.split("/") if p.strip()]
        for part in path_parts:
            if "-" in part and not part.isdigit() and part not in ["buy", "p"]:
                query = part.replace("-", " ")
                break

    if not query:
        query = clean_query(title)
        words = query.split()
        if len(words) > 3:
            query = " ".join(words[:4])
        else:
            query = " ".join(words)

    if query:
        candidates = search_product_image_via_search_engines(query, target_domain)
        for idx, img_url in enumerate(candidates[:5]):
            if _download_image(img_url, out_path):
                if validate_image_relevance(out_path, title):
                    print(f"  [IMG FETCH] Candidate {idx+1} validated successfully!")
                    return out_path
                else:
                    if os.path.exists(out_path):
                        try: os.remove(out_path)
                        except: pass

    #  Step 2: High-converting dynamic Pinterest deal pin card 
    print("  [IMG FETCH] Generating dynamic high-converting Pinterest deal pin card...")
    return generate_pinterest_deal_card(title, out_path, product_url)

