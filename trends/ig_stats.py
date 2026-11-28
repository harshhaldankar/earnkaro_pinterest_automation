"""
ig_stats.py - reads Instagram numbers for the dashboard: followers, and reach / views / likes /
comments / saves / shares (and, for reels, how long people watch) for the last 25 posts, plus the
account's reach, profile views and link taps yesterday. Saved to data/analytics/instagram.json (and a
dated copy); one line a day goes to data/analytics/instagram_history.json for the trend charts.
Run daily by "4 · Daily stats".
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from trends.instagram import IST, POSTED_FILE, _api, _load, ig_user_id

OUT_DIR = Path("data/analytics")
METRICS = ("reach", "views", "saved", "shares", "total_interactions")
REEL_METRICS = METRICS + ("ig_reels_avg_watch_time",)  # milliseconds; does the voice hold people?
ACCOUNT_METRICS = ("reach", "profile_views", "website_clicks", "accounts_engaged")
HISTORY = OUT_DIR / "instagram_history.json"
ERRORS = []  # what Instagram said when it refused a metric (shown once in the log and on the dashboard)


def _insights(media_id: str, metrics=METRICS) -> dict:
    """The post's metrics; a metric Instagram doesn't offer for that kind of post is left out."""
    try:
        data = _api("GET", f"{media_id}/insights", metric=",".join(metrics))["data"]
    except RuntimeError:  # one unsupported metric fails the whole call: ask one by one
        data = []
        for m in metrics:
            try:
                data += _api("GET", f"{media_id}/insights", metric=m)["data"]
            except RuntimeError as e:
                if str(e) not in ERRORS:
                    ERRORS.append(str(e)[:200])
    return {d["name"]: d["values"][0]["value"] for d in data if d.get("values")}


def _kind(m: dict) -> str:
    if m.get("media_product_type") == "REELS":
        return "reel"
    return "carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else "post"


def account_day(uid: str) -> dict:
    """The whole account's numbers for yesterday (IST): reach, profile views, link taps, accounts engaged."""
    day = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    out = {}
    for m in ACCOUNT_METRICS:  # one by one, so one Instagram refuses doesn't lose the others
        try:
            data = _api("GET", f"{uid}/insights", metric=m, period="day", metric_type="total_value",
                        since=int((day - timedelta(days=1)).timestamp()), until=int(day.timestamp()))["data"]
            out[m] = data[0]["total_value"]["value"] if data else None
        except (RuntimeError, KeyError, IndexError) as e:
            if str(e)[:200] not in ERRORS:
                ERRORS.append(str(e)[:200])
    return out


def save_history(rep: dict):
    """One line a day (the latest read of a day wins), for the follower and reach charts."""
    try:
        hist = json.loads(HISTORY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hist = []
    yday = (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
    row = {"date": datetime.now(IST).strftime("%Y-%m-%d"), "followers": rep["followers"],
           "posts": rep["media_count"], "day": yday, **rep.get("account", {})}
    hist = [h for h in hist if h["date"] != row["date"]] + [row]
    HISTORY.write_text(json.dumps(hist[-400:], indent=1), encoding="utf-8")


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
        ins = _insights(m["id"], REEL_METRICS if _kind(m) == "reel" else METRICS)
        watch = ins.get("ig_reels_avg_watch_time")
        posts.append({
            "date": m["timestamp"][:10], "kind": _kind(m), "link": m.get("permalink", ""),
            "key": ours.get(m.get("permalink"), ""),
            "title": (m.get("caption") or "").split("\n")[0][:80],
            "likes": m.get("like_count", 0), "comments": m.get("comments_count", 0),
            "reach": ins.get("reach"), "views": ins.get("views"), "saves": ins.get("saved"),
            "shares": ins.get("shares"), "interactions": ins.get("total_interactions"),
            "watch_s": round(watch / 1000, 1) if watch is not None else None,
        })
    account = account_day(uid)
    return {"fetched_at": datetime.now(IST).isoformat(timespec="minutes"), "username": me.get("username"),
            "followers": me.get("followers_count"), "media_count": me.get("media_count"), "posts": posts,
            "account": account,
            "errors": ERRORS[:3]}


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
    save_history(rep)
    p = rep["posts"]
    print(f"[IG stats] @{rep['username']}: {rep['followers']} followers; last {len(p)} posts: "
          f"{sum(x['reach'] or 0 for x in p):,} reach, {sum(x['saves'] or 0 for x in p)} saves")
    print(f"[IG stats] Yesterday: {rep['account']}")
    for err in rep["errors"]:
        print(f"[IG stats] Instagram refused some numbers: {err}")
    for x in p[:10]:
        print(f"  {x['date']} {x['kind']:8} reach {x['reach']}  views {x['views']}  likes {x['likes']}  "
              f"saves {x['saves']}  shares {x['shares']}  watched {x['watch_s']}s  {x['title'][:40]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
