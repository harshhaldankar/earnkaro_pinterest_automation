"""
pinterest_rss_publisher.py — Pulls RSS feed, processes affiliate deals,
normalizes boards, enhances descriptions with CTAs & hashtags, and publishes
pins using the Pinterest API (v5).

Features implemented per specification:
1. Board Name Mapping Logic:
   - "new" -> "Daily Shopping Deals India"
   - "Hot deale India" -> "Hot Deals India"
   - "women's Fashion Deals" -> "Women's Fashion Deals"
   - "Shoes &Sneaker Deals" -> "Shoes & Sneaker Deals"
2. Description Payload Enhancement:
   - Exact Call to Action string appended:
     "Click the link to get this deal before it expires!"
3. Dynamic Hashtag Injection:
   - 3 to 5 relevant hashtags mapped to each category:
     * Fashion/Shoes: #FashionDealsIndia #Sneakerhead #MyntraSale #FootwearSale
     * Home/Kitchen: #HomeDecorIndia #AmazonFinds #KitchenHacks #IndianHomeEssentials
     * General/Daily Deals: #LootDealsIndia #DiscountCodes #ShoppingIndia #DailyDeals
     * Beauty/Skincare: #BeautyDealsIndia #SkincareRoutine #NykaaSale #GlowUpIndia
     * Tech/Gadgets: #TechDealsIndia #AmazonFinds #GadgetLovers #ElectronicsSale
4. Robust string manipulations and Pinterest API v5 JSON payload construction.
"""

import os
import re
import json
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any
import requests
from dotenv import load_dotenv

load_dotenv()

# ── CONFIGURATION & CONSTANTS ───────────────────────────────────────────────

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
DEFAULT_RSS_FEED = "https://harshhaldankar.github.io/Getyourdeal/rss.xml"
EXACT_CTA_STRING = "Click the link to get this deal before it expires!"

# 1. BOARD NAME MAPPING TABLE
# Maps incoming board names / categories (including typos and legacy names)
# to canonical, SEO-friendly board names.
BOARD_NAME_MAPPING: Dict[str, str] = {
    # ── Requested mappings / fixes ──────────────────────────────────────────
    "new": "Daily Shopping Deals India",
    "hot deale india": "Hot Deals India",
    "women's fashion deals": "Women's Fashion Deals",
    "shoes &sneaker deals": "Shoes & Sneaker Deals",
    
    # Common variations and typos
    "shoes & sneaker deals": "Shoes & Sneaker Deals",
    "shoes and sneaker deals": "Shoes & Sneaker Deals",
    "shoes & sneakers deals": "Shoes & Sneaker Deals",
    "footwear": "Shoes & Sneaker Deals",
    
    "womens fashion deals": "Women's Fashion Deals",
    "women's fashion": "Women's Fashion Deals",
    
    "hot deal india": "Hot Deals India",
    "hot deals": "Hot Deals India",
    "hot deals india": "Hot Deals India",
    "daily shopping deals india": "Daily Shopping Deals India",
    "daily deals": "Daily Shopping Deals India",
    
    # Other standard store categories
    "men's fashion deals": "Men's Fashion Deals",
    "mens fashion deals": "Men's Fashion Deals",
    "home & kitchen deals": "Home & Kitchen Deals",
    "home & kitchen": "Home & Kitchen Deals",
    "beauty & skincare deals": "Beauty & Skincare Deals",
    "beauty & skincare": "Beauty & Skincare Deals",
    "tech gadgets deals": "Tech Gadgets Deals",
    "tech gadgets": "Tech Gadgets Deals",
    "health & fitness deals": "Health & Fitness Deals",
    "kids & baby deals": "Kids & Baby Deals",
    "general": "Hot Deals India",
}

# Optional: Hardcoded / Environment Board IDs for Pinterest API v5.
# If your Pinterest account uses specific alphanumeric Board IDs (e.g. "123456789012345"),
# define them in your .env as PINTEREST_BOARD_ID_<CATEGORY> or populate this dict.
DEFAULT_BOARD_IDS: Dict[str, str] = {
    "Daily Shopping Deals India": os.getenv("BOARD_ID_DAILY_SHOPPING", ""),
    "Hot Deals India": os.getenv("BOARD_ID_HOT_DEALS", ""),
    "Women's Fashion Deals": os.getenv("BOARD_ID_WOMENS_FASHION", ""),
    "Men's Fashion Deals": os.getenv("BOARD_ID_MENS_FASHION", ""),
    "Shoes & Sneaker Deals": os.getenv("BOARD_ID_SHOES_SNEAKERS", ""),
    "Home & Kitchen Deals": os.getenv("BOARD_ID_HOME_KITCHEN", ""),
    "Beauty & Skincare Deals": os.getenv("BOARD_ID_BEAUTY_SKINCARE", ""),
    "Tech Gadgets Deals": os.getenv("BOARD_ID_TECH_GADGETS", ""),
    "Health & Fitness Deals": os.getenv("BOARD_ID_HEALTH_FITNESS", ""),
    "Kids & Baby Deals": os.getenv("BOARD_ID_KIDS_BABY", ""),
}

