"""
research.py - this week's themes, from what people in India search on Pinterest.

Pinterest Trends has no India region, so the signal comes from Pinterest India itself
(in.pinterest.com, no login needed):
  - search suggestions for seed words ("kurta" -> "kurta sets for women", ...), most-searched first
  - the trending searches Pinterest shows on its India search page ("Diwali wall decor", ...)

A phrase becomes a theme when it is shoppable (it names something EarnKaro sells, see TYPES)
and EarnKaro's catalogue has enough matching products to show.
"""
import asyncio
import itertools
import re
from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

from trends.catalog import earns_commission

IST = timezone(timedelta(hours=5, minutes=30))
MIN_PRODUCTS = 5

BOARD_WOMEN = "Outfit Ideas for Women"
BOARD_MEN = "Men's Outfit Ideas"
BOARD_ETHNIC = "Indian Ethnic Wear & Wedding Guest Outfits"
BOARD_SHOES = "Shoes & Sneaker Outfits"
BOARD_ACCESSORIES = "Jewellery & Accessories Ideas"
BOARD_BEAUTY = "Makeup & Beauty Picks"
BOARD_HOME = "Home Decor Ideas India"

# Product types EarnKaro's catalogue covers. A phrase matches a type through `words`; products
# match through `match` (in the product name) within `cats`. gender None = taken from the phrase.
TYPES = {
    "kurta":      dict(words=["kurta", "kurti", "anarkali"], match=["kurta", "kurti", "anarkali"],
                       cats=["women-fashion/kurta-kurti"], board=BOARD_ETHNIC, gender="women"),
    "saree":      dict(words=["saree", "sarees", "sari"], match=["saree", "sari"],
                       cats=["women-fashion/sarees"], board=BOARD_ETHNIC, gender="women"),
    "wedding":    dict(words=["wedding guest", "ethnic wear", "ethnic outfit", "festive outfit", "diwali outfit", "traditional outfit"],
                       match=[], cats=["women-fashion/kurta-kurti", "women-fashion/sarees", "accessories/jewellery", "women-footwear/women-heels"],
                       board=BOARD_ETHNIC, gender="women"),
    "dress":      dict(words=["dress", "dresses", "gown"], match=["dress", "gown"],
                       cats=["women-fashion/women-dresses"], board=BOARD_WOMEN, gender="women"),
    "top":        dict(words=["tops", "top for", "tunic"], match=["top", "tunic", "shirt"],
                       cats=["women-fashion/tops-tunics", "women-fashion/shirts"], board=BOARD_WOMEN, gender="women"),
    "outfit":     dict(words=["outfit", "outfits", "look", "looks", "style"], match=[],
                       cats={"women": ["women-fashion/tops-tunics", "women-fashion/women-jeans", "women-fashion/women-dresses",
                                       "women-footwear/casual-shoes", "accessories/handbags"],
                             "men": ["men-fashion/men-tshirt", "men-fashion/men-shirts", "men-fashion/men-jeans",
                                     "men-footwear/men-casual-footwear", "accessories/watches"]},
                       board=None, gender=None),
    "jeans":      dict(words=["jeans", "denim"], match=["jeans", "denim"],
                       cats={"women": ["women-fashion/women-jeans"], "men": ["men-fashion/men-jeans"]}, board=None, gender=None),
    "tshirt":     dict(words=["t shirt", "t-shirt", "tshirt", "polo"], match=["t-shirt", "tshirt", "polo"],
                       cats=["men-fashion/men-tshirt"], board=BOARD_MEN, gender="men"),
    "shirt":      dict(words=["shirt", "shirts"], match=["shirt"],
                       cats={"women": ["women-fashion/shirts"], "men": ["men-fashion/men-shirts"]}, board=None, gender=None),
    "trousers":   dict(words=["trousers", "pants", "chinos", "formal outfit"], match=["trouser", "pant", "chino"],
                       cats=["men-fashion/men-trousers"], board=BOARD_MEN, gender="men"),
    "heels":      dict(words=["heels", "sandals", "flats", "footwear for women"], match=["heel", "sandal", "flat", "wedge", "mule"],
                       cats=["women-footwear/women-heels", "women-footwear/flat-sandals"], board=BOARD_SHOES, gender="women"),
    "sneakers":   dict(words=["sneakers", "shoes", "running shoes"], match=["sneaker", "shoe", "running"],
                       cats={"women": ["women-footwear/casual-shoes", "women-footwear/women-sports-shoes"],
                             "men": ["men-footwear/men-sports-shoes", "men-footwear/men-casual-footwear"]},
                       board=BOARD_SHOES, gender=None),
    "formal_shoes": dict(words=["formal shoes", "loafers", "oxford"], match=["formal", "loafer", "oxford", "derby", "brogue"],
                       cats=["men-footwear/formal-shoes"], board=BOARD_SHOES, gender="men"),
    "jewellery":  dict(words=["jewellery", "jewelry", "earrings", "jhumka", "jhumkas", "necklace", "maang tikka", "mangalsutra", "bangles"],
                       match=["jewellery", "earring", "jhumka", "necklace", "tika", "tikka", "chandbali", "studs", "bracelet", "mangalsutra", "nose pin"],
                       cats=["accessories/jewellery"], board=BOARD_ACCESSORIES, gender="women"),
    "handbag":    dict(words=["handbag", "handbags", "bag", "bags", "purse", "tote"], match=["bag", "tote", "sling", "clutch", "purse"],
                       cats=["accessories/handbags"], board=BOARD_ACCESSORIES, gender="women"),
    "watch":      dict(words=["watch", "watches"], match=["watch"],
                       cats=["accessories/watches"], board=BOARD_ACCESSORIES, gender=None),
    "sunglasses": dict(words=["sunglasses", "shades"], match=["sunglasses"],
                       cats=["accessories/all-sunglasses"], board=BOARD_ACCESSORIES, gender=None),
    "perfume":    dict(words=["perfume", "perfumes", "fragrance", "attar"], match=["perfume", "parfum", "fragrance", "deodorant", "body mist", "attar"],
                       cats=["beauty/fragrance"], board=BOARD_BEAUTY, gender=None),
    "makeup":     dict(words=["makeup", "lipstick", "nail paint", "kajal", "eyeliner", "foundation"],
                       match=["lipstick", "lip ", "kajal", "eyeliner", "mascara", "foundation", "compact", "blush", "highlighter",
                              "primer", "concealer", "nail", "makeup", "eyeshadow", "palette", "lip gloss", "sugar pop"],
                       cats=["beauty/make-up-nails"], board=BOARD_BEAUTY, gender="women"),
    "decor":      dict(words=["decor", "decoration", "room ideas", "wall art", "bedroom", "living room", "bedsheet", "home"],
                       match=["frame", "wall", "clock", "vase", "lamp", "cushion", "bedsheet", "curtain", "showpiece", "runner",
                              "table cover", "rug", "carpet", "planter", "idol", "shelf", "mirror", "candle", "decor", "hanging",
                              "flower", "dohar", "quilt", "pillow", "blanket", "towel set"],
                       cats=["home-kitchen/home-furnishing", "home-kitchen/bed-and-bath"], board=BOARD_HOME, gender="any"),
}
# Checked in this order, so "wedding guest outfit" is "wedding" and not "outfit"
TYPE_ORDER = ["wedding", "kurta", "saree", "formal_shoes", "jewellery", "handbag", "watch", "sunglasses", "perfume",
              "makeup", "decor", "heels", "sneakers", "tshirt", "jeans", "trousers", "dress", "top", "shirt", "outfit"]

