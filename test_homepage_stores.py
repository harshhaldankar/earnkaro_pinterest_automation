import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to EarnKaro...")
        await page.goto("https://earnkaro.com", wait_until="domcontentloaded")
        print("Waiting 5 seconds...")
        await asyncio.sleep(5)
        
        # Let's search for text containing "profit"
        print("Searching for store sections...")
        elements = await page.query_selector_all("text=/profit/i")
        print(f"Found {len(elements)} elements containing 'profit':")
        for idx, el in enumerate(elements[:20]):
            try:
                parent_text = await el.evaluate("node => node.parentElement ? node.parentElement.innerText : ''")
                text_clean = parent_text.strip().replace('\n', ' | ')
                print(f"  Element {idx}: {text_clean}")
            except Exception as e:
                pass
                
        # Let's look for images that might be logos of stores (like Myntra, Ajio, Flipkart)
        imgs = await page.query_selector_all("img")
        print(f"Found {len(imgs)} images. Some alt texts:")
        for idx, img in enumerate(imgs):
            alt = await img.get_attribute("alt")
            src = await img.get_attribute("src")
            if alt:
                print(f"  Img {idx}: alt='{alt}' | src='{src}'")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
