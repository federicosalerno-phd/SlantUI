/* ============================================================================
   theme.js: the roles, read back off the page for code that cannot use CSS.

   A <canvas>, a WebGL material and an inline style set from a script all
   need a colour as a value, and none of them can read a custom property.
   This file reads the roles off :root, once at start up and again whenever
   the palette is switched, and carries the four pieces of colour maths a
   canvas needs.

   The maths is a small copy of one corner of slantui/tokens/color.py, on
   purpose. A canvas needs a hex string turned into rgb() or rgba() and a
   blend between two of them, and a build step that shares forty lines with
   the Python is a worse trade than two copies that a test holds to the same
   answers. Note that the blend here is a straight line in sRGB, which is
   what a canvas gradient wants; the Python blends in OKLab, which is what a
   palette wants.

   Leaves on the window: Theme, THEME_ROLES.
   ========================================================================== */

/* The thirty one roles, in the order of slantui/tokens/roles.py. A test keeps the
   two lists the same. */
const THEME_ROLES = [
  'surface-0', 'surface-1', 'surface-2', 'surface-3',
  'control', 'control-hover', 'control-active',
  'text-1', 'text-2', 'text-3', 'text-4',
  'accent', 'accent-hover', 'accent-active', 'on-accent',
  'accent-text', 'accent-surface', 'accent-surface-hover',
  'ok', 'warn', 'err', 'on-status', 'ok-text', 'warn-text', 'err-text',
  'warn-surface',
  'err-surface', 'err-surface-hover',
  'scrim', 'shadow', 'overlay',
];

const Theme = {
  /* Resolved values, name to string, as of the last read(). */
  values: {},

  /* Read custom properties off :root and keep them. With no argument, the
     thirty one roles. With a list, those names (without the two dashes), which is
     how an application reads its own tokens through the same call. */
  read: function (names) {
    const cs = getComputedStyle(document.documentElement);
    const list = names || THEME_ROLES;
    for (let i = 0; i < list.length; i++) {
      this.values[list[i]] = cs.getPropertyValue('--' + list[i]).trim();
    }
    return this.values;
  },

  /* One value as last read, or '' for a name nobody has read. */
  get: function (name) {
    return this.values[name] || '';
  },

  /* Switch palette. The slug goes on <html data-palette>, which is what
     palettes.css keys on; an empty slug restores the default. Every name
     read so far is read again, so code that asks get() after this sees the
     new palette. */
  setPalette: function (slug) {
    const root = document.documentElement;
    if (slug) root.setAttribute('data-palette', slug);
    else root.removeAttribute('data-palette');
    const known = Object.keys(this.values);
    this.read(known.length ? known : null);
  },

  /* The current slug, or '' on the default palette. */
  palette: function () {
    return document.documentElement.getAttribute('data-palette') || '';
  },

  /* ── colour maths, hex in and canvas ready values out ───────────────────── */

  /* [r, g, b, a] from #RGB, #RGBA, #RRGGBB or #RRGGBBAA. a is 0 to 1. */
  rgb: function (h) {
    h = String(h).trim().replace('#', '');
    if (h.length === 3 || h.length === 4) {
      h = h.split('').map(function (c) { return c + c; }).join('');
    }
    const n = function (i) { return parseInt(h.slice(i, i + 2), 16); };
    const a = h.length === 8 ? n(6) / 255 : 1;
    return [n(0), n(2), n(4), a];
  },

  /* A straight blend between two colours, t from 0 to 1, as rgb(). */
  mix: function (a, b, t) {
    const x = this.rgb(a), y = this.rgb(b);
    const c = function (i) { return Math.round(x[i] + (y[i] - x[i]) * t); };
    return 'rgb(' + c(0) + ',' + c(1) + ',' + c(2) + ')';
  },

  /* The same colour at another alpha, as rgba(). */
  rgba: function (h, a) {
    const x = this.rgb(h);
    return 'rgba(' + x[0] + ',' + x[1] + ',' + x[2] + ',' + a + ')';
  },

  /* 0xRRGGBB, the form a Three.js material takes. */
  hex3d: function (h) {
    const x = this.rgb(h);
    return (x[0] << 16) | (x[1] << 8) | x[2];
  },
};
