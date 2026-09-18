"""The example application in examples/tour.

The example is the answer to one question: can an application be built on
SlantUI alone. These checks hold it to that answer.

The text level checks always run. They read the page, the stylesheet and the
script as files: every class the markup uses has to be defined by the
library or by the page's own three rules, every widget the library defines
has to appear in the page, and every slot the page calls has to exist on the
backend. The last one is the same check ``test_shell.py`` makes for the
window chrome, applied to the application's own slots.

The checks that need Qt import the backend. The one that opens the real
window is switched on by hand, as ``test_window.py`` is:

    set SLANTUI_SHOW_WINDOW=1
    .venv\\Scripts\\python -m pytest tests/test_example.py -q
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from slantui.css import STYLESHEETS
from slantui.css import path as css_path

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "tour"

# What a page of the example may import: the standard library, the package
# under test, and the file sitting next to it.
ALLOWED_IMPORTS = {"__future__", "sys", "os", "re", "json", "math", "random",
                   "time", "pathlib", "dataclasses", "typing",
                   "slantui", "backend"}
UI = EX / "ui"

PAGE = (UI / "index.html").read_text(encoding="utf-8")
APP_CSS = (UI / "app.css").read_text(encoding="utf-8")
APP_JS = (UI / "app.js").read_text(encoding="utf-8")

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_CLASS_IN_CSS = re.compile(r"\.([a-zA-Z][\w-]*)")
_CLASS_ATTR = re.compile(r'class="([^"]+)"')

# Classes no markup carries, because a script puts them on and takes them off.
# Everything else the library defines has to be somewhere in the page.
SCRIPT_ONLY = {
    "combopop", "combo-opt", "combo-on", "open",   # the dropdown's popup
    "dzover",                                      # a file is over the card
    "maximized",                                   # the window state, on body
    "tbar-credit",                                 # titlebar.js writes it
    "busy", "ok", "warn", "err", "on", "done",     # states of a pill, a tab, a toggle
}


def _css(name: str) -> str:
    return _COMMENT.sub(" ", css_path(name).read_text(encoding="utf-8"))


def _library_classes() -> set[str]:
    out: set[str] = set()
    for name in STYLESHEETS:
        out |= set(_CLASS_IN_CSS.findall(_css(name)))
    return out


def _script_hooks() -> set[str]:
    """Classes the library's own scripts look for. Two of them, .wbtn-min and
    .wbtn-max, carry no rule at all: the fill and the size come from .wbtn and
    the name is there for titlebar.js to find the button by."""
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


# ── the example is there and is wired to the library ────────────────────────
def test_the_example_is_all_there():
    for name in ("main.py", "backend.py", "ui/index.html", "ui/app.css", "ui/app.js"):
        assert (EX / name).is_file(), name


def test_the_page_loads_the_channel_before_the_library():
    """qwebchannel.js comes out of Qt's own resources and bridge.js needs it."""
    channel = PAGE.index("qrc:///qtwebchannel/qwebchannel.js")
    library = PAGE.index('src="slantui.js"')
    page = PAGE.index('src="app.js"')
    assert channel < library < page


def test_the_page_links_what_main_writes():
    main = (EX / "main.py").read_text(encoding="utf-8")
    for name in ("slantui.css", "slantui.js"):
        assert f'"{name}"' in main, f"main.py does not write {name}"
        assert f'"{name}"' in PAGE, f"index.html does not link {name}"


def test_the_example_reaches_outside_its_own_folder_for_nothing():
    """The whole point of the example. A path climbing out of the folder, or
    an import of anything but the library and the standard library, would end
    the claim that the library stands alone."""
    for path in sorted(EX.rglob("*")):
        if not path.is_file() or path.suffix not in (".py", ".js", ".css", ".html", ".md"):
            continue
        if path.name in ("slantui.css", "slantui.js"):
            continue        # written by main.py from the library, on every start
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "../" not in text and "..\\" not in text, path
        if path.suffix != ".py":
            continue
        for m in re.finditer(r"^\s*(?:import|from)\s+([\w.]+)", text, re.M):
            root = m.group(1).split(".")[0]
            assert root in ALLOWED_IMPORTS, f"{path} imports {m.group(1)}"


# ── the vocabulary ──────────────────────────────────────────────────────────
def test_every_class_the_page_uses_is_defined():
    """A typo in a class name is invisible on screen: the element simply has
    no style. The page may only name what the library or its own sheet
    defines."""
    known = (_library_classes() | _script_hooks()
             | set(_CLASS_IN_CSS.findall(_COMMENT.sub(" ", APP_CSS))))
    unknown = sorted(c for c in _page_classes() if c not in known)
    assert not unknown, f"nothing defines or looks for {unknown}"