# 3. DYNAMIC HASHTAG MAPPING TABLE (3 to 5 targeted hashtags per category)
CATEGORY_HASHTAGS: Dict[str, List[str]] = {
    # Fashion & Shoes
    "Shoes & Sneaker Deals": ["#FashionDealsIndia", "#Sneakerhead", "#MyntraSale", "#FootwearSale"],
    "Women's Fashion Deals": ["#FashionDealsIndia", "#MyntraSale", "#OOTDIndia", "#WomensFashionIndia"],
    "Men's Fashion Deals": ["#FashionDealsIndia", "#MyntraSale", "#MensFashionIndia", "#StreetwearIndia"],
    
    # Home & Kitchen
    "Home & Kitchen Deals": ["#HomeDecorIndia", "#AmazonFinds", "#KitchenHacks", "#IndianHomeEssentials"],
    
    # General & Daily Deals
    "Daily Shopping Deals India": ["#LootDealsIndia", "#DiscountCodes", "#ShoppingIndia", "#DailyDeals"],
    "Hot Deals India": ["#LootDealsIndia", "#DiscountCodes", "#ShoppingIndia", "#DealOfTheDay"],
    
    # Beauty & Skincare
    "Beauty & Skincare Deals": ["#BeautyDealsIndia", "#SkincareRoutine", "#NykaaSale", "#GlowUpIndia"],
    
    # Tech & Gadgets
    "Tech Gadgets Deals": ["#TechDealsIndia", "#AmazonFinds", "#GadgetLovers", "#ElectronicsSale"],
    
    # Health & Kids
    "Health & Fitness Deals": ["#FitnessIndia", "#HealthyLiving", "#WorkoutDeals", "#DiscountCodes"],
    "Kids & Baby Deals": ["#BabyCareIndia", "#KidsFashionIndia", "#ParentingHacks", "#LootDealsIndia"],
}


# ── LOGIC IMPLEMENTATIONS ──────────────────────────────────────────────────

def normalize_board_name(raw_name: str) -> str:
    """
    Reroutes and normalizes incoming board names or categories.
    Handles typos, capitalization, and spacing issues.
    """
    if not raw_name or not str(raw_name).strip():
        return "Hot Deals India"
        
    cleaned = str(raw_name).strip().lower()
    
    # Direct lookup in normalization table
    if cleaned in BOARD_NAME_MAPPING:
        return BOARD_NAME_MAPPING[cleaned]
        
    # Heuristics for partial matches
    if "shoe" in cleaned or "sneaker" in cleaned or "footwear" in cleaned:
        return "Shoes & Sneaker Deals"
    if "women" in cleaned:
        return "Women's Fashion Deals"
    if "men" in cleaned:
        return "Men's Fashion Deals"
    if "home" in cleaned or "kitchen" in cleaned:
        return "Home & Kitchen Deals"
    if "beauty" in cleaned or "skincare" in cleaned:
        return "Beauty & Skincare Deals"
    if "tech" in cleaned or "gadget" in cleaned:
        return "Tech Gadgets Deals"
    if "new" in cleaned:
        return "Daily Shopping Deals India"
        
    return "Hot Deals India"


def get_category_hashtags(board_name: str) -> List[str]:
    """
    Returns 3 to 5 relevant hashtags mapped to the given category/board.
    """
    canonical_board = normalize_board_name(board_name)
    if canonical_board in CATEGORY_HASHTAGS:
        return CATEGORY_HASHTAGS[canonical_board]
        
    # Fallback to general hashtags
    return ["#LootDealsIndia", "#DiscountCodes", "#ShoppingIndia"]


