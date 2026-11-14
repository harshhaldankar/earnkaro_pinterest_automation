"""
weekly.py - the weekly content kit: you make the images and reels once a week in Gemini (a prompt,
nothing to attach), the automation spreads them over the week.

  build_kit(themes)   Monday: data/weekly_kit.json - 14 trending looks (looks_bank.py, the ones this
                      week's Pinterest India searches mention first), each with a Gemini image prompt
                      (the look worn in a mirror selfie + a flat-lay of the pieces, no text) and shop
                      links for every piece (Myntra search via EarnKaro, Amazon search with our tag);
                      4 of them also get a reel prompt.
  notify(kit)         a GitHub issue tagging the owner (and an email, if the Gmail secrets exist)
  ingest()            hourly: an uploaded image (inbox/look-<id>/) becomes 1080x1350, gets a page on the
                      website (docs/looks/<id>/) and a pin day (2 a day); data/looks.json records it.
Posting: trends/post.py (pins, no text on the image: what gets saved), trends/instagram.py
(carousels Tue/Thu/Sat, reels inbox/reel-<id>/ on the other days).
"""
import asyncio
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from PIL import Image

from trends.looks_bank import LOOKS
from trends.research import BOARD_ETHNIC, BOARD_MEN, BOARD_WOMEN

IST = timezone(timedelta(hours=5, minutes=30))
REPO = "harshhaldankar/earnkaro_pinterest_automation"
SITE_URL = "https://harshhaldankar.github.io/Getyourdeal"
KIT_FILE = Path("data/weekly_kit.json")
LOOKS_FILE = Path("data/looks.json")
INBOX = Path("inbox")
LOOKS_PER_WEEK = 14
REELS_PER_WEEK = 4
PINS_PER_DAY = 2
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
ETHNIC_WORDS = ("kurta", "saree", "lehenga", "anarkali", "sangeet", "haldi", "wedding")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------- the kit ----------
def pick_looks(themes: list, last_week: set, month: int) -> list:
    """14 looks: in season, words that this week's Pinterest India searches use first, not last
    week's, men and women alternating."""
    latest = themes[0]["week"] if themes else ""
    signal = " ".join(p for t in themes if t["week"] == latest for p in [t["phrase"]] + t.get("related", [])).lower()

    def score(lk):
        s = sum(2 for w in lk["words"] if w in signal)
        s += 1 if (not lk["season"] or month in lk["season"]) else -10
        s -= 5 if lk["name"] + lk["gender"] in last_week else 0
        return s
    ranked = sorted(LOOKS, key=score, reverse=True)
    men = [lk for lk in ranked if lk["gender"] == "men" and score(lk) > -5]
    women = [lk for lk in ranked if lk["gender"] == "women" and score(lk) > -5]
    out = []
    while len(out) < LOOKS_PER_WEEK and (men or women):
        for group in (women, men):
            if group and len(out) < LOOKS_PER_WEEK:
                out.append(group.pop(0))
    return out


def image_prompt(lk: dict) -> str:
    who = "man" if lk["gender"] == "men" else "woman"
    ethnic = any(w in lk["name"].lower() for w in ETHNIC_WORDS)
    room = ("an elegant, softly lit room with marigold flowers and warm fairy lights" if ethnic
            else "a minimal light-grey studio with a black leather chair and soft window light")
    pieces = "; ".join(p for p, _ in lk["pieces"])
    return (f"Create a realistic fashion photo, vertical 4:5, split into two halves side by side with a thin white gap. "
            f"LEFT half: a stylish young Indian {who}, early 20s, taking a mirror selfie with a phone that hides the "
            f"face, full body from head to shoes, in {room}, wearing: {pieces}. "
            f"RIGHT half: the same pieces laid out as a neat flat-lay, seen from above, on a light floor: {pieces}. "
            f"Natural daylight, realistic fabric texture, premium fashion-catalogue look, everything in sharp focus. "
            f"No text, no logos, no brand names, no watermark.")


def reel_prompt(lk: dict) -> str:
    who, she, her = ("man", "He", "his") if lk["gender"] == "men" else ("woman", "She", "her")
    pieces = "; ".join(p for p, _ in lk["pieces"])
    return (f"Create an 8-second vertical 9:16 video in a handheld phone, Instagram outfit-check style. A stylish "
            f"young Indian {who}, early 20s, in a minimal light-grey studio with soft window light, wearing: {pieces}. "
            f"0-3s: {she.lower()} lifts {her} phone and checks the fit in a full-length mirror. 3-6s: {she.lower()} turns "
            f"side to side; the clothes move naturally. 6-8s: a quick close-up of the shoes and details, then a smile. "
            f"Realistic skin and fabric, natural light. No text, no captions, no logos, no music.")


