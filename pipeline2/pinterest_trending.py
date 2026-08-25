import asyncio
import json
import random
import time
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from shared.lock_manager import acquire_lock, release_lock
from pipeline2.config import TRENDING_CACHE_FILE, PINTEREST_SESSION_FILE

FASHION_BEAUTY_SEEDS = [
    'dress', 'kurta', 'shoes', 'lipstick', 'serum', 'saree', 'jeans', 'sneakers',
    'foundation', 'moisturizer', 'jacket', 'watch', 'handbag', 'sunscreen', 'perfume',
    'earrings', 'necklace', 'ring', 'bracelet', 'makeup', 'hair', 'skincare', 'outfit',
    'shirt', 't-shirt', 'pants', 'trousers', 'suit', 'lehenga', 'kurti', 'footwear',
    'style', 'fashion', 'beauty'
]

EVERGREEN_KEYWORDS = [
    "oversized t-shirt", "cargo pants", "sneakers under 2000", "niacinamide serum", 
    "matte lipstick", "foundation", "hair serum", "minimalist home decor", 
    "glass skin serum", "ceramic coffee mug", "aesthetic bedsheet",
    "korean skincare", "wide leg jeans", "tote bag", "silver jewelry",
    "ethnic kurta for men", "denim jacket for women", "white sneakers",
    "salicylic acid face wash", "lip gloss", "eyeliner", "blush palette",
    "hoop earrings", "pendant necklace", "sunglasses for men", "kurti set with dupatta",
    "black formal trousers", "gym wear", "yoga pants", "graphic tees", "polo neck t-shirt"
]

SEASONAL_KEYWORDS = {
    1: ["winter jacket", "thermal wear", "boots", "hoodie", "sweatshirt", "leather jacket", "beanie"],
    2: ["winter jacket", "thermal wear", "boots", "hoodie", "sweatshirt", "cardigan", "muffler"],
    3: ["cotton kurta", "summer dress", "sunglasses", "floral print", "summer outfits", "linen pants"],
    4: ["cotton kurta", "summer dress", "sunglasses", "floral print", "summer outfits", "tank top"],
    5: ["linen shirt", "flip flops", "sunscreen spf 50", "beach wear", "shorts", "swimwear"],
    6: ["linen shirt", "flip flops", "sunscreen spf 50", "beach wear", "shorts", "aloe vera gel"],
    7: ["monsoon jacket", "waterproof shoes", "umbrella", "raincoat", "crocs", "windcheater"],
    8: ["monsoon jacket", "waterproof shoes", "umbrella", "raincoat", "crocs", "waterproof makeup"],
    9: ["festive kurta", "ethnic wear", "gold jewelry", "diwali dress", "saree", "silk kurta"],
    10: ["festive kurta", "ethnic wear", "gold jewelry", "diwali dress", "saree", "lehenga choli"],
    11: ["wedding lehenga", "sherwani", "party wear", "blazer", "suit", "velvet dress"],
    12: ["wedding lehenga", "sherwani", "party wear", "blazer", "suit", "tuxedo"]
}

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

def fetch_duckduckgo_autocomplete(seed):
    keywords = []
    try:
        url = f"https://duckduckgo.com/ac/?q={urllib.parse.quote(seed)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        
        found = []
        for item in data:
            if isinstance(item, dict) and 'phrase' in item:
                phrase = item['phrase'].lower().strip()
                if 3 < len(phrase) < 50:
                    found.append(phrase)
                    
        print(f"[Trending] DDG Autocomplete for '{seed}': Found {len(found)} suggestions")
        keywords.extend(found)
    except Exception as e:
        print(f"[Trending] Error fetching DDG Autocomplete for '{seed}': {e}")
    return keywords

def fetch_google_trends():
    keywords = []
    try:
        url = "https://trends.google.com/trending/rss?geo=IN"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        for item in root.findall(".//item"):
            title = item.find("title")
            if title is not None and title.text:
                keywords.append(title.text.lower().strip())
                
        print(f"[Trending] Google Trends India: Found {len(keywords)} suggestions")
    except Exception as e:
        print(f"[Trending] Error fetching Google Trends: {e}")
    return keywords

def get_fallback_keywords():
    month = datetime.now().month
    seasonals = SEASONAL_KEYWORDS.get(month, [])
    # Weight seasonal keywords higher by adding them multiple times
    all_kws = EVERGREEN_KEYWORDS + seasonals * 3
    random.shuffle(all_kws)
    return all_kws

async def scrape_pinterest_trending(categories=None):
    """
    Main function to get trending keywords.
    Uses cache, then a 3-tier keyword discovery engine.
    """
    cached = get_cached_trends()
    if cached:
        return cached

    print("[Trending] Cache missed/expired. Fetching keywords from 3-tier engine...")
    
    results = []
    seen = set()

    def add_keyword(kw, category, source):
        if kw not in seen:
            seen.add(kw)
            results.append({
                "keyword": kw,
                "category": category,
                "source_url": source,
                "scraped_at": datetime.now(timezone.utc).isoformat()
            })

    # Tier 1: DuckDuckGo Autocomplete
    seeds = [
        'kurta men', 'sneakers', 'serum', 'lipstick shade', 'cargo pants', 
        'ethnic dress', 'hair oil', 'face wash', 'saree', 'watch men',
        'winter jacket', 'denim jacket', 'formal shirt', 'party wear',
        'ethnic wear', 'festival outfits', 'home decor', 'skincare routines', 'gym accessories'
    ]
    # Pick random seeds to ensure variety and not spam
    selected_seeds = random.sample(seeds, k=min(6, len(seeds)))
    for seed in selected_seeds:
        suggests = fetch_duckduckgo_autocomplete(seed)
        for kw in suggests:
            cat = "beauty" if any(b in seed for b in ['serum', 'lipstick', 'hair', 'face wash']) else "fashion"
            add_keyword(kw, cat, "https://duckduckgo.com/ac/")

    # Tier 2: Google Trends India
    trends = fetch_google_trends()
    for kw in trends:
        add_keyword(kw, "trending", "https://trends.google.com/")

    # Tier 3: Curated Seasonal Fallbacks
    fallbacks = get_fallback_keywords()
    for kw in fallbacks:
        cat = "beauty" if any(b in kw for b in ['serum', 'lipstick', 'sunscreen', 'skincare']) else "fashion"
        if any(h in kw for h in ["home", "mug", "bedsheet"]):
            cat = "home"
        add_keyword(kw, cat, "fallback")

    # Filter by category if requested
    if categories:
        results = [r for r in results if r["category"] in categories]

    # Prioritize Tier 1, use Tier 2 (Curated) as padding
    tier1 = [r for r in results if r["source_url"] != "fallback"]
    tier2 = [r for r in results if r["source_url"] == "fallback"]
    
    final_list = tier1.copy()
    if len(final_list) < 40:
        needed = 40 - len(final_list)
        final_list.extend(tier2[:needed])
        
    # Cap at 40 diverse keywords
    final_list = final_list[:40]
    
    # Shuffle for variety
    random.shuffle(final_list)
    
    save_cached_trends(final_list)
    print(f"[Trending] Final selection: {len(final_list)} keywords.")
    return final_list

if __name__ == "__main__":
    # Test script
    res = asyncio.run(scrape_pinterest_trending())
    print(json.dumps(res, indent=2))
