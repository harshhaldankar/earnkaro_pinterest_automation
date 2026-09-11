import json, re

with open('deals_data.json', 'r', encoding='utf-8') as f:
    raw = f.read()

# The file has TWO JSON arrays joined by a git merge conflict:
# [ ...HEAD version... ]
# =======
# [ ...remote version... ]
# >>>>>>> hash
# We need to extract both arrays and merge them into one

# Strategy: extract all JSON objects from the file using a robust approach
# First, clean all conflict markers and try to extract valid JSON objects

# Remove all conflict marker lines
lines = raw.split('\n')
clean_lines = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith('<<<<<<<') or stripped.startswith('>>>>>>>') or stripped == '=======':
        # Replace array open/close from the split points with commas
        clean_lines.append('')
    else:
        clean_lines.append(line)

clean = '\n'.join(clean_lines)

# The file now has two JSON arrays concatenated, possibly with ][ or ][ in the middle
# Replace ][ boundary (two arrays joined) with a comma
clean = re.sub(r'\]\s*\[', ',', clean)

# Try to parse
try:
    data = json.loads(clean)
    print(f'Parsed successfully! Total deals: {len(data)}')
except json.JSONDecodeError as e:
    print(f'Still failing: {e}')
    # More aggressive: extract all objects using regex
    objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', clean, re.DOTALL)
    data = []
    for obj_str in objects:
        try:
            obj = json.loads(obj_str)
            if 'title' in obj:
                data.append(obj)
        except:
            pass
    print(f'Extracted via regex: {len(data)} deals')

# Deduplicate by title
seen_titles = set()
unique_deals = []
for d in data:
    t = d.get('title', '')
    if t and t not in seen_titles:
        seen_titles.add(t)
        unique_deals.append(d)

print(f'After dedup: {len(unique_deals)} unique deals')

# Filter out bad category deals and those with no image
bad_patterns = [
    '/shop/', 'hair-care', 'personal-care',
    'sort=discount', 'f=Gender', 'f=Brand',
    'myntra.com/men', 'myntra.com/women', 'myntra.com/kids', 'myntra.com/clothing',
    'myntra.com/converse', 'myntra.com/myntra', 'myntra.com/shop',
    'ajio.com/s/', '/s/min', 'itm_source=banner',
    'linkredirect.in', '/category', '/collections'
]

good_deals = []
removed = []
for d in unique_deals:
    url = (d.get('product_url', '') + d.get('affiliate_link', '')).lower()
    title = d.get('title', '')
    # reject empty image
    if not d.get('image_path'):
        removed.append(('NO_IMAGE', title))
        continue
    # reject category deals
    is_bad = any(pat in url for pat in bad_patterns)
    if is_bad:
        removed.append(('CATEGORY', title))
    else:
        good_deals.append(d)

print(f'Removed {len(removed)} bad deals:')
for reason, title in removed[:15]:
    print(f'  [{reason}] {title[:60]}')

print(f'Final clean deals: {len(good_deals)}')

with open('deals_data.json', 'w', encoding='utf-8') as f:
    json.dump(good_deals, f, indent=2, ensure_ascii=False)

print('SUCCESS - deals_data.json is now clean and valid JSON!')
