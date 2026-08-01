import os
from pathlib import Path
from dotenv import load_dotenv

# Load all environment variables
env_path = Path("../.env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")
load_dotenv(env_path)

# Credentials
GEMINI_API_KEY_P2 = os.getenv("GEMINI_API_KEY_P2", "")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
PINTEREST_EMAIL = os.getenv("PINTEREST_EMAIL", "")
PINTEREST_PASSWORD = os.getenv("PINTEREST_PASSWORD", "")

# Shared constants
MAX_PINS_PER_DAY_P2 = 8
MAX_INSTAGRAM_POSTS_PER_DAY = 4

# Directories & Caches
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
TRENDING_CACHE_FILE = CACHE_DIR / "trending_cache.json"
IMAGE_CACHE_FILE = CACHE_DIR / "image_cache.json"
PINS_LOG_P2 = "pins_today_p2.json"
INSTAGRAM_SESSION_FILE = "instagram_session.json"
PINTEREST_SESSION_FILE = "pinterest_session.json"

# Board Routing
from shared.board_classifier import BOARD_ROUTING

# Trusted Image Domains (bypass Gemini validation)
TRUSTED_IMAGE_DOMAINS = [
    "media.ajio.com",
    "assets.myntassets.com",
    "rukminim2.flixcart.com",
    "rukminim1.flixcart.com",
    "m.media-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "nykaa.com", # Needs specific cdn url if they use it
]

# Profit Tiers Thresholds
PROFIT_TIERS = {
    "Ultra-High": 10.0,
    "High": 5.0,
    "Medium": 3.5,
    "Low": 0.0
}