SEEDS = [
    "kurta", "kurti", "saree", "wedding guest", "ethnic wear", "dress", "tops for women", "outfit ideas",
    "winter outfits", "jeans outfit", "men outfit", "shirt outfit men", "t shirt outfit men",
    "sneakers", "heels", "jewellery", "earrings", "handbags", "watches", "sunglasses",
    "perfume", "makeup", "lipstick", "home decor", "bedroom decor", "wall decor",
]
# Searches about something other than buying: tailoring, drawing, photos, hair, nails
EXCLUDE = re.compile(r"\b(poses?|drawing|sketch|hairstyles?|hair|nails?|nail art|photography|photo|pics?|dp|quotes?|caption|images?|"
                     r"wallpaper|reference|tattoo|mehndi|cake|kids?|baby|diy|from old|book|logo|png|cartoon|anime|stitching|"
                     r"cutting|pattern|how to|neck designs?|blouse designs?|black women|hijab|drawing|template|tutorial|organizer|"
                     r"display|making|shop design|poster)\b", re.I)
SEASON = {  # month -> words that get a boost
    **{m: ["wedding", "winter", "party", "festive", "ethnic", "saree", "jacket", "sweater", "velvet"] for m in (11, 12, 1, 2)},
    **{m: ["summer", "cotton", "linen", "holi", "beach"] for m in (3, 4, 5, 6)},
    **{m: ["monsoon", "rakhi", "rain", "office"] for m in (7, 8, 9)},
    10: ["diwali", "festive", "navratri", "garba", "ethnic", "party"],
}

