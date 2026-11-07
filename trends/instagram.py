"""
instagram.py - post one reel a day to Instagram through the official Graph API.

  python -m trends.instagram          post the oldest video waiting in inbox/ (at most one a day)
  python -m trends.instagram --check  check the token and print the Instagram account it posts to

Videos come from the weekly kit (docs/kit/): you make them in Gemini and upload each one to
inbox/<slug>-<n>/ on GitHub. The folder name picks the caption from data/kit.json.

Instagram fetches the video from a public URL, so it is copied to docs/ideas/<slug>/ and the
website is deployed first. Needs IG_USER_ID and IG_ACCESS_TOKEN (a Page token, which doesn't expire).
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(".env")

from shared.publish import commit_and_push, deploy_site
from trends import site

IST = timezone(timedelta(hours=5, minutes=30))
GRAPH = f"https://graph.facebook.com/{os.getenv('GRAPH_VERSION', 'v24.0')}"
INBOX = Path("inbox")
POSTED_FILE = Path("data/ig_posted.json")
KIT_FILE = Path("data/kit.json")
VIDEO_TYPES = {".mp4", ".mov", ".m4v"}


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _api(method: str, path: str, **params):
    params["access_token"] = os.getenv("IG_ACCESS_TOKEN", "")
    r = requests.request(method, f"{GRAPH}/{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", data["error"]))
    return data


def check() -> int:
    uid = os.getenv("IG_USER_ID", "")
    try:
        me = _api("GET", uid, fields="username,followers_count,media_count")
        print(f"[IG] OK: posting as @{me['username']} ({me.get('followers_count')} followers, {me.get('media_count')} posts)")
        return 0
    except RuntimeError as e:
        print(f"[IG] IG_USER_ID {uid[:4]}… is not an Instagram account ({e}).")
    try:  # say what the ID is instead, and find the Instagram account behind it if it's a Page
        node = _api("GET", uid, fields="id,name", metadata="1")
        print(f"[IG] That ID is a {node.get('metadata', {}).get('type', 'unknown')} named {node.get('name')!r}.")
    except RuntimeError as e:
        print(f"[IG] Couldn't read that ID either: {e}")
    for path in ("me", uid):
        try:
            ig = _api("GET", path, fields="name,instagram_business_account{id,username}").get("instagram_business_account")
            if ig:
                print(f"[IG] The token's Page is linked to @{ig['username']}: set IG_USER_ID to its id "
                      f"(it starts with {ig['id'][:4]} and is {len(ig['id'])} digits long).")
                break
        except RuntimeError:
            pass
    return 1


def caption_for(key: str) -> tuple:
    """(slug, caption) for an inbox folder: the kit's caption, else the theme's reel caption."""
    kit = _load(KIT_FILE, {})
    if key in kit:
        return kit[key]["slug"], kit[key]["caption"]
    from trends.build import reel_caption  # a folder named after a theme slug, without the -n
    slug = key.rsplit("-", 1)[0] if key not in {t["slug"] for t in _load(Path("data/themes.json"), [])} else key
    for th in _load(Path("data/themes.json"), []):
        if th["slug"] == slug:
            return slug, reel_caption(th)
    return "", f"Trending in India this week ✨\n\nComment LINK and we'll DM you every link 💌\n\n#IndianFashion #MyntraFinds"


def _wait_live(url: str, size: int, minutes: int = 20) -> bool:
    """GitHub Pages takes a few minutes to publish a deploy."""
    end = time.time() + minutes * 60
    while time.time() < end:
        try:
            r = requests.head(url, timeout=30)
            if r.status_code == 200 and int(r.headers.get("Content-Length", 0)) == size:
                return True
        except requests.RequestException:
            pass
        time.sleep(30)
    return False


def publish_reel(video_url: str, caption: str) -> str:
    """Instagram's two steps: a media container (Instagram downloads and processes the video), then publish."""
    uid = os.getenv("IG_USER_ID", "")
    container = _api("POST", f"{uid}/media", media_type="REELS", video_url=video_url, caption=caption,
                     share_to_feed="true")["id"]
    for _ in range(60):  # up to 10 minutes
        status = _api("GET", container, fields="status_code,status").get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram couldn't process the video ({status})")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram took too long to process the video")
    media_id = _api("POST", f"{uid}/media_publish", creation_id=container)["id"]
    return _api("GET", media_id, fields="permalink").get("permalink", media_id)


def main() -> int:
    if not os.getenv("IG_USER_ID") or not os.getenv("IG_ACCESS_TOKEN"):
        print("[IG] IG_USER_ID / IG_ACCESS_TOKEN not set; nothing posted.")
        return 0
    posted = _load(POSTED_FILE, [])
    today = datetime.now(IST).strftime("%Y-%m-%d")
    if any(p["ok"] and p["at"].startswith(today) for p in posted) and os.getenv("FORCE") != "1":
        print("[IG] Already posted a reel today.")
        return 0
    # (a fresh checkout gives every file the same time, so this is effectively kit order: slug-1, slug-2...)
    videos = sorted((p for p in INBOX.glob("*/*") if p.suffix.lower() in VIDEO_TYPES),
                    key=lambda p: (p.stat().st_mtime, str(p))) if INBOX.exists() else []
    if not videos:
        print("[IG] No videos in inbox/. Make one from the kit:", f"{site.SITE_URL}/kit/")
        return 0

    video = videos[0]
    key = video.parent.name
    slug, caption = caption_for(key)
    stamp = datetime.now(IST).strftime("%Y%m%d-%H%M")
    dest = Path("docs/ideas") / (slug or "videos") / f"ai-{key}-{stamp}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, dest)
    url = f"{site.SITE_URL}/{dest.relative_to('docs').as_posix()}"
    print(f"[IG] {video} -> {url}")

    if not deploy_site(f"Instagram video {key}") or not _wait_live(url, dest.stat().st_size):
        print("[IG] The video isn't on the website yet; will try again next run.")
        dest.unlink(missing_ok=True)
        return 1
    try:
        link = publish_reel(url, caption)
    except Exception as e:
        print(f"[IG] Posting failed: {e}")
        posted.append({"key": key, "file": video.name, "at": datetime.now(IST).isoformat(timespec="minutes"),
                       "ok": False, "error": str(e)[:300]})
        POSTED_FILE.write_text(json.dumps(posted, ensure_ascii=False, indent=1), encoding="utf-8")
        commit_and_push(f"Instagram: posting {key} failed", [str(POSTED_FILE), "docs"])
        return 1

    print(f"[IG] Posted: {link}")
    posted.append({"key": key, "file": video.name, "at": datetime.now(IST).isoformat(timespec="minutes"),
                   "ok": True, "link": link, "video": url})
    POSTED_FILE.write_text(json.dumps(posted, ensure_ascii=False, indent=1), encoding="utf-8")
    video.unlink()
    commit_and_push(f"Instagram: posted {key}", [str(POSTED_FILE), "inbox", "docs"])
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(check() if "--check" in sys.argv else main())
