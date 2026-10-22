import asyncio, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from telegram_watcher import load_deals, save_deals
from pinterest_poster import post_deal_to_pinterest, check_session_health

async def post_backlog(limit=20, dry_run=False, force=False):
    session_ok = await check_session_health()
    if not session_ok:
        print("Session DEAD. Run: python refresh_pinterest_session.py")
        return
    deals = load_deals()
    unpinned = sorted((d for d in deals if not d.get("pinned", False)),
                      key=lambda d: d.get("timestamp", ""), reverse=True)
    print(str(len(deals)) + " total, " + str(len(unpinned)) + " unpinned")
    if not unpinned:
        print("All pinned.")
        return
    targets = unpinned[:limit]
    posted = 0
    for i, deal in enumerate(targets, 1):
        t = deal.get("title","")[:55]
        print("  [" + str(i) + "/" + str(len(targets)) + "] " + t)
        if dry_run:
            posted += 1
            continue
        try:
            ok = await post_deal_to_pinterest(deal, ignore_posting_hours=force)
            if ok:
                deal["pinned"] = True
                posted += 1
                save_deals(deals)
                print("    Pinned!")
                await asyncio.sleep(15)
            else:
                print("    Skip")
        except Exception as e:
            print("    ERR: " + str(e))
    print("Done: posted=" + str(posted) + " remaining=" + str(len(unpinned)-posted))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="Bypass posting hours restriction (e.g. night-time testing)")
    a = p.parse_args()
    asyncio.run(post_backlog(a.limit, a.dry_run, a.force))