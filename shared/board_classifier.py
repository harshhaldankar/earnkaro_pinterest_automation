import re

BOARD_ROUTING = {
    "fashion_men": "Men's Fashion Deals 👔",
    "fashion_women": "Women's Fashion Deals 👗",
    "beauty": "Beauty & Skincare Deals 💄",
    "home": "Home & Kitchen Deals 🏠",
    "footwear": "Shoes & Sneaker Deals 👟",
    "general": "Hot Deals India 🔥",  # fallback
}

def classify_category(title: str, domain: str = "") -> str:
    """
    Classifies a product into a Pinterest board category based on its title and domain.
    Returns the mapped board name from BOARD_ROUTING.
    """
    title_lower = title.lower()
    domain_lower = domain.lower()
    
    # 1. Footwear
    if any(keyword in title_lower for keyword in ["shoe", "sneaker", "sandal", "crocs", "footwear", "boots", "slippers", "clogs"]):
        return BOARD_ROUTING["footwear"]
        
    # 2. Beauty
    if any(keyword in title_lower for keyword in ["serum", "cream", "lotion", "makeup", "lipstick", "perfume", "fragrance", "shampoo", "facewash", "sunscreen"]):
        return BOARD_ROUTING["beauty"]
    if any(d in domain_lower for d in ["maccaron", "nykaa", "purplle", "boddess"]):
        return BOARD_ROUTING["beauty"]
        
    # 3. Home
    if any(keyword in title_lower for keyword in ["decor", "cushion", "bedsheet", "curtain", "lamp", "cookware", "kitchen", "furniture", "sofa", "table", "chair", "mixer", "blender"]):
        return BOARD_ROUTING["home"]
        
    # 4. Fashion Men vs Women
    # If explicit keywords exist
    if any(keyword in title_lower for keyword in ["men's", "mens", " for men", "boy"]):
        return BOARD_ROUTING["fashion_men"]
    if any(keyword in title_lower for keyword in ["women's", "womens", " for women", "girl", "kurta", "saree", "lehenga", "dress", "gown"]):
        return BOARD_ROUTING["fashion_women"]
        
    # Broad fashion fallback
    if any(keyword in title_lower for keyword in ["shirt", "t-shirt", "jeans", "trouser", "jacket", "sweater", "hoodie", "apparel"]):
        # It's fashion, but unclear if men or women. Defaulting to general or try to guess.
        # Most generic fashion can go to general if not explicitly gendered.
        return BOARD_ROUTING["general"]

    return BOARD_ROUTING["general"]
