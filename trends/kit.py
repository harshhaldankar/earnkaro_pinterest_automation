"""
kit.py - the weekly Gemini video kit: docs/kit/ on the website (not linked, not indexed).

For each of this week's trends, two hero products, each with
  - the product photo to give Gemini (long-press to save on the phone)
  - a ready Veo prompt in the style of a premium product ad (no text, the product unchanged)
  - an upload link: the finished video goes to inbox/<slug>-<n>/ in this repo, and
    "3 · Instagram" posts it at 7 PM with its caption (trends/instagram.py)

Heroes are the two best-paying products of different kinds, so the two videos differ.
"""
import html
import json
from pathlib import Path

from trends import site
from trends.reel import nice_cap, short_label

REPO = "harshhaldankar/earnkaro_pinterest_automation"
KIT_FILE = Path("data/kit.json")
OBJECT_TYPES = {"formal_shoes", "jewellery", "handbag", "watch", "sunglasses", "perfume", "makeup", "heels", "sneakers"}
OBJECT_CATEGORIES = ("footwear", "accessories", "bags-luggage", "beauty")


def _rs(v) -> str:
    return "₹{:,}".format(int(round(v)))


def heroes(th: dict, n: int = 2) -> list:
    """[(photo number, product)]: best commission first, one per product category."""
    ranked = sorted(enumerate(th["products"], 1), key=lambda ip: -ip[1].get("commission", 0))
    out, seen = [], set()
    for i, p in ranked:
        if p["category"] not in seen:
            out.append((i, p))
            seen.add(p["category"])
        if len(out) == n:
            break
    for i, p in ranked:  # a theme of one kind (all makeup, say): the next best products
        if len(out) < n and all(i != j for j, _ in out):
            out.append((i, p))
    return out


def _scene(th: dict) -> str:
    words = f"{th['phrase']} {th['type']}".lower()
    if any(w in words for w in ("wedding", "saree", "kurta", "ethnic", "lehenga", "diwali")):
        return "a softly lit Indian wedding venue with marigold garlands and warm fairy lights"
    if "winter" in words:
        return "a misty hill-station street in the morning, with warm café lights in the background"
    if "office" in words or "formal" in words:
        return "a bright, modern Indian office lobby with soft morning light"
    return "a sunlit minimal studio with cream walls, soft shadows and a few dried flowers"


def prompt_for(th: dict, p: dict) -> str:
    item = short_label(p["name"], p["brand"]).lower()
    if th["board"] == "Home Decor Ideas India":
        return (f"Use the attached product photo. Create an 8-second 9:16 vertical premium home-decor ad. "
                f"The {item} from the photo is in a cosy, softly lit Indian living room at Diwali, with glowing "
                f"diyas, warm fairy lights and marigold flowers around it. The camera slowly pushes in, glides "
                f"across the details, then pulls back to show the whole corner. Warm golden light, shallow depth "
                f"of field, magazine look. Keep the {item} exactly as in the photo: same shape, colour and pattern. "
                f"No text, no people. Soft, festive instrumental music.")
    if th["type"] in OBJECT_TYPES or p["category"].startswith(OBJECT_CATEGORIES) or "footwear" in p["category"]:
        return (f"Use the attached product photo. Create an 8-second 9:16 vertical premium product commercial. "
                f"The product in the photo ({item}) floats and slowly rotates in mid-air in a soft pastel studio "
                f"(blush pink, powder blue and lavender gradient), with a soft shadow on the floor below. "
                f"Smooth camera moves: a slow orbit, then macro close-ups of the texture and details, then a pull "
                f"back to the full product. Subtle glowing light streaks sweep across it, and a few soft pastel "
                f"cubes float out of focus in the background. Keep the product exactly as in the photo: same "
                f"shape, colour, logo and details. No text, no people. Light, upbeat instrumental music.")
    who, pron = ("man", "He") if th.get("gender") == "men" else ("woman", "She")
    return (f"Use the attached photo. Create an 8-second 9:16 vertical fashion film. A young Indian {who} wears "
            f"exactly this {item}: same colour, pattern, fabric and details as in the photo. Setting: {_scene(th)}. "
            f"{pron} turns slowly and walks towards the camera, and the fabric moves naturally. The camera does a "
            f"slow push-in, then a close-up of the fabric and details, then pulls back to the full look. Soft "
            f"cinematic light, shallow depth of field, premium magazine look. No text. Soft, elegant instrumental music.")


