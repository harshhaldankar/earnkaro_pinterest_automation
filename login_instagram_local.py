import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("========================================")
    print(" INSTAGRAM SESSION EXTRACTOR")
    print("========================================")
    print("A browser window will open shortly.")
    print("Please log into Instagram manually.")
    print("========================================\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 414, "height": 896},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        
        page = await context.new_page()
        await page.goto("https://www.instagram.com/")
        
        print("Waiting for you to log in (waiting for the login box to disappear)...")
        
        try:
            # Loop for up to 5 minutes waiting for login to disappear
            for _ in range(150):
                await asyncio.sleep(2)
                # If we are no longer on the login screen
                if not await page.locator('input[name="username"]').is_visible():
                    print("\nLogin box disappeared! Waiting 5 seconds for cookies to settle...")
                    await asyncio.sleep(5)
                    
                    cookies = await context.cookies()
                    session_file = Path("instagram_session.json")
                    session_file.write_text(json.dumps(cookies, indent=2))
                    
                    print(f"✅ Success! Session saved to: {session_file.absolute()}")
                    print("You can now copy the contents of this file to your GitHub Secret.")
                    return
            
            print("\n❌ Timed out waiting for login (5 minutes exceeded).")
        except Exception as e:
            print(f"\n❌ Error occurred: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
