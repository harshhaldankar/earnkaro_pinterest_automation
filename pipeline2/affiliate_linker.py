import re
import urllib.parse
import os
from pipeline2.trend_matcher import ProductDeal

# Assuming we have Telethon client set up in the main runner
EKBOT_USERNAME = "ekconverter9bot"
EKBOT_TIMEOUT  = 30

def purify_url(url: str) -> str:
    """
    Strips ALL tracking and affiliate parameters to ensure clean EarnKaro conversion.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        
        # Params to strip completely
        bad_params = ['affid', 'tag', 'pid', 'offer_id', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'aff_id', 'click_id']
        
        clean_query = {k: v for k, v in query.items() if k.lower() not in bad_params}
        
        # Rebuild URL
        new_query = urllib.parse.urlencode(clean_query, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url

def inject_amazon_tag(url: str) -> str:
    """
    Injects Amazon affiliate tag locally without hitting EarnKaro.
    """
    tag = os.getenv("AMAZON_AFFILIATE_TAG", "getyourdeal00-21")
    try:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        
        # Remove any existing tag and add ours
        if 'tag' in query:
            del query['tag']
            
        query['tag'] = [tag]
        
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url

async def generate_affiliate_link(client, deal: ProductDeal) -> str:
    """
    Generates affiliate link via Telethon Bot or locally (for Amazon).
    """
    import time
    import asyncio
    from datetime import datetime, timezone

    clean_url = purify_url(deal.product_url)
    
    is_amazon = "amazon.in" in clean_url.lower() or "amazon.com" in clean_url.lower()
    if is_amazon:
        print(f"[Linker] Generating local Amazon tag for: {deal.title}")
        return inject_amazon_tag(clean_url)
        
    print(f"[Linker] Sending URL to @{EKBOT_USERNAME}: {clean_url[:70]}...")
    try:
        start_time = datetime.now(timezone.utc)
        await client.send_message(EKBOT_USERNAME, clean_url)
        
        start = time.time()
        while time.time() - start < EKBOT_TIMEOUT:
            await asyncio.sleep(2)
            
            messages = await client.get_messages(EKBOT_USERNAME, limit=3)
            for msg in messages:
                if not msg.text or msg.date < start_time:
                    continue
                    
                text = msg.text
                if any(x in text.lower() for x in ["could not locate", "error", "failed", "verify if the seller", "invalid"]):
                    print(f"  [BOT ERR] {text.strip()}")
                    return ""
                    
                urls = re.findall(r'https?://[^\s]+', text)
                for u in urls:
                    u = u.rstrip(".,)")
                    if any(d in u for d in ["ekaro.in", "fktr.in", "ajiio.in", "myntr.it", "ajiio.store", "myntr.store", "bitli.in"]):
                        # Ensure it isn't just bouncing back our original URL
                        if u != clean_url:
                            print(f"  [BOT SUCCESS] Got affiliate link: {u}")
                            return u
                            
        print(f"[Linker] Timeout waiting for @{EKBOT_USERNAME} reply.")
        return ""
    except Exception as e:
        print(f"[Linker] Error communicating with bot: {e}")
        return ""
