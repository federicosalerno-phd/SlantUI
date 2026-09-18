"""The gallery in docs/, and the script that shoots it.

The gallery is the catalogue the README is illustrated from, so the checks
here are about completeness and about the shots staying real. The text level
ones always run: every class the page uses has to be defined, every widget
the library draws has to be in the page (a widget missing from the gallery is
a widget nobody ever looks at again), the page may name no colour, and the
list of palettes the page carries has to be the one in the Python.

The rest open the real window and drive it the way capture.py does, so the
whole chain is tested: the page answers with a rectangle, the window hands
back a frame, and the crop lands on disk with something in it. They are
switched on by hand, as tests/test_window.py is:

    set SLANTUI_SHOW_WINDOW=1
    .venv\\Scripts\\python -m pytest tests/test_gallery.py -q
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

from slantui.css import STYLESHEETS
from slantui.css import path as css_path
from slantui.tokens import PALETTES

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PAGE = (DOCS / "gallery.html").read_text(encoding="utf-8")
GALLERY_CSS = (DOCS / "gallery.css").read_text(encoding="utf-8")
GALLERY_JS = (DOCS / "gallery.js").read_text(encoding="utf-8")
CAPTURE = (DOCS / "capture.py").read_text(encoding="utf-8")

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_CLASS_IN_CSS = re.compile(r"\.([a-zA-Z][\w-]*)")
_CLASS_ATTR = re.compile(r'class="([^"]+)"')
_SHOT = re.compile(r'data-shot="([^"]+)"')
_POSE_KEY = re.compile(r"^  '([\w-]+)': \{$", re.M)
_POSE_ATTR = re.compile(r'data-pose="([^"]+)"')
_SHOT_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# Classes no markup can carry, because a script is what puts them on. The
# gallery is shorter than the example's list by everything it shows on
# purpose: the popup's three classes only exist while the dropdown is open,
# and the gallery shoots that state from the real thing.
SCRIPT_ONLY = {
    "combopop", "combo-opt", "combo-on", "open",   # the dropdown, while it is open
    "maximized",                                   # the window state, on body
    "tbar-credit",                                 # titlebar.js writes it
}


def _css(name: str) -> str:
    return _COMMENT.sub(" ", css_path(name).read_text(encoding="utf-8"))


def _library_classes() -> set[str]:
    out: set[str] = set()
    for name in STYLESHEETS:
        out |= set(_CLASS_IN_CSS.findall(_css(name)))
    return out


def _script_hooks() -> set[str]:
    """Classes the library's own scripts look for, which carry no rule."""
    from slantui.js import SCRIPTS
    from slantui.js import path as js_path

    out: set[str] = set()
    for name in SCRIPTS:
        src = js_path(name).read_text(encoding="utf-8")
        for literal in re.findall(r"'([^']*)'", src):
            out |= set(re.findall(r"\.([a-zA-Z][\w-]*)", literal))
    return out


def _page_classes() -> set[str]:
    out: set[str] = set()
    for group in _CLASS_ATTR.findall(PAGE):
        out |= set(group.split())
    return out


def _shots() -> list[str]:
    return _SHOT.findall(PAGE)


# ── the gallery is there and is wired to the library ────────────────────────
def test_the_gallery_is_all_there():
    for name in ("gallery.html", "gallery.css", "gallery.js", "capture.py", "README.md"):
        assert (DOCS / name).is_file(), name


def test_the_page_loads_the_channel_before_the_library():
    channel = PAGE.index("qrc:///qtwebchannel/qwebchannel.js")
    library = PAGE.index('src="slantui.js"')
    page = PAGE.index('src="gallery.js"')
    assert channel < library < page


def test_the_page_links_what_capture_writes():
    for name in ("slantui.css", "slantui.js"):
        assert f'"{name}"' in CAPTURE, f"capture.py does not write {name}"
        assert f'"{name}"' in PAGE, f"gallery.html does not link {name}"


def test_the_two_written_files_are_not_tracked():
    """They are the library, copied next to the page on every run."""
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "docs/slantui.css" in ignored
    assert "docs/slantui.js" in ignored


# ── the vocabulary ──────────────────────────────────────────────────────────
def test_every_class_the_page_uses_is_defined():
    known = (_library_classes() | _script_hooks()
             | set(_CLASS_IN_CSS.findall(_COMMENT.sub(" ", GALLERY_CSS))))
    unknown = sorted(c for c in _page_classes() if c not in known)
    assert not unknown, f"nothing defines or looks for {unknown}"


def test_the_gallery_shows_every_widget_the_library_draws():
    """The point of the whole page. A class missing here is a component the
    README will never have a picture of."""
    missing = sorted(c for c in _library_classes()
                     if c not in SCRIPT_ONLY and c not in _page_classes())
    assert not missing, f"the gallery never shows {missing}"


