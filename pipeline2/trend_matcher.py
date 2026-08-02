import asyncio
import random
import urllib.parse
from playwright.async_api import async_playwright
import json

# Import the filter function from P1
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from telegram_watcher import is_single_product_url
except ImportError:
    def is_single_product_url(url: str) -> bool:
        return True # Fallback if unavailable

async def human_delay(min_s: float = 1.0, max_s: float = 3.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

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

async def scrape_ajio(page, keyword: str, category: str):
    deals = []
    url = f"https://www.ajio.com/search/?query={urllib.parse.quote(keyword)}"
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await human_delay()
        # Scroll to load images
        await page.evaluate("window.scrollBy(0, 800)")
        await human_delay()
        
        items = await page.query_selector_all('.item')
        for item in items[:6]:
            try:
                title_el = await item.query_selector('.nameCls')
                title = await title_el.inner_text() if title_el else ""
                
                link_el = await item.query_selector('a.rilrtl-products-list__link')
                product_url = await link_el.get_attribute('href') if link_el else ""
                if product_url and product_url.startswith('/'):
                    product_url = "https://www.ajio.com" + product_url
                    
                img_el = await item.query_selector('img')
                image_url = await img_el.get_attribute('src') if img_el else ""
                
                price_el = await item.query_selector('.price')
                price_text = await price_el.inner_text() if price_el else "0"
                price = int(''.join(filter(str.isdigit, price_text)))
                
                mrp_el = await item.query_selector('.orginal-price')
                mrp_text = await mrp_el.inner_text() if mrp_el else "0"
                mrp = int(''.join(filter(str.isdigit, mrp_text)))
                
                discount_el = await item.query_selector('.discount')
                discount_text = await discount_el.inner_text() if discount_el else "0"
                discount = int(''.join(filter(str.isdigit, discount_text))) if discount_text else 0
                
                if not discount and mrp > price > 0:
                    discount = round(((mrp - price) / mrp) * 100)
                    
                if title and product_url and price > 0 and discount > 40:
                    if is_single_product_url(product_url):
                        deals.append(ProductDeal(title, price, mrp, discount, image_url, product_url, "AJIO", category))
            except Exception:
                pass
    except Exception as e:
        print(f"[Matcher] AJIO scrape failed for '{keyword}': {e}")
    return deals

async def scrape_myntra(page, keyword: str, category: str):
    deals = []
    url = f"https://www.myntra.com/{urllib.parse.quote(keyword)}"
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await human_delay()
        await page.evaluate("window.scrollBy(0, 800)")
        await human_delay()
        
        items = await page.query_selector_all('.product-base')
        for item in items[:6]:
            try:
                brand_el = await item.query_selector('.product-brand')
                brand = await brand_el.inner_text() if brand_el else ""
                
                title_el = await item.query_selector('.product-product')
                title = await title_el.inner_text() if title_el else ""
                full_title = f"{brand} {title}".strip()
                
                link_el = await item.query_selector('a')
                product_url = await link_el.get_attribute('href') if link_el else ""
                if product_url and not product_url.startswith('http'):
                    product_url = "https://www.myntra.com/" + product_url.lstrip('/')
                    
                # Playwright gets the picture tag or img
                img_el = await item.query_selector('picture img')
                if not img_el:
                    img_el = await item.query_selector('img')
                image_url = await img_el.get_attribute('src') if img_el else ""
                
                price_el = await item.query_selector('.product-discountedPrice')
                price_text = await price_el.inner_text() if price_el else "0"
                price = int(''.join(filter(str.isdigit, price_text)))
                
                mrp_el = await item.query_selector('.product-strike')
                mrp_text = await mrp_el.inner_text() if mrp_el else "0"
                mrp = int(''.join(filter(str.isdigit, mrp_text)))
                
                discount_el = await item.query_selector('.product-discountPercentage')
                discount_text = await discount_el.inner_text() if discount_el else "0"
                discount = int(''.join(filter(str.isdigit, discount_text.split('%')[0]))) if discount_text else 0
                
                if title and product_url and price > 0 and discount > 40:
                    if is_single_product_url(product_url):
                        deals.append(ProductDeal(full_title, price, mrp, discount, image_url, product_url, "Myntra", category))
            except Exception:
                pass
    except Exception as e:
        print(f"[Matcher] Myntra scrape failed for '{keyword}': {e}")
    return deals

async def match_trends_to_products(trends: list):
    """
    Takes a list of trend dictionaries (from pinterest_trending) and searches retailers.
    Returns a combined list of ProductDeal objects.
    """
    all_deals = []
    print(f"[Matcher] Searching retailers for {len(trends)} trends...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Bypass navigator.webdriver check
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Block unnecessary resources to speed up scraping
        await page.route("**/*", lambda route: route.abort() 
                         if route.request.resource_type in ["font", "media"] else route.continue_())

        for trend in trends:
            kw = trend["keyword"]
            cat = trend["category"]
            print(f"[Matcher] Searching for '{kw}'...")
            
            # Scrape retailers sequentially
            ajio_deals = await scrape_ajio(page, kw, cat)
            all_deals.extend(sorted(ajio_deals, key=lambda x: x.discount_percent, reverse=True)[:3])
            
            myntra_deals = await scrape_myntra(page, kw, cat)
            all_deals.extend(sorted(myntra_deals, key=lambda x: x.discount_percent, reverse=True)[:3])
            
            # (Nykaa, Flipkart, Amazon could be added here following the same pattern)
            # Keeping AJIO and Myntra as primary for fashion/beauty high-profit arbitrage
            
        await browser.close()
        
    print(f"[Matcher] Found {len(all_deals)} deals with >40% discount across all trends.")
    return all_deals
