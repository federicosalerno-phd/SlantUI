# Examples

## tour

A window built on SlantUI and nothing else: the frameless shell, the oblique
title bar, a rail of four steps, a work area with a drawing in it, a side
panel holding one of every widget, a palette switcher that moves all eight
palettes, and a backend with four slots and two signals.

```bash
.venv\Scripts\python examples\tour\main.py
```

It is here to answer one question. The look came out of an application, so
until something else is built on it there is no proof that it left. Nothing
under `examples/` copies a stylesheet, imports another application, or
reaches out of its own folder, and a test says so.

```
main.py          the twelve lines that open the window
backend.py       one Bridge subclass: appInfo, runJob, cancelJob, setPalette
ui/index.html    the markup, which is one of every class components.css draws
ui/app.css       three rules, the whole of what the page adds to the library
ui/app.js        the steps, the palette, the drawing, the job
```

### What to take from it

**How the page finds the library.** The page is loaded from `file://`, so it
can only link what is on disk beside it, and SlantUI lives wherever pip put
it. `main.py` writes the five stylesheets and the four scripts next to the
page as one file each, from `slantui.css.bundle()` and `slantui.js.bundle()`,
before the window opens. `index.html` stays a static file with two relative
links in it, and the same three lines work from a checkout and from an
install. An application that ships into a read only folder does it once at
install time instead.

**How a page adds its own rules.** `app.css` is three rules long and names no
colour, only roles. Anything a page writes on top of the library is held to
the same rule, or it has one look on the dark palettes and another on the
light ones.

**How the page reaches Python.** Everything goes through `be()`, and
everything that comes back is a signal. The backend's four slots are the four
shapes an application needs: one that answers with JSON, one that starts work,
one that stops it, and one that drives the window.

**What the window chrome costs.** Nothing. The six slots the title bar calls
are on `Bridge` already, and the page's only part in it is the markup, one
`initTitlebar()` and the eight resize strips.

### What the tour does

| Step | On the stage | In the panel |
|------|--------------|--------------|
| Start | the drop card, which takes a real drop and names the file in the toolbar | notes, and the file that was dropped |
| Controls | the title bar's own profile, drawn large through `roundedPolyPath()` and `Path2D` | sliders, a dropdown, a number field with its stepper, a list to choose from |
| Run | the drawing, under the scrim while a job runs | the job, its progress card, and the spinner for work with no percentage |
| Results | the drawing | metric rows, the versions this window is running on, status words |

The sliders start at the real metrics, read off `:root` with
`Theme.read(['tbar-h', ...])`, which is the same call the thirty one roles come
through. The reset button puts them back.

### The tests

`tests/test_example.py` holds the example to its claim: every class the page
uses is defined by the library or by `app.css`, every widget the library
defines appears in the page, the page names no colour, every slot the page
calls exists on the backend, and the job reports from 0 to 100 in order. Five
more open the real window and drive it, and those need asking for:

```bash
set SLANTUI_SHOW_WINDOW=1
.venv\Scripts\python -m pytest tests/test_example.py -q
```
