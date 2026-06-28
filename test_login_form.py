import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to EarnKaro Login page...")
        await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
        print("DOM loaded, waiting 5 seconds...")
        await asyncio.sleep(5)
        print("Page Title:", await page.title())
        
        # Let's inspect inputs
        inputs = await page.query_selector_all("input")
        print("Found inputs:")
        for idx, inp in enumerate(inputs):
            name = await inp.get_attribute("name")
            type_attr = await inp.get_attribute("type")
            placeholder = await inp.get_attribute("placeholder")
            id_attr = await inp.get_attribute("id")
            print(f"  Input {idx}: name={name} | type={type_attr} | placeholder={placeholder} | id={id_attr}")
            
        # Let's inspect buttons
        buttons = await page.query_selector_all("button")
        print("Found buttons:")
        for idx, btn in enumerate(buttons):
            text = await btn.inner_text()
            type_attr = await btn.get_attribute("type")
            id_attr = await btn.get_attribute("id")
            print(f"  Button {idx}: text={text.strip()} | type={type_attr} | id={id_attr}")
            
        # Take screenshot of login page
        await page.screenshot(path="login_page.png")
        print("Screenshot saved to login_page.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
