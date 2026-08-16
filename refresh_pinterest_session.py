import asyncio
import json
from datetime import datetime, timezone
from playwright.async_api import async_playwright

async def refresh_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://www.pinterest.com/login/")
        print("Please log in to Pinterest in the browser window. You have 120 seconds.")
        
        await asyncio.sleep(120)
        
        cookies = await context.cookies()
        with open("pinterest_session.json", "w") as f:
            json.dump(cookies, f, indent=2)
            
        print("Session saved to pinterest_session.json.")
        
        for cookie in cookies:
            name = cookie.get("name")
            expires = cookie.get("expires", -1)
            if expires != -1:
                expiry_date = datetime.fromtimestamp(expires, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                print(f"Cookie {name} expires: {expiry_date}")
            else:
                print(f"Cookie {name} expires: Session (does not expire)")
                
        print("\nInstructions: Please update the PINTEREST_SESSION_JSON GitHub Secret with the contents of pinterest_session.json")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(refresh_session())
