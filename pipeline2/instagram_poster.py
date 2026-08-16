"""
instagram_poster.py — Posts deal images to Instagram using instagrapi.
Uses username/password login with session caching to avoid 2FA challenges.
"""
import os, json, random
from pathlib import Path
from datetime import datetime, timezone, timedelta
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired

IST = timezone(timedelta(hours=5, minutes=30))
IG_SESSION_FILE = "instagrapi_session.json"  # NEW separate file, not instagram_session.json
IG_LOG = "ig_posts_today.json"
MAX_IG_POSTS_PER_DAY = 2

CAPTIONS = [
    "🔥 {title}\n\n💰 Only ₹{price} (was ₹{mrp}) — {discount}% OFF!\n\nShop link in bio! 🛍️\n\n#IndianDeals #AmazonIndia #FlipkartSale #OnlineShopping #DealAlert #LootDeal #ShoppingIndia #SaveMoney",
    "🚨 Price Drop Alert!\n\n{title}\n✅ ₹{price} | {discount}% OFF\n\nLink in bio — grab before stock runs out! 💨\n\n#DiscountDeals #IndiaOffers #BestPrice #Shopping #Sale #Savings",
    "😱 Incredible deal found!\n\n{title}\n💸 MRP ₹{mrp} → Now just ₹{price}\n\nTap link in bio to shop! ⬆️\n\n#LootAlert #MegaSale #IndianShopping #BestDeals #FlipkartIndia #AmazonDeals"
]

def get_caption(deal) -> str:
    template = random.choice(CAPTIONS)
    try:
        return template.format(
            title=getattr(deal, 'title', str(deal))[:80],
            price=getattr(deal, 'price', ''),
            mrp=getattr(deal, 'mrp', ''),
            discount=getattr(deal, 'discount_percent', '')
        )
    except:
        return f"🔥 Amazing deal! {getattr(deal, 'title', '')}\n\nShop link in bio! #IndianDeals #Sale"

def check_ig_limit() -> bool:
    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        if Path(IG_LOG).exists():
            data = json.loads(Path(IG_LOG).read_text())
            count = sum(1 for p in data if p.get('date') == today)
            return count < MAX_IG_POSTS_PER_DAY
    except:
        pass
    return True

def log_ig_post(title: str):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    data = []
    if Path(IG_LOG).exists():
        try: data = json.loads(Path(IG_LOG).read_text())
        except: pass
    data.append({"date": today, "title": title, "ts": datetime.now(IST).isoformat()})
    Path(IG_LOG).write_text(json.dumps(data, indent=2))

def login_instagram() -> Client | None:
    username = os.getenv("INSTAGRAM_USERNAME", "")
    password = os.getenv("INSTAGRAM_PASSWORD", "")
    
    if not username or not password:
        print("[Instagram] FATAL: INSTAGRAM_USERNAME or INSTAGRAM_PASSWORD not set.")
        return None

    cl = Client()
    cl.delay_range = [2, 5]  # human-like delays

    # Try loading cached session first
    if Path(IG_SESSION_FILE).exists():
        try:
            cl.load_settings(IG_SESSION_FILE)
            cl.login(username, password)  # verify session still valid
            print("[Instagram] Loaded cached instagrapi session.")
            return cl
        except LoginRequired:
            print("[Instagram] Cached session expired — doing fresh login.")
        except Exception as e:
            print(f"[Instagram] Session load error: {e} — trying fresh login.")

    # Fresh login
    try:
        cl.login(username, password)
        cl.dump_settings(IG_SESSION_FILE)  # cache for next run
        print("[Instagram] Fresh login successful. Session cached.")
        return cl
    except ChallengeRequired:
        print("[Instagram] Instagram challenge required — cannot post from this IP automatically.")
        print("[Instagram] FIX: Run 'python refresh_instagram_session.py' locally to approve the challenge.")
        return None
    except TwoFactorRequired:
        print("[Instagram] 2FA required — disable 2FA on Instagram account or use app password.")
        return None
    except Exception as e:
        print(f"[Instagram] Login failed: {e}")
        return None

async def post_to_instagram(deals: list, image_paths: list) -> bool:
    if not check_ig_limit():
        print(f"[Instagram] Daily limit ({MAX_IG_POSTS_PER_DAY}) reached. Skipping.")
        return False
    
    if not deals or not image_paths:
        print("[Instagram] No deals or images provided.")
        return False

    cl = login_instagram()
    if not cl:
        return False

    deal = deals[0]
    image_path = image_paths[0]

    if not Path(image_path).exists():
        print(f"[Instagram] Image not found: {image_path}")
        return False

    caption = get_caption(deal)
    
    try:
        print(f"[Instagram] Uploading photo: {image_path}")
        cl.photo_upload(path=image_path, caption=caption)
        title = getattr(deal, 'title', str(deal))
        log_ig_post(title)
        print(f"[Instagram] ✅ Successfully posted: {title[:60]}")
        return True
    except Exception as e:
        print(f"[Instagram] ❌ Post failed: {e}")
        # Save to pending queue
        pending = []
        pending_file = Path("pending_ig_posts.json")
        if pending_file.exists():
            try: pending = json.loads(pending_file.read_text())
            except: pass
        pending.append({
            "title": getattr(deal, 'title', ''),
            "image": image_path,
            "caption": caption,
            "failed_at": datetime.now(IST).isoformat()
        })
        pending_file.write_text(json.dumps(pending, indent=2))
        print(f"[Instagram] Saved to pending_ig_posts.json for retry.")
        return False
