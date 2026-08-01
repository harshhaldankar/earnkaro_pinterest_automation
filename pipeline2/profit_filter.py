import re
from pipeline2.trend_matcher import ProductDeal

def estimate_profit_tier(title: str, url: str) -> str:
    """
    Analyzes the deal text and URL to estimate profit margins.
    Reuses P1 logic but adjusted for P2 context.
    """
    combined = f" {title} {url} ".lower()
    
    # 0% - 2% Profit Blacklist
    blacklist = r"\b(smartphone|mobile phone|iphone|galaxy s\d+|galaxy fold|galaxy flip|redmi note|iqoo|motorola razr|oneplus|poco|gift card|gold coin|silver coin|furniture|sofa|bed|grocery|macbook|ipad|airpods|airpod|credit card|debit card|loan|insurance|mutual fund|sim|recharge|broadband|wifi|medicine)\b"
    if re.search(blacklist, combined):
        return "Low"
        
    # >10% VIP Whitelist (Ultra-High)
    vip_list = r"\b(derma co|ounce organics|neuro|jivisa|adobe|n4n|nippon paint|nroute|indus astro|koparo|the moms co|ageeasy|nutriburst|strch|ramam|brillare|kerala ayurveda|house of koala|neuherbs|mcaffeine|beardo|plum)\b"
    if re.search(vip_list, combined):
        return "Ultra-High"
        
    # 5% - 10% High Profit
    high_profit = r"\b(myntra|ajio|nykaa|mamaearth|plumgoodness|buywow|jeans|shirt|t-shirt|shoes|sneakers|watch|dress|kurta|saree|makeup|skincare|perfume|lipstick|beauty|kurti|footwear|heels)\b"
    if re.search(high_profit, combined):
        return "High"
        
    # 3.5% - 5% Medium Profit
    mid_profit = r"\b(kitchen|appliance|refrigerator|washing machine|tv|television|laptop|earbuds|headphones|speaker|monitor|smartwatch|cookware|home decor)\b"
    if re.search(mid_profit, combined):
        return "Medium"
        
    return "Medium" # Default if not low

def filter_by_profit(deals: list[ProductDeal]) -> list[ProductDeal]:
    """
    Filters out Low profit deals and enforces >30% discount on Medium tier.
    Assigns the calculated tier to the deal object.
    """
    filtered = []
    print(f"[ProfitFilter] Evaluating {len(deals)} deals...")
    
    for deal in deals:
        tier = estimate_profit_tier(deal.title, deal.product_url)
        deal.profit_tier = tier
        
        if tier == "Low":
            print(f"  [REJECT] Low profit tier (0-2%): {deal.title}")
            continue
            
        if tier == "Medium":
            if deal.discount_percent <= 30:
                print(f"  [REJECT] Medium tier but discount <= 30% ({deal.discount_percent}%): {deal.title}")
                continue
                
        # Deal is acceptable
        filtered.append(deal)
        
    print(f"[ProfitFilter] Kept {len(filtered)} profitable deals.")
    return filtered
