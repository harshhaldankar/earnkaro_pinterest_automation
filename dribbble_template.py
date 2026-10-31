"""
dribbble_template.py - builds the Get Your Deal website (docs/deals/) from deals_data.json.

  docs/deals/index.html        catalog: search, sections (same split as the Pinterest boards),
                               store filter, sort, saved deals
  docs/deals/<deal_id>/        one page per deal, live or ended (pins keep pointing at them)
  docs/deals/live.json         live deals, read by deal pages to notice when their deal ends
  docs/deals/site.css          styles

(The module name is historical; telegram_watcher imports it by this name.)
"""

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

DOCS_DIR = Path("docs") / "deals"
MAX_DEALS = 80
SITE_URL = "https://harshhaldankar.github.io/Getyourdeal"
IST = timezone(timedelta(hours=5, minutes=30))
_GA4_PLACEHOLDER = "<!-- GA4_PLACEHOLDER -->"

STORE_DOMAINS = {
    "myntra": "Myntra", "myntr.it": "Myntra", "ajio": "AJIO", "ajiio.in": "AJIO", "amazon": "Amazon",
    "amzn": "Amazon", "flipkart": "Flipkart", "fkrt": "Flipkart", "nykaa": "Nykaa", "meesho": "Meesho",
    "tatacliq": "Tata CLiQ", "croma": "Croma", "mamaearth": "Mamaearth", "decathlon": "Decathlon",
}
ENDED_REASONS = {
    "out of stock": "It sold out",
    "price rose": "The price went back up",
    "discount now": "The discount is no longer on",
    "sale page": "This sale has finished",
    "no longer listed": "The store stopped listing it at this price",
    "older than": "It was posted a while ago and has likely changed",
}

# ----------------------------------------------------------------
# Legacy: pages from deals no longer in deals_data.json used the old template, which loads
# ../live.js and ../deals.css. Kept so any page we can't rebuild still works.
# ----------------------------------------------------------------
LIVE_SCRIPT_TAG = '<script src="../live.js" defer></script>'
LIVE_DEALS_JS = r"""(function () {
  var m = location.pathname.match(/(deal_[A-Za-z0-9_]+)\/?(index\.html)?$/);
  var pageId = m ? m[1] : null;
  fetch('../live.json', { cache: 'no-cache' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var deals = (data && data.deals) || [];
      if (pageId && !deals.some(function (d) { return d.id === pageId; })) {
        var main = document.querySelector('main');
        if (!main) return;
        var bar = document.createElement('div');
        bar.style.cssText = 'margin:16px auto;max-width:1100px;padding:14px 18px;border-radius:10px;' +
          'background:#FFF4E5;color:#7A3E00;font-weight:600;text-align:center;';
        bar.innerHTML = 'This deal has ended. <a href="../" style="color:#7A3E00;text-decoration:underline">See today\'s deals</a>';
        main.insertBefore(bar, main.firstChild);
      }
    })
    .catch(function () {});
})();
"""