def test_the_page_carries_one_of_every_widget():
    """The markup is the seed of the gallery, so a widget missing here is a
    widget the gallery would not show and nobody would look at again."""
    missing = sorted(c for c in _library_classes()
                     if c not in SCRIPT_ONLY and c not in _page_classes())
    assert not missing, f"the example never uses {missing}"


def test_the_page_names_no_colour():
    """The page is held to the rule the library holds itself to: a colour is
    a role, never a value. The script reads roles through Theme."""
    hits = []
    for name, text in (("app.css", APP_CSS), ("app.js", APP_JS), ("index.html", PAGE)):
        for n, line in enumerate(text.splitlines(), start=1):
            if re.search(r"#[0-9a-fA-F]{3}\b|#[0-9a-fA-F]{6}\b|\brgba?\(", line):
                hits.append(f"{name}:{n}  {line.strip()}")
    assert not hits, "\n" + "\n".join(hits)


def test_the_script_only_calls_the_library_it_loads():
    """Names the page takes off the window, and where each one comes from."""
    from slantui.js import path as js_path

    leaves = set()
    for name in ("theme.js", "bridge.js", "widgets.js", "titlebar.js"):
        src = js_path(name).read_text(encoding="utf-8")
        leaves |= set(re.findall(r"^function ([A-Za-z]\w*)", src, re.M))
        leaves |= set(re.findall(r"^const ([A-Za-z]\w*)", src, re.M))
    for name in ("Bridge", "be", "beJson", "Theme", "THEME_ROLES", "initSelects",
                 "numStep", "fitOneLine", "initTitlebar", "roundedPolyPath", "CREDIT_TEXT"):
        assert name in leaves, name
    for name in ("Theme", "roundedPolyPath", "CREDIT_TEXT", "initTitlebar",
                 "initSelects", "numStep", "fitOneLine", "beJson"):
        assert name in APP_JS, f"the example never uses {name}"


# ── the page and the backend agree ──────────────────────────────────────────
@pytest.fixture(scope="module")
def backend():
    pytest.importorskip("slantui.shell")
    sys.path.insert(0, str(EX))
    try:
        import backend as module
    finally:
        sys.path.remove(str(EX))
    return module


def _meta_names(cls) -> set[str]:
    mo = cls.staticMetaObject
    return {bytes(mo.method(i).name()).decode() for i in range(mo.methodCount())}


def test_every_slot_the_page_calls_is_on_the_backend(backend):
    called = set(re.findall(r"\bbe(?:Json)?\('([A-Za-z]\w*)'", APP_JS))
    assert called, "the example calls no slot at all"
    assert called <= _meta_names(backend.Tour), sorted(called - _meta_names(backend.Tour))


def test_every_signal_the_page_hears_is_on_the_backend(backend):
    heard = set(re.findall(r"Bridge\.on\('([A-Za-z]\w*)'", APP_JS))
    assert heard == {"progress", "jobDone"}
    assert heard <= _meta_names(backend.Tour)


def test_the_backend_stops_its_job_on_shutdown(backend):
    """The window calls shutdown() once on close. A backend that left work
    running there would keep the process alive with no window on screen."""
    b = backend.Tour()
    b.runJob(1000)
    assert b._running
    b.shutdown()
    assert not b._running


def test_a_cancel_answers_once_and_a_second_one_says_nothing(backend):
    """The page can press Cancel twice, and a slot that raised would take the
    window down with it: an exception inside a slot reaches Qt, which ends the
    process."""
    b = backend.Tour()
    ended: list[bool] = []
    b.jobDone.connect(ended.append)

    b.cancelJob()               # nothing is running
    assert ended == []
    b.runJob(1000)
    b.cancelJob()
    b.cancelJob()
    assert ended == [False]


def test_the_job_reports_from_zero_to_a_hundred(backend):
    """What the page receives over a whole run. The clock is driven by hand
    here, so the check is about the reports and not about the machine."""
    b = backend.Tour()
    seen: list[tuple[int, str]] = []
    ended: list[bool] = []
    b.progress.connect(lambda pct, stage: seen.append((pct, stage)))
    b.jobDone.connect(ended.append)

    b.runJob(600)                  # ten ticks of 60 ms
    b._timer.stop()
    while not ended:
        b._tick()

    assert ended == [True]
    assert seen[0] == (0, "Reading the file")
    assert seen[-1] == (100, "Writing the results")
    assert [p for p, _ in seen] == sorted(p for p, _ in seen)
    assert {stage for _, stage in seen} == {name for _, name in backend.STAGES}


