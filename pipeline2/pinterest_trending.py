import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

from shared.lock_manager import acquire_lock, release_lock
from pipeline2.config import TRENDING_CACHE_FILE, PINTEREST_SESSION_FILE

FALLBACK_KEYWORDS = [
    {"keyword": "cargo pants", "category": "fashion"},
    {"keyword": "ethnic kurta for men", "category": "fashion"},
    {"keyword": "sneakers under 2000", "category": "fashion"},
    {"keyword": "oversized t-shirt", "category": "fashion"},
    {"keyword": "glass skin serum", "category": "beauty"},
    {"keyword": "niacinamide serum", "category": "beauty"},
    {"keyword": "matte lipstick", "category": "beauty"},
    {"keyword": "sunscreen spf 50", "category": "beauty"},
    {"keyword": "minimalist home decor", "category": "home"},
    {"keyword": "ceramic coffee mug", "category": "home"},
    {"keyword": "aesthetic bedsheet", "category": "home"}
]

async def human_delay(min_s: float = 3.0, max_s: float = 8.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def load_session(context):
    if Path(PINTEREST_SESSION_FILE).exists():
        try:
            cookies = json.loads(Path(PINTEREST_SESSION_FILE).read_text())
            await context.add_cookies(cookies)
            return True
        except Exception as e:
            print(f"[Trending] Failed to load cookies: {e}")
    return False

def get_cached_trends():
    if TRENDING_CACHE_FILE.exists():
        try:
            data = json.loads(TRENDING_CACHE_FILE.read_text())
            timestamp = data.get("timestamp", 0)
            # 6 hours TTL = 21600 seconds
            if time.time() - timestamp < 21600:
                print("[Trending] Using cached trending keywords.")
                return data.get("trends", [])
        except Exception:
            pass
    return None

def save_cached_trends(trends):
    data = {
        "timestamp": time.time(),
        "trends": trends
    }
    TRENDING_CACHE_FILE.write_text(json.dumps(data, indent=2))

async def scrape_category(page, url: str, category_name: str) -> list:
    """Scrapes a Pinterest ideas page for trending keywords."""
    print(f"[Trending] Scraping {url}...")
    trends = []
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await human_delay(4, 7)
        
        # Scroll a bit to load pins
        await page.evaluate("window.scrollBy(0, 1000)")
        await human_delay(2, 4)

        # Extract text from h1, h2, h3 and alt tags to find trends
        # Pinterest often uses specific data-test-ids or just h3 for pin titles
        titles = await page.evaluate('''() => {
            let results = new Set();
            // Try to find text that looks like a trend/product
            document.querySelectorAll('h3, h2, h1, [data-test-id="pinTitle"]').forEach(el => {
                if (el.innerText && el.innerText.length > 5 && el.innerText.length < 50) {
                    results.add(el.innerText.trim());
                }
            });
            document.querySelectorAll('img[alt]').forEach(el => {
                let alt = el.getAttribute('alt');
                if (alt && alt.length > 5 && alt.length < 50 && !alt.includes('profile')) {
                    results.add(alt.trim());
                }
            });
            return Array.from(results);
        }''')

        for t in titles:
            # Basic cleanup
            clean = t.lower().replace("pinterest", "").strip()
            if clean and len(clean) > 3:
                trends.append({
                    "keyword": clean,
                    "category": category_name,
                    "source_url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                })
        print(f"[Trending] Found {len(trends)} keywords for {category_name}.")
    except Exception as e:
        print(f"[Trending] Error scraping {url}: {e}")
        
    return trends

async def scrape_pinterest_trending(categories=None):
    """
    Main function to get trending keywords.
    Uses cache, then Playwright scraper, then hardcoded fallbacks.
    """
    cached = get_cached_trends()
    if cached:
        return cached

    print("[Trending] Cache missed/expired. Launching Playwright to scrape Pinterest...")
    trends = []
    lock_file = None
    
    try:
        lock_file = acquire_lock("pinterest.lock")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1280, "height": 900})
            
            await load_session(context)
            page = await context.new_page()

            # Target pages
            targets = [
                ("https://www.pinterest.com/ideas/fashion/", "fashion"),
                ("https://www.pinterest.com/ideas/beauty/", "beauty"),
                ("https://www.pinterest.com/ideas/home-decor/", "home"),
            ]

            for url, cat in targets:
                if categories and cat not in categories:
                    continue
                cat_trends = await scrape_category(page, url, cat)
                trends.extend(cat_trends)
                
            await browser.close()
    except Exception as e:
        print(f"[Trending] Playwright scraping failed: {e}")
    finally:
        if lock_file:
            release_lock(lock_file)

    if not trends:
        print("[Trending] No trends scraped. Using hardcoded FALLBACK_KEYWORDS.")
        trends = []
        for fb in FALLBACK_KEYWORDS:
            fb["scraped_at"] = datetime.now(timezone.utc).isoformat()
            trends.append(fb)

    # Shuffle to ensure variety and cap at 30 trends to process
    random.shuffle(trends)
    selected = trends[:30]
    
    save_cached_trends(selected)
    return selected

if __name__ == "__main__":
    # Test script
    res = asyncio.run(scrape_pinterest_trending())
    print(json.dumps(res, indent=2))
