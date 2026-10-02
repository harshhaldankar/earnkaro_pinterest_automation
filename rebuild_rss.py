"""
rebuild_rss.py — Rebuilds docs/rss.xml cleanly from deals_data.json:
- Filters out category links, bad URLs, and fallback screenshots
- Pairs deals with matching dynamic UGC video reels and formats <enclosure type="video/mp4">
- Sets <instagram_eligible>true</instagram_eligible> and consistent GUIDs
- Auto-deploys updated rss.xml to harshhaldankar/Getyourdeal repository in real time if deploy token is available
"""
import json
import os
import glob
import base64
import requests
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.dom import minidom
from dotenv import load_dotenv

load_dotenv()

RSS_FILE = "docs/rss.xml"

def deploy_rss_to_getyourdeal_api(xml_content: str):
    """Directly pushes updated rss.xml to Getyourdeal via GitHub REST API (no git clone required)."""
    token = os.getenv("WEBSITE_DEPLOY_TOKEN") or os.getenv("DEPLOY_TOKEN")
    if not token:
        return
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        repo_url = "https://api.github.com/repos/harshhaldankar/Getyourdeal/contents/rss.xml"
        r_get = requests.get(repo_url, headers=headers, timeout=10)
        sha = r_get.json().get("sha") if r_get.status_code == 200 else None
        
        encoded_content = base64.b64encode(xml_content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": f"bot: Auto-sync fresh RSS feed with video enclosures {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "content": encoded_content
        }
        if sha:
            payload["sha"] = sha
            
        r_put = requests.put(repo_url, headers=headers, json=payload, timeout=12)
        if r_put.status_code in [200, 201]:
            print("  [DEPLOY API] Live Getyourdeal/rss.xml updated via GitHub API in real time!")
        else:
            print(f"  [DEPLOY API WARN] Status {r_put.status_code}: {r_put.text[:100]}")
    except Exception as e:
        print(f"  [DEPLOY API WARN] Failed to sync to Getyourdeal: {e}")

def rebuild_clean_rss():
    if not os.path.exists("deals_data.json"):
        print("[RSS] deals_data.json not found.")
        return ""

    with open("deals_data.json", "r", encoding="utf-8") as f:
        deals = json.load(f)

    print(f"Loaded {len(deals)} deals from database")

    clean_deals = []
    skipped = []
    for d in deals:
        img = d.get("image_path", "")
        title = d.get("title", "")
        aff = d.get("affiliate_link", "") or d.get("product_url", "")
        
        if not title:
            continue

        # Skip deals with fallback or missing images
        if not img or "fallback_" in img:
            skipped.append(("FALLBACK_IMG", title[:50]))
            continue
            
        # Ensure valid affiliate link is present
        if not aff or not aff.startswith("http"):
            skipped.append(("NO_AFF_LINK", title[:50]))
            continue

        clean_deals.append(d)

    print(f"Clean deals for RSS: {len(clean_deals)}")

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "GetYourDeal Verified Drops Feed"
    ET.SubElement(channel, "link").text = "https://harshhaldankar.github.io/Getyourdeal/"
    ET.SubElement(channel, "description").text = "Curated Indian E-Commerce Deals & Video Reels for Make.com"

    added = 0
    for d in clean_deals[:50]:
        title = d.get("title", "")
        img_path = d.get("image_path", "")
        aff_link = d.get("affiliate_link", "")
        timestamp = d.get("timestamp", "")
        desc = d.get("desc", "")
        
        if img_path.startswith("http"):
            image_url = img_path
        else:
            image_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{img_path}"

        ts_clean = timestamp.replace("-", "").replace(":", "").replace(".", "").replace("T", "_").split("+")[0].split("Z")[0]
        deal_id = f"deal_{ts_clean}"
        website_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{deal_id}/"

        title_lower = title.lower()
        if any(w in title_lower for w in ["watch", "wallet", "shoes", "sneaker", "bag", "handbag"]):
            board = "Accessories & Lifestyle"
        elif any(w in title_lower for w in ["shirt", "jeans", "dress", "top", "tshirt", "kurta", "saree", "blazer", "jacket", "trouser", "pant"]):
            board = "Fashion Deals India"
        elif any(w in title_lower for w in ["cream", "serum", "lotion", "lipstick", "perfume", "soap", "shampoo", "makeup", "skincare", "face wash", "body wash", "wash"]):
            board = "Beauty & Skincare Deals"
        elif any(w in title_lower for w in ["phone", "laptop", "earphone", "headphone", "charger", "camera", "gadget"]):
            board = "Tech Deals India"
        else:
            board = "Hot Deals India"

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = website_url
        ET.SubElement(item, "description").text = desc
        
        try:
            deal_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            pub_date = deal_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        except Exception:
            pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        ET.SubElement(item, "pubDate").text = pub_date
        ET.SubElement(item, "category").text = board
        ET.SubElement(item, "image_url").text = image_url
        ET.SubElement(item, "affiliate_link").text = aff_link
        ET.SubElement(item, "instagram_eligible").text = "true"

        # Match and attach UGC reels
        video_file_path = None
        ts_compact = timestamp.replace("-", "").replace(":", "").replace(".", "").replace("T", "_")[:15]
        for vf in glob.glob("docs/deals/videos/*.mp4"):
            if ts_compact in vf:
                video_file_path = vf
                break

        if not video_file_path:
            if any(w in title_lower for w in ["watch", "timepiece", "analog", "talgo"]):
                cand = "docs/deals/videos/reel_ugc_talgo_watch.mp4"
                if os.path.exists(cand):
                    video_file_path = cand
            elif any(w in title_lower for w in ["face wash", "body wash", "wash", "lotion", "serum", "cream", "skin", "hair", "dove"]):
                cand = "docs/deals/videos/reel_ugc_cocoa_lotion.mp4"
                if os.path.exists(cand):
                    video_file_path = cand

        if video_file_path and os.path.exists(video_file_path):
            v_name = os.path.basename(video_file_path)
            video_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/videos/{v_name}"
            ET.SubElement(item, "video_url").text = video_url
            v_sz = str(os.path.getsize(video_file_path))
            ET.SubElement(item, "enclosure", url=video_url, length=v_sz, type="video/mp4")
        
        guid_base = f"{title}_{timestamp}_{aff_link}"
        guid = hashlib.md5(guid_base.encode()).hexdigest()
        ET.SubElement(item, "guid", isPermaLink="false").text = f"deal_{guid}"
        
        added += 1

    os.makedirs("docs", exist_ok=True)
    xmlstr = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    clean_xml = "\n".join([line for line in xmlstr.split("\n") if line.strip()])
    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(clean_xml)

    print(f"SUCCESS - Clean RSS written to {RSS_FILE} ({added} items)")
    
    # Auto deploy directly to Getyourdeal
    deploy_rss_to_getyourdeal_api(clean_xml)
    return clean_xml

if __name__ == "__main__":
    rebuild_clean_rss()
