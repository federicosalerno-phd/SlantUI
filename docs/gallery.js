/* ============================================================================
   The gallery's own script.

   Two jobs. One is the page a person browses: the palette list, the four
   sections, the toolbar. The other is the six calls docs/capture.py makes
   to shoot it, which are the only reason this page is not a static file:

     shotNames()        every name in the catalogue, in the order they appear
     pose(name)         bring that one into view, and put it in its state
     isolate(name)      take the page out from under it, so the crop is it
     shotRect(name)     where it ended up, in CSS pixels of the viewport
     unisolate()        put the page back
     unpose()           take the state back off

   A shot is an element carrying data-shot. Four of them are states no markup
   can hold by itself: the dropdown's popup exists only while it is open, and
   the toast and the two scrim cards belong to the window and not to a
   cell. Those have an entry in POSES below.

   Everything this file calls that is not in it comes from SlantUI: Bridge
   and be() and beJson() from bridge.js, Theme from theme.js, initSelects()
   numStep() fitOneLine() from widgets.js, initTitlebar() from titlebar.js.
   ========================================================================== */

/* The eight palettes, in the order of slantui/tokens/palettes.py. A test
   keeps this list and the Python one the same. */
const PALETTES = [
  { name: 'Gold Dark', slug: 'gold-dark', scheme: 'dark' },
  { name: 'Gold Light', slug: 'gold-light', scheme: 'light' },
  { name: 'Teal Dark', slug: 'teal-dark', scheme: 'dark' },
  { name: 'Blue Dark', slug: 'blue-dark', scheme: 'dark' },
  { name: 'Purple Dark', slug: 'purple-dark', scheme: 'dark' },
  { name: 'Green Dark', slug: 'green-dark', scheme: 'dark' },
  { name: 'Slate Light', slug: 'slate-light', scheme: 'light' },
  { name: 'High Contrast', slug: 'high-contrast', scheme: 'dark' },
];

/* The clear margin left around a shot, in CSS pixels. It is there for the
   half pixel a glyph or a rounded corner fades out over, not for looks: what
   a picture is cropped to is what the shot paints and nothing else. The shell
   parts and the window itself say data-pad="0" in the markup and take none. */
const PAD = 4;

const GROUP_ROLE = { accent: 'accent-text', ok: 'ok-text' };

const HINTS = [
  'The window itself: the band, the rail, this strip, and the panel',
  'Fills and no outlines, and no state that needs a pointer on it',
  'What a side panel is built out of',
  'The overlays, shot from the live window',
];

let current = 'gold-dark';      // the palette on screen
let posed = '';                 // the shot whose state is up, if any
let section = 0;                // which of the four the rail points at
let toastTimer = null;

function $(id) { return document.getElementById(id); }

/* ── the shots ────────────────────────────────────────────────────────────── */
function shotEl(name) {
  return document.querySelector('[data-shot="' + name + '"]');
}

function shotNames() {
  const out = [];
  document.querySelectorAll('[data-shot]').forEach(function (el) {
    out.push(el.dataset.shot);
  });
  return JSON.stringify(out);
}

/* The states a shot cannot be left sitting in. Each entry shows it, hides it
   again, and says which rectangle to take when the element's own is not the
   whole of what appeared. */
const POSES = {
  'dropdown-open': {
    show: function () { $('comboOpen').click(); },
    /* widgets.js closes the popup on a mousedown anywhere else, in the
       capture phase, so that is what has to reach it. */
    hide: function () {
      document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    },
    /* The popup is a child of the body, so it is not under the shot and has
       to be named to survive the isolation. */
    keep: ['.combopop'],
    rect: function (r) { return union(r, ink('.combopop')); },
  },
  'toast': {
    show: function () { showToast('A line at the bottom, and then gone'); },
    hide: function () { $('toast').classList.remove('show'); },
  },
  'spinner': {
    show: function () { $('busy').classList.add('show'); },
    hide: function () { $('busy').classList.remove('show'); },
  },
  'progress': {
    show: function () { $('job').classList.add('show'); },
    hide: function () { $('job').classList.remove('show'); },
  },
  /* The library places it, from the first of the two question marks in the
     catalogue, and what it says is the markup's own. Then `on` goes on by
     hand: openSheet waits a frame for it and a shot has no frames to wait. */
  'sheet': {
    show: function () {
      const s = $('sheet');
      const more = document.querySelectorAll('.more')[0];
      more.scrollIntoView({ block: 'center' });
      openSheet(more, $('sheetTitle').textContent,
                s.querySelector('.sheet-body').innerHTML,
                s.querySelector('.sheet-fig').innerHTML);
      s.classList.add('on');
    },
    hide: function () {
      closeSheet();
      $('sheet').classList.remove('on');
      $('sheet').classList.remove('show');
    },
  },
  /* The lit mark. `on` is the library's own rule, the same one :hover uses,
     so the catalogue cannot show a state the pointer does not produce. */
  'titlebar-mark': {
    show: function () { markInCell().classList.add('on'); },
    hide: function () { markInCell().classList.remove('on'); },
  },
  /* The docked one has nowhere to be put: it takes its place from the shell. */
  'sheet-side': {
    show: function () { $('sheetSide').classList.add('show'); $('sheetSide').classList.add('on'); },
    hide: function () { $('sheetSide').classList.remove('on'); $('sheetSide').classList.remove('show'); },
  },
};

