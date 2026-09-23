/* ============================================================================
   icons.js: the named signs a window is made of.

   A window says the same dozen things in every application: close me, open a
   file, undo that, this went wrong. Before this file each of those was an
   `<svg>` written wherever it happened to be needed, so the same idea came out
   differently in two places and two different ideas came out the same. A page
   now asks for a NAME and the drawing lives in one map.

     btn.innerHTML = icon('undo');
     setIcon(btn, 'undo');                 // the same, without the assignment

   An entry is one of three shapes, and `icon()` does not care which:

     undo:   'M4 12a8 8 0 1 1 2.3 5.6'     one path's `d`
     close:  { s: '<rect .../>' }          the <svg>'s contents, verbatim
     info:   { g: '?' }                    still a character, not yet drawn

   The third shape is the point of the file. A sign that a page draws with a
   character out of the font has no stroke, no grid and no weight of its own:
   it is whatever the typeface happens to give. Naming it here does not fix
   that, but it puts it in the one place where fixing it is a one line change,
   and `iconReport()` counts how many are left. It does come back as an <svg>
   like every other sign, with the character set inside it, so a page never
   has to know which of its signs are finished.

   The set is drawn on a 24 by 24 grid, stroked, never filled, so one
   `stroke-width` in the stylesheet governs the lot. Six entries carry a `vb`
   of their own and are exceptions on purpose: the four window buttons, which
   are finished and drawn for a twelve pixel button, and the two stepper
   arrows, which fill a strip nine pixels by five where a square drawing would
   come out five pixels tall.

   Leaves on the window: ICONS, icon, setIcon, iconReport.
   ========================================================================== */

/* eslint no-unused-vars: 0 */

const ICON_GRID = '0 0 24 24';

const ICONS = {
  /* ── the window's own buttons ──────────────────────────────────────────
     The four exceptions to the grid, and they carry their own `vb` to say
     so. They are drawn for a twelve pixel button and they are finished: the
     rest of the set is provisional and will be redrawn, these four will not,
     so putting them on the common grid would be rescaling something that
     nobody asked to change. They keep the coordinates and the 1.35 stroke
     `.wbtn svg` has always given them. */
  'win-minimise': { vb: '0 0 12 12', s: '<path d="M2.5 6h7"/>' },
  'win-maximise': { vb: '0 0 12 12',
    s: '<rect x="2.5" y="2.5" width="7" height="7" rx="1"/>' },
  'win-restore': { vb: '0 0 12 12',
    s: '<rect x="1.8" y="4.2" width="6" height="6" rx="1"/>'
      + '<path d="M4.6 4.2V2.8a1 1 0 0 1 1-1h3.6a1 1 0 0 1 1 1v3.6a1 1 0 0 1-1 1H8.8"/>' },
  'win-close': { vb: '0 0 12 12', s: '<path d="M3 3l6 6M9 3l-6 6"/>' },

  /* ── pointing ──────────────────────────────────────────────────────── */
  'chevron-down': { s: '<polyline points="7.5 10 12 14.5 16.5 10"/>' },
  'chevron-left': { s: '<polyline points="14.5 5 7.5 12 14.5 19"/>' },
  'chevron-right': { s: '<polyline points="9.5 5 16.5 12 9.5 19"/>' },
  /* The stepper's two arrows. Filled, not stroked, and on a strip of their
     own: see the note at the top. */
  'step-up': { vb: '0 0 10 6', s: '<path d="M5 0.7 9.2 5.5 0.8 5.5z"/>' },
  'step-down': { vb: '0 0 10 6', s: '<path d="M5 5.3 0.8 0.5 9.2 0.5z"/>' },

  /* ── files ─────────────────────────────────────────────────────────── */
  open: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z',
  'open-recent': { s: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
    + '<polyline points="12 11 12 17"/><polyline points="9 14 12 17 15 14"/>' },
  save: { s: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
    + '<polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>' },
  /* TODO the same drawing as `save`: two different things wearing one sign.
     `iconReport()` counts it, and one line here parts them. */
  'export': { s: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
    + '<polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>' },

  /* ── acting ────────────────────────────────────────────────────────── */
  undo: { s: '<path d="M4 12a8 8 0 1 1 2.3 5.6"/><path d="M4 12V7M4 12h5"/>' },
  redo: { s: '<path d="M20 12a8 8 0 1 0 -2.3 5.6"/><path d="M20 12V7M20 12h-5"/>' },
  reset: { g: '⟳' },
  run: 'M13 2L4 14h7l-1 8 9-12h-7z',
  add: { g: '＋' },
  remove: { g: '－' },

  /* ── saying how it went ────────────────────────────────────────────── */
  check: 'M5 13l4 4L19 7',
  warning: { g: '⚠' },
  info: { g: '?' },

  /* ── going back to the start ────────────────────────────────── */
  home: { s: '<path d="M3 11l9-7 9 7"/><path d="M6 10v9h12v-9"/>'
    + '<path d="M10 19v-5h4v5"/>' },

  /* ── the stage ─────────────────────────────────────────────────────── */
  /* TODO `zoom-in` and `add` are the same character, and so are `zoom-out`
     and `remove`. Four ideas, two signs. */
  'zoom-in': { g: '＋' },
  'zoom-out': { g: '－' },
  fit: { s: '<circle cx="12" cy="12" r="5.5"/>'
    + '<path d="M12 1.5v4.5M12 18v4.5M1.5 12h4.5M18 12h4.5"/>' },
  jog: { g: '⇄' }
};