def test_the_gallery_names_no_colour():
    hits = []
    for name, text in (("gallery.css", GALLERY_CSS), ("gallery.js", GALLERY_JS),
                       ("gallery.html", PAGE)):
        for n, line in enumerate(text.splitlines(), start=1):
            if re.search(r"#[0-9a-fA-F]{3}\b|#[0-9a-fA-F]{6}\b|\brgba?\(", line):
                hits.append(f"{name}:{n}  {line.strip()}")
    assert not hits, "\n" + "\n".join(hits)


# ── the shots ───────────────────────────────────────────────────────────────
def test_every_shot_is_named_once_and_names_a_file():
    names = _shots()
    assert len(names) > 20, "the catalogue lost most of its shots"
    assert len(names) == len(set(names)), \
        sorted(n for n in names if names.count(n) > 1)
    bad = [n for n in names if not _SHOT_NAME.match(n)]
    assert not bad, f"a shot name is also a file name: {bad}"


def test_the_shell_and_the_window_are_shot_too():
    """The four parts of the window are shot where they are, so the catalogue
    covers the shell as well as the widgets."""
    for name in ("window", "titlebar", "steps", "toolbar", "panel"):
        assert name in _shots(), name


def test_the_name_printed_under_a_cell_is_the_name_of_the_shot():
    """The cells say what their file is called. A shot renamed in one place
    and not the other would put the wrong caption in the README."""
    printed = re.findall(r'<div class="gal-name[^"]*">([^<]+)</div>', PAGE)
    assert printed, "no cell prints its name"
    unknown = sorted(set(printed) - set(_shots()))
    assert not unknown, f"printed under a cell but never shot: {unknown}"


def test_every_pose_is_a_shot_and_every_posed_cell_has_a_button():
    """The four states a shot cannot hold by itself."""
    poses = set(_POSE_KEY.findall(GALLERY_JS))
    assert poses == {"dropdown-open", "toast", "spinner", "progress"}
    assert poses <= set(_shots())
    assert set(_POSE_ATTR.findall(PAGE)) <= poses


def test_the_capture_shoots_every_palette_and_says_where():
    """Its defaults are the whole job: all eight palettes into docs/shots."""
    assert 'default=HERE / "shots"' in CAPTURE
    assert "or list(PALETTES)" in CAPTURE


# ── the page and the Python agree about the palettes ────────────────────────
def test_the_page_carries_the_eight_palettes_of_the_python():
    """The switcher is markup, so nothing else would notice a palette added
    in palettes.py and never listed here."""
    listed = re.findall(
        r"\{ name: '([^']+)', slug: '([^']+)', scheme: '([^']+)' \}", GALLERY_JS)
    assert [p.slug for p in PALETTES.values()] == [s for _, s, _ in listed]
    assert [p.name for p in PALETTES.values()] == [n for n, _, _ in listed]
    assert [p.scheme for p in PALETTES.values()] == [s for _, _, s in listed]


# ── the real window ─────────────────────────────────────────────────────────
show_window = pytest.mark.skipif(
    os.environ.get("SLANTUI_SHOW_WINDOW", "") != "1",
    reason="opens a real window; set SLANTUI_SHOW_WINDOW=1 to run it")


@pytest.fixture(scope="session")
def qt_app():
    """The application, for the whole run. Session scope, and the other two
    window opening modules take the same one: a QApplication dropped when a
    module ends takes the next module's window with it."""
    shell = pytest.importorskip("slantui.shell")
    from slantui.shell.qt import QApplication

    existing = QApplication.instance()
    return existing if existing is not None else shell.Application(
        "SlantUI gallery test", app_id="SlantUI.GalleryTest")


@pytest.fixture(scope="module")
def capture():
    """docs/capture.py, imported the way the example's backend is."""
    pytest.importorskip("slantui.shell")
    sys.path.insert(0, str(DOCS))
    try:
        import capture as module
    finally:
        sys.path.remove(str(DOCS))
    return module


@pytest.fixture(scope="module")
def win(capture, qt_app):
    """The gallery, opened the way capture.py opens it, at the display's own
    scale: --scale is about the files, not about the page."""
    from slantui.shell import Window
    from slantui.shell.qt import QTimer

    capture.write_library_files()
    w = Window(capture.PAGE, bridge=capture.Gallery(), title="SlantUI Gallery",
               size=capture.WINDOW, min_size=capture.MIN_WINDOW)
    w.setPosition(50, 30)
    w.show()
    capture.wait(capture.BOOT_MS)
    yield w
    QTimer.singleShot(0, w.close)
    capture.wait(700)


@show_window
def test_the_gallery_comes_up(capture, win):
    assert capture.run_js(win, "document.title") == "SlantUI Gallery"
    assert capture.run_js(win, "Bridge.ready") is True
    assert capture.run_js(win, "document.querySelector('.tbar-credit').textContent") == \
        "Layout by Federico Salerno"
    assert capture.run_js(win, "document.querySelector('.tbar-band').style.clipPath") \
        .startswith("path(")