def _links(searches: list) -> dict:
    """{search: Myntra link through EarnKaro} with one EarnKaro login (in a thread: the weekly build is
    already inside an event loop). Empty without EarnKaro details or when it fails."""
    if not (os.getenv("EARNKARO_EMAIL") and os.getenv("EARNKARO_PASSWORD")) or os.getenv("KIT_LINKS", "1") != "1":
        return {}

    async def run():
        from trends.build import store_search
        from trends.catalog import EarnKaroSession
        out = {}
        async with EarnKaroSession() as ek:
            for q in searches:
                link = await ek.make_link(store_search("Myntra", q))
                if link:
                    out[q] = link
        return out
    try:
        with ThreadPoolExecutor(1) as ex:
            return ex.submit(asyncio.run, run()).result(timeout=1200)
    except Exception as e:
        print(f"[Kit] EarnKaro links failed ({type(e).__name__}); Amazon links only")
        return {}


def build_kit(themes: list) -> dict:
    """data/weekly_kit.json: this week's 14 looks and 4 reels."""
    from trends import site
    week = themes[0]["week"] if themes else datetime.now(IST).strftime("%Y-%m-%d")
    old = _load(KIT_FILE, {})
    last_week = {c["name"] + c["gender"] for c in old.get("combos", [])} if old.get("week") != week else set()
    looks = pick_looks(themes, last_week, datetime.now(IST).month)
    from trends.catalog import _MYNTRA_NO_PROFIT  # EarnKaro pays nothing on Myntra jewellery: Amazon only
    searches = sorted({q for lk in looks for _, q in lk["pieces"] if not _MYNTRA_NO_PROFIT.search(q)})
    prev = {p["search"]: p.get("myntra") for c in old.get("combos", []) for p in c.get("pieces", []) if p.get("myntra")}
    myntra = {**prev, **_links([q for q in searches if q not in prev])}
    combos = []
    for n, lk in enumerate(looks, 1):
        cid = f"{week}-{_slug(lk['gender'] + '-' + lk['name'])}"
        ethnic = any(w in lk["name"].lower() for w in ETHNIC_WORDS)
        combos.append({
            "id": cid, "n": n, "name": lk["name"], "gender": lk["gender"],
            "board": BOARD_ETHNIC if ethnic else BOARD_MEN if lk["gender"] == "men" else BOARD_WOMEN,
            "pieces": [{"what": what, "search": q, "myntra": myntra.get(q, ""), "amazon": site.amazon(q)} for what, q in lk["pieces"]],
            "prompt": image_prompt(lk), "reel_prompt": reel_prompt(lk),
            "upload": f"https://github.com/{REPO}/upload/master/inbox/look-{cid}",
            "reel_upload": f"https://github.com/{REPO}/upload/master/inbox/reel-{cid}",
        })
    reels = [c["id"] for c in combos[:REELS_PER_WEEK]]
    kit = {"week": week, "made": datetime.now(IST).isoformat(timespec="minutes"), "combos": combos, "reels": reels}
    _save(KIT_FILE, kit)
    print(f"[Kit] {len(combos)} looks and {len(reels)} reels for the week of {week} "
          f"({sum(1 for c in combos for p in c['pieces'] if p['myntra'])} Myntra links)")
    return kit


def find(key: str):
    """The kit look for an upload folder name (look-<id> or reel-<id>), or None."""
    for prefix in ("look-", "reel-"):
        if key.startswith(prefix):
            return next((c for c in _load(KIT_FILE, {}).get("combos", []) if c["id"] == key[len(prefix):]), None)
    return None


def caption(c: dict) -> str:
    pieces = " + ".join(p["search"].rsplit(" ", 1)[0] for p in c["pieces"][:4])
    tags = " ".join("#" + re.sub(r"[^A-Za-z0-9]", "", w.title()) for w in [c["name"].split("+")[0], "outfit ideas",
                                                                             f"{c['gender']} fashion", "OOTD"])
    return (f"{c['name']} 🔥\n\n{pieces}\n\n"
            f"Ye look chahiye? Comment 'LINK' likho, hum har piece ka link DM kar denge 💌\n"
            f"Save karo for later ✨\n\n{tags} #IndianFashion #OutfitInspo #StyleInspo")


