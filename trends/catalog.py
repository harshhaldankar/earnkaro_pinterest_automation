"""
catalog.py - products and shop links for a theme, from EarnKaro.

  EarnKaroSession      logged-in browser on earnkaro.com
    .products()        every product in CATEGORY_PATHS (Myntra/AJIO and others): name, brand,
                       store, photos, price, MRP, discount, commission and a tracked link
    .make_link(url)    EarnKaro's link maker: any store URL (a Myntra search page, say) as a
                       tracked link, so "shop all" links earn commission and never sell out
  amazon_search_link(query)   Amazon.in search with our own Associates tag

EarnKaro's catalogue only covers the categories below (no lehenga or hoodie pages), so a trend
becomes a theme only when enough of these products match it (see research.py).
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

EARNKARO_USER_ID = "5382823"
AMAZON_TAG = os.getenv("AMAZON_AFFILIATE_TAG") or "getyourdeal00-21"
PAGES_PER_CATEGORY = 1  # EarnKaro lists at most 24 products a category; later pages repeat them

CATEGORY_PATHS = [
    "women-fashion/kurta-kurti", "women-fashion/sarees", "women-fashion/women-dresses",
    "women-fashion/tops-tunics", "women-fashion/shirts", "women-fashion/women-jeans",
    "women-footwear/women-heels", "women-footwear/flat-sandals", "women-footwear/casual-shoes",
    "women-footwear/women-sports-shoes",
    "men-fashion/men-tshirt", "men-fashion/men-shirts", "men-fashion/men-jeans", "men-fashion/men-trousers",
    "men-footwear/men-sports-shoes", "men-footwear/men-casual-footwear", "men-footwear/formal-shoes",
    "accessories/watches", "accessories/handbags", "accessories/jewellery", "accessories/all-sunglasses",
    "bags-luggage/wallets-card-holders",
    "beauty/fragrance", "beauty/make-up-nails",
    "home-kitchen/home-furnishing", "home-kitchen/bed-and-bath",
]  # (EarnKaro's "super seller" lists are sale banners with placeholder prices, not products)


def amazon_search_link(query: str) -> str:
    return f"https://www.amazon.in/s?k={quote_plus(query)}&tag={AMAZON_TAG}"


def _to_float(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _clean_store(merchant: str) -> str:
    """EarnKaro merchant names carry internal suffixes ("AJIO Direct", "Myntra New")."""
    for suffix in (" Direct", " New"):
        merchant = merchant.replace(suffix, "")
    return merchant.strip()


def parse_products(page_props: dict, category_path: str) -> list:
    """A category page's pageProps as flat product dicts (expired ones dropped)."""
    out = []
    for item in page_props.get("data") or []:
        if item.get("type") != "products":
            continue
        a = item.get("attributes") or {}
        price = a.get("price") or {}
        end = a.get("product_end_datetime")
        if end:
            try:
                if datetime.fromisoformat(str(end).replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    continue
            except ValueError:
                pass
        link = a.get("cashback_url") or ""
        if not link:
            continue
        if link.endswith("id="):  # the tracking link attributes the click to our EarnKaro account
            link += EARNKARO_USER_ID
        out.append({
            "id": str(item.get("id")),
            "name": (a.get("name") or "").strip(),
            "brand": (a.get("brand") or "").strip(),
            "store": _clean_store(a.get("merchant_name") or ""),
            "image": a.get("image_url") or "",
            "images": list(dict.fromkeys(u for u in [a.get("image_url")] + list((a.get("image_urls") or {}).values()) if u)),
            "price": _to_float(price.get("discounted_price")),
            "mrp": _to_float(price.get("original_price")),
            "discount": int(_to_float(price.get("discount_percentage"))),
            "commission": _to_float(price.get("cashback_amount")),
            "link": link,
            "category": category_path,
        })
    return out


async def _login(page):
    await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
    await asyncio.sleep(2)
    await page.fill("#uname", os.getenv("EARNKARO_EMAIL", ""))
    await page.click("#btnLayoutContinue")
    await page.wait_for_selector("#pwd", state="visible", timeout=20000)
    await page.fill("#pwd", os.getenv("EARNKARO_PASSWORD", ""))
    await page.click("#btnLayoutSignInPass")
    await asyncio.sleep(6)


class EarnKaroSession:
    """async with EarnKaroSession() as ek: products = await ek.products(); link = await ek.make_link(url)"""

    async def __aenter__(self):
        if not os.getenv("EARNKARO_EMAIL") or not os.getenv("EARNKARO_PASSWORD"):
            raise RuntimeError("EARNKARO_EMAIL / EARNKARO_PASSWORD not set")
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self.page = await (await self._browser.new_context()).new_page()
        await _login(self.page)
        return self

    async def __aexit__(self, *exc):
        await self._browser.close()
        await self._pw.stop()

    async def _page_props(self, url: str) -> dict:
        await self.page.goto(url, wait_until="domcontentloaded")
        raw = await self.page.evaluate(
            "() => { const s = document.getElementById('__NEXT_DATA__'); return s ? s.textContent : '' }")
        return (json.loads(raw) if raw else {}).get("props", {}).get("pageProps", {})

    async def products(self, category_paths=CATEGORY_PATHS) -> list:
        found = {}
        for path in category_paths:
            for n in range(1, PAGES_PER_CATEGORY + 1):
                try:
                    props = await self._page_props(f"https://earnkaro.com/product/{path}?page[number]={n}")
                    if not props.get("isUserLoggedIn"):
                        print(f"[EarnKaro] Not logged in on {path}; login failed?")
                    items = parse_products(props, path)
                    new = [p for p in items if p["id"] not in found]
                    found.update((p["id"], p) for p in new)
                    if not new:
                        break
                except Exception as e:
                    print(f"[EarnKaro] {path} page {n}: failed ({e})")
                    break
        print(f"[EarnKaro] {len(found)} products from {len(category_paths)} categories")
        return list(found.values())

    async def make_link(self, url: str) -> str:
        """Tracked EarnKaro link for any store URL; '' if EarnKaro doesn't support the store."""
        try:
            # Through EarnKaro's own "Make Link" page (a direct call needs page state we don't have)
            await self.page.goto("https://earnkaro.com/create-earn-link", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            async with self.page.expect_response(lambda r: "makeearnlink" in r.url, timeout=20000) as resp:
                await self.page.fill("#deallink", url)
                await self.page.click("#Btn_Make_Profit_Button", force=True)
            data = await (await resp.value).json()
            return data.get("shared_link", "") if data.get("code") == "success" else ""
        except Exception as e:
            print(f"[EarnKaro] make_link failed for {url}: {e}")
            return ""
