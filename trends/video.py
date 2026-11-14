"""
video.py - "Today's video": one AI try-on video a day, made by hand in Gemini (Veo) and finished here.

  build_plan(themes)   data/video_plan.json: every product of this week's trends with what's needed to
                       make its video (the photo, the free app, a photo prompt, a motion prompt, the
                       caption and an upload link). The control room shows one a day.
  finish(src, key)     the uploaded clip (often 480p, 5 seconds, no sound) as a reel: 1080x1920,
                       sharpened, the trend and price on top for the first 2 seconds, a price sticker,
                       music, and the "Comment LINK" end card. "3 · Instagram reel" posts it.

Uploads go to inbox/video-<slug>-p<n>/ (trends/instagram.py finishes and posts them, with
caption_for() giving the product's own caption).
"""
import json
import re
import subprocess
import tempfile
from pathlib import Path

from trends.kit import REPO, caption_for
from trends.reel import AUDIO_DIR, get_ffmpeg_cmd, short_label

PLAN_FILE = Path("data/video_plan.json")
KEY = re.compile(r"^video-(.+)-p(\d+)$")


def kind_of(p: dict) -> str:
    c = p["category"]
    if "footwear" in c:
        return "footwear"
    if "handbag" in c or "wallet" in c:
        return "bag"
    if c.startswith("accessories"):
        return "accessory"
    if c.startswith("beauty"):
        return "beauty"
    if c.startswith("home"):
        return "home"
    return "clothing"


def prompts(th: dict, p: dict) -> dict:
    """{tool, photo_step, photo_prompt, video_prompt} for one product."""
    men = th.get("gender") == "men" or p["category"].startswith("men")
    who, she, her = ("man", "He", "his") if men else ("woman", "She", "her")
    item = short_label(p["name"], p["brand"]).lower()
    kind = kind_of(p)
    look = "same colour, pattern and details as in the photo"
    scene = ("Mirror selfie in a bright, tidy bedroom, phone in hand covering part of the face" if kind in ("clothing", "accessory")
             else "Standing on a sunny city street, photo taken from a friend's phone")
    if kind == "home":
        photo = (f"Create a realistic vertical 9:16 photo of exactly this {item} ({look}) in a cosy, softly lit Indian "
                 f"living room with plants and warm fairy lights, as if shot on a phone. No people, no text.")
    else:
        verb = {"bag": "carrying", "beauty": "holding up"}.get(kind, "wearing")
        photo = (f"Create a realistic vertical 9:16 photo of a young Indian {who}, early 20s, {verb} exactly this {item} "
                 f"({look}). {scene}. Natural daylight, casual Instagram look. No text.")
    motion = {
        "clothing": (f"Handheld phone video, mirror outfit check. {she} turns slowly side to side to show the outfit, then "
                     + ("adjusts the collar and nods at the camera." if men else "smiles and adjusts her hair.")
                     + " Natural daylight, slight camera shake, casual UGC style, realistic fabric movement."),
        "footwear": (f"Handheld phone video looking down at {her} feet. {she} steps forward, turns {her} foot to show the "
                     f"shoe from the side, then taps it. Natural light, slight shake, casual UGC style."),
        "bag": (f"Handheld phone video. {she} lifts the bag towards the camera, turns it to show the details, then smiles. "
                f"Soft daylight, slight shake, casual UGC style."),
        "accessory": (f"Handheld phone close-up. {she} turns slowly so the {item} catches the light, then smiles at the "
                      f"camera. Soft daylight, casual UGC style."),
        "beauty": (f"Handheld phone video. {she} holds the product up to the camera, turns it to show the label, then "
                   f"smiles. Bright natural light, casual UGC style."),
        "home": f"Slow handheld phone pan across the cosy room, ending close on the {item}. Warm light, casual UGC style.",
    }[kind]
    if kind == "clothing":
        return {"tool": "Kling AI → Virtual Try-On", "kind": kind,
                "photo_step": "Open Kling AI → Virtual Try-On, upload the product photo, pick a model and generate. "
                              "(No Kling? Use the photo prompt in Gemini instead.)",
                "photo_prompt": photo, "video_prompt": motion}
    return {"tool": "Gemini (photo) + Kling or Upsampler (video)", "kind": kind,
            "photo_step": "In Gemini, upload the product photo with the photo prompt. Check the product looks the same.",
            "photo_prompt": photo, "video_prompt": motion}


