"""
create.py - one trending deal from the control room ("korean pants", say) as pins, a reel and a story.

The "5 · Create" workflow runs it with the control room form (CR_* environment variables). Photos the
control room uploaded are in inbox/create/<id>/ (Gemini images or your own pictures). Without them,
a Myntra/AJIO deal takes matching photos from EarnKaro's catalogue, and otherwise the designs are
type only. Amazon's own product photos are never used (Amazon allows them only through its tools).

  link    Amazon: the deal link, or an Amazon search, with our Associates tag
          Myntra / AJIO: an EarnKaro tracked link to the deal, or to the store's search
  board   from the trend's words and audience (research.py's boards), unless the form picks one
  pins    one per photo (up to 4) and a mood board with 4 photos, or a type-only pin; queued
          first, so they go out in the next hourly runs
  reel    with 3 or more photos: the editorial reel, posted tonight (first in line) or right away;
          with fewer, a Gemini prompt and caption to make the video yourself
  story   1080x1920, with room at the bottom for Instagram's link sticker; or posted right away
          (the API can't add link stickers, so a posted story says "link in bio")
Each run is listed in data/created.json, which the control room shows, and on the website's
"Hot right now" strips (home page; Amazon ones on the Amazon picks page too).
"""
import asyncio
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv(".env")

from shared.publish import commit_and_push, deploy_site
from trends import site
from trends.pins import _fill, _font, _headline_lines, _pastel, clean_headline, create_moodboard_pin, create_natural_pin
from trends.research import (BOARD_ACCESSORIES, BOARD_BEAUTY, BOARD_ETHNIC, BOARD_HOME, BOARD_MEN, BOARD_SHOES,
                             BOARD_WOMEN, TYPES, products_for, slug_of, theme_key, title_of, type_of)

IST = timezone(timedelta(hours=5, minutes=30))
CREATED_FILE = Path("data/created.json")
QUEUE_FILE = Path("data/queue.json")
BOARD_AMAZON = "Amazon Finds India"
BOARDS = [BOARD_WOMEN, BOARD_MEN, BOARD_ETHNIC, BOARD_SHOES, BOARD_ACCESSORIES, BOARD_BEAUTY, BOARD_HOME, BOARD_AMAZON]
STORES = {"amazon": "Amazon", "myntra": "Myntra", "ajio": "AJIO"}
STORE_COLOR = {"Amazon": (255, 153, 0), "Myntra": (255, 63, 108), "AJIO": (44, 65, 82)}
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _rs(v) -> str:
    return f"₹{v:,.0f}"


# ---------- what the form asked for ----------
def read_form() -> dict:
    trend = re.sub(r"\s+", " ", re.sub(r"[^\w\s&'-]", " ", os.getenv("CR_TREND", ""))).strip()[:60]
    if len(trend) < 3:
        raise SystemExit("[Create] Type a trend, like 'korean pants'.")
    fid = os.getenv("CR_ID", "")
    if not re.fullmatch(r"[a-z0-9-]{6,40}", fid):
        fid = datetime.now(IST).strftime("%Y%m%d%H%M%S")
    audience = os.getenv("CR_AUDIENCE", "women").lower()
    store = STORES.get(os.getenv("CR_STORE", "amazon").lower(), "Amazon")
    make = {m.strip() for m in os.getenv("CR_MAKE", "pins,reel,story").lower().split(",") if m.strip()}
    return dict(id=fid, trend=trend, audience=audience if audience in ("women", "men", "everyone") else "women",
                store=store, link=os.getenv("CR_LINK", "").strip(), line=os.getenv("CR_LINE", "").strip()[:60],
                board=os.getenv("CR_BOARD", "").strip(), make=make,
                reel=os.getenv("CR_REEL", "tonight").lower(), story=os.getenv("CR_STORY", "download").lower())


def phrase_of(f: dict) -> str:
    """The search words: the trend plus the audience ('korean pants women')."""
    p = f["trend"].lower()
    if f["audience"] in ("women", "men") and not re.search(r"\b(wom[ae]n|m[ae]n|girls?|boys?|ladies)\b", p):
        p += " " + f["audience"]
    return p


def board_of(f: dict, phrase: str) -> str:
    """The form's board, or the one research.py gives this kind of thing, by audience."""
    if f["board"] in BOARDS:
        return f["board"]
    t = type_of(phrase)
    b = TYPES[t]["board"] if t else None
    if b in (None, BOARD_MEN, BOARD_WOMEN):  # a generic fashion board goes by who it's for
        if not t and f["store"] == "Amazon":
            return BOARD_AMAZON  # a heater or a charger isn't an outfit
        b = BOARD_MEN if f["audience"] == "men" else BOARD_WOMEN
    return b


