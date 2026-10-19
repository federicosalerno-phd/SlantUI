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
     jog:    { g: '⇄' }                    still a character, not yet drawn

   The third shape is the point of the file. A sign that a page draws with a
   character out of the font has no stroke, no grid and no weight of its own:
   it is whatever the typeface happens to give. Naming it here does not fix
   that, but it puts it in the one place where fixing it is a one line change,
   and `iconReport()` counts how many are left. It does come back as an <svg>
   like every other sign, with the character set inside it, so a page never
   has to know which of its signs are finished.

   The set is drawn on a 24 by 24 grid, stroked, so one `stroke-width` in the
   stylesheet governs the lot. The one thing filled is a point: every arrow,
   chevron and head is the same filled triangle (ARROW_HEAD, below). Nine
   entries carry a `vb` of their own and are exceptions on purpose: the four
   window buttons, which are finished and drawn for a twelve pixel button, and
   the two of the sound switch that sits among them (sounds.js), the
   two stepper arrows, which fill a strip of their own (four and a half pixels
   by six and a half) where a square drawing would come out smaller, and the
   picker's arrow, for the same reason and at the same size.

   Leaves on the window: ICONS, icon, setIcon, iconReport, iconInkShift,
   iconCentred, iconInkAttrs, ARROW_HEAD, arrowHead, arrowHeadPath.
   ========================================================================== */

/* eslint no-unused-vars: 0 */

const ICON_GRID = '0 0 24 24';

/* THE ARROWHEAD.

   Every point a window draws is one triangle: filled, never two strokes
   meeting in a V, and slim, half as wide as ARROW_HEAD of its length (0.9 to
   2.6, 38 degrees at the point). Two strokes in a V have a round corner where
   a point should be, and at the size of a button they read as a smudge; a
   filled triangle keeps its point and its straight edges at every size and
   every scaling. One shape, so the chevron on a button, the arrow of a
   dropdown and the head of a curved arrow are one sign at three sizes, and an
   application that draws its own arrows (a dimension line, a figure) draws
   them with the same two functions:

     arrowHead([x, y], [dx, dy], len)      the corners: the point at (x, y),
                                           then the two ends of its base, len
                                           behind it
     arrowHeadPath([x, y], [dx, dy], len)  the same as a path's `d`

   [dx, dy] is the way it points, of any length but none. A line that ends in
   one stops inside it, where the triangle is wider than the line, so the two
   read as one shape with the triangle's own point. */
const ARROW_HEAD = 0.9 / 2.6;

function arrowHead(tip, dir, len) {
  const n = Math.hypot(dir[0], dir[1]) || 1, ux = dir[0] / n, uy = dir[1] / n, w = len * ARROW_HEAD;
  const bx = tip[0] - ux * len, by = tip[1] - uy * len;
  return [[tip[0], tip[1]], [bx - uy * w, by + ux * w], [bx + uy * w, by - ux * w]];
}

function _num(v) { return String(Math.round(v * 1000) / 1000); }

function arrowHeadPath(tip, dir, len) {
  const p = arrowHead(tip, dir, len);
  return 'M' + p.map(function (q) { return _num(q[0]) + ' ' + _num(q[1]); }).join('L') + 'z';
}

/* A head as the set draws it: filled with the text colour and not stroked, so
   its corners stay sharp whatever the stroke of the rest is. */
function _head(tip, dir, len) {
  return '<path d="' + arrowHeadPath(tip, dir, len) + '" fill="currentColor" stroke="none"/>';
}

/* A curved arrow: an arc about (cx, cy) of radius r from the angle `from` to
   the angle `to`, in degrees the way SVG turns them (from the right, clockwise
   on screen), with its head `len` long on the chord that ends at `to`. The arc
   runs on into the head by a little more than half its stroke, so arc and head
   join with no gap. */
