/* ============================================================================
   titlebar.js: the window's own title bar.

   The Qt window is frameless, so moving, resizing, minimising, maximising and
   closing it are the page's job. None of that is reimplemented here: the drag
   and the resize are handed straight back to the window manager through
   startSystemMove / startSystemResize on the Python side, which is what keeps
   Windows' snapping, edge magnetism, shadow and double click behaviour.

   The band's shape is clipped here instead of in CSS. Its lower profile,
   measured down from the top edge of the window, is:

     0            x1        x2                                    W
     ┌────────────────────────────────────────────────────────────┐  0
     │                        ·.                                  │
     │                          `·.____________________________   │  --tbar-thin
     │                                                            │
     └──────────────────────────┘                                 │  --tbar-h
       thick, under the name      the taper      thin, under the buttons

   so the band never stops: it only gets thinner. x1 is wherever the name ends,
   which is why this is computed from the real layout instead of guessed.

   Under the thin half, between the oblique and the right edge, the title
   bar's box shows below the band. That strip has no colour of its own: it is
   painted with whatever is under the title bar, measured along the line just
   below it, one run per colour. Over the step rail it is the rail, over a bare
   stage it is the stage, and never a stripe of its own between the two.

   The markup this file expects, all classes (css/layout.css draws them):

     .titlebar
       .tbar-band              the element the clip path goes on
       .tbar-brand             logo and name; its width is where the taper starts
         .tbar-logo            the mark, which setBrandAction() can make a button
       .tbar-drag
       .tbar-credit            written here when the page did not put one in
       .tbar-btns
         .wbtn.wbtn-min  .wbtn.wbtn-max  .wbtn.wbtn-close
     .rz[data-edge]            the eight resize strips, anywhere in the body

   And on the Python side, six slots on the bridge object and one signal:
   winDrag, winResize(edge), winMinimize, winMaximizeToggle, winClose,
   winIsMaximized, and windowMaximized(bool).

   The two drawings the maximise button swaps between are not here: they are
   `win-maximise` and `win-restore` in icons.js, like every other sign.

   Leaves on the window: initTitlebar, shapeTitleBar, setBrandAction,
   onWindowMaximized, roundedPolyPath, CREDIT_TEXT.
   ========================================================================== */

/* The licence's one condition. The text is fixed here and the size in
   css/layout.css, and both stay. */
const CREDIT_TEXT = 'Layout by Federico Salerno';


/* An SVG path through the points, with each corner rounded by its own `r`
   (a quadratic through the vertex, trimmed to half the shorter side). */
function roundedPolyPath(pts) {
  const n = pts.length;
  let d = '';
  for (let i = 0; i < n; i++) {
    const prev = pts[(i - 1 + n) % n], cur = pts[i], next = pts[(i + 1) % n];
    const r = cur.r || 0;
    if (r <= 0) {
      d += (i === 0 ? 'M' : 'L') + cur.x.toFixed(2) + ',' + cur.y.toFixed(2) + ' ';
      continue;
    }
    const v1x = prev.x - cur.x, v1y = prev.y - cur.y;
    const v2x = next.x - cur.x, v2y = next.y - cur.y;
    const l1 = Math.hypot(v1x, v1y) || 1, l2 = Math.hypot(v2x, v2y) || 1;
    const a = Math.min(r, l1 / 2), b = Math.min(r, l2 / 2);
    const p1x = cur.x + v1x / l1 * a, p1y = cur.y + v1y / l1 * a;
    const p2x = cur.x + v2x / l2 * b, p2y = cur.y + v2y / l2 * b;
    d += (i === 0 ? 'M' : 'L') + p1x.toFixed(2) + ',' + p1y.toFixed(2) + ' ';
    d += 'Q' + cur.x.toFixed(2) + ',' + cur.y.toFixed(2) + ' ' +
         p2x.toFixed(2) + ',' + p2y.toFixed(2) + ' ';
  }
  return d + 'Z';
}

/* Cut the band to that profile. Called at start up and on every resize, since
   both the window width and the width of the name decide the shape. */
function shapeTitleBar() {
  const bar = document.querySelector('.titlebar');
  if (!bar) return;
  const band = bar.querySelector('.tbar-band');
  const brand = bar.querySelector('.tbar-brand');
  if (!band || !brand) return;

  const cs = getComputedStyle(document.documentElement);
  const num = function (name, fallback) {
    const v = parseFloat(cs.getPropertyValue(name));
    return isNaN(v) ? fallback : v;
  };
  const W = bar.clientWidth;
  const h1 = bar.clientHeight;
  const h2 = num('--tbar-thin', 28);
  const slant = num('--tbar-slant', 38);
  const join = num('--tbar-join', 8);

  const x1 = Math.round(brand.getBoundingClientRect().width);
  const x2 = Math.min(W, x1 + slant);

  const pts = [
    { x: 0, y: 0 },                 // window corner
    { x: W, y: 0 },                 // window corner
    { x: W, y: h2 },                // the thin end, flush with the right edge
    { x: x2, y: h2, r: join },      // top of the taper
    { x: x1, y: h1, r: join },      // bottom of the taper
    { x: 0, y: h1 },                // window corner
  ];
  const d = roundedPolyPath(pts);

  // clip-path: path() needs a recent Chromium (Qt 6). On the Qt 5 fallback the
  // same profile is used without the rounded joints.
  if (window.CSS && CSS.supports && CSS.supports('clip-path', 'path("M0 0")')) {
    band.style.clipPath = 'path("' + d + '")';
  } else {
    band.style.clipPath = 'polygon(' + pts.map(function (p) {
      return p.x + 'px ' + p.y + 'px';
    }).join(',') + ')';
  }
  _paintStrip(bar, x1);
}