TYPEAHEAD_JS = """async (term) => {
  const data = JSON.stringify({options: {term: term, pin_scope: 'pins', autocomplete_request_surface: 0}, context: {}});
  const headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*, q=0.01',
    'X-Pinterest-AppState': 'active', 'X-Pinterest-Source-Url': '/', 'X-Pinterest-PWS-Handler': 'www/index.js',
    'X-APP-VERSION': window.__APP_VERSION__ || ''};
  const r = await fetch('/resource/AdvancedTypeaheadResource/get/?source_url=%2F&data=' + encodeURIComponent(data), {headers});
  try { return (((await r.json()).resource_response || {}).data || {}).items || []; } catch (e) { return []; }
}"""
TRENDING_JS = """async () => {
  const headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/javascript, */*, q=0.01',
    'X-Pinterest-AppState': 'active', 'X-Pinterest-Source-Url': '/', 'X-Pinterest-PWS-Handler': 'www/index.js',
    'X-APP-VERSION': window.__APP_VERSION__ || ''};
  const r = await fetch('/resource/SearchTabResource/get/?source_url=%2F&data=' + encodeURIComponent(JSON.stringify({options: {}, context: {}})), {headers});
  const out = [];
  const walk = (o) => {
    if (Array.isArray(o)) { o.forEach(walk); return; }
    if (o && typeof o === 'object') {
      for (const k of ['title', 'query']) { const v = o[k]; const t = typeof v === 'object' && v ? (v.format || v.text) : v;
        if (typeof t === 'string' && t.length > 2 && t.length < 60) out.push(t); }
      Object.values(o).forEach(walk);
    }
  };
  try { walk(((await r.json()).resource_response || {}).data); } catch (e) {}
  return out;
}"""