/* The mark in the catalogue's cell, not the one on the real band above it:
   the page carries two, and the shot is the cell. */
function markInCell() {
  return shotEl('titlebar-mark').querySelector('.tbar-logo-btn');
}

function union(a, b) {
  if (!b) return a;
  const x = Math.min(a.left, b.left), y = Math.min(a.top, b.top);
  return {
    left: x, top: y,
    right: Math.max(a.right, b.right), bottom: Math.max(a.bottom, b.bottom),
    width: Math.max(a.right, b.right) - x, height: Math.max(a.bottom, b.bottom) - y,
  };
}

/* Bring a shot into view and put it in its state. The answer goes back to
   the caller, so the Python knows the page is done before it grabs. */
function pose(name) {
  unpose();
  const el = shotEl(name);
  if (!el) return 'missing';
  if ($('gal').contains(el)) el.scrollIntoView({ block: 'center' });
  else $('gal').scrollTop = 0;        // the shell parts, with the page at its top
  const p = POSES[name];
  if (p) {
    p.show();
    posed = name;
    setCleared(false);
  }
  return name;
}

function unpose() {
  unisolate();
  const p = POSES[posed];
  if (p) p.hide();
  clearTimeout(toastTimer);
  posed = '';
  setCleared(true);
  return 'clear';
}

/* ── taking the page out from under a shot ────────────────────────────────── */
/* A picture of a widget is the widget. What it happened to be standing on is
   the page, and the page is not in the picture: the cell it sits in, the
   catalogue behind the cell, the window behind the catalogue, and the widget
   in the next cell along.

   So every ancestor of the shot gives up its fill, and everything that is
   neither the shot nor an ancestor of it is made invisible. Nothing moves,
   because visibility keeps the layout: the rectangle measured under the
   isolation is the rectangle the page had before it. capture.py clears the
   colour behind the page at the same time, so what is left under the widget
   is the empty frame, and the grab comes back with the corners Chromium
   antialiased against nothing at all. */
let dressed = [];               // [element, its own style] of everything moved

function ancestors(el) {
  const out = [];
  for (let n = el.parentElement; n; n = n.parentElement) out.push(n);
  return out;
}

function isolate(name) {
  unisolate();
  const el = shotEl(name);
  if (!el) return 'missing';
  const p = POSES[name];
  const shot = [el];
  ((p && p.keep) || []).forEach(function (sel) {
    document.querySelectorAll(sel).forEach(function (k) { shot.push(k); });
  });

  const inside = new Set(shot);          // the shot itself: left alone
  const above = new Set();               // its ancestors: emptied, walked into
  shot.forEach(function (k) {
    ancestors(k).forEach(function (n) { above.add(n); });
  });

  above.forEach(function (n) {
    dressed.push([n, n.style.cssText]);
    n.style.setProperty('background', 'transparent', 'important');
    n.style.setProperty('box-shadow', 'none', 'important');
  });

  (function sweep(node) {
    for (let i = 0; i < node.children.length; i++) {
      const c = node.children[i];
      if (inside.has(c)) continue;
      if (above.has(c)) { sweep(c); continue; }
      dressed.push([c, c.style.cssText]);
      c.style.setProperty('visibility', 'hidden', 'important');
    }
  })(document.documentElement);

  // A picture cannot carry a movement, and a grab lands wherever the clock
  // happens to be: the spinner's ring came out at a different angle every
  // run, and a band crossing a track could be off the end of it entirely.
  // So anything animating inside the shot is stopped, on the same frame
  // every time, a third of the way through whatever its own duration is.
  // unisolate puts the style attributes back, so the page keeps moving.
  shot.forEach(function (k) {
    const all = [k].concat(Array.prototype.slice.call(k.querySelectorAll('*')));
    all.forEach(function (n) {
      const cs = getComputedStyle(n);
      if (!cs.animationName || cs.animationName === 'none') return;
      dressed.push([n, n.style.cssText]);
      n.style.setProperty('animation-delay',
                          (-0.35 * (parseFloat(cs.animationDuration) || 0)) + 's', 'important');
      n.style.setProperty('animation-play-state', 'paused', 'important');
    });
  });

  return name;
}

