"""
creator.py - the Gemini video prompt for every reel: the same two creators (one woman, one man), each in
their own room, filmed selfie-style on a phone and talking to the viewer. Only what they show changes:
an outfit, shoes, a bag, a watch or jewellery, a beauty product, or something for the home.

  video_prompt(gender, kind, item, line, photo=False) -> str
  kind_from_text("korean pants")                     -> "clothing"
  product_line(item, seed)                           -> what the creator says about one product
"""
import json
import math
import random
import re
from pathlib import Path

# The woman is described from the reel the owner picked (22 Nov 2026); the man matches her style.
CREATORS = {
    "women": ("the same young Indian woman in every video, about 23: medium-brown wheatish skin with natural "
              "texture and a few small acne marks, a round face, dark brown eyes, thick natural eyebrows, a wide "
              "warm smile, long dark-brown hair pulled back in a low ponytail with a few loose strands, no makeup",
              "her bedroom in a Mumbai apartment: white walls, a dark-brown wooden wardrobe with suitcases on top, "
              "a window with sheer white floral curtains, a potted areca palm and a money plant by the window, a bed "
              "with a white floral bedsheet, beige floor tiles, a ceiling fan and a hanging bulb"),
    "men": ("the same young Indian man in every video, about 24: medium-brown skin with natural texture, short black "
            "hair with a soft fade, light stubble, dark brown eyes, an easy friendly grin, slim build",
            "his bedroom in a Mumbai apartment: white walls, a dark-brown wooden wardrobe, a window with plain grey "
            "curtains, a potted snake plant, a bed with a navy-blue bedsheet, a small study table with a laptop, "
            "beige floor tiles, a ceiling fan"),
}

# What the creator does while talking (0-6 s) and in the silent end (6-8 s), by kind of product.
# {s} = she/he, {h} = her/his, {item} = the product.
ACTIONS = {
    "clothing": ("talks straight to the camera like a friend on a video call, tilting the phone down to show the "
                 "clothes as {s} names them",
                 "{s} steps back, does a quick casual turn and smiles at the camera"),
    "footwear": ("sits on the edge of the bed, holds one of the {item} up close to the camera and turns it to show "
                 "the side and sole, then points the phone down at {h} feet wearing them",
                 "{s} stands up, takes two steps so the shoes are seen walking, and smiles at the camera"),
    "bag": ("holds the {item} up close to the camera, turns it to show the front and the details, then opens it to "
            "show the inside",
            "{s} slings it on {h} shoulder, checks it in the wardrobe mirror and smiles at the camera"),
    "accessory": ("is wearing the {item} and brings it close to the camera so it catches the window light, turning "
                  "it slowly",
                  "{s} pulls the phone back so the whole look is seen and smiles at the camera"),
    "beauty": ("holds the {item} up close to the camera to show the label, then applies a little on the back of "
               "{h} hand or face",
               "{s} shows the result close to the camera and smiles"),
    "home": ("holds the {item} up close to the camera, turns it to show the details, then places it on the study "
             "table or shelf by the window",
             "{s} steps back so the {item} is seen in the room and gives a happy thumbs-up"),
    "gadget": ("holds the {item} up close to the camera, shows the details, then uses it for a moment the way it is "
               "meant to be used",
               "{s} looks back at the camera, nods and smiles"),
}

_KINDS = [
    ("footwear", r"shoe|sneaker|heel|sandal|slipper|flip.?flop|loafer|boot|wedge|flat|mule|kolhapuri|jutti|mojari"),
    ("bag", r"\bbag|tote|handbag|backpack|wallet|clutch|purse|sling"),
    ("accessory", r"watch|earring|necklace|jewel|ring\b|bracelet|bangle|chain|sunglass|anklet|pendant|cap\b|hat\b|belt"),
    ("beauty", r"lipstick|serum|cream|makeup|perfume|sunscreen|foundation|kajal|mascara|blush|skincare|face ?wash|"
               r"moisturi[sz]er|lip|nail|shampoo|hair oil|beauty"),
    ("gadget", r"earbud|headphone|speaker|charger|power ?bank|smart ?watch|phone|gadget|trimmer|dryer|straightener|"
               r"mixer|kettle|bottle|organi[sz]er|lamp\b"),
    ("home", r"decor|cushion|curtain|bedsheet|rug|vase|frame|candle|light|plant|mug|kitchen|home|wall"),
]


def kind_from_text(text: str) -> str:
    t = text.lower()
    for kind, pat in _KINDS:
        if re.search(pat, t):
            return kind
    return "clothing"


PRODUCT_OPENERS = ("Okay, you guys need to see this!", "Be honest, would you buy this?", "Rate this out of ten!",
                   "Okay, I'm obsessed with this!")