def build_pin_description(
    raw_desc: str,
    board_name: str,
    raw_title: str = "",
    cta: str = EXACT_CTA_STRING,
    max_length: int = 500
) -> str:
    """
    Modifies and enhances the pin description payload:
    - Cleans raw RSS text (strips raw HTML tags and long naked URLs)
    - Appends the exact Call to Action string
    - Injects 3 to 5 dynamic hashtags
    - Ensures total length stays safely within Pinterest's 500 characters limit
    """
    # 1. Clean raw description text
    text = raw_desc or raw_title or "Check out this curated deal!"
    # Strip HTML tags like <p>, <br>, <strong>
    text = re.sub(r'<[^>]+>', ' ', text)
    # Strip existing naked URLs from the body text (the URL goes into the 'link' parameter)
    text = re.sub(r'https?://[^\s]+', '', text)
    # Collapse multiple whitespaces and trim
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 2. Get category hashtags
    hashtags = get_category_hashtags(board_name)
    hashtag_str = " ".join(hashtags)
    
    # 3. Construct description with exact CTA and hashtags
    # Suffix to append: "\n\nClick the link to get this deal before it expires!\n\n#Tag1 #Tag2 #Tag3"
    suffix = f"\n\n{cta}\n\n{hashtag_str}"
    
    available_chars = max_length - len(suffix)
    if available_chars <= 20:
        desc_core = text[:max(10, available_chars)].rstrip()
    elif len(text) > available_chars:
        desc_core = text[:available_chars - 3].rstrip() + "..."
    else:
        desc_core = text
        
    final_description = f"{desc_core}{suffix}".strip()
    return final_description


def extract_media_and_link(item_elem: ET.Element) -> Tuple[str, str]:
    """
    Extracts image URL and destination affiliate link from an RSS <item> element.
    Handles standard RSS, Media RSS namespaces, and custom tags.
    """
    link = ""
    image_url = ""
    
    # 1. Affiliate / Destination link
    affiliate_tag = item_elem.find("affiliate_link")
    if affiliate_tag is not None and affiliate_tag.text:
        link = affiliate_tag.text.strip()
    else:
        link_tag = item_elem.find("link")
        if link_tag is not None and link_tag.text:
            link = link_tag.text.strip()
            
    # 2. Image URL (check <image_url>, <enclosure>, or <media:content>)
    img_tag = item_elem.find("image_url")
    if img_tag is not None and img_tag.text:
        image_url = img_tag.text.strip()
        
    if not image_url:
        enclosure = item_elem.find("enclosure")
        if enclosure is not None and enclosure.get("url"):
            enclosure_type = enclosure.get("type", "")
            if "image" in enclosure_type or not image_url:
                image_url = enclosure.get("url", "").strip()
                
    if not image_url:
        # Check Media RSS namespace
        for child in item_elem:
            if child.tag.endswith("content") and child.get("url"):
                if child.get("medium") == "image" or "image" in child.get("type", ""):
                    image_url = child.get("url", "").strip()
                    break
            elif child.tag.endswith("thumbnail") and child.get("url"):
                image_url = child.get("url", "").strip()
                break

    return link, image_url


