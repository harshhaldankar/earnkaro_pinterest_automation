"""
site.py - the Get Your Deal website (docs/), built from data/themes.json.

  docs/index.html                 this week's trend ideas, then earlier ones
  docs/ideas/<slug>/index.html    one idea: its products with Buy buttons, and "shop all" links
  docs/privacy.html, terms.html, 404.html, site.css
"""
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trends.pins import create_cover
from trends.reel import short_label

DOCS = Path("docs")
AMAZON_TAG = os.getenv("AMAZON_AFFILIATE_TAG") or "getyourdeal00-21"
AMAZON_DISCLOSURE = "As an Amazon Associate we earn from qualifying purchases."


def amazon(path_or_query: str, search: bool = True) -> str:
    """An Amazon.in link with our Associates tag: a search ("winter jacket men") or a page ("deals")."""
    from urllib.parse import quote_plus
    if search:
        return f"https://www.amazon.in/s?k={quote_plus(path_or_query)}&tag={AMAZON_TAG}"
    return f"https://www.amazon.in/{path_or_query}?tag={AMAZON_TAG}"


# What people in India buy on Amazon, by month; the Amazon picks page shows the current season's
# lists plus everyday essentials. Any purchase within 24 hours of a click counts, not just the item.
AMAZON_SEASONS = {
    (11, 12, 1, 2): [
        ("Winter wear", ["winter jacket men", "winter jacket women", "sweatshirt women", "thermal wear men",
                         "woollen cap and gloves", "blanket double bed"]),
        ("Wedding season", ["saree for wedding", "kurta set women", "men ethnic kurta", "wedding gift items",
                            "jewellery set for women", "bridal makeup kit"]),
    ],
    (3, 4, 5, 6): [
        ("Summer", ["cotton kurti women", "linen shirt men", "sunscreen spf 50", "water bottle steel",
                    "table fan", "sunglasses men"]),
        ("Wedding season", ["saree for wedding", "kurta set women", "men ethnic kurta", "wedding gift items"]),
    ],
    (7, 8, 9, 10): [
        ("Monsoon", ["umbrella", "raincoat men", "waterproof shoes", "mosquito repellent"]),
        ("Festive season", ["diwali decoration items", "diya set", "ethnic wear women", "gift hamper"]),
    ],
}
AMAZON_EVERYDAY = ("Everyday essentials", ["bluetooth earbuds", "fast charger", "power bank", "phone cover",
                                            "kitchen storage containers", "face wash", "hair oil", "bedsheet double"])
SITE_URL = "https://harshhaldankar.github.io/Getyourdeal"
IST = timezone(timedelta(hours=5, minutes=30))
CONTACT_EMAIL = "Carrercurve@gmail.com"
LEGAL_UPDATED = "6 November 2026"