def product_line(item: str, seed: str = "") -> str:
    """About 10 words: a question or reaction, the product in a few words, the call to comment."""
    words = item.split()[:4]
    name = " ".join(words)
    opener = PRODUCT_OPENERS[sum(map(ord, seed or item)) % len(PRODUCT_OPENERS)]
    name = name.replace("korean", "Korean")
    this = "these" if words and words[-1].endswith("s") and not words[-1].endswith("ss") else "this"  # these jeans
    return f"{opener} Look at {this} {name}. Comment LINK!"


# ---------- variety: what changes from reel to reel, and learning which versions do best ----------
# The creator stays the same; the hook (first words), the place in their home and the closing move change.
# Every reel's choices are saved in data/reel_variants.json; Instagram's numbers for those reels
# (data/analytics/instagram.json) make the better-performing choices come up more often, while choices
# with few tries still get picked, so new ideas keep being tested.
HOOKS = {  # {Pieces} "Baggy jeans and white sneakers", {a}/{b} the first two pieces, {occasion}
    "rate": "Okay, rate this fit out of ten! {Pieces}. Comment LINK!",
    "honest": "Be honest, would you wear this? {Pieces}. Comment LINK!",
    "occasion": "This is my {occasion} fit! {Pieces}. Comment LINK!",
    "tip": "Styling tip: {a} with {b}. Trust me! Comment LINK!",
    "pov": "POV: you finally found the perfect {occasion} fit. Comment LINK!",
    "cute": "Okay wait, how cute is this fit? {Pieces}. Comment LINK!",  # women only
    "clean": "Bro, this fit is too clean! {Pieces}. Comment LINK!",     # men only
}
PRODUCT_HOOKS = {
    "obsessed": "Okay, I'm obsessed with this! Look at {this} {item}. Comment LINK!",
    "honest": "Be honest, would you buy this? Look at {this} {item}. Comment LINK!",
    "rate": "Rate this out of ten! Look at {this} {item}. Comment LINK!",
    "found": "Found the best {item} today! Comment LINK and I'll send it!",
    "need": "Okay, you guys need to see this! Look at {this} {item}. Comment LINK!",
}
SCENES = {
    "bedroom": None,  # the creator's own room (CREATORS)
    "balcony": "the small balcony of {h} Mumbai apartment: potted plants, a plastic chair, city buildings behind, "
               "warm late-afternoon light",
    "living": "the living room of {h} Mumbai apartment: a grey sofa with cushions, a bookshelf, a rug, daylight from "
              "a big window",
    "lift": "the mirrored lift of {h} apartment building; {s} films in the lift mirror, holding the phone",
    "door": "by the front door of {h} Mumbai apartment, about to step out: a shoe rack and keys on a hook beside {o}",
}
MOVES = {  # the silent end of an outfit reel (other products keep their own ending, ACTIONS)
    "turn": "{s} steps back, does a quick casual turn and smiles at the camera",
    "walk": "{s} walks two steps towards the camera and smiles",
    "spin": "{s} does a small happy spin and laughs",
    "fix": "{s} adjusts {h} collar or sleeves, looks back at the camera and nods",
    "wink": "{s} leans in close to the camera and winks",
}
OCCASIONS = [("wedding|sangeet|haldi|reception|mehendi|lehenga|anarkali|saree", "wedding guest"), ("office", "office"),
             ("brunch|co-ord", "brunch"), ("winter|coat|puffer|sweater|cardigan|flannel|hoodie|sweatshirt", "winter"),
             ("old money|linen|suede", "dinner date"), ("street|racing|cargo|baggy|korean", "weekend")]


def occasion_of(name: str) -> str:
    n = name.lower()
    return next((o for pat, o in OCCASIONS if re.search(pat, n)), "everyday")


VARIANTS_FILE = Path("data/reel_variants.json")
STATS_FILE = Path("data/analytics/instagram.json")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def scores() -> dict:
    """{dimension: {choice: (average engagement, reels)}} from Instagram's numbers for past reels.
    Engagement = likes + 2 x comments + 3 x saves + 3 x shares + reach / 50 (saves and shares count
    most: they are what Instagram rewards)."""
    variants = _load(VARIANTS_FILE, {})
    out = {}
    for post in _load(STATS_FILE, {}).get("posts", []):
        v = variants.get(post.get("key", ""))
        if not v:
            continue
        e = ((post.get("likes") or 0) + 2 * (post.get("comments") or 0) + 3 * (post.get("saves") or 0)
             + 3 * (post.get("shares") or 0) + (post.get("reach") or 0) / 50)
        for dim in ("hook", "scene", "move"):
            if v.get(dim):
                tot, n = out.setdefault(dim, {}).get(v[dim], (0.0, 0))
                out[dim][v[dim]] = (tot + e, n + 1)
    return {d: {c: (t / n, n) for c, (t, n) in cs.items()} for d, cs in out.items()}


