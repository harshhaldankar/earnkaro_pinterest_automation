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

CURATED_IMAGES = {
    "jacket": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop",
    "coat": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop",
    "jeans": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&auto=format&fit=crop",
    "denim": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&auto=format&fit=crop",
    "shirt": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "t-shirt": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "tee": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "top": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "shoes": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "sneakers": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "sneaker": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "running": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "watch": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop",
    "smartwatch": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop",
    "phone": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "mobile": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "iphone": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "oneplus": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "samsung": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "skincare": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "cream": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "face": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "serum": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "shampoo": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "lotion": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "bedsheet": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "bedsheets": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "bed": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "bag": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",
    "handbag": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",
    "backpack": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",
    "headphone": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop",
    "headphones": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop",
    "earbuds": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop",
    "pods": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop",
    "cookware": "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "pan": "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "bottle": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop",
}

def fetch_and_save_image(title, out_path="docs/deals/images/fallback.jpg"):
    """
    Priority fallback image downloader:
    1. Check for a matching high-converting curated Unsplash lifestyle photo.
    2. Try official Clearbit brand logo.
    3. Fallback to a high-quality generic shopping display pattern.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    # 1. Match curated lifestyle keywords
    txt = title.lower()
    matched_url = None
    for kw, img_url in CURATED_IMAGES.items():
        if kw in txt:
            matched_url = img_url
            print(f"  [IMG FETCH] Matched curated lifestyle keyword '{kw}' -> {img_url[:60]}...")
            break

    if matched_url:
        try:
            r = requests.get(matched_url, timeout=12, stream=True)
            if r.status_code == 200:
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                with Image.open(out_path) as im:
                    im.verify()
                print(f"  [IMG FETCH] Saved lifestyle image: {out_path}")
                return out_path
        except Exception as e:
            print(f"  [IMG FETCH] Failed to download lifestyle image: {e}")
            if os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass

    # 2. Try fetching the official brand logo
    domain = get_brand_domain(title)
    if domain:
        logo_url = f"https://logo.clearbit.com/{domain}?size=500"
        try:
            print(f"  [IMG FETCH] Fetching brand logo: {domain}")
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
                try: os.remove(out_path)
                except: pass

    # 3. Safe fallback pattern
    generic_url = "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=600&auto=format&fit=crop"
    try:
        r = requests.get(generic_url, timeout=10, stream=True)
        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            print(f"  [IMG FETCH] Saved generic shopping fallback pattern")
            return out_path
    except Exception as e:
        print(f"  [IMG FETCH] Failed generic fallback: {e}")
        if os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass

    return None
