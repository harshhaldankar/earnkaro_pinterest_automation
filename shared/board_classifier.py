import re
from typing import List, Dict

# Canonical SEO-optimized board names
BOARD_ROUTING = {
    "fashion_men": "Men's Fashion Deals",
    "fashion_women": "Women's Fashion Deals",
    "beauty": "Beauty & Skincare Deals",
    "home": "Home & Kitchen Deals",
    "footwear": "Shoes & Sneaker Deals",
    "accessories": "Watches & Accessories Deals",
    "tech": "Hot Deals India",  # off-niche: one catch-all board
    "health": "Hot Deals India",
    "kids": "Hot Deals India",
    "daily_deals": "Hot Deals India",
    "general": "Hot Deals India",  # fallback
}

# Explicit Board Name Normalization / Mapping Table (handles legacy names and typos)
BOARD_NORMALIZATION_MAP: Dict[str, str] = {
    # 1. Reroute "new" and daily-deal names to the catch-all board
    "new": "Hot Deals India",
    "new deals": "Hot Deals India",
    "daily deals": "Hot Deals India",
    "daily shopping": "Hot Deals India",
    "daily shopping deals india": "Hot Deals India",

    # 2. Fix "Hot deale India" typo to "Hot Deals India"
    "hot deale india": "Hot Deals India",
    "hot deal india": "Hot Deals India",
    "hot deals india": "Hot Deals India",
    "hot deals": "Hot Deals India",
    "general": "Hot Deals India",

    # 3. Fix capitalization for "women's Fashion Deals" -> "Women's Fashion Deals"
    "women's fashion deals": "Women's Fashion Deals",
    "womens fashion deals": "Women's Fashion Deals",
    "women's fashion": "Women's Fashion Deals",
    "womens fashion": "Women's Fashion Deals",

    # 4. Fix missing space for "Shoes &Sneaker Deals" -> "Shoes & Sneaker Deals"
    "shoes &sneaker deals": "Shoes & Sneaker Deals",
    "shoes & sneaker deals": "Shoes & Sneaker Deals",
    "shoes & sneakers deals": "Shoes & Sneaker Deals",
    "shoes &sneakers deals": "Shoes & Sneaker Deals",
    "shoes and sneaker deals": "Shoes & Sneaker Deals",
    "footwear deals": "Shoes & Sneaker Deals",
    "footwear": "Shoes & Sneaker Deals",

    # Other categories normalized
    "men's fashion deals": "Men's Fashion Deals",
    "mens fashion deals": "Men's Fashion Deals",
    "watches & accessories deals": "Watches & Accessories Deals",
    "watches & accessories": "Watches & Accessories Deals",
    "accessories deals": "Watches & Accessories Deals",
    "home & kitchen deals": "Home & Kitchen Deals",
    "home & kitchen": "Home & Kitchen Deals",
    "beauty & skincare deals": "Beauty & Skincare Deals",
    "beauty & skincare": "Beauty & Skincare Deals",
    "tech gadgets deals": "Hot Deals India",
    "tech gadgets": "Hot Deals India",
    "health & fitness deals": "Hot Deals India",
    "kids & baby deals": "Hot Deals India",
}

