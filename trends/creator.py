"""
creator.py - the Gemini video prompt for every reel: the same two creators (one woman, one man), each in
their own room, filmed selfie-style on a phone and talking to the viewer. Only what they show changes:
an outfit, shoes, a bag, a watch or jewellery, a beauty product, or something for the home.

  video_prompt(gender, kind, item, line, photo=False) -> str
  kind_from_text("korean pants")                     -> "clothing"
  product_line(item, seed)                           -> what the creator says about one product
"""
import re

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


def video_prompt(gender: str, kind: str, item: str, line: str, photo: bool = False) -> str:
    """The Gemini (Veo) prompt: 8 seconds, the creator says `line` in the first 6 seconds, then a silent end.
    item: the outfit ("white oversized shirt; beige korean pants; ...") or one product ("black tote bag").
    photo: a product photo is attached in Gemini, so the product must match it exactly."""
    g = "men" if gender == "men" else "women"
    s, h, S = ("he", "his", "He") if g == "men" else ("she", "her", "She")
    person, room = CREATORS[g]
    talk, end = (a.format(s=s, h=h, item=item) for a in ACTIONS.get(kind, ACTIONS["clothing"]))
    showing = (f"{S} is wearing: {item}." if kind == "clothing"
               else f"{S} is showing the {item}" + (" (exactly as in the attached photo: same colour, shape, material and "
                                                 "details)." if photo else "."))
    return (f"An 8-second vertical 9:16 selfie video, filmed by a real Indian creator on an iPhone front camera, "
            f"held at arm's length. The creator is {person}. Natural and relatable, not a model. "
            f"Setting: {room}; ordinary daylight from the window. {showing} "
            f'{S} starts talking right away, in the first second, and says (casual, natural Indian-English accent): '
            f'"{line}" {S} finishes the whole sentence by second 6. '
            f"0-6s: {s} {talk}, with natural expressions, raised eyebrows and a small laugh. "
            f"6-8s: no more talking; {end}. "
            f"Lips in sync with the words. Audio: only {h} voice from the phone mic, loud and clear, slight room echo. "
            f"No music. Look: real phone footage, slight hand shake, natural skin texture, not cinematic, "
            f"no slow motion, no studio. No text, no captions, no logos.")