/* A sign that has not been drawn yet, as an <svg> all the same.

   The stylesheet's contract is that a sign inside a button, a toolbar or a row
   label IS an inline <svg>: that is what gets the size, the stroke and the
   seven pixels of air next to the word, and what keeps it from being a stray
   white dingbat out of a fallback font. A character handed back as a character
   obeys none of that, and it showed: it came out glued to the word it sat
   next to. So a character is set INSIDE the drawing instead, filled with the
   text colour and not stroked, and it behaves like every other sign until the
   day it is replaced by one. */
function _glyphBox(c) {
  const t = String(c).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return '<text x="12" y="17.5" text-anchor="middle" font-size="19"'
    + ' fill="currentColor" stroke="none">' + t + '</text>';
}

/* The one place that turns an entry into markup. Returns a string and not an
   element on purpose: a string goes into innerHTML, into a template and into
   a test that has no DOM, and the three callers of this file all want one. */
/* What a sign looks like where nothing has said. These are presentation
   ATTRIBUTES, which any CSS rule beats, so `.btn svg`, `.ct svg` and
   `.spin-b svg` still govern where they apply. They matter where they do not:
   an <svg> with no width given takes its own intrinsic size, which is 300 by
   150, and one with no stroke given paints itself black. Both have happened,
   and the second is invisible on a dark surface. */
const ICON_DEFAULTS = ' width="1em" height="1em" fill="none" stroke="currentColor"'
  + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';

/* THE MIDDLE OF A SIGN IS THE MIDDLE OF ITS INK.

   A drawing sits inside a 24 by 24 box and almost never fills it evenly: a
   tick hangs low and left, an arrow leans right, a letter carries its own
   shoulders. Leave each one where it was drawn and a row of them reads
   crooked, one half a pixel high, the next one low. Nobody can see which sign
   is at fault; everybody can see the row.

   So the middle is not up to whoever draws. The registry measures, once per
   name, where the ink actually is, and moves it to the middle of the box. A
   sign is centred BY CONSTRUCTION. That holds for the drawings that are here,
   for the ones still set in a character, and for the ones that replace them
   later: they will not have to be centred, they will only have to exist.

   The GEOMETRIC box is measured, not the painted one. A uniform stroke grows
   a shape evenly on every side, so it does not move the middle, and the
   geometric box is the only one that does not depend on how thick the nib is.

   Measuring needs a rendered element, so it happens against a ruler kept off
   screen, once per name, and then it is remembered. Before there is a document
   to hang the ruler on, the sign comes back as drawn and is NOT remembered, so
   the next call measures it for real. */
const _inkShift = {};
let _ruler = null;

