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
   and `report()` counts how many are left.

   Everything is drawn on a 24 by 24 grid, stroked, never filled, so one
   `stroke-width` in the stylesheet governs the lot. The two stepper arrows are
   the exception and carry their own `vb`: they fill a strip nine pixels by
   five, and a square drawing in there would come out five pixels tall.

   Leaves on the window: ICONS, icon, setIcon, iconReport.
   ========================================================================== */

/* eslint no-unused-vars: 0 */

const ICON_GRID = '0 0 24 24';

const ICONS = {
  /* ── the window's own buttons ──────────────────────────────────────────
     Drawn on the same grid as everything else and scaled down by
     `.wbtn svg`, which is why that rule carries its own stroke-width: a
     twelve pixel button showing a twenty-four unit drawing halves every
     line it is given. */
  'win-minimise': 'M5 12h14',
  'win-maximise': { s: '<rect x="5" y="5" width="14" height="14" rx="2"/>' },
  'win-restore': { s: '<rect x="3.6" y="8.4" width="12" height="12" rx="2"/>'
    + '<path d="M9.2 8.4V5.6a2 2 0 0 1 2-2h7.2a2 2 0 0 1 2 2v7.2a2 2 0 0 1-2 2H17.6"/>' },
  'win-close': 'M6 6l12 12M18 6L6 18',

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

  /* ── the stage ─────────────────────────────────────────────────────── */
  /* TODO `zoom-in` and `add` are the same character, and so are `zoom-out`
     and `remove`. Four ideas, two signs. */
  'zoom-in': { g: '＋' },
  'zoom-out': { g: '－' },
  fit: { s: '<circle cx="12" cy="12" r="5.5"/>'
    + '<path d="M12 1.5v4.5M12 18v4.5M1.5 12h4.5M18 12h4.5"/>' },
  jog: { g: '⇄' }
};

/* The one place that turns an entry into markup. Returns a string and not an
   element on purpose: a string goes into innerHTML, into a template and into
   a test that has no DOM, and the three callers of this file all want one. */
function icon(name, attrs) {
  const e = ICONS[name];
  if (e === undefined) return '';
  const def = (typeof e === 'string') ? { s: '<path d="' + e + '"/>' } : e;
  if (def.g) return def.g;
  let a = '';
  if (attrs) for (const k in attrs) a += ' ' + k + '="' + String(attrs[k]) + '"';
  return '<svg viewBox="' + (def.vb || ICON_GRID) + '"' + a + '>' + def.s + '</svg>';
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
