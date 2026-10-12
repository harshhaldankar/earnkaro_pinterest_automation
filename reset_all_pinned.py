import json

with open('deals_data.json', 'r', encoding='utf-8') as f:
    deals = json.load(f)

reset_count = 0
for deal in deals:
    if deal.get('pinned', False):
        deal['pinned'] = False
        reset_count += 1

with open('deals_data.json', 'w', encoding='utf-8') as f:
    json.dump(deals, f, ensure_ascii=False, indent=2)

print('Reset ' + str(reset_count) + ' deals to pinned=False')
print('Total deals: ' + str(len(deals)))
