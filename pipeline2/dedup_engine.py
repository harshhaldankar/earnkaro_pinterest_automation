import json
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

INDEX_FILE = "posted_deals_index.json"

def _normalize_url(url: str) -> str:
    """
    Normalizes a URL by lowercasing the domain and path, 
    and stripping all query parameters. This ensures tracking 
    links don't bypass deduplication.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        # Rebuild without query string
        clean = f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.lower()}"
        return clean.strip('/')
    except Exception:
        return url

def _load_index() -> dict:
    if Path(INDEX_FILE).exists():
        try:
            return json.loads(Path(INDEX_FILE).read_text())
        except Exception:
            pass
    return {}

def _save_index(data: dict):
    Path(INDEX_FILE).write_text(json.dumps(data, indent=2))

def is_duplicate(url: str) -> bool:
    """Checks if a normalized URL exists in the deduplication index."""
    if not url: return False
    index = _load_index()
    norm_url = _normalize_url(url)
    return norm_url in index

def register_posted_deal(url: str, pipeline: int, boards: list[str] = None):
    """Registers a URL as posted to prevent future duplicates."""
    if not url: return
    index = _load_index()
    norm_url = _normalize_url(url)
    
    index[norm_url] = {
        "pipeline": pipeline,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "boards": boards or []
    }
    _save_index(index)

def dedup_against_all(deals: list) -> list:
    """Filters a list of deals (ProductDeal objects), removing any that are already in the index."""
    unique_deals = []
    index = _load_index()
    for deal in deals:
        norm_url = _normalize_url(deal.product_url)
        if norm_url not in index:
            unique_deals.append(deal)
        else:
            print(f"[Dedup] Skipping duplicate deal: {deal.title}")
    return unique_deals
