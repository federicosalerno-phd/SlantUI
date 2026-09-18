/* A stand in for the parts of the DOM the SlantUI scripts touch, so that
   tests/test_scripts.py can run them in a bare V8 with no browser.

   Only what the scripts use is here: elements with classes, attributes, a
   style object, listeners, a parent chain, single class selectors, and the
   two measurements the title bar and fitOneLine read. Measurements are set
   by the test, except scrollWidth, which is modelled from the text length
   and the font size so that fitOneLine has something to shrink against.

   The test sets CSS_VARS, a map of custom property name to value, and
   getComputedStyle reads from it. */

const CALLS = [];       // what the scripts asked the window manager for
const LOG = [];         // console output
const TIMERS = [];      // setTimeout callbacks, never run unless the test says

const console = {
  log: function () { LOG.push(['log'].concat(Array.prototype.slice.call(arguments))); },
  warn: function () { LOG.push(['warn'].concat(Array.prototype.slice.call(arguments))); },
  error: function () { LOG.push(['error'].concat(Array.prototype.slice.call(arguments))); },
};

function setTimeout(fn, ms) { TIMERS.push({ fn: fn, ms: ms }); return TIMERS.length; }
function requestAnimationFrame(fn) { fn(); }

function Event(type, init) {
  this.type = type;
  this.bubbles = !!(init && init.bubbles);
  this.defaultPrevented = false;
  this.target = null;
}
Event.prototype.preventDefault = function () { this.defaultPrevented = true; };
Event.prototype.stopPropagation = function () { this.stopped = true; };

let CSS_VARS = {};
function getComputedStyle() {
  return { getPropertyValue: function (name) { return CSS_VARS[name] || ''; } };
}

function El(tag, cls) {
  this.tagName = (tag || 'div').toUpperCase();
  this.className = cls || '';
  this.children = [];
  this.style = {};
  this.attrs = {};
  this.dataset = {};
  this.listeners = {};
  this.textContent = '';
  this.innerHTML = '';
  this.title = '';
  this.value = '';
  this.clientWidth = 0;
  this.clientHeight = 0;
  this.offsetHeight = 0;
  this.rect = { left: 0, top: 0, width: 0, height: 0, right: 0, bottom: 0 };
  this.parentNode = null;
  const self = this;
  this.classList = {
    contains: function (c) { return self.className.split(/\s+/).indexOf(c) >= 0; },
    add: function (c) { if (!this.contains(c)) self.className = (self.className + ' ' + c).trim(); },
    remove: function (c) { self.className = self.className.split(/\s+/).filter(function (x) { return x && x !== c; }).join(' '); },
    toggle: function (c, on) {
      if (on === undefined) on = !this.contains(c);
      if (on) this.add(c); else this.remove(c);
      return on;
    },
  };
}
Object.defineProperty(El.prototype, 'scrollWidth', {
  get: function () {
    const size = parseFloat(this.style.fontSize) || 12;
    return Math.ceil(this.textContent.length * size * 0.55);
  },
});
El.prototype.matches = function (sel) {
  const want = sel.split('.').filter(function (s) { return s.length; });
  const have = this.className.split(/\s+/);
  return want.every(function (c) { return have.indexOf(c) >= 0; });
};
El.prototype.querySelectorAll = function (sel) {
  const out = [];
  const walk = function (node) {
    for (let i = 0; i < node.children.length; i++) {
      const c = node.children[i];
      if (c.matches(sel)) out.push(c);
      walk(c);
    }
  };
  walk(this);
  return out;
};
El.prototype.querySelector = function (sel) {
  // '.a .b' means a .b somewhere under a .a; the scripts use at most one space.
  const parts = sel.trim().split(/\s+/);
  let scope = [this];
  for (let p = 0; p < parts.length; p++) {
    const next = [];
    for (let s = 0; s < scope.length; s++) next.push.apply(next, scope[s].querySelectorAll(parts[p]));
    scope = next;
    if (!scope.length) return null;
  }
  return scope[0];
};
El.prototype.closest = function (sel) {
  let n = this;
  while (n) { if (n.matches && n.matches(sel)) return n; n = n.parentNode; }
  return null;
};
El.prototype.contains = function (n) {
  while (n) { if (n === this) return true; n = n.parentNode; }
  return false;
};
El.prototype.getAttribute = function (k) { return (k in this.attrs) ? this.attrs[k] : null; };
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
El.prototype.removeAttribute = function (k) { delete this.attrs[k]; };
El.prototype.getBoundingClientRect = function () { return this.rect; };
El.prototype.appendChild = function (c) { c.parentNode = this; this.children.push(c); return c; };
El.prototype.insertBefore = function (c, ref) {
  c.parentNode = this;
  const i = this.children.indexOf(ref);
  if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
  return c;
};
El.prototype.removeChild = function (c) {
  const i = this.children.indexOf(c);
  if (i >= 0) this.children.splice(i, 1);
  c.parentNode = null;
  return c;
};
El.prototype.addEventListener = function (type, fn) {
  (this.listeners[type] = this.listeners[type] || []).push(fn);
};
/* Bubbles up the parent chain like the real thing, and runs the on<type>
   property handlers the widgets set, then the window's capture listeners
   first. */
El.prototype.dispatchEvent = function (ev) {
  ev.target = ev.target || this;
  const win = globalThis;
  const cap = (win._capture && win._capture[ev.type]) || [];
  for (let i = 0; i < cap.length; i++) cap[i].call(win, ev);
  let n = this;
  while (n && !ev.stopped) {
    const prop = n['on' + ev.type];
    if (typeof prop === 'function') prop.call(n, ev);
    const fns = n.listeners[ev.type] || [];
    for (let i = 0; i < fns.length; i++) fns[i].call(n, ev);
    if (!ev.bubbles) break;
    n = n.parentNode;
  }
  const bub = (win._bubble && win._bubble[ev.type]) || [];
  if (!ev.stopped) for (let i = 0; i < bub.length; i++) bub[i].call(win, ev);
  return !ev.defaultPrevented;
};

/* window is the global object in V8, so its listeners live on globalThis. */
globalThis.window = globalThis;
globalThis._capture = {};
globalThis._bubble = {};
globalThis.innerHeight = 600;
globalThis.innerWidth = 800;
globalThis.addEventListener = function (type, fn, capture) {
  const where = capture ? globalThis._capture : globalThis._bubble;
  (where[type] = where[type] || []).push(fn);
};
globalThis.CSS = { supports: function () { return globalThis.SUPPORTS_PATH !== false; } };
globalThis.SUPPORTS_PATH = true;

const document = {
  documentElement: new El('html'),
  body: new El('body'),
  createElement: function (tag) { return new El(tag); },
  querySelector: function (sel) { return this.body.querySelector(sel); },
  querySelectorAll: function (sel) { return this.body.querySelectorAll(sel); },
  getElementById: function (id) {
    const walk = function (node) {
      for (let i = 0; i < node.children.length; i++) {
        const c = node.children[i];
        if (c.attrs.id === id) return c;
        const hit = walk(c);
        if (hit) return hit;
      }
      return null;
    };
    return walk(this.body);
  },
};
document.body.parentNode = document.documentElement;

/* Convenience for the tests: fire an event with a target inside `el`. */
function fire(el, type, props) {
  const ev = new Event(type, { bubbles: true });
  if (props) for (const k in props) ev[k] = props[k];
  el.dispatchEvent(ev);
  return ev;
}