function _iconRuler() {
  if (_ruler) return _ruler;
  /* Not "is there a document" but "can this one draw": a test harness hands the
     scripts a stand-in document with a handful of methods on it, and asking it
     for an element it cannot make is how a library breaks a page it never sees.
     Where nothing can be drawn there is nothing to measure, and a sign comes
     back as it was drawn. */
  if (typeof document === 'undefined' || !document.body
      || typeof document.createElementNS !== 'function') return null;
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('style', 'position:absolute;left:-9999px;top:0;width:24px;height:24px');
  s.setAttribute('aria-hidden', 'true');
  document.body.appendChild(s);
  _ruler = s;
  return s;
}

/* How far the ink has to move to sit in the middle, as an SVG translate, or ''
   when it is already there or cannot yet be measured. Exported because an
   application keeps its own registry of its own signs (a cutting plane, a
   guide, a bone) and must centre them by the same measure, not by a second
   copy of this. */
function iconInkShift(key, inside, viewBox) {
  if (_inkShift[key] !== undefined) return _inkShift[key];
  const r = _iconRuler();
  if (!r) return '';
  const vb = String(viewBox || ICON_GRID).split(/[\s,]+/).map(Number);
  if (vb.length !== 4 || vb.some(isNaN)) return '';
  r.setAttribute('viewBox', String(viewBox || ICON_GRID));
  r.innerHTML = inside;
  let b;
  try { b = r.getBBox(); } catch (_) { r.innerHTML = ''; return ''; }
  r.innerHTML = '';
  if (!b || (!b.width && !b.height)) { _inkShift[key] = ''; return ''; }
  const dx = (vb[0] + vb[2] / 2) - (b.x + b.width / 2);
  const dy = (vb[1] + vb[3] / 2) - (b.y + b.height / 2);
  /* under a hundredth of a unit is not an offset, it is measurement noise */
  const v = (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) ? ''
          : (Math.round(dx * 1000) / 1000) + ' ' + (Math.round(dy * 1000) / 1000);
  _inkShift[key] = v;
  return v;
}

/* The drawing, wrapped in that move when there is one. */
function iconCentred(key, inside, viewBox) {
  const t = iconInkShift(key, inside, viewBox);
  return t ? '<g transform="translate(' + t + ')">' + inside + '</g>' : inside;
}

function icon(name, attrs) {
  const e = ICONS[name];
  if (e === undefined) return '';
  const def = (typeof e === 'string') ? { s: '<path d="' + e + '"/>' } : e;
  const inside = def.g ? _glyphBox(def.g) : def.s;
  let a = '';
  if (attrs) for (const k in attrs) a += ' ' + k + '="' + String(attrs[k]) + '"';
  /* The sign says it is one, and says whether it is still a character. A
     drawing's ink box is the same at every size, so it can be centred exactly
     and measured exactly; a character's is not, because the engine shapes and
     hints it at the size it is drawn, so the same letter is 10.40 units wide
     in a 24px box and 10.97 in a 16px one. A checker that measures centring
     therefore measures the drawings, and counts the characters as what they
     are: the part of the set that has not been drawn yet. */
  return '<svg viewBox="' + (def.vb || ICON_GRID) + '" data-segno="' + name + '"'
    + (def.g ? ' data-carattere=""' : '') + ICON_DEFAULTS + a
    + '>' + iconCentred(name, inside, def.vb) + '</svg>';
}

/* Put one into an element, and say whether there was one to put. */
function setIcon(el, name) {
  if (!el) return false;
  const m = icon(name);
  if (!m) return false;
  el.innerHTML = m;
  return true;
}

/* What is left to do, in numbers. Two questions, because the set has two ways
   of being unfinished: a sign that is still a character out of the font, and
   two names sharing one drawing, which is two ideas a reader cannot tell
   apart. Both are reported, neither is an error. */
function iconReport() {
  const glyphs = [], byDrawing = {}, shared = [];
  for (const name in ICONS) {
    const e = ICONS[name];
    const def = (typeof e === 'string') ? { s: '<path d="' + e + '"/>' } : e;
    if (def.g) { glyphs.push(name); continue; }
    const key = (def.vb || ICON_GRID) + '|' + def.s.replace(/\s+/g, ' ').trim();
    (byDrawing[key] = byDrawing[key] || []).push(name);
  }
  for (const k in byDrawing) if (byDrawing[k].length > 1) shared.push(byDrawing[k]);
  const total = Object.keys(ICONS).length;
  return { total: total, drawn: total - glyphs.length, glyphs: glyphs, shared: shared };
}