def amazon_link(url: str, phrase: str) -> str:
    """The deal's Amazon.in link with our tag (any other tag replaced), or an Amazon search."""
    u = urlsplit(url) if url else None
    if u and u.scheme == "https" and (u.hostname or "").endswith("amazon.in"):
        q = [(k, v) for k, v in parse_qsl(u.query) if k != "tag"] + [("tag", site.AMAZON_TAG)]
        return urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), ""))
    if u and (u.hostname or "") in ("amzn.to", "amzn.in"):
        return url  # a SiteStripe short link already carries the tag it was made with
    return site.amazon(phrase)


# ---------- designs ----------
def _badge(d, cx, y, store, size=30):
    f = _font("Roboto-Bold.ttf", size)
    txt = f"ON {store.upper()}"
    w = d.textlength(txt, font=f) + 2 * size
    d.rounded_rectangle((cx - w / 2, y, cx + w / 2, y + size * 2), radius=size, fill=STORE_COLOR[store])
    d.text((cx, y + size), txt, font=f, fill=(255, 255, 255) if store != "Amazon" else (20, 20, 20), anchor="mm")


def create_type_pin(out: str, title: str, line: str, store: str, seed: int = 0):
    """No photo: a big serif title on a pastel card, the deal line and the store."""
    return _type_card(1000, 1500, out, title, line, store, seed, "TRENDING IN INDIA", "getyourdeal")


def _type_card(W, H, out, title, line, store, seed, eyebrow, foot):
    c = _pastel(W, H, seed)
    d = ImageDraw.Draw(c)
    words, lines, f = clean_headline(title).split(), [], _font("PlayfairDisplay.ttf", 112)
    for w in words:  # wrap at ~82% of the width, up to 4 lines
        if lines and d.textlength(lines[-1] + " " + w, font=f) <= W * 0.82:
            lines[-1] += " " + w
        else:
            lines.append(w)
    lines = lines[:4]
    y = H * 0.43 - 65 * (len(lines) - 1)
    d.text((W / 2, y - 170), eyebrow, font=_font("Roboto-Bold.ttf", 30), fill=(120, 100, 110), anchor="mm")
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill=(40, 32, 38), anchor="mm")
        y += 130
    if line:
        d.text((W / 2, y + 40), line, font=_font("Roboto-Bold.ttf", 40), fill=(95, 80, 88), anchor="mm")
        y += 80
    _badge(d, W / 2, y + 60, store)
    d.text((W / 2, H - (60 if H < 1800 else 300)), foot, font=_font("Roboto-Bold.ttf", 26 if H < 1800 else 32),
           fill=(150, 130, 140), anchor="mm")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    c.save(out, "JPEG", quality=90)
    return out


def create_story(photo, out: str, title: str, line: str, store: str, seed: int = 0):
    """1080x1920 story: the photo on top (or a pastel card), the title and line on a cream band, and
    an empty strip at the bottom for Instagram's link sticker."""
    W, H, band = 1080, 1920, 620
    if not photo:  # (the bottom ~300px stays clear for the sticker)
        return _type_card(W, H, out, title, line, store, seed, "TRENDING NOW", "Tap the link below")
    c = Image.new("RGB", (W, H), (250, 245, 240))
    c.paste(_fill(photo, W, H - band + 60, seed), (0, 0))
    fade = Image.new("RGBA", (W, 120))
    fd = ImageDraw.Draw(fade)
    for y in range(120):
        fd.line((0, y, W, y), fill=(250, 245, 240, int(255 * y / 120)))
    c.paste(fade, (0, H - band - 60), fade)
    top = H - band + 40
    d = ImageDraw.Draw(c)
    d.text((W / 2, top), "TRENDING NOW", font=_font("Roboto-Bold.ttf", 30), fill=(120, 100, 110), anchor="mm")
    lines, size = _headline_lines(d, clean_headline(title) or title, max_w=940)
    hf = _font("PlayfairDisplay.ttf", size + 14)
    y = top + 90
    for ln in lines:
        d.text((W / 2, y), ln, font=hf, fill=(40, 32, 38), anchor="mm")
        y += size + 26
    if line:
        d.text((W / 2, y + 10), line, font=_font("Roboto-Bold.ttf", 40), fill=(95, 80, 88), anchor="mm")
        y += 60
    _badge(d, W / 2, y + 30, store, 28)
    d.text((W / 2, H - 120), "Tap the link below", font=_font("Roboto-Bold.ttf", 30), fill=(150, 130, 140), anchor="mm")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    c.save(out, "JPEG", quality=90)
    return out


