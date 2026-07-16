"""
STEP 1: One-time Telegram authentication setup.
Run this script ONCE to log in with your phone number.
It will save a session file so future runs are fully automatic.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
import os

load_dotenv()

# We need Telegram API credentials (free to get - instructions below)
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def setup():
    if not API_ID or not API_HASH:
        print("="*60)
        print("SETUP REQUIRED: Get your Telegram API credentials")
        print("="*60)
        print("1. Go to: https://my.telegram.org/auth")
        print("2. Log in with your phone number")
        print("3. Click 'API Development Tools'")
        print("4. Create a new app (any name, e.g. 'GetYourDeal')")
        print("5. Copy the 'api_id' and 'api_hash' values")
        print("6. Add them to your .env file:")
        print("   TELEGRAM_API_ID=12345678")
        print("   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890")
        print("="*60)
        return

    print("Connecting to Telegram...")
    client = TelegramClient('earnkaro_session', int(API_ID), API_HASH)
    await client.start()

    print("\n✅ Login successful! Session saved as 'earnkaro_session.session'")
    print("You won't need to log in again.\n")

    # Print the string session so we can save it for GitHub Actions
    session_string = StringSession.save(client.session)
    print("📋 STRING SESSION (save this for GitHub Actions secrets):")
    print(f"TELEGRAM_SESSION={session_string}")

    # Test: show some info about the account
    me = await client.get_me()
    print(f"\n✅ Logged in as: {me.first_name} ({me.username})")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(setup())
