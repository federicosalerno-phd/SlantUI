The browser side scripts, in load order:

| File | What | Leaves on the window |
|------|------|----------------------|
| `icons.js` | the named signs a window is made of, as markup | `ICONS`, `icon`, `setIcon`, `iconReport` |
| `theme.js` | the roles read back off `:root` for a canvas, and four pieces of colour maths | `Theme`, `THEME_ROLES` |
| `bridge.js` | the QWebChannel transport, with a queue for calls made too early | `Bridge`, `be`, `beJson` |
| `widgets.js` | the dropdown, the number stepper, a section that opens, the cells under a start page, text that has to fit on one line | `initSelects`, `numStep`, `initFolds`, `setFold`, `setStcell`, `fitOneLine` |
| `titlebar.js` | the oblique band, the strip under it, the window buttons, the resize strips, the credit line, the mark as a button | `initTitlebar`, `shapeTitleBar`, `setBrandAction`, `onWindowMaximized`, `roundedPolyPath`, `CREDIT_TEXT` |
| `sounds.js` | the window's seven sounds (CC0 samples, ready before the first press, played on the press of a `data-sound` control) and the switch on the band that keeps them quiet (Ctrl+M) | `initSounds`, `playSound`, `setSoundsOn`, `setSoundHints`, `soundsOn`, `soundLatency`, `renderSound`, `SOUND_VOICES` |

Classic scripts, not modules, because the embedded browser serves the page
from `file://`. `slantui.js` (the Python package in this folder) knows the
order and hands out the paths. `tests/test_scripts.py` runs them in a bare V8
against `tests/fakedom.js`.