function unisolate() {
  for (let i = dressed.length - 1; i >= 0; i--) {
    dressed[i][0].style.cssText = dressed[i][1];
  }
  dressed = [];
  return 'dressed';
}

/* ── what a shot covers ───────────────────────────────────────────────────── */
/* The crop is the ink, not the box. A row of three buttons is a block as wide
   as the column it stands in, and cropping to that block would leave the
   buttons off centre in the picture with transparency making up the rest. So
   the rectangle is the union of everything under the shot that paints: a
   fill, a background image, a border, a shadow, a glyph. */
const CLEAR = /^(transparent|rgba\(0,\s*0,\s*0,\s*0\))$/;
const SIDES = ['Top', 'Right', 'Bottom', 'Left'];
const DRAWN = /^(IMG|SVG|CANVAS|VIDEO|INPUT|SELECT|TEXTAREA)$/;

function paints(el, cs) {
  if (!CLEAR.test(cs.backgroundColor)) return true;
  if (cs.backgroundImage !== 'none') return true;
  if (cs.boxShadow !== 'none') return true;
  if (DRAWN.test(el.tagName.toUpperCase())) return true;
  return SIDES.some(function (s) {
    return parseFloat(cs['border' + s + 'Width']) > 0
      && cs['border' + s + 'Style'] !== 'none'
      && !CLEAR.test(cs['border' + s + 'Color']);
  });
}

/* A shadow paints outside the element it belongs to. Chromium writes the
   computed value as "colour x y blur spread", and an inset one paints
   nothing outside at all.

   A blur of n is a gaussian of half that, and a gaussian is not finished at
   one standard deviation: cropping at the blur leaves the tail of the shadow
   cut off square, which on a transparent picture is a faint rectangle around
   the widget. Three halves of it is past the last pixel that carries any. */
function shadowed(cs, r) {
  if (cs.boxShadow === 'none') return r;
  let out = r;
  cs.boxShadow.split(/,(?![^(]*\))/).forEach(function (one) {
    if (one.indexOf('inset') >= 0) return;
    const n = (one.replace(/\w+\([^)]*\)/g, ' ').match(/-?[\d.]+px/g) || [])
      .map(parseFloat);
    if (n.length < 2) return;
    const grow = (n[2] || 0) * 1.5 + (n[3] || 0);
    out = union(out, {
      left: r.left + n[0] - grow, top: r.top + n[1] - grow,
      right: r.right + n[0] + grow, bottom: r.bottom + n[1] + grow,
    });
  });
  return out;
}

/* The lines of text an element holds itself. A line box is the glyphs plus
   the leading above and below them, which is the room a line of type asks
   for and the right thing to crop to. */
function lines(el, out) {
  for (let i = 0; i < el.childNodes.length; i++) {
    const n = el.childNodes[i];
    if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const list = range.getClientRects();
    for (let k = 0; k < list.length; k++) {
      if (list[k].width > 0 && list[k].height > 0) out = union(out || list[k], list[k]);
    }
  }
  return out;
}

/* What an element hides is not ink. The side panel is a column with its body
   scrolling inside it, so the rows below the fold are laid out and drawn
   nowhere: an element that clips passes its own rectangle down, and what its
   children paint is counted only where the two meet. */
function cut(r, c) {
  if (!c || !r) return r;
  const left = Math.max(r.left, c.left), top = Math.max(r.top, c.top);
  const right = Math.min(r.right, c.right), bottom = Math.min(r.bottom, c.bottom);
  if (right <= left || bottom <= top) return null;
  return { left: left, top: top, right: right, bottom: bottom,
           width: right - left, height: bottom - top };
}