# ----------------------------------------------------------------
# Styles
# ----------------------------------------------------------------
SITE_CSS = """
:root {
  --bg: #faf9f7;
  --card: #ffffff;
  --ink: #1c1b19;
  --muted: #6b6862;
  --faint: #9a968f;
  --line: #e7e4de;
  --soft: #f3f1ec;
  --accent: #c2410c;
  --accent-ink: #ffffff;
  --accent-hover: #9a3412;
  --good: #15803d;
  --warn-bg: #fff4e5;
  --warn-ink: #7a3e00;
  --radius: 10px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; font-family: var(--font); font-size: 15px; line-height: 1.5; color: var(--ink); background: var(--bg); }
a { color: inherit; }
img { display: block; max-width: 100%; }
button, input, select { font: inherit; color: inherit; }
.wrap { max-width: 1200px; margin: 0 auto; padding: 0 16px; }

/* Header */
.top { background: var(--card); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 10; }
.top .wrap { display: flex; align-items: center; gap: 16px; height: 60px; }
.logo { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; font-size: 18px; text-decoration: none; white-space: nowrap; letter-spacing: -0.2px; }
.logo svg { width: 22px; height: 22px; color: var(--accent); flex-shrink: 0; }
.search { flex: 1; max-width: 520px; margin-left: auto; position: relative; }
.search input { width: 100%; height: 40px; border: 1px solid var(--line); border-radius: 999px; background: var(--soft); padding: 0 16px 0 38px; outline: none; }
.search input:focus { border-color: var(--ink); background: var(--card); }
.search svg { position: absolute; left: 13px; top: 11px; width: 18px; height: 18px; color: var(--faint); }
.saved-link { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; font-weight: 600; font-size: 14px; color: var(--muted); white-space: nowrap; background: none; border: 0; cursor: pointer; padding: 6px 4px; }
.saved-link svg { width: 18px; height: 18px; }
.saved-link .n:empty { display: none; }
.saved-link .n { background: var(--accent); color: #fff; border-radius: 999px; font-size: 11px; padding: 0 6px; line-height: 18px; }

/* Catalog */
.intro { padding: 22px 0 6px; }
.intro h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: -0.3px; }
.intro p { margin: 0; color: var(--muted); font-size: 14px; }
.tabs { display: flex; gap: 8px; overflow-x: auto; padding: 14px 0 4px; scrollbar-width: none; }
.tabs::-webkit-scrollbar { display: none; }
.tab { flex-shrink: 0; border: 1px solid var(--line); background: var(--card); border-radius: 999px; padding: 7px 14px; font-size: 14px; font-weight: 600; cursor: pointer; color: var(--ink); }
.tab .c { color: var(--faint); font-weight: 500; margin-left: 4px; }
.tab[aria-pressed="true"] { background: var(--ink); color: #fff; border-color: var(--ink); }
.tab[aria-pressed="true"] .c { color: #cfcac2; }
.toolbar { display: flex; align-items: center; gap: 10px; padding: 12px 0; flex-wrap: wrap; }
.toolbar .count { color: var(--muted); font-size: 14px; margin-right: auto; }
.toolbar select { height: 36px; border: 1px solid var(--line); border-radius: 8px; background: var(--card); padding: 0 10px; font-size: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 16px; padding-bottom: 32px; }
.empty { display: none; text-align: center; color: var(--muted); padding: 48px 16px; }
.empty.show { display: block; }

/* Card */
.card { position: relative; background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; display: flex; flex-direction: column; }
.card[hidden] { display: none; }
.card:hover { border-color: #cfcac2; }
.card > a { text-decoration: none; display: flex; flex-direction: column; flex: 1; }
.card .pic { aspect-ratio: 4 / 5; background: var(--soft); display: flex; align-items: center; justify-content: center; }
.card .pic img { width: 100%; height: 100%; object-fit: contain; }
.card .body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 3px; flex: 1; }
.card .store { font-size: 12px; color: var(--muted); font-weight: 600; }
.card .name { font-size: 14px; font-weight: 500; line-height: 1.35; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.7em; }
.price { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.price b { font-size: 16px; }
.price s { color: var(--faint); font-size: 13px; }
.price .off { color: var(--good); font-weight: 700; font-size: 13px; }
.card .when { font-size: 12px; color: var(--faint); margin-top: auto; padding-top: 6px; }
.save { position: absolute; top: 8px; right: 8px; width: 34px; height: 34px; border-radius: 50%; border: 0; background: rgba(255,255,255,0.92); display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--muted); box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
.save svg { width: 18px; height: 18px; }
.save[aria-pressed="true"] { color: #e11d48; }
.save[aria-pressed="true"] svg { fill: currentColor; }

/* Deal page */
.crumbs { font-size: 13px; color: var(--muted); padding: 16px 0 0; }
.crumbs a { text-decoration: none; }
.crumbs a:hover { text-decoration: underline; }
.deal { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px; padding: 16px 0 32px; align-items: start; }
.deal .photo { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); aspect-ratio: 4 / 5; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.deal .photo img { width: 100%; height: 100%; object-fit: contain; }
.deal .store-tag { display: inline-block; font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 6px; }
.deal h1 { font-size: 24px; line-height: 1.3; margin: 0 0 14px; letter-spacing: -0.3px; }
.deal .price b { font-size: 28px; }
.deal .price s { font-size: 16px; }
.deal .price .off { font-size: 16px; }
.deal .saving { color: var(--good); font-size: 14px; margin-top: 2px; }
.status { font-size: 13px; color: var(--muted); margin: 12px 0 18px; display: flex; align-items: center; gap: 6px; }
.status .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good); }
.ended-note { display: none; background: var(--warn-bg); color: var(--warn-ink); border-radius: 8px; padding: 12px 14px; font-size: 14px; margin: 12px 0 18px; }
.is-ended .ended-note { display: block; }
.is-ended .status { display: none; }
.buy { display: flex; align-items: center; justify-content: center; height: 50px; border-radius: 8px; background: var(--accent); color: var(--accent-ink); font-weight: 700; font-size: 16px; text-decoration: none; }
.buy:hover { background: var(--accent-hover); }
.is-ended .buy { background: var(--card); color: var(--ink); border: 1px solid var(--line); }
.actions { display: flex; gap: 8px; margin-top: 10px; }
.actions > * { flex: 1; height: 42px; border-radius: 8px; border: 1px solid var(--line); background: var(--card); display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-size: 14px; font-weight: 600; text-decoration: none; cursor: pointer; }
.actions svg { width: 17px; height: 17px; }
.actions .wa { color: #128c4b; }
.actions [aria-pressed="true"] { color: #e11d48; }
.actions [aria-pressed="true"] svg { fill: currentColor; }
.facts { margin: 22px 0 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }
.facts li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
.facts li span:first-child { color: var(--muted); }
.fine { font-size: 12.5px; color: var(--faint); margin-top: 14px; }
.more h2 { font-size: 18px; margin: 8px 0 12px; }

/* Footer */
.foot { border-top: 1px solid var(--line); background: var(--card); margin-top: 24px; }
.foot .wrap { padding: 24px 16px 32px; display: grid; gap: 8px; font-size: 13px; color: var(--muted); }
.foot strong { color: var(--ink); }
.foot nav { display: flex; gap: 16px; }

/* Privacy / Terms */
.legal { max-width: 720px; padding: 24px 0 40px; font-size: 15px; line-height: 1.65; }
.legal h1 { font-size: 26px; letter-spacing: -0.3px; margin: 0 0 4px; }
.legal .updated { color: var(--muted); font-size: 13px; margin: 0 0 20px; }
.legal h2 { font-size: 17px; margin: 26px 0 6px; }
.legal p, .legal ul { margin: 0 0 10px; }
.legal ul { padding-left: 20px; }
.toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); background: var(--ink); color: #fff; padding: 10px 16px; border-radius: 8px; font-size: 14px; opacity: 0; transition: opacity .2s; pointer-events: none; }
.toast.show { opacity: 1; }

@media (max-width: 760px) {
  .top .wrap { height: auto; flex-wrap: wrap; padding-top: 10px; padding-bottom: 10px; gap: 10px; }
  .search { order: 3; flex-basis: 100%; max-width: none; }
  .saved-link { margin-left: auto; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .card .body { padding: 8px 10px 10px; }
  .card .name { font-size: 13.5px; }
  .deal { grid-template-columns: 1fr; gap: 18px; }
  .deal h1 { font-size: 20px; }
  .intro h1 { font-size: 19px; }
}
"""

