/* ============================================================================
   widgets.js: the four small pieces the platform does not give a page in a
   usable shape.

   1. `.combo`, a dropdown. A native <select> hands its popup to the platform,
      which draws it outside the page with its own colours; inside the
      embedded browser that popup comes up unreadable. This one is a plain
      list in the page, in the palette. It answers to `.value` exactly like a
      <select> does and fires a `change` event, so the code around it does
      not know the difference.

        <div class="combo" tabindex="0" data-options="A|B|C" data-value="B">
          <span class="combo-v"></span>
        </div>

      The arrow is `chevron-down` out of icons.js and `initSelects` puts it
      there, so no page writes that drawing.

      What the reader sees and what the code reads are the same string
      unless `data-values` says otherwise, parallel to `data-options` and
      separated the same way. A <select> has carried that split since it was
      invented, and a list built from data needs it: the rows read "Report
      of March, 412 pages" and the value is the index. A list built by code
      goes in through `setOptions`, which writes both attributes.

        setOptions(el, ['Report of March, 412 pages'], ['0']);

      Neither a label nor a value may contain a vertical bar, which is the
      separator. `setOptions` says so instead of writing a list that would
      come back wrong.

   2. `numStep`, the number field's up and down arrows, done by hand, since
      the engine's own stepper cannot be styled (see base.css).

   2b. `.jog`, a number that is dragged and not placed: a tape of ticks
      under a fixed index, where a slider's track would be. A slider maps the
      width of its track onto its whole range, so a short track is a coarse
      one; a jog moves its number by a set amount for every pixel the hand
      travels, so a wide gesture is a small, gradual change. It answers to
      `.value`, `.min`, `.max` and `.step` exactly like an
      <input type="range"> does, fires `input` while it is dragged and
      `change` when it is let go, so the code around it does not know the
      difference. See the block over `setJog` below.

        <div class="jog" data-min="0" data-max="360" data-wrap data-gain="0.28"></div>

   3. `fitOneLine`, text that must never spill out of its box. A file name
      can run to fifty characters; the label shrinks until it fits, and only
      if it is still too long does it drop the middle, keeping the start and
      the extension. The full text is always in the tooltip.

   1b. `.picker`, the dropdown with a picture on every row, for a setting that
      holds for the whole application: the language, with its flag. It is
      New-SlantPicker of the WPF half, drawn in the page. See the block over
      `setPicker` below.

   4. `openSheet`, the one surface that says what a control is for. A page
      that explains its controls inside its own panels ends up with panels
      that are mostly prose; this puts every explanation in one place and
      opens it BESIDE the control that was asked about, on the far side of
      the band that control sits in. It veils nothing, blurs nothing and
      takes no focus, so the page it is explaining stays usable while it is
      open, and it closes on Esc, on a press outside, or on the same control
      again. See the block over `openSheet` below for the markup and the one
      function a page hands over.

   Leaves on the window: initSelects, setOptions, setPicker, numStep, setJog,
   initJogs, fitOneLine, fitButtonWords, initSheets, openSheet, closeSheet,
   sheetIsOpen, showSheet, hideSheet.
   ========================================================================== */

/* ── dropdown ─────────────────────────────────────────────────────────────── */
let _cbPop = null;        // the open popup, or null
let _cbOwner = null;      // the .combo it belongs to

function _cbClose() {
  if (_cbPop && _cbPop.parentNode) _cbPop.parentNode.removeChild(_cbPop);
  if (_cbOwner) _cbOwner.classList.remove('open');
  _cbPop = null;
  _cbOwner = null;
}

/* The rows, as {label, value} pairs. With no data-values the two are the
   same string, which is what almost every combo wants. */
function _cbItems(el) {
  const labels = (el.getAttribute('data-options') || '').split('|')
    .filter(function (s) { return s.length; });
  const raw = el.getAttribute('data-values');
  const values = raw === null ? null : raw.split('|');
  return labels.map(function (label, i) {
    return { label: label, value: (values && i < values.length) ? values[i] : label };
  });
}

function _cbSet(el, value, fire) {
  const items = _cbItems(el);
  let shown = value;
  for (let i = 0; i < items.length; i++) {
    if (items[i].value === value) { shown = items[i].label; break; }
  }
  el.setAttribute('data-value', value);
  const lbl = el.querySelector('.combo-v');
  if (lbl) lbl.textContent = shown;
  if (fire) el.dispatchEvent(new Event('change', { bubbles: true }));
}

/* Fill a combo from code. `values` is optional and defaults to the labels.
   The current value is kept when it is still in the list, so refilling a
   list with one more row in it does not move the selection. */
function setOptions(el, labels, values) {
  const bar = function (s) { return String(s).indexOf('|') >= 0; };
  if (labels.some(bar) || (values && values.some(bar))) {
    throw new Error('a combo option may not contain a vertical bar: that is '
                    + 'the separator data-options is written with');
  }
  el.setAttribute('data-options', labels.join('|'));
  if (values) el.setAttribute('data-values', values.join('|'));
  else el.removeAttribute('data-values');
  const items = _cbItems(el);
  const had = el.getAttribute('data-value');
  const keep = items.some(function (it) { return it.value === had; });
  _cbSet(el, keep ? had : (items.length ? items[0].value : ''), false);
}

/* Open under the trigger, or above it when there is no room below. Fixed
   positioning, so no scroll container can clip it.

   A list longer than the room on either side is capped at the larger of the
   two and scrolls inside, with the chosen row brought into view: forty-five
   languages are a list a window cannot hold, and a popup that ran past the
   bottom edge left the last rows where no pointer could reach them. */