# ---------- notifications ----------
GUIDE = """Hi,

Here's how our weekly content works. We make everything once a week; the automation posts it through the week.

Where: {site}/dashboard/#content  (the "Make content" tab, section "This week's kit")

EVERY WEEK (about 45 minutes), usually Monday:
1. 14 outfit images. On each card: "Copy image prompt", paste it in Gemini, generate. Nothing to attach.
   Then "Upload" and upload the image Gemini made.
2. 4 reels. On each reel card: "Copy video prompt", in Gemini choose Video, paste, generate. Then "Upload" it.

WHAT HAPPENS AUTOMATICALLY
- Each image gets its own page on our website with a shop link for every piece (Myntra and Amazon).
- Pinterest: 2 outfit pins every day (no text on the image: that's what gets saved).
- Instagram: a carousel of 4 looks on Tue, Thu, Sat; a reel on Mon, Wed, Fri, Sun.
- Anyone who comments LINK gets the links by DM (ManyChat).

RULES
- Never buy through our own links; never offer anything in return for buying.
- The dashboard shows progress ("x of 14 made") and what goes out each day.

{status}
"""


def kit_status(kit: dict) -> str:
    if not kit.get("combos"):
        return ""
    return (f"THIS WEEK ({kit['week']}): {len(kit['combos'])} outfit images and {len(kit['reels'])} reels to make:\n"
            + "\n".join(f"  {c['n']:2d}. {c['name']} ({c['gender']})" for c in kit["combos"]))


def send_email(subject: str, body: str) -> bool:
    """Through Gmail (an app password). EMAIL_TO: comma-separated addresses, kept in a GitHub secret
    because this repo is public."""
    import smtplib
    from email.message import EmailMessage
    user, pw, to = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"), os.getenv("EMAIL_TO", "")
    rcpt = [a.strip() for a in to.split(",") if a.strip()]
    if not (user and pw and rcpt):
        print("[Mail] GMAIL_USER / GMAIL_APP_PASSWORD / EMAIL_TO not set: no email")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"Get Your Deal <{user}>", ", ".join(rcpt)
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
            s.login(user, pw)
            s.send_message(msg)
        print(f"[Mail] Sent to {len(rcpt)} people")
        return True
    except Exception as e:  # never print the password; the error text doesn't contain it
        print(f"[Mail] Couldn't send: {type(e).__name__}")
        return False


def _issue(title: str, body: str) -> bool:
    import requests
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY", REPO)
    if not token:
        print("[Kit] No GITHUB_TOKEN: no notification")
        return False
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30, json={"title": title, "body": body},
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    print(f"[Kit] Notification issue: {r.status_code} {r.json().get('html_url', '') if r.ok else ''}")
    return r.status_code == 201


def notify(kit: dict) -> bool:
    """Monday: a GitHub issue tagging the owner (GitHub emails it and shows it in its app), and an email
    to the team if the Gmail secrets exist."""
    if not kit.get("combos"):
        return False
    owner = os.getenv("GITHUB_REPOSITORY", REPO).split("/")[0]
    send_email(f"🗓️ This week's content kit is ready ({kit['week']})",
               f"This week's kit is ready to make: {SITE_URL}/dashboard/#content\n\n" + kit_status(kit))
    body = (f"@{owner} this week's content kit is ready: **{len(kit['combos'])} outfit images** and "
            f"**{len(kit['reels'])} reels**. Copy each prompt into Gemini and upload what it makes:\n"
            f"{SITE_URL}/dashboard/#content\n\n"
            f"They go out on their own: 2 outfit pins a day, Instagram carousels Tue/Thu/Sat, reels Mon/Wed/Fri/Sun.\n\n"
            + "\n".join(f"- [ ] {c['n']}. {c['name']} ({c['gender']})" for c in kit["combos"]))
    return _issue(f"🗓️ Weekly content kit ready: week of {kit['week']}", body)


# ---------- uploads -> finished looks ----------
def finish_image(src: Path, out: Path):
    """The uploaded image at 1080x1350 (Instagram's 4:5; fine on Pinterest), no text added."""
    W, H = 1080, 1350
    im = Image.open(src).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=92)


