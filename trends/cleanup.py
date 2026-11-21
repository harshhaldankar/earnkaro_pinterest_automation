"""
cleanup.py - deletes duplicate pins from our Pinterest account, keeping the first copy of each.

A duplicate is a pin with the same title, description and link as an earlier one, repeated
at least MIN_COPIES times (Nov 14-18 2026 a
save bug reposted 3 pins ~50 times each). Uses the logged-in browser session (pinterest_session.json).

  python -m trends.cleanup            # dry run: lists what would be deleted
  python -m trends.cleanup --delete   # deletes them
"""
import asyncio
import json
import random
import sys
from collections import defaultdict

from playwright.async_api import async_playwright

from trends.pinterest import load_or_login

USERNAME = "getyourdeal45"
BASE = "https://in.pinterest.com"
UNIQUE_TITLES = ("| Outfit idea for",)  # outfit-look pins: one per look, so any second copy is a duplicate
MIN_COPIES = 5  # only the bug repeats; 2-3 pins sharing a title are collages/templates with different images

_GET = """async ([resource, options, source]) => {
  const q = new URLSearchParams({source_url: source, data: JSON.stringify({options, context: {}})});
  const r = await fetch(`/resource/${resource}/get/?${q}`, {headers: {
    "Accept": "application/json", "X-Requested-With": "XMLHttpRequest", "X-Pinterest-PWS-Handler": "www/[username].js"}});
  return {status: r.status, body: await r.text()};
}"""

_DELETE = """async ([pinId, source]) => {
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
  const body = new URLSearchParams({source_url: source, data: JSON.stringify({options: {id: pinId}, context: {}})});
  const r = await fetch("/resource/PinResource/delete/", {method: "POST", body, headers: {
    "Accept": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf,
    "Content-Type": "application/x-www-form-urlencoded"}});
  return {status: r.status, body: (await r.text()).slice(0, 300)};
}"""


async def all_pins(page) -> list:
    pins, bookmark = [], None
    for _ in range(40):  # 40 pages x 50 = up to 2,000 pins
        opts = {"username": USERNAME, "page_size": 50, "field_set_key": "grid_item"}
        if bookmark:
            opts["bookmarks"] = [bookmark]
        res = await page.evaluate(_GET, ["UserPinsResource", opts, f"/{USERNAME}/_created/"])
        if res["status"] != 200:
            raise RuntimeError(f"listing pins failed: HTTP {res['status']} {res['body'][:200]}")
        rr = json.loads(res["body"])["resource_response"]
        pins += [p for p in (rr.get("data") or []) if isinstance(p, dict) and p.get("id")]
        bookmark = rr.get("bookmark")
        if not bookmark or bookmark == "-end-":
            break
    return pins


def _is_dup(title: str, copies: int) -> bool:
    return copies >= MIN_COPIES or (copies >= 2 and any(t in title for t in UNIQUE_TITLES))


def duplicates(pins: list) -> tuple:
    groups = defaultdict(list)
    for p in pins:
        title = (p.get("title") or p.get("grid_title") or "").strip()
        desc = (p.get("description") or "").strip()
        if not (title or desc):
            continue  # nothing to compare on: never delete
        groups[(title, desc, (p.get("link") or "").strip())].append(p)
    extra = []
    for (title, _, _), g in groups.items():
        if not _is_dup(title, len(g)):
            continue
        g.sort(key=lambda p: int(p["id"]))  # pin ids grow over time: keep the oldest
        extra += g[1:]
    return groups, extra


async def main(delete: bool) -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900}, user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"))
        if not await load_or_login(context):
            print("[Cleanup] Not logged in")
            return 1
        page = await context.new_page()
        await page.goto(f"{BASE}/{USERNAME}/_created/", wait_until="domcontentloaded")
        await asyncio.sleep(5)

        pins = await all_pins(page)
        groups, extra = duplicates(pins)
        print(f"[Cleanup] {len(pins)} pins on the account; {len(extra)} are duplicates")
        for (title, desc, link), g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if _is_dup(title, len(g)):
                print(f"  {len(g):3}x  keep {g[0]['id']}  {(title or desc)[:70]}")
        if not delete:
            print("[Cleanup] Dry run: nothing deleted (run with --delete)")
            await browser.close()
            return 0

        done = failed = 0
        for p in extra:
            res = await page.evaluate(_DELETE, [p["id"], f"/{USERNAME}/_created/"])
            if res["status"] == 200:
                done += 1
            else:
                failed += 1
                print(f"  [Cleanup] couldn't delete {p['id']}: HTTP {res['status']} {res['body'][:150]}")
                if failed >= 5:
                    print("[Cleanup] Stopping after 5 failures")
                    break
            await asyncio.sleep(random.uniform(3, 6))  # unhurried, like a person tidying up
        print(f"[Cleanup] Deleted {done} duplicates; {failed} failed")
        await browser.close()
        return 0 if not failed else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main("--delete" in sys.argv)))
