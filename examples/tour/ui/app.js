/* ============================================================================
   The tour's own script. Everything it calls that is not in this file comes
   from SlantUI: Bridge and be() and beJson() from bridge.js, Theme from
   theme.js, initSelects() numStep() fitOneLine() from widgets.js, and
   initTitlebar() roundedPolyPath() from titlebar.js.

   The page is a classic script, like the library's four, because the window
   serves it from file:// and a file:// page gets no module loading.
   ========================================================================== */

/* The switcher's labels and the slug each one sets. The slugs are the eight
   in slantui/tokens/palettes.py; palettes.css keys on them. */
const PALETTES = {
  'Gold Dark': 'gold-dark',
  'Gold Light': 'gold-light',
  'Teal Dark': 'teal-dark',
  'Blue Dark': 'blue-dark',
  'Purple Dark': 'purple-dark',
  'Green Dark': 'green-dark',
  'Slate Light': 'slate-light',
  'High Contrast': 'high-contrast',
};

const JOB_MS = { 'Quick (1.2 s)': 1200, 'Normal (2.4 s)': 2400, 'Slow (4.8 s)': 4800 };

/* The page's own tokens, read off :root through the same call the roles use.
   The four metrics are the real geometry of the window's title bar, which is
   what the sliders start at and what the reset button comes back to. */
const METRICS = ['tbar-h', 'tbar-thin', 'tbar-slant', 'tbar-join', 'font'];

const GROUP_ROLE = { accent: 'accent-text', ok: 'ok-text' };

const HINTS = [
  'Drop a file on the card, or click it',
  'The three sliders and the field cut the shape on the stage',
  'Run calls a slot; the card follows the signal that answers',
  'Numbers in rows, and the versions this window is running on',
];

let step = 0;            // which of the four steps is showing
let zoom = 1;            // the stage's own zoom, off the toolbar
let corner = 'round';    // which .mitem is selected
let showRoles = false;   // the toolbar toggle
let fileName = '';       // what was dropped on the card
let ticks = 0;           // how many progress reports the last job sent
let running = false;
let toastTimer = null;
let busyTimer = null;

function $(id) { return document.getElementById(id); }

function num(name) { return parseFloat(Theme.get(name)) || 0; }

/* ── the steps ────────────────────────────────────────────────────────────── */
function go(i) {
  step = i;
  document.querySelectorAll('.tab').forEach(function (t) {
    const n = Number(t.dataset.step);
    t.classList.toggle('active', n === i);
    t.classList.toggle('done', n < i);
  });
  document.querySelectorAll('.rp-page').forEach(function (p) {
    p.classList.toggle('show', Number(p.dataset.step) === i);
  });

  /* The card is step one's; the drawing belongs to the three after it. */
  const drawing = i > 0;
  $('dz').classList.toggle('hidden', drawing);
  $('cv').classList.toggle('hidden', !drawing);
  $('covl').classList.toggle('hidden', !drawing);
  $('czoom').classList.toggle('hidden', !drawing);

  /* A control a step cannot use is hidden in place, never removed: the row
     is on every screen and nothing in it is allowed to move. */
  ['ctIn', 'ctOut', 'ctFit', 'ctRoles'].forEach(function (id) {
    $(id).classList.toggle('ghost', !drawing);
  });
  $('ctClear').classList.toggle('ghost', !fileName);
  $('cthint').textContent = HINTS[i];
  if (drawing) draw();
}

/* ── the palette ──────────────────────────────────────────────────────────── */
function readTheme() {
  Theme.read();             // the thirty one roles
  Theme.read(METRICS);      // and this page's own, through the same call
}

function setPalette(label) {
  const slug = PALETTES[label];
  if (!slug) return;
  Theme.setPalette(slug);   // the attribute on <html>, and everything read again
  be('setPalette', slug);   // and the colour behind the page, which is the window's
  /* A combo takes a value the way a select does, and setting it fires
     nothing, so this cannot come back round. */
  $('palette').value = label;
  paint();
}

/* Everything that holds a colour as a value instead of as a role: the group
   headings, the bar on the active row, and the drawing. Run at start up and
   again after every palette change. */
