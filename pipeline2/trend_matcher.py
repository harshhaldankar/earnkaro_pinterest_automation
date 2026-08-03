import asyncio
import random
import urllib.parse
import json
from curl_cffi import requests
import re
import time
import sys
import os

# Import the filter function from P1
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from telegram_watcher import is_single_product_url
except ImportError:
    def is_single_product_url(url: str) -> bool:
        return True

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
]

class ProductDeal:
    def __init__(self, title, price, mrp, discount_percent, image_url, product_url, retailer, category):
        self.title = title
        self.price = price
        self.mrp = mrp
        self.discount_percent = discount_percent
        self.image_url = image_url
        self.product_url = product_url
        self.retailer = retailer
        self.category = category
        
        # Computed fields
        self.profit_tier = "Unknown"
        self.affiliate_url = ""

    def to_dict(self):
        return self.__dict__

def extract_digits(text: str) -> int:
    """Extract numeric value from price string like '₹1,299' -> 1299"""
    digits = ''.join(filter(str.isdigit, text))
    return int(digits) if digits else 0

# ─────────────────────────────────────────────────────────
# FLIPKART — Primary retailer (works from datacenter IPs)
# Uses server-rendered HTML with BeautifulSoup
# ─────────────────────────────────────────────────────────
def scrape_flipkart(session, keyword: str, category: str):
    """Scrapes Flipkart search results sorted by discount. Returns list of ProductDeal."""
    deals = []
    url = f"https://www.flipkart.com/search?q={urllib.parse.quote(keyword)}&sort=discount&as-show=on"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.flipkart.com/",
    }
    
    try:
        response = session.get(url, headers=headers, impersonate="chrome110", timeout=15)
        if response.status_code != 200:
            print(f"[Matcher] Flipkart HTTP {response.status_code} for '{keyword}'")
            return deals
            
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Flipkart uses div[data-id] for each product card
        cards = soup.select("div[data-id]")
        if not cards:
            print(f"[Matcher] Flipkart: No product cards found for '{keyword}'")
            return deals
            
        for card in cards[:12]:  # Check up to 12 products
            try:
                # Product URL
                link_el = card.find("a", href=True)
                if not link_el:
                    continue
                product_url = link_el["href"]
                if product_url.startswith("/"):
                    product_url = "https://www.flipkart.com" + product_url
                
                # Skip non-product links (ads, sponsored)
                if "/p/" not in product_url:
                    continue
                    
                # Brand name (div.Fo1I0b)  
                brand_el = card.find("div", class_="Fo1I0b")
                brand = brand_el.get_text(strip=True) if brand_el else ""
                
                # Title (a.atJtCj or a.wjcEIp or a.WKTcLC)
                title_el = (card.find("a", class_="atJtCj") or 
                           card.find("a", class_="wjcEIp") or 
                           card.find("a", class_="WKTcLC") or
                           card.find("a", class_="CGtC98"))
                title_text = title_el.get_text(strip=True) if title_el else ""
                full_title = f"{brand} {title_text}".strip() if brand else title_text
                
                if not full_title:
                    continue
                
                # Selling price (div.hZ3P6w or div.Nx9bqj or div._30jeq3)
                price_el = (card.find("div", class_="hZ3P6w") or 
                           card.find("div", class_="Nx9bqj") or
                           card.find("div", class_="_30jeq3"))
                price = extract_digits(price_el.get_text()) if price_el else 0
                
                # MRP / original price (div.kRYCnD or div.yRaY8j or div._3I9_wc)
                mrp_el = (card.find("div", class_="kRYCnD") or 
                         card.find("div", class_="yRaY8j") or
                         card.find("div", class_="_3I9_wc"))
                mrp = extract_digits(mrp_el.get_text()) if mrp_el else 0
                
                # Discount (div.HQe8jr or div.UkUFwK or div._3Ay6Sb)
                discount_el = (card.find("div", class_="HQe8jr") or 
                              card.find("div", class_="UkUFwK") or
                              card.find("div", class_="_3Ay6Sb"))
                discount = 0
                if discount_el:
                    disc_text = discount_el.get_text()
                    disc_digits = ''.join(filter(str.isdigit, disc_text.split('%')[0]))
                    discount = int(disc_digits) if disc_digits else 0
                
                # Compute discount from price/mrp if not parsed
                if not discount and mrp > price > 0:
                    discount = round(((mrp - price) / mrp) * 100)
                
                # Image URL
                img_el = card.find("img")
                image_url = ""
                if img_el:
                    image_url = img_el.get("src", "") or img_el.get("data-src", "")
                
                # Only include deals with >40% discount
                if full_title and product_url and price > 0 and discount > 40:
                    if is_single_product_url(product_url):
                        deals.append(ProductDeal(
                            full_title, price, mrp, discount, 
                            image_url, product_url, "Flipkart", category
                        ))
            except Exception:
                continue
                
        print(f"[Matcher] Flipkart: Found {len(deals)} deals (>40% off) for '{keyword}'")
    except Exception as e:
        print(f"[Matcher] Flipkart scrape failed for '{keyword}': {e}")
    
    return sorted(deals, key=lambda x: x.discount_percent, reverse=True)[:5]


