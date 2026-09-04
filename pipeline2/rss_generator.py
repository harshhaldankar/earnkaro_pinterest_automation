import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.dom import minidom

RSS_FILE = "docs/rss.xml"

def create_or_load_rss():
    if os.path.exists(RSS_FILE):
        try:
            tree = ET.parse(RSS_FILE)
            return tree, tree.getroot()
        except Exception:
            pass
            
    # Create fresh RSS structure
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "GetYourDeal Automated Feed"
    ET.SubElement(channel, "link").text = "https://harshhaldankar.github.io/Getyourdeal/"
    ET.SubElement(channel, "description").text = "Latest automated deals and videos for Make.com"
    return ET.ElementTree(rss), rss

def add_deal_to_rss(title: str, website_url: str, video_url: str, description: str, image_url: str = "", instagram_eligible: bool = True, affiliate_link: str = ""):
    tree, root = create_or_load_rss()
    channel = root.find("channel")
    if channel is None:
        return
        
    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = website_url
    ET.SubElement(item, "description").text = description
    ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    ET.SubElement(item, "instagram_eligible").text = "true" if instagram_eligible else "false"
    
    if image_url:
        ET.SubElement(item, "image_url").text = image_url

    # Direct affiliate shopping link (for Make.com captions / Instagram bio link)
    if affiliate_link:
        ET.SubElement(item, "affiliate_link").text = affiliate_link
        
    # Video enclosure & direct video_url tag for Make.com to download and post to Instagram
    if video_url:
        ET.SubElement(item, "video_url").text = video_url
        ET.SubElement(item, "enclosure", url=video_url, length="0", type="video/mp4")

    
    # Prepend item to channel so newest is first (after standard tags)
    insert_idx = len(channel.findall("title")) + len(channel.findall("link")) + len(channel.findall("description"))
    channel.insert(insert_idx, item)
    
    # Keep only last 50 items to avoid large files
    items = channel.findall("item")
    if len(items) > 50:
        for i in items[50:]:
            channel.remove(i)
            
    os.makedirs(os.path.dirname(RSS_FILE) or ".", exist_ok=True)
    
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    # Clean up empty lines from minidom
    clean_xml = "\n".join([line for line in xmlstr.split("\n") if line.strip()])
    
    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(clean_xml)
        
    print(f"[RSS Gen] Successfully added '{title[:30]}...' to RSS feed.")