ICON_TAG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z"/><circle cx="7.5" cy="7.5" r="1.5"/></svg>'
ICON_SEARCH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
ICON_HEART = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 7.9 3.6 4.5 7 4.5c2 0 3.6 1.1 5 3 1.4-1.9 3-3 5-3 3.4 0 5.6 3.4 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2Z"/></svg>'
ICON_WA = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.1 5.1 0 0 0 1.1 2.7 11.7 11.7 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.4-.3Z"/></svg>'
ICON_LINK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/></svg>'

# Saved deals live in this browser only (localStorage); everything degrades to no-op without it
SAVED_JS = """
var SAVED_KEY = 'gyd_saved';
function getSaved() { try { return JSON.parse(localStorage.getItem(SAVED_KEY) || '[]'); } catch (e) { return []; } }
function setSaved(list) { try { localStorage.setItem(SAVED_KEY, JSON.stringify(list)); } catch (e) {} }
function isSaved(id) { return getSaved().indexOf(id) !== -1; }
function toggleSaved(id) {
  var list = getSaved(), i = list.indexOf(id);
  if (i === -1) list.unshift(id); else list.splice(i, 1);
  setSaved(list.slice(0, 200));
  return i === -1;
}
function paintSaved() {
  document.querySelectorAll('[data-save]').forEach(function (b) {
    b.setAttribute('aria-pressed', isSaved(b.getAttribute('data-save')) ? 'true' : 'false');
  });
  var n = getSaved().length;
  document.querySelectorAll('.saved-link .n').forEach(function (e) { e.textContent = n ? n : ''; });
}
function toast(msg) {
  var t = document.querySelector('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('show'); }, 1800);
}
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-save]');
  if (!b) return;
  e.preventDefault();
  var on = toggleSaved(b.getAttribute('data-save'));
  paintSaved();
  toast(on ? 'Saved on this device' : 'Removed from saved');
  if (window.onSavedChange) window.onSavedChange();
});
paintSaved();
"""