@show_window
def test_the_page_lists_the_shots_the_markup_carries(capture, win):
    names = json.loads(capture.run_js(win, "shotNames()"))
    assert names == _shots()


@show_window
def test_a_shot_answers_with_a_rectangle_inside_the_window(capture, win):
    capture.run_js(win, "pose('buttons')")
    rect = json.loads(capture.run_js(win, "shotRect('buttons')"))
    assert rect["w"] > 100 and rect["h"] > 30
    assert 0 <= rect["x"] < win.width() and 0 <= rect["y"] < win.height()


@show_window
def test_the_open_dropdown_is_shot_with_its_popup(capture, win):
    """The pose that exists because no markup can hold the state: the popup
    is built by widgets.js on a click and lives outside the cell."""
    closed = json.loads(capture.run_js(win, "shotRect('dropdown-open')"))
    capture.run_js(win, "pose('dropdown-open')")
    capture.wait(capture.POSE_MS)
    assert capture.run_js(win, "document.querySelectorAll('.combopop').length") == 1
    open_rect = json.loads(capture.run_js(win, "shotRect('dropdown-open')"))
    assert open_rect["h"] > closed["h"] + 60, (closed, open_rect)

    capture.run_js(win, "unpose()")
    capture.wait(capture.POSE_MS)
    assert capture.run_js(win, "document.querySelectorAll('.combopop').length") == 0


@show_window
def test_the_palette_switch_reaches_the_window(capture, win):
    capture.run_js(win, "setPalette('slate-light')")
    capture.wait(capture.PALETTE_MS)
    assert capture.run_js(win, "document.documentElement.getAttribute('data-palette')") \
        == "slate-light"
    assert win.background == PALETTES["slate-light"]["surface-0"]

    capture.run_js(win, "setPalette('gold-dark')")
    capture.wait(capture.PALETTE_MS)
    assert win.background == PALETTES["gold-dark"]["surface-0"]


@show_window
def test_the_grab_has_the_page_in_it(capture, win):
    """The one thing the whole tool rests on. A window that handed back an
    empty frame, or the QML background with no web content in it, would write
    240 flat rectangles and nobody would notice until the README."""
    image = win.grabWindow()
    assert not image.isNull()
    assert image.width() >= win.width()
    seen = set()
    for y in range(0, image.height(), 23):
        for x in range(0, image.width(), 23):
            seen.add(image.pixel(x, y))
    assert len(seen) > 40, f"the frame has {len(seen)} colours in it"


@show_window
def test_a_crop_lands_on_disk_at_the_size_the_page_asked_for(capture, win, tmp_path):
    capture.run_js(win, "pose('chips')")
    capture.wait(capture.POSE_MS)
    rect = json.loads(capture.run_js(win, "shotRect('chips')"))
    out = tmp_path / "chips.png"
    w, h = capture.grab(win, rect, out)

    k = w / rect["w"]
    assert out.stat().st_size > 400
    assert abs(h - rect["h"] * k) <= 2
@show_window
def test_no_shot_is_wider_than_the_box_it_is_cropped_to(capture, win):
    """A crop is the element's own rectangle, so anything spilling out of it
    is cut off in the file and nowhere else. Five status pills in one row did
    exactly that."""
    spills = []
    for name in _shots():
        capture.run_js(win, f"pose('{name}')")
        capture.wait(60)
        size = json.loads(capture.run_js(win, f"""
            (function () {{
              var e = document.querySelector('[data-shot="{name}"]');
              return JSON.stringify([e.clientWidth, e.scrollWidth,
                                     e.clientHeight, e.scrollHeight]);
            }})()"""))
        cw, sw, ch, sh = size
        if sw > cw + 1 or sh > ch + 1:
            spills.append(f"{name}: {cw} by {ch} holds {sw} by {sh}")
        capture.run_js(win, "unpose()")
    assert not spills, "\n" + "\n".join(spills)


@show_window
def test_nothing_in_the_page_throws_when_every_control_is_clicked(capture, win):
    """Clicks the toolbar, the palette list, the footer and the four pose
    buttons. A JavaScript error in a handler is silent in an embedded
    browser: the button stops working and the page looks no different.

    Last in the file, since it leaves the page on another palette and puts
    the page back itself.
    """
    capture.run_js(win, "window.__errs = []; "
                        "window.onerror = function (m) { window.__errs.push(m); }; 1")
    clicked = capture.run_js(win, """
        var n = 0;
        document.querySelectorAll('.ct, #palettes .mitem, [data-pose], .rp-foot .btn, #btnAbout')
            .forEach(function (el) { el.click(); n += 1; });
        n;
    """)
    assert clicked > 15
    capture.wait(400)
    assert json.loads(capture.run_js(win, "JSON.stringify(window.__errs)")) == []

    capture.run_js(win, "unpose(); setPalette('gold-dark'); 1")
    capture.wait(capture.PALETTE_MS)
