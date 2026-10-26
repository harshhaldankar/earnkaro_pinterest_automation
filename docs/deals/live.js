(function () {
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
