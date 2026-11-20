"""
ig_stats.py - reads Instagram numbers for the dashboard: followers, and reach / views / likes /
comments / saves / shares for the last 25 posts. Saved to data/analytics/instagram.json (and a
dated copy). Run daily by "4 · Daily stats".
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from trends.instagram import IST, POSTED_FILE, _api, _load, ig_user_id

OUT_DIR = Path("data/analytics")
METRICS = ("reach", "views", "saved", "shares", "total_interactions")


def _insights(media_id: str) -> dict:
    """The post's metrics; a metric Instagram doesn't offer for that kind of post is left out."""
    try:
        data = _api("GET", f"{media_id}/insights", metric=",".join(METRICS))["data"]
    except RuntimeError:  # one unsupported metric fails the whole call: ask one by one
        data = []
        for m in METRICS:
            try:
                data += _api("GET", f"{media_id}/insights", metric=m)["data"]
            except RuntimeError:
                pass
    return {d["name"]: d["values"][0]["value"] for d in data if d.get("values")}


def _kind(m: dict) -> str:
    if m.get("media_product_type") == "REELS":
        return "reel"
    return "carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else "post"


def fetch() -> dict:
    uid = ig_user_id()
    if not uid:
        raise RuntimeError("no Instagram account for this token")
    me = _api("GET", uid, fields="username,followers_count,media_count")
    media = _api("GET", f"{uid}/media", limit=25, fields=(
        "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"))["data"]
    ours = {p.get("link"): p["key"] for p in _load(POSTED_FILE, []) if p.get("ok") and p.get("link")}
    posts = []
    for m in media:
        ins = _insights(m["id"])
        posts.append({
            "date": m["timestamp"][:10], "kind": _kind(m), "link": m.get("permalink", ""),
            "key": ours.get(m.get("permalink"), ""),
            "title": (m.get("caption") or "").split("\n")[0][:80],
            "likes": m.get("like_count", 0), "comments": m.get("comments_count", 0),
            "reach": ins.get("reach"), "views": ins.get("views"), "saves": ins.get("saved"),
            "shares": ins.get("shares"), "interactions": ins.get("total_interactions"),
        })
    return {"fetched_at": datetime.now(IST).isoformat(timespec="minutes"), "username": me.get("username"),
            "followers": me.get("followers_count"), "media_count": me.get("media_count"), "posts": posts}


def main() -> int:
    if not os.getenv("IG_ACCESS_TOKEN"):
        print("[IG stats] IG_ACCESS_TOKEN not set; skipping.")
        return 0
    try:
        rep = fetch()
    except Exception as e:
        print(f"[IG stats] Couldn't read Instagram: {e}")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rep, ensure_ascii=False, indent=1)
    (OUT_DIR / "instagram.json").write_text(text, encoding="utf-8")  # what the dashboard reads
    (OUT_DIR / f"instagram-{datetime.now(IST):%Y-%m-%d}.json").write_text(text, encoding="utf-8")
    p = rep["posts"]
    print(f"[IG stats] @{rep['username']}: {rep['followers']} followers; last {len(p)} posts: "
          f"{sum(x['reach'] or 0 for x in p):,} reach, {sum(x['saves'] or 0 for x in p)} saves")
    for x in p[:10]:
        print(f"  {x['date']} {x['kind']:8} reach {x['reach']}  views {x['views']}  likes {x['likes']}  "
              f"saves {x['saves']}  shares {x['shares']}  {x['title'][:40]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
