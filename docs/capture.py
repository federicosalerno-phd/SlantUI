"""Open the gallery in a real SlantUI window and save a picture of every
component, in every palette.

    .venv\\Scripts\\python docs\\capture.py            write docs/shots/
    .venv\\Scripts\\python docs\\capture.py --show     open the page and leave it open
    .venv\\Scripts\\python docs\\capture.py --tour     the example window as well

There is no screenshot tool involved and nothing is ever cropped by hand. The
window renders the page, ``QQuickView.grabWindow()`` hands back the frame as a
``QImage``, and the page itself says which rectangle of it to keep: for every
element carrying ``data-shot``, ``docs/gallery.js`` scrolls it into view, puts
it in the state the shot wants, and answers with its rectangle in CSS pixels.
The Python multiplies that by the device pixel ratio of the grab and saves the
crop. So the picture is of the real widget, drawn by the real window, and it
cannot drift away from what the library does.

``--scale`` fixes the device pixel ratio instead of taking the display's, so
the same command produces the same pixel sizes on a 100 % monitor and on a
150 % one. Two is what a page rendered at twice the size wants; the manifest
records the CSS size of every shot next to the file, which is the width to
give an ``img`` tag.

The window is 1240 by 800, the same size the example opens at, so a shot of
the shell lines up with a shot of the application.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from slantui import __version__, css, js
from slantui.shell import Application, Bridge, Window, pyqtSlot
from slantui.shell.qt import USE_QT6, QEventLoop, QRect, QTimer, qVersion
from slantui.tokens import DEFAULT, PALETTES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAGE = HERE / "gallery.html"
TOUR = ROOT / "examples" / "tour"

WINDOW = (1240, 800)
MIN_WINDOW = (940, 600)

# Chromium up, the page parsed, the first frame on screen.
BOOT_MS = 2400
# After a palette change: the fills transition in a tenth of a second.
PALETTE_MS = 320
# After a pose: the popup is laid out, the toast has finished moving.
POSE_MS = 180


class Gallery(Bridge):
    """The gallery's backend: the two slots the page asks for.

    The six the title bar calls are on :class:`Bridge` already. ``setPalette``
    is the one from the example, and for the same reason: the page switches
    palette by itself, and the colour behind it belongs to the window.
    """

    @pyqtSlot(str)
    def setPalette(self, slug: str) -> None:
        if self.window is not None and slug in PALETTES:
            self.window.set_palette(slug)

    @pyqtSlot(result=str)
    def appInfo(self) -> str:
        return json.dumps({
            "slantui": __version__,
            "python": "%d.%d.%d" % sys.version_info[:3],
            "qt": qVersion(),
            "binding": "PyQt6" if USE_QT6 else "PyQt5",
        })


# ── driving the window ──────────────────────────────────────────────────────
def wait(ms: int) -> None:
    """Let the window paint for ``ms``. A sleep would freeze it instead."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def run_js(win: Window, expr: str, timeout_ms: int = 5000):
    """Run ``expr`` in the page and wait for its answer."""
    box: list = []
    loop = QEventLoop()

    def got(value):
        box.append(value)
        loop.quit()

    win.run_js(expr, got)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    if not box:
        raise RuntimeError(f"the page did not answer {expr!r} in {timeout_ms} ms")
    return box[0]


def place(win: Window) -> None:
    """Put the window at a known place on the screen it opened on.

    At a forced scale the window is larger than the screen in logical pixels,
    and where Windows puts one of those is not predictable: a run of this
    tool found it at -1280, off every screen, where Chromium stops laying the
    page out at all (innerWidth 0) and the grab comes back as one flat
    colour. The top left corner of the work area is always at least mostly on
    screen.
    """
    area = win.screen().availableGeometry()
    win.setPosition(area.x(), area.y())


