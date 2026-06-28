"""
generate_website.py
Reads content.json (produced by the automation pipeline) and writes:
  - docs/deals.html  → auto-updated deals page (served by GitHub Pages)
  - docs/index.html  → landing page (copied from template)

Run after poster_pinterest.py so pin_url and pin_image_path are populated.
"""
import json
import os
import shutil
from datetime import datetime

DOCS_DIR   = "docs"   # GitHub Pages serves from /docs
ASSETS_DIR = os.path.join(DOCS_DIR, "pins")

def load_content():
    if not os.path.exists("content.json"):
        print("content.json not found. Skipping website generation.")
        return []
    with open("content.json", "r", encoding="utf-8") as f:
        return json.load(f)

def copy_static_files():
    """Copy static site files (index, privacy, terms, style) into docs/ if present."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    for fname in ["index.html", "privacy.html", "terms.html", "style.css"]:
        src = os.path.join("site", fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DOCS_DIR, fname))

def copy_pin_images(items):
    """Copy generated pin images into docs/pins/ so they're served by GitHub Pages."""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for item in items:
        src = item.get("pin_image_path", "")
        if src and os.path.exists(src):
            dst = os.path.join(ASSETS_DIR, os.path.basename(src))
            shutil.copy2(src, dst)
            item["web_image_path"] = "pins/" + os.path.basename(src)
        else:
            item["web_image_path"] = ""

def render_deal_card(item):
    brand      = item.get("brand", "Brand")
    rate       = item.get("rate", "")
    title      = item.get("pinterest_title", "")
    angle      = item.get("angle", "")
    desc       = item.get("pinterest_description", "")[:200]
    aff_link   = item.get("affiliate_link", "#")
    pin_url    = item.get("pin_url", "#")
    img_path   = item.get("web_image_path", "")
    category   = item.get("category", "Deal")
    rank       = item.get("rank", 0)

    img_tag = (
        f'<img src="{img_path}" alt="Pin image for {brand}" loading="lazy" />'
        if img_path else
        f'<div class="card-img-placeholder">{brand[0]}</div>'
    )

    return f"""
    <article class="deal-card" id="deal-{rank}">
      <div class="card-img-wrap">
        {img_tag}
        <span class="card-rank">#{rank}</span>
        <span class="card-cat">{category}</span>
      </div>
      <div class="card-body">
        <h3 class="card-brand">{brand}</h3>
        <div class="card-rate">{rate}</div>
        <p class="card-angle">"{angle}"</p>
        <p class="card-title">{title}</p>
        <p class="card-desc">{desc}…</p>
        <div class="card-actions">
          <a href="{aff_link}" target="_blank" rel="noopener" class="btn-deal">
            🛍️ Get This Deal
          </a>
          <a href="{pin_url}" target="_blank" rel="noopener" class="btn-pin">
            📌 View Pin
          </a>
        </div>
      </div>
    </article>"""

def generate_deals_page(items):
    now   = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    count = len(items)
    cards = "\n".join(render_deal_card(item) for item in items)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Today's Best Deals – Get Your Deal</title>
  <meta name="description" content="Hand-picked affiliate deals updated daily on top Indian brands — Myntra, Nykaa, Flipkart &amp; more." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="style.css" />
  <link rel="stylesheet" href="deals.css" />
</head>
<body>

  <nav class="navbar scrolled">
    <div class="nav-inner">
      <a href="index.html" class="logo"><span class="logo-icon">🛍️</span><span>Get Your Deal</span></a>
      <div class="nav-links">
        <a href="index.html">Home</a>
        <a href="deals.html" class="active">Today's Deals</a>
        <a href="privacy.html">Privacy</a>
        <a href="terms.html">Terms</a>
      </div>
    </div>
  </nav>

  <div class="deals-hero">
    <div class="badge">🔄 Auto-updated by automation</div>
    <h1>Today's <span class="gradient-text">Top {count} Deals</span></h1>
    <p class="deals-timestamp">Last updated: <strong>{now}</strong></p>
    <p class="deals-sub">
      Hand-picked affiliate deals on India's top brands — curated by AI, posted to Pinterest daily.
    </p>
  </div>

  <main class="deals-grid" id="deals-grid">
    {cards}
  </main>

  <div class="deals-cta-strip">
    <p>🔔 Follow us on Pinterest to never miss a deal!</p>
    <a href="https://pinterest.com" target="_blank" rel="noopener" class="btn-primary">
      📌 Follow on Pinterest
    </a>
  </div>

  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-logo">🛍️ Get Your Deal</div>
      <div class="footer-links">
        <a href="privacy.html">Privacy Policy</a>
        <a href="terms.html">Terms of Service</a>
        <a href="mailto:Carrercurve@gmail.com">Contact</a>
      </div>
      <p class="footer-copy">© 2024 Get Your Deal. Affiliate links disclosure: we earn a commission at no extra cost to you.</p>
    </div>
  </footer>

  <script>
    window.addEventListener("scroll", () => {{
      document.querySelector(".navbar").classList.toggle("scrolled", window.scrollY > 20);
    }});
    const obs = new IntersectionObserver((entries) => {{
      entries.forEach(e => {{ if (e.isIntersecting) e.target.classList.add("visible"); }});
    }}, {{ threshold: 0.08 }});
    document.querySelectorAll(".deal-card").forEach(el => obs.observe(el));
  </script>
