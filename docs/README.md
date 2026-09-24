# The gallery

`gallery.html` is a SlantUI window holding a catalogue of SlantUI: one cell
for every component the library draws, laid out for reading. The shell around
it, the oblique band, the rail, the toolbar and the side panel, is the real
thing, so the shots of those are shots of the window you are looking at.

```bash
.venv\Scripts\python docs\capture.py            write docs/shots/
.venv\Scripts\python docs\capture.py --show     open it and leave it open
.venv\Scripts\python docs\capture.py --tour     the example's window as well
.venv\Scripts\python docs\splash.py             the WPF loading screen
.venv\Scripts\python docs\publish.py            copy what the pages show into docs/img/
```

The first three need SlantUI installed in the environment, as the example
does: `pip install -e ".[shell,dev]"`. `splash.py` needs Windows PowerShell
and nothing else. `publish.py` needs nothing.

<picture>
<source media="(prefers-color-scheme: dark)" srcset="img/gold-dark/window.png">
<img src="img/gold-light/window.png" width="1240" alt="The gallery window: the catalogue in the work area, the eight palettes in the side panel">
</picture>

## How a picture gets made

No screenshot tool, and nothing cropped by hand. The window renders the page,
`QQuickView.grabWindow()` hands the frame back as a `QImage`, and the page
says which rectangle of it to keep. Every element with a `data-shot`
attribute is one picture; `gallery.js` answers six calls:

```
shotNames()        every name, in the order they appear
pose(name)         scroll it into view and put it in the state it is shot in
isolate(name)      empty every ancestor and hide everything else
shotRect(name)     what it covers, in CSS pixels of the viewport
unisolate()        put the page back
unpose()           take the state back off
```

So a shot is of the real widget, drawn by the real window, in the real
palette. It cannot drift away from what the library does, which a picture
made once and kept in a folder always does.

The isolation is what makes the picture the widget and not the page it was
standing on. Every ancestor of the shot gives up its fill, everything that is
not the shot is made invisible, and `capture.py` clears the colour behind the
page, so the frame comes back with real transparency around the widget. The
rectangle follows from the same idea: it is what the shot paints, a fill, a
border, a shadow or a glyph, and not the block it was laid out in, so a row
of three buttons is cropped to the three buttons. A picture of a whole window
is cut to the radius Windows rounds a window to.

Four of the thirty one are states no markup can hold by itself: the dropdown's
popup only exists while it is open, and the toast and the two scrim cards
belong to the window and not to a cell. Those have an entry in `POSES` and a
button in their cell, so a person browsing the page can see them too.

## What comes out

```
docs/shots/<palette>/<name>.png     40 shots, 8 palettes
docs/shots/tour/<palette>-<n>.png   the example's window, with --tour
docs/shots/shots.json               what was written, and how big
```

The manifest carries the CSS size of every shot next to its files, which is
the width to give an `img` tag: the files are at four times that by default,
so a reader who zooms into one finds more of it. The glyphs are drawn with
grey antialiasing, because subpixel fringes are tuned to one display's pixels
and a picture is never looked at at the size it was drawn.

`--scale` fixes the device pixel ratio instead of taking the display's, so
the same command gives the same pixel sizes on a 100 % monitor and on a
150 % one. At 4 the window is larger than any screen, which is fine: the
scene graph renders all of it and the grab reads that, not the screen.
Chromium logs a line or two about its GPU context while that is true, and
the files are unaffected.

`--palettes` and `--shots` take comma separated lists and are how you
iterate on one cell without waiting for 248 files. A full run clears the
PNGs of each palette before writing them again, so a renamed shot leaves
nothing behind, and writes the manifest; a run of one shot touches that one
file and leaves the manifest as it was.

```bash
.venv\Scripts\python docs\capture.py --palettes gold-dark --shots buttons,chips
```

## shots/ is not in the repository, img/ is

`docs/shots/` is generated and ignored by git: 334 files and twenty four
megabytes with `--tour`, and all but a few of them illustrate nothing. GitHub
draws what is in the repository and nothing else, so the ones the pages do
show are copied into `docs/img/`, which is tracked.

```bash
.venv\Scripts\python docs\publish.py           write docs/img/
.venv\Scripts\python docs\publish.py --check   say what is out of date
```

The pages are the list, and there is no second one to keep in step. Every
picture a tracked markdown file points at under `docs/img` is carried, its
source is the same path under `docs/shots`, and a file nobody points at any
more is deleted on the next run. So a picture enters the repository by being
put in a page and leaves it by being taken out of one.

`tests/test_readme.py` is the other half: it fails when a page shows a
picture the repository has not got, when the folder carries one nobody shows,
when a page points into `docs/shots`, when a published picture is not what
the last capture wrote, and when an `img` tag gives a width that is not the
one the shot was taken at. The two checks that need `docs/shots` skip
where it is not there, which is every clone but this one.

## The loading screen is shot somewhere else

`splash.py` writes `docs/shots/<palette>/splash.png` and has nothing to do
with the gallery. The screen it photographs is the WPF half of the library and
it draws on a thread of its own, through a `HostVisual`, which a
`RenderTargetBitmap` of a window does not contain at all: a picture of that
window taken the ordinary way comes back with a hole where the screen should
be. So the tool takes two. The window renders itself, band and blurred page
and all; the drawing thread hands over what it has on screen through
`Snapshot`; the two are laid together at the same scale and cut to the corner
radius Windows cuts a window to, the way `capture.py` cuts its own.

What is under the veil is the gallery's own `window.png` with its band cropped
off, put back into a real window as its page. Under fourteen pixels of blur
nobody is reading it. What it is there for is that the light and the shapes
behind the scrim belong to a real page instead of a flat fill.

It needs `capture.py` to have run first, because it shoots over what that
wrote, and it writes into the same folders, so `publish.py` carries it into
`docs/img` like any other picture a page shows. It is not in the manifest:
`capture.py` writes that, and a full run of `capture.py` is still what the
manifest counts.

Everything else in this folder is source.