def wait_for_page(win: Window, wired: str, tries: int = 25) -> None:
    """Hold until the page is parsed, laid out, and has ``wired`` on it.

    BOOT_MS is a guess, and a guess that is wrong now and then: a window that
    is slow to be mapped lays the page out at no size at all, every rectangle
    comes back as zeros, and the run dies on the first crop with nothing to
    say about why. This asks the page instead.
    """
    answer = ""
    for _ in range(tries):
        answer = run_js(win, "JSON.stringify([document.readyState, typeof "
                             + wired + ", innerWidth, innerHeight])")
        state, kind, w, h = json.loads(answer)
        if state == "complete" and kind == "function" and w > 0 and h > 0:
            return
        wait(200)
    screen = win.screen().geometry()
    raise RuntimeError(
        f"the page never came up: {answer}. The window is {win.width()} by "
        f"{win.height()} at {win.x()},{win.y()} on a screen of {screen.width()} "
        f"by {screen.height()}; a window with no screen under it is drawn by "
        f"nobody.")


def grab(win: Window, rect: dict[str, int] | None, path: Path) -> tuple[int, int]:
    """Save one crop of the window. ``rect`` is in CSS pixels, or ``None`` for
    the whole window. Returns the size of the file in pixels."""
    image = win.grabWindow()
    if image.isNull():
        raise RuntimeError("the window handed back an empty frame")
    whole = QRect(0, 0, image.width(), image.height())
    if rect is None:
        crop = image
    else:
        # The grab is in device pixels and the page measures in CSS pixels.
        k = image.width() / max(win.width(), 1)
        want = QRect(round(rect["x"] * k), round(rect["y"] * k),
                     round(rect["w"] * k), round(rect["h"] * k)).intersected(whole)
        if want.width() < 2 or want.height() < 2:
            raise RuntimeError(f"{path.stem}: the page put it outside the window, {rect}")
        crop = image.copy(want)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not crop.save(str(path)):
        raise RuntimeError(f"could not write {path}")
    return crop.width(), crop.height()


def count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def clear_pngs(folder: Path) -> None:
    """Drop the PNGs of a previous run, so a renamed shot leaves nothing
    behind. Only ``.png`` files, only in the folder being written, and only
    when the run is about to write all of them again."""
    if folder.is_dir():
        for old in folder.glob("*.png"):
            old.unlink()


# ── the gallery ─────────────────────────────────────────────────────────────
def shoot_gallery(win: Window, out: Path, slugs: list[str],
                  wanted: list[str] | None) -> dict:
    """Every shot in every palette. Returns the manifest."""
    names = json.loads(run_js(win, "shotNames()"))
    if wanted is not None:
        unknown = [n for n in wanted if n not in names]
        if unknown:
            raise SystemExit(f"the page has no shot called {', '.join(unknown)}")
        names = [n for n in names if n in wanted]

    shots: dict[str, dict] = {n: {"files": {}} for n in names}
    for slug in slugs:
        run_js(win, f"setPalette('{slug}')")
        wait(PALETTE_MS)
        folder = out / slug
        if wanted is None:
            # A run of one shot leaves the other twenty nine alone.
            clear_pngs(folder)
        for name in names:
            answer = run_js(win, f"pose('{name}')")
            if answer == "missing":
                raise RuntimeError(f"the page lost the shot called {name}")
            wait(POSE_MS)
            rect = json.loads(run_js(win, f"shotRect('{name}')"))
            if not rect:
                raise RuntimeError(f"the page gave no rectangle for {name}")
            w, h = grab(win, rect, folder / f"{name}.png")
            shots[name]["files"][slug] = f"{slug}/{name}.png"
            shots[name].setdefault("w", rect["w"])
            shots[name].setdefault("h", rect["h"])
            shots[name].setdefault("px", [w, h])
            run_js(win, "unpose()")
        print(f"  {slug:<14} {count(len(names), 'shot')}")
    return shots


