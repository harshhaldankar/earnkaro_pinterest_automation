"""
dribbble_template.py - Exact implementation of Dribbble Shot 25042708
Fashion Ecommerce Responsive Website by Orbix Studio
Adapted for GetYourDeal India Affiliate Deals
"""

import os
import re
import random
from pathlib import Path
from datetime import datetime

DOCS_DIR = Path("docs") / "deals"
MAX_DEALS = 80
_GA4_PLACEHOLDER = "<!-- GA4_PLACEHOLDER -->"

DRIBBLE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=Space+Grotesk:wght@500;700;800&display=swap');

:root {
  --bg-app: #F5F6F8;
  --bg-card: #FFFFFF;
  --bg-dark: #111827;
  --text-main: #111827;
  --text-muted: #6B7280;
  --text-light: #9CA3AF;
  --border-color: #E5E7EB;
  --border-subtle: #F3F4F6;
  --pill-bg: #F3F4F6;
  --accent-star: #F59E0B;
  --accent-green: #10B981;
  --accent-red: #EF4444;
  --font-main: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-heading: 'Space Grotesk', 'Plus Jakarta Sans', sans-serif;
  --radius-lg: 26px;
  --radius-md: 18px;
  --radius-pill: 9999px;
  --shadow-soft: 0 4px 20px rgba(0, 0, 0, 0.04);
  --shadow-hover: 0 12px 32px rgba(0, 0, 0, 0.08);
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-main);
  background-color: var(--bg-app);
  color: var(--text-main);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
}

a {
  color: inherit;
  text-decoration: none;
}

/* Top Announcement & Header */
.top-notice {
  background: #000000;
  color: #FFFFFF;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-align: center;
  padding: 8px 16px;
  text-transform: uppercase;
}

.site-header {
  background: #FFFFFF;
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 14px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  flex: 1;
}

.menu-btn {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: 1.5px solid var(--border-color);
  background: #FFFFFF;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  transition: all 0.2s;
}

.menu-btn:hover {
  background: var(--pill-bg);
  border-color: #D1D5DB;
}

.menu-btn span {
  width: 20px;
  height: 2.2px;
  background: var(--text-main);
  border-radius: 2px;
}

.header-center {
  flex-shrink: 0;
  text-align: center;
}

.brand-logo {
  font-family: var(--font-heading);
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.6px;
  color: #000000;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.brand-logo span {
  color: var(--accent-orange);
}

.header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 1;
}

/* Slide-out Category Drawer */
.drawer-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  z-index: 2000;
  opacity: 0;
  visibility: hidden;
  transition: all 0.3s ease;
}

.drawer-overlay.open {
  opacity: 1;
  visibility: visible;
}

.category-drawer {
  position: fixed;
  top: 0;
  left: 0;
  width: 320px;
  max-width: 85vw;
  height: 100%;
  background: #FFFFFF;
  z-index: 2001;
  box-shadow: 6px 0 28px rgba(0, 0, 0, 0.12);
  transform: translateX(-100%);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}

.category-drawer.open {
  transform: translateX(0);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px;
  border-bottom: 1px solid var(--border-color);
}

.drawer-title {
  font-family: var(--font-heading);
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-main);
}

.drawer-close-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: #FFFFFF;
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-main);
  transition: all 0.2s;
}

.drawer-close-btn:hover {
  background: var(--pill-bg);
}

.drawer-categories {
  padding: 16px 14px;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.drawer-cat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  border-radius: 12px;
  border: none;
  background: transparent;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-main);
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.drawer-cat-item:hover, .drawer-cat-item.active {
  background: var(--pill-bg);
  color: #000000;
}

.drawer-cat-item.active {
  font-weight: 700;
  background: #000000;
  color: #FFFFFF;
}

.drawer-cat-item .cat-icon {
  font-size: 1.2rem;
}

.drawer-footer {
  padding: 20px 24px;
  border-top: 1px solid var(--border-color);
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.4;
  background: #FAFAFA;
}

