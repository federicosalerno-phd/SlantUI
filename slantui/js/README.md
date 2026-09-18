The browser side scripts, in load order:

| File | What | Leaves on the window |
|------|------|----------------------|
| `theme.js` | the roles read back off `:root` for a canvas, and four pieces of colour maths | `Theme`, `THEME_ROLES` |
| `bridge.js` | the QWebChannel transport, with a queue for calls made too early | `Bridge`, `be`, `beJson` |
| `widgets.js` | the dropdown, the number stepper, text that has to fit on one line | `initSelects`, `numStep`, `fitOneLine` |
| `titlebar.js` | the oblique band, the window buttons, the resize strips, the credit line | `initTitlebar`, `shapeTitleBar`, `onWindowMaximized`, `roundedPolyPath`, `CREDIT_TEXT` |

Classic scripts, not modules, because the embedded browser serves the page
from `file://`. `slantui.js` (the Python package in this folder) knows the
order and hands out the paths. `tests/test_scripts.py` runs them in a bare V8
against `tests/fakedom.js`.