</body>
</html>"""

    out_path = os.path.join(DOCS_DIR, "deals.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {out_path} with {count} deals.")

def generate_deals_css():
    css = """
/* ── DEALS PAGE ─────────────────────────────────────────────── */
.deals-hero {
  padding: 130px 5% 60px;
  text-align: center;
  background: linear-gradient(180deg, rgba(233,69,96,0.12) 0%, transparent 100%);
  border-bottom: 1px solid var(--border);
}
.deals-hero h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 800;
  letter-spacing: -2px;
  margin: 16px 0;
}
.deals-timestamp { color: var(--muted); font-size: 0.9rem; margin-bottom: 10px; }
.deals-sub { color: var(--muted); max-width: 520px; margin: 0 auto; font-size: 1rem; }

.deals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 28px;
  max-width: 1300px;
  margin: 60px auto;
  padding: 0 5%;
}

.deal-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  overflow: hidden;
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.5s, transform 0.5s, box-shadow 0.3s;
}
.deal-card.visible { opacity: 1; transform: translateY(0); }
.deal-card:hover { box-shadow: 0 24px 70px rgba(233,69,96,0.15); transform: translateY(-4px); }

.card-img-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 2/3;
  overflow: hidden;
  background: var(--surface);
}
.card-img-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s;
}
.deal-card:hover .card-img-wrap img { transform: scale(1.04); }
.card-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 5rem;
  font-weight: 800;
  color: rgba(255,255,255,0.1);
  background: linear-gradient(135deg, var(--surface), var(--card));
}
.card-rank {
  position: absolute;
  top: 14px; left: 14px;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(8px);
  color: #fff;
  font-size: 0.8rem;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 50px;
}
.card-cat {
  position: absolute;
  top: 14px; right: 14px;
  background: var(--primary);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 50px;
}

.card-body { padding: 20px 22px 24px; }
.card-brand { font-size: 1.2rem; font-weight: 800; margin-bottom: 6px; }
.card-rate {
  display: inline-block;
  background: rgba(233,69,96,0.12);
  border: 1px solid rgba(233,69,96,0.3);
  color: var(--primary);
  font-size: 0.85rem;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 50px;
  margin-bottom: 12px;
}
.card-angle { color: #f59e0b; font-size: 0.9rem; font-style: italic; margin-bottom: 8px; }
.card-title { font-size: 0.97rem; font-weight: 600; margin-bottom: 8px; line-height: 1.4; }
.card-desc { color: var(--muted); font-size: 0.85rem; margin-bottom: 18px; line-height: 1.5; }

.card-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.btn-deal {
  flex: 1;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #fff;
  padding: 10px 18px;
  border-radius: 50px;
  font-weight: 600;
  font-size: 0.88rem;
  text-align: center;
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn-deal:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(233,69,96,0.4); }
.btn-pin {
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 10px 16px;
  border-radius: 50px;
  font-weight: 600;
  font-size: 0.88rem;
  text-align: center;
  transition: border-color 0.2s, color 0.2s;
}
.btn-pin:hover { border-color: rgba(255,255,255,0.3); color: var(--text); }

.deals-cta-strip {
  background: linear-gradient(135deg, rgba(233,69,96,0.15), rgba(124,58,237,0.15));
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 48px 5%;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}
.deals-cta-strip p { font-size: 1.2rem; font-weight: 600; }

@media (max-width: 600px) {
  .deals-grid { grid-template-columns: 1fr; padding: 0 4%; }
  .card-actions { flex-direction: column; }
}
"""
    out_path = os.path.join(DOCS_DIR, "deals.css")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(css)
    print(f"Generated {out_path}")

def main():
    print("=== Step 5b: Generate Website Deals Page ===")
    os.makedirs(DOCS_DIR, exist_ok=True)
    items = load_content()
    if not items:
        print("No deals found. Skipping.")
        return
    copy_static_files()
    copy_pin_images(items)
    generate_deals_css()
    generate_deals_page(items)
    print(f"Website updated! {len(items)} deals written to {DOCS_DIR}/deals.html")

if __name__ == "__main__":
    main()
