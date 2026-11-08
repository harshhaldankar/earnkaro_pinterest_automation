"""
earnings.py - a daily snapshot of what EarnKaro reports: the money end of the funnel.

  python -m trends.earnings     log in, read the Reports and Order details pages, save data/earnings/<date>.json

What's kept (numbers only; no names, emails or full order IDs - this repo is public):
  totals        all-time profit: pending / confirmed / paid / cancelled, order value, payout threshold,
                and EarnKaro's "traffic source" approval status
  orders        store, commission, status, date, last 4 of the order ID, the share link it came through
  yesterday     clicks, transactions and profit for yesterday (taken daily, so this builds an exact history)
  last14        the same totals for the last 14 days, plus daily_profit (the overview chart's CSV export)
  brands        clicks, transactions and profit per store over the last 14 days

EarnKaro's report API answers are encrypted for its own page, so this reads what the page shows
(the overview totals, its chart's CSV export and the brands table) rather than calling that API.
"""
import asyncio
import csv
import io
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")

from trends.catalog import EarnKaroSession

IST = timezone(timedelta(hours=5, minutes=30))
OUT_DIR = Path("data/earnings")
RANGE = "Last 14 Days"
TOTAL_FIELDS = ("total_earned", "total_ordervalue", "pending_cashback", "confirmed_cashback", "paid_cashback",
                "requested_cashback", "cancelled_cashback", "total_rewards_earned", "total_referral_earned",
                "payment_threshold", "traffic_source_status")
BRAND_ROW = re.compile(r"\n\s*([A-Za-z][\w &.'-]*)\s*\n\s*([\d,.]+[KLM]?)\s+([\d,.]+[KLM]?)\s+₹\s?([\d,.]+[KLM]?)\s+([\d.]+)%")


def _money(v) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)) or 0)
    except ValueError:
        return 0.0


def _count(text: str) -> float:
    """'1.8K' -> 1800, '2.1L' -> 210000, '₹41.7' -> 41.7 (EarnKaro shortens big numbers)."""
    m = re.search(r"([\d,.]+)\s*([KLM])?", text.replace("₹", ""))
    if not m:
        return 0.0
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0.0
    return n * {"K": 1e3, "L": 1e5, "M": 1e6}.get(m.group(2) or "", 1)


async def _page_props(page, url: str) -> dict:
    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(6)
    raw = await page.evaluate("() => { const s = document.getElementById('__NEXT_DATA__'); return s ? s.textContent : '' }")
    return (json.loads(raw) if raw else {}).get("props", {}).get("pageProps", {})


def _totals(props: dict) -> dict:
    a = ((props.get("earningsData") or {}).get("data") or [{}])[0].get("attributes", {})
    return {k: (a.get(k) if k == "traffic_source_status" else _money(a.get(k))) for k in TOTAL_FIELDS if k in a}


def _orders(props: dict) -> list:
    out = []
    for it in props.get("data") or []:
        a = it.get("attributes", it)
        store = re.search(r"/stores/([a-z]+)", a.get("merchant_image_url") or "")
        oid = str(a.get("order_id") or "")
        out.append({"store": (store.group(1).title() if store else "?"), "commission": _money(a.get("cashback_amount")),
                    "status": a.get("cashback_status"), "date": (a.get("transaction_date") or "")[:10],
                    "order": f"…{oid[-4:]}" if oid else "", "share_id": a.get("shareid") or ""})
    return out


async def _pick_range(page, which: int, label: str):
    """Open the which-th "Filter by" (0: performance overview, 1: brands table) and choose a date range."""
    box = page.locator(".new_main_filter").nth(which)
    await box.scroll_into_view_if_needed()
    await box.locator("button.new_filter_btn").click()
    await asyncio.sleep(1.2)
    await box.locator("button.new_filter_tab_title", has_text="Date Range").click()
    await asyncio.sleep(1.0)
    await box.locator("li", has_text=label).first.click()
    await asyncio.sleep(0.6)
    await box.locator("button.new_filter_apply_btn", has_text="Apply").click()
    await asyncio.sleep(6)


async def _overview(page) -> dict:
    """The three totals on the overview tabs ("Clicks 1.8K", "Txns 1", "Profit ₹41.7")."""
    out = {}
    for cls, key in (("pink", "clicks"), ("green", "transactions"), ("blue", "profit")):
        parts = (await page.locator(f"li.{cls}").first.inner_text()).split(None, 1)
        out[key] = _count(parts[1] if len(parts) > 1 else "0")
    return out