# Dynamic Hashtag mapping per Board Category (3 to 5 relevant hashtags)
CATEGORY_HASHTAGS: Dict[str, List[str]] = {
    # Fashion/Shoes:
    "Shoes & Sneaker Deals": ["#FashionDealsIndia", "#Sneakerhead", "#MyntraSale", "#FootwearSale"],
    "Women's Fashion Deals": ["#FashionDealsIndia", "#MyntraSale", "#OOTDIndia", "#WomensFashionIndia"],
    "Men's Fashion Deals": ["#FashionDealsIndia", "#MyntraSale", "#MensFashionIndia", "#StreetwearIndia"],
    
    "Watches & Accessories Deals": ["#WatchesIndia", "#AccessoriesIndia", "#MyntraSale", "#FashionDealsIndia"],

    # Home/Kitchen:
    "Home & Kitchen Deals": ["#HomeDecorIndia", "#AmazonFinds", "#KitchenHacks", "#IndianHomeEssentials"],
    
    # General / Daily Deals:
    "Daily Shopping Deals India": ["#LootDealsIndia", "#DiscountCodes", "#ShoppingIndia", "#DailyDeals"],
    "Hot Deals India": ["#LootDealsIndia", "#DiscountCodes", "#ShoppingIndia", "#DealOfTheDay"],
    
    # Beauty/Skincare:
    "Beauty & Skincare Deals": ["#BeautyDealsIndia", "#SkincareRoutine", "#NykaaSale", "#GlowUpIndia"],
    
    # Tech/Gadgets:
    "Tech Gadgets Deals": ["#TechDealsIndia", "#AmazonFinds", "#GadgetLovers", "#ElectronicsSale"],
    
    # Health & Fitness / Kids:
    "Health & Fitness Deals": ["#FitnessIndia", "#HealthyLiving", "#WorkoutDeals", "#DiscountCodes"],
    "Kids & Baby Deals": ["#BabyCareIndia", "#KidsFashionIndia", "#ParentingHacks", "#LootDealsIndia"],
}

CALL_TO_ACTION = "Click the link to get this deal before it expires!"

def normalize_board_name(board_name: str) -> str:
    """
    Normalizes any board name or alias into a canonical, SEO-friendly Pinterest board name.
    Fixes typos like 'Hot deale India', 'women's Fashion Deals', 'Shoes &Sneaker Deals', and reroutes 'new'.
    """
    if not board_name:
        return "Hot Deals India"
    
    key = board_name.strip().lower()
    if key in BOARD_NORMALIZATION_MAP:
        return BOARD_NORMALIZATION_MAP[key]
    
    # Fallback to smart casing if already well formed
    for canonical in BOARD_ROUTING.values():
        if key == canonical.lower():
            return canonical
            
    return "Hot Deals India"

def get_category_hashtags(board_name: str) -> List[str]:
    """
    Returns 3 to 5 targeted, SEO-friendly hashtags for the given board.
    """
    canonical_board = normalize_board_name(board_name)
    
    # Match specific board hashtags
    if canonical_board in CATEGORY_HASHTAGS:
        return CATEGORY_HASHTAGS[canonical_board]
        
    # Categorical heuristics fallback
    b_lower = canonical_board.lower()
    if any(k in b_lower for k in ["fashion", "shoe", "sneaker", "clothing", "wear"]):
        return ["#FashionDealsIndia", "#Sneakerhead", "#MyntraSale"]
    elif any(k in b_lower for k in ["home", "kitchen", "decor"]):
        return ["#HomeDecorIndia", "#AmazonFinds", "#KitchenHacks"]
    elif any(k in b_lower for k in ["beauty", "skin", "cosmetic"]):
        return ["#BeautyDealsIndia", "#SkincareRoutine", "#NykaaSale"]
    elif any(k in b_lower for k in ["tech", "gadget", "phone", "electronics"]):
        return ["#TechDealsIndia", "#AmazonFinds", "#GadgetLovers"]
        
    return ["#LootDealsIndia", "#DiscountCodes", "#ShoppingIndia"]

def build_enhanced_description(
    raw_desc: str,
    board_name: str,
    raw_title: str = "",
    cta: str = CALL_TO_ACTION,
    max_length: int = 500
) -> str:
    """
    Constructs an SEO-optimized Pinterest pin description:
    1. Clean product description/details without raw URLs or HTML
    2. Exact CTA string: 'Click the link to get this deal before it expires!'
    3. 3-5 category hashtags injected dynamically
    4. Truncates safely under max_length (500 chars limit for Pinterest)
    """
    # 1. Clean description
    clean_text = raw_desc or raw_title or "Exclusive deal on top brand!"
    # Strip existing HTML tags
    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
    # Strip existing raw URLs (they belong in the link payload, not description)
    clean_text = re.sub(r'https?://[^\s]+', '', clean_text)
    # Normalize excessive whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # 2. Get category hashtags
    hashtags = get_category_hashtags(board_name)
    hashtag_str = " ".join(hashtags)
    
    # 3. Assemble components
    # Structure:
    # {clean_text}
    # 
    # Click the link to get this deal before it expires!
    # 
    # #Tag1 #Tag2 #Tag3
    cta_and_tags = f"\n\n{cta}\n\n{hashtag_str}"
    
    available_chars_for_text = max_length - len(cta_and_tags)
    if available_chars_for_text < 30:
        # If very tight, prioritize CTA + tags
        desc_core = clean_text[:max(10, available_chars_for_text)].rstrip()
    elif len(clean_text) > available_chars_for_text:
        desc_core = clean_text[:available_chars_for_text - 3].rstrip() + "..."
    else:
        desc_core = clean_text
        
    final_desc = f"{desc_core}{cta_and_tags}".strip()
    return final_desc

