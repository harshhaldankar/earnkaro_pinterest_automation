"""
Rebuild rss.xml from scratch using only clean deals_data.json entries.
Removes all fallback images and category deals from the live RSS feed.
"""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.dom import minidom

RSS_FILE = "docs/rss.xml"

# Load clean deals database
with open("deals_data.json", "r", encoding="utf-8") as f:
    deals = json.load(f)

print(f"Loaded {len(deals)} deals from database")

# Filter: only deals with real images (no fallback) and single-product URLs
bad_patterns = [
    '/shop/', 'hair-care', 'personal-care', 'sort=discount',
    'f=Gender', 'f=Brand', 'f=Coupons', 'myntra.com/converse',
    'myntra.com/men', 'myntra.com/women', 'myntra.com/myntra',
    'myntra.com/clothing', 'ajio.com/s/', '/s/min', 'itm_source=banner',
    'linkredirect.in', 'affid=growthte', '/collections', 'category',
    'min70percent', 'men-topwear', 'women-topwear'
]

clean_deals = []
skipped = []
for d in deals:
    img = d.get("image_path", "")
    url = (d.get("product_url", "") + " " + d.get("affiliate_link", "")).lower()
    
    # Skip deals with fallback or empty images
    if not img or "fallback_" in img:
        skipped.append(("FALLBACK_IMG", d.get("title", "")[:50]))
        continue
    
    # Skip category deals
    if any(pat in url for pat in bad_patterns):
        skipped.append(("CATEGORY_URL", d.get("title", "")[:50]))
        continue

    # Skip deals where actual image file has a bad URL pattern
    clean_deals.append(d)

print(f"Skipped {len(skipped)} bad deals:")
for reason, title in skipped[:10]:
    print(f"  [{reason}] {title}")

print(f"Clean deals for RSS: {len(clean_deals)}")

# Build fresh RSS from scratch
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")
ET.SubElement(channel, "title").text = "GetYourDeal Verified Drops Feed"
ET.SubElement(channel, "link").text = "https://harshhaldankar.github.io/Getyourdeal/"
ET.SubElement(channel, "description").text = "Curated Indian E-Commerce Deals & Video Reels for Make.com"

added = 0
for d in clean_deals[:50]:  # Keep top 50
    title = d.get("title", "")
    img_path = d.get("image_path", "")
    aff_link = d.get("affiliate_link", "")
    timestamp = d.get("timestamp", "")
    
    # Build image URL  
    if img_path.startswith("http"):
        image_url = img_path
    else:
        image_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{img_path}"

    # Build deal page URL
    ts_clean = timestamp.replace("-", "").replace(":", "").replace(".", "").replace("T", "_").split("+")[0].split("Z")[0]
    deal_id = f"deal_{ts_clean}"
    website_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{deal_id}/"

    # Try to find board category
    title_lower = title.lower()
    if any(w in title_lower for w in ["watch", "wallet", "shoes", "sneaker", "bag", "handbag"]):
        board = "Accessories & Lifestyle"
    elif any(w in title_lower for w in ["shirt", "jeans", "dress", "top", "tshirt", "kurta", "saree", "blazer", "jacket", "trouser", "pant"]):
        board = "Fashion Deals India"
    elif any(w in title_lower for w in ["cream", "serum", "lotion", "lipstick", "perfume", "soap", "shampoo", "makeup", "skincare"]):
        board = "Beauty & Skincare Deals"
    elif any(w in title_lower for w in ["phone", "laptop", "earphone", "headphone", "charger", "camera", "gadget"]):
        board = "Tech Deals India"
    else:
        board = "Hot Deals India"

    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = website_url
    ET.SubElement(item, "description").text = d.get("desc", "")
    ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    ET.SubElement(item, "category").text = board
    ET.SubElement(item, "board").text = board
    ET.SubElement(item, "image_url").text = image_url
    ET.SubElement(item, "affiliate_link").text = aff_link
    ET.SubElement(item, "instagram_eligible").text = "false"
    added += 1

print(f"Added {added} clean items to RSS")

# Write
os.makedirs("docs", exist_ok=True)
xmlstr = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
clean_xml = "\n".join([line for line in xmlstr.split("\n") if line.strip()])
with open(RSS_FILE, "w", encoding="utf-8") as f:
    f.write(clean_xml)

print(f"SUCCESS - Clean RSS written to {RSS_FILE}")
print("First 3 items in new RSS:")
for d in clean_deals[:3]:
    print(f"  - {d.get('title','')[:60]}")
    print(f"    Image: {d.get('image_path','')[:60]}")
