import re

BOARD_ROUTING = {
    "fashion_men": "Men's Fashion Deals",
    "fashion_women": "Women's Fashion Deals",
    "beauty": "Beauty & Skincare Deals",
    "home": "Home & Kitchen Deals",
    "footwear": "Shoes & Sneaker Deals",
    "tech": "Tech Gadgets Deals",
    "health": "Health & Fitness Deals",
    "kids": "Kids & Baby Deals",
    "general": "Hot Deals India",  # fallback
}

def classify_category(title: str, domain: str = "") -> str:
    """
    Classifies a product into a Pinterest board category based on its title and domain.
    Returns the mapped board name from BOARD_ROUTING.
    """
    title_lower = title.lower()
    domain_lower = domain.lower()
    
    # 1. Footwear
    if re.search(r'\b(' + '|'.join(["shoe", "sneaker", "sandal", "crocs", "footwear", "boots", "slippers", "clogs", "loafers", "oxfords", "brogues", "heels", "flats", "mules", "espadrilles", "chukkas", "wellies", "cleats", "plimsolls", "wedges", "flip-flops", "slides", "pumps", "stiletto", "moccasins", "derby", "boat shoes", "sneakers", "trainers"]) + r')\b', title_lower):
        return BOARD_ROUTING["footwear"]
        
    # 2. Beauty
    if re.search(r'\b(' + '|'.join(["serum", "cream", "lotion", "makeup", "lipstick", "perfume", "fragrance", "shampoo", "facewash", "sunscreen", "moisturizer", "toner", "cleanser", "foundation", "concealer", "blush", "bronzer", "highlighter", "eyeshadow", "mascara", "eyeliner", "lip gloss", "lip balm", "nail polish", "conditioner", "hair oil", "hair mask", "body wash", "soap", "deodorant", "cologne"]) + r')\b', title_lower):
        return BOARD_ROUTING["beauty"]
    if any(d in domain_lower for d in ["maccaron", "nykaa", "purplle", "boddess", "plumgoodness", "mamaearth", "sugarcosmetics"]):
        return BOARD_ROUTING["beauty"]
        
    # 3. Home
    if re.search(r'\b(' + '|'.join(["decor", "cushion", "bedsheet", "curtain", "lamp", "cookware", "kitchen", "furniture", "sofa", "table", "chair", "mixer", "blender", "rug", "carpet", "vase", "clock", "pillow", "blanket", "towel", "mattress", "wardrobe", "cabinet", "shelf", "dining", "cutlery", "pan", "pot", "spatula", "oven", "microwave"]) + r')\b', title_lower):
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
    # If explicit keywords exist
    if re.search(r'\b(?:men\'?s?|boy|male)\b', title_lower):
        return BOARD_ROUTING["fashion_men"]
    if re.search(r'\b(?:women\'?s?|girl|female|kurti|saree|lehenga|dress|gown)\b', title_lower):
        return BOARD_ROUTING["fashion_women"]
        
    # Broad fashion fallback
    if re.search(r'\b(' + '|'.join(["shirt", "t-shirt", "jeans", "trouser", "jacket", "sweater", "hoodie", "apparel", "raincoat", "windcheater", "polo", "sweatshirt", "cardigan", "blazer", "coat", "shorts", "chinos", "cargo", "denim", "kurta", "kurti", "jumpsuit", "coord", "suit"]) + r')\b', title_lower):
        # It's fashion, but unclear if men or women. Defaulting to general or try to guess.
        # Most generic fashion can go to general if not explicitly gendered.
        return BOARD_ROUTING["general"]

    return BOARD_ROUTING["general"]