function inkRect(el) {
  let out = null;
  const add = function (r) { if (r) out = union(out || r, r); };
  (function walk(node, clip) {
    const cs = getComputedStyle(node);
    if (cs.display === 'none' || cs.visibility === 'hidden'
        || parseFloat(cs.opacity) === 0) return;
    if (cs.position === 'fixed') clip = null;
    const r = node.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && paints(node, cs)) {
      add(cut(shadowed(cs, r), clip));
    }
    const text = lines(node, null);
    if (text) add(cut(text, clip));
    if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
      clip = cut(r, clip);
      /* Nothing of it is on screen, so nothing under it is either. The side
         panel's body is a column of rows and only the first few are in the
         window; walking into one that is wholly below the fold with no
         rectangle left to clip it against is what once made the picture of
         the window half as tall again as the window. */
      if (!clip) return;
    }
    for (let i = 0; i < node.children.length; i++) walk(node.children[i], clip);
  })(el, null);
  return out || el.getBoundingClientRect();
}

function ink(sel) {
  const el = document.querySelector(sel);
  return el ? inkRect(el) : null;
}

/* Where the shot ended up, padded, in CSS pixels of the viewport. Whole
   pixels, and outwards, so that a scale of two or three lands the crop on
   pixel boundaries of the grab and no edge is resampled. */
function shotRect(name) {
  const el = shotEl(name);
  if (!el) return '{}';
  const p = POSES[name];
  let r = inkRect(el);
  if (p && p.rect) r = p.rect(r);
  const pad = el.dataset.pad === undefined ? PAD : Number(el.dataset.pad);
  const x = Math.floor(r.left) - pad;
  const y = Math.floor(r.top) - pad;
  return JSON.stringify({
    x: x, y: y,
    w: Math.ceil(r.right) + pad - x,
    h: Math.ceil(r.bottom) + pad - y,
  });
}

/* ── the palette ──────────────────────────────────────────────────────────── */
function buildPalettes() {
  const host = $('palettes');
  PALETTES.forEach(function (p) {
    const row = document.createElement('div');
    row.className = 'mitem' + (p.slug === current ? ' sel' : '');
    row.dataset.slug = p.slug;
    row.innerHTML = '<span class="mitem-name"></span><span class="mbadge"></span>';
    row.querySelector('.mitem-name').textContent = p.name;
    row.querySelector('.mbadge').textContent = p.scheme.toUpperCase();
    row.onclick = function () { setPalette(p.slug); };
    host.appendChild(row);
  });
}

function paletteAt(slug) {
  for (let i = 0; i < PALETTES.length; i++) {
    if (PALETTES[i].slug === slug) return PALETTES[i];
  }
  return PALETTES[0];
}

/* The page and the window move together: Theme puts the slug on <html>,
   where palettes.css keys on it, and the slot moves the colour behind the
   page, which is what shows in the strip a live resize has not painted yet. */
function setPalette(slug) {
  current = paletteAt(slug).slug;
  Theme.setPalette(current);
  be('setPalette', current);
  document.querySelectorAll('#palettes .mitem').forEach(function (row) {
    row.classList.toggle('sel', row.dataset.slug === current);
  });
  const p = paletteAt(current);
  $('st').textContent = p.name;
  fitOneLine($('fname'), 'docs/shots/' + p.slug, 11.5, 9);
  paint();
  return current;
}

function stepPalette(d) {
  let i = 0;
  PALETTES.forEach(function (p, n) { if (p.slug === current) i = n; });
  setPalette(PALETTES[(i + d + PALETTES.length) % PALETTES.length].slug);
}

/* The light twin of a dark palette, and the way back. */
function otherScheme() {
  const dark = paletteAt(current).scheme === 'dark';
  setPalette(dark ? 'gold-light' : 'gold-dark');
}

/* Everything that holds a colour as a value instead of as a role. Here that
   is only the group headings and the bar on the active metric row. */
function paint() {
  document.querySelectorAll('.mg').forEach(function (h) {
    h.style.color = Theme.get(GROUP_ROLE[h.dataset.group]);
  });
  document.querySelectorAll('.mrow').forEach(function (r) {
    r.style.setProperty('--gc', Theme.get(GROUP_ROLE[r.dataset.group]));
  });
}

/* ── the rail and the toolbar ─────────────────────────────────────────────── */
function goSection(i) {
  section = i;
  const sec = document.querySelector('.gal-sec[data-sec="' + i + '"]');
  if (sec) $('gal').scrollTop = sec.offsetTop - 12;
  markSection(i);
}

