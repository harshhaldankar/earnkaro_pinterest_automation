import os
import json
import asyncio
import aiohttp
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from google import genai

from pipeline2.config import IMAGE_CACHE_FILE, TRUSTED_IMAGE_DOMAINS, GEMINI_API_KEY_P2
from pipeline2.trend_matcher import ProductDeal
from shared.rate_limiter import execute_with_backoff, increment_usage

def is_domain_trusted(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        return any(trusted in domain for trusted in TRUSTED_IMAGE_DOMAINS)
    except Exception:
        return False

def get_cached_image(url: str) -> str:
    if IMAGE_CACHE_FILE.exists():
        try:
            data = json.loads(IMAGE_CACHE_FILE.read_text())
            return data.get(url, "")
        except Exception:
            pass
    return ""

def set_cached_image(url: str, local_path: str):
    data = {}
    if IMAGE_CACHE_FILE.exists():
        try:
            data = json.loads(IMAGE_CACHE_FILE.read_text())
        except Exception:
            pass
    data[url] = local_path
    IMAGE_CACHE_FILE.write_text(json.dumps(data, indent=2))

async def validate_with_gemini(image_bytes: bytes, title: str) -> bool:
    """Uses Gemini 2.0 Flash to validate if the image matches the product title."""
    if not GEMINI_API_KEY_P2:
        return True # Fallback if no key

    client = genai.Client(api_key=GEMINI_API_KEY_P2)
    prompt = f"Does this image show {title}? Reply YES or NO."
    
    # We use a synchronous wrapper inside executor since genai is sync, or just execute_with_backoff
    def run_genai():
        increment_usage("GEMINI_P2")
        # In Gemini SDK, we upload file or pass bytes. Since we have bytes, we can pass it directly
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, {'mime_type': 'image/jpeg', 'data': image_bytes}]
        )
        return response.text.strip().upper()

    try:
        # Run in thread pool to not block asyncio
        loop = asyncio.get_event_loop()
        # Rate limit wrapper handles 429
        result = await execute_with_backoff(lambda: loop.run_in_executor(None, run_genai), max_retries=3)
        return "YES" in result
    except Exception as e:
        print(f"[ImageFetcher] Gemini validation failed (rate limit/error): {e}. Falling back to heuristics.")
        # Heuristic fallback: size > 20KB (we already have it loaded, we can just return True for now)
        return len(image_bytes) > 20480

async def fetch_and_validate_image(deal: ProductDeal) -> str:
    """
    Downloads the product image, validates it via Gemini if untrusted,
    and returns the local file path.
    """
    if not deal.image_url:
        return ""

    cached = get_cached_image(deal.image_url)
    if cached and os.path.exists(cached):
        return cached

    print(f"[ImageFetcher] Downloading {deal.image_url[:60]}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(deal.image_url) as resp:
                if resp.status != 200:
                    return ""
                img_bytes = await resp.read()

        # Validation
        if not is_domain_trusted(deal.image_url):
            print(f"[ImageFetcher] Domain untrusted. Validating with Gemini...")
            is_valid = await validate_with_gemini(img_bytes, deal.title)
            if not is_valid:
                print(f"[ImageFetcher] Validation failed for {deal.title}. Rejecting image.")
                return ""
        else:
            print(f"[ImageFetcher] Domain is trusted. Skipping Gemini validation.")

        # Save to disk
        from pipeline2.config import CACHE_DIR
        local_path = CACHE_DIR / f"{deal.retailer.lower()}_{deal.title[:10].replace(' ', '_')}_{hash(deal.image_url)}.jpg"
        
        # Convert and optimize
        image = Image.open(BytesIO(img_bytes)).convert("RGB")
        image.save(local_path, "JPEG", quality=90)
        
        set_cached_image(deal.image_url, str(local_path))
        return str(local_path)
    except Exception as e:
        print(f"[ImageFetcher] Error fetching image: {e}")
        return ""
