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

   3. `fitOneLine`, text that must never spill out of its box. A file name
      can run to fifty characters; the label shrinks until it fits, and only
      if it is still too long does it drop the middle, keeping the start and
      the extension. The full text is always in the tooltip.

   4. `openSheet`, the one surface that says what a control is for. A page
      that explains its controls inside its own panels ends up with panels
      that are mostly prose; this puts every explanation in one place and
      opens it BESIDE the control that was asked about, on the far side of
      the band that control sits in. It veils nothing, blurs nothing and
      takes no focus, so the page it is explaining stays usable while it is
      open, and it closes on Esc, on a press outside, or on the same control
      again. See the block over `openSheet` below for the markup and the one
      function a page hands over.

   Leaves on the window: initSelects, setOptions, numStep, fitOneLine,
   initSheets, openSheet, closeSheet, sheetIsOpen, showSheet, hideSheet.
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
   positioning, so no scroll container can clip it. */
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
  const h = pop.offsetHeight;
  const below = window.innerHeight - r.bottom - 6;
  pop.style.top = (below >= h || r.top < h + 6)
    ? Math.round(r.bottom + 4) + 'px'
    : Math.round(r.top - h - 4) + 'px';
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
      else if (e.key === 'Escape') _cbClose();
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
  window.addEventListener('keydown', function (e) { if (e.key === 'Escape') _cbClose(); }, true);
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