function markSection(i) {
  document.querySelectorAll('.tab[data-sec]').forEach(function (t) {
    const n = Number(t.dataset.sec);
    t.classList.toggle('active', n === i);
    t.classList.toggle('done', n < i);
  });
  $('cthint').textContent = HINTS[i];
}

/* Which section the catalogue is showing, as it scrolls. */
function onScroll() {
  const top = $('gal').scrollTop + 40;
  let i = 0;
  document.querySelectorAll('.gal-sec').forEach(function (sec, n) {
    if (sec.offsetTop <= top) i = n;
  });
  if (i !== section) {
    section = i;
    markSection(i);
  }
}

function toggleNames() {
  const on = $('ctNames').classList.toggle('on');
  document.querySelectorAll('.gal-name').forEach(function (el) {
    el.classList.toggle('hidden', !on);
  });
}

/* The red toolbar button keeps its space and appears only while there is
   something to clear. */
function setCleared(clear) {
  $('ctClear').classList.toggle('ghost', clear);
}

function showToast(text) {
  const el = $('toast');
  el.textContent = text;
  el.classList.add('show');
  posed = 'toast';
  setCleared(false);
  clearTimeout(toastTimer);
  /* The capture takes the toast down itself, so the timer is only for a
     person browsing the page. */
  toastTimer = setTimeout(function () { unpose(); }, 2600);
}

function showInfo(info) {
  if (!info) return;
  const text = 'SlantUI ' + info.slantui + ' on ' + info.binding +
               ', Qt ' + info.qt + ', Python ' + info.python;
  $('btnAbout').title = text;
  showToast(text);
}

/* ── wiring ───────────────────────────────────────────────────────────────── */
function wire() {
  document.querySelectorAll('.tab[data-sec]').forEach(function (t) {
    t.onclick = function () { goSection(Number(t.dataset.sec)); };
  });
  document.querySelectorAll('[data-pose]').forEach(function (b) {
    b.onclick = function () { pose(b.dataset.pose); };
  });
  document.querySelectorAll('.spin-b').forEach(function (b) {
    b.onclick = function () { numStep(b.dataset.stepFor, Number(b.dataset.dir)); };
  });
  document.querySelectorAll('.scrim').forEach(function (s) {
    s.onclick = unpose;
  });
  document.querySelectorAll('.mrow').forEach(function (r) {
    r.onclick = function () {
      document.querySelectorAll('.mrow').forEach(function (o) { o.classList.remove('active'); });
      r.classList.add('active');
    };
  });

  $('gal').addEventListener('scroll', onScroll);
  $('ctNames').onclick = toggleNames;
  $('ctTwin').onclick = otherScheme;
  $('ctTop').onclick = function () { goSection(0); };
  $('ctClear').onclick = unpose;
  $('sheetSideClose').onclick = unpose;
  $('btnDefault').onclick = function () { setPalette('gold-dark'); };
  $('btnPrev').onclick = function () { stepPalette(-1); };
  $('btnNext').onclick = function () { stepPalette(1); };
  $('btnAbout').onclick = function () { beJson('appInfo', undefined, showInfo); };

  /* A file dropped on a page in an embedded browser makes the browser
     navigate to it, and the application is gone with no way back. */
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) { e.preventDefault(); });
}

/* The icon cell fills itself from ICONS, so a name added to the library shows
   up here without anyone remembering to add a tile. A sign that is still a
   character out of the font says so under itself: that is the list of what is
   left to draw, and it shortens on its own. */
function buildIcons() {
  const box = $('iconSet');
  if (!box) return;
  const names = Object.keys(ICONS).sort();
  box.innerHTML = names.map(function (n) {
    const e = ICONS[n];
    const glyph = (e && e.g) ? e.g : '';
    return '<div class="gal-icon' + (glyph ? ' gal-icon-raw' : '') + '">'
      + '<span class="gal-icon-m">' + icon(n) + '</span>'
      + '<span class="gal-icon-n">' + n + '</span></div>';
  }).join('');
}

function boot() {
  Bridge.init();
  initSelects();
  initTitlebar();

  Theme.read();
  buildIcons();
  buildPalettes();
  wire();
  setPalette(current);
  markSection(0);
  /* The progress card is a still, so it is set once and left there. */
  $('jobFill').style.transform = 'scaleX(' + Number($('jobPct').textContent) / 100 + ')';
}

boot();
