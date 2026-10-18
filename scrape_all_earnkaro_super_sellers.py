import asyncio
import os
import json
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

EARNKARO_EMAIL = os.getenv("EARNKARO_EMAIL")
EARNKARO_PASSWORD = os.getenv("EARNKARO_PASSWORD")

async def scrape_all():
    print("[Festive] Starting EarnKaro Myntra Super Sellers extraction...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = await context.new_page()

        # Login
        print("[Auth] Logging into EarnKaro...")
        await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await page.fill("#uname", EARNKARO_EMAIL)
        await page.click("#btnLayoutContinue")
        await asyncio.sleep(2)
        await page.fill("#pwd", EARNKARO_PASSWORD)
        await page.click("#btnLayoutSignInPass")
        await asyncio.sleep(5)

        # Target super sellers page
        target = "https://earnkaro.com/product/trending-offers/myntra-super-sellers-web"
        print("[Nav] Loading:", target)
        await page.goto(target, wait_until="domcontentloaded")
        await asyncio.sleep(6)

        # Get all detail card links
        card_links = await page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href*="/PPS16-Myntra-catcard"]'));
            const unique = [];
            const seen = new Set();
            for (const a of links) {
                const href = a.href;
                if (!seen.has(href)) {
                    seen.add(href);
                    const img = a.querySelector("img") || a.closest("div")?.querySelector("img");
                    unique.push({
                        url: href,
                        img: img ? (img.src || img.getAttribute("data-src") || "") : "",
                        alt: img ? (img.alt || "") : ""
                    });
                }
            }
            return unique;
        }""")

        print(f"[Cards] Found {len(card_links)} Myntra Super Seller cards.")
        
        results = []
        for i, card in enumerate(card_links, 1):
            detail_url = card["url"]
            print(f"\n[{i}/{len(card_links)}] Extracting card: {detail_url}")
            try:
                await page.goto(detail_url, wait_until="domcontentloaded")
                await asyncio.sleep(3)

                title = await page.title()
                # Clean title: strip " - EarnKaro" etc.
                title = title.replace(" - EarnKaro", "").replace("EarnKaro", "").strip()

                # Get hero image if missing
                img = card["img"]
                if not img:
                    img = await page.evaluate("""() => {
                        const im = document.querySelector('.product_img img, .detail_img img, .store_img img, img');
                        return im ? (im.src || '') : '';
                    }""")

                # Click COPY LINK to fetch the real tracked affiliate link into clipboard
                affiliate_link = ""
                copy_btn = page.get_by_text("COPY LINK", exact=False).first
                if await copy_btn.count():
                    await copy_btn.click()
                    await asyncio.sleep(1.5)
                    try:
                        affiliate_link = await page.evaluate("navigator.clipboard.readText()")
                    except Exception as ce:
                        print(f"   Clipboard error: {ce}")

                # If clipboard link didn't work, fallback to direct card link or sharelink
                if not affiliate_link or not affiliate_link.startswith("http"):
                    print("   [WARN] Could not get clipboard link, using detail_url")
                    affiliate_link = detail_url

                print(f"   Title: {title}")
                print(f"   Img: {img[:70]}")
                print(f"   Affiliate Link: {affiliate_link}")

                results.append({
                    "title": title,
                    "detail_url": detail_url,
                    "image_url": img,
                    "affiliate_link": affiliate_link,
                    "retailer": "Myntra",
                    "source": "EarnKaro Super Sellers"
                })
            except Exception as e:
                print(f"   [ERR] Failed on {detail_url}: {e}")

        with open("earnkaro_super_sellers_scraped.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n[DONE] Successfully scraped {len(results)} Myntra Super Seller deals to earnkaro_super_sellers_scraped.json")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_all())