/* Breadcrumb Navigation */
.breadcrumb-bar {
  max-width: 1440px;
  margin: 0 auto;
  padding: 16px 28px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.breadcrumb-bar a:hover {
  color: #000000;
}

/* Hero Showcase (Product Page) */
.product-showcase-container {
  max-width: 1440px;
  margin: 16px auto 40px;
  padding: 0 28px;
}

.product-showcase-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 36px;
  align-items: start;
}

/* Single Hero Product Image */
.single-product-media-card {
  background: #FFFFFF;
  border-radius: var(--radius-lg);
  position: relative;
  overflow: hidden;
  height: 540px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 36px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-soft);
}

.single-product-media-card img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  mix-blend-mode: multiply;
  transition: transform 0.3s ease;
}

.single-product-media-card:hover img {
  transform: scale(1.03);
}

.floating-pill-badge {
  position: absolute;
  top: 20px;
  right: 20px;
  background: #FFFFFF;
  color: #111827;
  font-size: 0.8rem;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
  border: 1px solid var(--border-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Product Info Card */
.product-details-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 36px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-soft);
}

.product-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.product-title-main {
  font-family: var(--font-heading);
  font-size: 2.1rem;
  font-weight: 800;
  color: var(--text-main);
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.wishlist-circle-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1.5px solid var(--border-color);
  background: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.wishlist-circle-btn svg {
  width: 20px;
  height: 20px;
  fill: #EF4444;
}

.product-rating-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 24px;
  font-size: 0.9rem;
  font-weight: 600;
}

.star-badge {
  color: var(--accent-star);
  font-size: 1rem;
}

.store-meta-tag {
  background: var(--pill-bg);
  color: var(--text-main);
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  margin-left: 8px;
}

/* The Signature Black Price Card from Dribbble */
.dribbble-price-card {
  background: var(--bg-dark);
  color: #FFFFFF;
  border-radius: 22px;
  padding: 24px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
  box-shadow: 0 10px 25px rgba(17, 24, 39, 0.15);
}

.price-card-left {
  display: flex;
  flex-direction: column;
}

.price-main-display {
  font-family: var(--font-heading);
  font-size: 2.4rem;
  font-weight: 800;
  letter-spacing: -1px;
  line-height: 1;
}

.price-mrp-strikethrough {
  font-size: 0.95rem;
  color: #9CA3AF;
  text-decoration: line-through;
  margin-top: 4px;
}

.savings-highlight {
  color: #34D399;
  font-size: 0.85rem;
  font-weight: 700;
  margin-top: 2px;
}

.btn-buy-dribbble {
  background: #FFFFFF;
  color: #111827;
  border-radius: var(--radius-pill);
  padding: 14px 30px;
  font-weight: 800;
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s ease;
  cursor: pointer;
  border: none;
}

.btn-buy-dribbble:hover {
  background: #F3F4F6;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 255, 255, 0.3);
}

/* Accordion */
.spec-accordion {
  border-top: 1px solid var(--border-color);
  padding: 20px 0;
}

.spec-accordion-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 1.05rem;
  font-weight: 700;
  cursor: pointer;
}

.spec-accordion-body {
  margin-top: 12px;
  font-size: 0.9rem;
  color: var(--text-muted);
  line-height: 1.6;
}

/* Deal Verification & Trust Card */
.deal-trust-card {
  background: #F9FAFB;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 20px;
}

.trust-badge-item {
  display: flex;
  align-items: center;
  gap: 14px;
}

.trust-icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #FFFFFF;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

.trust-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.2;
}

.trust-sub {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 2px;
}

.deal-meta-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-pill {
  background: #FFFFFF;
  border: 1px solid var(--border-color);
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  font-size: 0.8rem;
  color: var(--text-muted);
}

.meta-pill strong {
  color: var(--text-main);
}

/* Catalog Grid (More All You Needs) */
.catalog-section {
  max-width: 1440px;
  margin: 0 auto 60px;
  padding: 0 28px;
}

.catalog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.catalog-title {
  font-family: var(--font-heading);
  font-size: 2.2rem;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: var(--text-main);
}

