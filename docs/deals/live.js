(function () {
  var m = location.pathname.match(/(deal_[A-Za-z0-9_]+)\/?(index\.html)?$/);
  var pageId = m ? m[1] : null;
  var cat = '';
  document.querySelectorAll('.meta-pill').forEach(function (p) {
    if (p.textContent.indexOf('Category:') !== -1 && p.querySelector('strong')) {
      cat = p.querySelector('strong').textContent.trim();
    }
  });

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function card(d) {
    var a = el('a', 'deal-card-dribbble');
    a.href = '../' + d.id + '/';
    var imgWrap = el('div', 'card-image-wrapper');
    if (d.img) {
      var img = el('img');
      img.src = '../' + d.img;
      img.alt = d.title;
      img.loading = 'lazy';
      imgWrap.appendChild(img);
    }
    imgWrap.appendChild(el('span', 'card-discount-tag', d.disc || 'DEAL'));
    a.appendChild(imgWrap);
    var box = el('div', 'card-content-box');
    var meta = el('div', 'card-meta-row');
    meta.appendChild(el('span', 'card-brand-label', d.brand));
    meta.appendChild(el('span', 'card-category-label', d.cat));
    box.appendChild(meta);
    box.appendChild(el('h3', 'card-deal-title', d.title));
    var bottom = el('div', 'card-bottom-row');
    var prices = el('div', 'card-price-stack');
    prices.appendChild(el('span', 'card-current-price', d.price));
    bottom.appendChild(prices);
    bottom.appendChild(el('div', 'card-arrow-circle', '→'));
    box.appendChild(bottom);
    a.appendChild(box);
    return a;
  }

  function showEnded(section) {
    var main = document.querySelector('main');
    if (!main) return;
    var bar = el('div');
    bar.style.cssText = 'margin:16px auto;max-width:1100px;padding:14px 18px;border-radius:14px;' +
      'background:#FFF4E5;color:#7A3E00;font-weight:600;text-align:center;';
    bar.appendChild(document.createTextNode('This deal may have ended — prices change fast. '));
    var link = el('a', '', 'See live ' + (cat || 'deals') + ' below ↓');
    link.href = '#live-deals';
    link.style.cssText = 'color:#7A3E00;text-decoration:underline;';
    bar.appendChild(link);
    main.insertBefore(bar, main.firstChild);
  }

  fetch('../live.json', { cache: 'no-cache' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var deals = (data && data.deals) || [];
      var isLive = deals.some(function (d) { return d.id === pageId; });
      var others = deals.filter(function (d) { return d.id !== pageId; });
      var same = others.filter(function (d) { return d.cat === cat; });
      var rest = others.filter(function (d) { return d.cat !== cat; });
      var picks = same.concat(rest).slice(0, 8);

      var section = document.querySelector('.catalog-section');
      var grid = section && section.querySelector('.deals-grid-dribbble');
      if (grid && picks.length) {
        section.id = 'live-deals';
        grid.textContent = '';
        picks.forEach(function (d) { grid.appendChild(card(d)); });
        var heading = section.querySelector('.catalog-title');
        if (heading) heading.textContent = same.length ? 'Live Now in ' + cat + '.' : 'Live Deals Now.';
      }
      if (pageId && !isLive) showEnded(section);
    })
    .catch(function () { /* keep the static related deals */ });
})();
