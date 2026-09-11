
import sys

with open("telegram_watcher.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the is_single_product_url function to be stricter with Myntra and Ajio
old_func = """def is_single_product_url(url: str) -> bool:"""
new_func = """def is_single_product_url(url: str) -> bool:
    url_lower = url.lower()
    # Sneaky Myntra/Ajio/Nykaa category patterns
    if "myntra.com" in url_lower:
        if "/shop/" in url_lower or "sale" in url_lower or not "/buy" in url_lower:
            # Most single products on myntra have /buy in the URL
            pass 
            # Actually, myntra products often end with /buy, let us just block generic words
        if any(bad in url_lower for bad in ["/shop/", "/hair-care", "/personal-care", "/women-", "/men-", "/clothing"]):
            return False
    """

# We just insert a regex check for category words in the existing function
hook = """def is_single_product_url(url: str) -> bool:
    url_lower = url.lower()
    
    # Block sneaky category URLs (especially Myntra/Nykaa/Ajio)
    category_keywords = [
        "/shop/", "/c/", "/s/", "search", "category", "collections",
        "hair-care", "personal-care", "skin-care", "top-wear", "bottom-wear",
        "women-clothing", "men-clothing", "sale", "store"
    ]
    if any(keyword in url_lower for keyword in category_keywords):
        return False
"""

if "category_keywords =" not in content:
    content = content.replace("def is_single_product_url(url: str) -> bool:", hook)

with open("telegram_watcher.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patched URL firewall")