def gemini_prompt(f: dict, title: str) -> str:
    who = "man" if f["audience"] == "men" else "woman"
    return (f"Create an 8-second 9:16 vertical fashion film about the trend \"{title}\" in India. A young Indian {who} "
            f"wears a stylish {f['trend'].lower()} look in a sunlit minimal studio with cream walls and soft shadows. "
            f"Slow push-in, a close-up of the fabric and details, then a pull back to the full look. Soft cinematic "
            f"light, shallow depth of field, premium magazine look. No text. Light, upbeat instrumental music. "
            f"(If you have a photo of the exact product, attach it and add: keep the product exactly as in the photo.)")


def caption(f: dict, title: str, tags: str) -> str:
    deal = f["line"] or f"Find it on {f['store']}"
    ad = "\n\n#ad As an Amazon Associate we earn from qualifying purchases." if f["store"] == "Amazon" else ""
    return (f"{title} is trending in India right now 🔥\n\n{deal} 🛍️\n\n"
            f"Comment LINK and we'll DM you the link 💌\nOr tap the link in our bio 🔗\nSave this for later ✨\n\n{tags}{ad}")


def hashtags(f: dict, title: str) -> str:
    base = ["#" + re.sub(r"[^A-Za-z0-9]", "", title.title())]
    base += [f"#{f['store']}Finds", "#TrendingInIndia"]
    base += ["#AmazonIndia", "#AmazonDeals"] if f["store"] == "Amazon" else ["#IndianFashion", "#AffordableFashion"]
    return " ".join(dict.fromkeys(base))


# ---------- the run ----------
async def make_link_and_photos(f: dict, phrase: str, folder: Path) -> tuple:
    """(tracked link, [photo paths], [catalogue products]) - an EarnKaro login only for Myntra/AJIO."""
    photos = []
    inbox = Path("inbox/create") / f["id"]
    for i, p in enumerate(sorted(x for x in inbox.glob("*") if x.suffix.lower() in PHOTO_TYPES)[:6], 1):
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((1600, 1600))
            out = folder / f"p{i}.jpg"
            im.save(out, "JPEG", quality=90)
            photos.append(str(out))
        except Exception as e:
            print(f"[Create] Skipped photo {p.name}: {e}")
    if f["store"] == "Amazon":
        return amazon_link(f["link"], phrase), photos, []

    from trends.build import download, store_search
    from trends.catalog import EarnKaroSession
    host = urlsplit(f["link"]).hostname or "" if f["link"] else ""
    target = f["link"] if host.endswith(f"{f['store'].lower()}.com") else store_search(f["store"], phrase)
    prods = []
    async with EarnKaroSession() as ek:
        link = await ek.make_link(target)
        key = theme_key(phrase)
        if not photos and key and key[0] in TYPES:
            catalog = await ek.products(sorted({c for c in (TYPES[key[0]]["cats"].get(key[1], []) if isinstance(TYPES[key[0]]["cats"], dict)
                                                             else TYPES[key[0]]["cats"])}))
            for p in [p for p in products_for(key, catalog) if p["store"] == f["store"]][:6]:
                out = folder / f"p{len(photos) + 1}.jpg"
                if download(p["image"], out):
                    photos.append(str(out))
                    prods.append(p)
    if not link:
        raise SystemExit(f"[Create] EarnKaro couldn't make a link for {target}")
    return link, photos, prods


