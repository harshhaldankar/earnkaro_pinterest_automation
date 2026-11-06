"""
post.py - posts the next pin from data/queue.json to Pinterest. The "2 · Post pins" workflow
runs it once an hour, 8 AM - 10 PM IST.

The queue is written only by the weekly build; what has been posted goes to data/posted.json,
written only here, so the two never change the same file. A posted pin's image is deleted.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")

from trends.pinterest import MAX_PINS_PER_DAY, check_session_health, is_posting_hours, pins_today, post_pin

IST = timezone(timedelta(hours=5, minutes=30))
QUEUE_FILE = Path("data/queue.json")
POSTED_FILE = Path("data/posted.json")
MAX_AGE_DAYS = 21     # a theme older than this is out of date; its leftover pins are dropped
TRIES_PER_RUN = 3     # a pin that fails shouldn't block the queue (skipped after 3 failures)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def pending() -> list:
    log = _load(POSTED_FILE)
    fails = {}
    for p in log:
        if not p["ok"]:
            fails[p["id"]] = fails.get(p["id"], 0) + 1
    done = {p["id"] for p in log if p["ok"]} | {i for i, n in fails.items() if n >= 3}
    cutoff = (datetime.now(IST) - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    return [q for q in _load(QUEUE_FILE)
            if q["id"] not in done and q["id"].split(":")[0] >= cutoff and Path(q["image"]).exists()]


def mark_posted(item: dict, ok: bool):
    log = _load(POSTED_FILE)
    log.append({"id": item["id"], "at": datetime.now(IST).isoformat(timespec="minutes"), "ok": ok})
    POSTED_FILE.write_text(json.dumps(log, indent=1), encoding="utf-8")
    if ok and "pin_images" in item["image"]:
        Path(item["image"]).unlink(missing_ok=True)


async def main() -> int:
    todo = pending()
    print(f"[Post] {len(todo)} pins waiting")
    if not todo:
        return 0
    if not is_posting_hours():
        print("[Post] Outside posting hours (7 AM - 11 PM IST)")
        return 0
    if pins_today() >= MAX_PINS_PER_DAY:
        print(f"[Post] Daily limit of {MAX_PINS_PER_DAY} reached")
        return 0
    if not await check_session_health():
        print("[Post] Pinterest login expired: refresh the PINTEREST_SESSION_JSON secret")
        return 1
    for item in todo[:TRIES_PER_RUN]:
        print(f"[Post] {item['title']}  ->  {item['board']}")
        ok = await post_pin(item["image"], item["title"], item["description"], item["link"], item["board"])
        if ok:
            mark_posted(item, True)
            print("[Post] Posted")
            return 0
        mark_posted(item, False)  # a pin that fails 3 times is skipped from then on
        print("[Post] Failed; trying the next one")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