CATALOG_JS = """
(function () {
  var grid = document.getElementById('grid');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
  var q = document.getElementById('q'), store = document.getElementById('store'), sort = document.getElementById('sort');
  var tabs = document.querySelectorAll('.tab'), count = document.getElementById('count'), empty = document.getElementById('empty');
  var section = 'all';
  var params = new URLSearchParams(location.search);
  if (params.get('q')) q.value = params.get('q');
  var cat = (params.get('cat') || '').toLowerCase();
  if (cat) tabs.forEach(function (t) { if (t.getAttribute('data-section') === cat) section = cat; });
  if (location.hash === '#saved') section = 'saved';

  function apply() {
    var words = q.value.toLowerCase().split(/\\s+/).filter(Boolean);
    var st = store.value, saved = getSaved(), shown = 0;
    tabs.forEach(function (t) { t.setAttribute('aria-pressed', t.getAttribute('data-section') === section ? 'true' : 'false'); });
    var key = sort.value;
    cards.sort(function (a, b) {
      if (key === 'discount') return (+b.dataset.disc) - (+a.dataset.disc);
      if (key === 'price') return (+a.dataset.price || 1e9) - (+b.dataset.price || 1e9);
      return a.dataset.ts < b.dataset.ts ? 1 : -1;
    });
    cards.forEach(function (c) {
      var ok = (section === 'all' || (section === 'saved' ? saved.indexOf(c.dataset.id) !== -1 : c.dataset.section === section))
        && (!st || c.dataset.store === st)
        && words.every(function (w) { return c.dataset.text.indexOf(w) !== -1; });
      c.hidden = !ok;
      if (ok) shown++;
      grid.appendChild(c);
    });
    count.textContent = shown + (shown === 1 ? ' deal' : ' deals');
    empty.classList.toggle('show', shown === 0);
    empty.textContent = section === 'saved' && !saved.length
      ? 'Nothing saved yet. Tap the heart on any deal to keep it here.'
      : 'No deals match. Try a different word or clear the filters.';
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { section = t.getAttribute('data-section'); apply(); }); });
  [q, store, sort].forEach(function (el) { el.addEventListener('input', apply); });
  document.getElementById('savedBtn').addEventListener('click', function () { section = 'saved'; apply(); window.scrollTo(0, 0); });
  window.onSavedChange = function () { if (section === 'saved') apply(); };
  apply();
})();
"""


# ----------------------------------------------------------------
# Deal data -> display values
# ----------------------------------------------------------------
def clean_val(val_raw):
    if not val_raw:
        return ""
    return str(val_raw).replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()


def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _deal_id(d: dict) -> str:
    ts = d.get("timestamp", "")
    return "deal_" + ts.replace("-", "").replace(":", "").replace(".", "").replace("T", "_")


def _int(v):
    try:
        return int(float(clean_val(v)))
    except (TypeError, ValueError):
        return None


def _store(d: dict) -> str:
    from telegram_watcher import get_store_name
    name = get_store_name(d.get("title", ""))
    if name not in ("Hot Deal", "Axis Bank"):
        return "AJIO" if name == "Ajio" else name
    for url in (d.get("store_url"), d.get("affiliate_link"), d.get("product_url")):
        u = (url or "").lower()
        for key, store in STORE_DOMAINS.items():
            if key in u:
                return store
    return ""


def _posted(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "")).replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def _ago(dt) -> str:
    if not dt:
        return ""
    mins = (datetime.now(timezone.utc) - dt).total_seconds() / 60
    if mins < 60:
        return "just now" if mins < 2 else f"{int(mins)} min ago"
    hours = mins / 60
    if hours < 24:
        return f"{int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    days = int(hours / 24)
    return "yesterday" if days == 1 else f"{days} days ago"


def _view(d: dict) -> dict:
    """Everything a card or page shows, cleaned up once."""
    from pinterest_poster import product_name
    from telegram_watcher import extract_price
    from shared.board_classifier import site_section
    title = d.get("title", "")
    name = product_name(title, d.get("desc", ""))
    price = _int(extract_price(re.sub(r"\d+\s*%", "", title)) or "")
    mrp = _int(d.get("mrp"))
    if mrp and price and mrp <= price:
        mrp = None
    disc = d.get("discount_percent")
    if not disc and price and mrp:
        disc = round((1 - price / mrp) * 100)
    sale_m = re.search(r"((?:upto|up to|min\.?|flat)\s*\d+\s*%)", title, re.IGNORECASE)
    band = re.search(r"\b(under|starting(?:\s+at)?|starts?(?:\s+at)?|from)\s*(?:rs\.?|₹)\s*([\d,]+)", title, re.IGNORECASE)
    band_label = ""
    if band and "@" not in title:
        # A collection's price band ("Under Rs 799") is not a price
        band_label, price, mrp = f"{band.group(1).capitalize()} ₹{int(band.group(2).replace(',', '')):,}", None, None
    if not disc and not sale_m:
        m = re.search(r"(\d+)\s*%\s*off", title, re.IGNORECASE)
        disc = int(m.group(1)) if m else None
    slug, label = site_section(title)
    posted = _posted(d.get("timestamp", ""))
    checked = _posted(d.get("price_checked_at", "") or "")  # None: never checked at the store
    reason = (d.get("ended_reason") or "").lower()
    return {
        "id": _deal_id(d), "name": name, "store": _store(d), "section": slug, "section_label": label,
        "price": price, "mrp": mrp, "disc": int(disc) if disc else None,
        "sale_label": band_label or ((sale_m.group(1).replace("upto", "Up to").replace("Upto", "Up to") + " off") if sale_m and not price else ""),
        "img": d.get("image_path", ""), "ts": d.get("timestamp", ""), "posted": posted, "checked": checked,
        "link": d.get("affiliate_link") or d.get("product_url") or "",
        "ended": bool(d.get("ended")),
        "ended_text": next((v for k, v in ENDED_REASONS.items() if k in reason), ""),
    }


