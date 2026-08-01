import json
import os
import time
import random
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Callable, Any

RATE_LIMIT_FILE = "rate_limits.json"
IST = timezone(timedelta(hours=5, minutes=30))

def _get_today_str() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")

def get_usage(key_identifier: str) -> int:
    """Gets the current daily usage for a given key identifier (e.g., 'GEMINI_P1')."""
    if not os.path.exists(RATE_LIMIT_FILE):
        return 0
    try:
        with open(RATE_LIMIT_FILE, "r") as f:
            data = json.load(f)
        today = _get_today_str()
        return data.get(today, {}).get(key_identifier, 0)
    except (json.JSONDecodeError, FileNotFoundError):
        return 0

def increment_usage(key_identifier: str, count: int = 1):
    """Increments the daily usage for a given key identifier."""
    data = {}
    if os.path.exists(RATE_LIMIT_FILE):
        try:
            with open(RATE_LIMIT_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    today = _get_today_str()
    if today not in data:
        data[today] = {}
        
    data[today][key_identifier] = data[today].get(key_identifier, 0) + count

    # Cleanup old days to prevent file bloating
    keys_to_delete = [k for k in data.keys() if k != today]
    for k in keys_to_delete:
        del data[k]

    # Write atomically
    tmp_file = f"{RATE_LIMIT_FILE}.tmp"
    with open(tmp_file, "w") as f:
        json.dump(data, f)
    os.replace(tmp_file, RATE_LIMIT_FILE)

async def execute_with_backoff(
    func: Callable, 
    *args, 
    max_retries: int = 5, 
    initial_delay: float = 2.0, 
    **kwargs
) -> Any:
    """
    Executes an async function with exponential backoff and jitter.
    Specifically catches 429 Too Many Requests errors.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Simple check if "429" or "too many requests" is in the error message
            error_str = str(e).lower()
            if "429" in error_str or "too many requests" in error_str or "quota" in error_str:
                if attempt == max_retries - 1:
                    print(f"[RateLimiter] Max retries ({max_retries}) reached. Failing.")
                    raise e
                
                # Exponential backoff with full jitter
                # jitter = random.uniform(0, delay)
                jitter = delay * random.uniform(0.5, 1.5)
                print(f"[RateLimiter] Rate limited (429). Retrying in {jitter:.2f} seconds (Attempt {attempt+1}/{max_retries})...")
                await asyncio.sleep(jitter)
                delay *= 2  # Exponentially increase the base delay
            else:
                # If it's a different error, don't backoff, just raise
                raise e