def build_pinterest_payload(
    title: str,
    raw_description: str,
    destination_link: str,
    image_url: str,
    raw_board: str,
    board_id_map: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Constructs the final Pinterest API (v5) JSON payload:
    - Normalizes the board name
    - Resolves the board_id (or falls back to board name/default ID)
    - Formats title (max 100 chars)
    - Enhances description with CTA and dynamic hashtags (max 500 chars)
    - Sets up media_source with image_url
    """
    # 1. Normalize board name
    canonical_board = normalize_board_name(raw_board)
    
    # 2. Resolve board ID (API v5 requires a board_id string)
    board_map = board_id_map or DEFAULT_BOARD_IDS
    board_id = board_map.get(canonical_board, "") or os.getenv("PINTEREST_DEFAULT_BOARD_ID", "")
    
    # 3. Clean title (Pinterest title limit is 100 chars)
    clean_title = re.sub(r'<[^>]+>', '', title or "Hot Shopping Deal").strip()
    clean_title = re.sub(r'\s+', ' ', clean_title)
    if len(clean_title) > 100:
        clean_title = clean_title[:97] + "..."
        
    # 4. Enhance description with exact CTA and dynamic hashtags
    enhanced_desc = build_pin_description(
        raw_desc=raw_description,
        board_name=canonical_board,
        raw_title=clean_title,
        cta=EXACT_CTA_STRING,
        max_length=500
    )
    
    # 5. Build Pinterest API v5 Payload
    payload: Dict[str, Any] = {
        "title": clean_title,
        "description": enhanced_desc,
        "link": destination_link,
        "board_id": board_id if board_id else canonical_board,
        "media_source": {
            "source_type": "image_url",
            "url": image_url
        }
    }
    
    return payload


# ── RSS PROCESSING & API EXECUTION ─────────────────────────────────────────

def parse_rss_feed(source: str) -> List[Dict[str, Any]]:
    """
    Loads and parses an RSS feed from a URL, local file path, or XML string.
    Returns a list of structured item dictionaries.
    """
    if source.startswith("http://") or source.startswith("https://"):
        response = requests.get(source, timeout=15)
        response.raise_for_status()
        xml_content = response.content
    elif os.path.exists(source):
        with open(source, "rb") as f:
            xml_content = f.read()
    else:
        xml_content = source.encode("utf-8") if isinstance(source, str) else source

    root = ET.fromstring(xml_content)
    channel = root.find("channel")
    if channel is None:
        channel = root

    items = []
    for item in channel.findall("item"):
        title = item.findtext("title", "").strip()
        description = item.findtext("description", "").strip()
        category = item.findtext("category", "") or item.findtext("board", "")
        link, image_url = extract_media_and_link(item)
        
        items.append({
            "title": title,
            "description": description,
            "category": category,
            "link": link,
            "image_url": image_url
        })
        
    return items


def publish_pin_to_pinterest_api(
    payload: Dict[str, Any],
    access_token: str,
    dry_run: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Executes the POST request to the Pinterest API v5 /pins endpoint.
    """
    if dry_run:
        print(f"[DRY-RUN] Pinterest API Payload:\n{json.dumps(payload, indent=2)}")
        return True, {"id": "dry_run_pin_id", "status": "simulated"}

    headers = {
        "Authorization": f"Bearer {access_token.strip()}",
        "Content-Type": "application/json"
    }

    url = f"{PINTEREST_API_BASE}/pins"
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        
        if response.status_code in (200, 201):
            res_data = response.json()
            pin_id = res_data.get("id", "unknown")
            print(f"  [SUCCESS] Pin published! Pin ID: {pin_id}")
            return True, res_data
        else:
            print(f"  [ERROR] Pinterest API returned status {response.status_code}: {response.text}")
            return False, {"status_code": response.status_code, "error": response.text}
            
    except Exception as e:
        print(f"  [EXCEPTION] Failed to post pin: {e}")
        return False, {"error": str(e)}


def process_rss_and_publish_pins(
    rss_source: str = DEFAULT_RSS_FEED,
    access_token: Optional[str] = None,
    board_id_map: Optional[Dict[str, str]] = None,
    limit: int = 10,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Full pipeline runner:
    1. Pulls RSS feed
    2. Maps boards & normalizes typos ('new', 'Hot deale India', etc.)
    3. Builds descriptions with exact CTA and dynamic hashtags
    4. Constructs Pinterest API payload
    5. Publishes to Pinterest API
    """
    token = access_token or os.getenv("PINTEREST_ACCESS_TOKEN", "")
    if not token and not dry_run:
        print("[WARN] No PINTEREST_ACCESS_TOKEN found. Defaulting to dry_run mode.")
        dry_run = True

    print(f"\n=======================================================")
    print(f"  PINTEREST RSS PUBLISHER")
    print(f"  Feed Source: {rss_source}")
    print(f"  Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE POSTING'}")
    print(f"  Limit: {limit} items")
    print(f"=======================================================\n")

    items = parse_rss_feed(rss_source)
    print(f"Loaded {len(items)} items from RSS feed.")

    results = []
    processed_count = 0

    for idx, item in enumerate(items, 1):
        if processed_count >= limit:
            break

        title = item["title"]
        raw_board = item["category"]
        link = item["link"]
        image = item["image_url"]
        raw_desc = item["description"]

        if not link or not image:
            print(f"[{idx}] Skipping '{title[:40]}...' (missing link or image)")
            continue

        # Build final payload with all required string manipulations
        payload = build_pinterest_payload(
            title=title,
            raw_description=raw_desc,
            destination_link=link,
            image_url=image,
            raw_board=raw_board,
            board_id_map=board_id_map
        )

        canonical_board = normalize_board_name(raw_board)
        print(f"[{idx}] Routing: '{raw_board}' -> '{canonical_board}'")
        print(f"      Title: {payload['title'][:60]}")
        print(f"      Hashtags: {' '.join(get_category_hashtags(canonical_board))}")

        success, res = publish_pin_to_pinterest_api(payload, token, dry_run=dry_run)
        results.append({
            "title": title,
            "board": canonical_board,
            "success": success,
            "response": res,
            "payload": payload
        })

        processed_count += 1

    print(f"\n[SUMMARY] Processed {processed_count} items. Successful: {sum(1 for r in results if r['success'])}")
    return results


# ── TEST & CLI EXECUTION ───────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Process RSS feed and publish pins via Pinterest API")
    parser.add_argument("--feed", default=DEFAULT_RSS_FEED, help="URL or path to RSS XML feed")
    parser.add_argument("--limit", type=int, default=5, help="Max items to process")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview payload without making API calls")
    args = parser.parse_args()

    process_rss_and_publish_pins(
        rss_source=args.feed,
        limit=args.limit,
        dry_run=args.dry_run
    )