def gemini_script(th: dict, p: dict) -> str:
    """An 8-second shot-by-shot script for Gemini's video tool (Veo), with the product photo attached.
    Gemini may make it landscape; the person stays centred so our 9:16 crop keeps them."""
    men = th.get("gender") == "men" or p["category"].startswith("men")
    who, she, her = ("man", "He", "his") if men else ("woman", "She", "her")
    item = short_label(p["name"], p["brand"]).lower()
    kind = kind_of(p)
    this = "these" if item.endswith("s") and not item.endswith("ss") else "this"  # "these sandals", "this dress"
    same = f"exactly {this} {item} from the attached photo: same colour, pattern, material and details, unchanged"
    style = ("Shot on a phone, handheld, casual Instagram UGC style, natural daylight, realistic skin and fabric, "
             f"slight camera shake. Keep {'the person' if kind != 'home' else 'the subject'} centred in the frame, vertical 9:16. "
             "No text, no captions, no logos, no music; natural ambient sound only.")
    if kind == "home":
        return (f"Create an 8-second video. {same[0].upper() + same[1:]}, placed in a cosy, softly lit Indian living room "
                f"with plants and warm fairy lights. 0-3s: the camera glides slowly through the room. 3-6s: it moves in "
                f"close on the {item}, showing the texture. 6-8s: it pulls back to show the whole corner. No people. {style}")
    shots = {
        "clothing": (f"0-2s: {she.lower()} steps in front of a mirror in a bright, tidy bedroom and glances at the camera. "
                     f"2-6s: {she.lower()} turns slowly side to side to show the fit; the fabric moves naturally. "
                     f"6-8s: close-up of the fabric and details, then {she.lower()} smiles at the camera."),
        "footwear": (f"0-2s: close-up of {her} feet stepping onto a sunny street. 2-5s: {she.lower()} walks towards the camera, "
                     f"the shoes in focus. 5-8s: {she.lower()} stops, turns one foot to show the side, then taps it."),
        "bag": (f"0-2s: {she.lower()} walks along a sunny street carrying the bag. 2-5s: {she.lower()} lifts it towards the "
                f"camera and turns it to show the details. 5-8s: {she.lower()} smiles and slings it back on {her} shoulder."),
        "accessory": (f"0-2s: {she.lower()} looks into a mirror in soft daylight. 2-6s: {she.lower()} turns slowly so the "
                      f"{item} catches the light; close-up on it. 6-8s: {she.lower()} smiles at the camera."),
        "beauty": (f"0-2s: {she.lower()} holds the product up to the camera in a bright room. 2-6s: {she.lower()} turns it to "
                   f"show the label, then applies a little. 6-8s: close-up of the result, then a smile."),
    }[kind]
    verb = {"bag": "carries", "beauty": "uses"}.get(kind, "wears")
    return (f"Create an 8-second video. A young Indian {who}, early 20s, {verb} {same}. {shots} {style}")


# ---------- Google Flow storyboards: 3 shots joined in Scenebuilder, with the same model every time ----------
# Made once in Gemini and saved; attached in Flow as an "ingredient" so every reel has the same face.
MODEL_PROMPTS = {
    "woman": ("Create a realistic portrait photo, vertical 3:4, of a friendly young Indian woman, 24, warm medium-brown "
              "skin, long dark wavy hair, natural makeup, soft smile, wearing a plain white t-shirt, standing against a "
              "plain light-grey wall, soft daylight, full upper body visible, sharp focus. No text, no jewellery."),
    "man": ("Create a realistic portrait photo, vertical 3:4, of a friendly young Indian man, 25, warm medium-brown skin, "
            "short neat black hair, light stubble, relaxed smile, wearing a plain white t-shirt, standing against a plain "
            "light-grey wall, soft daylight, full upper body visible, sharp focus. No text, no accessories."),
}
_LOOK = ("Vertical 9:16, shot on a phone, handheld, natural daylight, realistic skin and fabric, casual Instagram UGC "
         "style. Keep the product exactly as in its ingredient photo: same colour, pattern, shape and details. "
         "Plain packaging, no brand logos, no text, no captions, no music.")


