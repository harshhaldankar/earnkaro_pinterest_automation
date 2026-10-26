"""
rebuild_rss.py — Reconstructs docs/rss.xml with complete fidelity.
Features:
- Full Pinterest & Make.com compatibility (<media:content>, <media:thumbnail>, <enclosure>)
- Strict 1-to-1 matching for real product video reels (Zero mismatched fallbacks)
- Non-video deals receive image enclosure and <instagram_eligible>false</instagram_eligible>
- Auto-deploys updated rss.xml to harshhaldankar/Getyourdeal repository in real time
"""
import json
import os
import re
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
REELS_FILE = "docs/reels.xml"   # Instagram-only feed: every item is a real .mp4 reel

def deploy_rss_to_getyourdeal_api(xml_content: str, filename: str = "rss.xml"):
    """Directly pushes an updated feed to Getyourdeal via GitHub REST API (no git clone required)."""
    token = os.getenv("WEBSITE_DEPLOY_TOKEN") or os.getenv("DEPLOY_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        return
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        repo_url = f"https://api.github.com/repos/harshhaldankar/Getyourdeal/contents/{filename}"
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
            print(f"  [DEPLOY API] Live Getyourdeal/{filename} updated via GitHub API in real time!")
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

        # Ended deals (sold out, price rose, sale over) must not reach Make.com / Instagram
        if d.get("ended"):
            skipped.append(("ENDED", title[:50]))
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

    # Construct RSS with Media RSS namespace
    MEDIA_NS = "http://search.yahoo.com/mrss/"
    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:media", MEDIA_NS)
    
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "GetYourDeal Verified Drops Feed"
    ET.SubElement(channel, "link").text = "https://harshhaldankar.github.io/Getyourdeal/"
    ET.SubElement(channel, "description").text = "Curated Indian E-Commerce Deals & Video Reels for Make.com"

    # Board classifier and description enhancer
    try:
        from shared.board_classifier import classify_category, normalize_board_name, build_enhanced_description
    except Exception:
        classify_category = None
        normalize_board_name = lambda x: x or "Hot Deals India"
        build_enhanced_description = None

    added = 0
    reel_items = []  # -> docs/reels.xml (Instagram): only deals with a real product reel
    for d in clean_deals[:50]:
        title = d.get("title", "")
        img_path = d.get("image_path", "")
        aff_link = d.get("affiliate_link", "")
        timestamp = d.get("timestamp", "")
        desc = d.get("desc", "")
        raw_board = d.get("board") or ""
        
        if img_path.startswith("http"):
            image_url = img_path
        else:
            image_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{img_path}"

        ts_clean = timestamp.replace("-", "").replace(":", "").replace(".", "").replace("T", "_").split("+")[0].split("Z")[0]
        deal_id = f"deal_{ts_clean}"
        website_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/{deal_id}/"

        if raw_board:
            board = normalize_board_name(raw_board)
        elif classify_category:
            try:
                board = normalize_board_name(classify_category(title))
            except Exception:
                board = "Hot Deals India"
        else:
            board = "Hot Deals India"

        # Enhance description with exact CTA and dynamic hashtags
        if build_enhanced_description:
            enhanced_desc = build_enhanced_description(raw_desc=desc, board_name=board, raw_title=title)
        else:
            enhanced_desc = desc

        # Make.com maps this into Pinterest's Title field, which rejects > 100 characters.
        # Use the same keyword-first pin title the Playwright poster uses (capped at 100).
        try:
            from pinterest_poster import generate_seo_pin_content
            feed_title = generate_seo_pin_content(title, desc)[0]
        except Exception:
            feed_title = title
        if len(feed_title) > 100:
            feed_title = feed_title[:99].rstrip() + "…"

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = feed_title
        ET.SubElement(item, "link").text = website_url
        ET.SubElement(item, "description").text = enhanced_desc
        
        try:
            deal_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            pub_date = deal_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        except Exception:
            pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        ET.SubElement(item, "pubDate").text = pub_date
        ET.SubElement(item, "category").text = board
        ET.SubElement(item, "board").text = board
        ET.SubElement(item, "image_url").text = image_url
        ET.SubElement(item, "affiliate_link").text = aff_link

        # Media RSS image tags (Standard for Pinterest, Make.com, Buffer, etc.)
        ET.SubElement(item, f"{{{MEDIA_NS}}}content", url=image_url, medium="image", type="image/jpeg")
        ET.SubElement(item, f"{{{MEDIA_NS}}}thumbnail", url=image_url)

        # ── Video Reel Association (STRICT 1-TO-1 MATCH ONLY) ──
        video_file_path = None
        ts_compact = ts_clean[:15]
        img_stem = os.path.splitext(os.path.basename(img_path))[0].replace("pin_", "").replace("deal_", "")
        
        # Exact reel for this deal first (reel_<deal_id>.mp4). The fuzzy fallbacks below match on
        # date+hour, and Pipeline 2 adds several deals in the same minute — they would all get the
        # first reel found.
        exact = f"docs/deals/videos/reel_{deal_id}.mp4"
        if os.path.exists(exact):
            video_file_path = exact
        else:
            for vf in glob.glob("docs/deals/videos/*.mp4"):
                vf_norm = os.path.basename(vf)
                # reel_<deal_id>.mp4 files belong to exactly one deal; fuzzy-match only legacy names
                if re.match(r"reel_deal_\d{8}_\d{12}", vf_norm):
                    continue
                if img_stem in vf_norm or ts_compact in vf_norm or deal_id in vf_norm or ts_clean[:13] in vf_norm:
                    video_file_path = vf
                    break

        # Calculate local image file size for enclosure
        local_img_file = os.path.join("docs", "deals", img_path) if not img_path.startswith("http") else None
        img_len = str(os.path.getsize(local_img_file)) if (local_img_file and os.path.exists(local_img_file)) else "100000"

        if video_file_path and os.path.exists(video_file_path):
            v_name = os.path.basename(video_file_path)
            video_url = f"https://harshhaldankar.github.io/Getyourdeal/deals/videos/{v_name}"
            v_sz = str(os.path.getsize(video_file_path))
            ET.SubElement(item, "video_url").text = video_url
            ET.SubElement(item, "enclosure", url=video_url, length=v_sz, type="video/mp4")
            ET.SubElement(item, f"{{{MEDIA_NS}}}content", url=video_url, medium="video", type="video/mp4")
            ET.SubElement(item, "instagram_eligible").text = "true"
        else:
            # When no video reel exists, provide the standard Image Enclosure for Pinterest & RSS readers
            ET.SubElement(item, "enclosure", url=image_url, length=img_len, type="image/jpeg")
            ET.SubElement(item, "instagram_eligible").text = "false"
        
        guid_base = f"{title}_{timestamp}_{aff_link}"
        guid = hashlib.md5(guid_base.encode()).hexdigest()
        ET.SubElement(item, "guid", isPermaLink="false").text = f"deal_{guid}"

        if video_file_path == exact:  # product reels only, never legacy screenshot reels
            reel_items.append({"title": feed_title, "link": website_url, "board": board,
                               "video_url": video_url, "video_len": v_sz, "image_url": image_url,
                               "pub_date": pub_date, "guid": f"deal_{guid}"})

        added += 1

    os.makedirs("docs", exist_ok=True)
    xmlstr = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    clean_xml = "\n".join([line for line in xmlstr.split("\n") if line.strip()])
    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(clean_xml)

    print(f"SUCCESS - Clean RSS written to {RSS_FILE} ({added} items)")

    reels_xml = build_reels_feed(reel_items)
    with open(REELS_FILE, "w", encoding="utf-8") as f:
        f.write(reels_xml)
    print(f"SUCCESS - Instagram reels feed written to {REELS_FILE} ({len(reel_items)} reels)")

    # Auto deploy directly to Getyourdeal
    deploy_rss_to_getyourdeal_api(clean_xml)
    deploy_rss_to_getyourdeal_api(reels_xml, "reels.xml")
    return clean_xml


def instagram_caption(feed_title: str, board: str) -> str:
    """'<product> – ₹price (NN% OFF) | Store' -> caption. Instagram captions can't hold links."""
    try:
        from shared.board_classifier import get_category_hashtags
        tags = " ".join(get_category_hashtags(board))
    except Exception:
        tags = "#DealsIndia"
    name, _, offer = feed_title.partition(" – ")
    offer = offer.replace(" | ", " on ")
    return f"{name}\n{offer}\n\n🛍️ Tap the link in bio to shop this deal\n\n{tags} #ReelsIndia #DealsIndia".strip()


def build_reels_feed(reel_items: list) -> str:
    """
    Feed for Make.com's Instagram 'Create a Reel' module: every item's enclosure, video_url and
    media:content are the .mp4, so a JPG can never be sent as a video (Instagram error 2207082).
    """
    MEDIA_NS = "http://search.yahoo.com/mrss/"  # same as rebuild_clean_rss()
    ET.register_namespace("media", MEDIA_NS)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "GetYourDeal Instagram Reels"
    ET.SubElement(channel, "link").text = "https://harshhaldankar.github.io/Getyourdeal/"
    ET.SubElement(channel, "description").text = "Product reels with Instagram captions, for Make.com"
    for r in reel_items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = r["title"]
        ET.SubElement(item, "link").text = r["link"]
        ET.SubElement(item, "description").text = instagram_caption(r["title"], r["board"])
        ET.SubElement(item, "pubDate").text = r["pub_date"]
        ET.SubElement(item, "video_url").text = r["video_url"]
        ET.SubElement(item, "cover_url").text = r["image_url"]
        ET.SubElement(item, "enclosure", url=r["video_url"], length=r["video_len"], type="video/mp4")
        ET.SubElement(item, f"{{{MEDIA_NS}}}content", url=r["video_url"], medium="video", type="video/mp4")
        ET.SubElement(item, "guid", isPermaLink="false").text = r["guid"]
    # ET.indent rather than the minidom + drop-blank-lines trick, which also deletes the blank
    # lines inside captions
    ET.indent(rss, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(rss, encoding="unicode")

if __name__ == "__main__":
    rebuild_clean_rss()