def _price_html(v: dict) -> str:
    if v["price"]:
        out = f"<b>₹{v['price']:,}</b>"
        if v["mrp"]:
            out += f" <s>₹{v['mrp']:,}</s>"
        if v["disc"]:
            out += f' <span class="off">{v["disc"]}% off</span>'
    elif v["sale_label"]:
        out = f'<span class="off">{_e(v["sale_label"])}</span>'
    elif v["disc"]:
        out = f'<span class="off">{v["disc"]}% off</span>'
    else:
        out = '<span class="off">See price</span>'
    return f'<div class="price">{out}</div>'


def _outbound(v: dict, medium: str) -> str:
    if not v["link"]:
        return "#"
    sep = "&" if "?" in v["link"] else "?"
    return f"{v['link']}{sep}utm_source=website&utm_medium={medium}&utm_campaign=getyourdeal"


_FILL_CACHE = {}


def _fill(img: str) -> str:
    """style attribute giving an image's frame the image's own edge colour, so banners and
    wide screenshots don't sit between grey bars."""
    if img not in _FILL_CACHE:
        style = ""
        try:
            from PIL import Image
            with Image.open(DOCS_DIR / img) as im:
                small = im.convert("RGB").resize((24, 24))
            edge = [small.getpixel((i, j)) for i in range(24) for j in (0, 23)] + \
                   [small.getpixel((j, i)) for i in range(24) for j in (0, 23)]
            style = ' style="background:#%02x%02x%02x"' % tuple(sum(p[c] for p in edge) // len(edge) for c in range(3))
        except Exception:
            pass
        _FILL_CACHE[img] = style
    return _FILL_CACHE[img]


def _card(v: dict, prefix: str) -> str:
    text = f"{v['name']} {v['store']} {v['section_label']}".lower()
    img = f'<img src="{prefix}{_e(v["img"])}" alt="{_e(v["name"])}" loading="lazy">' if v["img"] else ""
    return f"""
      <article class="card" data-id="{v['id']}" data-section="{v['section']}" data-store="{_e(v['store'].lower())}" data-price="{v['price'] or 0}" data-disc="{v['disc'] or 0}" data-ts="{_e(v['ts'])}" data-text="{_e(text)}">
        <a href="{prefix}{v['id']}/">
          <div class="pic"{_fill(v['img']) if v['img'] else ''}>{img}</div>
          <div class="body">
            <div class="store">{_e(v['store'] or v['section_label'])}</div>
            <h3 class="name">{_e(v['name'])}</h3>
            {_price_html(v)}
            <div class="when">Posted {_ago(v['posted'])}</div>
          </div>
        </a>
        <button class="save" type="button" data-save="{v['id']}" aria-label="Save deal" aria-pressed="false">{ICON_HEART}</button>
      </article>"""


def _header(prefix: str, search_value: str = "") -> str:
    return f"""
  <header class="top">
    <div class="wrap">
      <a class="logo" href="{prefix}">{ICON_TAG}Get Your Deal</a>
      <form class="search" action="{prefix}" role="search">
        {ICON_SEARCH}
        <input id="q" name="q" type="search" placeholder="Search deals, e.g. kurta, sneakers, watch" value="{_e(search_value)}" autocomplete="off">
      </form>
      <button class="saved-link" id="savedBtn" type="button" onclick="location.href='{prefix}#saved'">{ICON_HEART}Saved <span class="n"></span></button>
    </div>
  </header>"""


def _footer(prefix: str) -> str:
    return f"""
  <footer class="foot">
    <div class="wrap">
      <div><strong>Get Your Deal</strong> &middot; fashion, beauty and home deals from Indian stores, posted several times a day.</div>
      <div>Prices and stock change quickly. The price you see at the store's checkout is the one that counts.</div>
      <nav><a href="{prefix}../privacy.html">Privacy</a><a href="{prefix}../terms.html">Terms</a><a href="{prefix}../terms.html#affiliate">Affiliate disclosure</a></nav>
    </div>
  </footer>"""


def _page(title: str, description: str, body: str, prefix: str, extra_head: str = "", body_class: str = "") -> str:
    cls = f' class="{body_class}"' if body_class else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description)}">
  <link rel="stylesheet" href="{prefix}site.css">
  {extra_head}
  {_GA4_PLACEHOLDER}
</head>
<body{cls}>
{body}
  <script>{SAVED_JS}</script>
