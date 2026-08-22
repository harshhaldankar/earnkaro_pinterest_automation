import json
import os
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict

def clean_json_string(s):
    # Remove git conflict markers, taking the incoming changes
    s = re.sub(r'<<<<<<<.*?=======', '', s, flags=re.DOTALL)
    s = re.sub(r'>>>>>>>.*?\n', '', s)
    return s

def load_json(filepath, default_val):
    if not os.path.exists(filepath):
        return default_val
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    content = clean_json_string(content)
    try:
        return json.loads(content)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return default_val

def get_platform(url):
    if not url: return 'Other'
    url = url.lower()
    if 'amazon' in url: return 'Amazon'
    if 'flipkart' in url or 'fkrt' in url: return 'Flipkart'
    if 'myntra' in url: return 'Myntra'
    if 'ajio' in url: return 'Ajio'
    return 'Other'

def clean_board_name(name):
    return re.sub(r'[^\x00-\x7F]+', '', name).strip()

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    analytics = load_json(os.path.join(base_dir, 'analytics.json'), [])
    deals = load_json(os.path.join(base_dir, 'deals_data.json'), [])
    pins_today = load_json(os.path.join(base_dir, 'pins_today.json'), [])
    pins_today_p2 = load_json(os.path.join(base_dir, 'pins_today_p2.json'), [])
    posted_deals_index = load_json(os.path.join(base_dir, 'posted_deals_index.json'), {})
    
    ig_posts_today = load_json(os.path.join(base_dir, 'ig_posts_today.json'), [])
    pending_ig_posts = load_json(os.path.join(base_dir, 'pending_ig_posts.json'), [])
    rate_limits = load_json(os.path.join(base_dir, 'rate_limits.json'), {})
    trending_keywords = load_json(os.path.join(base_dir, 'cache', 'trending_cache.json'), {})
    
    current_time = time.time()
    pinterest_session = load_json(os.path.join(base_dir, 'pinterest_session.json'), [])
    instagram_session = load_json(os.path.join(base_dir, 'instagram_session.json'), {})
    
    def check_pinterest_session(session_data):
        if not session_data:
            return {"status": "UNKNOWN", "expired_cookies": []}
        status = "ACTIVE"
        expired_cookies = []
        critical = {"_auth", "_pinterest_sess", "csrftoken"}
        if isinstance(session_data, list):
            for cookie in session_data:
                name = cookie.get('name', '')
                if name in critical and 'expires' in cookie and cookie['expires'] != -1:
                    if cookie['expires'] < current_time:
                        status = "EXPIRED"
                        expired_cookies.append(name)
        return {"status": status, "expired_cookies": expired_cookies}

    def check_instagram_session(session_data):
        if not session_data:
            return {"status": "UNKNOWN", "expired_cookies": []}
        if isinstance(session_data, dict) and 'authorization_data' in session_data:
            last_login = session_data.get('last_login') or 0
            if current_time - float(last_login) < 90 * 86400:
                return {"status": "ACTIVE", "expired_cookies": []}
            return {"status": "EXPIRED", "expired_cookies": ["authorization_data"]}
        return {"status": "UNKNOWN", "expired_cookies": []}

    session_health = {
        "pinterest": check_pinterest_session(pinterest_session),
        "instagram": check_instagram_session(instagram_session)
    }

    board_stats = defaultdict(int)
    # Ensure expected keys exist
    board_stats["Hot Deals India"] = 0
    board_stats["Shoes & Sneaker Deals"] = 0
    board_stats["Home & Kitchen"] = 0
    board_stats["Beauty & Skincare"] = 0
    
    all_pins = []
    if isinstance(pins_today, list): all_pins.extend(pins_today)
    if isinstance(pins_today_p2, list): all_pins.extend(pins_today_p2)
    if isinstance(posted_deals_index, dict):
        for k, v in posted_deals_index.items():
            if isinstance(v, dict):
                all_pins.append(v)
            elif isinstance(v, list):
                all_pins.extend(v)

    for p in all_pins:
        if 'board' in p:
            board_stats[clean_board_name(p['board'])] += 1

    p1_total = len(analytics)
    p1_fully_posted = sum(1 for a in analytics if a.get('status') in ('POSTED_ALL', 'LIVE', 'LIVE_NO_AFFILIATE'))
    p1_website_only = sum(1 for a in analytics if a.get('status') == 'WEBSITE_ONLY')
    p1_skipped = sum(1 for a in analytics if a.get('status') == 'SKIPPED')
    
    p1_live = sum(1 for a in analytics if a.get('status') in ('POSTED_ALL', 'WEBSITE_ONLY', 'LIVE', 'LIVE_NO_AFFILIATE'))
    if p1_skipped == 0 and p1_total > 0:
        p1_skipped = p1_total - p1_live
        
    p1_success_rate = (p1_live / p1_total * 100) if p1_total > 0 else 0.0
    
    skip_reasons = defaultdict(int)
    profit_tiers = defaultdict(int)
    
    timeline_counts = defaultdict(int)
    last_run_p1 = "1970-01-01T00:00:00"
    
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    
    for a in analytics:
        status = a.get('status')
        reason = a.get('reason', 'Unknown')
        tier = a.get('profit_tier', 'Unknown')
        ts_str = a.get('timestamp')
        
        if status == 'SKIPPED':
            if reason == 'No Real Photo': reason = 'No Real Photo (Image Fetch/Validation Failed)'
            skip_reasons[reason] += 1
            
        profit_tiers[tier] += 1
        
        if ts_str:
            if ts_str > last_run_p1:
                last_run_p1 = ts_str
            try:
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if dt >= fourteen_days_ago:
                    date_str = dt.strftime('%Y-%m-%d')
                    timeline_counts[date_str] += 1
            except:
                pass
                
    timeline = [{"date": k, "count": v} for k, v in sorted(timeline_counts.items())]
    
    # Pipeline 2 stats
    p2_total = len(deals)
    p2_pinned = sum(1 for d in deals if d.get('pinned', False))
    p2_not_pinned = p2_total - p2_pinned
    p2_pin_rate = (p2_pinned / p2_total * 100) if p2_total > 0 else 0.0
    
    platforms = defaultdict(int)
    last_run_p2 = "1970-01-01T00:00:00"
    
    for d in deals:
        url = d.get('product_url', '')
        plat = get_platform(url)
        platforms[plat] += 1
        ts_str = d.get('timestamp')
        if ts_str and ts_str > last_run_p2:
            last_run_p2 = ts_str
            
    recent_deals_full = sorted(deals, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
    recent_deals = []
    for d in recent_deals_full:
        recent_deals.append({
            "title": d.get('title', ''),
            "platform": get_platform(d.get('product_url', '')),
            "pinned": d.get('pinned', False),
            "timestamp": d.get('timestamp', '')
        })
        
    p2_total_pins = len(pins_today) if isinstance(pins_today, list) else 0
    
    # Generate schema
    state = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "session_health": session_health,
        "board_stats": dict(board_stats),
        "pipeline1": {
            "total_processed": p1_total,
            "live": p1_live,
            "fully_posted": p1_fully_posted,
            "website_only": p1_website_only,
            "skipped": p1_skipped,
            "success_rate_pct": round(p1_success_rate, 2),
            "last_run": last_run_p1 if last_run_p1 != "1970-01-01T00:00:00" else None,
            "skip_reasons": dict(skip_reasons),
            "profit_tiers": dict(profit_tiers),
            "timeline": timeline
        },
        "pipeline2": {
            "total_deals": p2_total,
            "pinned": p2_pinned,
            "not_pinned": p2_not_pinned,
            "pin_rate_pct": round(p2_pin_rate, 2),
            "total_pins": p2_total_pins,
            "last_run": last_run_p2 if last_run_p2 != "1970-01-01T00:00:00" else None,
            "platforms": dict(platforms),
            "recent_deals": recent_deals
        },
        "instagram_stats": {
            "posts_today": len(ig_posts_today) if isinstance(ig_posts_today, list) else 0,
            "pending_posts": len(pending_ig_posts) if isinstance(pending_ig_posts, list) else 0
        },
        "api_quotas": rate_limits,
        "trending_keywords": trending_keywords
    }
    
    docs_dir = os.path.join(base_dir, 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    out_path = os.path.join(docs_dir, 'dashboard_state.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
        
    print(f"Generated dashboard_state.json with Pipeline1 total: {p1_total}, Pipeline2 deals: {p2_total}")

if __name__ == '__main__':
    main()