SITE_CSS = """
:root {
  --bg: #faf7f4; --card: #ffffff; --ink: #22181e; --muted: #6f6168; --faint: #a0949a; --line: #ece4de;
  --soft: #f6efe9; --pink: #f6d6e4; --accent: #c8186e; --accent-hover: #a3125a; --good: #15803d;
  --radius: 12px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --serif: "Playfair Display", Georgia, "Times New Roman", serif;
}
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; font-family: var(--font); font-size: 15px; line-height: 1.55; color: var(--ink); background: var(--bg); }
a { color: inherit; }
img { display: block; max-width: 100%; }
.wrap { max-width: 1160px; margin: 0 auto; padding: 0 16px; }
.top { background: var(--card); border-bottom: 1px solid var(--line); }
.top .wrap { display: flex; align-items: center; gap: 16px; height: 60px; }
.logo { font-weight: 800; font-size: 18px; text-decoration: none; letter-spacing: -0.2px; }
.logo span { color: var(--accent); }
.top nav { margin-left: auto; display: flex; gap: 18px; font-size: 14px; font-weight: 600; color: var(--muted); }
.top nav a { text-decoration: none; }
.hero { padding: 34px 0 18px; }
.eyebrow { font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
.hero h1 { font-family: var(--serif); font-weight: 600; font-size: clamp(28px, 4vw, 40px); line-height: 1.15; margin: 8px 0 8px; text-wrap: balance; }
.hero p { margin: 0; color: var(--muted); max-width: 64ch; }
.section-title { font-size: 18px; margin: 28px 0 12px; }
.ideas { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 18px; }
.idea { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; text-decoration: none; display: flex; flex-direction: column; }
.idea:hover { border-color: #d9cdc5; }
.idea img { aspect-ratio: 2 / 3; width: 100%; object-fit: cover; background: var(--soft); }
.idea .body { padding: 12px 14px 14px; display: grid; gap: 2px; }
.idea .name { font-weight: 700; font-size: 15px; line-height: 1.3; }
.idea .meta { color: var(--muted); font-size: 13px; }
.crumbs { font-size: 13px; color: var(--muted); padding: 16px 0 0; }
.crumbs a { text-decoration: none; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 0; padding: 0; list-style: none; }
.chips li { background: var(--pink); color: var(--ink); border-radius: 999px; font-size: 13px; }
.chips li a { display: block; padding: 6px 12px; text-decoration: none; }
.chips li:hover { background: #f0c4d8; }
.chips-label { margin: 14px 0 0; font-size: 13px; color: var(--muted); }
.amz-band { margin: 6px 0 4px; padding: 16px 18px; border-radius: var(--radius); background: #fff4e5; border: 1px solid #f5d9ad;
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; }
.amz-band p { margin: 0; font-weight: 600; }
.amz-band .btns { display: flex; gap: 10px; flex-wrap: wrap; }
.btn.amz { background: #ff9900; border-color: #ff9900; color: #111; }
.btn.amz:hover { background: #e88a00; }
.amz-page .section-title { margin-top: 30px; }
.looks { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
.look { position: relative; display: flex; flex-direction: column; border-radius: 16px; overflow: hidden; background: var(--card); border: 1px solid var(--line); text-decoration: none; }
.look img { width: 100%; aspect-ratio: 4 / 5; object-fit: cover; display: block; }
.look .lb { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px 12px; }
.look .lb b { font-size: 14px; line-height: 1.3; }
.look .lb small { font-size: 12px; color: var(--muted); }
.reel-badge { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,.65); color: #fff; font-size: 12px; font-weight: 700; padding: 4px 9px; border-radius: 999px; }
.look-media { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; margin: 0 auto 24px; }
.look-media img, .look-media video { width: 100%; max-width: 420px; border-radius: 16px; display: block; background: #000; }
.look-media video { aspect-ratio: 9 / 16; max-width: 320px; }
.more { text-align: right; margin: 8px 0 0; }
@media (max-width: 640px) { .looks { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; } }
.pieces { list-style: none; padding: 0; margin: 0 auto 24px; max-width: 640px; display: grid; gap: 10px; }
.piece { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 14px; background: var(--card); }
.piece .btns { display: flex; gap: 6px; flex: none; }
.piece .btn { padding: 8px 14px; }
.hots { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.hot { display: flex; flex-direction: column; border-radius: 16px; overflow: hidden; background: var(--card); border: 1px solid var(--line); text-decoration: none; }
.hot img { width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; }
.hot .hb { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px 12px; }
.hot b { font-size: 14px; line-height: 1.3; }
.hot small { font-size: 12px; color: var(--muted); }
.hot .tgo { margin: 4px 0 0; }
@media (max-width: 640px) { .hots { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.amz-hero { margin: 18px 0 6px; padding: 26px 22px; border-radius: 18px; color: #1b1206;
  background: radial-gradient(120% 140% at 0% 0%, #ffe3b0 0%, #ffd08a 35%, #ffb84d 100%); }
.amz-hero .eyebrow { color: #7a3d00; }
.amz-hero h1 { font-family: var(--serif); font-size: clamp(26px, 4vw, 38px); line-height: 1.15; margin: 8px 0 8px; }
.amz-hero p { margin: 0; max-width: 60ch; color: #4a2f10; }
.deals { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 18px; }
.deal { display: flex; gap: 12px; align-items: center; padding: 12px 14px; border-radius: 14px; background: rgba(255,255,255,.75);
  text-decoration: none; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.deal:hover { background: #fff; }
.deal.hot { background: #232f3e; color: #fff; }
.deal.hot small { color: #ffd08a; }
.deal .di { font-size: 24px; }
.deal b { display: block; font-size: 15px; }
.deal small { display: block; font-size: 12px; color: #6b4a22; }
.trends { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.trend { background: var(--card); border: 1px solid var(--line); border-radius: 16px; overflow: hidden; }
.trend-main { display: flex; gap: 12px; align-items: center; padding: 14px 16px; text-decoration: none; }
.trend-main:hover { background: #fff8ee; }
.trend-main b { display: block; font-size: 15px; }
.trend-main small { display: block; font-size: 12px; color: var(--muted); }
.trend .ti { font-size: 26px; width: 44px; height: 44px; border-radius: 12px; background: #fff1dc; display: grid; place-items: center; flex: none; }
.tgo { margin-left: auto; font-size: 13px; font-weight: 700; color: #c45500; white-space: nowrap; }
.minis { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 14px; }
.minis a { font-size: 12px; padding: 5px 10px; border-radius: 999px; background: var(--soft); text-decoration: none; color: var(--ink); }
.minis a:hover { background: #ffe7c2; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.tile { display: flex; flex-direction: column; gap: 8px; padding: 14px; border-radius: 16px; background: var(--card); border: 1px solid var(--line);
  text-decoration: none; min-height: 132px; transition: transform .12s, box-shadow .12s; }
.tile:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.08); border-color: #f3c98a; }
.tile .ti { font-size: 28px; width: 48px; height: 48px; border-radius: 14px; background: #fff1dc; display: grid; place-items: center; }
.tile .tn { font-weight: 700; font-size: 14px; line-height: 1.3; }
.tile .tn small { display: block; font-weight: 500; color: var(--muted); font-size: 12px; }
.tile .tgo { margin: auto 0 0; }
@media (max-width: 640px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } .amz-hero { padding: 22px 16px; } }
.amz-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.amz-card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; }
.amz-card h3 { margin: 0 0 4px; font-size: 16px; }
.amz-card .chips { margin-top: 8px; }
.disclosure { color: var(--muted); font-size: 13px; margin: 18px 0 0; }
.shop-all { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0 8px; }
.btn { display: inline-flex; align-items: center; justify-content: center; height: 44px; padding: 0 18px; border-radius: 999px; font-weight: 700; font-size: 14px; text-decoration: none; border: 1px solid var(--line); background: var(--card); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn.primary:hover { background: var(--accent-hover); }
.products { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; padding: 12px 0 8px; }
.product { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; display: flex; flex-direction: column; scroll-margin-top: 16px; }
.product:target { border-color: var(--accent); box-shadow: 0 0 0 3px var(--pink); }
.product .pic { aspect-ratio: 4 / 5; background: var(--soft); }
.product .pic img { width: 100%; height: 100%; object-fit: cover; }
.product .body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 3px; flex: 1; }
.product .brand { font-size: 12px; color: var(--muted); font-weight: 700; }
.product .name { font-size: 14px; line-height: 1.35; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.7em; }
.price { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; margin-top: 2px; }
.price b { font-size: 16px; }
.price s { color: var(--faint); font-size: 13px; }
.price .off { color: var(--good); font-weight: 700; font-size: 13px; }
.product .btn { margin-top: auto; height: 40px; }
.product .btn.primary { margin-top: 10px; }
.note { color: var(--muted); font-size: 13px; margin: 14px 0 0; }
.foot { border-top: 1px solid var(--line); background: var(--card); margin-top: 40px; }
.foot .wrap { padding: 24px 16px 32px; display: grid; gap: 8px; font-size: 13px; color: var(--muted); }
.foot strong { color: var(--ink); }
.foot nav { display: flex; gap: 16px; flex-wrap: wrap; }
.legal { max-width: 720px; padding: 24px 0 40px; font-size: 15px; line-height: 1.65; }
.legal h1 { font-size: 26px; margin: 0 0 4px; }
.legal .updated { color: var(--muted); font-size: 13px; margin: 0 0 20px; }
.legal h2 { font-size: 17px; margin: 26px 0 6px; }
.legal p, .legal ul { margin: 0 0 10px; }
.empty { color: var(--muted); padding: 40px 0; }
@media (max-width: 640px) {
  .ideas, .products { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .product .body, .idea .body { padding: 8px 10px 10px; }
  .top nav { display: none; }
}
"""

FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&display=swap">'


def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _rs(v) -> str:
    return f"₹{v:,.0f}"


PINTEREST_VERIFY = "2281a75d5fabac698e511ccdb5bd4252"  # Pinterest "claim your website" tag


def _page(title: str, description: str, body: str, root: str, og_image: str = "", canonical: str = "") -> str:
    og = f'<meta property="og:image" content="{_e(og_image)}">' if og_image else ""
    can = f'<link rel="canonical" href="{_e(canonical)}">' if canonical else ""
    return f"""<!DOCTYPE html>
<html lang="en-IN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="p:domain_verify" content="{PINTEREST_VERIFY}"/>
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description)}">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(description)}">
  {og}{can}
  {FONT_LINK}
  <link rel="stylesheet" href="{root}site.css">
</head>
<body>
  <header class="top"><div class="wrap">
    <a class="logo" href="{root}">Get Your Deal<span>.</span></a>
    <nav><a href="{root}#this-week">This week</a><a href="{root}looks/">Looks</a><a href="{root}amazon/">Amazon picks</a><a href="{root}#earlier">Earlier ideas</a></nav>
  </div></header>
{body}
  <footer class="foot"><div class="wrap">
    <div><strong>Get Your Deal</strong> &middot; what India is searching on Pinterest each week, with products to shop.</div>
    <div>Prices and stock change quickly. The price at the store's checkout is the one that counts.</div>
    <div>Some links are affiliate links. {AMAZON_DISCLOSURE}</div>
    <nav><a href="{root}privacy.html">Privacy</a><a href="{root}terms.html">Terms</a><a href="{root}terms.html#affiliate">Affiliate disclosure</a></nav>
  </div></footer>
</body>
</html>"""