</body>
</html>"""


# ----------------------------------------------------------------
# Pages
# ----------------------------------------------------------------
def write_single_deal_page(deal, deal_anchor_id=None, related_deals=()):
    """One deal page. related_deals: deal dicts or views to suggest underneath (live ones only)."""
    v = _view(deal) if "id" not in deal or "name" not in deal else deal
    if deal_anchor_id:
        v["id"] = deal_anchor_id
    related = [r if "name" in r and "section" in r else _view(r) for r in related_deals]
    related = [r for r in related if not r["ended"] and r["id"] != v["id"]][:8]

    store = v["store"] or "the store"
    saving = f"You save ₹{v['mrp'] - v['price']:,}" if v["price"] and v["mrp"] else ""
    posted_str = v["posted"].astimezone(IST).strftime("%d %b %Y, %I:%M %p IST") if v["posted"] else ""
    img = f'<img src="../{_e(v["img"])}" alt="{_e(v["name"])}">' if v["img"] else ""
    og_img = f'<meta property="og:image" content="{SITE_URL}/deals/{_e(v["img"])}">' if v["img"] else ""
    share_text = f"{v['name']}" + (f" for ₹{v['price']:,}" if v["price"] else "") + f" on {store}: {SITE_URL}/deals/{v['id']}/"
    wa = "https://wa.me/?text=" + html.escape(re.sub(r"\s+", "%20", share_text), quote=True)
    more = "".join(_card(r, "../") for r in related)
    more_html = f"""
    <section class="more">
      <h2>{'More in ' + _e(v['section_label']) if related and related[0]['section'] == v['section'] and v['section'] != 'more' else "Today's deals"}</h2>
      <div class="grid">{more}</div>
    </section>""" if related else ""

    body = f"""{_header('../')}
  <main class="wrap">
    <div class="crumbs"><a href="../">All deals</a> &rsaquo; <a href="../?cat={v['section']}">{_e(v['section_label'])}</a></div>
    <div class="deal">
      <div class="photo"{_fill(v['img']) if v['img'] else ''}>{img}</div>
      <div>
        {f'<span class="store-tag">{_e(v["store"])}</span>' if v["store"] else ''}
        <h1>{_e(v['name'])}</h1>
        {_price_html(v) if v['price'] or v['disc'] or v['sale_label'] or not v['ended'] else ''}
        {f'<div class="saving">{saving}</div>' if saving else ''}
        <div class="status"><span class="dot"></span>{'Price checked ' + _ago(v['checked']) if v['checked'] else 'Posted ' + _ago(v['posted']) + '. Check the final price at the store'}</div>
        <div class="ended-note"><strong>This deal has ended.</strong> {_e(v['ended_text']) + '. ' if v['ended_text'] else ''}You can still check the current price, or look at the live deals below.</div>
        <a class="buy" href="{_e(_outbound(v, 'deal_page'))}" target="_blank" rel="noopener sponsored nofollow">{'Check price on ' if v['ended'] else 'Buy on '}{_e(store)}</a>
        <div class="actions">
          <a class="wa" href="{wa}" target="_blank" rel="noopener">{ICON_WA}Share</a>
          <button type="button" onclick="navigator.clipboard && navigator.clipboard.writeText(location.href).then(function(){{toast('Link copied')}})">{ICON_LINK}Copy link</button>
          <button type="button" data-save="{v['id']}" aria-pressed="false">{ICON_HEART}Save</button>
        </div>
        <ul class="facts">
          <li><span>Store</span><span>{_e(v['store'] or 'Partner store')}</span></li>
          <li><span>Category</span><span>{_e(v['section_label'])}</span></li>
          {f'<li><span>Posted</span><span>{posted_str}</span></li>' if posted_str else ''}
        </ul>
        <p class="fine">Prices and stock on {_e(store)} change often; the checkout price is final.</p>
      </div>
    </div>
    {more_html}
  </main>
{_footer('../')}
  <script>
    fetch('../live.json', {{ cache: 'no-cache' }}).then(function (r) {{ return r.json(); }}).then(function (d) {{
      if (!(d.deals || []).some(function (x) {{ return x.id === '{v['id']}'; }})) document.body.classList.add('is-ended');
    }}).catch(function () {{}});
  </script>"""

    desc = f"{v['name']}" + (f" for ₹{v['price']:,}" if v["price"] else "") + (f" ({v['disc']}% off)" if v["disc"] else "") + f" on {store}."
    page = _page(f"{v['name'][:70]} | Get Your Deal", desc, body, "../",
                 extra_head=f'<meta property="og:title" content="{_e(v["name"][:90])}">\n  {og_img}',
                 body_class="is-ended" if v["ended"] else "")
    page_dir = DOCS_DIR / v["id"]
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "index.html").write_text(page, encoding="utf-8")


def _orphan_view(page: Path):
    """Rebuild data for an old page whose deal is gone from deals_data.json (it has ended)."""
    from shared.board_classifier import site_section
    from pinterest_poster import product_name
    text = page.read_text(encoding="utf-8")
    # Old template first, then pages this function already rebuilt
    h1 = re.search(r'<h1 class="product-title-main">(.*?)</h1>', text, re.S) or re.search(r'<h1>(.*?)</h1>', text, re.S)
    if not h1:
        return None
    title = html.unescape(h1.group(1)).strip()
    img = re.search(r'(?:single-product-media-card|class="photo")">\s*<img src="\.\./([^"]+)"', text)
    link = (re.search(r'href="([^"]+)"[^>]*class="btn-buy-dribbble"', text)
            or re.search(r'class="buy" href="([^"]+)"', text))
    raw_link = html.unescape(link.group(1)) if link else ""
    raw_link = re.sub(r"[?&]utm_source=website.*$", "", raw_link)
    slug, label = site_section(title)
    m = re.match(r"deal_(\d{8})_(\d{6})", page.parent.name)
    posted = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc) if m else None
    d = {"title": title, "affiliate_link": raw_link}
    return {
        "id": page.parent.name, "name": product_name(title), "store": _store(d), "section": slug, "section_label": label,
        "price": None, "mrp": None, "disc": None, "sale_label": "", "img": img.group(1) if img else "",
        "ts": posted.isoformat() if posted else "", "posted": posted, "checked": posted, "link": raw_link,
        "ended": True, "ended_text": "",
    }


CONTACT_EMAIL = "Carrercurve@gmail.com"
LEGAL_UPDATED = "31 October 2026"

PRIVACY_BODY = f"""
      <h1>Privacy</h1>
      <p class="updated">Last updated {LEGAL_UPDATED}</p>
      <p>Get Your Deal is a list of deals from Indian online stores. You can browse it without an account, and we don't ask you for any personal information.</p>
      <h2>What we collect</h2>
      <p>Nothing directly. The site has no sign-up, no forms, no analytics and no advertising trackers, and it doesn't set cookies of its own.</p>
      <h2>Saved deals</h2>
      <p>When you tap the heart on a deal, it's saved in your own browser (local storage), not sent to us. Clearing your browser's site data removes it.</p>
      <h2>Hosting</h2>
      <p>The site is hosted on GitHub Pages. Like any web host, GitHub may log technical details such as your IP address to keep the service secure. See the <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub Privacy Statement</a>.</p>
      <h2>When you go to a store</h2>
      <p>Buy buttons take you to the store (for example Amazon, Myntra or AJIO), sometimes through a tracking link from an affiliate network. The link tells the store the visit came from our site. From then on, the store's own privacy policy and cookies apply. We never see what you buy, your payment details or your address.</p>
      <h2>Sharing</h2>
      <p>The Share button opens WhatsApp with the deal's link. Nothing is sent unless you send the message yourself.</p>
      <h2>Children</h2>
      <p>The site isn't meant for children under 13, and we don't knowingly collect anyone's personal information.</p>
      <h2>Contact</h2>
      <p>Questions about this page: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. If this policy changes, the date at the top changes too.</p>"""

TERMS_BODY = f"""
      <h1>Terms</h1>
      <p class="updated">Last updated {LEGAL_UPDATED}</p>
      <p>By using Get Your Deal you agree to these terms.</p>
      <h2>What we do</h2>
      <p>We find discounts on fashion, footwear, accessories, beauty and home products at Indian online stores and list them here, on Pinterest and on Instagram. We don't sell anything ourselves.</p>
      <h2>Your order is with the store</h2>
      <p>When you buy, your order, payment, delivery, returns and refunds are handled by the store you bought from, under its own terms. Please contact the store about any order.</p>
      <h2>Prices and stock</h2>
      <p>Deals change quickly. We check deals and remove them when they sell out or end, but a price or size can change before we notice. The price shown at the store's checkout is the one that counts.</p>
      <h2 id="affiliate">Affiliate disclosure</h2>
      <p>Some links on this site are affiliate links. If you buy through one, the store or affiliate network may pay us a commission. You pay the same price either way. As an Amazon Associate we earn from qualifying purchases. We also earn through EarnKaro on purchases at stores such as Myntra and AJIO.</p>
      <h2>Product names and images</h2>
      <p>Product names, photos and brand names belong to their brands and stores. We show them only to point you to the deal.</p>
      <h2>No warranty</h2>
      <p>The site is provided as is. We aren't responsible for products, prices or stores, or for any loss from using the site, as far as the law allows.</p>
      <h2>Law</h2>
      <p>These terms are governed by the laws of India.</p>
      <h2>Contact</h2>
      <p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>"""


def write_legal_pages():
    """docs/privacy.html and docs/terms.html, in the site's own look."""
    for name, title, body in (("privacy", "Privacy", PRIVACY_BODY), ("terms", "Terms", TERMS_BODY)):
        page = _page(f"{title} – Get Your Deal", f"{title} for Get Your Deal.",
                     f"{_header('deals/')}\n  <main class=\"wrap legal\">{body}\n  </main>\n{_footer('deals/')}", "deals/")
        (DOCS_DIR.parent / f"{name}.html").write_text(page, encoding="utf-8")


