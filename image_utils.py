"""image_utils.py — Helper to fetch high-quality product/brand images from search engines and Clearbit."""
import os
import re
import requests
from urllib.parse import quote_plus
from PIL import Image

BRAND_DOMAINS = {
    "myntra": "myntra.com",
    "ajio": "ajio.com",
    "flipkart": "flipkart.com",
    "amazon": "amazon.in",
    "nykaa": "nykaa.com",
    "mamaearth": "mamaearth.in",
    "wow": "buywow.in",
    "plum": "plumgoodness.com",
    "croma": "croma.com",
    "oneplus": "oneplus.in",
    "axis": "axisbank.com",
}

def clean_query(title):
    """Strip tracking codes, price terms, and emojis for a clean product search."""
    txt = title.lower()
    # Remove emojis
    txt = re.sub(r'[^\x00-\x7F]+', '', txt)
    
    # Strip common pricing patterns (e.g. @ 299, at Rs 499, at 499)
    txt = re.sub(r'(?:at|from|@|rs\.?|inr)?\s*[₹]?\s*\d+[\d,]*\s*(?:only)?', '', txt, flags=re.IGNORECASE)
    
    # Split and remove bad words
    bad_words = {"at", "from", "rs", "inr", "only", "hot", "deal", "loot", "verified", "affiliate", "buying", "link", "buy", "here", "grab", "now", "save", "big", "off", "free", "shipping"}
    words = [w.strip() for w in txt.split() if w.strip()]
    cleaned_words = [w for w in words if w not in bad_words]
    return " ".join(cleaned_words)

def search_image_urls(query):
    """Search Bing and Yahoo for a list of image URLs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    found_urls = []
    
    # 1. Bing Search
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            urls = re.findall(r'murl&quot;:&quot;(http[^&]+)&quot;', r.text)
            if not urls:
                urls = re.findall(r'"murl":"(http[^"]+)"', r.text)
            if urls:
                found_urls.extend(urls)
    except Exception as e:
        print(f"  [IMG SEARCH] Bing failed: {e}")
        
    # 2. Yahoo Search
    url = f"https://images.search.yahoo.com/search/images?p={quote_plus(query)}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            urls = re.findall(r'"iurl":"(http[^"]+)"', r.text)
            if urls:
                found_urls.extend(urls)
    except Exception as e:
        print(f"  [IMG SEARCH] Yahoo failed: {e}")
        
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in found_urls:
        # Filter out obvious logo/banner files in search results if product name is long
        if len(query.split()) > 2 and any(x in u.lower() for x in ["logo", "banner", "header", "icon", "placeholder"]):
            continue
        if u not in seen:
            seen.add(u)
            deduped.append(u)
            
    return deduped

def get_brand_domain(text):
    """Find the brand domain matching the deal text."""
    txt = text.lower()
    for brand, domain in BRAND_DOMAINS.items():
        if brand in txt:
            return domain
    return None

def fetch_and_save_image(title, out_path="docs/deals/images/fallback.jpg"):
    """
    Finds a product image via search, downloads it.
    If search fails or downloading fails, fetches the high-quality Clearbit Brand Logo.
    Returns path to saved image, or None if completely failed.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    query = clean_query(title)
    print(f"  [IMG FETCH] Searching for: '{query}'")
    
    img_urls = search_image_urls(query)
    
    # Try downloading from the search results, top 5 candidates
    for i, img_url in enumerate(img_urls[:5]):
        try:
            print(f"  [IMG FETCH] Try #{i+1} downloading: {img_url}")
            r = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, stream=True)
            if r.status_code == 200:
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                # Validate it's a real openable image
                with Image.open(out_path) as im:
                    im.verify()
                print(f"  [IMG FETCH] Saved product search image to: {out_path}")
                return out_path
        except Exception as e:
            print(f"  [IMG FETCH] Failed try #{i+1}: {e}")
            if os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass

    # Fallback to Clearbit logo
    domain = get_brand_domain(title)
    if domain:
        logo_url = f"https://logo.clearbit.com/{domain}?size=500"
        try:
            print(f"  [IMG FETCH] Falling back to Clearbit Logo for: {domain}")
            r = requests.get(logo_url, timeout=8, stream=True)
            if r.status_code == 200:
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                with Image.open(out_path) as im:
                    im.verify()
                print(f"  [IMG FETCH] Saved brand logo to: {out_path}")
                return out_path
        except Exception as e:
            print(f"  [IMG FETCH] Clearbit fetch failed: {e}")
            if os.path.exists(out_path):
                os.remove(out_path)

    return None