async def main() -> int:
    f = read_form()
    now = datetime.now(IST)
    phrase = phrase_of(f)
    title = title_of(f["trend"].lower() + (f" for {f['audience']}" if f["audience"] in ("women", "men")
                                           and f["audience"] not in f["trend"].lower() else ""))
    slug = slug_of(title)
    board = board_of(f, phrase)
    folder = site.DOCS / "deals" / slug
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    print(f"[Create] {title} · {f['store']} · board: {board}")

    link, photos, prods = await make_link_and_photos(f, phrase, folder)
    line = f["line"] or (f"From {_rs(min(p['price'] for p in prods))} on {f['store']}" if prods else f"Shop it on {f['store']}")
    tags = hashtags(f, title)
    cap = caption(f, title, tags)
    disclosure = " #ad As an Amazon Associate we earn from qualifying purchases." if f["store"] == "Amazon" else ""
    entry = dict(id=f["id"], at=now.isoformat(timespec="minutes"), trend=f["trend"], title=title, slug=slug,
                 audience=f["audience"], store=f["store"], board=board, link=link, line=line, photos=len(photos),
                 caption=cap, pins=0)

    # pins: first in the queue
    if "pins" in f["make"]:
        pin_dir = Path("data/pin_images") / f"deal-{slug}"
        made = []
        if len(photos) >= 4:
            made.append(create_moodboard_pin(photos[:4], str(pin_dir / "board.jpg"), title, line, seed=1))
        for i, ph in enumerate(photos[:4], 1):
            made.append(create_natural_pin(ph, str(pin_dir / f"pin{i}.jpg"), title, line, seed=i))
        if not photos:
            made += [create_type_pin(str(pin_dir / f"type{s}.jpg"), title, line, f["store"], seed=s) for s in (0, 1)]
        made = [m for m in made if m]
        stamp = now.strftime("%Y-%m-%d")
        queue = _load(QUEUE_FILE, [])
        ids = {q["id"] for q in queue}
        new = [{"id": f"{stamp}:deal-{slug}:{Path(m).stem}", "image": Path(m).as_posix(),
                "title": f"{title} · {line}"[:100],
                "description": (f"{title}, trending in India right now. {line}. Tap to shop on {f['store']}. "
                                f"{tags}{disclosure}")[:500],
                "link": link, "board": board} for m in made]
        new = [q for q in new if q["id"] not in ids]
        _save(QUEUE_FILE, new + queue)
        entry["pins"] = len(new)
        if made:
            shutil.copy(made[0], folder / "card.jpg")
        print(f"[Create] {len(new)} pins queued first, on {board}")

    # story
    if "story" in f["make"]:
        create_story(photos[0] if photos else None, str(folder / "story.jpg"), title, line, f["store"])
        entry["story"] = f"{site.SITE_URL}/deals/{slug}/story.jpg"
        if not (folder / "card.jpg").exists():
            shutil.copy(folder / "story.jpg", folder / "card.jpg")

    # reel
    reel_key = None
    if "reel" in f["make"]:
        if len(photos) >= 3:
            from trends.editorial import create_editorial_reel
            from trends.reel import short_label
            items = ([dict(img=ph, label=short_label(p["name"], p["brand"]), price=p["price"], mrp=p["mrp"], store=p["store"])
                      for ph, p in zip(photos, prods)] if prods else
                     [dict(img=ph, label=title, price=0, line=line, store=f["store"]) for ph in photos])
            if create_editorial_reel(items, str(folder / "reel.mp4"), title, line):
                entry["reel"] = f"{site.SITE_URL}/deals/{slug}/reel.mp4"
                if f["reel"] == "tonight":  # inbox videos go before the weekly reels; "00-" sorts first
                    reel_key = f"00-deal-{slug}"
                    (Path("inbox") / reel_key).mkdir(parents=True, exist_ok=True)
                    shutil.copy(folder / "reel.mp4", Path("inbox") / reel_key / "reel.mp4")
                    entry["reel_status"] = "posts tonight (first in line)"
        if "reel" not in entry:
            entry["gemini"] = {"prompt": gemini_prompt(f, title),
                               "upload": f"https://github.com/harshhaldankar/earnkaro_pinterest_automation/upload/master/inbox/00-deal-{slug}"}
            entry["reel_status"] = "make the video in Gemini, then upload it"
            reel_key = f"00-deal-{slug}"
    entry["inbox_key"] = reel_key

    created = [c for c in _load(CREATED_FILE, []) if c.get("slug") != slug]
    created.insert(0, entry)
    _save(CREATED_FILE, created[:30])
    shutil.rmtree(Path("inbox/create") / f["id"], ignore_errors=True)
    site.rebuild(_load(Path("data/themes.json"), []))

    if os.getenv("PUBLISH", "1") != "1":
        print(json.dumps(entry, ensure_ascii=False, indent=1))
        return 0
    if not commit_and_push(f"Create: {title} ({f['store']})", ["data", "docs", "inbox"]):
        return 1
    deploy_site(f"Create: {title}")

    # right away, if asked: Instagram downloads from the live site
    from trends import instagram as ig
    if f["reel"] == "now" and entry.get("reel") or f["story"] == "now" and entry.get("story"):
        posted = _load(ig.POSTED_FILE, [])
        for kind in ("reel", "story"):
            if f[kind] != "now" or not entry.get(kind):
                continue
            path = folder / ("reel.mp4" if kind == "reel" else "story.jpg")
            if not ig._wait_live(entry[kind], path.stat().st_size):
                entry[f"{kind}_status"] = "the website didn't update in time; not posted"
                continue
            try:
                permalink = ig.publish_reel(entry[kind], cap) if kind == "reel" else ig.publish_story(entry[kind])
                entry[f"{kind}_status"], entry[f"{kind}_link"] = "posted", permalink
                if kind == "reel":  # counts as today's reel
                    posted.append({"key": f"deal:{slug}", "file": "reel.mp4", "at": datetime.now(IST).isoformat(timespec="minutes"),
                                   "ok": True, "link": permalink, "video": entry["reel"]})
            except Exception as e:
                entry[f"{kind}_status"] = f"posting failed: {str(e)[:160]}"
            print(f"[Create] {kind}: {entry[f'{kind}_status']}")
        _save(ig.POSTED_FILE, posted)
        created[0] = entry
        _save(CREATED_FILE, created[:30])
        commit_and_push(f"Create: posted {title}", ["data"])
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