function _cbOpen(el) {
  if (_cbOwner === el) { _cbClose(); return; }
  _cbClose();
  const items = _cbItems(el);
  if (!items.length) return;
  const r = el.getBoundingClientRect();
  const pop = document.createElement('div');
  pop.className = 'combopop';
  items.forEach(function (o) {
    const row = document.createElement('div');
    row.className = 'combo-opt' + (o.value === el.getAttribute('data-value') ? ' combo-on' : '');
    row.textContent = o.label;
    row.onmousedown = function (e) { e.preventDefault(); };
    row.onclick = function () { _cbSet(el, o.value, true); _cbClose(); };
    pop.appendChild(row);
  });
  pop.style.left = Math.round(r.left) + 'px';
  pop.style.width = Math.round(r.width) + 'px';
  pop.style.visibility = 'hidden';
  document.body.appendChild(pop);
  const below = window.innerHeight - r.bottom - 10;
  const above = r.top - 10;
  const whole = pop.offsetHeight;
  const room = Math.max(below, above);
  if (whole > room) pop.style.maxHeight = Math.floor(room) + 'px';
  const h = pop.offsetHeight;
  pop.style.top = (below >= h || below >= above)
    ? Math.round(r.bottom + 4) + 'px'
    : Math.round(r.top - h - 4) + 'px';
  const on = pop.querySelector('.combo-on');
  if (on && whole > room) pop.scrollTop = on.offsetTop - (h - on.offsetHeight) / 2;
  pop.style.visibility = '';
  el.classList.add('open');
  _cbPop = pop;
  _cbOwner = el;
}

/* Give every `.combo` on the page a `.value` property and its handlers. Called
   once at boot, before anything reads a value; calling it again wires only
   the combos added since. */
function initSelects() {
  document.querySelectorAll('.combo').forEach(function (el) {
    if (el._wired) return;
    el._wired = true;
    // The arrow is the widget's, not the page's. It used to be written into
    // the markup wherever a dropdown went, which is five copies of one drawing
    // and five chances for them to drift; a page that still writes it keeps
    // working, and one that leaves it out gets it here.
    if (!el.querySelector('.combo-c')) {
      const c = document.createElement('span');
      c.innerHTML = icon('chevron-down', { class: 'combo-c' });
      if (c.firstChild) el.appendChild(c.firstChild);
    }
    Object.defineProperty(el, 'value', {
      get: function () { return el.getAttribute('data-value') || ''; },
      set: function (v) { _cbSet(el, v, false); },
      configurable: true,
    });
    const first = _cbItems(el)[0];
    _cbSet(el, el.getAttribute('data-value') || (first ? first.value : ''), false);
    el.addEventListener('mousedown', function (e) { e.preventDefault(); });
    el.addEventListener('click', function (e) { e.stopPropagation(); _cbOpen(el); });
    el.addEventListener('keydown', function (e) {
      const items = _cbItems(el);
      const here = el.value;
      let i = -1;
      for (let n = 0; n < items.length; n++) { if (items[n].value === here) { i = n; break; } }
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _cbOpen(el); }
      else if (e.key === 'ArrowDown' && i < items.length - 1) { e.preventDefault(); _cbSet(el, items[i + 1].value, true); }
      else if (e.key === 'ArrowUp' && i > 0) { e.preventDefault(); _cbSet(el, items[i - 1].value, true); }
    });
  });

  if (initSelects._global) return;
  initSelects._global = true;
  // Capture phase, so a click anywhere else closes the popup before that click
  // does anything; a press on the popup itself, or on its trigger, is its own
  // business (removing the popup here would eat the option's click).
  window.addEventListener('mousedown', function (e) {
    if (!_cbPop) return;
    if (_cbPop.contains(e.target)) return;
    if (_cbOwner && _cbOwner.contains(e.target)) return;
    _cbClose();
  }, true);
  window.addEventListener('resize', function () { _cbClose(); });
  // Esc on an open list closes the list and nothing else. It is marked as used,
  // so a page that takes Esc as "one step back" (checking defaultPrevented)
  // does not also go back: one key, one thing. With no list open it passes on.
  window.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !_cbPop) return;
    _cbClose();
    e.preventDefault();
  }, true);
}

/* ── picker ───────────────────────────────────────────────────────────────── */
/* The dropdown with a picture on every row: a setting that holds for the whole
   application and is changed rarely, the language or the engine. It is the web
   twin of New-SlantPicker in wpf/SlantUI.psm1, and the two draw one design: the
   same button (the picture, a tag in a place of fixed width, a small filled
   arrow), the same list (picture, tag, name and note in columns shared by every
   row, the current row lit), the same cap on its height with the current row
   brought into view, and the same way in and out, in the same milliseconds.

     <div class="picker" tabindex="0"></div>

     setPicker(el, [{ code: 'it', tag: 'IT', label: 'Italiano', note: '',
                      flag: 'flags/it.svg' }, ...],
               'it', { maxHeight: 300 });

   `flag` is the path of a flag's image, and the picker draws it the way
   New-FlagBox does: 18 by 13.5, inside a thread of fill so the white of a
   tricolour does not melt into the surface, and the tag in its place when the
   path is null. `visual`, instead, is a function that returns an Element (a
   logo, anything else): it is called anew every time one is needed, because an
   element has one parent and the button and the list each want their own. The tag has one width whatever it says, so choosing
   another entry never moves the row the button sits in. It answers to `.value`
   and fires `change`, like a <select> and like `.combo`. */
let _pkPop = null;        // the open list, or null
let _pkOwner = null;      // the .picker it belongs to
let _pkGoing = null;      // the timer that removes a list on its way out

// The movement, in the numbers New-SlantPicker uses: the fade in is short and
// the travel almost twice as long, so the list does not seem to slide in
// already opaque. Out is one short movement, and the list is removed by a timer
// and not by the animation's end, which might not arrive.
const _PK_IN_FADE = 110, _PK_IN_MOVE = 210, _PK_OUT = 120, _PK_GONE = 130;
const _PK_EASE_QUAD_OUT = 'cubic-bezier(0.5, 1, 0.89, 1)';
const _PK_EASE_QUINT_OUT = 'cubic-bezier(0.22, 1, 0.36, 1)';
const _PK_EASE_QUAD_IN = 'cubic-bezier(0.11, 0, 0.5, 0)';

