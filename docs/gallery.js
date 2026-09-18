/* ============================================================================
   The gallery's own script.

   Two jobs. One is the page a person browses: the palette list, the four
   sections, the toolbar. The other is the four calls docs/capture.py makes
   to shoot it, which are the only reason this page is not a static file:

     shotNames()        every name in the catalogue, in the order they appear
     pose(name)         bring that one into view, and put it in its state
     shotRect(name)     where it ended up, in CSS pixels of the viewport
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

/* How much of what is around a shot comes with it. The shell parts and the
   window itself say data-pad="0" in the markup and take none. */
const PAD = 10;

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
    rect: function (r) { return union(r, box('.combopop')); },
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
};

function box(sel) {
  const el = document.querySelector(sel);
  return el ? el.getBoundingClientRect() : null;
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
  const p = POSES[posed];
  if (p) p.hide();
  clearTimeout(toastTimer);
  posed = '';
  setCleared(true);
  return 'clear';
}

/* Where the shot ended up, padded, in CSS pixels of the viewport. */
function shotRect(name) {
  const el = shotEl(name);
  if (!el) return '{}';
  const p = POSES[name];
  let r = el.getBoundingClientRect();
  if (p && p.rect) r = p.rect(r);
  const pad = el.dataset.pad === undefined ? PAD : Number(el.dataset.pad);
  return JSON.stringify({
    x: Math.round(r.left) - pad,
    y: Math.round(r.top) - pad,
    w: Math.round(r.width) + pad * 2,
    h: Math.round(r.height) + pad * 2,
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
  $('btnDefault').onclick = function () { setPalette('gold-dark'); };
  $('btnPrev').onclick = function () { stepPalette(-1); };
  $('btnNext').onclick = function () { stepPalette(1); };
  $('btnAbout').onclick = function () { beJson('appInfo', undefined, showInfo); };

  /* A file dropped on a page in an embedded browser makes the browser
     navigate to it, and the application is gone with no way back. */
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) { e.preventDefault(); });
}

function boot() {
  Bridge.init();
  initSelects();
  initTitlebar();

  Theme.read();
  buildPalettes();
  wire();
  setPalette(current);
  markSection(0);
  /* The progress card is a still, so it is set once and left there. */
  $('jobFill').style.transform = 'scaleX(' + Number($('jobPct').textContent) / 100 + ')';
}

boot();
