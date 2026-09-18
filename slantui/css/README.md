The stylesheets, in load order:

| File | What | Written by |
|------|------|------------|
| `palettes.css` | the eight palettes as custom properties, one `:root` block each | `python -m slantui.tokens css -o slantui/css/palettes.css` |
| `metrics.css` | radii, type, the geometry of the band, the rail and the side panel | hand |
| `base.css` | reset, document defaults, focus ring, scrollbars, helpers | hand |
| `layout.css` | the shell: title bar, step rail, work area, side panel | hand |
| `components.css` | the widgets | hand |

`slantui.css` (the Python package in this folder) knows the order and hands
out the paths. Nothing hand written names a colour: `tests/test_stylesheets.py`
fails on a hex value, an `rgb()`, an id selector, a property that is neither
a role nor a metric, and a solid border.
