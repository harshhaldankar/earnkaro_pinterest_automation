import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_deal_to_telegram(item):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Skipping Telegram notification.")
        return False
        
    print(f"Sending Telegram alert for {item['brand']}...")
    
    # Structure the message caption
    # Include:
    # 1. Hinglish WhatsApp message
    # 2. Affiliate link
    # 3. Posted Pin URL
    whatsapp_msg = item["whatsapp_message"]
    pin_url = item.get("pin_url", "No Pin URL generated")
    affiliate_link = item.get("affiliate_link", "")
    
    # We will format this caption nicely
    caption = f"""🔥 <b>{item['brand'].upper()} DEAL ALERT ({item['rate']})</b> 🔥

{whatsapp_msg}

━━━━━━━━━━━━━━━━━━━
📌 <b>Pinterest Pin URL:</b> {pin_url}
🔗 <b>Affiliate Link:</b> {affiliate_link}
━━━━━━━━━━━━━━━━━━━
👉 <i>Forward this text directly to your WhatsApp Channel / Group!</i>"""

    # Limit Telegram caption to 1024 characters (Telegram's limit for photo captions)
    if len(caption) > 1024:
        # If it exceeds, we truncate the WhatsApp message slightly or send it as a text follow-up
        truncated_whatsapp = whatsapp_msg[:500] + "...\n(Truncated for length. Check affiliate link below)"
        caption = f"""🔥 <b>{item['brand'].upper()} DEAL ALERT ({item['rate']})</b> 🔥

{truncated_whatsapp}

━━━━━━━━━━━━━━━━━━━
📌 <b>Pinterest Pin URL:</b> {pin_url}
🔗 <b>Affiliate Link:</b> {affiliate_link}
━━━━━━━━━━━━━━━━━━━
👉 <i>Forward this text directly to your WhatsApp Channel / Group!</i>"""

    # Upload and send the generated Pin image
    image_path = item.get("pin_image_path")
    if not image_path or not os.path.exists(image_path):
        print(f"Pin image path not found for {item['brand']}. Sending text-only message.")
        # Send text message
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": caption,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url, json=payload)
            if res.status_code == 200:
                print("Text message sent successfully!")
                return True
            else:
                print(f"Telegram text message failed. Code: {res.status_code}, Response: {res.text}")
                return False
        except Exception as e:
            print(f"Error sending text message to Telegram: {e}")
            return False
            
    # Send photo message
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    
    try:
        with open(image_path, "rb") as photo_file:
            files = {"photo": photo_file}
            res = requests.post(url, data=payload, files=files)
            if res.status_code == 200:
                print(f"Photo message for {item['brand']} sent successfully to Telegram!")
                return True
            else:
                print(f"Telegram photo message failed. Code: {res.status_code}, Response: {res.text}")
                return False
    except Exception as e:
        print(f"Error sending photo to Telegram: {e}")
        return False

def run_telegram_pipeline():
    if not os.path.exists("content.json"):
        print("Error: content.json not found! Please run poster_pinterest.py first.")
        return

    with open("content.json", "r", encoding="utf-8") as f:
        content_items = json.load(f)

    print("\nStarting Telegram notification pipeline...")
    success_count = 0
    for item in content_items:
        if send_deal_to_telegram(item):
            success_count += 1
            
    print(f"\nTelegram pipeline completed! Sent {success_count}/10 deals to channel.")

if __name__ == "__main__":
    run_telegram_pipeline()
