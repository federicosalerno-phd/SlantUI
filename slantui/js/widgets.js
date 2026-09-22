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

   4. `openSheet`, the one surface that opens over the page to say what a
      control is for. A page that explains its controls inside its own panels
      ends up with panels that are mostly prose; this puts every explanation
      in one place, opens it from the control that was asked about, and takes
      Esc, a press outside and the keyboard with it. See the block over
      `openSheet` below for the markup and the one function a page hands over.

   Leaves on the window: initSelects, setOptions, numStep, fitOneLine,
   initSheets, openSheet, closeSheet, sheetIsOpen.
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
/* One surface that opens over the page and says what a control is for. There
   is one in the document and it is moved from control to control, so the page
   never grows a second place keeping the same answer.

   The markup, once, anywhere in the body:

     <div class="scrim scrim-veil" id="sheetVeil">
       <div class="sheet" role="dialog" aria-modal="true" tabindex="-1"
            aria-labelledby="sheetTitle">
         <div class="sheet-hd">
           <div class="sheet-title" id="sheetTitle"></div>
           <button class="ct" data-sheet-close>...</button>
         </div>
         <div class="sheet-body"></div>
       </div>
     </div>

   A control that has something to say carries a `.more` button beside it, and
   the page hands over ONE function that turns a trigger into its content:

     initSheets(function (trigger) {
       const k = trigger.getAttribute('data-more');
       return k ? { title: titleFor(k), html: bodyFor(k) } : null;
     });

   The listener is delegated, so a `.more` written into the page an hour later
   works without wiring. `.more` has to be a <button>: Enter and Space then
   reach it as a click, and the whole thing is on the keyboard for free. */
let _shOpener = null;             // the .more that asked, and gets the focus back
let _shProvider = null;
let _shTimer = 0;

function _shParts() {
  const veil = document.querySelector('.scrim-veil');
  if (!veil) return null;
  return {
    veil: veil,
    sheet: veil.querySelector('.sheet'),
    title: veil.querySelector('.sheet-title'),
    body: veil.querySelector('.sheet-body'),
  };
}

/* --t-out in milliseconds, so the layer comes down when the fade has run and
   not at some number written twice. */
function _shOutMs() {
  const v = getComputedStyle(document.documentElement).getPropertyValue('--t-out');
  const n = parseFloat(v);
  return (isFinite(n) && n > 0) ? (v.indexOf('ms') >= 0 ? n : n * 1000) : 180;
}

function _shFocusable(root) {
  return [].slice.call(root.querySelectorAll(
    'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'))
    .filter(function (el) { return !el.disabled && el.offsetParent !== null; });
}

/* Open it for `trigger`. The same trigger pressed again closes it, the way
   the dropdown behaves, so the control is a switch and not a one way door. */
function openSheet(trigger, title, html) {
  const p = _shParts();
  if (!p || !p.sheet) return;
  if (_shOpener && _shOpener === trigger) { closeSheet(); return; }
  if (_shOpener) _shOpener.classList.remove('on');
  clearTimeout(_shTimer);

  p.title.textContent = (title == null) ? '' : String(title);
  p.body.innerHTML = (html == null) ? '' : String(html);
  p.body.scrollTop = 0;
  p.veil.classList.add('show');

  /* Where it grows from. The sheet is scaled down while it is closed, so its
     rectangle is measured with the transform off: once, on opening, never per
     frame. Reading offsetWidth in between is what stops the browser from
     animating away from `none`. */
  let origin = '50% 50%';
  if (trigger && trigger.getBoundingClientRect) {
    const before = p.sheet.style.transition;
    p.sheet.style.transition = 'none';
    p.sheet.style.transform = 'none';
    const a = trigger.getBoundingClientRect();
    const c = p.sheet.getBoundingClientRect();
    if (c.width > 0 && c.height > 0) {
      origin = Math.round(a.left + a.width / 2 - c.left) + 'px '
             + Math.round(a.top + a.height / 2 - c.top) + 'px';
    }
    p.sheet.style.transform = '';
    void p.sheet.offsetWidth;
    p.sheet.style.transition = before;
  }
  p.sheet.style.transformOrigin = origin;

  const show = function () { p.veil.classList.add('on'); };
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(show);
  else show();

  _shOpener = trigger || null;
  if (trigger && trigger.classList) trigger.classList.add('on');
  if (p.sheet.focus) p.sheet.focus();
}

/* Esc, a press outside, or the same trigger again. The focus goes back to
   whatever asked, because a reader who opened this with the keyboard has to
   get the keyboard back where they left it. */
function closeSheet() {
  const p = _shParts();
  if (!p || !p.veil.classList.contains('show')) return;
  p.veil.classList.remove('on');
  const back = _shOpener;
  _shOpener = null;
  if (back && back.classList) back.classList.remove('on');
  clearTimeout(_shTimer);
  _shTimer = setTimeout(function () {
    p.veil.classList.remove('show');
    p.body.innerHTML = '';
  }, _shOutMs());
  if (back && back.focus) back.focus();
}

function sheetIsOpen() {
  const p = _shParts();
  return !!(p && p.veil.classList.contains('show'));
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
      if (c) openSheet(more, c.title, c.html);
      return;
    }
    if (t && t.closest && t.closest('[data-sheet-close]')) closeSheet();
  });

  /* Capture, so a press outside closes before that press does anything else.
     A press on the trigger is its own business: letting it through is what
     makes the same trigger close what it opened. */
  window.addEventListener('mousedown', function (e) {
    if (!sheetIsOpen()) return;
    const p = _shParts();
    if (p.sheet.contains(e.target)) return;
    if (_shOpener && _shOpener.contains(e.target)) return;
    closeSheet();
  }, true);

  window.addEventListener('keydown', function (e) {
    if (!sheetIsOpen()) return;
    if (e.key === 'Escape') { e.preventDefault(); closeSheet(); return; }
    if (e.key !== 'Tab') return;
    /* The focus stays inside while it is open: the sheet itself is the first
       stop, and the ends of the list wrap onto each other. */
    const p = _shParts();
    const f = _shFocusable(p.sheet);
    if (!f.length) { e.preventDefault(); return; }
    const here = document.activeElement;
    if (here === p.sheet) {
      e.preventDefault();
      (e.shiftKey ? f[f.length - 1] : f[0]).focus();
    } else if (!e.shiftKey && here === f[f.length - 1]) {
      e.preventDefault(); f[0].focus();
    } else if (e.shiftKey && here === f[0]) {
      e.preventDefault(); f[f.length - 1].focus();
    } else if (!p.sheet.contains(here)) {
      e.preventDefault(); f[0].focus();
    }
  }, true);
}
