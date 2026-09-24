"""The SlantUI tour: one window, four steps, one of every widget.

Run it from the repository with the environment that has PyQt6 in it:

    .venv\\Scripts\\python examples\\tour\\main.py

Nothing in this folder copies a stylesheet or a script out of another
application, and nothing in it reaches outside its own folder. The page is
built on SlantUI's five
stylesheets, its four scripts and its shell, which is what the example is
here to prove.

The one thing an application has to arrange for itself is how the page
reaches the library's files. The page is loaded from ``file://``, so it can
only link what is on disk next to it, and SlantUI's own files live wherever
pip put the package. ``bundle()`` answers that: the five stylesheets and the
four scripts, in load order, as one string each. Written next to the page,
they keep ``index.html`` a plain static file with two relative links in it,
and the same three lines work from a pip install and from a checkout.

An application that ships to a read only folder writes them once at install
time instead, into the same folder as the page.
"""
from __future__ import annotations

import sys
from pathlib import Path

from slantui import css, js
from slantui.shell import Application, Splash, Window
from slantui.tokens import DEFAULT, PALETTES

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import Tour  # noqa: E402  the backend sits next to this file

APP_NAME = "SlantUI Tour"
UI = Path(__file__).resolve().parent / "ui"


def write_library_files() -> None:
    """Put SlantUI's stylesheets and scripts next to the page.

    Rewritten on every start, so a change to a file in ``slantui/css`` or
    ``slantui/js`` shows up the next time the window opens.
    """
    (UI / "slantui.css").write_text(css.bundle(), encoding="utf-8")
    (UI / "slantui.js").write_text(js.bundle(), encoding="utf-8")
    # The mark for the loading screen, which is a file and not a fill this
    # time: the one in the band is inline SVG taking the accent from the
    # page's own colour, and a file has to carry its own. So it is written
    # here, out of the palette, like everything else this example draws.
    (UI / "brand.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="%s"><path d="M2 5.8h20v5.6h-6.1L9.6 18.2H2z"/></svg>'
        % PALETTES[DEFAULT.slug]["accent"], encoding="utf-8")


def main() -> int:
    write_library_files()
    app = Application(APP_NAME, app_id="SlantUI.Tour")
    tour = Tour()
    win = Window(UI / "index.html", bridge=tour, title=APP_NAME,
                 size=(1240, 800), min_size=(940, 600))

    # What every application wearing this library does, in three lines: the
    # loading screen over its own window while the page loads, and away when
    # the page speaks. It starts waiting, because at this point there is
    # nothing to measure; the page's own loading is followed from there.
    splash = Splash(window=win, logo=UI / "brand.svg", text="starting", busy=True)
    splash.show()
    tour.on_page_ready = lambda: splash.hide()

    win.show()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