async def _csv_series(page) -> dict:
    """The overview chart's own CSV export (it always charts profit): {YYYY-MM-DD: value}."""
    async with page.expect_download(timeout=20000) as dl:
        await page.evaluate("() => document.querySelector('.apexcharts-menu-item.exportCSV').click()")
    path = await (await dl.value).path()
    out = {}
    for row in list(csv.reader(io.StringIO(Path(path).read_text(encoding="utf-8-sig"))))[1:]:
        if len(row) >= 2:
            try:
                out[datetime.strptime(row[0].strip(), "%a %b %d %Y").strftime("%Y-%m-%d")] = _money(row[1])
            except ValueError:
                continue
    return out


def _brands(text: str) -> list:
    i = text.find("Brands\tClicks")
    if i < 0:
        return []
    block = text[i:text.find("About EarnKaro", i)]
    return [{"store": m.group(1).strip(), "clicks": int(_count(m.group(2))), "transactions": int(_count(m.group(3))),
             "profit": _count(m.group(4)), "conversion": float(m.group(5))} for m in BRAND_ROW.finditer(block)]


async def snapshot() -> dict:
    snap = {"taken_at": datetime.now(IST).isoformat(timespec="minutes"), "range": RANGE}
    async with EarnKaroSession() as ek:
        page = ek.page
        await page.set_viewport_size({"width": 1280, "height": 900})
        orders_props = await _page_props(page, "https://earnkaro.com/my-earnings/order-details")
        report_props = await _page_props(page, "https://earnkaro.com/reports")
        # The login form never says it failed (wrong password, OTP, a block): a logged-out page would
        # read as ₹0 and no orders, so stop here instead of saving that as real numbers.
        if not report_props.get("isUserLoggedIn") or not orders_props.get("isUserLoggedIn"):
            raise RuntimeError("not logged in to EarnKaro (password changed, OTP or a block?)")
        snap["orders"] = _orders(orders_props)
        snap["totals"] = _totals(report_props)
        if "total_earned" not in snap["totals"]:
            raise RuntimeError("EarnKaro's Reports page had no earnings data")
        for key, label in (("yesterday", "Yesterday"), ("last14", RANGE)):
            try:
                await _pick_range(page, 0, label)
                snap[key] = await _overview(page)
                if key == "last14":
                    snap["daily_profit"] = [{"date": d, "profit": v} for d, v in sorted((await _csv_series(page)).items())]
            except Exception as e:
                print(f"[Earnings] {label} overview not read: {str(e).splitlines()[0]}")
        try:
            await _pick_range(page, 1, RANGE)
            snap["brands"] = _brands(await page.evaluate("() => document.body.innerText"))
        except Exception as e:
            print(f"[Earnings] Brand table not read: {str(e).splitlines()[0]}")
            snap["brands"] = []
    if "yesterday" in snap:
        snap["yesterday"]["date"] = (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
    return snap


def save(snap: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{datetime.now(IST):%Y-%m-%d}.json"
    text = json.dumps(snap, ensure_ascii=False, indent=1)
    path.write_text(text, encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(text, encoding="utf-8")  # what the dashboard reads
    # One small file with a row per day (yesterday's clicks, orders, profit), so the dashboard draws
    # the history without fetching every daily snapshot
    hist_file = OUT_DIR / "history.json"
    try:
        hist = {r["date"]: r for r in json.loads(hist_file.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        hist = {}
    if snap.get("yesterday", {}).get("date"):
        hist[snap["yesterday"]["date"]] = snap["yesterday"]
    hist_file.write_text(json.dumps(sorted(hist.values(), key=lambda r: r["date"]), indent=1), encoding="utf-8")
    t, y, l14 = snap.get("totals", {}), snap.get("yesterday", {}), snap.get("last14", {})
    print(f"[Earnings] All time ₹{t.get('total_earned', 0):,.2f} (pending ₹{t.get('pending_cashback', 0):,.2f}), "
          f"{len(snap.get('orders', []))} orders | yesterday {y.get('clicks', 0):,.0f} clicks, "
          f"{y.get('transactions', 0):,.0f} orders | 14 days {l14.get('clicks', 0):,.0f} clicks, "
          f"{l14.get('transactions', 0):,.0f} orders, ₹{l14.get('profit', 0):,.2f} | {len(snap.get('brands', []))} stores "
          f"| traffic source: {t.get('traffic_source_status', '?')}")
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        snap = asyncio.run(snapshot())
    except Exception as e:  # login or page load failed: keep yesterday's file rather than writing a broken one
        print(f"[Earnings] Snapshot failed: {str(e).splitlines()[0]}")
        sys.exit(1)
    print(save(snap))