def caption_for(th: dict, p: dict) -> str:
    from trends.build import hashtags  # build imports kit, so import here
    others = len(th["products"]) - 1
    cap = nice_cap(max(x["price"] for x in th["products"]))
    item = short_label(p["name"], p["brand"])
    return (f"{th['title']} ✨\n\n"
            f"{item}: just {_rs(p['price'])} on {p['store']} 🛍️\n"
            f"Plus {others} more picks under {_rs(cap)} that India is searching for right now.\n\n"
            f"Comment LINK and we'll DM you every link 💌\n"
            f"Or tap the link in our bio 🔗\n"
            f"Save this for your next shopping trip ✨\n\n{hashtags(th)}")


def build_kit(themes: list) -> dict:
    """data/kit.json and docs/kit/index.html for the latest week's themes."""
    latest = themes[0]["week"] if themes else ""
    kit = {}
    for th in [t for t in themes if t["week"] == latest]:
        for n, (i, p) in enumerate(heroes(th), 1):
            key = f"{th['slug']}-{n}"
            kit[key] = {
                "slug": th["slug"], "title": th["title"], "photo": f"ideas/{th['slug']}/p{i}.jpg",
                "product": short_label(p["name"], p["brand"]), "price": p["price"], "store": p["store"],
                "prompt": prompt_for(th, p), "caption": caption_for(th, p),
            }
    KIT_FILE.write_text(json.dumps(kit, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_page(kit, latest)
    from trends.video import build_plan  # the control room's "Today's video" (video.py imports this module)
    build_plan(themes)
    from trends.weekly import build_kit as build_weekly_kit  # the 14 outfit combos of the week
    build_weekly_kit(themes)
    return kit


def _write_page(kit: dict, week: str):
    e = html.escape
    cards = []
    for n, (key, k) in enumerate(kit.items(), 1):
        cards.append(f"""
<section class="card">
  <h2>{n}. {e(k['title'])} <small>{e(k['product'])} · {_rs(k['price'])} on {e(k['store'])}</small></h2>
  <a href="../{k['photo']}" target="_blank"><img src="../{k['photo']}" alt="{e(k['product'])}"></a>
  <p class="step">1 · Save this photo (long-press), open Gemini → Video, attach it and paste the prompt:</p>
  <textarea readonly id="p{n}">{e(k['prompt'])}</textarea>
  <button onclick="copy('p{n}', this)">Copy prompt</button>
  <p class="step">2 · Download the video, then upload it here. It posts to Instagram at 7 PM with this caption:</p>
  <a class="up" href="https://github.com/{REPO}/upload/master/inbox/{key}" target="_blank">Upload video for #{n}</a>
  <details><summary>Caption</summary><textarea readonly id="c{n}">{e(k['caption'])}</textarea>
  <button onclick="copy('c{n}', this)">Copy caption</button></details>
</section>""")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Video Kit</title>
<style>
:root{{--bg:#faf5f0;--ink:#282026;--muted:#6e5c66;--card:#fff;--accent:#c8186e;--line:#eadfd8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1719;--ink:#f3ecef;--muted:#b9a8b0;--card:#272023;--line:#3a3034}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:640px;margin:0 auto;padding:20px 16px 60px}}
h1{{font-family:Georgia,serif;font-weight:500;margin:.2em 0}} .lead{{color:var(--muted)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:18px 0}}
h2{{font-size:1.1rem;margin:0 0 10px}} h2 small{{display:block;color:var(--muted);font-weight:400}}
img{{width:100%;max-height:420px;object-fit:contain;border-radius:12px;background:#f1ebe6}}
.step{{font-weight:600;margin:14px 0 6px}}
textarea{{width:100%;box-sizing:border-box;min-height:150px;border:1px solid var(--line);border-radius:10px;
padding:10px;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--ink)}}
button,.up{{display:inline-block;margin-top:8px;padding:10px 16px;border-radius:999px;border:0;
background:var(--accent);color:#fff;font-weight:600;text-decoration:none;cursor:pointer}}
details{{margin-top:12px}} summary{{cursor:pointer;color:var(--muted)}}
</style></head><body><main>
<h1>This week's video kit</h1>
<p class="lead">Week of {e(week)}. Make one video a day in Gemini. Upload it with the button and it goes
out on Instagram at 7 PM with the caption. Videos uploaded after 7 PM go out the next evening.</p>
{''.join(cards)}
</main>
<script>
function copy(id, b){{const t=document.getElementById(id);t.select();
(navigator.clipboard?navigator.clipboard.writeText(t.value):Promise.reject()).catch(()=>document.execCommand('copy'));
const o=b.textContent;b.textContent='Copied';setTimeout(()=>b.textContent=o,1500)}}
</script></body></html>
"""
    out = Path("docs/kit/index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"[Kit] {len(kit)} videos: {site.SITE_URL}/kit/")