def flow_storyboard(th: dict, p: dict) -> list:
    """[{shot, time, ingredients, prompt}] x3 for Google Flow: unboxing, wearing or using it, the reveal."""
    men = th.get("gender") == "men" or p["category"].startswith("men")
    she, her, who = ("he", "his", "man") if men else ("she", "her", "woman")
    item = short_label(p["name"], p["brand"]).lower()
    kind = kind_of(p)
    M = f"The {who} from the attached photo"
    shots = {
        "clothing": [
            ("Unboxing", ["product"], f"Close-up of hands opening a plain kraft parcel on a bed with white sheets, "
             f"pulling back tissue paper and lifting out the {item}, then holding it up to the camera to show the fabric."),
            ("Try-on", ["product", "model"], f"{M} wears the {item} and turns slowly in front of a full-length mirror in a "
             f"bright bedroom, adjusting {her} sleeves; the fabric moves naturally."),
            ("Reveal", ["product", "model"], f"{M} in the {item} walks towards the camera on a sunny street, then stops, "
             f"smiles and does a small turn to show the full outfit."),
        ],
        "footwear": [
            ("Unboxing", ["product"], f"Close-up of hands opening a plain shoebox on a wooden floor, unwrapping tissue "
             f"paper and lifting out the {item}, turning them to show the sides and sole."),
            ("Try-on", ["product", "model"], f"{M} sits on the edge of a bed and puts on the {item}, fastening them; "
             f"close-up on the feet, then {she} stands up."),
            ("Reveal", ["product", "model"], f"Low camera following {her} feet in the {item} walking on a sunny street, "
             f"then rising to show the {who}'s full outfit as {she} smiles."),
        ],
        "bag": [
            ("Unboxing", ["product"], f"Close-up of hands opening a plain parcel on a table, sliding the {item} out of a "
             f"cloth dust bag and turning it to show the details and the inside."),
            ("Pack it", ["product", "model"], f"{M} drops a phone, sunglasses and a lipstick into the {item}, closes it, "
             f"and slings it on {her} shoulder in front of a mirror."),
            ("Reveal", ["product", "model"], f"{M} walks out of a café with the {item} on {her} shoulder, glances at the "
             f"camera and smiles."),
        ],
        "accessory": [
            ("Unboxing", ["product"], f"Close-up of hands opening a small plain gift box on a dressing table and lifting "
             f"out the {item}; it catches the light."),
            ("Put it on", ["product", "model"], f"{M} puts on the {item} in front of a mirror; close-up as it catches the "
             f"light, then {she} looks at the camera."),
            ("Reveal", ["product", "model"], f"{M}, dressed for an evening out, turns towards the camera in warm "
             f"golden-hour light; the {item} is clearly visible, then a smile."),
        ],
        "beauty": [
            ("Unboxing", ["product"], f"Close-up of hands opening a plain parcel on a vanity table and lining up the "
             f"{item} next to a mirror, then turning it to show the label."),
            ("Apply", ["product", "model"], f"{M} sits at the vanity and applies the {item}, close-up on the face and "
             f"the product."),
            ("Reveal", ["product", "model"], f"Close-up of {M}'s finished look in soft window light; {she} turns to the "
             f"camera and smiles."),
        ],
        "home": [
            ("Unboxing", ["product"], f"Close-up of hands opening a plain parcel on a living-room rug and lifting out "
             f"the {item}, showing the texture."),
            ("Style it", ["product"], f"Hands place the {item} in a cosy Indian living-room corner with a plant and "
             f"warm fairy lights, adjusting it until it looks right."),
            ("Reveal", ["product"], f"The camera slowly pulls back to reveal the whole styled corner in warm evening "
             f"light, with the {item} as the centrepiece."),
        ],
    }[kind]
    out = []
    for n, (name, ing, action) in enumerate(shots, 1):
        # In Gemini a video takes one photo: the product alone, or our model already wearing it (the dress step)
        attach = f"the {who} wearing it (step 1 photo)" if "model" in ing else "the product photo"
        out.append({"shot": n, "name": name, "time": f"{(n - 1) * 8}-{n * 8}s", "attach": attach,
                    "prompt": f"Create an 8-second video from the attached photo. {action} {_LOOK}"})
    return out