def _idea_card(th: dict, root: str) -> str:
    low = min(p["price"] for p in th["products"])
    return f"""
      <a class="idea" href="{root}ideas/{th['slug']}/">
        <img src="{root}ideas/{th['slug']}/cover.jpg" alt="{_e(th['title'])}" loading="lazy">
        <div class="body"><span class="name">{_e(th['title'])}</span>
          <span class="meta">{len(th['products'])} picks from {_rs(low)}</span></div>
      </a>"""


def _product_card(p: dict, i: int, slug: str) -> str:
    off = f'<span class="off">{p["discount"]}% off</span>' if p["discount"] else ""
    mrp = f"<s>{_rs(p['mrp'])}</s>" if p["mrp"] > p["price"] else ""
    return f"""
      <article class="product" id="p{i}">
        <div class="pic"><img src="p{i}.jpg" alt="{_e(p['name'])}" loading="lazy"></div>
        <div class="body">
          <span class="brand">{_e(p['brand'] or p['store'])}</span>
          <h3 class="name" title="{_e(p['name'])}">{_e(short_label(p['name'], p['brand']))}</h3>
          <div class="price"><b>{_rs(p['price'])}</b>{mrp}{off}</div>
          <a class="btn primary" href="{_e(p['link'])}" target="_blank" rel="noopener sponsored nofollow">{"See in-stock styles on" if p.get("search") else "Buy on"} {_e(p['store'])}</a>
        </div>
      </article>"""


def write_idea_page(th: dict, others: list):
    folder = DOCS / "ideas" / th["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    shop = "".join(f'<a class="btn{" primary" if i == 0 else ""}" href="{_e(url)}" target="_blank" rel="noopener sponsored nofollow">{_e(label)}</a>'
                   for i, (label, url) in enumerate(th.get("shop_links", [])))
    chips = "".join(f'<li><a href="{_e(amazon(r))}" target="_blank" rel="noopener sponsored nofollow">{_e(r)}</a></li>'
                    for r in th.get("related", [])[:8])
    updated = datetime.fromisoformat(th["built_at"]).astimezone(IST).strftime("%d %b %Y")
    low = min(p["price"] for p in th["products"])
    more = "".join(_idea_card(o, "../../") for o in others[:4])
    body = f"""
  <main class="wrap">
    <div class="crumbs"><a href="../../">All ideas</a> &rsaquo; {_e(th['title'])}</div>
    <section class="hero">
      <span class="eyebrow">Trending on Pinterest in India</span>
      <h1>{_e(th['title'])}</h1>
      <p>{len(th['products'])} picks from {_rs(low)}, chosen from Myntra and AJIO for what people in India are searching this week. Prices checked {updated}.</p>
      {f'<p class="chips-label">Also search on Amazon:</p><ul class="chips" aria-label="Related searches on Amazon">{chips}</ul>' if chips else ''}
      {f'<div class="shop-all">{shop}</div>' if shop else ''}
    </section>
    <section class="products" aria-label="Products">{''.join(_product_card(p, i + 1, th['slug']) for i, p in enumerate(th['products']))}
    </section>
    <p class="note">Each button opens {"the store's search for that style, with similar ones that are in stock right now" if all(p.get("search") for p in th["products"]) else "the store"}. Prices shown are from when we picked them; the store's price is the one that counts.</p>
    {f'<h2 class="section-title">More ideas</h2><div class="ideas">{more}</div>' if more else ''}
  </main>"""
    desc = f"{th['title']}: {len(th['products'])} picks from {_rs(low)} on Myntra and AJIO, trending on Pinterest in India this week."
    url = f"{SITE_URL}/ideas/{th['slug']}/"
    (folder / "index.html").write_text(
        _page(f"{th['title']} – Get Your Deal", desc, body, "../../", f"{url}collage.jpg", url), encoding="utf-8")


