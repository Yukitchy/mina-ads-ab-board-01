/* devbar.js — dev-only device preview toggle (PC / スマホ).
 *
 * Drop <script src="devbar.js"></script> at the end of <body>. It shows a small
 * floating control that re-renders the SAME page inside a phone-sized iframe, so
 * CSS media queries actually fire — unlike simply narrowing the body, which does
 * not change the viewport and therefore does not trigger @media rules.
 *
 * It only appears on localhost / file:// / ?dev=1, so it never ships to a real
 * visitor. Reusable as-is in any project.
 */
(function () {
  var q = new URLSearchParams(location.search);

  // The inner copy must not draw its own devbar (that would recurse).
  if (q.has('noframe')) return;

  var isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) ||
                location.protocol === 'file:';
  // ?dev=1 sticks to this browser so Yuuki does not have to retype it; ?dev=0 turns it off.
  var sticky = false;
  try {
    if (q.get('dev') === '0') { localStorage.removeItem('devbar'); }
    else if (q.has('dev')) { localStorage.setItem('devbar', '1'); }
    sticky = localStorage.getItem('devbar') === '1';
  } catch (e) {}
  if (!isLocal && !q.has('dev') && !sticky && !window.DEVBAR_FORCE) return;

  var DEVICES = {
    sp: { w: 390, h: 844, label: 'iPhone 390×844' },
    tablet: { w: 768, h: 1024, label: 'iPad 768×1024' }
  };

  var css = document.createElement('style');
  css.textContent = [
    '#devbar{position:fixed;right:14px;bottom:14px;z-index:2147483000;display:flex;gap:3px;',
      'padding:4px;border-radius:999px;background:rgba(18,26,34,.92);backdrop-filter:blur(8px);',
      'box-shadow:0 6px 24px rgba(0,0,0,.3);font:600 12px/1 -apple-system,BlinkMacSystemFont,sans-serif}',
    '#devbar button{appearance:none;border:0;background:transparent;color:#9FB4C4;cursor:pointer;',
      'padding:8px 13px;border-radius:999px;font:inherit;transition:background .14s,color .14s}',
    '#devbar button.on{background:#3E9BD6;color:#fff}',
    '#devbar button:hover:not(.on){color:#fff}',
    '#devstage{position:fixed;inset:0;z-index:2147482000;display:none;place-items:center;',
      'background:#1A2530;padding:28px 16px;overflow:auto}',
    '#devstage.show{display:grid}',
    '#devstage .phone{background:#0B1218;border-radius:38px;padding:10px;flex:none;',
      'box-shadow:0 24px 60px rgba(0,0,0,.5)}',
    '#devstage iframe{display:block;border:0;border-radius:29px;background:#fff}',
    '#devstage .cap{position:fixed;top:12px;left:0;right:0;text-align:center;color:#7E93A3;',
      'font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.12em}',
    'html.devframe body{overflow:hidden}'
  ].join('');
  document.head.appendChild(css);

  var stage = document.createElement('div');
  stage.id = 'devstage';
  stage.innerHTML = '<p class="cap"></p><div class="phone"><iframe title="Device preview"></iframe></div>';
  document.body.appendChild(stage);

  var bar = document.createElement('div');
  bar.id = 'devbar';
  bar.innerHTML =
    '<button data-dev="pc" class="on" type="button">PC</button>' +
    '<button data-dev="sp" type="button">スマホ</button>' +
    '<button data-dev="tablet" type="button">タブレット</button>';
  document.body.appendChild(bar);

  var frame = stage.querySelector('iframe');
  var cap = stage.querySelector('.cap');

  function innerURL() {
    var u = new URL(location.href);
    u.searchParams.set('noframe', '1');
    return u.toString();
  }

  function setMode(mode) {
    var d = DEVICES[mode];
    [].forEach.call(bar.querySelectorAll('button'), function (b) {
      b.classList.toggle('on', b.dataset.dev === mode);
    });

    if (!d) {
      stage.classList.remove('show');
      document.documentElement.classList.remove('devframe');
      frame.src = 'about:blank';
      return;
    }
    frame.width = d.w;
    frame.height = d.h;
    frame.style.width = d.w + 'px';
    frame.style.height = d.h + 'px';
    cap.textContent = d.label + '  ·  ESC or PC to exit';
    if (frame.src === 'about:blank' || !frame.src) frame.src = innerURL();
    stage.classList.add('show');
    document.documentElement.classList.add('devframe');
  }

  bar.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (b) setMode(b.dataset.dev);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && stage.classList.contains('show')) setMode('pc');
  });

  // Click the dark surround to leave preview.
  stage.addEventListener('click', function (e) {
    if (e.target === stage) setMode('pc');
  });
})();