def rebuild_dribbble_website(deals):
    """Rebuild the catalog, every deal page and live.json."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (DOCS_DIR / "live.js").write_text(LIVE_DEALS_JS, encoding="utf-8")
    write_legal_pages()

    usable = [d for d in deals
              if d.get("image_path") and (DOCS_DIR / d["image_path"]).exists()
              and "http" not in d.get("title", "").lower()
              and len(d.get("title", "").strip()) >= 6 and not d.get("title", "").strip().isdigit()]
    views = [_view(d) for d in usable]
    live = sorted((v for v in views if not v["ended"]), key=lambda v: v["ts"], reverse=True)[:MAX_DEALS]
    live_ids = {v["id"] for v in live}

    def related_for(v):
        same = [r for r in live if r["section"] == v["section"] and r["id"] != v["id"]]
        rest = [r for r in live if r["section"] != v["section"]]
        return (same + rest)[:8]

    for v in views:
        if v["ended"] or v["id"] in live_ids:
            write_single_deal_page(v, None, related_for(v))
    known = {v["id"] for v in views}
    orphans = 0
    for page in DOCS_DIR.glob("deal_*/index.html"):
        if page.parent.name in known:
            continue
        ov = _orphan_view(page)
        if ov:
            write_single_deal_page(ov, None, related_for(ov))
            orphans += 1

    # Catalog
    from shared.board_classifier import SITE_SECTIONS
    counts = {}
    for v in live:
        counts[v["section"]] = counts.get(v["section"], 0) + 1
    tabs = f'<button class="tab" type="button" data-section="all" aria-pressed="true">All<span class="c">{len(live)}</span></button>'
    for slug, label, _ in SITE_SECTIONS + [("more", "More", "")]:
        if counts.get(slug):
            tabs += f'<button class="tab" type="button" data-section="{slug}" aria-pressed="false">{_e(label)}<span class="c">{counts[slug]}</span></button>'
    tabs += '<button class="tab" type="button" data-section="saved" aria-pressed="false">Saved</button>'
    stores = sorted({v["store"] for v in live if v["store"]})
    store_opts = '<option value="">All stores</option>' + "".join(
        f'<option value="{_e(s.lower())}">{_e(s)}</option>' for s in stores)
    updated = datetime.now(IST).strftime("%d %b, %I:%M %p")

    body = f"""{_header('./')}
  <main class="wrap">
    <div class="intro">
      <h1>Today's deals on fashion, beauty and home</h1>
      <p>From Myntra, AJIO, Amazon and more. We remove deals once they sell out or the price goes back up. Updated {updated} IST.</p>
    </div>
    <div class="tabs" role="toolbar" aria-label="Sections">{tabs}</div>
    <div class="toolbar">
      <span class="count" id="count">{len(live)} deals</span>
      <select id="store" aria-label="Store">{store_opts}</select>
      <select id="sort" aria-label="Sort">
        <option value="new">Newest first</option>
        <option value="discount">Biggest discount</option>
        <option value="price">Lowest price</option>
      </select>
    </div>
    <div class="grid" id="grid">{''.join(_card(v, './') for v in live)}
    </div>
    <p class="empty" id="empty"></p>
  </main>
{_footer('./')}
  <script>
    (function () {{ var h = location.hash; if (h.indexOf('#deal_') === 0) location.replace('./' + h.slice(1) + '/'); }})();
  </script>"""
    page = _page("Get Your Deal – fashion, beauty & home deals in India",
                 "Handpicked deals on fashion, footwear, watches, beauty and home from Myntra, AJIO, Amazon and more, checked and updated through the day.",
                 body, "./")
    page = page.replace("</body>", f"  <script>{CATALOG_JS}</script>\n</body>")
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"[Web] Rebuilt catalog with {len(live)} live deals, {len(views) - len(live)} ended pages, {orphans} old pages.")

    # live.json: deal pages check it to notice when their deal ends. Old field names kept for live.js.
    entries = [{
        "id": v["id"], "name": v["name"], "store": v["store"], "section": v["section"],
        "price": f"₹{v['price']:,}" if v["price"] else "See price", "disc": f"{v['disc']}% OFF" if v["disc"] else "",
        "img": v["img"], "ts": v["ts"], "title": v["name"], "brand": v["store"], "cat": v["section_label"],
    } for v in live]
    (DOCS_DIR / "live.json").write_text(
        json.dumps({"generated_at": datetime.utcnow().isoformat() + "Z", "deals": entries}, ensure_ascii=False),
        encoding="utf-8")
