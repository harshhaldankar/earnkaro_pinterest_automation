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
    "ethnic kurta for men"
]

SEASONAL_KEYWORDS = {
    1: ["winter jacket", "thermal wear", "boots", "hoodie", "sweatshirt"],
    2: ["winter jacket", "thermal wear", "boots", "hoodie", "sweatshirt"],
    3: ["cotton kurta", "summer dress", "sunglasses", "floral print", "summer outfits"],
    4: ["cotton kurta", "summer dress", "sunglasses", "floral print", "summer outfits"],
    5: ["linen shirt", "flip flops", "sunscreen spf 50", "beach wear", "shorts"],
    6: ["linen shirt", "flip flops", "sunscreen spf 50", "beach wear", "shorts"],
    7: ["monsoon jacket", "waterproof shoes", "umbrella", "raincoat", "crocs"],
    8: ["monsoon jacket", "waterproof shoes", "umbrella", "raincoat", "crocs"],
    9: ["festive kurta", "ethnic wear", "gold jewelry", "diwali dress", "saree"],
    10: ["festive kurta", "ethnic wear", "gold jewelry", "diwali dress", "saree"],
    11: ["wedding lehenga", "sherwani", "party wear", "blazer", "suit"],
    12: ["wedding lehenga", "sherwani", "party wear", "blazer", "suit"]
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

def fetch_google_trends():
    keywords = []
    try:
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        
        for item in root.findall('.//item'):
            title = item.find('title')
            if title is not None and title.text:
                kw = title.text.lower()
                # Check if it matches fashion/beauty seeds
                if any(seed in kw for seed in FASHION_BEAUTY_SEEDS):
                    keywords.append(kw)
        print(f"[Trending] Google Trends: Found {len(keywords)} fashion/beauty keywords")
    except Exception as e:
        print(f"[Trending] Error fetching Google Trends: {e}")
    return keywords

def fetch_pinterest_autocomplete(seed):
    keywords = []
    try:
        data_param = json.dumps({"options":{"query":seed,"scope":"pins"}})
        url = f"https://www.pinterest.com/resource/TypeaheadResource/get/?source_url=/&data={urllib.parse.quote(data_param)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Recursively find strings in 'term' or 'query' keys
        def extract_terms(obj):
            terms = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ['term', 'query', 'title', 'text', 'suggestion'] and isinstance(v, str):
                        if 3 < len(v) < 50:
                            terms.append(v)
                    else:
                        terms.extend(extract_terms(v))
            elif isinstance(obj, list):
                for item in obj:
                    terms.extend(extract_terms(item))
            return terms
            
        found = extract_terms(data)
        
        # Fallback if exact structure parsing failed
        if not found and 'resource_response' in data and 'data' in data['resource_response']:
            res_data = data['resource_response']['data']
            if isinstance(res_data, list):
                for item in res_data:
                    if isinstance(item, str):
                        found.append(item)
                    elif isinstance(item, dict) and 'term' in item:
                        found.append(item['term'])

        found = list(set([t.lower().strip() for t in found]))
        print(f"[Trending] Pinterest Autocomplete for '{seed}': Found {len(found)} suggestions")
        keywords.extend(found)
    except Exception as e:
        print(f"[Trending] Error fetching Pinterest Autocomplete for '{seed}': {e}")
    return keywords

def get_fallback_keywords():
    month = datetime.now().month
    seasonals = SEASONAL_KEYWORDS.get(month, [])
    all_kws = EVERGREEN_KEYWORDS + seasonals
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

    # Tier 1: Google Trends
    gt_keywords = fetch_google_trends()
    for kw in gt_keywords:
        add_keyword(kw, "fashion", "https://trends.google.com/")

    # Tier 2: Pinterest Autocomplete
    seeds = [
        'kurta men', 'sneakers', 'serum', 'lipstick shade', 'cargo pants', 
        'ethnic dress', 'hair oil', 'face wash', 'saree', 'watch men'
    ]
    # Pick a few random seeds to ensure variety and not spam
    selected_seeds = random.sample(seeds, k=min(4, len(seeds)))
    for seed in selected_seeds:
        suggests = fetch_pinterest_autocomplete(seed)
        for kw in suggests:
            cat = "beauty" if any(b in seed for b in ['serum', 'lipstick', 'hair', 'face wash']) else "fashion"
            add_keyword(kw, cat, "https://www.pinterest.com/resource/TypeaheadResource/")

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

    # Prioritize Tier 1 and Tier 2, use Tier 3 as padding
    tier12 = [r for r in results if r["source_url"] != "fallback"]
    tier3 = [r for r in results if r["source_url"] == "fallback"]
    
    final_list = tier12.copy()
    if len(final_list) < 30:
        needed = 30 - len(final_list)
        final_list.extend(tier3[:needed])
        
    # Cap at 30 diverse keywords
    final_list = final_list[:30]
    
    # Shuffle for variety
    random.shuffle(final_list)
    
    save_cached_trends(final_list)
    print(f"[Trending] Final selection: {len(final_list)} keywords.")
    return final_list

if __name__ == "__main__":
    # Test script
    res = asyncio.run(scrape_pinterest_trending())
    print(json.dumps(res, indent=2))
