import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    print("========================================")
    print(" INSTAGRAM SESSION EXTRACTOR")
    print("========================================")
    print("A browser window will open shortly.")
    print("Please log into Instagram manually.")
    print("The script will automatically detect when you reach the home feed")
    print("and save your session cookies.")
    print("========================================\n")
    
    async with async_playwright() as p:
        # Launch browser in non-headless mode so user can see it and interact
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 414, "height": 896}, # Mobile viewport is better for IG
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        
        page = await context.new_page()
        await page.goto("https://www.instagram.com/")
        
        print("Waiting for you to log in...")
        
        try:
            # Wait for the New Post button (plus icon) which only appears when logged in
            # We give the user 5 minutes to complete login
            await page.wait_for_selector('svg[aria-label="New post"]', timeout=300000)
            
            print("\n✅ Login detected! Saving cookies...")
            
            cookies = await context.cookies()
            session_file = Path("instagram_session.json")
            session_file.write_text(json.dumps(cookies, indent=2))
            
            print(f"✅ Success! Session saved to: {session_file.absolute()}")
            print("You can now copy the contents of this file to your GitHub Secret.")
            
        except Exception as e:
            print(f"\n❌ Timed out waiting for login or an error occurred: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