function paint() {
  document.querySelectorAll('.mg').forEach(function (h) {
    h.style.color = Theme.get(GROUP_ROLE[h.dataset.group]);
  });
  document.querySelectorAll('.mrow').forEach(function (r) {
    r.style.setProperty('--gc', Theme.get(GROUP_ROLE[r.dataset.group]));
  });
  if (step > 0) draw();
}

/* ── the drawing on the stage ─────────────────────────────────────────────── */
/* The title bar's own profile, drawn large: the same points titlebar.js cuts
   the band to, through the same roundedPolyPath(), painted with Path2D
   instead of a clip path. One geometry, two ways of putting it on screen. */
function draw() {
  const cv = $('cv'), stage = $('stage');
  const w = stage.clientWidth, h = stage.clientHeight;
  if (!w || !h) return;

  /* The backing store is in device pixels and the drawing in CSS pixels, so
     a 150 % display gets a sharp line instead of a soft one. */
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(h * dpr);
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);

  const k = 2.2 * zoom;
  const h1 = num('tbar-h') * k;
  const h2 = Number($('slThin').value) * k;
  const slant = Number($('slSlant').value) * k;
  const join = corner === 'round' ? Number($('slJoin').value) * k : 0;
  const W = Math.min(w - 72, 880 * zoom);
  const x1 = Math.min(W, Number($('brandW').value) * k);
  const x2 = Math.min(W, x1 + slant);

  const pts = [
    { x: 0, y: 0 },
    { x: W, y: 0 },
    { x: W, y: h2 },
    { x: x2, y: h2, r: join },
    { x: x1, y: h1, r: join },
    { x: 0, y: h1 },
  ];

  /* The block behind the band grows to hold the legend when it is on, and
     the whole composition is centred on that, never on the band alone. */
  const block = h1 + (showRoles ? 78 : 46) * zoom;

  g.save();
  g.translate(Math.round((w - W) / 2), Math.round((h - block) / 2));

  /* The window behind the band, so the shape reads as what it is. */
  g.fillStyle = Theme.get('surface-1');
  g.beginPath();
  g.rect(0, 0, W, block);
  g.fill();

  g.fillStyle = Theme.get($('fill').value);
  g.fill(new Path2D(roundedPolyPath(pts)));

  const font = Theme.get('font');
  g.fillStyle = Theme.get('text-1');
  g.font = '600 ' + (15 * zoom).toFixed(1) + 'px ' + font;
  g.textBaseline = 'middle';
  g.fillText('SlantUI', 26 * zoom, h1 / 2);

  g.fillStyle = Theme.get('text-4');
  g.font = 'italic ' + (11 * zoom).toFixed(1) + 'px ' + font;
  g.textAlign = 'center';
  g.fillText(CREDIT_TEXT, W / 2, h2 / 2);
  g.textAlign = 'left';

  if (showRoles) legend(g, W, h1);
  g.restore();

  $('czoom').textContent = Math.round(zoom * 100) + ' %';
  $('covlA').textContent = 'roundedPolyPath, ' + pts.length + ' points';
  $('covlB').textContent = 'fill: ' + $('fill').value;
}

/* The roles the drawing just used, named on the stage. */
function legend(g, W, h1) {
  const names = ['surface-1', $('fill').value, 'text-1', 'text-4'];
  const y0 = h1 + 18 * zoom;
  g.font = (11 * zoom).toFixed(1) + 'px ' + Theme.get('font');
  names.forEach(function (name, i) {
    const y = y0 + i * 15 * zoom;
    g.fillStyle = Theme.get(name);
    g.fillRect(26 * zoom, y - 4 * zoom, 9 * zoom, 9 * zoom);
    g.fillStyle = Theme.get('text-3');
    g.fillText(name, 42 * zoom, y);
  });
}

