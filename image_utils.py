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


def scrape_product_image_playwright(product_url: str) -> str | None:
    """
    Launch Playwright sync browser to render the page and extract the product image.
    This bypasses user-agent blocks and cloud challenges on Myntra, Ajio, etc.
    """
    from playwright.sync_api import sync_playwright
    import time
    
    print(f"  [IMG] Running Playwright browser image scraper fallback...")
    img_url = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            # Navigate with a timeout
            page.goto(product_url, timeout=25000, wait_until="domcontentloaded")
            time.sleep(3)  # Allow JS and lazy images to load
            
            # 1. Try og:image meta tag first
            og_meta = page.locator('meta[property="og:image"]').first
            if og_meta.count():
                val = og_meta.get_attribute("content")
                if val and val.startswith("http"):
                    img_url = val
                    
            # 2. Try Ajio-specific selectors
            if not img_url and "ajio.com" in product_url:
                ajio_img = page.locator('img.main-img, img.img-responsive, .product-img img').first
                if ajio_img.count():
                    val = ajio_img.get_attribute("src")
                    if val and val.startswith("http"):
                        img_url = val

            # 3. Try Myntra-specific selectors
            if not img_url and "myntra.com" in product_url:
                myntra_img = page.locator('img.image-grid-image, img.pdp-main-image').first
                if myntra_img.count():
                    val = myntra_img.get_attribute("src")
                    if val and val.startswith("http"):
                        img_url = val

            # 4. Generic size-based fallback: look for first large img element
            if not img_url:
                images = page.locator('img').all()
                for img in images:
                    src = img.get_attribute("src")
                    if src and src.startswith("http"):
                        try:
                            # Verify image size is suitable for a product card
                            w = img.evaluate("el => el.naturalWidth")
                            h = img.evaluate("el => el.naturalHeight")
                            if w > 200 and h > 200:
                                img_url = src
                                break
                        except: pass
            
            browser.close()
    except Exception as e:
        print(f"  [IMG] Playwright scraper failed: {e}")
    return img_url


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
        #  Amazon India 
        if "amazon.in" in domain or "amazon.com" in domain:
            img = _amazon_image_from_asin(product_url)
            if img:
                print(f"  [IMG] Got Amazon product image [OK]")
                return img

        #  Flipkart 
        elif "flipkart.com" in domain:
            img = _flipkart_image(product_url)
            if img:
                print(f"  [IMG] Got Flipkart product image ")
                return img

        #  Generic og:image for all other retailers (Myntra, Nykaa, Mamaearth, etc.) 
        else:
            r = requests.get(product_url, headers=_HEADERS, timeout=10)
            if r.status_code == 200:
                img = _extract_og_image(r.text)
                if img:
                    print(f"  [IMG] Got og:image from {domain} ")
                    return img

    except Exception as e:
        print(f"  [IMG] Retailer image requests scrape failed for {domain}: {e}")

    # Playwright browser fallback if requests failed
    # Run in a subprocess to avoid "using Playwright Sync API inside asyncio loop" error
    import subprocess
    import sys
    playwright_img = None
    try:
        cmd = [
            sys.executable,
            "-c",
            f"from image_utils import scrape_product_image_playwright; print(scrape_product_image_playwright({repr(product_url)}) or '')"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = res.stdout.strip()
        if out and out.startswith("http"):
            playwright_img = out
    except Exception as e:
        print(f"  [IMG] Subprocess Playwright scraper failed: {e}")

    if playwright_img:
        print(f"  [IMG] Success via Playwright scraper fallback [OK]")
        return playwright_img

    return None


# 
# 2. Curated Lifestyle Keyword Map (60+ categories)
# 

CURATED_IMAGES = {
    #  Clothing 
    "jacket":     "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop",
    "puffer":     "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop",
    "coat":       "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop",
    "hoodie":     "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&auto=format&fit=crop",
    "sweatshirt": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&auto=format&fit=crop",
    "jeans":      "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&auto=format&fit=crop",
    "denim":      "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&auto=format&fit=crop",
    "trouser":    "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&auto=format&fit=crop",
    "pants":      "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&auto=format&fit=crop",
    "shirt":      "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "t-shirt":    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "tshirt":     "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "tee":        "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "polo":       "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop",
    "top":        "https://images.unsplash.com/photo-1485462537746-965f33f7f6a7?w=600&auto=format&fit=crop",
    "kurti":      "https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=600&auto=format&fit=crop",
    "saree":      "https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=600&auto=format&fit=crop",
    "lehenga":    "https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=600&auto=format&fit=crop",
    "dress":      "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&auto=format&fit=crop",
    "kurta":      "https://images.unsplash.com/photo-1567401893414-76b7b1e5a7a5?w=600&auto=format&fit=crop",
    "tracksuit":  "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&auto=format&fit=crop",
    "activewear": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&auto=format&fit=crop",
    "sportswear": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&auto=format&fit=crop",

    #  Footwear 
    "shoes":     "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "sneaker":   "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "sneakers":  "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "sandal":    "https://images.unsplash.com/photo-1603487742131-4160ec999306?w=600&auto=format&fit=crop",
    "heels":     "https://images.unsplash.com/photo-1603487742131-4160ec999306?w=600&auto=format&fit=crop",
    "slipper":   "https://images.unsplash.com/photo-1603487742131-4160ec999306?w=600&auto=format&fit=crop",
    "boots":     "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "loafers":   "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",
    "running":   "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop",

    #  Watches & Accessories 
    "watch":       "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop",
    "smartwatch":  "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop",
    "sunglasses":  "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=600&auto=format&fit=crop",
    "sunglass":    "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=600&auto=format&fit=crop",
    "belt":        "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",
    "wallet":      "https://images.unsplash.com/photo-1627123424574-724758594913?w=600&auto=format&fit=crop",
    "jewellery":   "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&auto=format&fit=crop",
    "jewelry":     "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&auto=format&fit=crop",
    "necklace":    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&auto=format&fit=crop",
    "ring":        "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&auto=format&fit=crop",
    "earring":     "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&auto=format&fit=crop",

    #  Bags 
    "bag":       "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",
    "handbag":   "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",
    "backpack":  "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&auto=format&fit=crop",
    "luggage":   "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&auto=format&fit=crop",
    "suitcase":  "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&auto=format&fit=crop",
    "tote":      "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop",

    #  Beauty & Skincare 
    "skincare":  "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "cream":     "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "moisturizer":"https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "serum":     "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "sunscreen": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "face wash": "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "shampoo":   "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "conditioner":"https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "lotion":    "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",
    "lip":       "https://images.unsplash.com/photo-1586495777744-4e6b0e85d1e4?w=600&auto=format&fit=crop",
    "lipstick":  "https://images.unsplash.com/photo-1586495777744-4e6b0e85d1e4?w=600&auto=format&fit=crop",
    "makeup":    "https://images.unsplash.com/photo-1586495777744-4e6b0e85d1e4?w=600&auto=format&fit=crop",
    "foundation":"https://images.unsplash.com/photo-1586495777744-4e6b0e85d1e4?w=600&auto=format&fit=crop",
    "perfume":   "https://images.unsplash.com/photo-1541643600914-78b084683702?w=600&auto=format&fit=crop",
    "fragrance": "https://images.unsplash.com/photo-1541643600914-78b084683702?w=600&auto=format&fit=crop",
    "body spray":"https://images.unsplash.com/photo-1541643600914-78b084683702?w=600&auto=format&fit=crop",
    "deodorant": "https://images.unsplash.com/photo-1541643600914-78b084683702?w=600&auto=format&fit=crop",
    "spray":     "https://images.unsplash.com/photo-1541643600914-78b084683702?w=600&auto=format&fit=crop",
    "hair":      "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=600&auto=format&fit=crop",
    "oil":       "https://images.unsplash.com/photo-1608248597481-496100c80836?w=600&auto=format&fit=crop",

    #  Electronics 
    "phone":      "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "mobile":     "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "smartphone": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "iphone":     "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "samsung":    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "oneplus":    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "redmi":      "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "realme":     "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "laptop":     "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=600&auto=format&fit=crop",
    "tablet":     "https://images.unsplash.com/photo-1544244015-0df4592c8e3f?w=600&auto=format&fit=crop",
    "ipad":       "https://images.unsplash.com/photo-1544244015-0df4592c8e3f?w=600&auto=format&fit=crop",
    "headphone":  "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop",
    "headphones": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop",
    "earbuds":    "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop",
    "airpods":    "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&auto=format&fit=crop",
    "speaker":    "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=600&auto=format&fit=crop",
    "tv":         "https://images.unsplash.com/photo-1593359677879-a4bb92f4834c?w=600&auto=format&fit=crop",
    "television": "https://images.unsplash.com/photo-1593359677879-a4bb92f4834c?w=600&auto=format&fit=crop",
    "camera":     "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&auto=format&fit=crop",
    "charger":    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",
    "powerbank":  "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop",

    #  Home & Kitchen 
    "bedsheet":   "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "bedsheets":  "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "pillow":     "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "mattress":   "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "curtain":    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=600&auto=format&fit=crop",
    "cookware":   "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "pan":        "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "pressure cooker": "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "mixer":      "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "grinder":    "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop",
    "bottle":     "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop",
    "water bottle":"https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop",
    "thermos":    "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop",
    "washing machine": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&auto=format&fit=crop",
    "refrigerator":"https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=600&auto=format&fit=crop",
    "fridge":     "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=600&auto=format&fit=crop",
    "air conditioner": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&auto=format&fit=crop",
    "ac ":        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&auto=format&fit=crop",

    #  Sports & Fitness 
    "gym":        "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&auto=format&fit=crop",
    "fitness":    "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&auto=format&fit=crop",
    "yoga":       "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=600&auto=format&fit=crop",
    "protein":    "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&auto=format&fit=crop",
    "supplement": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&auto=format&fit=crop",

    #  Books 
    "book":       "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=600&auto=format&fit=crop",
    "books":      "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=600&auto=format&fit=crop",

    #  Food & Grocery 
    "chocolate":  "https://images.unsplash.com/photo-1481391319762-47dff72954d9?w=600&auto=format&fit=crop",
    "coffee":     "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&auto=format&fit=crop",
    "tea":        "https://images.unsplash.com/photo-1556742400-b5b7c512e3b7?w=600&auto=format&fit=crop",
    "grocery":    "https://images.unsplash.com/photo-1542838132-92c53300491e?w=600&auto=format&fit=crop",
}

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


def fetch_and_save_image(title: str, out_path: str = "docs/deals/images/fallback.jpg",
                         product_url: str = None) -> str | None:
    """
    Full image resolution priority chain:
      1. Scrape actual product photo from retailer page (og:image / product CDN)
      2. Curated lifestyle photo matched by keyword (60+ categories)
      3. Official brand logo via Clearbit
      4. Safe generic premium shopping fallback
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    #  Step 1: Actual product image from retailer 
    if product_url:
        img_url = scrape_product_image(product_url)
        if img_url:
            if _download_image(img_url, out_path):
                print(f"  [IMG FETCH]  Real product image saved: {out_path}")
                return out_path
            else:
                print(f"  [IMG FETCH] Retailer image download failed, trying fallbacks...")

    #  Step 2: Curated lifestyle keyword match 
    txt = title.lower()
    for kw, img_url in CURATED_IMAGES.items():
        if kw in txt:
            print(f"  [IMG FETCH] Matched lifestyle keyword '{kw}'")
            if _download_image(img_url, out_path):
                print(f"  [IMG FETCH]  Lifestyle image saved: {out_path}")
                return out_path

    #  Step 3: Clearbit brand logo 
    domain = get_brand_domain(title)
    if domain:
        logo_url = f"https://logo.clearbit.com/{domain}?size=500"
        print(f"  [IMG FETCH] Trying brand logo: {domain}")
        if _download_image(logo_url, out_path):
            print(f"  [IMG FETCH]  Brand logo saved: {out_path}")
            return out_path

    #  Step 4: Premium generic shopping pattern 
    generic_url = "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=600&auto=format&fit=crop"
    print(f"  [IMG FETCH] Using generic shopping fallback")
    if _download_image(generic_url, out_path):
        print(f"  [IMG FETCH]  Generic fallback saved: {out_path}")
        return out_path

    return None