function _pkItem(el, code) {
  const items = el._pkItems || [];
  for (let i = 0; i < items.length; i++) if (items[i].code === code) return items[i];
  return items[0] || null;
}

// A flag in its box (New-FlagBox). An image with the corners of a picture
// would not be a mark of 18 px, so it is the box's background; without a file,
// the tag, dimmed, in the same box.
function _pkFlag(it) {
  const b = document.createElement('span');
  b.className = 'flagbox';
  const i = document.createElement('i');
  if (it.flag) i.style.backgroundImage = 'url("' + it.flag + '")';
  else { b.classList.add('bare'); i.textContent = it.tag || String(it.code).toUpperCase(); }
  b.appendChild(i);
  return b;
}
function _pkVisual(it) {
  if (it.visual) return it.visual();
  return it.flag !== undefined ? _pkFlag(it) : null;
}

function _pkShow(el) {
  const it = _pkItem(el, el._pkValue);
  while (el.firstChild) el.removeChild(el.firstChild);
  if (!it) return;
  const v = _pkVisual(it);
  if (v) el.appendChild(v);
  const tag = document.createElement('span');
  tag.className = 'picker-tag';
  tag.textContent = it.tag || String(it.code).toUpperCase();
  el.appendChild(tag);
  const a = document.createElement('span');
  a.innerHTML = icon('picker-down', { class: 'picker-c' });
  if (a.firstChild) el.appendChild(a.firstChild);
}

function _pkClose(now) {
  const pop = _pkPop, owner = _pkOwner;
  _pkPop = null;
  _pkOwner = null;
  if (owner) owner.classList.remove('open');
  if (!pop) return;
  if (_pkGoing) { clearTimeout(_pkGoing); _pkGoing = null; }
  const gone = function () { if (pop.parentNode) pop.parentNode.removeChild(pop); };
  if (now || !pop.animate) { gone(); return; }
  try {
    pop.animate([{ opacity: 1, transform: 'none' },
                 { opacity: 0, transform: 'translateY(-5px) scale(0.985)' }],
                { duration: _PK_OUT, easing: _PK_EASE_QUAD_IN, fill: 'forwards' });
  } catch (e) { /* no animation, no matter: the timer removes it */ }
  _pkGoing = setTimeout(function () { _pkGoing = null; gone(); }, _PK_GONE);
}

function _pkOpen(el) {
  if (_pkOwner === el) { _pkClose(); return; }
  _pkClose(true);
  _cbClose();
  const items = el._pkItems || [];
  if (!items.length) return;
  const pop = document.createElement('div');
  pop.className = 'pickerpop';
  pop.setAttribute('role', 'listbox');
  let on = null;
  items.forEach(function (it) {
    const row = document.createElement('div');
    row.className = 'picker-row' + (it.code === el._pkValue ? ' on' : '');
    row.setAttribute('role', 'option');
    row.setAttribute('data-code', it.code);
    const v = _pkVisual(it);
    row.appendChild(v || document.createElement('span'));
    const tag = document.createElement('span');
    tag.className = 'picker-tag';
    tag.textContent = it.tag || String(it.code).toUpperCase();
    const lab = document.createElement('span');
    lab.className = 'picker-label';
    lab.textContent = it.label || '';
    const note = document.createElement('span');
    note.className = 'picker-note';
    note.textContent = it.note || '';
    row.appendChild(tag);
    row.appendChild(lab);
    row.appendChild(note);
    row.onmousedown = function (e) { e.preventDefault(); };
    row.onclick = function () { _pkClose(); _pkSet(el, it.code, true); };
    if (it.code === el._pkValue) on = row;
    pop.appendChild(row);
  });
  const r = el.getBoundingClientRect();
  pop.style.visibility = 'hidden';
  document.body.appendChild(pop);
  // Under the button if it fits, above it otherwise; and if it fits neither,
  // capped at the larger room and scrolling, never past the window's edge.
  const margin = 10, gap = 4;
  const below = window.innerHeight - r.bottom - margin - gap;
  const above = r.top - margin - gap;
  let cap = Math.max(below, above);
  if (el._pkMax > 0) cap = Math.min(cap, el._pkMax);
  const whole = pop.offsetHeight;
  if (whole > cap) pop.style.maxHeight = Math.floor(cap) + 'px';
  const h = pop.offsetHeight, w = pop.offsetWidth;
  const up = h > below && above > below;
  pop.style.top = Math.round(up ? r.top - gap - h : r.bottom + gap) + 'px';
  let left = r.left;
  if (left + w > window.innerWidth - margin) left = window.innerWidth - margin - w;
  pop.style.left = Math.round(Math.max(margin, left)) + 'px';
  if (on && whole > cap) pop.scrollTop = on.offsetTop - (h - on.offsetHeight) / 2;
  pop.style.visibility = '';
  el.classList.add('open');
  _pkPop = pop;
  _pkOwner = el;
  if (pop.animate) {
    try {
      pop.animate([{ opacity: 0 }, { opacity: 1 }],
                  { duration: _PK_IN_FADE, easing: _PK_EASE_QUAD_OUT });
      pop.animate([{ transform: 'translateY(-7px) scale(0.965)' }, { transform: 'none' }],
                  { duration: _PK_IN_MOVE, easing: _PK_EASE_QUINT_OUT });
    } catch (e) { /* shown still, just without the movement */ }
  }
}

function _pkSet(el, code, fire) {
  el._pkValue = String(code);
  _pkShow(el);
  if (fire) el.dispatchEvent(new Event('change', { bubbles: true }));
}