def dress_prompt(th: dict, p: dict) -> str:
    """Gemini photo: our saved model wearing (or holding) the product, used for shots 2 and 3."""
    men = th.get("gender") == "men" or p["category"].startswith("men")
    who = "man" if men else "woman"
    item = short_label(p["name"], p["brand"]).lower()
    verb = {"bag": "carrying", "beauty": "holding up", "home": ""}.get(kind_of(p), "wearing")
    if not verb:
        return ""
    return (f"Use the two attached photos: the first is our model, the second is a product. Create a realistic "
            f"vertical 9:16 full-body photo of exactly the same {who} (same face, hair and skin tone) {verb} exactly "
            f"this {item} (same colour, pattern, material and details), standing in a bright, tidy bedroom in "
            f"natural daylight. No text, no logos.")


def build_plan(themes: list) -> list:
    """Every product of the latest week's trends, clothing first (try-on apps do clothes best), then
    the best-paying; trends interleaved so consecutive days differ."""
    latest = themes[0]["week"] if themes else ""
    per_theme = []
    for th in [t for t in themes if t["week"] == latest]:
        rows = []
        for i, p in enumerate(th["products"], 1):
            if not (Path("docs/ideas") / th["slug"] / f"p{i}.jpg").exists():
                continue
            key = f"video-{th['slug']}-p{i}"
            rows.append({
                "key": key, "slug": th["slug"], "title": th["title"], "n": i, "photo": f"ideas/{th['slug']}/p{i}.jpg",
                "product": short_label(p["name"], p["brand"]), "brand": p["brand"], "store": p["store"],
                "price": p["price"], "mrp": p["mrp"], "discount": p["discount"],
                **prompts(th, p), "gemini_script": gemini_script(th, p), "flow": flow_storyboard(th, p), "dress": dress_prompt(th, p),
                "model": "man" if th.get("gender") == "men" or p["category"].startswith("men") else "woman",
                "caption": caption_for(th, p),
                "upload": f"https://github.com/{REPO}/upload/master/inbox/{key}",
            })
        rows.sort(key=lambda r: (r["kind"] != "clothing", -th["products"][r["n"] - 1].get("commission", 0)))
        per_theme.append(rows)
    plan = [r for group in zip(*[g + [None] * (max(map(len, per_theme), default=0) - len(g)) for g in per_theme])
            for r in group if r]
    PLAN_FILE.write_text(json.dumps({"week": latest, "models": MODEL_PROMPTS, "videos": plan}, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return plan


def find(key: str):
    """(theme, product, photo number) for an upload key, or None."""
    m = KEY.match(key)
    if not m:
        return None
    try:
        themes = json.loads(Path("data/themes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for th in themes:
        if th["slug"] == m.group(1) and 0 < int(m.group(2)) <= len(th["products"]):
            return th, th["products"][int(m.group(2)) - 1], int(m.group(2))
    return None


def _duration(path: str) -> float:
    err = subprocess.run([get_ffmpeg_cmd(), "-i", path], capture_output=True, text=True, errors="ignore").stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def upload_order(files: list) -> list:
    """Clips in the order they were uploaded (each GitHub upload is its own commit), then by name:
    upload shot 1, then shot 2, then shot 3."""
    def when(f):
        r = subprocess.run(["git", "log", "-1", "--format=%ct", "--", str(f)], capture_output=True, text=True)
        return int(r.stdout.strip() or 0)
    return sorted(files, key=lambda f: (when(f), str(f)))


def finish(src, out: str, th: dict, p: dict, n: int) -> bool:
    """The uploaded clip(s) (one path or a list, joined in order, up to 30 s) as a finished reel at
    out. False (and out not written) if anything fails."""
    from trends.editorial import H, W, _hook_layer, _outro, _rs
    from trends.popreel import _sticker
    srcs = [str(s) for s in (src if isinstance(src, (list, tuple)) else [src])]
    clips = [(s, _duration(s)) for s in srcs]
    clips = [(s, d) for s, d in clips if d > 0.5]
    if not clips:
        print(f"[Video] {srcs} isn't a readable video")
        return False
    budget, kept = 30.0, []
    for s, d in clips:
        if budget <= 0.5:
            break
        kept.append((s, min(d, budget)))
        budget -= min(d, budget)
    clip = sum(d for _, d in kept)
    k = len(kept)
    photo = f"docs/ideas/{th['slug']}/p{n}.jpg"
    item = dict(label=short_label(p["name"], p["brand"]), price=p["price"], mrp=p["mrp"], discount=p["discount"], store=p["store"])
    total = clip + 1.8
    with tempfile.TemporaryDirectory() as tmp:
        hook, sticker, outro = (str(Path(tmp) / f) for f in ("hook.png", "sticker.png", "outro.png"))
        _hook_layer(th["title"], f"just {_rs(p['price'])} on {p['store']}").save(hook)
        s = _sticker(item, False)
        s.save(sticker)
        _outro([photo], 1).save(outro)
        sx, sy = W - s.width - 30, H - s.height - 330
        cmd = [get_ffmpeg_cmd(), "-y", "-loglevel", "error"]
        for path, d in kept:  # inputs 0..k-1: the clips; then outro, hook, sticker, music
            cmd += ["-t", f"{d:.2f}", "-i", path]
        cmd += ["-loop", "1", "-t", "1.8", "-i", outro, "-i", hook, "-i", sticker]
        music = AUDIO_DIR / "lofi_upbeat.ogg"
        if music.exists():
            cmd += ["-i", str(music)]
        fit = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,fps=30,unsharp=5:5:0.7"
        fc = "".join(f"[{i}:v]{fit},format=yuv420p[s{i}];" for i in range(k))
        fc += ("".join(f"[s{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0,format=rgba[c];" if k > 1
               else "[s0]format=rgba[c];")
        fc += (f"[c][{k + 1}:v]overlay=0:0:enable='lt(t,2.2)'[c1];"
               f"[c1][{k + 2}:v]overlay={sx}:{sy}:enable='gte(t,0.8)',format=yuv420p[c2];"
               f"[{k}:v]scale={W}:{H},setsar=1,fps=30,format=yuv420p[o];"
               f"[c2][o]concat=n=2:v=1:a=0,scale=out_range=tv,format=yuv420p[v]")  # standard range for phones
        if music.exists():
            fc += f";[{k + 3}:a]atrim=0:{total:.2f},afade=t=in:st=0:d=0.2,afade=t=out:st={total - 0.8:.2f}:d=0.8[a]"
        cmd += ["-filter_complex", fc, "-map", "[v]"] + (["-map", "[a]", "-c:a", "aac", "-b:a", "160k"] if music.exists() else [])
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-t", f"{total:.2f}", out]
        r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        if r.returncode != 0 or not Path(out).exists():
            print(f"[Video] Finishing failed: {r.stderr[-400:]}")
            Path(out).unlink(missing_ok=True)
            return False
    print(f"[Video] Finished {k} clip(s) -> {out} ({total:.1f}s)")
    return True


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    plan = build_plan(json.loads(Path("data/themes.json").read_text(encoding="utf-8")))
    print(f"[Video] {len(plan)} videos planned; first: {plan[0]['product'] if plan else '-'}")