/* ── the file on the card ─────────────────────────────────────────────────── */
function takeFile(name, type, bytes) {
  fileName = name;
  $('fileIcon').classList.remove('hidden');
  /* The toolbar has room for so much, and a name can run to fifty
     characters: fitOneLine shrinks it, then drops the middle and keeps the
     extension, with the whole thing in the tooltip. */
  fitOneLine($('fname'), name, 11.5, 9);
  $('piName').textContent = name;
  $('piType').textContent = type || 'unknown';
  $('piSize').textContent = (bytes / 1024).toFixed(1) + ' kB';
  $('ctClear').classList.remove('ghost');
  setStatus('ok', 'File taken');
  toast('Taken: ' + name);
}

function forgetFile() {
  fileName = '';
  $('fileIcon').classList.add('hidden');
  fitOneLine($('fname'), '', 11.5, 9);
  $('piName').textContent = 'none';
  $('piType').textContent = 'none';
  $('piSize').textContent = '0';
  $('ctClear').classList.add('ghost');
  setStatus('', 'Ready');
}

/* ── the status pill and the toast ────────────────────────────────────────── */
function setStatus(kind, text) {
  $('sd').className = 'sd' + (kind ? ' ' + kind : '');
  $('st').textContent = text;
}

function toast(text, ms) {
  const el = $('toast');
  el.textContent = text;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { el.classList.remove('show'); }, ms || 2200);
}

/* ── the job, which is the round trip to Python ───────────────────────────── */
function runJob() {
  if (running) return;
  running = true;
  ticks = 0;
  $('btnRun').disabled = true;
  $('btnCancel').disabled = false;
  $('chipCancel').classList.add('hidden');
  $('chipStale').classList.add('hidden');
  $('calloutErr').classList.add('hidden');
  $('calloutRun').classList.remove('hidden');
  $('chipRun').textContent = 'running';
  $('job').classList.add('show');
  setStatus('busy', 'Working');
  be('runJob', JOB_MS[$('length').value] || 2400);
}

function onProgress(pct, stage) {
  ticks += 1;
  $('jobPct').textContent = pct;
  /* The fill moves through a transform, which the compositor does on its
     own, and never through width, which is a layout on every frame. */
  $('jobFill').style.transform = 'scaleX(' + (pct / 100) + ')';
  $('jobStage').textContent = stage;
  $('mvStage').textContent = stage;
  $('piTicks').textContent = ticks;
  $('mvTicks').textContent = ticks;
}

function onJobDone(finished) {
  running = false;
  $('btnRun').disabled = false;
  $('btnCancel').disabled = true;
  $('job').classList.remove('show');
  $('chipRun').textContent = finished ? 'finished' : 'idle';
  $('chipCancel').classList.toggle('hidden', finished);
  $('chipStale').classList.toggle('hidden', finished);
  $('calloutRun').classList.add('hidden');
  $('calloutErr').classList.toggle('hidden', finished);
  $('piEnded').textContent = finished ? 'finished' : 'cancelled';
  setStatus(finished ? 'ok' : 'warn', finished ? 'Done' : 'Cancelled');
  toast(finished ? 'The job finished' : 'The job was cancelled');
}

function showInfo(info) {
  if (!info) return;
  $('piSlantui').textContent = info.slantui;
  $('piPython').textContent = info.python;
  $('piQt').textContent = info.qt;
  $('piBinding').textContent = info.binding;
  $('btnAbout').title = 'SlantUI ' + info.slantui + ' on ' + info.binding +
                        ', Qt ' + info.qt;
}

/* ── wiring ───────────────────────────────────────────────────────────────── */
function wireSteps() {
  document.querySelectorAll('.tab').forEach(function (t) {
    t.onclick = function () { go(Number(t.dataset.step)); };
  });
  document.querySelectorAll('[data-go]').forEach(function (b) {
    b.onclick = function () { go(Number(b.dataset.go)); };
  });
}

function wireToolbar() {
  $('ctIn').onclick = function () { setZoom(zoom * 1.18); };
  $('ctOut').onclick = function () { setZoom(zoom * 0.85); };
  $('ctFit').onclick = function () { setZoom(1); };
  $('ctRoles').onclick = function () {
    showRoles = !showRoles;
    $('ctRoles').classList.toggle('on', showRoles);
    draw();
  };
  $('ctClear').onclick = forgetFile;
}

