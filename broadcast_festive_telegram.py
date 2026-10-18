import asyncio
import os
import json
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STR = os.getenv("TELEGRAM_SESSION")
TARGET_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "me") # Defaults to "Saved Messages" (me) or channel username

async def broadcast_deals(limit=5):
    print("=" * 60)
    print("  ?? TELEGRAM FESTIVE BROADCAST")
    print(f"  Target: {TARGET_CHANNEL}")
    print("=" * 60)

    deals_file = "deals_data.json"
    deals = json.load(open(deals_file, "r", encoding="utf-8"))
    festive_deals = [d for d in deals if d.get("pipeline") == "Festive Super Sellers"][:limit]

    if not festive_deals:
        print("No festive deals found.")
        return

    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.start()
    print("Connected to Telegram as authenticated user.")

    for i, deal in enumerate(festive_deals, 1):
        title = deal.get("title", "")
        desc = deal.get("desc", "")
        link = deal.get("affiliate_link", "")
        img_rel = deal.get("image_path", "")
        img_full = os.path.join("docs", "deals", img_rel) if not os.path.isabs(img_rel) else img_rel

        caption = f"?? **{title}**\n\n{desc}\n\n?? **Shop Now:** {link}\n\n#MyntraSale #DiwaliLoot #Deals"

        print(f"\n[{i}/{len(festive_deals)}] Broadcasting: {title}")
        try:
            if os.path.exists(img_full):
                await client.send_file(TARGET_CHANNEL, img_full, caption=caption)
            else:
                await client.send_message(TARGET_CHANNEL, caption)
            print("  ? Sent successfully!")
            await asyncio.sleep(4)
        except Exception as e:
            print(f"  ? Failed: {e}")

    await client.disconnect()
    print("\nBroadcast complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--channel", type=str, default=None)
    args = parser.parse_args()
    if args.channel:
        TARGET_CHANNEL = args.channel
    asyncio.run(broadcast_deals(limit=args.limit))
