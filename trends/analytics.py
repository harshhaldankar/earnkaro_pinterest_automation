"""
analytics.py - read our Pinterest Analytics every Monday and turn it into planning signals.

  python -m trends.analytics      fetch the last 30 days, save data/analytics/<date>.json, print a summary

The weekly build calls fetch() first:
  - board_weights(report)  boards that earn reach, clicks and saves per pin get more of this week's
                           trends (research.pick_themes multiplies theme scores by these)
  - report_md(report)      the "Last 30 days on Pinterest" section at the top of PLAN.md

There is no Pinterest API access, so this opens analytics.pinterest.com with the posting login
(pinterest_session.json) and keeps the numbers the page itself loads (its GraphQL responses).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.async_api import async_playwright

IST = timezone(timedelta(hours=5, minutes=30))
BUSINESS_ID = os.getenv("PINTEREST_BUSINESS_ID", "1096837821656197845")
SESSION_FILE = Path("pinterest_session.json")
OUT_DIR = Path("data/analytics")
URL = (f"https://analytics.pinterest.com/overview/?actingBusinessId={BUSINESS_ID}&age=all&aggregation=last30d"
       "&board_metric=IMPRESSION&board_id=&claimed_account_type=all&content_type=all&device_type=all&gender=all"
       "&include_curated=created&include_realtime=true&pin_format=all&pin_metric=IMPRESSION&primary_metric=IMPRESSION"
       "&recent_pins=false&selected_split=NO_SPLIT&source_type=all")


def _num(v) -> float:
    return float(v or 0)


def _parse(responses: list) -> dict:
    """The page's GraphQL answers as one report: totals, daily series, boards and pins."""
    rep = {"summary": {}, "deltas": {}, "daily": [], "boards": [], "pins": [], "audience": {}}
    for body in responses:
        data = (body or {}).get("data") or {}
        for name, node in data.items():
            d = (node or {}).get("data")
            if not d:
                continue
            if name == "v3AnalyticsMetricsDeltasQuery" and d.get("summaryMetrics"):
                m = d["summaryMetrics"]
                rep["summary"] = {"impressions": _num(m.get("impressionFloat")), "engagements": _num(m.get("engagementFloat")),
                                  "outbound_clicks": _num(m.get("outboundClickFloat")), "saves": _num(m.get("saveFloat")),
                                  "days": d.get("numOfDays", 30)}
                rep["deltas"] = d.get("deltas") or {}
            elif name == "v3AnalyticsAudienceDeltasQuery" and d.get("summaryMetrics"):
                rep["audience"] = {"total": _num(d["summaryMetrics"].get("totalAudienceFloat")),
                                   "engaged": _num(d["summaryMetrics"].get("engagersFloat"))}
            elif name == "v3AnalyticsMetricsGraphqlQuery":
                for s in d:
                    for day in (s.get("series") or {}).get("dailyMetrics") or []:
                        m = day.get("metrics") or {}
                        rep["daily"].append({"date": day["date"], "impressions": _num(m.get("impressionFloat")),
                                             "outbound_clicks": _num(m.get("outboundClickFloat")), "saves": _num(m.get("saveFloat"))})
            elif name == "v3AnalyticsTopBoardsGraphqlQuery":
                seen = {b["name"] for b in rep["boards"]}
                for metric, rows in d.items():
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        b, m = row.get("board") or {}, row.get("metrics") or {}
                        if not b.get("name") or b["name"] in seen:
                            continue
                        seen.add(b["name"])
                        rep["boards"].append({"name": b["name"], "pins": b.get("pinCount") or 0, "url": b.get("url", ""),
                                              "impressions": _num(m.get("impressionFloat")), "engagements": _num(m.get("engagementFloat")),
                                              "pin_clicks": _num(m.get("pinClickFloat")), "outbound_clicks": _num(m.get("outboundClickFloat")),
                                              "saves": _num(m.get("saveFloat"))})
            elif name == "v3AnalyticsTopPinsGraphqlQuery":
                seen = {p["id"] for p in rep["pins"]}
                for metric, rows in d.items():
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        pin = row.get("pin") or {}
                        m = row.get("metrics") or {}
                        pid = str(pin.get("entityId") or pin.get("id") or "")
                        if not pid or pid in seen:
                            continue
                        seen.add(pid)
                        rep["pins"].append({"id": pid, "title": pin.get("title") or pin.get("gridTitle") or "",
                                            "link": pin.get("link") or "", "impressions": _num(m.get("impressionFloat")),
                                            "pin_clicks": _num(m.get("pinClickFloat")),
                                            "outbound_clicks": _num(m.get("outboundClickFloat")), "saves": _num(m.get("saveFloat"))})
    return rep