function setZoom(z) {
  zoom = Math.max(0.5, Math.min(2.2, z));
  draw();
}

function wireControls() {
  ['slThin', 'slSlant', 'slJoin'].forEach(function (id) {
    $(id).oninput = function () { readSliders(); draw(); };
  });
  $('fill').onchange = draw;
  $('brandW').oninput = draw;
  document.querySelectorAll('.spin-b').forEach(function (b) {
    b.onclick = function () { numStep(b.dataset.stepFor, Number(b.dataset.dir)); };
  });

  document.querySelectorAll('.mitem[data-corner]').forEach(function (m) {
    m.onclick = function () {
      document.querySelectorAll('.mitem').forEach(function (o) { o.classList.remove('sel'); });
      m.classList.add('sel');
      corner = m.dataset.corner;
      $('slJoin').disabled = corner !== 'round';
      draw();
    };
  });

  document.querySelectorAll('.mrow').forEach(function (r) {
    r.onclick = function () {
      document.querySelectorAll('.mrow').forEach(function (o) { o.classList.remove('active'); });
      r.classList.add('active');
    };
  });

  $('btnReset').onclick = function () {
    seedFromMetrics();
    draw();
    toast('Back to the metrics in metrics.css');
  };
}

function readSliders() {
  $('svThin').textContent = $('slThin').value + ' px';
  $('svSlant').textContent = $('slSlant').value + ' px';
  $('svJoin').textContent = $('slJoin').value + ' px';
  $('mvThin').textContent = $('slThin').value + ' px';
  $('mvSlant').textContent = $('slSlant').value + ' px';
  $('mvJoin').textContent = $('slJoin').value + ' px';
}

/* The sliders start at the window's real geometry, off metrics.css. */
function seedFromMetrics() {
  $('slThin').value = num('tbar-thin');
  $('slSlant').value = num('tbar-slant');
  $('slJoin').value = num('tbar-join');
  readSliders();
}

function wireJob() {
  $('btnRun').onclick = runJob;
  $('btnCancel').onclick = function () { be('cancelJob'); };
  $('btnBusy').onclick = function () {
    $('busy').classList.add('show');
    clearTimeout(busyTimer);
    busyTimer = setTimeout(function () { $('busy').classList.remove('show'); }, 1400);
  };
  $('btnFinish').onclick = function () {
    setStatus('ok', 'All good');
    toast('That is the whole widget set');
  };
  $('btnAbout').onclick = function () { toast($('btnAbout').title, 3000); };
}

function wireDropZone() {
  const dz = $('dz');
  dz.addEventListener('dragover', function (e) {
    e.preventDefault();
    dz.classList.add('dzover');
  });
  dz.addEventListener('dragleave', function () { dz.classList.remove('dzover'); });
  dz.addEventListener('drop', function (e) {
    e.preventDefault();
    dz.classList.remove('dzover');
    const f = e.dataTransfer.files[0];
    if (f) takeFile(f.name, f.type, f.size);
  });
  dz.onclick = function () {
    toast('A real application opens a file dialog here, from a slot of its own');
  };

  /* A file dropped anywhere else would make the browser navigate to it, and
     the application would be gone with no way back. Every page in an
     embedded browser wants these two lines. */
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) { e.preventDefault(); });
}

/* ── start up ─────────────────────────────────────────────────────────────── */
function boot() {
  Bridge.init();          // the channel, with everything queued until it is up
  initSelects();          // the dropdowns answer to .value from here on
  initTitlebar();         // the band, the window buttons, the credit line

  Bridge.on('progress', onProgress);
  Bridge.on('jobDone', onJobDone);
  beJson('appInfo', undefined, showInfo);

  readTheme();
  seedFromMetrics();
  wireSteps();
  wireToolbar();
  wireControls();
  wireJob();
  wireDropZone();

  $('palette').onchange = function () { setPalette($('palette').value); };
  window.addEventListener('resize', draw);

  paint();
  go(0);
  /* Once more after the first frame: the stage has no size until layout. */
  requestAnimationFrame(draw);
}

boot();
