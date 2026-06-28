import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to EarnKaro...")
        await page.goto("https://earnkaro.com", wait_until="domcontentloaded")
        print("DOM loaded, waiting 5 seconds...")
        await asyncio.sleep(5)
        print("Page Title:", await page.title())
        
        # Look for Login link/button
        login_selectors = [
            "text=Login",
            "text=Sign In",
            "a[href*='login']",
            "a[href*='signin']",
            "button:has-text('Login')",
            "button:has-text('Sign')"
        ]
        
        for sel in login_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    print(f"Found login selector: {sel}")
            except Exception as e:
                pass
                
        # Let's take a screenshot of the main page
        await page.screenshot(path="homepage.png")
        print("Screenshot saved to homepage.png")
        
        # Let's print HTML of links
        links = await page.query_selector_all("a")
        print("Found links:")
        for link in links[:30]:
            text = await link.inner_text()
            href = await link.get_attribute("href")
            if text or href:
                print(f"  Text: {text.strip()} | Href: {href}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