def _hot(root: str, store: str = "") -> str:
    """'Hot right now': deals made from the control room's Create panel in the last 14 days."""
    try:
        made = json.loads(Path("data/created.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    cutoff = (datetime.now(IST) - timedelta(days=14)).isoformat()
    cards = "".join(f"""
      <a class="hot" href="{_e(c['link'])}" target="_blank" rel="noopener sponsored nofollow">
        <img src="{root}deals/{_e(c['slug'])}/card.jpg" alt="{_e(c['title'])}" loading="lazy">
        <span class="hb"><b>{_e(c['title'])}</b><small>{_e(c['line'])}</small><span class="tgo">Shop on {_e(c['store'])} →</span></span>
      </a>""" for c in made if c.get("at", "") >= cutoff and (not store or c.get("store") == store)
                      and (DOCS / "deals" / c.get("slug", "-") / "card.jpg").exists())
    return f'<h2 class="section-title">🔥 Hot right now</h2><div class="hots">{cards}</div>' if cards else ""


def _looks() -> list:
    """Made looks (data/looks.json, newest first) whose image is on the site."""
    try:
        looks = json.loads(Path("data/looks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [lk for lk in reversed(looks) if (DOCS / "looks" / lk["id"] / "pin.jpg").exists()]


def _reel_of(look_id: str) -> str:
    """The look's posted reel video (docs/looks/<id>/ai-*.mp4), newest, or ''."""
    vids = sorted((DOCS / "looks" / look_id).glob("ai-*.mp4"))
    return vids[-1].name if vids else ""


def _look_card(lk: dict, root: str) -> str:
    reel = '<span class="reel-badge">▶ Reel</span>' if _reel_of(lk["id"]) else ""
    return f"""
      <a class="look" href="{root}looks/{_e(lk['id'])}/">
        <img src="{root}looks/{_e(lk['id'])}/pin.jpg" alt="{_e(lk['name'])} outfit idea" loading="lazy">{reel}
        <span class="lb"><b>{_e(lk['name'])}</b><small>Outfit idea · {_e(lk['gender'])}</small></span>
      </a>"""


def write_looks():
    """docs/looks/index.html (every look, newest first) and each look's page (with its reel, if any)."""
    looks = _looks()
    for lk in looks:
        if lk.get("pieces"):
            _look_page(lk)
    cards = "".join(_look_card(lk, "../") for lk in looks) or '<p class="empty">The first looks are on their way.</p>'
    body = f"""
  <main class="wrap">
    <section class="hero">
      <span class="eyebrow">Outfit ideas · new every week</span>
      <h1>Trending looks</h1>
      <p>What's trending in India right now, as complete outfits. Tap a look to shop every piece on Myntra or Amazon.</p>
    </section>
    <div class="looks">{cards}</div>
  </main>"""
    (DOCS / "looks").mkdir(parents=True, exist_ok=True)
    (DOCS / "looks" / "index.html").write_text(
        _page("Trending looks – Get Your Deal", "Trending outfit ideas in India, every piece linked to shop.",
              body, "../", canonical=f"{SITE_URL}/looks/"), encoding="utf-8")


def _look_page(lk: dict):
    """docs/looks/<id>/: the image (and the reel), and a shop link for every piece."""
    reel = _reel_of(lk["id"])
    rows = "".join(f"""
      <li class="piece"><span>{_e(p['what'][:1].upper() + p['what'][1:])}</span>
        <span class="btns">{f'<a class="btn primary" href="{_e(p["myntra"])}" target="_blank" rel="noopener sponsored nofollow">Myntra</a>' if p.get("myntra") else ""}
        <a class="btn" href="{_e(p['amazon'])}" target="_blank" rel="noopener sponsored nofollow">Amazon</a></span></li>""" for p in lk["pieces"])
    media = (f'<div class="look-media"><img src="pin.jpg" alt="{_e(lk["name"])} outfit">'
             + (f'<video src="{_e(reel)}" controls playsinline muted loop preload="metadata" poster="pin.jpg"></video>' if reel else "")
             + "</div>")
    body = f"""
  <main class="wrap">
    <div class="crumbs"><a href="../">All looks</a> &rsaquo; {_e(lk['name'])}</div>
    <section class="hero">
      <span class="eyebrow">Outfit idea · {_e(lk['gender'])}</span>
      <h1>{_e(lk['name'])}</h1>
      <p>Every piece of this look, with a link to find it. The links open the store's search, so you see what's in stock today.</p>
    </section>
    {media}
    <ul class="pieces">{rows}</ul>
    <p class="disclosure">{AMAZON_DISCLOSURE} The image is an AI-made styling idea; the links show similar pieces.</p>
  </main>"""
    folder = DOCS / "looks" / lk["id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(
        _page(f"{lk['name']} – outfit idea – Get Your Deal", f"{lk['name']}: {', '.join(p['search'] for p in lk['pieces'])}. Shop every piece.",
              body, "../../", f"{SITE_URL}/looks/{lk['id']}/pin.jpg", f"{SITE_URL}/looks/{lk['id']}/"), encoding="utf-8")


def write_home(current: list, earlier: list):
    week = datetime.now(IST).strftime("%d %b %Y")
    cards = "".join(_idea_card(t, "") for t in current) or '<p class="empty">This week\'s ideas are on their way.</p>'
    old = "".join(_idea_card(t, "") for t in earlier[:24])
    body = f"""
  <main class="wrap">
    <section class="hero">
      <span class="eyebrow">Week of {week}</span>
      <h1>What India is searching on Pinterest this week</h1>
      <p>Each week we look at what people in India search for on Pinterest, then pick products to match from Myntra and AJIO, with links to shop every look.</p>
    </section>
    <div class="amz-band">
      <p>Shopping on Amazon today? Start from our picks.</p>
      <div class="btns"><a class="btn amz" href="amazon/">Amazon picks</a>
        <a class="btn" href="{_e(amazon("deals", search=False))}" target="_blank" rel="noopener sponsored nofollow">Today's deals on Amazon</a></div>
    </div>
    {_hot("")}
    {(lambda ls: f'<h2 class="section-title" id="looks">✨ Trending looks</h2><div class="looks">{"".join(_look_card(lk, "") for lk in ls[:8])}</div><p class="more"><a href="looks/">All looks →</a></p>' if ls else "")(_looks())}
    <h2 class="section-title" id="this-week">This week</h2>
    <div class="ideas">{cards}</div>
    {f'<h2 class="section-title" id="earlier">Earlier ideas</h2><div class="ideas">{old}</div>' if old else ''}
  </main>"""
    (DOCS / "index.html").write_text(
        _page("Get Your Deal – trending style ideas in India", "What India is searching on Pinterest this week: outfit, ethnic wear, beauty and home decor ideas, with products to shop.",
              body, "", canonical=f"{SITE_URL}/"), encoding="utf-8")


def _icon(q: str) -> str:
    """A small emoji for an Amazon search tile (by keyword; a shopping bag otherwise)."""
    for words, ic in ((("jacket", "sweatshirt", "sweater", "thermal", "hoodie"), "🧥"), (("cap", "glove", "woollen"), "🧤"),
                      (("blanket", "bedsheet", "quilt"), "🛏️"), (("saree", "lehenga"), "🥻"), (("kurta", "kurti", "ethnic"), "👘"),
                      (("gift", "hamper"), "🎁"), (("jewellery", "jewelry", "earring", "necklace"), "💍"),
                      (("makeup", "lipstick", "bridal"), "💄"), (("earbud", "headphone"), "🎧"), (("charger", "power bank", "cable"), "🔌"),
                      (("phone", "mobile"), "📱"), (("kitchen", "container", "bottle"), "🍳"), (("face", "skin", "sunscreen", "serum"), "🧴"),
                      (("hair",), "💆"), (("shoe", "sneaker", "heel", "sandal"), "👟"), (("bag", "handbag"), "👜"),
                      (("watch",), "⌚"), (("shirt", "t shirt", "t-shirt", "top", "outfit"), "👕"), (("umbrella", "rain"), "☔"),
                      (("diya", "diwali", "decor", "decoration"), "🪔"), (("fan",), "🌀"), (("sunglass",), "🕶️"), (("perfume",), "🌸")):
        if any(w in q.lower() for w in words):
            return ic
    return "🛍️"


def _label(q: str) -> tuple:
    """'winter jacket men' -> ('Winter jacket', 'Men'): the audience word goes on a second line."""
    words = q.split()
    who = next((w for w in words if w.lower() in ("men", "women", "kids", "girls", "boys")), "")
    rest = " ".join(w for w in words if w != who)
    if who and rest.endswith(" for"):
        rest = rest[:-4]
    return rest[:1].upper() + rest[1:], who.title()


def write_amazon(current: list):
    """docs/amazon/: this week's trends and the season's most-bought things, as Amazon links with our tag."""
    def tile(q):
        name, who = _label(q)
        return (f'<a class="tile" href="{_e(amazon(q))}" target="_blank" rel="noopener sponsored nofollow">'
                f'<span class="ti">{_icon(q)}</span><span class="tn">{_e(name)}{f"<small>{_e(who)}</small>" if who else ""}</span>'
                f'<span class="tgo">Amazon →</span></a>')

    trend_cards = "".join(f"""
      <div class="trend">
        <a class="trend-main" href="{_e(amazon(t['phrase']))}" target="_blank" rel="noopener sponsored nofollow">
          <span class="ti">{_icon(t['phrase'])}</span>
          <span><b>{_e(t['title'])}</b><small>Trending on Pinterest India this week</small></span>
          <span class="tgo">Shop →</span></a>
        <div class="minis">{''.join(f'<a href="{_e(amazon(r))}" target="_blank" rel="noopener sponsored nofollow">{_e(r)}</a>' for r in t.get('related', [])[:4])}</div>
      </div>""" for t in current)
    month = datetime.now(IST).month
    season = next((v for k, v in AMAZON_SEASONS.items() if month in k), [])
    sections = "".join(f"""
    <h2 class="section-title">{_e(name)}</h2>
    <div class="tiles">{''.join(tile(q) for q in qs)}</div>""" for name, qs in season + [AMAZON_EVERYDAY])
    deal = lambda path, ic, title, sub, cls="": (
        f'<a class="deal {cls}" href="{_e(amazon(path, search=False))}" target="_blank" rel="noopener sponsored nofollow">'
        f'<span class="di">{ic}</span><span><b>{title}</b><small>{sub}</small></span></a>')
    body = f"""
  <main class="wrap amz-page">
    <section class="amz-hero">
      <span class="eyebrow">Amazon picks · updated every Monday</span>
      <h1>This week's trends, ready on Amazon</h1>
      <p>What India is searching for right now, plus what people buy most this season. Tap anything to open Amazon.in with the search ready.</p>
      <div class="deals">
        {deal("deals", "⚡", "Today's deals", "Lightning deals and price drops", "hot")}
        {deal("gp/bestsellers", "🏆", "Best sellers", "What India buys most today")}
        {deal("gp/new-releases", "✨", "New arrivals", "Just launched on Amazon")}
      </div>
    </section>
    {_hot("../", "Amazon")}
    {f'<h2 class="section-title">Trending on Pinterest India</h2><div class="trends">{trend_cards}</div>' if trend_cards else ''}
    {sections}
    <p class="disclosure">{AMAZON_DISCLOSURE} Prices and availability are set by Amazon.</p>
  </main>"""
    (DOCS / "amazon").mkdir(parents=True, exist_ok=True)
    (DOCS / "amazon" / "index.html").write_text(
        _page("Amazon picks – Get Your Deal", "This week's trending searches in India and the season's most-bought things, on Amazon.in.",
              body, "../", canonical=f"{SITE_URL}/amazon/"), encoding="utf-8")


PRIVACY_BODY = f"""
      <h1>Privacy</h1>
      <p class="updated">Last updated {LEGAL_UPDATED}</p>
      <p>Get Your Deal shows style ideas trending in India with products to shop. You can browse it without an account, and we don't ask you for any personal information.</p>
      <h2>What we collect</h2>
      <p>Nothing directly. The site has no sign-up, no forms, no analytics and no advertising trackers, and it doesn't set cookies of its own.</p>
      <h2>Hosting</h2>
      <p>The site is hosted on GitHub Pages. Like any web host, GitHub may log technical details such as your IP address to keep the service secure. See the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub Privacy Statement</a>.</p>
      <h2>When you go to a store</h2>
      <p>Buy and "See all" buttons take you to the store (Myntra, AJIO or Amazon), sometimes through a tracking link from an affiliate network. From then on, the store's own privacy policy and cookies apply. We never see what you buy, your payment details or your address.</p>
      <h2>Children</h2>
      <p>The site isn't meant for children under 13, and we don't knowingly collect anyone's personal information.</p>
      <h2>Contact</h2>
      <p>Questions about this page: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. If this policy changes, the date at the top changes too.</p>"""

TERMS_BODY = f"""
      <h1>Terms</h1>
      <p class="updated">Last updated {LEGAL_UPDATED}</p>
      <p>By using Get Your Deal you agree to these terms.</p>
      <h2>What we do</h2>
      <p>We look at what people in India search for on Pinterest and list matching products from online stores, here, on Pinterest and on Instagram. We don't sell anything ourselves.</p>
      <h2>Your order is with the store</h2>
      <p>Your order, payment, delivery, returns and refunds are handled by the store you buy from, under its own terms. Please contact the store about any order.</p>
      <h2>Prices and stock</h2>
      <p>Prices and stock change quickly. The price shown at the store's checkout is the one that counts.</p>
      <h2 id="affiliate">Affiliate disclosure</h2>
      <p>Some links on this site are affiliate links. If you buy through one, the store or affiliate network may pay us a commission. You pay the same price either way. As an Amazon Associate we earn from qualifying purchases. We also earn through EarnKaro on purchases at stores such as Myntra and AJIO.</p>
      <h2>Product names and images</h2>
      <p>Product names, photos and brand names belong to their brands and stores. We show them only to point you to the product.</p>
      <h2>No warranty</h2>
      <p>The site is provided as is. We aren't responsible for products, prices or stores, or for any loss from using the site, as far as the law allows.</p>
      <h2>Law</h2>
      <p>These terms are governed by the laws of India.</p>
      <h2>Contact</h2>
      <p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>"""


def write_static():
    DOCS.mkdir(exist_ok=True)
    (DOCS / "site.css").write_text(SITE_CSS, encoding="utf-8")
    # The control-room dashboard: a static page that reads the pipeline's data live from GitHub
    (DOCS / "dashboard").mkdir(exist_ok=True)
    (DOCS / "dashboard" / "index.html").write_text(
        (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8"), encoding="utf-8")
    for name, title, body in (("privacy", "Privacy", PRIVACY_BODY), ("terms", "Terms", TERMS_BODY)):
        (DOCS / f"{name}.html").write_text(
            _page(f"{title} – Get Your Deal", f"{title} for Get Your Deal.", f'  <main class="wrap legal">{body}\n  </main>', ""),
            encoding="utf-8")
    nf = """
  <main class="wrap"><section class="hero">
    <h1>This page has moved</h1>
    <p>We now post weekly style ideas trending in India. <a href="/Getyourdeal/">See this week's ideas</a>.</p>
  </section></main>"""
    (DOCS / "404.html").write_text(_page("Page not found – Get Your Deal", "This page has moved.", nf, "/Getyourdeal/"), encoding="utf-8")


def rebuild(themes: list):
    """themes: every built theme, newest first; the ones from the latest week are 'this week'."""
    write_static()
    if not themes:
        write_home([], [])
        write_amazon([])
        return
    latest = themes[0]["week"]
    current = [t for t in themes if t["week"] == latest]
    earlier = [t for t in themes if t["week"] != latest]
    for t in themes:
        folder = DOCS / "ideas" / t["slug"]
        if not (folder / "cover.jpg").exists():
            create_cover([str(folder / f"p{i}.jpg") for i in range(1, 5)], str(folder / "cover.jpg"))
        write_idea_page(t, [o for o in current + earlier if o["slug"] != t["slug"]])
    write_looks()
    write_home(current, earlier)
    write_amazon(current)
    print(f"[Site] {len(current)} ideas this week, {len(earlier)} earlier")


if __name__ == "__main__":
    rebuild(json.load(open("data/themes.json", encoding="utf-8")) if Path("data/themes.json").exists() else [])