/* ── the strip under the thin half ─────────────────────────────────────── */
/* What a point just under the title bar looks like: the fills of everything
   stacked there, front to back, laid over one another until one of them is
   opaque. Nothing inside the title bar counts, and nothing the page has made
   invisible either: an element at opacity 0 is still hit by elementsFromPoint
   but paints nothing. Returns a CSS colour. */
function _colourUnder(bar, x, y, fills) {
  const stack = document.elementsFromPoint(x, y);
  let r = 0, g = 0, b = 0, a = 0;
  for (let i = 0; i < stack.length && a < 0.999; i++) {
    const el = stack[i];
    if (bar.contains(el)) continue;
    if (!fills.has(el)) fills.set(el, _fillOf(el));
    const c = fills.get(el);
    if (!c) continue;
    const k = (1 - a) * c[3];
    r += c[0] * k; g += c[1] * k; b += c[2] * k; a += k;
  }
  if (a <= 0) return 'transparent';
  return 'rgba(' + Math.round(r / a) + ',' + Math.round(g / a) + ',' +
         Math.round(b / a) + ',' + (+a.toFixed(3)) + ')';
}

/* An element's own fill as [r, g, b, a], its alpha taken down by its opacity
   and every ancestor's, or null when it paints nothing. */
function _fillOf(el) {
  const m = /rgba?\(([^)]*)\)/.exec(getComputedStyle(el).backgroundColor || '');
  if (!m) return null;
  const v = m[1].split(/[\s,\/]+/).filter(function (s) { return s.length; }).map(parseFloat);
  let alpha = v.length > 3 ? v[3] : 1;
  for (let n = el; n && n.nodeType === 1 && alpha > 0; n = n.parentNode) {
    alpha *= parseFloat(getComputedStyle(n).opacity);
  }
  return alpha > 0 ? [v[0], v[1], v[2], alpha] : null;
}

/* Paint the strip. The line just under the bar is read every 16 px from the
   foot of the oblique to the right edge, and where two readings differ the
   edge between them is found to half a pixel, so a column under the band
   gets a run exactly as wide as itself. One colour is a fill, several are a
   gradient of hard stops. Where the engine cannot tell (no elementsFromPoint)
   the bar keeps the fill layout.css gives it. */
function _paintStrip(bar, x1) {
  if (!document.elementsFromPoint) return;
  const box = bar.getBoundingClientRect();
  const y = box.bottom + 0.5;
  if (box.width <= 0 || y >= window.innerHeight) return;
  const fills = new Map();
  const at = function (x) { return _colourUnder(bar, box.left + x, y, fills); };
  // The engine rounds a hit test to whole pixels, and half a pixel short of
  // the right edge rounds out of the page, so the last reading is a pixel in.
  const last = box.width - 1;
  let from = Math.max(0.5, Math.min(last, x1 - 16));
  let colour = at(from);
  const runs = [[colour, 0]];
  for (let x = from + 16; from < last; x += 16) {
    const to = Math.min(x, last);
    const c = at(to);
    if (c !== colour) {
      let lo = from, hi = to;
      while (hi - lo > 0.5) {
        const mid = (lo + hi) / 2;
        if (at(mid) === colour) lo = mid; else hi = mid;
      }
      colour = at(hi);
      runs.push([colour, Math.round(hi)]);
      // Past the edge the reading starts again from where it was found.
      from = hi;
      x = hi;
      continue;
    }
    from = to;
  }
  if (runs.length === 1) {
    bar.style.background = runs[0][0];
    return;
  }
  bar.style.background = 'linear-gradient(to right,' + runs.map(function (run, i) {
    const end = i + 1 < runs.length ? runs[i + 1][1] + 'px' : '100%';
    return run[0] + ' ' + run[1] + 'px ' + end;
  }).join(',') + ')';
}

/* The credit line. Whatever the page put in .tbar-credit, or did not, the
   element ends up there with the licence's text in it. */
function _ensureCredit(bar) {
  let el = bar.querySelector('.tbar-credit');
  if (!el) {
    el = document.createElement('span');
    el.className = 'tbar-credit';
    const btns = bar.querySelector('.tbar-btns');
    if (btns) bar.insertBefore(el, btns);
    else bar.appendChild(el);
  }
  el.textContent = CREDIT_TEXT;
  return el;
}

