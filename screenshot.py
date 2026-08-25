import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        # Use file protocol for absolute path
        file_path = os.path.abspath("docs/deals/index.html")
        await page.goto(f"file:///{file_path.replace(chr(92), '/')}") # Windows path fix
        
        # Wait a bit for fonts to load
        await page.wait_for_timeout(2000)
        
        artifact_path = r"C:\Users\Harsh Haldankar\.gemini\antigravity\brain\1df2bea1-f540-40ae-b0a1-18212d544e8e\website_preview.png"
        await page.screenshot(path=artifact_path, full_page=False)
        print(f"Screenshot saved to {artifact_path}")
        await browser.close()

asyncio.run(main())
