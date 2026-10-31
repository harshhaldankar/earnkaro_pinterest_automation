"""
Live price / stock checks for posted deals, and the rules for when a deal has ended.

Why: EarnKaro's listings lag the store (a watch listed at ₹3,475 on EarnKaro was ₹2,155 on
Myntra the same day) and loot deals sell out in hours, so pins and pages drift out of date.

Sources, best first:
  - Myntra product pages carry window.__myx (price, MRP, outOfStock, sizes) and answer plain requests.
  - AJIO blocks plain requests and headless browsers (403), so for AJIO we rely on EarnKaro's listing.
"""
import json
import re
import urllib.parse
from datetime import datetime, timezone

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

MAX_REFRESH_AGE_DAYS = 14      # older deals are ended without a check
SALE_PAGE_LIFETIME_DAYS = 3    # store-wide sale pages have no single price to check
UNLISTED_LIFETIME_DAYS = 7     # AJIO deals that dropped off EarnKaro's listing this long ago
UNVERIFIED_LIFETIME_DAYS = 2   # Myntra deals with no successful store check for this long
PRICE_RISE_LIMIT = 1.15        # >15% above the posted price: the deal is gone
MIN_LIVE_DISCOUNT = 40


def age_days(deal: dict) -> float:
    ts = (deal.get("timestamp") or "").replace("Z", "")
    try:
        return (datetime.utcnow() - datetime.fromisoformat(ts)).total_seconds() / 86400
    except ValueError:
        return float("inf")


def resolve_store_url(link: str) -> str | None:
    """EarnKaro tracking link (linkredirect.in splash) -> the store URL it forwards to."""
    if not link:
        return None
    if "linkredirect.in" not in link:
        return link
    try:
        page = requests.get(link, headers={"User-Agent": UA}, timeout=10).text
        m = re.search(r'cashbackUrl\s*=\s*"([^"]+)"', page)
        if m:
            # Myntra/AJIO splash pages wrap the store URL in ?url=; Amazon ones point at it directly
            url = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(1)).query).get("url", [""])[0]
            return url or m.group(1)
    except requests.RequestException:
        pass
    return None


def check_myntra(url: str) -> dict | None:
    """{'price', 'mrp', 'discount', 'in_stock'} from a Myntra product page, or None if unreadable."""
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-IN"}, timeout=12)
        m = re.search(r"window\.__myx\s*=\s*(\{.*?\})\s*</script>", r.text, re.S)
        if r.status_code != 200 or not m:
            return None
        pdp = json.loads(m.group(1)).get("pdpData") or {}
        price = (pdp.get("price") or {}).get("discounted")
        mrp = (pdp.get("price") or {}).get("mrp")
        if not price:
            return None
        sizes = pdp.get("sizes") or []
        out = (pdp.get("flags") or {}).get("outOfStock") or (sizes and not any(s.get("available") for s in sizes))
        disc = round((1 - price / mrp) * 100) if mrp else 0
        return {"price": int(price), "mrp": int(mrp or 0), "discount": disc, "in_stock": not out}
    except (requests.RequestException, ValueError):
        return None


def check_amazon(url: str) -> dict | None:
    """{'price', 'mrp', 'discount', 'in_stock'} from an Amazon product page, or None if unreadable
    (a robot check, or a page that needs a size picked first)."""
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-IN"}, timeout=15)
        t = r.text
        if r.status_code != 200 or "captcha" in t.lower():
            return None
        avail = re.search(r'id="availability"[^>]*>\s*<span[^>]*>\s*([^<]+)', t)
        price = re.search(r'class="a-price-whole">([\d,]+)', t)
        if not avail or not price:
            return None
        a = avail.group(1).strip().lower()
        if "unavailable" in a or "out of stock" in a:
            in_stock = False
        elif "in stock" in a:
            in_stock = True
        else:
            return None
        p = int(price.group(1).replace(",", ""))
        mrp_m = re.search(r'a-text-price[^>]*>\s*<span class="a-offscreen">₹([\d,]+)', t)
        mrp = int(mrp_m.group(1).replace(",", "")) if mrp_m else 0
        disc = round((1 - p / mrp) * 100) if mrp > p else None
        return {"price": p, "mrp": mrp, "discount": disc, "in_stock": in_stock}
    except (requests.RequestException, ValueError):
        return None


def check_store(url: str) -> dict | None:
    if "myntra.com" in url:
        return check_myntra(url)
    if "amazon." in url:
        return check_amazon(url)
    return None


def is_single_product(url: str) -> bool:
    u = (url or "").lower()
    return (("myntra.com" in u and re.search(r"/\d+/buy", u) is not None) or ("ajio.com" in u and "/p/" in u)
            or ("amazon." in u and "/dp/" in u))


def earnkaro_id(deal: dict) -> str:
    """EarnKaro product/card id (lowercase), e.g. 'pps1-amazon-catcard-249'. Stored on deals whose link
    no longer goes through EarnKaro (Amazon collections carry our own tag); else from the tracking link."""
    return deal.get("earnkaro_id") or (deal.get("affiliate_link") or "").split("?")[0].rsplit("/", 1)[-1].lower()