def _choose(dim: str, options: list, seed: str, used: dict, stats: dict) -> str:
    """Best average so far plus a bonus for choices tried less (so they still get tested), minus a penalty
    for choices already used this week (so one week's reels differ). A little chance from the reel's id."""
    rnd = random.Random(f"{seed}:{dim}")
    st = stats.get(dim, {})
    best = max([m for m, _ in st.values()] or [1.0]) or 1.0
    total = sum(n for _, n in st.values())

    def score(c):
        mean, n = st.get(c, (best, 0))  # an untried choice is assumed as good as the best so far
        return mean / best + 0.6 * math.sqrt(math.log(total + 2) / (n + 1)) - 0.45 * used.get(c, 0) + rnd.random() * 0.15
    pick = max(options, key=score)
    used[pick] = used.get(pick, 0) + 1
    return pick


def pick_variant(seed: str, gender: str, kind: str, used: dict | None = None, stats: dict | None = None,
                 outfit: bool = True) -> dict:
    """{hook, scene, move} for one reel. `used` collects this week's picks (pass the same dict for a week).
    outfit=False: one product (even a piece of clothing), so the product hooks ("Look at this ...")."""
    used = {} if used is None else used
    stats = scores() if stats is None else stats
    if kind == "clothing" and outfit:
        hooks = [h for h in HOOKS if not (h == "cute" and gender == "men") and not (h == "clean" and gender != "men")]
    else:
        hooks = list(PRODUCT_HOOKS)
    scenes = [sc for sc in SCENES if not (sc == "lift" and kind in ("home", "gadget", "beauty"))]
    v = {"hook": _choose("hook", hooks, seed, used.setdefault("hook", {}), stats),
         "scene": _choose("scene", scenes, seed, used.setdefault("scene", {}), stats)}
    if kind == "clothing":
        v["move"] = _choose("move", list(MOVES), seed, used.setdefault("move", {}), stats)
    return v


def remember(key: str, variant: dict, week: str = ""):
    """Save which choices a reel used, so its Instagram numbers can be credited to them later."""
    data = _load(VARIANTS_FILE, {})
    data[key] = {**variant, "week": week}
    VARIANTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _these(words: list) -> str:
    return "these" if words and words[-1].endswith("s") and not words[-1].endswith("ss") else "this"


def look_line(name: str, pieces: list, hook: str) -> str:
    """What the creator says in an outfit reel: ~13 words, finished within 6 seconds."""
    pieces = [p.replace("korean", "Korean") for p in pieces[:2]]
    a, b = (pieces + ["the shoes"])[:2]
    joined = " and ".join(pieces)
    return HOOKS[hook].format(Pieces=joined[:1].upper() + joined[1:], a=a, b=b, occasion=occasion_of(name))


def item_line(item: str, hook: str) -> str:
    """What the creator says about one product."""
    words = item.replace("korean", "Korean").split()[:4]
    return PRODUCT_HOOKS[hook].format(item=" ".join(words), this=_these(words))


def video_prompt(gender: str, kind: str, item: str, line: str, photo: bool = False, variant: dict | None = None) -> str:
    """The Gemini (Veo) prompt: 8 seconds, the creator says `line` in the first 6 seconds, then a silent end.
    item: the outfit ("white oversized shirt; beige korean pants; ...") or one product ("black tote bag").
    photo: a product photo is attached in Gemini, so the product must match it exactly.
    variant: {scene, move} from pick_variant (default: the creator's room, the usual ending)."""
    variant = variant or {}
    g = "men" if gender == "men" else "women"
    s, h, S, o = ("he", "his", "He", "him") if g == "men" else ("she", "her", "She", "her")
    person, room = CREATORS[g]
    place = SCENES.get(variant.get("scene") or "bedroom")
    place = place.format(s=s, h=h, o=o) if place else room
    talk, end = (a.format(s=s, h=h, item=item) for a in ACTIONS.get(kind, ACTIONS["clothing"]))
    if kind == "clothing" and variant.get("move") in MOVES:
        end = MOVES[variant["move"]].format(s=s, h=h)
    showing = (f"{S} is wearing: {item}." if kind == "clothing"
               else f"{S} is showing the {item}" + (" (exactly as in the attached photo: same colour, shape, material and "
                                                 "details)." if photo else "."))
    return (f"An 8-second vertical 9:16 selfie video, filmed by a real Indian creator on an iPhone front camera, "
            f"held at arm's length. The creator is {person}. Natural and relatable, not a model. "
            f"Setting: {place}; ordinary natural light. {showing} "
            f'{S} starts talking right away, in the first second, and says (casual, natural Indian-English accent): '
            f'"{line}" {S} finishes the whole sentence by second 6. '
            f"0-6s: {s} {talk}, with natural expressions, raised eyebrows and a small laugh. "
            f"6-8s: no more talking; {end}. "
            f"Lips in sync with the words. Audio: only {h} voice from the phone mic, loud and clear, slight room echo. "
            f"No music. Look: real phone footage, slight hand shake, natural skin texture, not cinematic, "
            f"no slow motion, no studio. No text, no captions, no logos.")
