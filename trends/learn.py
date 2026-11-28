"""
learn.py - learns from our own results which kinds of content work, and steers next week's content.

Every post (Pinterest pins from Pinterest Analytics, Instagram reels and carousels from data/analytics/
instagram.json) is described by its features: men's or women's, the occasion (wedding guest, winter,
office...), ethnic or western, the product type (outfit, shoes, bag, watch...), the format (outfit pin,
reel pin, deal pin, reel, carousel) and its main words ("korean", "baggy", "puffer"). Each feature's
results are averaged, pulled towards the overall average when there are few posts (so one lucky post
doesn't swing everything), and turned into a weight: above 1 works better than average, below 1 worse.

Written to data/learnings.json (daily, after the stats). Used by:
  - weekly.pick_looks: looks with winning features are picked first; the men/women split follows results
  - post.py: how many automatic deal pins a day (0-2), by how deal pins do against our own looks
  - the dashboard's "What the data says" card
Reel hooks, places and closing moves learn the same way in trends/creator.py.

  python -m trends.learn      # update data/learnings.json and print what it found
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
OUT = Path("data/learnings.json")
PRIOR = 5          # posts' worth of "average" every feature starts with (shrinks small samples)
MIN_SHOWN = 2      # a feature needs this many posts before it's reported as working or not
STOP = {"for", "men", "women", "outfit", "outfits", "idea", "ideas", "look", "looks", "the", "and", "with", "a", "of",
        "in", "on", "to", "trending", "india", "2026", "latest", "from", "picks", "under", "today", "this", "fit"}
# Pins whose numbers say nothing about the content: reposted ~50 times by the Nov 14-18 save bug
TAINTED = r"Flex Renew Sneakers|Embellished Criss Cross Wedges|Navy Blue Embossed Printed Round Neck"
ETHNIC = r"kurta|kurti|saree|lehenga|anarkali|sherwani|ethnic|wedding|sangeet|haldi|mehendi|reception|festive|diwali"


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def features(text: str, fmt: str) -> dict:
    """The features of one post from its title or name, and its format."""
    from trends.creator import kind_from_text, occasion_of
    t = text.lower().replace("&amp;", "&")
    gender = "men" if re.search(r"\bmen'?s?\b|\bmale\b|\bguy", t) and not re.search(r"\bwomen", t) else (
        "women" if re.search(r"women|girl|ladies|kurti|saree|lehenga|anarkali|heels|handbag|makeup", t) else "")
    words = [w for w in re.findall(r"[a-z]{3,}", t) if w not in STOP][:6]
    f = {"format": fmt, "kind": kind_from_text(t), "occasion": occasion_of(t),
         "style": "ethnic" if re.search(ETHNIC, t) else "western"}
    if gender:
        f["gender"] = gender
    return {**f, "words": words}


def _pin_format(title: str) -> str:
    return "outfit pin" if "| Outfit idea for" in title else "deal pin"


def _ig_text(post: dict, looks: dict, kit: dict) -> str:
    key = post.get("key", "")
    if key.startswith("carousel:"):
        return " ".join(looks.get(i, {}).get("name", "") + " " + looks.get(i, {}).get("gender", "")
                        for i in key[9:].split(","))
    from trends.weekly import find
    lk = find(key) if key.startswith("reel-") else None
    if lk:
        return f"{lk['name']} {lk['gender']}"
    return re.sub(r"^(auto:[\d-]+:|deal:|video-)", "", key).replace("-", " ") + " " + post.get("title", "")


def samples() -> list:
    """[(features, score)] for every post we have numbers for. Scores are put on one scale per platform
    (the platform's average = 1) so Pinterest and Instagram can be combined."""
    out = []
    ana = _load("data/analytics/latest.json", {})
    pins = [p for p in ana.get("pins", []) if p.get("title") and not re.search(TAINTED, p["title"])]
    raw = [(p, p.get("impressions", 0) + 20 * p.get("saves", 0) + 10 * p.get("outbound_clicks", 0)
            + 5 * p.get("pin_clicks", 0)) for p in pins]
    avg = (sum(s for _, s in raw) / len(raw)) if raw else 0
    for p, s in raw:
        if avg:
            out.append((features(p["title"], _pin_format(p["title"])), s / avg, "pinterest"))
    ig = _load("data/analytics/instagram.json", {}).get("posts", [])
    looks = {lk["id"]: lk for lk in _load("data/looks.json", [])}
    kit = {c["id"]: c for c in _load("data/weekly_kit.json", {}).get("combos", [])}
    raw = [(p, (p.get("likes") or 0) + 2 * (p.get("comments") or 0) + 3 * (p.get("saves") or 0)
            + 3 * (p.get("shares") or 0) + (p.get("reach") or p.get("views") or 0) / 50)  # views until reach is shared
           for p in ig if p.get("key")]
    avg = (sum(s for _, s in raw) / len(raw)) if raw else 0
    for p, s in raw:
        if avg:
            fmt = "carousel" if p.get("kind") == "carousel" else "reel"
            out.append((features(_ig_text(p, looks, kit), fmt), s / avg, "instagram"))
    return out


def learn() -> dict:
    data = samples()
    stats = {}
    for f, score, _ in data:
        for dim, val in f.items():
            for v in (val if isinstance(val, list) else [val]):
                tot, n = stats.setdefault(dim, {}).get(v, (0.0, 0))
                stats[dim][v] = (tot + score, n + 1)
    weights = {}
    for dim, vals in stats.items():
        weights[dim] = {}
        for v, (tot, n) in vals.items():
            shrunk = (tot + PRIOR * 1.0) / (n + PRIOR)  # average 1.0 is the prior
            weights[dim][v] = {"weight": round(max(0.5, min(1.8, shrunk)), 2), "posts": n,
                               "avg": round(tot / n, 2)}
    rep = {"updated": datetime.now(IST).isoformat(timespec="minutes"),
           "posts": {"pinterest": sum(1 for *_, s in data if s == "pinterest"),
                     "instagram": sum(1 for *_, s in data if s == "instagram")},
           "weights": weights}
    rep["women_share"] = women_share(weights)
    rep["deal_pins_per_day"] = deal_pins_per_day(weights)
    rep["insights"] = insights(weights, rep)
    return rep


def w(weights: dict, dim: str, val: str) -> float:
    return weights.get(dim, {}).get(val, {}).get("weight", 1.0)


def women_share(weights: dict) -> float:
    """The share of women's looks next week (0.35-0.65), leaning towards whichever does better."""
    wm, ww = w(weights, "gender", "men"), w(weights, "gender", "women")
    return round(max(0.35, min(0.65, ww / (wm + ww))), 2)


def deal_pins_per_day(weights: dict) -> int:
    """Automatic deal pins a day (0-2): more if they beat our outfit pins, none if they clearly lose."""
    d = weights.get("format", {}).get("deal pin", {})
    o = weights.get("format", {}).get("outfit pin", {})
    if d.get("posts", 0) < 3 or o.get("posts", 0) < 3:
        return 1  # not enough to judge yet
    ratio = d["weight"] / o["weight"]
    return 2 if ratio > 1.25 else 0 if ratio < 0.6 else 1


NAMES = {"gender": "{v}'s content", "occasion": "{v} looks", "style": "{v} wear", "kind": "{v}",
         "format": "{v}s", "words": '"{v}"'}


def insights(weights: dict, rep: dict) -> list:
    """Plain-language findings: [{"kind": "works"|"weak", "text"}], strongest first, plus what changes."""
    found = []
    for dim, vals in weights.items():
        for v, s in vals.items():
            if s["posts"] < MIN_SHOWN or dim == "words" and s["posts"] < 3:
                continue
            if s["weight"] >= 1.15 or s["weight"] <= 0.87:
                label = NAMES.get(dim, "{v}").format(v=v)
                good = s["weight"] >= 1.15
                found.append({"kind": "works" if good else "weak", "dim": dim, "value": v, "weight": s["weight"],
                              "text": f"{label[:1].upper() + label[1:]}: {s['avg']:.1f}x the average over "
                                      f"{s['posts']} posts" + ("" if good else " (shown less next week)")})
    found.sort(key=lambda x: -abs(x["weight"] - 1))
    changes = []
    if abs(rep["women_share"] - 0.5) >= 0.05:
        changes.append(f"Next week's looks: {round(14 * rep['women_share'])} women's, "
                       f"{14 - round(14 * rep['women_share'])} men's")
    if rep["deal_pins_per_day"] != 1:
        changes.append(f"Automatic deal pins: {rep['deal_pins_per_day']} a day")
    return found[:12] + [{"kind": "change", "text": c} for c in changes]


def look_bonus(lk: dict, weights: dict) -> float:
    """How much better than average a look's features have done (0 = average); for pick_looks."""
    f = features(f"{lk['name']} {lk['gender']} " + " ".join(q for _, q in lk["pieces"]), "outfit pin")
    b = 3 * (w(weights, "gender", lk["gender"]) - 1) + 3 * (w(weights, "occasion", f["occasion"]) - 1)
    b += 2 * (w(weights, "style", f["style"]) - 1)
    b += sum(1.5 * (w(weights, "words", x) - 1) for x in f["words"])
    return b


def load() -> dict:
    return _load(OUT, {})


def main() -> int:
    rep = learn()
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[Learn] {rep['posts']['pinterest']} Pinterest pins, {rep['posts']['instagram']} Instagram posts")
    for i in rep["insights"]:
        print(f"  {'+' if i['kind'] == 'works' else '-' if i['kind'] == 'weak' else '>'} {i['text']}")
    if not rep["insights"]:
        print("  Not enough posts yet to see a pattern")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