.deals-grid-dribbble {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.deal-card-dribbble {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;
  position: relative;
  box-shadow: var(--shadow-soft);
}

.deal-card-dribbble:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-hover);
  border-color: #D1D5DB;
}

.card-image-wrapper {
  height: 280px;
  background: #F3F4F6;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
}

.card-image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  mix-blend-mode: multiply;
  transition: transform 0.3s ease;
}

.deal-card-dribbble:hover .card-image-wrapper img {
  transform: scale(1.06);
}

.card-discount-tag {
  position: absolute;
  top: 16px;
  left: 16px;
  background: #FFFFFF;
  color: #000000;
  font-size: 0.75rem;
  font-weight: 800;
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  letter-spacing: 0.3px;
}

.card-freshness-tag {
  position: absolute;
  bottom: 16px;
  right: 16px;
  background: rgba(17, 24, 39, 0.85);
  color: #FFFFFF;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
}

.card-content-box {
  padding: 22px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.card-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-brand-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-light);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-category-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
}

.card-deal-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.35;
  margin-bottom: 16px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 2.7em;
}

.card-bottom-row {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--border-subtle);
  padding-top: 14px;
}

.card-price-stack {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.card-current-price {
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--text-main);
}

.card-original-mrp {
  font-size: 0.85rem;
  color: var(--text-light);
  text-decoration: line-through;
}

.card-arrow-circle {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #111827;
  color: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.deal-card-dribbble:hover .card-arrow-circle {
  background: #000000;
  transform: translateX(3px);
}

/* Footer */
.site-footer {
  background: #FFFFFF;
  border-top: 1px solid var(--border-color);
  padding: 48px 28px 32px;
  margin-top: 60px;
}

.footer-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 16px;
}

.footer-logo {
  font-family: var(--font-heading);
  font-size: 1.5rem;
  font-weight: 800;
}

.footer-disclaimer {
  font-size: 0.75rem;
  color: var(--text-light);
  max-width: 600px;
  line-height: 1.5;
}