function _wireButton(bar, cls, slot) {
  const btn = bar.querySelector(cls);
  if (btn) btn.onclick = function () { be(slot); };
}

/* A press on one of these is a press on a control, and never the start of a
   window move: the three window buttons, and the mark once the application
   has made it a button. Two calls instead of one selector list, because
   `closest` is given one plain class everywhere in this file. */
function _isControl(el) {
  return !!(el && (el.closest('.wbtn') || el.closest('.tbar-logo-btn')));
}

/* The mark, made into a button. Registering an action is what creates it: a
   page that registers nothing keeps the plain mark, because a button that
   answers the pointer and then does nothing is worse than no button.

   What pressing it means is the application's, and so is the hint, which it
   passes in its own words. The library knows there is a mark on the band; it
   does not know what is behind it. Pass no function to take the action back
   and the mark goes back to being a mark.

   Returns the button, or null when there is none to make or none left. */
function setBrandAction(fn, hint) {
  const bar = document.querySelector('.titlebar');
  const brand = bar && bar.querySelector('.tbar-brand');
  const logo = brand && brand.querySelector('.tbar-logo');
  if (!logo) return null;
  let btn = brand.querySelector('.tbar-logo-btn');
  if (typeof fn !== 'function') {
    if (btn) {
      brand.insertBefore(logo, btn);
      brand.removeChild(btn);
      shapeTitleBar();
    }
    return null;
  }
  if (!btn) {
    btn = document.createElement('button');
    btn.className = 'tbar-logo-btn';
    btn.setAttribute('type', 'button');
    brand.insertBefore(btn, logo);
    brand.removeChild(logo);
    btn.appendChild(logo);
    shapeTitleBar();
  }
  /* Called with nothing: what the application registered is its own business
     and takes no event from here. */
  btn.onclick = function () { fn(); };
  if (hint) {
    btn.title = hint;
    btn.setAttribute('aria-label', hint);
  } else {
    btn.title = '';
    btn.removeAttribute('aria-label');
  }
  return btn;
}

function initTitlebar() {
  const bar = document.querySelector('.titlebar');
  if (!bar) return;
  _ensureCredit(bar);

  /* Anywhere on the bar except a control starts a system move. */
  bar.addEventListener('mousedown', function (e) {
    if (e.button !== 0 || _isControl(e.target)) return;
    e.preventDefault();
    be('winDrag');
  });
  bar.addEventListener('dblclick', function (e) {
    if (_isControl(e.target)) return;
    be('winMaximizeToggle');
  });

  _wireButton(bar, '.wbtn-min', 'winMinimize');
  _wireButton(bar, '.wbtn-max', 'winMaximizeToggle');
  _wireButton(bar, '.wbtn-close', 'winClose');

  const edges = document.querySelectorAll('.rz');
  for (let i = 0; i < edges.length; i++) {
    edges[i].addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      be('winResize', this.dataset.edge);
    });
  }

  shapeTitleBar();
  // Once more after the first frame: the name's width is only final after layout.
  requestAnimationFrame(shapeTitleBar);
  window.addEventListener('resize', shapeTitleBar);
  _watchUnder(bar);

  Bridge.on('windowMaximized', onWindowMaximized);
  be('winIsMaximized', onWindowMaximized);
}

/* What is under the band changes without the window changing size: a row is
   shown or hidden, a class moves the page from one screen to the next, the
   palette changes, a fill fades in. Each of those asks for the shape again,
   at most once a frame. Nothing here
   watches inline styles, so the page can animate what it likes under the
   band without the strip being measured on every frame of it. */
function _watchUnder(bar) {
  let asked = false;
  const again = function () {
    if (asked) return;
    asked = true;
    requestAnimationFrame(function () { asked = false; shapeTitleBar(); });
  };
  const rows = bar.parentNode;
  if (typeof MutationObserver === 'function' && rows) {
    const mo = new MutationObserver(function (list) {
      for (let i = 0; i < list.length; i++) {
        if (!bar.contains(list[i].target)) { again(); return; }
      }
    });
    mo.observe(rows, { subtree: true, childList: true, attributes: true,
                       attributeFilter: ['class', 'hidden'] });
    mo.observe(document.documentElement, { attributes: true,
                                           attributeFilter: ['data-palette'] });
  }
  if (typeof ResizeObserver === 'function' && rows) {
    const ro = new ResizeObserver(again);
    for (let i = 0; i < rows.children.length; i++) {
      if (rows.children[i] !== bar) ro.observe(rows.children[i]);
    }
  }
  if (document.addEventListener) {
    document.addEventListener('transitionend', function (e) {
      if (!bar.contains(e.target)) again();
    });
  }
}

/* Qt says when the window was maximised or restored, including when it was
   Windows that did it (snap, Win+Up, double click). */
function onWindowMaximized(max) {
  document.body.classList.toggle('maximized', !!max);
  const btn = document.querySelector('.titlebar .wbtn-max');
  if (btn) {
    btn.title = max ? 'Restore' : 'Maximise';
    setIcon(btn, max ? 'win-restore' : 'win-maximise');
  }
  shapeTitleBar();
}
