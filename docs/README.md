# The gallery

`gallery.html` is a SlantUI window holding a catalogue of SlantUI: one cell
for every component the library draws, laid out for reading. The shell around
it, the oblique band, the rail, the toolbar and the side panel, is the real
thing, so the shots of those are shots of the window you are looking at.

```bash
.venv\Scripts\python docs\capture.py            write docs/shots/
.venv\Scripts\python docs\capture.py --show     open it and leave it open
.venv\Scripts\python docs\capture.py --tour     the example's window as well
.venv\Scripts\python docs\publish.py            copy what the pages show into docs/img/
```

The first three need SlantUI installed in the environment, as the example
does: `pip install -e ".[shell,dev]"`. `publish.py` needs nothing.

![The gallery window: the catalogue in the work area, the eight palettes in the side panel](img/gold-dark/window.png)

## How a picture gets made

No screenshot tool, and nothing cropped by hand. The window renders the page,
`QQuickView.grabWindow()` hands the frame back as a `QImage`, and the page
says which rectangle of it to keep. Every element with a `data-shot`
attribute is one picture; `gallery.js` answers four calls:

```
shotNames()        every name, in the order they appear
pose(name)         scroll it into view and put it in the state it is shot in
shotRect(name)     where it ended up, in CSS pixels of the viewport
unpose()           take the state back off
```

So a shot is of the real widget, drawn by the real window, in the real
palette. It cannot drift away from what the library does, which a picture
made once and kept in a folder always does.

Four of the thirty are states no markup can hold by itself: the dropdown's
popup only exists while it is open, and the toast and the two scrim cards
belong to the window and not to a cell. Those have an entry in `POSES` and a
button in their cell, so a person browsing the page can see them too.

## What comes out

```
docs/shots/<palette>/<name>.png     30 shots, 8 palettes
docs/shots/tour/<palette>-<n>.png   the example's window, with --tour
docs/shots/shots.json               what was written, and how big
```

The manifest carries the CSS size of every shot next to its files, which is
the width to give an `img` tag: the files are at twice that by default, so
they stay sharp on a dense display.

`--scale` fixes the device pixel ratio instead of taking the display's, so
the same command gives the same pixel sizes on a 100 % monitor and on a
150 % one. At 2 the window is larger than most screens, which is fine: the
scene graph renders all of it and the grab reads that, not the screen.
Chromium logs a line or two about its GPU context while that is true, and
the files are unaffected.

`--palettes` and `--shots` take comma separated lists and are how you
iterate on one cell without waiting for 240 files. A full run clears the
PNGs of each palette before writing them again, so a renamed shot leaves
nothing behind, and writes the manifest; a run of one shot touches that one
file and leaves the manifest as it was.

```bash
.venv\Scripts\python docs\capture.py --palettes gold-dark --shots buttons,chips
```

## shots/ is not in the repository, img/ is

`docs/shots/` is generated and ignored by git: 251 files and six megabytes
with `--tour`, and all but a few of them illustrate nothing. GitHub draws what
is in the repository and nothing else, so the ones the pages do show are
copied into `docs/img/`, which is tracked.

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

Everything else in this folder is source.
