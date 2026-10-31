"""
pin_scheduler.py - posts ONE deal to Pinterest per run; run hourly by .github/workflows/pin_scheduler.yml.

Both pipelines only add deals to the website. This picks the newest live deal that isn't on
Pinterest yet, so pins go out at a steady pace through the day instead of in bursts.

"On Pinterest yet" comes from pinned_names.json (the repeat-pin guard, written only by this job)
plus the old per-deal "pinned" flag, so this job never writes deals_data.json and can't clash
with the pipelines' commits.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

from telegram_watcher import load_deals, deal_age_days, MAX_PIN_AGE_DAYS
from pinterest_poster import post_deal_to_pinterest, check_session_health, recently_pinned, is_posting_hours, pins_today, MAX_PINS_PER_DAY

PINS_PER_RUN = 1
TRIES_PER_RUN = 3  # a pin that fails (image, board) shouldn't block the queue


def queue(deals):
    """Live, recent deals not on Pinterest yet, newest first."""
    return sorted(
        (d for d in deals
         if not d.get("ended") and not d.get("pinned") and d.get("image_path")
         and deal_age_days(d) <= MAX_PIN_AGE_DAYS and not recently_pinned(d.get("title", ""))),
        key=lambda d: d.get("timestamp", ""), reverse=True)


async def main() -> int:
    pending = queue(load_deals())
    print(f"[PIN QUEUE] {len(pending)} deals waiting for Pinterest")
    if not pending:
        return 0
    if not is_posting_hours():
        print("[PIN QUEUE] Outside posting hours (7 AM - 11 PM IST)")
        return 0
    if pins_today() >= MAX_PINS_PER_DAY:
        print(f"[PIN QUEUE] Daily limit of {MAX_PINS_PER_DAY} pins reached")
        return 0
    if not await check_session_health():
        print("[PIN QUEUE] Pinterest session DEAD — refresh PINTEREST_SESSION_JSON")
        return 1

    posted = 0
    for deal in pending[:TRIES_PER_RUN]:
        print(f"[PIN QUEUE] Pinning: {deal.get('title', '')[:70]}")
        try:
            if await post_deal_to_pinterest(deal):
                posted += 1
                print("  [OK] Pinned")
                if posted >= PINS_PER_RUN:
                    break
            else:
                print("  [SKIP] Not pinned")
        except Exception as e:
            print(f"  [ERR] {e}")
    print(f"[PIN QUEUE] Pinned {posted}; {len(pending) - posted} still waiting")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