function setPicker(el, items, value, opts) {
  el._pkItems = (items || []).slice();
  el._pkMax = (opts && opts.maxHeight) || 0;
  el._pkValue = String(value !== undefined ? value
                       : (el._pkValue !== undefined ? el._pkValue
                          : (el._pkItems[0] ? el._pkItems[0].code : '')));
  _pkShow(el);
  if (el._pkWired) return;
  el._pkWired = true;
  el.setAttribute('role', 'button');
  el.setAttribute('aria-haspopup', 'listbox');
  Object.defineProperty(el, 'value', {
    get: function () { return el._pkValue || ''; },
    set: function (v) { _pkSet(el, v, false); },
    configurable: true,
  });
  el.addEventListener('mousedown', function (e) { e.preventDefault(); });
  el.addEventListener('click', function (e) { e.stopPropagation(); _pkOpen(el); });
  el.addEventListener('keydown', function (e) {
    const list = el._pkItems || [];
    let i = -1;
    for (let n = 0; n < list.length; n++) if (list[n].code === el._pkValue) { i = n; break; }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _pkOpen(el); }
    else if (e.key === 'ArrowDown' && i < list.length - 1) { e.preventDefault(); _pkSet(el, list[i + 1].code, true); }
    else if (e.key === 'ArrowUp' && i > 0) { e.preventDefault(); _pkSet(el, list[i - 1].code, true); }
  });
  if (setPicker._global) return;
  setPicker._global = true;
  // The same three ways out as the combo: a press anywhere else, Esc (which is
  // used up, so a page that takes Esc as a step back does not also step back),
  // and the window changing size.
  window.addEventListener('mousedown', function (e) {
    if (!_pkPop) return;
    if (_pkPop.contains(e.target)) return;
    if (_pkOwner && _pkOwner.contains(e.target)) return;
    _pkClose();
  }, true);
  window.addEventListener('resize', function () { _pkClose(true); });
  window.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !_pkPop) return;
    _pkClose();
    e.preventDefault();
  }, true);
}

/* ── number stepper ───────────────────────────────────────────────────────── */
/* What the engine's own up and down arrows do, done by hand: stepUp() and
   stepDown() refuse to work on an empty field, and the result has to keep
   the number of decimals the step implies or "50" becomes
   "50.00000000000001". `field` is the input element or its id. */
