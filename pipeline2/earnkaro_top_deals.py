"""
Pipeline 2 deal source: EarnKaro's own product category pages.

Every product there is already from a store EarnKaro pays commission on, and the page data
carries price, MRP, discount, the commission per sale ("cashback_amount") and a tracking link.
Category pages need a logged-in session; the products sit in the page's __NEXT_DATA__ JSON.
"""
import asyncio
import json
import os
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright

EARNKARO_USER_ID = "5382823"

# Fashion, beauty, home and small accessories — the Pinterest niche (see telegram_watcher.ALLOWED_CATEGORIES)
CATEGORY_PATHS = [
    "women-fashion/kurta-kurti", "women-fashion/women-dresses", "women-fashion/tops-tunics",
    "women-fashion/sarees", "women-fashion/women-jeans", "women-footwear/women-heels",
    "women-footwear/flat-sandals", "women-footwear/casual-shoes",
    "men-fashion/men-tshirt", "men-fashion/men-shirts", "men-fashion/men-jeans",
    "men-footwear/men-sports-shoes", "men-footwear/men-casual-footwear",
    "beauty/fragrance", "beauty/make-up-nails", "health-personal-care/hair-care-styling",
    "accessories/watches", "accessories/handbags", "accessories/jewellery", "accessories/all-sunglasses",
    "home-kitchen/home-furnishing", "home-kitchen/bed-and-bath",
]
# All categories every run: most listed Myntra items turn out sold out on the live check, so
# Pipeline 2 needs the whole pool (~22 pages, ~1 min) to find 5 that are really in stock
CATEGORIES_PER_RUN = len(CATEGORY_PATHS)
MIN_DISCOUNT = 50
MAX_PRICE = 15000


def categories_for_this_run(now: datetime = None) -> list:
    """Rotate through CATEGORY_PATHS by half-day, so each run looks at a different slice."""
    now = now or datetime.now(timezone.utc)
    slot = (now.toordinal() * 2 + (now.hour >= 12)) * CATEGORIES_PER_RUN
    n = len(CATEGORY_PATHS)
    return [CATEGORY_PATHS[(slot + i) % n] for i in range(CATEGORIES_PER_RUN)]


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


def deal_title(d: dict) -> str:
    """Pin/website title. Price as '@ ₹X' and '% Off' so extract_price and the discount badge parse it."""
    name = d["name"]
    if d["brand"] and not name.lower().startswith(d["brand"].lower()):
        name = f"{d['brand']} {name}"
    return f"{name} @ ₹{d['price']:,.0f} | {d['discount']}% Off on {d['store']}"


def card_title(d: dict) -> str:
    """Amazon card title. Products read like any deal; collections keep their own wording."""
    if d.get("kind") == "product":
        return deal_title(d)
    return f"Amazon: {d['name']}"  # "Amazon: Kurta Sets Under Rs 599" (store prefix: see product_name)


def parse_products(page_props: dict, category_path: str) -> list:
    """Turn a category page's pageProps into flat deal dicts."""
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
        # The tracking link ends in "?id=" — the EarnKaro user ID attributes the click to us
        if link.endswith("id="):
            link += EARNKARO_USER_ID
        out.append({
            "id": item.get("id"),
            "name": (a.get("name") or "").strip(),
            "brand": (a.get("brand") or "").strip(),
            "store": _clean_store(a.get("merchant_name") or ""),
            "image": a.get("image_url") or "",
            # Up to 4 shots of the product (EarnKaro repeats the main one) — used for reels
            "images": list(dict.fromkeys(u for u in [a.get("image_url")] + list((a.get("image_urls") or {}).values()) if u)),
            "price": _to_float(price.get("discounted_price")),
            "mrp": _to_float(price.get("original_price")),
            "discount": int(_to_float(price.get("discount_percentage"))),
            "commission": _to_float(price.get("cashback_amount")),
            "link": link,
            "category_path": category_path,
        })
    return out


def is_good_deal(d: dict) -> bool:
    return (d["name"] and d["image"] and d["price"] > 0
            and d["price"] <= MAX_PRICE and d["discount"] >= MIN_DISCOUNT)


def pick_top(deals: list, limit: int, per_category: int = 1) -> list:
    """Best commission x discount first, at most `per_category` from each category for variety."""
    ranked = sorted(deals, key=lambda d: d["commission"] * (1 + d["discount"] / 100), reverse=True)
    picked, per_cat = [], {}
    for d in ranked:
        if per_cat.get(d["category_path"], 0) >= per_category:
            continue
        picked.append(d)
        per_cat[d["category_path"]] = per_cat.get(d["category_path"], 0) + 1
        if len(picked) >= limit:
            break
    return picked


