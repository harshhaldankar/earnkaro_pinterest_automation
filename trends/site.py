"""
site.py - the Get Your Deal website (docs/), built from data/themes.json.

  docs/index.html                 this week's trend ideas, then earlier ones
  docs/ideas/<slug>/index.html    one idea: its products with Buy buttons, and "shop all" links
  docs/privacy.html, terms.html, 404.html, site.css
"""
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DOCS = Path("docs")
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
.chips li { background: var(--pink); color: var(--ink); border-radius: 999px; padding: 4px 12px; font-size: 13px; }
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


def _page(title: str, description: str, body: str, root: str, og_image: str = "", canonical: str = "") -> str:
    og = f'<meta property="og:image" content="{_e(og_image)}">' if og_image else ""
    can = f'<link rel="canonical" href="{_e(canonical)}">' if canonical else ""
    return f"""<!DOCTYPE html>
<html lang="en-IN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
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
    <nav><a href="{root}#this-week">This week</a><a href="{root}#earlier">Earlier ideas</a></nav>
  </div></header>
{body}
  <footer class="foot"><div class="wrap">
    <div><strong>Get Your Deal</strong> &middot; what India is searching on Pinterest each week, with products to shop.</div>
    <div>Prices and stock change quickly. The price at the store's checkout is the one that counts.</div>
    <nav><a href="{root}privacy.html">Privacy</a><a href="{root}terms.html">Terms</a><a href="{root}terms.html#affiliate">Affiliate disclosure</a></nav>
  </div></footer>
</body>
</html>"""


def _idea_card(th: dict, root: str) -> str:
    low = min(p["price"] for p in th["products"])
    return f"""
      <a class="idea" href="{root}ideas/{th['slug']}/">
        <img src="{root}ideas/{th['slug']}/collage.jpg" alt="{_e(th['title'])}" loading="lazy">
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
          <h3 class="name">{_e(p['name'])}</h3>
          <div class="price"><b>{_rs(p['price'])}</b>{mrp}{off}</div>
          <a class="btn primary" href="{_e(p['link'])}" target="_blank" rel="noopener sponsored nofollow">Buy on {_e(p['store'])}</a>
        </div>
      </article>"""


def write_idea_page(th: dict, others: list):
    folder = DOCS / "ideas" / th["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    shop = "".join(f'<a class="btn{" primary" if i == 0 else ""}" href="{_e(url)}" target="_blank" rel="noopener sponsored nofollow">{_e(label)}</a>'
                   for i, (label, url) in enumerate(th.get("shop_links", [])))
    chips = "".join(f"<li>{_e(r)}</li>" for r in th.get("related", [])[:8])
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
      {f'<ul class="chips" aria-label="Related searches">{chips}</ul>' if chips else ''}
      {f'<div class="shop-all">{shop}</div>' if shop else ''}
    </section>
    <section class="products" aria-label="Products">{''.join(_product_card(p, i + 1, th['slug']) for i, p in enumerate(th['products']))}
    </section>
    <p class="note">Sold out? The "See all" links above always show what's in stock right now.</p>
    {f'<h2 class="section-title">More ideas</h2><div class="ideas">{more}</div>' if more else ''}
  </main>"""
    desc = f"{th['title']}: {len(th['products'])} picks from {_rs(low)} on Myntra and AJIO, trending on Pinterest in India this week."
    url = f"{SITE_URL}/ideas/{th['slug']}/"
    (folder / "index.html").write_text(
        _page(f"{th['title']} – Get Your Deal", desc, body, "../../", f"{url}collage.jpg", url), encoding="utf-8")


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
    <h2 class="section-title" id="this-week">This week</h2>
    <div class="ideas">{cards}</div>
    {f'<h2 class="section-title" id="earlier">Earlier ideas</h2><div class="ideas">{old}</div>' if old else ''}
  </main>"""
    (DOCS / "index.html").write_text(
        _page("Get Your Deal – trending style ideas in India", "What India is searching on Pinterest this week: outfit, ethnic wear, beauty and home decor ideas, with products to shop.",
              body, "", canonical=f"{SITE_URL}/"), encoding="utf-8")


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
        return
    latest = themes[0]["week"]
    current = [t for t in themes if t["week"] == latest]
    earlier = [t for t in themes if t["week"] != latest]
    for t in themes:
        write_idea_page(t, [o for o in current + earlier if o["slug"] != t["slug"]])
    write_home(current, earlier)
    print(f"[Site] {len(current)} ideas this week, {len(earlier)} earlier")


if __name__ == "__main__":
    rebuild(json.load(open("data/themes.json", encoding="utf-8")) if Path("data/themes.json").exists() else [])