def classify_category(title: str, domain: str = "") -> str:
    """
    Classifies a product into a Pinterest board category based on its title and domain.
    Returns the mapped board name from BOARD_ROUTING.
    """
    title_lower = title.lower()
    domain_lower = domain.lower()
    
    # 1. Footwear
    if re.search(r'\b(' + '|'.join(["shoe", "sneaker", "sandal", "crocs", "footwear", "boots", "slippers", "clogs", "loafers", "oxfords", "brogues", "heels", "flats", "mules", "espadrilles", "chukkas", "wellies", "cleats", "plimsolls", "wedges", "flip-flops", "slides", "pumps", "stiletto", "moccasins", "derby", "boat shoes", "sneakers", "trainers", "kolhapuri", "juttis", "mojaris"]) + r')(?:e?s)?\b', title_lower):  # plural-tolerant: "Sandals"
        return BOARD_ROUTING["footwear"]

    # 1b. Smartwatches are gadgets; watches, bags, eyewear and jewellery are accessories
    if re.search(r'\b(smart\s?watch(?:es)?|galaxy watch|apple watch|redmi watch|fitness band|amazfit|fire-boltt|noise colorfit)', title_lower):
        return BOARD_ROUTING["tech"]
    if re.search(r'\b(' + '|'.join(["watch", "analogue", "analog", "chronograph", "sunglass", "eyewear", "spectacle", "wallet", "belt",
                                     "handbag", "bag", "backpack", "rucksack", "sling", "clutch", "tote", "purse", "jewellery",
                                     "jewelry", "necklace", "earring", "bracelet", "bangle", "pendant", "anklet", "mangalsutra",
                                     "cufflink", "jhumka", "nose pin", "hair clip", "scrunchie"]) + r')(?:e?s)?\b', title_lower):
        return BOARD_ROUTING["accessories"]

    # 2. Beauty
    if re.search(r'\b(' + '|'.join(["serum", "cream", "lotion", "makeup", "lipstick", "perfume", "fragrance", "shampoo", "facewash", "sunscreen", "moisturizer", "toner", "cleanser", "foundation", "concealer", "blush", "bronzer", "highlighter", "eyeshadow", "mascara", "eyeliner", "lip gloss", "lip balm", "nail polish", "conditioner", "hair oil", "hair mask", "body wash", "soap", "deodorant", "cologne", "eau de toilette", "eau de parfum", "edt", "edp", "body mist", "deo", "kajal", "face wash", "skincare", "hair serum", "beauty"]) + r')(?:e?s)?\b', title_lower):
        return BOARD_ROUTING["beauty"]
    if any(d in domain_lower for d in ["maccaron", "nykaa", "purplle", "boddess", "plumgoodness", "mamaearth", "sugarcosmetics"]):
        return BOARD_ROUTING["beauty"]
        
    # 3. Home
    if re.search(r'\b(' + '|'.join(["decor", "cushion", "bedsheet", "curtain", "lamp", "cookware", "kitchen", "furniture", "sofa", "table", "chair", "mixer", "blender", "rug", "carpet", "vase", "clock", "pillow", "blanket", "towel", "mattress", "wardrobe", "cabinet", "shelf", "dining", "cutlery", "pan", "pot", "spatula", "oven", "microwave", "home furnishing", "wall art", "planter", "candle", "photo frame", "mirror", "showpiece", "figurine", "idol", "quilt", "dohar", "comforter", "container", "dinner set", "kettle", "bottle", "storage", "doormat", "bed cover", "artificial flower"]) + r')(?:e?s)?\b', title_lower):
        return BOARD_ROUTING["home"]

    # 4. Tech
    if re.search(r'\b(' + '|'.join(["smartphone", "laptop", "tablet", "earbuds", "headphones", "speaker", "smartwatch", "camera", "monitor", "keyboard", "mouse", "router", "power bank", "charger", "cable", "ssd", "hdd", "usb", "flash drive", "gaming console", "tv", "television", "projector", "microphone", "webcam", "drone", "printer", "scanner", "memory card", "processor", "motherboard", "graphics card"]) + r')\b', title_lower):
        return BOARD_ROUTING["tech"]

    # 5. Health
    if re.search(r'\b(' + '|'.join(["protein", "supplement", "vitamin", "dumbbells", "yoga mat", "treadmill", "resistance band", "whey", "creatine", "bcaa", "massager", "weighing scale", "blood pressure", "thermometer", "fitness tracker", "gym bag", "shaker bottle", "jumprope", "kettlebell", "foam roller", "multivitamin", "fish oil", "collagen", "pre-workout", "mass gainer", "glucosamine", "probiotic", "melatonin", "ashwagandha", "biotin"]) + r')\b', title_lower):
        return BOARD_ROUTING["health"]

    # 6. Kids
    if re.search(r'\b(' + '|'.join(["baby", "diaper", "toys", "kids", "toddler", "stroller", "car seat", "cradle", "pacifier", "baby wipe", "formula", "feeding bottle", "baby lotion", "baby powder", "onesie", "romper", "bib", "high chair", "baby monitor", "playgym", "lego", "action figure", "doll", "puzzle", "board game", "tricycle", "scooter", "playpen", "teether", "rattle"]) + r')\b', title_lower):
        return BOARD_ROUTING["kids"]
        
    # 7. Fashion Men vs Women
    if re.search(r'\b(?:men\'?s?|boy|male)\b', title_lower):
        return BOARD_ROUTING["fashion_men"]
    if re.search(r'\b(?:women\'?s?|girls?|female|ladies|kurtis?|kurtas?|sarees?|lehengas?|dress(?:es)?|gowns?|anarkali|tops?|tunics?|leggings|bras?|lingerie|salwar|dupattas?|palazzos?|ethnic wear)\b', title_lower):
        return BOARD_ROUTING["fashion_women"]
    # Untagged shirts, polos, chinos and jeans in these channels are almost always men's
    if re.search(r'\b(?:shirts?|t-shirts?|tshirts?|polos?|chinos?|trousers?|jeans|blazers?|hoodies?|jackets?|cargos?|joggers?)\b', title_lower):
        return BOARD_ROUTING["fashion_men"]
        
    # Broad fashion fallback
    if re.search(r'\b(' + '|'.join(["shirt", "t-shirt", "jeans", "trouser", "jacket", "sweater", "hoodie", "apparel", "raincoat", "windcheater", "polo", "sweatshirt", "cardigan", "blazer", "coat", "shorts", "chinos", "cargo", "denim", "kurta", "kurti", "jumpsuit", "coord", "suit"]) + r')\b', title_lower):
        return BOARD_ROUTING["general"]

    return BOARD_ROUTING["general"]


# Website sections, in menu order: the same split as the Pinterest boards.
# Boards outside the niche (tech, health, kids, general) show under "More".
SITE_SECTIONS = [
    ("women", "Women", "Women's Fashion Deals"),
    ("men", "Men", "Men's Fashion Deals"),
    ("footwear", "Footwear", "Shoes & Sneaker Deals"),
    ("accessories", "Watches & Accessories", "Watches & Accessories Deals"),
    ("beauty", "Beauty", "Beauty & Skincare Deals"),
    ("home", "Home", "Home & Kitchen Deals"),
]


def site_section(title: str) -> tuple:
    """(slug, label) of the website section for a deal."""
    board = classify_category(title)
    for slug, label, b in SITE_SECTIONS:
        if b == board:
            return slug, label
    return "more", "More"