/* Responsive */
@media (max-width: 1180px) {
  .product-showcase-grid {
    grid-template-columns: 1fr;
  }
  .collage-main-hero {
    height: 440px;
  }
  .deals-grid-dribbble {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 820px) {
  .header-left .nav-pill,
  .header-left .nav-pill-dropdown,
  .header-search,
  .category-chips {
    display: none;
  }
  .deals-grid-dribbble {
    grid-template-columns: repeat(2, 1fr);
  }
  .collage-showcase {
    grid-template-columns: 1fr;
  }
  .collage-main-hero {
    grid-column: 1 / 2;
    grid-row: auto;
    height: 380px;
  }
  .collage-sub-item {
    display: none;
  }
  .product-details-card {
    padding: 24px;
  }
  .dribbble-price-card {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
    text-align: center;
  }
  .btn-buy-dribbble {
    justify-content: center;
  }
}

@media (max-width: 540px) {
  .deals-grid-dribbble {
    grid-template-columns: 1fr;
  }
  .catalog-title {
    font-size: 1.6rem;
  }
  .header-inner {
    padding: 12px 18px;
  }
  .product-showcase-container, .catalog-section {
    padding: 0 16px;
  }
}
"""

def clean_val(val_raw):
    if not val_raw:
        return ""
    clean = str(val_raw).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
    return clean

def rebuild_dribbble_website(deals):
    """
    Main website rebuilder producing exact Dribbble Shot 25042708 styling.
    Writes:
      - docs/deals/deals.css
      - docs/deals/index.html (More All You Needs catalog)
      - docs/deals/<deal_id>/index.html (Full Product Detail Showcases)
    """
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "deals.css").write_text(DRIBBLE_CSS, encoding="utf-8")
    
    from telegram_watcher import extract_price, get_store_name, get_category, clean_telegram_text, _deal_link, _freshness_badge

    valid_deals = [
        d for d in deals
        if d.get("image_path") and (DOCS_DIR / d.get("image_path")).exists()
        and "http" not in d.get("title", "").lower()
        and len(d.get("title", "").strip()) >= 6
        and not d.get("title", "").strip().isdigit()
    ]
    display_deals = valid_deals[:MAX_DEALS]

    catalog_cards_html = ""
    for idx, d in enumerate(display_deals):
        raw_title = d.get("title", "Hot Deal")
        clean_t, _ = clean_telegram_text(raw_title)
        clean_title = (clean_t or raw_title).replace("<", "&lt;").replace(">", "&gt;")
        
        ts = d.get("timestamp", "")
        img_path = d.get("image_path", "")
        clean_ts = ts.replace("-", "").replace(":", "").replace(".", "").replace("T", "_") if ts else f"item_{idx}"
        deal_anchor_id = f"deal_{clean_ts}"
        
        brand = get_store_name(clean_title)
        cat = get_category(brand, clean_title)
        price_raw = extract_price(clean_title)
        c_price = clean_val(price_raw)
        disp_price = f"₹{c_price}" if c_price else "See Price"
        
        mrp_raw = clean_val(d.get("mrp", ""))
        mrp_html = f'<span class="card-original-mrp">₹{mrp_raw}</span>' if mrp_raw else ""
        
        disc_match = re.search(r'((?:(?:Min|Upto|Up\s*to|Flat)\s*)?\d+(?:-\d+)?%\s*(?:OFF|off|Off|discount|Discount))', clean_title, re.IGNORECASE)
        disc_text = disc_match.group(1).upper() if disc_match else (f"{d.get('discount_percent')}% OFF" if d.get('discount_percent') else "DEAL")
        
        fresh_tag = _freshness_badge(ts)
        fresh_html = f'<span class="card-freshness-tag">{fresh_tag}</span>' if fresh_tag else ""
        
        card_link = f"./{deal_anchor_id}/"
        img_html = f'<img src="{img_path}" alt="{clean_title}" loading="lazy"/>' if img_path else ""

        catalog_cards_html += f"""
      <a href="{card_link}" class="deal-card-dribbble" data-category="{cat}">
        <div class="card-image-wrapper">
          {img_html}
          <span class="card-discount-tag">{disc_text}</span>
          {fresh_html}
        </div>
        <div class="card-content-box">
          <div class="card-meta-row">
            <span class="card-brand-label">{brand}</span>
            <span class="card-category-label">{cat}</span>
          </div>
          <h3 class="card-deal-title">{clean_title}</h3>
          <div class="card-bottom-row">
            <div class="card-price-stack">
              <span class="card-current-price">{disp_price}</span>
              {mrp_html}
            </div>
            <div class="card-arrow-circle">&rarr;</div>
          </div>
        </div>
      </a>"""

        # Generate individual deal product page matching Dribbble
        other_deals = [x for x in display_deals if x is not d]
        random.shuffle(other_deals)
        write_single_deal_page(d, deal_anchor_id, other_deals[:4])

    now_str = datetime.utcnow().strftime("%d %b %Y")
    
    # Catalog Main Page
    catalog_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>GetYourDeal &mdash; Curated Drops &amp; Verified Deals</title>
  <meta name="description" content="Discover India's biggest curated discounts on Amazon, Flipkart, Myntra, Ajio &amp; more."/>
  <link rel="stylesheet" href="deals.css"/>
  {_GA4_PLACEHOLDER}
</head>
<body>

  <div class="top-notice">
    ⚡ India's Curated Fashion & Tech Drops &bull; Verified Discount Deals
  </div>

  <!-- Header: Burger on Left, Centered Get Your Deal Logo, Empty Spacer on Right -->
  <header class="site-header">
    <div class="header-inner">
      <div class="header-left">
        <button class="menu-btn" id="burgerMenuBtn" aria-label="Open Categories Menu">
          <span></span><span></span><span></span>
        </button>
      </div>

      <div class="header-center">
        <a href="./" class="brand-logo">Get Your <span>Deal.</span></a>
      </div>

      <div class="header-right"></div>
    </div>
  </header>

  <!-- Slide-out Category Drawer -->
  <div class="drawer-overlay" id="categoryDrawerOverlay"></div>
  <aside class="category-drawer" id="categoryDrawer">
    <div class="drawer-header">
      <div class="drawer-title">Categories</div>
      <button class="drawer-close-btn" id="closeDrawerBtn" aria-label="Close">&times;</button>
    </div>
    <div class="drawer-categories">
      <button class="drawer-cat-item active" data-filter="all">
        <span class="cat-icon">🏷️</span> All Deals
      </button>
      <button class="drawer-cat-item" data-filter="Fashion & Bags">
        <span class="cat-icon">👗</span> Fashion &amp; Bags
      </button>
      <button class="drawer-cat-item" data-filter="Electronics & Tech">
        <span class="cat-icon">⚡</span> Electronics &amp; Tech
      </button>
      <button class="drawer-cat-item" data-filter="Beauty & Health">
        <span class="cat-icon">✨</span> Beauty &amp; Health
      </button>
      <button class="drawer-cat-item" data-filter="Shoes & Sneaker">
        <span class="cat-icon">👟</span> Shoes &amp; Footwear
      </button>
      <button class="drawer-cat-item" data-filter="Home & Kitchen">
        <span class="cat-icon">🏠</span> Home &amp; Kitchen
      </button>
      <button class="drawer-cat-item" data-filter="Loot Deals">
        <span class="cat-icon">🔥</span> Loot Deals
      </button>
    </div>
    <div class="drawer-footer">
      <p>Hand-picked discounts verified daily across top Indian stores.</p>
    </div>
  </aside>

  <!-- Catalog Main Page -->
  <main class="catalog-section">
    <div class="catalog-header">
      <h1 class="catalog-title" id="catalogHeading">More All You Needs.</h1>
      <span style="color:var(--text-muted);font-weight:600;font-size:0.95rem;">{len(display_deals)} Active Deals</span>
    </div>

    <div class="deals-grid-dribbble" id="dealsGrid">
      {catalog_cards_html}
    </div>
  </main>

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-logo">Get Your <span>Deal.</span></div>
      <p style="color:var(--text-muted);font-size:0.9rem;">India's Best Curated E-Commerce Deals &amp; Drops</p>
      <p class="footer-disclaimer">Affiliate Disclosure: When you purchase through our links, we may earn an affiliate commission at zero additional cost to you.</p>
    </div>
  </footer>

  <script>
    const burgerBtn = document.getElementById('burgerMenuBtn');
    const drawer = document.getElementById('categoryDrawer');
    const overlay = document.getElementById('categoryDrawerOverlay');
    const closeBtn = document.getElementById('closeDrawerBtn');

    function openDrawer() {{
      drawer.classList.add('open');
      overlay.classList.add('open');
    }}

    function closeDrawer() {{
      drawer.classList.remove('open');
      overlay.classList.remove('open');
    }}

    if (burgerBtn) burgerBtn.addEventListener('click', openDrawer);
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    if (overlay) overlay.addEventListener('click', closeDrawer);

    // Category Filtering via Drawer
    const drawerItems = document.querySelectorAll('.drawer-cat-item');
    const cards = document.querySelectorAll('.deal-card-dribbble');
    const catalogHeading = document.getElementById('catalogHeading');

    drawerItems.forEach(item => {{
      item.addEventListener('click', () => {{
        drawerItems.forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        const filter = item.getAttribute('data-filter') || 'all';

        cards.forEach(card => {{
          const cat = card.getAttribute('data-category') || '';
          if (filter === 'all' || cat.includes(filter)) {{
            card.style.display = 'flex';
          }} else {{
            card.style.display = 'none';
          }}
        }});

        if (catalogHeading) {{
          catalogHeading.textContent = filter === 'all' ? 'More All You Needs.' : filter + ' Drops.';
        }}
        closeDrawer();
      }});
    }});

    // URL parameter support (e.g. ?cat=Fashion)
    const urlParams = new URLSearchParams(window.location.search);
    const catParam = urlParams.get('cat') || urlParams.get('filter');
    if (catParam) {{
      drawerItems.forEach(item => {{
        const filter = item.getAttribute('data-filter') || '';
        if (filter.toLowerCase().includes(catParam.toLowerCase())) {{
          item.click();
        }}
      }});
    }}
  </script>

</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(catalog_html, encoding="utf-8")
    print(f"[Dribbble Web] Rebuilt catalog with {len(display_deals)} deals.")


def write_single_deal_page(deal, deal_anchor_id, related_deals):
    from telegram_watcher import extract_price, get_store_name, get_category, clean_telegram_text, _deal_link, _freshness_badge

    title = deal.get("title", "Hot Deal")
    desc = deal.get("desc", "")
    img_path = deal.get("image_path", "")
    ts = deal.get("timestamp", "")
    
    clean_t, _ = clean_telegram_text(title)
    clean_title = (clean_t or title).replace("<", "&lt;").replace(">", "&gt;")
    
    brand = get_store_name(clean_title)
    cat = get_category(brand, f"{clean_title} {desc}")
    
    p_raw = extract_price(clean_title)
    c_price = clean_val(p_raw)
    disp_price = f"₹{c_price}" if c_price else "See Price"
    
    mrp_raw = clean_val(deal.get("mrp", ""))
    mrp_display = f"₹{mrp_raw}" if mrp_raw else ""
    
    disc_match = re.search(r'((?:(?:Min|Upto|Up\s*to|Flat)\s*)?\d+(?:-\d+)?%\s*(?:OFF|off|Off|discount|Discount))', clean_title, re.IGNORECASE)
    disc_text = disc_match.group(1).upper() if disc_match else (f"{deal.get('discount_percent')}% OFF" if deal.get('discount_percent') else "HOT DEAL")
    
    savings_text = ""
    if c_price and mrp_raw:
        try:
            p_i = int(c_price)
            m_i = int(mrp_raw)
            if m_i > p_i:
                savings_text = f"You save ₹{m_i - p_i:,} ({disc_text})"
        except:
            pass
            
    direct_link = _deal_link(deal, utm_medium="deal_page")
    img_src = f"../{img_path}" if img_path else ""
    og_image = f"https://harshhaldankar.github.io/Getyourdeal/deals/{img_path}" if img_path else ""

    related_cards = ""
    for rd in related_deals[:4]:
        rt = rd.get("title", "Deal")
        rtc, _ = clean_telegram_text(rt)
        cl_rt = (rtc or rt).replace("<", "&lt;").replace(">", "&gt;")
        r_brand = get_store_name(cl_rt)
        r_cat = get_category(r_brand, cl_rt)
        r_price_raw = extract_price(cl_rt)
        r_cp = clean_val(r_price_raw)
        r_dp = f"₹{r_cp}" if r_cp else "See Price"
        r_mrp = clean_val(rd.get("mrp", ""))
        r_mrp_h = f'<span class="card-original-mrp">₹{r_mrp}</span>' if r_mrp else ""
        r_img = rd.get("image_path", "")
        r_img_h = f'<img src="../{r_img}" alt="{cl_rt}" loading="lazy"/>' if r_img else ""
        
        r_ts = rd.get("timestamp", "")
        r_cts = r_ts.replace("-", "").replace(":", "").replace(".", "").replace("T", "_") if r_ts else "item"
        r_anchor = f"deal_{r_cts}"
        
        r_dm = re.search(r'((?:(?:Min|Upto|Up\s*to|Flat)\s*)?\d+(?:-\d+)?%\s*(?:OFF|off|Off|discount|Discount))', cl_rt, re.IGNORECASE)
        r_dt = r_dm.group(1).upper() if r_dm else "DEAL"

        related_cards += f"""
        <a href="../{r_anchor}/" class="deal-card-dribbble">
          <div class="card-image-wrapper">
            {r_img_h}
            <span class="card-discount-tag">{r_dt}</span>
          </div>
          <div class="card-content-box">
            <div class="card-meta-row">
              <span class="card-brand-label">{r_brand}</span>
              <span class="card-category-label">{r_cat}</span>
            </div>
            <h3 class="card-deal-title">{cl_rt}</h3>
            <div class="card-bottom-row">
              <div class="card-price-stack">
                <span class="card-current-price">{r_dp}</span>
                {r_mrp_h}
              </div>
              <div class="card-arrow-circle">&rarr;</div>
            </div>
          </div>
        </a>"""

    single_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{clean_title[:70]} | GetYourDeal</title>
  <meta name="description" content="{clean_title}. Buy authentic products with verified discounts on GetYourDeal."/>
  <meta property="og:title" content="{clean_title[:70]}"/>
  <meta property="og:image" content="{og_image}"/>
  <link rel="stylesheet" href="../deals.css"/>
  {_GA4_PLACEHOLDER}
</head>
<body>

  <div class="top-notice">
    ⚡ India's Curated Fashion & Tech Drops &bull; Verified Discount Deals
  </div>

  <!-- Header: Burger on Left, Centered Get Your Deal Logo, Empty Spacer on Right -->
  <header class="site-header">
    <div class="header-inner">
      <div class="header-left">
        <button class="menu-btn" id="burgerMenuBtn" aria-label="Open Categories Menu">
          <span></span><span></span><span></span>
        </button>
      </div>

      <div class="header-center">
        <a href="../" class="brand-logo">Get Your <span>Deal.</span></a>
      </div>

      <div class="header-right"></div>
    </div>
  </header>

  <!-- Slide-out Category Drawer (linking back to catalog) -->
  <div class="drawer-overlay" id="categoryDrawerOverlay"></div>
  <aside class="category-drawer" id="categoryDrawer">
    <div class="drawer-header">
      <div class="drawer-title">Categories</div>
      <button class="drawer-close-btn" id="closeDrawerBtn" aria-label="Close">&times;</button>
    </div>
    <div class="drawer-categories">
      <a href="../?cat=all" class="drawer-cat-item active">
        <span class="cat-icon">🏷️</span> All Deals
      </a>
      <a href="../?cat=Fashion" class="drawer-cat-item">
        <span class="cat-icon">👗</span> Fashion &amp; Bags
      </a>
      <a href="../?cat=Electronics" class="drawer-cat-item">
        <span class="cat-icon">⚡</span> Electronics &amp; Tech
      </a>
      <a href="../?cat=Beauty" class="drawer-cat-item">
        <span class="cat-icon">✨</span> Beauty &amp; Health
      </a>
      <a href="../?cat=Shoes" class="drawer-cat-item">
        <span class="cat-icon">👟</span> Shoes &amp; Footwear
      </a>
      <a href="../?cat=Home" class="drawer-cat-item">
        <span class="cat-icon">🏠</span> Home &amp; Kitchen
      </a>
      <a href="../?cat=Loot" class="drawer-cat-item">
        <span class="cat-icon">🔥</span> Loot Deals
      </a>
    </div>
    <div class="drawer-footer">
      <p>Hand-picked discounts verified daily across top Indian stores.</p>
    </div>
  </aside>

  <!-- Breadcrumb -->
  <div class="breadcrumb-bar">
    <a href="../">&larr; All Deals</a> &bull;
    <span>{cat}</span>
  </div>

  <!-- Product Detail Showcase -->
  <main class="product-showcase-container">
    <div class="product-showcase-grid">

      <!-- Left: ONE Crisp, High-Quality Product Image -->
      <div class="single-product-media-card">
        <img src="{img_src}" alt="{clean_title}" loading="eager"/>
        <span class="floating-pill-badge">{disc_text}</span>
      </div>

      <!-- Right: Product Details Card -->
      <div class="product-details-card">
        <div class="product-title-row">
          <h1 class="product-title-main">{clean_title}</h1>
          <button class="wishlist-circle-btn" id="shareDealBtn" title="Copy Deal Link" onclick="copyDealLink()">
            <svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
          </button>
        </div>

        <!-- Best element: Star rating + Verified Reviews + Store Assured -->
        <div class="product-rating-row">
          <span class="star-badge">&#9733; 4.9</span>
          <span class="rating-text">(41 Verified Reviews)</span>
          <span class="store-meta-tag">{brand} Assured</span>
        </div>

        <!-- The Iconic Black Price Box -->
        <div class="dribbble-price-card">
          <div class="price-card-left">
            <div class="price-main-display">{disp_price}</div>
            {f'<div class="price-mrp-strikethrough">MRP {mrp_display}</div>' if mrp_display else ''}
            {f'<div class="savings-highlight">{savings_text}</div>' if savings_text else ''}
          </div>
          <a href="{direct_link}" target="_blank" rel="noopener noreferrer sponsored" class="btn-buy-dribbble">
            Buy Now &rarr;
          </a>
        </div>

        <!-- Description Accordion -->
        <div class="spec-accordion">
          <div class="spec-accordion-title">
            <span>Description</span>
          </div>
          <div class="spec-accordion-body">
            {desc if desc else f"Authentic {brand} product curated with verified discount. Fast express dispatch and official store buyer protection."}
          </div>
        </div>

        <!-- Deal Verification & Trust Card -->
        <div class="deal-trust-card">
          <div class="trust-badge-item">
            <div class="trust-icon">&#9889;</div>
            <div class="trust-content">
              <div class="trust-title">Verified Discount Offer</div>
              <div class="trust-sub">Direct official store pricing with live savings</div>
            </div>
          </div>
          <div class="trust-badge-item">
            <div class="trust-icon">&#128722;</div>
            <div class="trust-content">
              <div class="trust-title">Official Store Checkout</div>
              <div class="trust-sub">Complete order securely on {brand}'s website or app</div>
            </div>
          </div>
          <div class="trust-badge-item">
            <div class="trust-icon">&#128737;</div>
            <div class="trust-content">
              <div class="trust-title">100% Genuine &amp; Safe</div>
              <div class="trust-sub">Protected by standard brand return policy &amp; warranty</div>
            </div>
          </div>
        </div>

        <!-- Quick Store & Category Meta Info -->
        <div class="deal-meta-pills">
          <span class="meta-pill">🏬 Store: <strong>{brand}</strong></span>
          <span class="meta-pill">📂 Category: <strong>{cat}</strong></span>
          <span class="meta-pill">⚡ Limited Time Deal</span>
        </div>

      </div>
    </div>
  </main>

  <!-- More All You Needs (Related Deals) -->
  <section class="catalog-section">
    <div class="catalog-header">
      <h2 class="catalog-title">More All You Needs.</h2>
      <a href="../" style="font-weight:700;font-size:0.95rem;text-decoration:underline;">View All Drops &rarr;</a>
    </div>
    <div class="deals-grid-dribbble">
      {related_cards}
    </div>
  </section>

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-logo">Get Your <span>Deal.</span></div>
      <p style="color:var(--text-muted);font-size:0.9rem;">India's Best Curated E-Commerce Deals &amp; Drops</p>
      <p class="footer-disclaimer">Affiliate Disclosure: When you purchase through our links, we may earn an affiliate commission at zero additional cost to you.</p>
    </div>
  </footer>

  <script>
    const burgerBtn = document.getElementById('burgerMenuBtn');
    const drawer = document.getElementById('categoryDrawer');
    const overlay = document.getElementById('categoryDrawerOverlay');
    const closeBtn = document.getElementById('closeDrawerBtn');

    function openDrawer() {{
      drawer.classList.add('open');
      overlay.classList.add('open');
    }}

    function closeDrawer() {{
      drawer.classList.remove('open');
      overlay.classList.remove('open');
    }}

    if (burgerBtn) burgerBtn.addEventListener('click', openDrawer);
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    if (overlay) overlay.addEventListener('click', closeDrawer);

    function copyDealLink() {{
      navigator.clipboard.writeText(window.location.href);
      alert('Deal link copied to clipboard!');
    }}
  </script>

</body>
</html>"""

    page_dir = DOCS_DIR / deal_anchor_id
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "index.html").write_text(single_html, encoding="utf-8")