async def _login(page):
    await page.goto("https://earnkaro.com/login", wait_until="domcontentloaded")
    await asyncio.sleep(2)
    await page.fill("#uname", os.getenv("EARNKARO_EMAIL", ""))
    await page.click("#btnLayoutContinue")
    await asyncio.sleep(2)
    await page.fill("#pwd", os.getenv("EARNKARO_PASSWORD", ""))
    await page.click("#btnLayoutSignInPass")
    await asyncio.sleep(6)


async def fetch_earnkaro_deals(category_paths: list) -> list:
    """Log in once, read each category page's product JSON. Returns all parsed products."""
    if not os.getenv("EARNKARO_EMAIL") or not os.getenv("EARNKARO_PASSWORD"):
        raise RuntimeError("EARNKARO_EMAIL / EARNKARO_PASSWORD not set")
    deals = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await (await browser.new_context()).new_page()
        await _login(page)
        for path in category_paths:
            try:
                await page.goto(f"https://earnkaro.com/product/{path}", wait_until="domcontentloaded")
                raw = await page.evaluate(
                    "() => { const s = document.getElementById('__NEXT_DATA__'); return s ? s.textContent : '' }")
                props = (json.loads(raw) if raw else {}).get("props", {}).get("pageProps", {})
                if not props.get("isUserLoggedIn"):
                    print(f"[EarnKaro] Not logged in on {path} — login failed?")
                found = parse_products(props, path)
                print(f"[EarnKaro] {path}: {len(found)} products")
                deals.extend(found)
            except Exception as e:
                print(f"[EarnKaro] {path}: failed ({e})")
        try:
            cards = await _fetch_amazon_cards(page)
            print(f"[EarnKaro] Amazon deal cards: {len(cards)}")
            deals.extend(cards)
        except Exception as e:
            print(f"[EarnKaro] Amazon deal cards: failed ({e})")
        await browser.close()
    return deals


# ----------------------------------------------------------------
# Amazon: EarnKaro doesn't list Amazon in its category pages. It features hand-picked Amazon
# "deal cards" on its home page instead: single products ("Adidas Men Run Sneaker @ Rs 2660
# Worth Rs 6999", product page) and collections ("Kurta Sets Under Rs 599", category page).
# The card's price fields are placeholders; the real price is in its name.
# ----------------------------------------------------------------
AMAZON_CARD_RE = re.compile(r"/PPS\d+-(?:Flash-)?Amazon-catcard-\d+$")
AMAZON_EXTRA_PAGES = ["https://earnkaro.com/top-selling-products/amazon-gif"]


def _walk_products(o, out: list):
    if isinstance(o, dict):
        if o.get("type") == "products" and isinstance(o.get("attributes"), dict):
            out.append(o)
        for v in o.values():
            _walk_products(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk_products(v, out)


def amazon_card(d: dict) -> dict:
    """Fill price/MRP/discount from a card's name; mark it as a product or a collection."""
    name = d["name"]
    m = re.search(r"\s*@\s*Rs\.?\s*([\d,]+)\s*Worth\s*Rs\.?\s*([\d,]+)", name, re.IGNORECASE)
    if m:
        price, mrp = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        disc = round((1 - price / mrp) * 100) if mrp > price else 0
        return {**d, "name": name[:m.start()].strip(), "price": price, "mrp": mrp, "discount": disc,
                "kind": "product", "store": "Amazon", "brand": ""}
    pct = re.search(r"(\d+)\s*%\s*off", name, re.IGNORECASE)
    return {**d, "price": 0.0, "mrp": 0.0, "discount": int(pct.group(1)) if pct else 0,
            "kind": "collection", "store": "Amazon", "brand": ""}


async def _fetch_amazon_cards(page) -> list:
    await page.goto("https://earnkaro.com/", wait_until="domcontentloaded")
    await asyncio.sleep(4)
    hrefs = await page.eval_on_selector_all("a[href]", "els => [...new Set(els.map(e => e.href.split('?')[0]))]")
    urls = [h for h in hrefs if AMAZON_CARD_RE.search(h)] + AMAZON_EXTRA_PAGES
    cards = {}
    for url in urls:
        await page.goto(url, wait_until="domcontentloaded")
        raw = await page.evaluate(
            "() => { const s = document.getElementById('__NEXT_DATA__'); return s ? s.textContent : '' }")
        items = []
        _walk_products(json.loads(raw) if raw else {}, items)
        for d in parse_products({"data": items}, "amazon"):
            if d["store"] == "Amazon":
                cards[d["id"]] = amazon_card(d)
    return list(cards.values())
