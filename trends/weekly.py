"""
weekly.py - the weekly content kit: you make the images and reels once a week in Gemini, the
automation spreads them over the week.

  build_kit(themes)   Monday: data/weekly_kit.json with 14 outfit combos (top + bottom + shoes + bag,
                      ethnic looks, a makeup kit, a decor corner...) from this week's products, each
                      with one reference image of its items (docs/kit/combos/<id>.jpg), a Gemini prompt
                      and an upload link (inbox/combo-<id>/). The 4 reels come from video_plan.json.
  notify(kit)         a GitHub issue that tags the owner, so GitHub sends an email and an app notification
  ingest()            hourly: an uploaded combo image gets the "COMMENT LINK / FULL OUTFIT COMBO AT JUST
                      ₹X" headline, a page on the website (docs/looks/<id>/) and pin dates (2 a day);
                      data/looks.json records it. Posting: trends/post.py (pins) and trends/instagram.py
                      (carousels on Tue, Thu and Sat).
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from trends.pins import _font, _on_white
from trends.reel import short_label
from trends.research import BOARD_BEAUTY, BOARD_ETHNIC, BOARD_HOME, BOARD_MEN, BOARD_WOMEN

IST = timezone(timedelta(hours=5, minutes=30))
REPO = "harshhaldankar/earnkaro_pinterest_automation"
SITE_URL = "https://harshhaldankar.github.io/Getyourdeal"
KIT_FILE = Path("data/weekly_kit.json")
LOOKS_FILE = Path("data/looks.json")
INBOX = Path("inbox")
COMBOS_PER_WEEK = 14
PINS_PER_DAY = 2
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
    return "₹{:,}".format(int(round(v)))


# ---------- the kit ----------
def role_of(p: dict, gender: str) -> tuple:
    """(role, gender) of a product: top / main (kurti, saree, dress) / bottom / shoes / bag / extra / beauty / home."""
    c = p["category"]
    g = "men" if c.startswith("men") else "women" if c.startswith("women") else gender
    if c.startswith("beauty"):
        return "beauty", "women"
    if c.startswith("home"):
        return "home", "any"
    if "footwear" in c:
        return "shoes", g
    if "handbag" in c or "wallet" in c:
        return "bag", g
    if c.startswith("accessories"):
        return "extra", g
    if any(k in c for k in ("jeans", "trousers")):
        return "bottom", g
    if any(k in c for k in ("kurta", "sarees")):
        return "ethnic", "women"
    if "dresses" in c:
        return "dress", "women"
    return "top", g


# (label, board, roles in the order they're laid out, the Gemini layout for those roles)
TEMPLATES = [
    ("Men's casual look", BOARD_MEN, "men", ["top", "bottom", "shoes", "extra?"],
     "the shirt or t-shirt on a wooden hanger at the top left, the jeans or trousers laid flat on the right, "
     "the shoes at the bottom left, the watch or accessory small at the bottom centre"),
    ("Women's casual look", BOARD_WOMEN, "women", ["top", "bottom", "shoes", "bag?"],
     "the top on a wooden hanger at the top left, the jeans laid flat on the right, the shoes at the bottom left, "
     "the bag at the bottom centre"),
    ("Ethnic look", BOARD_ETHNIC, "women", ["ethnic", "shoes", "bag?", "extra?"],
     "the kurta or saree on a wooden hanger in the centre-left, the footwear at the bottom left, the bag on the "
     "right, the jewellery small at the bottom right"),
    ("Dress look", BOARD_WOMEN, "women", ["dress", "shoes", "bag?"],
     "the dress on a wooden hanger in the centre-left, the shoes at the bottom left, the bag on the right"),
    ("Makeup kit", BOARD_BEAUTY, "women", ["beauty", "beauty", "beauty", "beauty?"],
     "the makeup products arranged neatly on a marble tray with a few dried flowers"),
    ("Home decor corner", BOARD_HOME, "any", ["home", "home", "home?"],
     "the decor items styled together on a wooden console table, with a plant"),
]
# how many of each per week (14), in the order they go out
WEEK_PLAN = ["Men's casual look", "Women's casual look", "Ethnic look", "Men's casual look", "Ethnic look",
             "Women's casual look", "Makeup kit", "Ethnic look", "Men's casual look", "Dress look",
             "Women's casual look", "Home decor corner", "Ethnic look", "Men's casual look"]


def _pool(themes: list) -> dict:
    """{(role, gender): [product]} from the trends still being pinned, with their photo and tracked link."""
    cutoff = (datetime.now(IST) - timedelta(days=21)).isoformat()
    pool = {}
    for th in themes:
        if th.get("built_at", "") < cutoff:
            continue
        for i, p in enumerate(th["products"], 1):
            photo = Path("docs/ideas") / th["slug"] / f"p{i}.jpg"
            if not photo.exists():
                continue
            role = role_of(p, th.get("gender", "women"))
            item = {"slug": th["slug"], "n": i, "photo": photo.as_posix(), "name": short_label(p["name"], p["brand"]),
                    "brand": p["brand"], "store": p["store"], "price": p["price"], "link": p["link"], "role": role[0]}
            pool.setdefault(role, []).append(item)
    return pool


def _reference_sheet(items: list, out: Path):
    """The combo's items side by side on white, one image to attach in Gemini."""
    cell = 520
    c = Image.new("RGB", (cell * len(items) + 20 * (len(items) + 1), cell + 40), "white")
    for k, it in enumerate(items):
        im = Image.open(it["photo"]).convert("RGB")
        im.thumbnail((cell, cell))
        c.paste(im, (20 + k * (cell + 20) + (cell - im.width) // 2, 20 + (cell - im.height) // 2))
    out.parent.mkdir(parents=True, exist_ok=True)
    c.save(out, "JPEG", quality=90)


def prompt_for(label: str, layout: str, n: int) -> str:
    what = "these products" if label in ("Makeup kit", "Home decor corner") else "these clothes and accessories"
    return (f"Create a premium flat-lay fashion photo, vertical 4:5. Use exactly {what} from the attached image "
            f"({n} items: same colours, patterns, materials and details; leave out any models or mannequins): "
            f"{layout}. Warm beige wall, soft diagonal window light and gentle shadows, realistic fabric texture, "
            f"high-end catalogue look, everything in sharp focus. Leave the top 20% of the image empty (plain wall) "
            f"for a headline. No text, no people, no logos, no watermarks.")


def build_kit(themes: list) -> dict:
    """data/weekly_kit.json: this week's 14 combos (and the reels, from video_plan.json)."""
    week = themes[0]["week"] if themes else ""
    pool = _pool(themes)
    used = {}  # (role, gender) -> how many taken so far, so each combo takes the next item
    combos = []
    by_label = {t[0]: t for t in TEMPLATES}
    for label in WEEK_PLAN * 2:  # a second pass fills in if a look type had no products
        if len(combos) >= COMBOS_PER_WEEK:
            break
        _, board, gender, roles, layout = by_label[label]
        items, ok = [], True
        for r in roles:
            optional = r.endswith("?")
            key = (r.rstrip("?"), gender)
            cands = pool.get(key, []) or (pool.get((key[0], "any"), []) if key[0] == "home" else [])
            cands = [c for c in cands if c not in items]
            if not cands:
                if optional:
                    continue
                ok = False
                break
            k = used.get(key, 0)
            used[key] = k + 1
            items.append(cands[k % len(cands)])
        if not ok or len(items) < 2:
            continue
        n = len(combos) + 1
        cid = f"{week}-c{n:02d}"
        sheet = Path("docs/kit/combos") / f"{cid}.jpg"
        _reference_sheet(items, sheet)
        combos.append({
            "id": cid, "n": n, "label": label, "board": board, "items": items,
            "total": round(sum(i["price"] for i in items)), "sheet": sheet.relative_to("docs").as_posix(),
            "prompt": prompt_for(label, layout, len(items)),
            "upload": f"https://github.com/{REPO}/upload/master/inbox/combo-{cid}",
        })
    plan = _load(Path("data/video_plan.json"), {}).get("videos", [])
    reels, kinds = [], set()
    for v in plan:  # 4 reels of different kinds where possible (clothing, footwear, bag...)
        if len(reels) < 4 and (v["kind"] not in kinds or len(kinds) >= 3):
            reels.append(v["key"])
            kinds.add(v["kind"])
    kit = {"week": week, "made": datetime.now(IST).isoformat(timespec="minutes"), "combos": combos, "reels": reels}
    _save(KIT_FILE, kit)
    print(f"[Kit] {len(combos)} outfit combos and {len(reels)} reels for the week of {week}")
    return kit


def notify(kit: dict) -> bool:
    """A GitHub issue tagging the owner: GitHub emails it and shows it in the mobile app."""
    import requests
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY", REPO)
    if not token or not kit.get("combos"):
        print("[Kit] No GITHUB_TOKEN (or no combos): no notification")
        return False
    body = (f"@{repo.split('/')[0]} this week's content kit is ready: **{len(kit['combos'])} outfit images** and "
            f"**{len(kit['reels'])} reels**.\n\n"
            f"Make them in Gemini and upload them here (each card has its photo, prompt and upload button):\n"
            f"{SITE_URL}/dashboard/#weekly-kit\n\n"
            f"Once uploaded, they go out on their own: 2 outfit pins a day on Pinterest, carousels on Instagram on "
            f"Tue, Thu and Sat, reels on Mon, Wed, Fri and Sun.\n\n"
            + "\n".join(f"- [ ] {c['n']}. {c['label']} (full look {_rs(c['total'])})" for c in kit["combos"]))
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                      json={"title": f"🗓️ Weekly content kit ready: week of {kit['week']}", "body": body})
    print(f"[Kit] Notification issue: {r.status_code}")
    return r.status_code == 201


# ---------- uploads -> finished looks ----------
def finish_image(src: Path, out: Path, total: float, label: str):
    """The uploaded image at 1080x1350 with the headline at the top, on a soft light band."""
    W, H = 1080, 1350
    im = Image.open(src).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    band = Image.new("RGBA", (W, H))
    bd = ImageDraw.Draw(band)
    for y in range(330):  # light fade behind the text, so it reads on any background
        bd.line((0, y, W, y), fill=(250, 244, 236, int(200 * (1 - y / 330) ** 1.3)))
    c = im.convert("RGBA")
    c.alpha_composite(band)
    d = ImageDraw.Draw(c)
    f = _font("PlayfairDisplay.ttf", 112)
    try:  # Playfair is a variable font: its bold weight, like the magazine headline it imitates
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    a, b = "COMMENT ", "LINK"
    wa, wb = d.textlength(a, font=f), d.textlength(b, font=f)
    x0 = (W - wa - wb) / 2
    d.text((x0, 52), a, font=f, fill=(20, 16, 18))
    d.text((x0 + wa, 52), b, font=f, fill=(128, 22, 28))
    what = "FULL KIT" if label == "Makeup kit" else "FULL CORNER" if label == "Home decor corner" else "FULL OUTFIT COMBO"
    d.text((W / 2, 212), f"(  {what} AT JUST {_rs(total)}/-  )", font=_font("Roboto-Bold.ttf", 34),
           fill=(60, 50, 52), anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    c.convert("RGB").save(out, "JPEG", quality=92)


def look_page(combo: dict):
    """docs/looks/<id>/: the image and every item with its shop link."""
    from trends import site
    items = "".join(f"""
      <article class="product">
        <div class="pic"><img src="../../{escape(i['photo'][5:])}" alt="{escape(i['name'])}" loading="lazy"></div>
        <div class="body"><span class="brand">{escape(i['brand'] or i['store'])}</span>
          <h3 class="name">{escape(i['name'])}</h3>
          <div class="price"><b>{_rs(i['price'])}</b></div>
          <a class="btn primary" href="{escape(i['link'])}" target="_blank" rel="noopener sponsored nofollow">See it on {escape(i['store'])}</a>
        </div></article>""" for i in combo["items"])
    body = f"""
  <main class="wrap">
    <div class="crumbs"><a href="../../">All ideas</a> &rsaquo; {escape(combo['label'])}</div>
    <section class="hero">
      <span class="eyebrow">Outfit combo</span>
      <h1>{escape(combo['label'])}: full look {_rs(combo['total'])}</h1>
      <p>Every piece of this look, with a link to shop it. Prices change quickly; the store's price is the one that counts.</p>
    </section>
    <p><img src="pin.jpg" alt="{escape(combo['label'])}" style="width:100%;max-width:540px;border-radius:16px;display:block;margin:0 auto 24px"></p>
    <section class="products" aria-label="Pieces">{items}</section>
  </main>"""
    folder = site.DOCS / "looks" / combo["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(site._page(f"{combo['label']} – Get Your Deal",
                                                  f"{combo['label']}: every piece with a link, full look {_rs(combo['total'])}.",
                                                  body, "../../", f"{SITE_URL}/looks/{combo['id']}/pin.jpg",
                                                  f"{SITE_URL}/looks/{combo['id']}/"), encoding="utf-8")


def _next_pin_day(looks: list) -> str:
    """The first day from today with fewer than PINS_PER_DAY outfit pins scheduled."""
    day = datetime.now(IST).date()
    count = {}
    for lk in looks:
        count[lk["pin_day"]] = count.get(lk["pin_day"], 0) + 1
    while count.get(day.isoformat(), 0) >= PINS_PER_DAY:
        day += timedelta(days=1)
    return day.isoformat()


def ingest() -> int:
    """Uploaded combo images -> finished looks. Returns how many were added."""
    kit = _load(KIT_FILE, {})
    combos = {c["id"]: c for c in kit.get("combos", [])}
    looks = _load(LOOKS_FILE, [])
    have = {lk["id"] for lk in looks}
    added = 0
    for folder in sorted(INBOX.glob("combo-*")) if INBOX.exists() else []:
        cid = folder.name[len("combo-"):]
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES)
        combo = combos.get(cid)
        if not files or not combo or cid in have:
            if cid in have or not combo:  # a second upload of the same look, or last week's: tidy up
                for p in files:
                    p.unlink()
            continue
        out = Path("docs/looks") / cid / "pin.jpg"
        try:
            finish_image(files[0], out, combo["total"], combo["label"])
        except Exception as e:
            print(f"[Kit] {files[0]} couldn't be read: {e}")
            continue
        look_page(combo)
        looks.append({"id": cid, "label": combo["label"], "board": combo["board"], "total": combo["total"],
                      "image": out.as_posix(), "page": f"{SITE_URL}/looks/{cid}/", "at": datetime.now(IST).isoformat(timespec="minutes"),
                      "pin_day": _next_pin_day(looks), "items": [i["name"] for i in combo["items"]]})
        for p in files:
            p.unlink()
        added += 1
        print(f"[Kit] {cid} {combo['label']}: finished, pin on {looks[-1]['pin_day']}")
    if added:
        _save(LOOKS_FILE, looks)
    return added


def look_pins(today: str) -> list:
    """Queue items for post.py: the looks whose pin day has come."""
    out = []
    for lk in _load(LOOKS_FILE, []):
        if lk["pin_day"] > today or not Path(lk["image"]).exists():
            continue
        words = " · ".join(lk["items"][:3])
        out.append({"id": f"{lk['pin_day']}:look:{lk['id']}", "image": lk["image"],
                    "title": f"{lk['label']} under {_rs(lk['total'])}: full outfit combo"[:100],
                    "description": (f"{lk['label']}: {words}. The full look for {_rs(lk['total'])}, every piece with a "
                                    f"link. Save it for your next shopping trip. #OutfitIdeas #OutfitInspo "
                                    f"#IndianFashion #AffordableFashion #OutfitCombo")[:500],
                    "link": lk["page"], "board": lk["board"]})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--ingest" in sys.argv:
        n = ingest()
        print(f"[Kit] {n} new looks")
        if n and os.getenv("PUBLISH", "1") == "1":
            from shared.publish import deploy_site
            deploy_site(f"{n} new outfit looks")
    else:
        kit = build_kit(_load(Path("data/themes.json"), []))
        if "--notify" in sys.argv:
            notify(kit)