@pytest.fixture(scope="session")
def qt_app():
    """The application, for the whole run.

    Only the window tests below ask for it, so nothing in the headless suite
    starts WebEngine. Session scope, not module scope: the QApplication lives
    as long as something holds a reference, so a module scoped fixture drops
    it when its module ends and the next module's window is built with no
    application under it, which aborts the process. tests/test_window.py has
    the same fixture and the two share whichever was made first.
    """
    shell = pytest.importorskip("slantui.shell")
    from slantui.shell.qt import QApplication

    existing = QApplication.instance()
    return existing if existing is not None else shell.Application(
        "SlantUI example test", app_id="SlantUI.ExampleTest")


# ── the real window ─────────────────────────────────────────────────────────
show_window = pytest.mark.skipif(
    os.environ.get("SLANTUI_SHOW_WINDOW", "") != "1",
    reason="opens a real window; set SLANTUI_SHOW_WINDOW=1 to run it")


@pytest.fixture(scope="module")
def win(backend, qt_app):
    """The example, opened the way main.py opens it."""
    sys.path.insert(0, str(EX))
    try:
        import main
    finally:
        sys.path.remove(str(EX))
    from slantui.shell import Window
    from slantui.shell.qt import QTimer

    main.write_library_files()
    w = Window(UI / "index.html", bridge=backend.Tour(), title="SlantUI Tour",
               size=(1240, 800), min_size=(940, 600))
    w.setPosition(60, 40)
    w.show()
    wait(2200)                      # Chromium up, the page parsed, the first draw
    yield w
    QTimer.singleShot(0, w.close)
    wait(700)


def wait(ms: int) -> None:
    from slantui.shell.qt import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def js(win, expr: str, timeout_ms: int = 3000):
    from slantui.shell.qt import QEventLoop, QTimer

    box: list = []
    loop = QEventLoop()

    def got(value):
        box.append(value)
        loop.quit()
    win.run_js(expr, got)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    assert box, f"no answer from the page for {expr!r}"
    return box[0]


@show_window
def test_the_example_comes_up(win):
    assert js(win, "document.title") == "SlantUI Tour"
    assert js(win, "Bridge.ready") is True
    assert js(win, "document.querySelector('.tbar-credit').textContent") == \
        "Layout by Federico Salerno"
    assert js(win, "document.querySelector('.tbar-band').style.clipPath").startswith("path(")


@show_window
def test_the_backend_answered_with_its_versions(win):
    from slantui import __version__

    assert js(win, "document.getElementById('piSlantui').textContent") == __version__
    assert js(win, "document.getElementById('piQt').textContent") != "reading..."


@show_window
def test_the_steps_move_the_panel_and_the_stage(win):
    js(win, "go(1); 1")
    wait(200)
    assert js(win, "document.querySelector('.rp-page.show').dataset.step") == "1"
    assert js(win, "document.getElementById('cv').classList.contains('hidden')") is False
    assert js(win, "document.getElementById('dz').classList.contains('hidden')") is True
    assert js(win, "document.getElementById('cv').width") > 0


@show_window
def test_the_palette_switch_reaches_the_window(win):
    """Theme.setPalette() moves the page, and the slot moves the colour
    behind it. The two have to end up on the same palette."""
    from slantui.tokens import PALETTES

    js(win, "setPalette('Slate Light'); 1")
    wait(300)
    assert js(win, "document.documentElement.getAttribute('data-palette')") == "slate-light"
    assert js(win, "Theme.get('surface-0')") == PALETTES["slate-light"]["surface-0"]
    assert win.background == PALETTES["slate-light"]["surface-0"]

    js(win, "setPalette('Gold Dark'); 1")
    wait(300)
    assert win.background == PALETTES["gold-dark"]["surface-0"]


@show_window
def test_the_job_runs_from_the_page_and_the_card_follows_it(win):
    js(win, "go(2); runJob(); 1")
    wait(300)
    assert js(win, "document.getElementById('job').classList.contains('show')") is True
    wait(3000)
    assert js(win, "document.getElementById('job').classList.contains('show')") is False
    assert js(win, "document.getElementById('jobPct').textContent") == "100"
    assert js(win, "document.getElementById('piEnded').textContent") == "finished"
    assert js(win, "document.querySelector('.sd').className") == "sd ok"