async def fetch_signals(seeds=SEEDS) -> tuple[dict, list]:
    """({seed: [suggestion, ...]}, [trending search, ...]) from Pinterest India."""
    suggestions = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await (await browser.new_context(locale="en-IN", timezone_id="Asia/Kolkata")).new_page()
        await page.goto("https://in.pinterest.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)
        for seed in seeds:
            items = await page.evaluate(TYPEAHEAD_JS, seed)
            suggestions[seed] = [(i.get("query") or i.get("display") or "").strip().lower() for i in items
                                 if (i.get("query") or i.get("display"))]
            await page.wait_for_timeout(400)
        trending = list(dict.fromkeys(t.strip() for t in await page.evaluate(TRENDING_JS)
                                      if t.strip().lower() not in ("popular on pinterest", "ideas for you")))
        await browser.close()
    print(f"[Research] {sum(len(v) for v in suggestions.values())} suggestions from {len(seeds)} seeds; "
          f"trending in India: {', '.join(trending[:10])}")
    return suggestions, trending


def _has(phrase: str, word: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", phrase) is not None


def gender_of(phrase: str):
    if re.search(r"\b(women|womens|woman|girls?|ladies|her)\b", phrase):
        return "women"
    if re.search(r"\b(men|mens|man|boys?|guys?|him)\b", phrase):
        return "men"
    return None


def type_of(phrase: str):
    for key in TYPE_ORDER:
        if any(_has(phrase, w) for w in TYPES[key]["words"]):
            return key
    return None


def theme_key(phrase: str):
    """(type, gender) - phrases with the same key are one theme; None if not shoppable."""
    if EXCLUDE.search(phrase):
        return None
    t = type_of(phrase)
    if not t:
        return None
    g = TYPES[t]["gender"] or gender_of(phrase) or ("women" if t not in ("watch", "sunglasses", "perfume", "sneakers") else None)
    if TYPES[t]["gender"] == "women" and gender_of(phrase) == "men":
        return None  # "kurta pajama men" when only women's kurtas are in the catalogue
    if g is None:
        g = "women"
    return t, g


def products_for(key, catalog: list) -> list:
    """Catalogue products matching a theme key, best discounts first, at most 2 per brand."""
    t, g = key
    spec = TYPES[t]
    cats = spec["cats"][g] if isinstance(spec["cats"], dict) else spec["cats"]
    out, per_brand = [], {}
    for p in sorted(catalog, key=lambda p: (p["discount"], p["commission"]), reverse=True):
        name = p["name"].lower() + " "
        if p["category"] not in cats or not p["image"] or p["price"] <= 0 or not earns_commission(p):
            continue
        # Word starts only: "flower" must not match the brand "Soulflower"
        if spec["match"] and not any(re.search(rf"(?<![a-z]){re.escape(m.strip())}", name) for m in spec["match"]):
            continue
        if g in ("women", "men") and spec["gender"] is None:
            other = "men" if g == "women" else "women"
            if gender_of(name) == other:
                continue
        b = p["brand"].lower()
        if per_brand.get(b, 0) >= 2:
            continue
        per_brand[b] = per_brand.get(b, 0) + 1
        out.append(p)
    if len(cats) > 1:
        # A look mixes categories (kurta, jewellery, heels...): take them in turn, not all from one
        by_cat = [[p for p in out if p["category"] == c] for c in cats]
        out = [p for row in itertools.zip_longest(*by_cat) for p in row if p]
    return out


def title_of(phrase: str) -> str:
    # "winter outfits man" -> "winter outfits for men"
    phrase = re.sub(r"(?<!for) (men|man|mens)$", " for men", phrase)
    phrase = re.sub(r"(?<!for) (women|woman|womens)$", " for women", phrase)
    small = {"for", "and", "with", "in", "of", "to", "the", "a", "on"}
    words = [w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(phrase.split())]
    t = " ".join(words)
    for a, b in (("Co Ord", "Co-ord"), ("Co-ord Set", "Co-ord Set"), ("T Shirt", "T-shirt"), ("Tshirt", "T-shirt"),
                 ("Mens", "Men's"), ("Womens", "Women's"), ("Jewelry", "Jewellery"), ("Diy", "DIY")):
        t = re.sub(rf"\b{a}\b", b, t)
    return t


def slug_of(phrase: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", phrase.lower()).strip("-")[:60]


def board_for(key: tuple) -> str:
    t, g = key
    return TYPES[t]["board"] or (BOARD_MEN if g == "men" else BOARD_WOMEN)


def pick_themes(suggestions: dict, trending: list, catalog: list, recent_keys=(), count=6, now=None,
                board_weights=None) -> list:
    """Score phrases, merge those that mean the same theme, keep the ones with products.
    board_weights (from analytics.board_weights): our own Pinterest results; a board that earns more
    reach and clicks per pin scales its themes' scores up and may take 3 of the week's trends."""
    board_weights = board_weights or {}
    now = now or datetime.now(IST)
    season = SEASON.get(now.month, [])
    trending_l = [t.lower() for t in trending]
    phrases = {}
    for seed, items in suggestions.items():
        for rank, s in enumerate(items):
            if not s or s == seed:
                continue
            phrases[s] = phrases.get(s, 0) + (len(items) - rank) / max(len(items), 1)
    for t in trending_l:
        phrases[t] = phrases.get(t, 0) + 1.5
    themes = {}
    for phrase, score in phrases.items():
        key = theme_key(phrase)
        if not key:
            continue
        if re.search(rf"\b{now.year}\b", phrase):
            score += 0.6
        if any(w in phrase for w in season):
            score += 0.8
        if any(phrase in t or t in phrase for t in trending_l):
            score += 1.0
        th = themes.setdefault(key, {"key": key, "score": 0, "phrases": []})
        th["score"] += score
        th["phrases"].append((score, phrase))
    for th in themes.values():
        th["score"] *= board_weights.get(board_for(th["key"]), 1.0)
    picked, per_board = [], {}
    for th in sorted(themes.values(), key=lambda t: t["score"], reverse=True):
        if th["key"] in recent_keys:
            continue
        prods = products_for(th["key"], catalog)
        if len(prods) < MIN_PRODUCTS:
            continue
        t, g = th["key"]
        board = board_for(th["key"])
        if per_board.get(board, 0) >= (3 if board_weights.get(board, 1.0) >= 1.3 else 2):
            continue
        per_board[board] = per_board.get(board, 0) + 1
        ranked = [p for _, p in sorted(th["phrases"], reverse=True)]
        # Title from the best phrase that names the audience when the type is gendered
        best = next((p for p in ranked if gender_of(p) or TYPES[t]["gender"] in ("women", "any")), ranked[0])
        picked.append({
            "key": f"{t}:{g}", "type": t, "gender": g, "phrase": best, "title": title_of(best), "slug": slug_of(title_of(best)),
            "related": [p for p in ranked if p != best][:8], "score": round(th["score"], 2), "board": board,
            "products": prods[:8],
        })
        if len(picked) >= count:
            break
    return picked


async def research(catalog: list, recent_keys=(), count=6, board_weights=None) -> list:
    suggestions, trending = await fetch_signals()
    themes = pick_themes(suggestions, trending, catalog, recent_keys, count, board_weights=board_weights)
    for th in themes:
        print(f"[Research] {th['title']}  (score {th['score']}, {len(th['products'])} products, board: {th['board']})")
    return themes


if __name__ == "__main__":
    import json, sys
    sys.stdout.reconfigure(encoding="utf-8")
    catalog = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else []
    for th in asyncio.run(research(catalog)):
        print(" ", th["title"], "|", ", ".join(th["related"][:4]), "|", [p["name"][:30] for p in th["products"][:3]])