# ── the example, for the picture at the top of the README ───────────────────
def shoot_tour(out: Path, slugs: list[str]) -> list[str]:
    """The example application's own window, whole, in every palette.

    The four steps are shot on the default palette and the others get the
    one with the drawing on the stage.
    """
    sys.path.insert(0, str(TOUR))
    try:
        import main as tour_main
        from backend import Tour
    finally:
        sys.path.remove(str(TOUR))

    tour_main.write_library_files()
    win = Window(TOUR / "ui" / "index.html", bridge=Tour(), title="SlantUI Tour",
                 size=WINDOW, min_size=MIN_WINDOW)
    place(win)
    win.show()
    wait(BOOT_MS)
    wait_for_page(win, "go")

    folder = out / "tour"
    if len(slugs) == len(PALETTES):
        clear_pngs(folder)
    files = []
    try:
        for slug in slugs:
            run_js(win, f"setPalette('{PALETTES[slug].name}')")
            wait(PALETTE_MS)
            steps = (0, 1, 2, 3) if slug == DEFAULT.slug else (1,)
            for step in steps:
                run_js(win, f"go({step})")
                wait(POSE_MS)
                name = f"{slug}-{step + 1}.png"
                grab(win, None, folder / name)
                files.append(f"tour/{name}")
            print(f"  {slug:<14} {count(len(steps), 'window shot')}")
    finally:
        QTimer.singleShot(0, win.close)
        wait(500)
    return files


# ── the run ─────────────────────────────────────────────────────────────────
def write_library_files() -> None:
    """SlantUI's stylesheets and scripts, next to the page.

    The same three lines the example uses, and for the same reason: the page
    is loaded from ``file://`` and the library lives wherever pip put it.
    """
    (HERE / "slantui.css").write_text(css.bundle(), encoding="utf-8")
    (HERE / "slantui.js").write_text(js.bundle(), encoding="utf-8")


def force_scale(scale: float) -> None:
    """Fix the device pixel ratio, whatever the display is set to.

    Qt multiplies the screen's own scale into the window, so on a 150 %
    monitor the shots would come out at 1.5 and on another machine at 1. With
    the screen's contribution switched off, the factor below is the whole of
    it. Both have to be in the environment before the application object
    exists. A window at twice the size is larger than the screen it opens on,
    which is fine: the scene graph renders all of it and the grab reads that,
    not the screen.
    """
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(scale)


def parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Shoot every SlantUI component in every palette.")
    p.add_argument("--show", action="store_true",
                   help="open the gallery and leave it open, shooting nothing")
    p.add_argument("--tour", action="store_true",
                   help="also shoot the example application's window")
    p.add_argument("--scale", type=float, default=2.0,
                   help="device pixel ratio of the shots (default 2)")
    p.add_argument("--out", type=Path, default=HERE / "shots",
                   help="where the PNGs go (default docs/shots)")
    p.add_argument("--palettes", default="",
                   help="a comma separated list of slugs, default all eight")
    p.add_argument("--shots", default="",
                   help="a comma separated list of shot names, default all")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    slugs = [s.strip() for s in args.palettes.split(",") if s.strip()] or list(PALETTES)
    unknown = [s for s in slugs if s not in PALETTES]
    if unknown:
        raise SystemExit(f"not a SlantUI palette: {', '.join(unknown)}")
    wanted = [s.strip() for s in args.shots.split(",") if s.strip()] or None

    if not args.show:
        force_scale(args.scale)
    write_library_files()

    app = Application("SlantUI Gallery", app_id="SlantUI.Gallery")
    win = Window(PAGE, bridge=Gallery(), title="SlantUI Gallery",
                 size=WINDOW, min_size=MIN_WINDOW)
    place(win)
    win.show()
    if args.show:
        return app.run()

    wait(BOOT_MS)
    win.raise_()
    wait_for_page(win, "shotNames")
    print(f"gallery, {args.scale:g}x")
    shots = shoot_gallery(win, args.out, slugs, wanted)
    QTimer.singleShot(0, win.close)
    wait(500)

    tour = shoot_tour(args.out, slugs) if args.tour else []

    total = sum(len(s["files"]) for s in shots.values()) + len(tour)
    if wanted is None and slugs == list(PALETTES):
        manifest = {
            "scale": args.scale,
            "window": {"w": WINDOW[0], "h": WINDOW[1]},
            "palettes": slugs,
            "shots": shots,
            "tour": tour,
        }
        (args.out / "shots.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                             encoding="utf-8")
        print(f"{total} files in {args.out}")
    else:
        # A partial run would write a manifest missing everything it skipped.
        print(f"{total} files in {args.out}, and shots.json is from the last full run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
