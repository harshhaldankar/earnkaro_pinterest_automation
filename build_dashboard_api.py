import json
import os
import re
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

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    analytics = load_json(os.path.join(base_dir, 'analytics.json'), [])
    deals = load_json(os.path.join(base_dir, 'deals_data.json'), [])
    pins_today = load_json(os.path.join(base_dir, 'pins_today.json'), [])
    
    # Pipeline 1 stats
    p1_total = len(analytics)
    p1_live = sum(1 for a in analytics if a.get('status') == 'LIVE')
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
                # Assuming ISO format like 2026-08-16T12:00:00
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
        "pipeline1": {
            "total_processed": p1_total,
            "live": p1_live,
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
        }
    }
    
    docs_dir = os.path.join(base_dir, 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    out_path = os.path.join(docs_dir, 'dashboard_state.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
        
    print(f"Generated dashboard_state.json with Pipeline1 total: {p1_total}, Pipeline2 deals: {p2_total}")
    with open(out_path, 'r', encoding='utf-8') as f:
        print(f.read())
if __name__ == '__main__':
    main()