# ─────────────────────────────────────────────────────────
# AJIO — Secondary retailer (may be blocked on datacenter)
# Tries JSON API first, falls back gracefully
# ─────────────────────────────────────────────────────────
def scrape_ajio(session, keyword: str, category: str):
    """Attempts AJIO search API. Returns empty list if blocked."""
    deals = []
    url = f"https://www.ajio.com/api/search?searchQuery={urllib.parse.quote(keyword)}&pageSize=20&curated=true&gridColumns=3"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Referer": "https://www.ajio.com/",
        "Origin": "https://www.ajio.com",
    }
    
    try:
        response = session.get(url, headers=headers, impersonate="chrome110", timeout=10)
        if response.status_code != 200:
            print(f"[Matcher] AJIO blocked (HTTP {response.status_code}) for '{keyword}' — skipping")
            return deals
            
        data = response.json()
        products = data.get("products", [])
        
        for p in products[:10]:
            try:
                title = p.get("name", "")
                price = int(p.get("price", {}).get("value", 0) if isinstance(p.get("price"), dict) else p.get("price", 0))
                mrp = int(p.get("wasPriceData", {}).get("value", 0) if isinstance(p.get("wasPriceData"), dict) else p.get("wasPriceData", 0))
                discount = int(p.get("discount", 0))
                
                if not discount and mrp > price > 0:
                    discount = round(((mrp - price) / mrp) * 100)
                
                images = p.get("images", [])
                image_url = images[0].get("url", "") if images else ""
                if image_url and not image_url.startswith("http"):
                    image_url = "https:" + image_url
                    
                product_url = p.get("url", "")
                if product_url and product_url.startswith("/"):
                    product_url = "https://www.ajio.com" + product_url
                
                if title and product_url and price > 0 and discount > 40:
                    if is_single_product_url(product_url):
                        deals.append(ProductDeal(title, price, mrp, discount, image_url, product_url, "AJIO", category))
            except Exception:
                continue
                
        print(f"[Matcher] AJIO: Found {len(deals)} deals (>40% off) for '{keyword}'")
    except Exception as e:
        print(f"[Matcher] AJIO failed for '{keyword}': {e}")
    
    return sorted(deals, key=lambda x: x.discount_percent, reverse=True)[:3]


# ─────────────────────────────────────────────────────────
# MYNTRA — Secondary retailer (may be blocked on datacenter)
# Tries JSON API, falls back gracefully
# ─────────────────────────────────────────────────────────
def scrape_myntra(session, keyword: str, category: str):
    """Attempts Myntra search API. Returns empty list if blocked."""
    deals = []
    encoded = urllib.parse.quote(keyword)
    url = f"https://www.myntra.com/gateway/v2/search/{encoded}?p=1&rows=20&o=0&plaEnabled=false"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Referer": "https://www.myntra.com/",
        "x-myntraweb": "Yes",
        "x-requested-with": "browser",
    }
    
    try:
        response = session.get(url, headers=headers, impersonate="chrome110", timeout=10)
        if response.status_code != 200:
            print(f"[Matcher] Myntra blocked (HTTP {response.status_code}) for '{keyword}' — skipping")
            return deals
            
        data = response.json()
        products = data.get("products", [])
        
        for p in products[:10]:
            try:
                title = p.get("productName", p.get("name", ""))
                brand = p.get("brand", "")
                full_title = f"{brand} {title}".strip() if brand else title
                
                price = int(p.get("price", 0))
                mrp = int(p.get("mrp", 0))
                discount = int(p.get("discount", 0))
                
                if not discount and mrp > price > 0:
                    discount = round(((mrp - price) / mrp) * 100)
                
                image_url = p.get("searchImage", "")
                product_url = p.get("landingPageUrl", "")
                if product_url and not product_url.startswith("http"):
                    product_url = "https://www.myntra.com/" + product_url.lstrip("/")
                
                if title and product_url and price > 0 and discount > 40:
                    if is_single_product_url(product_url):
                        deals.append(ProductDeal(full_title, price, mrp, discount, image_url, product_url, "Myntra", category))
            except Exception:
                continue
                
        print(f"[Matcher] Myntra: Found {len(deals)} deals (>40% off) for '{keyword}'")
    except Exception as e:
        print(f"[Matcher] Myntra failed for '{keyword}': {e}")
    
    return sorted(deals, key=lambda x: x.discount_percent, reverse=True)[:3]


# ─────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────
async def match_trends_to_products(trends: list):
    """
    Takes a list of trend dicts and searches retailers for matching deals.
    Flipkart is primary (always works). AJIO/Myntra are bonus (may be blocked).
    Returns a combined list of ProductDeal objects.
    """
    all_deals = []
    print(f"[Matcher] Searching retailers for {len(trends)} trends...")
    
    with requests.Session() as session:
        for trend in trends:
            kw = trend["keyword"]
            cat = trend["category"]
            print(f"\n[Matcher] Searching for '{kw}'...")
            
            # Primary: Flipkart (always works from any IP)
            flipkart_deals = scrape_flipkart(session, kw, cat)
            all_deals.extend(flipkart_deals)
            
            # Secondary: AJIO (may fail on datacenter IPs — that's OK)
            ajio_deals = scrape_ajio(session, kw, cat)
            all_deals.extend(ajio_deals)
            
            # Secondary: Myntra (may fail on datacenter IPs — that's OK)  
            myntra_deals = scrape_myntra(session, kw, cat)
            all_deals.extend(myntra_deals)
            
            # Small delay between keywords to be polite
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
    print(f"\n[Matcher] === TOTAL: Found {len(all_deals)} deals with >40% discount across all trends. ===")
    return all_deals
