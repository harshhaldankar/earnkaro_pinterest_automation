"""
Run this LOCALLY when Instagram challenge blocks GitHub Actions.
It opens a real browser for you to approve the challenge.
"""
import os
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

username = os.getenv("INSTAGRAM_USERNAME")
password = os.getenv("INSTAGRAM_PASSWORD")

print(f"Logging in as: {username}")
cl = Client()
cl.delay_range = [1, 3]
cl.login(username, password)
cl.dump_settings("instagrapi_session.json")
print("\n✅ Session saved to instagrapi_session.json")
print("\nNow add this file's contents to GitHub Secret: INSTAGRAPI_SESSION_JSON")
with open("instagrapi_session.json") as f:
    print(f.read())
