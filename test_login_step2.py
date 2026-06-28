import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to EarnKaro Login page...")
        await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
        print("Waiting 5 seconds...")
        await asyncio.sleep(5)
        
        # Fill email
        print("Filling uname...")
        await page.fill("#uname", "dummy_test_email@example.com")
        
        # Click Continue
        print("Clicking Continue...")
        await page.click("#btnLayoutContinue")
        
        # Wait 3 seconds for dynamic form change
        await asyncio.sleep(3)
        
        # Check inputs and buttons now
        print("After Continue, checking inputs:")
        inputs = await page.query_selector_all("input")
        for idx, inp in enumerate(inputs):
            name = await inp.get_attribute("name")
            type_attr = await inp.get_attribute("type")
            placeholder = await inp.get_attribute("placeholder")
            id_attr = await inp.get_attribute("id")
            style = await inp.get_attribute("style")
            print(f"  Input {idx}: name={name} | type={type_attr} | placeholder={placeholder} | id={id_attr} | style={style}")
            
        buttons = await page.query_selector_all("button")
        print("After Continue, checking buttons:")
        for idx, btn in enumerate(buttons):
            text = await btn.inner_text()
            type_attr = await btn.get_attribute("type")
            id_attr = await btn.get_attribute("id")
            print(f"  Button {idx}: text={text.strip()} | type={type_attr} | id={id_attr}")
            
        await page.screenshot(path="login_step2.png")
        print("Screenshot saved to login_step2.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