def posted_price(deal: dict) -> int | None:
    m = re.search(r"₹\s?([\d,]+)", deal.get("title", ""))
    return int(m.group(1).replace(",", "")) if m else None


def apply_live_price(deal: dict, live: dict):
    """Put the live price into the deal so the website shows what the store charges now."""
    old = posted_price(deal)
    if not live["mrp"] or live["discount"] is None:
        # Amazon pages without an M.R.P. line: keep the posted MRP and recompute the discount
        mrp = int(float(deal.get("mrp") or 0))
        live = {**live, "mrp": mrp, "discount": round((1 - live["price"] / mrp) * 100) if mrp > live["price"] else 0}
    if old and live["price"] != old:
        deal["title"] = re.sub(r"₹\s?[\d,]+", f"₹{live['price']:,}", deal["title"], count=1)
        deal["title"] = re.sub(r"\d+% Off", f"{live['discount']}% Off", deal["title"], count=1)
        deal["desc"] = f"{live['discount']}% off: ₹{live['price']:,} (MRP ₹{live['mrp']:,})."
    deal["mrp"] = str(live["mrp"])
    deal["discount_percent"] = live["discount"]


def end_deal(deal: dict, reason: str):
    deal["ended"] = True
    deal["ended_reason"] = reason
    deal["ended_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def refresh_deals(deals: list, earnkaro_now: dict = None) -> dict:
    """
    Re-check recent deals in place. earnkaro_now maps EarnKaro product id (lowercase) -> current
    listing (from this run's fetch), used for stores we can't check directly.
    Returns counts for the log.
    """
    earnkaro_now = earnkaro_now or {}
    stats = {"checked": 0, "updated": 0, "ended": 0, "unknown": 0}
    for deal in deals:
        if deal.get("ended"):
            continue
        if age_days(deal) > MAX_REFRESH_AGE_DAYS:
            # Too old to trust any more; left live, it stayed on the site forever
            end_deal(deal, f"older than {MAX_REFRESH_AGE_DAYS} days")
            stats["ended"] += 1
            continue
        stats["checked"] += 1
        store_url = deal.get("store_url")
        if not store_url:
            store_url = resolve_store_url(deal.get("affiliate_link") or deal.get("product_url"))
            if store_url:
                deal["store_url"] = store_url

        if earnkaro_now and "amazon." in (store_url or "") and earnkaro_id(deal) not in earnkaro_now:
            # Amazon cards are hand-picked by EarnKaro and taken down when the offer ends
            end_deal(deal, "no longer featured on EarnKaro")
            stats["ended"] += 1
            continue

        if not store_url or not is_single_product(store_url):
            # Store-wide sale page (or unknown target): no price to check, give it a fixed lifetime
            if age_days(deal) > SALE_PAGE_LIFETIME_DAYS:
                end_deal(deal, "sale page older than 3 days")
                stats["ended"] += 1
            continue

        live = check_store(store_url)
        is_amazon = "amazon." in store_url
        if is_amazon and live is None and earnkaro_id(deal) in earnkaro_now:
            # Store check unavailable, but EarnKaro still features the card: good enough for Amazon
            deal["last_listed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            stats["unknown"] += 1
            continue
        if live is None and ("myntra.com" in store_url or is_amazon):
            # EarnKaro keeps listing Myntra items after they sell out, so its listing proves nothing.
            # Without a store check (or, for Amazon, a featured card) for UNVERIFIED_LIFETIME_DAYS,
            # assume the deal is gone.
            last_ok = max(deal.get("price_checked_at") or "", deal.get("last_listed_at") if is_amazon else "",
                          deal.get("timestamp") or "")
            if age_days({"timestamp": last_ok}) > UNVERIFIED_LIFETIME_DAYS:
                end_deal(deal, f"stock not confirmed for {UNVERIFIED_LIFETIME_DAYS} days")
                stats["ended"] += 1
            else:
                stats["unknown"] += 1
            continue
        if live is None:
            pid = (deal.get("affiliate_link") or "").split("?")[0].rsplit("/", 1)[-1].lower()
            listed = earnkaro_now.get(pid)
            if listed:
                live = {"price": int(listed["price"]), "mrp": int(listed["mrp"]),
                        "discount": listed["discount"], "in_stock": True, "source": "earnkaro"}
                deal["last_listed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            elif deal.get("pipeline") == 2 and age_days(deal) > UNLISTED_LIFETIME_DAYS:
                end_deal(deal, "no longer listed on EarnKaro")
                stats["ended"] += 1
                continue
            else:
                stats["unknown"] += 1
                continue

        old = posted_price(deal)
        if not live["in_stock"]:
            end_deal(deal, "out of stock")
            stats["ended"] += 1
        elif old and live["price"] > old * PRICE_RISE_LIMIT:
            end_deal(deal, f"price rose ₹{old:,} -> ₹{live['price']:,}")
            stats["ended"] += 1
        elif live["discount"] is not None and live["discount"] < MIN_LIVE_DISCOUNT:
            end_deal(deal, f"discount now {live['discount']}%")
            stats["ended"] += 1
        else:
            if old != live["price"]:
                stats["updated"] += 1
            apply_live_price(deal, live)
        if live.get("source") != "earnkaro":  # the website shows this as "Price checked"
            deal["price_checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return stats
