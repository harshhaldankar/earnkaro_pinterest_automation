import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone, timedelta

RSS_FILE = "docs/rss.xml"

tree = ET.parse(RSS_FILE)
root = tree.getroot()
channel = root.find("channel")

items = channel.findall("item")
print(f"Total items in RSS: {len(items)}")

base_time = datetime.now(timezone.utc)

for idx, item in enumerate(items):
    # Sequential timestamp: 1 minute apart so Make.com has distinct chronological order
    item_time = base_time - timedelta(minutes=idx)
    
    # Update pubDate
    pub_el = item.find("pubDate")
    if pub_el is None:
        pub_el = ET.SubElement(item, "pubDate")
    pub_el.text = item_time.strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    # Add or update unique GUID with cache-busting v2 tag
    guid_el = item.find("guid")
    if guid_el is None:
        guid_el = ET.SubElement(item, "guid")
    guid_el.set("isPermaLink", "false")
    
    link_el = item.find("link")
    link_text = link_el.text if link_el is not None and link_el.text else f"item_{idx}"
    deal_id = os.path.basename(link_text.strip("/ "))
    guid_el.text = f"ugc_v2_{deal_id}_{idx+1}"

xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
clean_xml = "\n".join([line for line in xmlstr.split("\n") if line.strip()])

with open(RSS_FILE, "w", encoding="utf-8") as f:
    f.write(clean_xml)

print(f"SUCCESS: Added distinct <guid> and sequential pubDate to all {len(items)} items in {RSS_FILE}!")