async def _fetch() -> dict:
    responses = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 1000})
        await ctx.add_cookies(json.loads(SESSION_FILE.read_text()))
        page = await ctx.new_page()

        async def keep(r):
            if "/_/graphql/" in r.url:
                try:
                    responses.append(await r.json())
                except Exception:
                    pass
        page.on("response", keep)
        await page.goto("https://in.pinterest.com/", wait_until="domcontentloaded")
        await asyncio.sleep(4)
        await page.goto(URL, wait_until="domcontentloaded")
        await asyncio.sleep(20)
        for _ in range(6):  # top pins and boards load as they scroll into view
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(4)
        landed = page.url
        await browser.close()
    if "overview" not in landed:
        raise RuntimeError("Pinterest Analytics needs a login (pinterest_session.json expired?)")
    return _parse(responses)


async def fetch_async() -> dict | None:
    """Fetch and save the last-30-days report; None if it can't be read (the build carries on without it)."""
    if not SESSION_FILE.exists():
        print("[Analytics] No pinterest_session.json; skipping.")
        return None
    try:
        return _save(await _fetch())
    except Exception as e:
        print(f"[Analytics] Couldn't read Pinterest Analytics: {e}")
        return None


def _save(rep: dict) -> dict:
    rep["fetched_at"] = datetime.now(IST).isoformat(timespec="minutes")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{datetime.now(IST):%Y-%m-%d}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    s = rep["summary"]
    print(f"[Analytics] Last 30 days: {s.get('impressions', 0):,.0f} impressions, {s.get('outbound_clicks', 0):,.0f} outbound clicks, "
          f"{s.get('saves', 0):,.0f} saves; {len(rep['boards'])} boards, {len(rep['pins'])} pins")
    return rep


def board_weights(rep: dict | None) -> dict:
    """{board name: 0.75..1.5}. Value per pin = impressions + 25 x outbound clicks + 15 x saves + 3 x pin clicks,
    compared with the average board. Boards with no data yet stay at 1.0."""
    if not rep or not rep.get("boards"):
        return {}
    vals = {}
    for b in rep["boards"]:
        if b["pins"] <= 0:
            continue
        v = b["impressions"] + 25 * b["outbound_clicks"] + 15 * b["saves"] + 3 * b["pin_clicks"]
        vals[b["name"]] = v / b["pins"]
    if not vals:
        return {}
    avg = sum(vals.values()) / len(vals)
    return {name: round(max(0.75, min(1.5, (v / avg) ** 0.5)), 2) for name, v in vals.items()} if avg else {}


def _delta(d) -> str:
    if d is None:
        return ""
    return f" ({'+' if d >= 0 else ''}{d * 100:.0f}%)"


def report_md(rep: dict | None) -> str:
    if not rep or not rep.get("summary"):
        return "_Pinterest Analytics couldn't be read this week._\n"
    s, d = rep["summary"], rep.get("deltas", {})
    lines = [f"Impressions **{s['impressions']:,.0f}**{_delta(d.get('impression'))} · "
             f"Outbound clicks **{s['outbound_clicks']:,.0f}**{_delta(d.get('outboundClick'))} · "
             f"Saves **{s['saves']:,.0f}**{_delta(d.get('save'))} · "
             f"Engagements **{s['engagements']:,.0f}**{_delta(d.get('engagement'))}", ""]
    if rep.get("boards"):
        w = board_weights(rep)
        lines += ["| Board | Pins | Impressions | Pin clicks | Outbound clicks | Saves | Weight this week |",
                  "|---|---|---|---|---|---|---|"]
        for b in sorted(rep["boards"], key=lambda b: -b["impressions"]):
            lines.append(f"| {b['name']} | {b['pins']} | {b['impressions']:,.0f} | {b['pin_clicks']:,.0f} | "
                         f"{b['outbound_clicks']:,.0f} | {b['saves']:,.0f} | {w.get(b['name'], 1.0)} |")
    if rep.get("pins"):
        lines += ["", "Top pins: " + "; ".join(f"{p['title'][:50] or p['id']} ({p['impressions']:,.0f} impr., "
                                               f"{p['outbound_clicks']:,.0f} clicks, {p['saves']:,.0f} saves)"
                                               for p in sorted(rep["pins"], key=lambda p: -p["impressions"])[:5])]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    r = asyncio.run(fetch_async())
    print(report_md(r))
    print("Board weights:", board_weights(r))