function numStep(field, dir) {
  const el = (typeof field === 'string') ? document.getElementById(field) : field;
  if (!el) return;
  const step = parseFloat(el.step) || 1;
  const cur = parseFloat(el.value);
  let v = isNaN(cur) ? (dir > 0 ? step : 0) : cur + dir * step;
  const lo = parseFloat(el.min), hi = parseFloat(el.max);
  if (!isNaN(lo) && v < lo) v = lo;
  if (!isNaN(hi) && v > hi) v = hi;
  if (v < 0) v = 0;
  const dec = (String(step).split('.')[1] || '').length;
  el.value = dec ? v.toFixed(dec) : String(Math.round(v));
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

/* ── jog ──────────────────────────────────────────────────────────────────── */
/* A jog is wired once and configured by its attributes, so a page can write
   one in markup and call initJogs(), or build one in code and call
   setJog(el, opts), which writes the attributes for it and wires it:

     data-min, data-max   the range. At an end the jog stops, and the tape
                          runs out under the index (components.css).
     data-wrap            the range is a whole turn: past one end the number
                          comes in at the other, and the tape has no ends.
     data-gain            how far the number moves for one pixel of travel.
                          Without it, the whole range takes --jog-run pixels.
     data-step            how far an arrow key moves it. Without it, ten
                          times the finest step a pixel makes.
     data-value           where it starts.

   A number made by the hand is rounded to the finest power of ten that one
   pixel can still move (a gain of 0.28 rounds to 0.1, one of 0.011 to 0.01),
   so the number written is the number shown and no pixel of travel is lost.
   Inside a drag the jog keeps the number unrounded, so a slow hand never
   sticks. A number set from code is kept exactly as it was given.

   The hand: a press takes the pointer and fires `jogstart`, every pixel of
   travel moves the number and fires `input` when it changes, and letting go
   fires `change` if anything did and then `jogend`. The two ends of the
   gesture are events of their own, and bubble, because a page that holds its
   work back while a hand is down needs to know exactly when the hand went down
   and came up, and a press the jog refuses (another button, a jog switched
   off) is neither. While it is held, <html> carries `jog-drag`, which keeps
   the pointer's shape when the hand leaves the strip.

   Setting `.value` to the number it already holds does nothing, so a page
   that writes the value back into the jog while the hand is moving it does not
   cost the hand the part of a pixel it has not been paid for yet. "The number
   it already holds" is the same number give or take the last digits of a
   floating point sum: a page that wraps an angle with ((v % 360) + 360) % 360
   writes back 0.30000000000001 for 0.3, and that is not a new number. */
function _jogNum(el, name) {
  const v = parseFloat(el.getAttribute('data-' + name));
  return isNaN(v) ? null : v;
}

function _jogRange(el) {
  const lo = _jogNum(el, 'min'), hi = _jogNum(el, 'max');
  return {
    lo: lo === null ? -Infinity : lo,
    hi: hi === null ? Infinity : hi,
    wrap: el.getAttribute('data-wrap') !== null && lo !== null && hi !== null && hi > lo,
  };
}

function _jogGain(el) {
  const g = _jogNum(el, 'gain');
  if (g !== null && g > 0) return g;
  const r = _jogRange(el);
  if (!(isFinite(r.lo) && isFinite(r.hi) && r.hi > r.lo)) return 1;
  const run = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--jog-run'));
  return (r.hi - r.lo) / (run > 0 ? run : 400);
}

// The finest power of ten one pixel of travel still moves the number by.
function _jogFine(el) {
  return Math.pow(10, Math.floor(Math.log10(_jogGain(el)) + 1e-9));
}

function _jogStep(el) {
  const s = _jogNum(el, 'step');
  return s !== null && s > 0 ? s : _jogFine(el) * 10;
}

function _jogFit(el, v) {
  const r = _jogRange(el);
  if (r.wrap) {
    if (v >= r.lo && v < r.hi) return v;           // in the turn: not a digit touched
    const span = r.hi - r.lo;
    return r.lo + (((v - r.lo) % span) + span) % span;
  }
  return Math.min(r.hi, Math.max(r.lo, v));
}

function _jogRound(el, v) {
  const f = _jogFine(el);
  const dec = Math.max(0, -Math.round(Math.log10(f)));
  return +(Math.round(v / f) * f).toFixed(dec);
}

function _jogSet(style, name, value) {
  if (value === null) style.removeProperty(name);
  else style.setProperty(name, value);
}

// The tape: where it stands, and how far it reaches either side of the index.
// It moves with the hand, so what lies to the left of the index is the larger
// numbers and what lies to the right the smaller ones.
function _jogDraw(el) {
  const j = el._jog, g = _jogGain(el), r = _jogRange(el);
  _jogSet(el.style, '--jog-x', Math.round(j.raw / g) + 'px');
  const reach = function (d) { return Math.round(Math.max(0, d / g) * 100) / 100 + 'px'; };
  _jogSet(el.style, '--jog-l', r.wrap || !isFinite(r.hi) ? null : reach(r.hi - j.raw));
  _jogSet(el.style, '--jog-r', r.wrap || !isFinite(r.lo) ? null : reach(j.raw - r.lo));
  el.setAttribute('aria-valuenow', String(j.v));
}

// Move by `d`, as the hand or a key would: `input` if the number changed.
function _jogMove(el, d) {
  const j = el._jog, r = _jogRange(el);
  let raw = j.raw + d;
  if (!r.wrap) raw = Math.min(r.hi, Math.max(r.lo, raw));
  j.raw = raw;
  // fitted, then rounded, then fitted again: a number that rounds up onto the
  // end of a turn is its start
  const v = _jogFit(el, _jogRound(el, _jogFit(el, raw)));
  _jogDraw(el);
  if (v === j.v) return;
  j.v = v;
  j.moved = true;
  el.setAttribute('aria-valuenow', String(v));
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

function _jogEnd(el) {
  const j = el._jog;
  if (!j.drag) return;
  j.drag = false;
  el.classList.remove('drag');
  document.documentElement.classList.remove('jog-drag');
  j.raw = j.v;
  _jogDraw(el);
  if (j.moved) el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dispatchEvent(new Event('jogend', { bubbles: true }));
}

function _jogWire(el) {
  if (el._jog) return;
  const v0 = _jogNum(el, 'value');
  el._jog = { v: 0, raw: 0, x: 0, drag: false, moved: false };
  el._jog.v = el._jog.raw = _jogFit(el, v0 === null ? 0 : v0);
  el.setAttribute('role', 'slider');
  if (el.getAttribute('tabindex') === null) el.setAttribute('tabindex', '0');
  Object.defineProperty(el, 'value', {
    get: function () { return String(el._jog.v); },
    set: function (x) {
      const n = parseFloat(x);
      if (isNaN(n) || Math.abs(n - el._jog.v) <= 1e-9 * Math.max(1, Math.abs(n))) return;
      el._jog.v = el._jog.raw = _jogFit(el, n);
      _jogDraw(el);
    },
    configurable: true,
  });
  ['min', 'max', 'step'].forEach(function (k) {
    Object.defineProperty(el, k, {
      get: function () { return el.getAttribute('data-' + k) || ''; },
      set: function (x) {
        el.setAttribute('data-' + k, String(x));
        if (k !== 'step') el.setAttribute('aria-value' + k, String(x));
        el._jog.v = el._jog.raw = _jogFit(el, el._jog.v);
        _jogDraw(el);
      },
      configurable: true,
    });
  });
  Object.defineProperty(el, 'disabled', {
    get: function () { return el.getAttribute('aria-disabled') === 'true'; },
    set: function (x) { if (x) el.setAttribute('aria-disabled', 'true'); else el.removeAttribute('aria-disabled'); },
    configurable: true,
  });
  el.addEventListener('pointerdown', function (e) {
    if (e.button !== 0 || el.disabled) return;
    e.preventDefault();
    try { el.setPointerCapture(e.pointerId); } catch (_) { /* a pointer already gone */ }
    if (el.focus) el.focus({ preventScroll: true });
    el._jog.x = e.clientX;
    el._jog.drag = true;
    el._jog.moved = false;
    el.classList.add('drag');
    document.documentElement.classList.add('jog-drag');
    el.dispatchEvent(new Event('jogstart', { bubbles: true }));
  });
  el.addEventListener('pointermove', function (e) {
    const j = el._jog;
    if (!j.drag) return;
    const dx = e.clientX - j.x;
    j.x = e.clientX;
    if (dx) _jogMove(el, dx * _jogGain(el));
  });
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (t) {
    el.addEventListener(t, function () { _jogEnd(el); });
  });
  el.addEventListener('keydown', function (e) {
    if (el.disabled) return;
    const s = _jogStep(el);
    const d = { ArrowRight: s, ArrowUp: s, ArrowLeft: -s, ArrowDown: -s,
                PageUp: 10 * s, PageDown: -10 * s }[e.key];
    if (!d) return;
    e.preventDefault();
    el._jog.moved = false;
    _jogMove(el, d);
    el._jog.raw = el._jog.v;
    if (el._jog.moved) el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  _jogDraw(el);
}

/* Wire every `.jog` under `root` (the page when it is left out) that is not
   wired yet. */
function initJogs(root) {
  (root || document).querySelectorAll('.jog').forEach(_jogWire);
}

/* Configure one jog from code and wire it: `opts` takes min, max, gain, step,
   wrap and value, the attributes above without their prefix. */
function setJog(el, opts) {
  if (!el) return null;
  const o = opts || {};
  ['min', 'max', 'gain', 'step', 'value'].forEach(function (k) {
    if (o[k] !== undefined && o[k] !== null) el.setAttribute('data-' + k, String(o[k]));
  });
  if (o.wrap !== undefined) {
    if (o.wrap) el.setAttribute('data-wrap', ''); else el.removeAttribute('data-wrap');
  }
  if (o.min !== undefined && o.min !== null) el.setAttribute('aria-valuemin', String(o.min));
  if (o.max !== undefined && o.max !== null) el.setAttribute('aria-valuemax', String(o.max));
  _jogWire(el);
  el.value = (o.value !== undefined && o.value !== null) ? o.value : el._jog.v;
  return el;
}

/* ── text that has to fit ─────────────────────────────────────────────────── */
/* Shrink from `maxPx` down to `minPx` in half pixel steps; if that is still
   not enough, keep the head and the last 8 characters (the tail is what
   tells two files with the same beginning apart at a glance). The element needs
   `white-space:nowrap; overflow:hidden` for the measurement to mean anything,
   which is what the `.fit` class is for. */
function fitOneLine(el, text, maxPx, minPx) {
  if (!el) return;
  const s = (text == null) ? '' : String(text);
  el.title = s;
  el.style.fontSize = '';
  el.textContent = s;
  if (!s) return;
  const box = el.clientWidth;
  if (box < 24) return;                       // not laid out yet: leave it alone
  let size = maxPx;
  el.style.fontSize = size + 'px';
  while (el.scrollWidth > box && size > minPx) {
    size -= 0.5;
    el.style.fontSize = size + 'px';
  }
  if (el.scrollWidth <= box) return;
  const tail = s.slice(-8);
  const ellipsis = String.fromCharCode(0x2026);
  for (let head = s.length - 8; head > 3; head -= 2) {
    el.textContent = s.slice(0, head) + ellipsis + tail;
    if (el.scrollWidth <= box) return;
  }
}

/* ── the word beside a sign, placed by its ink ───────────────────────────── */
/* A button with a sign centres the INK of the sign and of its word, not their
   boxes (components.css). The sign carries the measure of its ink from icon();
   the word's ink is measured here, because a letter does not fill its own
   advance either: measured in the gallery, the N of "Next" starts a pixel into
   its box and the d of "Grid" ends short of it, and that was what was left of a
   group sitting off the middle of its button, up to 0.8 px CSS. The engine's
   own measureText rounds those to whole pixels, so the word is drawn, four
   times over, on a canvas of its own, and the columns that carry ink are read
   back. The answer goes on the word as data-ink-l and data-ink-r (what is empty
   before the first and after the last inked column, in CSS px), once per text
   and font; and the stylesheet lets that much hang out of the group, the same
   way the empty part of the sign's box does.

   A word changes: the language, a panel written later, a label set from code.
   So the library watches the document for text that changes inside a button
   with a sign and measures it again, a frame later, at most once a frame. A
   page does nothing. */
const _inkWords = {};
let _inkCanvas = null;

function _wordInk(text, font, size) {
  const key = font + '|' + text;
  if (_inkWords[key]) return _inkWords[key];
  if (!_inkCanvas) _inkCanvas = document.createElement('canvas');
  let g = _inkCanvas.getContext('2d', { willReadFrequently: true });
  if (!g) return null;
  g.font = font;
  const adv = g.measureText(text).width;
  const S = 4, pad = Math.ceil(size);
  const W = Math.ceil((adv + 2 * pad) * S), H = Math.ceil(size * 3 * S);
  if (!W || !H) return null;
  _inkCanvas.width = W;
  _inkCanvas.height = H;
  g = _inkCanvas.getContext('2d', { willReadFrequently: true });
  g.setTransform(S, 0, 0, S, 0, 0);
  g.font = font;
  g.textBaseline = 'middle';
  g.fillText(text, pad, size * 1.5);
  const a = g.getImageData(0, 0, W, H).data;
  let lo = -1, hi = -1;
  for (let x = 0; x < W && lo < 0; x++) {
    for (let y = 0; y < H; y++) if (a[(y * W + x) * 4 + 3] >= 128) { lo = x; break; }
  }
  for (let x = W - 1; x >= 0 && hi < 0; x--) {
    for (let y = 0; y < H; y++) if (a[(y * W + x) * 4 + 3] >= 128) { hi = x; break; }
  }
  if (lo < 0) return null;
  const r = { l: lo / S - pad, r: pad + adv - (hi + 1) / S };
  _inkWords[key] = r;
  return r;
}

/* The words of the buttons with a sign under `root` (or the whole page). */
function fitButtonWords(root) {
  if (typeof document === 'undefined' || typeof document.createElement !== 'function') return;
  const r = root || document;
  if (typeof r.querySelectorAll !== 'function') return;
  const words = r.querySelectorAll('.btn > .btn-label');
  for (let i = 0; i < words.length; i++) {
    const w = words[i], b = w.parentElement;
    if (!b || !b.querySelector('svg')) continue;
    const text = (w.textContent || '').trim();
    if (!text) { w.removeAttribute('data-ink-l'); w.removeAttribute('data-ink-r'); continue; }
    const cs = getComputedStyle(w);
    const size = parseFloat(cs.fontSize) || 13;
    const ink = _wordInk(text, cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily, size);
    if (!ink) continue;
    w.setAttribute('data-ink-l', ink.l.toFixed(2));
    w.setAttribute('data-ink-r', ink.r.toFixed(2));
  }
}

let _wordsAsked = false;
function _askWords() {
  if (_wordsAsked) return;
  _wordsAsked = true;
  requestAnimationFrame(function () { _wordsAsked = false; fitButtonWords(); });
}

(function _watchWords() {
  if (typeof document === 'undefined' || typeof MutationObserver !== 'function'
      || typeof document.addEventListener !== 'function') return;
  const start = function () {
    new MutationObserver(function (list) {
      for (let i = 0; i < list.length; i++) {
        const t = list[i].target, el = t.nodeType === 1 ? t : t.parentElement;
        if (el && el.closest && el.closest('.btn')) { _askWords(); return; }
        const added = list[i].addedNodes;
        for (let k = 0; k < added.length; k++) {
          const n = added[k];
          if (n.nodeType === 1 && (n.matches('.btn') || n.querySelector('.btn'))) { _askWords(); return; }
        }
      }
    }).observe(document.documentElement, { subtree: true, childList: true, characterData: true });
    _askWords();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(_askWords);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();

/* ── the sheet ────────────────────────────────────────────────────────────── */
/* One surface that says what a control is for. There is one in the document
   and it is moved from control to control, so a page never grows a second
   place keeping the same answer.

   The markup, once, anywhere in the body:

     <div class="sheet sheet-at" id="sheet" role="note" aria-labelledby="sheetTitle">
       <div class="sheet-hd">
         <div class="sheet-title" id="sheetTitle"></div>
         <button class="ct" data-sheet-close>...</button>
       </div>
       <div class="sheet-fig"></div>
       <div class="sheet-body"></div>
     </div>

   A control that has something to say carries a `.more` button beside it, and
   the page hands over ONE function that turns a trigger into its content:

     initSheets(function (trigger) {
       const k = trigger.getAttribute('data-more');
       return k ? { title: titleFor(k), html: bodyFor(k), fig: figFor(k) } : null;
     });

   `fig` is a drawing and is optional; it goes in `.sheet-fig`, which takes no
   room at all while it is empty.

   The listener is delegated, so a `.more` written into the page an hour later
   works without wiring. `.more` has to be a <button>: Enter and Space then
   reach it as a click, and the whole thing is on the keyboard for free.

   It opens BESIDE the question and takes nothing away from the page. No veil,
   no blur, and no focus: the reader was in the middle of something and is
   still in the middle of it, what is under the sheet still answers a press,
   and Esc reaches the sheet from wherever the focus happens to be. */

/* The bands fixed to the window's edge. A sheet opened from a control inside
   one of them clears the WHOLE band, and not just the control that asked: an
   answer lying over the row under the question is an answer in the way. */
const SHEET_BANDS = '.rp,.toolbar,.topbar,.titlebar';

let _shOpener = null;             // the .more that asked, and wears the accent
let _shProvider = null;

function _shParts() {
  const sheet = document.querySelector('.sheet-at');
  if (!sheet) return null;
  return {
    sheet: sheet,
    title: sheet.querySelector('.sheet-title'),
    fig: sheet.querySelector('.sheet-fig'),
    body: sheet.querySelector('.sheet-body'),
  };
}

/* A metric in pixels, read off the page, so a gap here is the library's own
   spacing and not a number written a second time. */
function _shPx(name, fallback) {
  const n = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
  return (isFinite(n) && n > 0) ? n : fallback;
}

/* --t-out in milliseconds, so the layer comes down when the fade has run and
   not at some number written twice. */
function _shOutMs() {
  const v = getComputedStyle(document.documentElement).getPropertyValue('--t-out');
  const n = parseFloat(v);
  return (isFinite(n) && n > 0) ? (v.indexOf('ms') >= 0 ? n : n * 1000) : 180;
}

/* Where a sheet is allowed to lie: the stage, which is the part of the window
   that is not a band. A sheet is about the work, so it belongs over the work,
   and a sheet lying half across a toolbar reads as a sheet that missed.

   A page with no stage, or with one too small to be the work area, gets the
   window with the bands along its top taken off it. */
function _shField(gap) {
  const W = window.innerWidth, H = window.innerHeight;
  const st = document.querySelector('.stage');
  if (st) {
    const r = st.getBoundingClientRect();
    if (r.width > W / 2 && r.height > H / 2)
      return { l: r.left + gap, t: r.top + gap, r: r.right - gap, b: r.bottom - gap };
  }
  const f = { l: gap, t: gap, r: W - gap, b: H - gap };
  const bars = document.querySelectorAll('.titlebar,.topbar');
  for (let i = 0; i < bars.length; i++) {
    const r = bars[i].getBoundingClientRect();
    if (r.height > 0 && r.width > W / 2 && r.top < H / 2) f.t = Math.max(f.t, r.bottom + gap);
  }
  return f;
}

/* Put `el` beside `trigger`, outside the band the trigger sits in.

   The sheet leaves by whichever of that band's four sides has the most room
   inside the field, which puts it over the work area when the question came
   from a side panel and under the rail when it came from a toolbar, without
   either being written down here. It is capped to the room there is BEFORE
   it is measured, so what opens can never reach back over the band it came
   out of, whatever the window size. Everything is read once, on opening. */
function _shPlace(el, trigger) {
  const gap = _shPx('--sp-3', 12);
  const t = trigger.getBoundingClientRect();
  const host = (trigger.closest && trigger.closest(SHEET_BANDS)) || trigger;
  const h = host.getBoundingClientRect();
  const f = _shField(gap);

  const sides = [
    { name: 'left', room: h.left - f.l },
    { name: 'right', room: f.r - h.right },
    { name: 'up', room: h.top - f.t },
    { name: 'down', room: f.b - h.bottom },
  ];
  let pick = sides[0];
  for (let i = 1; i < sides.length; i++) if (sides[i].room > pick.room) pick = sides[i];
  const across = (pick.name === 'left' || pick.name === 'right');

  /* One gap between the band and the sheet, and the sheet inside the field on
     the other axis. */
  el.style.maxWidth = (across ? Math.max(0, pick.room - gap) : Math.max(0, f.r - f.l)) + 'px';
  el.style.maxHeight = (across ? Math.max(0, f.b - f.t) : Math.max(0, pick.room - gap)) + 'px';

  /* offsetWidth is the layout box, which a transform does not move, so the
     sheet is measured while it is still scaled down: there is nothing to
     switch off and switch back on. */
  const w = el.offsetWidth, ht = el.offsetHeight;
  let x, y;
  if (across) {
    x = (pick.name === 'left') ? h.left - gap - w : h.right + gap;
    y = (t.top + t.bottom) / 2 - ht / 2;
  } else {
    y = (pick.name === 'up') ? h.top - gap - ht : h.bottom + gap;
    x = (t.left + t.right) / 2 - w / 2;
  }
  /* Beside the question where there is room for it, and inside the field
     where there is not: a sheet asked for from the bottom of a tall panel
     stops at the bottom of the work area. */
  x = Math.min(Math.max(x, f.l), Math.max(f.l, f.r - w));
  y = Math.min(Math.max(y, f.t), Math.max(f.t, f.b - ht));

  el.style.left = Math.round(x) + 'px';
  el.style.top = Math.round(y) + 'px';
  /* It grows out of the question: the origin is the middle of the control
     that asked, in the sheet's own coordinates. */
  el.style.transformOrigin = Math.round((t.left + t.right) / 2 - x) + 'px '
                           + Math.round((t.top + t.bottom) / 2 - y) + 'px';
}

/* Up, and in on the next frame. Hidden is display:none, so the two steps are
   what lets a transition run at all: the layer has to be in the layout for a
   frame before anything about it can change. Any .sheet goes up this way,
   which is how a page drives one it placed itself. */
function showSheet(el) {
  if (!el) return;
  clearTimeout(el._shTimer);
  el.classList.add('show');
  const arrive = function () { el.classList.add('on'); };
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(arrive);
  else arrive();
}

/* Out, and down once the fade has run. */
function hideSheet(el) {
  if (!el || !el.classList.contains('show')) return;
  el.classList.remove('on');
  clearTimeout(el._shTimer);
  el._shTimer = setTimeout(function () { el.classList.remove('show'); }, _shOutMs());
}

/* The trigger wears the accent while its own sheet is the one open, and says
   so to a reader who cannot see the accent. */
function _shMark(el, open) {
  if (!el || !el.classList) return;
  el.classList.toggle('on', !!open);
  if (el.setAttribute) el.setAttribute('aria-expanded', open ? 'true' : 'false');
}

/* Open it for `trigger`. The same trigger pressed again closes it, the way
   the dropdown behaves, so the control is a switch and not a one way door. */
function openSheet(trigger, title, html, fig) {
  const p = _shParts();
  if (!p || !p.body) return;
  if (_shOpener && _shOpener === trigger) { closeSheet(); return; }
  if (_shOpener) _shMark(_shOpener, false);
  clearTimeout(p.sheet._shTimer);

  if (p.title) p.title.textContent = (title == null) ? '' : String(title);
  p.body.innerHTML = (html == null) ? '' : String(html);
  if (p.fig) p.fig.innerHTML = (fig == null) ? '' : String(fig);
  p.body.scrollTop = 0;

  p.sheet.classList.add('show');
  if (trigger && trigger.getBoundingClientRect) _shPlace(p.sheet, trigger);
  showSheet(p.sheet);

  _shOpener = trigger || null;
  _shMark(_shOpener, true);
}

/* Esc, a press outside, or the same trigger again. Nothing is handed back,
   because nothing was taken: the focus never left the page. */
function closeSheet() {
  const p = _shParts();
  if (!p || !p.sheet.classList.contains('show')) return;
  const back = _shOpener;
  _shOpener = null;
  _shMark(back, false);
  hideSheet(p.sheet);
}

function sheetIsOpen() {
  const p = _shParts();
  return !!(p && p.sheet.classList.contains('show'));
}

/* Hand over the one function that turns a trigger into its content. Call it
   again to replace that function; the listeners are only ever wired once. */
function initSheets(provider) {
  if (provider) _shProvider = provider;
  if (initSheets._global) return;
  initSheets._global = true;

  document.addEventListener('click', function (e) {
    const t = e.target;
    const more = (t && t.closest) ? t.closest('.more') : null;
    if (more) {
      e.preventDefault();
      e.stopPropagation();
      const c = _shProvider ? _shProvider(more) : null;
      if (c) openSheet(more, c.title, c.html, c.fig);
      return;
    }
    if (t && t.closest && t.closest('[data-sheet-close]')) closeSheet();
  });

  /* Capture, so a press outside closes before that press does anything else.
     It is not swallowed: the control under it still gets the press, which is
     the whole difference between this and something modal. A press on the
     trigger is its own business, and letting it through is what makes the
     same trigger close what it opened. */
  window.addEventListener('mousedown', function (e) {
    if (!sheetIsOpen()) return;
    const p = _shParts();
    if (p.sheet.contains(e.target)) return;
    if (_shOpener && _shOpener.contains(e.target)) return;
    closeSheet();
  }, true);

  window.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !sheetIsOpen()) return;
    e.preventDefault();
    closeSheet();
  }, true);

  /* A window being resized moves the band the sheet came out of, and a sheet
     that stayed where it was would end up over it. */
  window.addEventListener('resize', function () {
    if (!sheetIsOpen() || !_shOpener) return;
    const p = _shParts();
    if (p) _shPlace(p.sheet, _shOpener);
  });
}
