"""
sync_only.py
------------
Runs ONLY the website rebuild + Pinterest pin sync for existing deals.
Does NOT connect to Telegram or fetch any new deals.

Usage:
    .venv\\Scripts\\python sync_only.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from telegram_watcher import load_deals, save_deals, rebuild_website, push_to_github
from pinterest_poster import post_deal_to_pinterest


async def sync():
    deals = load_deals()

    print("=" * 60)
    print("[INFO] Current deals in database:")
    print("=" * 60)
    for d in deals:
        status = "PINNED    " if d.get("pinned") else "NOT PINNED"
        print(f"  [{status}] {d.get('title', 'Unknown')}")
    print()

    # ── Step 1: Rebuild website ──────────────────────────────────
    print("=" * 60)
    print("[WEB] Rebuilding website from current deals_data.json...")
    print("=" * 60)
    rebuild_website(deals)
    push_to_github("Manual sync: rebuild website")

    # ── Step 2: Pin any unpinned deals ───────────────────────────
    print()
    print("=" * 60)
    print("[PINTEREST] Syncing unpinned deals to Pinterest...")
    print("=" * 60)

    unpinned = [d for d in deals if not d.get("pinned", False)]
    print(f"[INFO] {len(unpinned)} deal(s) need to be pinned")

    if not unpinned:
        print("[SYNC] All deals are already pinned. Nothing to do.")
        return

    sync_updated = False
    for deal in unpinned:
        title = deal.get("title", "Unknown")
        print(f"\n  [PIN] Posting: {title}")
        try:
            pinned = await post_deal_to_pinterest(deal)
            if pinned:
                deal["pinned"] = True
                sync_updated = True
                print(f"  [OK]  Successfully pinned: {title}")
                await asyncio.sleep(5)
            else:
                print(f"  [SKIP] Could not pin: {title}")
        except Exception as e:
            print(f"  [ERR] Failed for '{title}': {e}")

    if sync_updated:
        save_deals(deals)
        rebuild_website(deals)
        push_to_github("Sync: mark deals as pinned")
        print("\n[SYNC] Done. Website + Pinterest updated and pushed.")
    else:
        print("\n[SYNC] Done. No successful pins this run.")


if __name__ == "__main__":
    asyncio.run(sync())
