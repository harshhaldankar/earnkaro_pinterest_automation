import json
import os
import re
from collections import Counter

def safe_load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Simple regex to remove git merge conflict markers keeping HEAD
    text = re.sub(r'<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> .*?\n', r'\1\n', text, flags=re.DOTALL)
    # Also handle in case no trailing newline on >>>>>>> 
    text = re.sub(r'<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>>.*', r'\1\n', text, flags=re.DOTALL)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse {filepath}: {e}")
        # Return partial or empty on failure
        return []

def main():
    analytics_file = 'analytics.json'
    deals_file = 'deals_data.json'
    pins_file = 'pins_today.json'
    out_file = 'docs/dashboard_state.json'
    
    analytics = safe_load_json(analytics_file)
    deals = safe_load_json(deals_file)
    pins = safe_load_json(pins_file)
            
    pipeline1_live = sum(1 for item in analytics if item.get('status') == 'LIVE')
    pipeline1_skipped = sum(1 for item in analytics if item.get('status') == 'SKIPPED')
    
    dashboard_state = {
        'pipeline1': {
            'totalProcessed': pipeline1_live + pipeline1_skipped,
            'live': pipeline1_live,
            'skipped': pipeline1_skipped,
            'status': 'active' if pipeline1_live + pipeline1_skipped > 0 else 'offline'
        },
        'pipeline2': {
            'activeDeals': len(deals),
            'pinterestPins': len(pins),
            'targetPins': 1000
        }
    }
    
    os.makedirs('docs', exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(dashboard_state, f, indent=4)
        
    print(f"Dashboard state saved to {out_file}")

if __name__ == "__main__":
    main()
