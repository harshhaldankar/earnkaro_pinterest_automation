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
VERSION = os.getenv("GRAPH_VERSION", "v24.0")
INBOX = Path("inbox")
POSTED_FILE = Path("data/ig_posted.json")
KIT_FILE = Path("data/kit.json")
NEW_TOKEN_FILE = Path(".ig_token")  # a renewed Instagram-login token; the workflow saves it as the secret
VIDEO_TYPES = {".mp4", ".mov", ".m4v"}


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _ig_login() -> bool:
    """Two kinds of token work: a Facebook Page/user token (EAA…, Instagram linked to a Page) or an
    Instagram-login token (IG…, no Page needed, lasts 60 days and is renewed by refresh_token())."""
    return os.getenv("IG_ACCESS_TOKEN", "").startswith("IG")


def _api(method: str, path: str, **params):
    params["access_token"] = os.getenv("IG_ACCESS_TOKEN", "")
    host = "graph.instagram.com" if _ig_login() else "graph.facebook.com"
    r = requests.request(method, f"https://{host}/{VERSION}/{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", data["error"]))
    return data


def ig_user_id() -> str:
    """IG_USER_ID may be the Instagram account's ID or its Facebook Page's ID; for a Page, the
    Instagram professional account linked to it. '' if there's none.
    With an Instagram-login token the account is the token's own, so IG_USER_ID isn't needed."""
    if _ig_login():
        return str(_api("GET", "me", fields="user_id,username").get("user_id", ""))
    uid = os.getenv("IG_USER_ID", "")
    try:
        if _api("GET", uid, fields="media_count").get("media_count") is not None:
            return uid
    except RuntimeError:
        pass
    for path in (uid, "me"):  # a Page (by ID, or the Page the token belongs to)
        try:
            ig = _api("GET", path, fields="name,instagram_business_account").get("instagram_business_account")
            if ig:
                return ig["id"]
        except RuntimeError:
            pass
    try:  # a token made for the Instagram account itself (business login): the account it may post to
        info = _api("GET", "debug_token", input_token=os.getenv("IG_ACCESS_TOKEN", ""))["data"]
        for scope in info.get("granular_scopes", []):
            if scope["scope"] in ("instagram_content_publish", "instagram_basic") and scope.get("target_ids"):
                return scope["target_ids"][0]
    except (RuntimeError, KeyError):
        pass
    return ""


def refresh_token():
    """Instagram-login tokens expire 60 days after they're issued or renewed; renew on every run and
    leave the new one in .ig_token for the workflow to store. Facebook Page tokens don't expire."""
    if not _ig_login():
        return
    try:
        r = requests.get(f"https://graph.instagram.com/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": os.getenv("IG_ACCESS_TOKEN")},
                         timeout=60).json()
        if r.get("access_token"):
            NEW_TOKEN_FILE.write_text(r["access_token"], encoding="utf-8")
            os.environ["IG_ACCESS_TOKEN"] = r["access_token"]
            print(f"[IG] Token renewed for {int(r.get('expires_in', 0)) // 86400} days.")
        else:
            print(f"[IG] Token not renewed: {r.get('error', r)}")
    except requests.RequestException as e:
        print(f"[IG] Token not renewed: {e}")


def _diagnose():
    """What Facebook says about the token and the Page (IDs shortened; no tokens printed)."""
    def short(v):
        return f"{str(v)[:4]}…({len(str(v))} digits)" if v else v
    tries = [
        ("token owner", "me", {"fields": "id,name"}),
        ("token permissions", "me/permissions", {}),
        ("Pages of the token's user", "me/accounts", {"fields": "name,instagram_business_account,connected_instagram_account"}),
        ("the Page", os.getenv("IG_USER_ID", ""), {"fields": "name,instagram_business_account,connected_instagram_account,"
                                                             "page_backed_instagram_accounts"}),
        ("token debug", "debug_token", {"input_token": os.getenv("IG_ACCESS_TOKEN", "")}),
    ]
    for label, path, params in tries:
        try:
            data = _api("GET", path, **params)
            text = json.dumps(data)
            for k in ("access_token",):
                text = text.replace(os.getenv("IG_ACCESS_TOKEN", "") or "\0", "***")
            text = __import__("re").sub(r'"(\d{9,})"', lambda m: f'"{short(m.group(1))}"', text)
            print(f"[IG] {label}: {text[:700]}")
        except RuntimeError as e:
            print(f"[IG] {label}: error {e}")


def check() -> int:
    uid = ig_user_id()
    if not uid:
        print("[IG] Couldn't find an Instagram professional account this token may post to. What Facebook says:")
        _diagnose()
        return 1
    me = _api("GET", "me" if _ig_login() else uid, fields="username,followers_count,media_count")
    print(f"[IG] OK: posting as @{me['username']} ({me.get('followers_count')} followers, {me.get('media_count')} posts)")
    return 0


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
    uid = ig_user_id()
    if not uid:
        raise RuntimeError("no Instagram account is linked to the Facebook Page in IG_USER_ID")
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
    if "--check" in sys.argv:
        refresh_token()
        sys.exit(check())
    sys.exit(main())