function _arcArrow(cx, cy, r, from, to, len) {
  const sg = to > from ? 1 : -1, deg = 180 / Math.PI;
  const at = to - sg * 2 * Math.asin(len / (2 * r)) * deg, into = at + sg * 1.4 / r * deg;
  const p = function (a) { return [cx + r * Math.cos(a / deg), cy + r * Math.sin(a / deg)]; };
  const a = p(from), e = p(into), b = p(at), t = p(to);
  return '<path d="M' + _num(a[0]) + ' ' + _num(a[1]) + 'A' + r + ' ' + r + ' 0 '
    + (Math.abs(into - from) > 180 ? 1 : 0) + ' ' + (sg > 0 ? 1 : 0) + ' ' + _num(e[0]) + ' ' + _num(e[1]) + '"/>'
    + _head(t, [t[0] - b[0], t[1] - b[1]], len);
}

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
  /* The sound switch, on the same twelve and the same stroke: a speaker with
     two waves, and the same speaker with a cross where the waves were. The
     cross spans the same box as the waves, so the two drawings have one ink
     box, are moved to the middle by one measure, and the speaker stays where
     it is when the switch flips. */
  'sound-on': { vb: '0 0 12 12', s: '<path d="M1 4.5H3.6L6 2.4V9.6L3.6 7.5H1Z"/>'
    + '<path d="M8.156 4.444A2.2 2.2 0 0 1 8.156 7.556M9.570 3.030A4.2 4.2 0 0 1 9.570 8.970"/>' },
  'sound-off': { vb: '0 0 12 12', s: '<path d="M1 4.5H3.6L6 2.4V9.6L3.6 7.5H1Z"/>'
    + '<path d="M8 4.6l2.8 2.8M10.8 4.6l-2.8 2.8"/>' },

  /* ── pointing ──────────────────────────────────────────────────────── */
  /* The four ways, each the arrowhead fourteen long about the middle of the
     grid. The names stay: they are what the pages ask for. */
  'chevron-up': { s: _head([12, 5], [0, -1], 14) },
  'chevron-down': { s: _head([12, 19], [0, 1], 14) },
  'chevron-left': { s: _head([5, 12], [-1, 0], 14) },
  'chevron-right': { s: _head([19, 12], [1, 0], 14) },
  /* The stepper's two arrows: the arrowhead on a strip of its own, see the
     note at the top, filled by its stylesheet (.spin-b svg). */
  'step-up': { vb: '0 0 4.5 6.5', s: '<path d="' + arrowHeadPath([2.25, 0], [0, -1], 6.5) + '"/>' },
  'step-down': { vb: '0 0 4.5 6.5', s: '<path d="' + arrowHeadPath([2.25, 6.5], [0, 1], 6.5) + '"/>' },
  /* The picker's arrow: the arrowhead New-SlantPicker draws in the WPF half
     ("M 0,0 L 4.5,0 L 2.25,6.5 Z"), on a strip of its own for the same reason
     as the stepper's, as large as a dropdown's, filled by .picker-c. */
  'picker-down': { vb: '0 0 4.5 6.5', s: '<path d="' + arrowHeadPath([2.25, 6.5], [0, 1], 6.5) + '"/>' },

  /* ── files ─────────────────────────────────────────────────────────── */
  open: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z',
  'open-recent': { s: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
    + '<path d="M12 9V12.4"/>' + _head([12, 18], [0, 1], 7) },
  save: { s: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
    + '<polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>' },
  /* TODO the same drawing as `save`: two different things wearing one sign.
     `iconReport()` counts it, and one line here parts them. */
  'export': { s: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
    + '<polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>' },
  /* Make another one of these. Two sheets, the front one whole and the one
     behind it showing at two corners, which is the one drawing a window has
     used for a copy since windows had one. It is its own drawing and not a
     second name on `save`: copying a document is not writing it down. */
  copy: { s: '<rect x="9" y="9" width="12" height="12" rx="2"/>'
    + '<path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>' },

  /* ── acting ────────────────────────────────────────────────────────── */
  /* Three turns on one circle, each with the arrowhead on its end: undo back
     round to the left, redo its mirror, reset round to the top left. */
  undo: { s: _arcArrow(12, 12, 8, 120, -190, 8.5) },
  redo: { s: _arcArrow(12, 12, 8, 60, 370, 8.5) },
  reset: { s: _arcArrow(12, 12, 8, 155, -160, 8.5) },
  run: 'M13 2L4 14h7l-1 8 9-12h-7z',
  play: 'M7 4.6 19 12 7 19.4z',
  stop: { s: '<rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/>' },
  add: 'M12 5v14M5 12h14',
  remove: 'M5 12h14',

  /* ── saying how it went ────────────────────────────────────────────── */
  check: 'M5 13l4 4L19 7',
  warning: { g: '⚠' },
  info: { s: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.4"/>' },

  /* ── going back to the start ────────────────────────────────── */
  home: { s: '<path d="M3 11l9-7 9 7"/><path d="M6 10v9h12v-9"/>'
    + '<path d="M10 19v-5h4v5"/>' },

  /* ── the stage ─────────────────────────────────────────────────────── */
  /* TODO still characters: a magnifier with a plus and with a minus is what
     they want to be, and not `add` and `remove`, which they used to share. */
  'zoom-in': { g: '＋' },
  'zoom-out': { g: '－' },
  grid: { s: '<rect x="4.5" y="4.5" width="6" height="6" rx="1"/><rect x="13.5" y="4.5" width="6" height="6" rx="1"/>'
    + '<rect x="4.5" y="13.5" width="6" height="6" rx="1"/><rect x="13.5" y="13.5" width="6" height="6" rx="1"/>' },
  fit: { s: '<circle cx="12" cy="12" r="5.5"/>'
    + '<path d="M12 1.5v4.5M12 18v4.5M1.5 12h4.5M18 12h4.5"/>' },
  /* what is shown on the stage and what is not: an open eye, and the same eye
     struck through, so a row of them reads at a glance */
  eye: { s: '<path d="M2.5 12s3.6-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.6 6.5-9.5 6.5S2.5 12 2.5 12z"/>'
    + '<circle cx="12" cy="12" r="2.8"/>' },
  'eye-off': { s: '<path d="M2.5 12s3.6-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.6 6.5-9.5 6.5S2.5 12 2.5 12z"/>'
    + '<path d="M4.5 4.5l15 15"/>' },
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
function _ink(key, inside, viewBox) {
  if (_inkShift[key] !== undefined) return _inkShift[key];
  const r = _iconRuler();
  if (!r) return null;
  const vb = String(viewBox || ICON_GRID).split(/[\s,]+/).map(Number);
  if (vb.length !== 4 || vb.some(isNaN)) return null;
  r.setAttribute('viewBox', String(viewBox || ICON_GRID));
  r.innerHTML = inside;
  let b;
  try { b = r.getBBox(); } catch (_) { r.innerHTML = ''; return null; }
  r.innerHTML = '';
  if (!b || (!b.width && !b.height)) { _inkShift[key] = { t: '', w: 0, h: 0 }; return _inkShift[key]; }
  const dx = (vb[0] + vb[2] / 2) - (b.x + b.width / 2);
  const dy = (vb[1] + vb[3] / 2) - (b.y + b.height / 2);
  /* under a hundredth of a unit is not an offset, it is measurement noise */
  const t = (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) ? ''
          : (Math.round(dx * 1000) / 1000) + ' ' + (Math.round(dy * 1000) / 1000);
  _inkShift[key] = { t: t, w: b.width / vb[2], h: b.height / vb[3] };
  return _inkShift[key];
}

function iconInkShift(key, inside, viewBox) {
  const k = _ink(key, inside, viewBox);
  return k ? k.t : '';
}

/* The drawing, wrapped in that move when there is one. */
function iconCentred(key, inside, viewBox) {
  const t = iconInkShift(key, inside, viewBox);
  return t ? '<g transform="translate(' + t + ')">' + inside + '</g>' : inside;
}

/* HOW BIG THE INK IS, WRITTEN ON THE SIGN.

   The same measure says how much of its box the ink fills, across and down,
   and a sign carries it as data-ink-w and data-ink-h. A button reads them
   (components.css): it sizes the sign so that its ink is as tall as the
   capitals of the word next to it, and lets the empty part of the box hang
   out on either side, so the space between the ink and the word is the
   gap, and the button centres the ink with the word and not the box. Measured
   before this, the ink was 74 to 119 % of the capitals depending on the
   drawing, and a group of sign and word sat up to 6 px off the middle of its
   button. An application writes the same two on its own signs with this. '' when
   the ink cannot be measured yet. */
function iconInkAttrs(key, inside, viewBox) {
  const k = _ink(key, inside, viewBox);
  /* a straight line has no height (or no width): it still has a size, its
     length, and the button sizes it by its larger side */
  if (!k || (!k.w && !k.h)) return '';
  return ' data-ink-w="' + k.w.toFixed(4) + '" data-ink-h="' + k.h.toFixed(4) + '"';
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
    + (def.g ? ' data-carattere=""' : '') + iconInkAttrs(name, inside, def.vb) + ICON_DEFAULTS + a
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