def look_page(c: dict):
    """docs/looks/<id>/: the image and a shop link for every piece."""
    from trends import site
    rows = "".join(f"""
      <li class="piece"><span>{escape(p['what'][:1].upper() + p['what'][1:])}</span>
        <span class="btns">{f'<a class="btn primary" href="{escape(p["myntra"])}" target="_blank" rel="noopener sponsored nofollow">Myntra</a>' if p.get("myntra") else ""}
        <a class="btn" href="{escape(p['amazon'])}" target="_blank" rel="noopener sponsored nofollow">Amazon</a></span></li>""" for p in c["pieces"])
    body = f"""
  <main class="wrap">
    <div class="crumbs"><a href="../../">All ideas</a> &rsaquo; {escape(c['name'])}</div>
    <section class="hero">
      <span class="eyebrow">Outfit idea · {escape(c['gender'])}</span>
      <h1>{escape(c['name'])}</h1>
      <p>Every piece of this look, with a link to find it. The links open the store's search, so you see what's in stock today.</p>
    </section>
    <p><img src="pin.jpg" alt="{escape(c['name'])} outfit" style="width:100%;max-width:540px;border-radius:16px;display:block;margin:0 auto 24px"></p>
    <ul class="pieces">{rows}</ul>
    <p class="disclosure">{site.AMAZON_DISCLOSURE} The image is an AI-made styling idea; the links show similar pieces.</p>
  </main>"""
    folder = site.DOCS / "looks" / c["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(site._page(f"{c['name']} – outfit idea – Get Your Deal",
                                                  f"{c['name']}: {', '.join(p['search'] for p in c['pieces'])}. Shop every piece.",
                                                  body, "../../", f"{SITE_URL}/looks/{c['id']}/pin.jpg",
                                                  f"{SITE_URL}/looks/{c['id']}/"), encoding="utf-8")


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
    """Uploaded look images -> finished looks. Returns how many were added."""
    looks = _load(LOOKS_FILE, [])
    have = {lk["id"] for lk in looks}
    added = 0
    for folder in sorted(INBOX.glob("look-*")) if INBOX.exists() else []:
        c = find(folder.name)
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES)
        if not files:
            continue
        if not c or c["id"] in have:  # last week's, or a second upload of the same look: tidy up
            for p in files:
                p.unlink()
            continue
        out = Path("docs/looks") / c["id"] / "pin.jpg"
        try:
            finish_image(files[0], out)
        except Exception as e:
            print(f"[Kit] {files[0]} couldn't be read: {e}")
            continue
        look_page(c)
        looks.append({"id": c["id"], "name": c["name"], "gender": c["gender"], "board": c["board"],
                      "searches": [p["search"] for p in c["pieces"]], "image": out.as_posix(),
                      "page": f"{SITE_URL}/looks/{c['id']}/", "at": datetime.now(IST).isoformat(timespec="minutes"),
                      "pin_day": _next_pin_day(looks)})
        have.add(c["id"])
        for p in files:
            p.unlink()
        added += 1
        print(f"[Kit] {c['id']}: finished, pin on {looks[-1]['pin_day']}")
    if added:
        _save(LOOKS_FILE, looks)
    return added


def look_pins(today: str) -> list:
    """Queue items for post.py: the looks whose pin day has come. Titles and descriptions use the
    words people search ('baggy jeans outfit men')."""
    out = []
    for lk in _load(LOOKS_FILE, []):
        if lk["pin_day"] > today or not Path(lk["image"]).exists():
            continue
        g = "men" if lk["gender"] == "men" else "women"
        words = ", ".join(f"{s.rsplit(' ', 1)[0]} outfit {g}" for s in lk["searches"][:3])
        out.append({"id": f"{lk['pin_day']}:look:{lk['id']}", "image": lk["image"],
                    "title": f"{lk['name']} | Outfit idea for {g}"[:100],
                    "description": (f"{lk['name']}: the full look and every piece to shop. {words}. "
                                    f"Save it for later. #OutfitIdeas #OutfitInspo #{g.title()}Fashion #IndianFashion "
                                    f"#StreetStyle")[:500],
                    "link": lk["page"], "board": lk["board"]})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv
    load_dotenv(".env")
    if "--ingest" in sys.argv:
        n = ingest()
        print(f"[Kit] {n} new looks")
        if n and os.getenv("PUBLISH", "1") == "1":
            from shared.publish import deploy_site
            deploy_site(f"{n} new outfit looks")
    elif "--guide" in sys.argv:
        text = GUIDE.format(site=SITE_URL, status=kit_status(_load(KIT_FILE, {})))
        send_email("Get Your Deal – how the weekly content kit works", text)
        owner = os.getenv("GITHUB_REPOSITORY", REPO).split("/")[0]
        sys.exit(0 if _issue("📘 How the weekly content kit works", f"@{owner}\n\n```text\n{text}\n```") else 1)
    else:
        kit = build_kit(_load(Path("data/themes.json"), []))
        if "--notify" in sys.argv:
            notify(kit)
