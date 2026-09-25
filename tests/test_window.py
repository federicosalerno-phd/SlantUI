"""The real window, on screen, for a few seconds.

Switched off unless ``SLANTUI_SHOW_WINDOW=1`` is in the environment: it
needs a display, PyQt6 with QtWebEngine, and on Windows the DWM, which only
dresses windows that are on screen. Run it by hand after touching the shell:

    set SLANTUI_SHOW_WINDOW=1
    .venv\\Scripts\\python -m pytest tests/test_window.py -q -s

It builds a page from SlantUI's own stylesheets and scripts with nothing but
a title bar in it, opens it in :class:`Window`, and checks the whole chain:
the QML loads, the channel carries the bridge, titlebar.js writes the credit
line, the HWND carries the frame styles while the client area stays the
whole window, maximise stops at the taskbar, restore comes back to the same
size, minimise reaches the taskbar, and the page hears about each state.
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SLANTUI_SHOW_WINDOW", "") != "1",
    reason="opens a real window; set SLANTUI_SHOW_WINDOW=1 to run it")

ROOT = Path(__file__).resolve().parent.parent

PAGE = """<!doctype html>
<html data-palette="gold-dark">
<head>
<meta charset="utf-8">
<title>SlantUI window test</title>
%s
</head>
<body>
<div class="app">
  <div class="titlebar">
    <div class="tbar-band"></div>
    <div class="tbar-brand"><span class="tbar-name">Window test</span></div>
    <div class="tbar-drag"></div>
    <div class="tbar-btns">
      <button class="wbtn wbtn-min" title="Minimise"></button>
      <button class="wbtn wbtn-max" title="Maximise"></button>
      <button class="wbtn wbtn-close" title="Close"></button>
    </div>
  </div>
  <div class="work"><div class="main"></div></div>
</div>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
%s
<script>
  window.__events = [];
  Bridge.on('windowMaximized', function (m) { window.__events.push(m); });
  Bridge.init();
  initTitlebar();
</script>
</body>
</html>
"""


def _page(tmp_path: Path) -> Path:
    from slantui.css import STYLESHEETS
    from slantui.css import path as css_path
    from slantui.js import SCRIPTS
    from slantui.js import path as js_path

    links = "\n".join(f'<link rel="stylesheet" href="{css_path(n).as_uri()}">' for n in STYLESHEETS)
    scripts = "\n".join(f'<script src="{js_path(n).as_uri()}"></script>' for n in SCRIPTS)
    out = tmp_path / "index.html"
    out.write_text(PAGE % (links, scripts), encoding="utf-8")
    return out


@pytest.fixture(scope="session")
def shell():
    """Session scope, because the application fixture below is, and a wider
    fixture cannot ask for a narrower one."""
    return pytest.importorskip("slantui.shell")


@pytest.fixture(scope="session")
def app(shell):
    """The application, for the whole run.

    Session scope, not module scope, and this matters. The QApplication lives
    exactly as long as something holds a reference to it, so a module scoped
    fixture hands it to the garbage collector the moment its module ends, and
    the next module that builds a window builds it with no application under
    it, which aborts the process. The other window opening module is
    tests/test_example.py, which takes the same one.
    """
    from slantui.shell.qt import QApplication

    existing = QApplication.instance()
    if existing is not None:
        return existing
    return shell.Application("SlantUI window test", app_id="SlantUI.WindowTest")


@pytest.fixture(scope="module")
def win(shell, app, tmp_path_factory):
    from slantui.shell.qt import QTimer

    page = _page(tmp_path_factory.mktemp("page"))
    w = shell.Window(page, title="SlantUI window test", size=(1100, 700), min_size=(600, 400))
    w.setPosition(80, 60)
    w.show()
    wait(app, 1800)                    # Chromium up, the page parsed, the DWM done
    yield w
    QTimer.singleShot(0, w.close)
    wait(app, 200)
    # destroyed while there is still an application, and not whenever the
    # garbage collector gets to it: a window that outlives the application
    # takes the process down on the way out
    w.deleteLater()
    wait(app, 100)


def wait(app, ms: int) -> None:
    from slantui.shell.qt import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def js(app, win, expr: str, timeout_ms: int = 3000):
    """Evaluate ``expr`` in the page and hand back its value."""
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


# ── Win32 readings, through a private handle so no argument types leak ──────
_USER32 = None


def _user32():
    global _USER32
    if _USER32 is None:
        _USER32 = ctypes.WinDLL("user32")
    return _USER32


def _rects(hwnd: int):
    from ctypes import wintypes

    wr, cr = wintypes.RECT(), wintypes.RECT()
    _user32().GetWindowRect(hwnd, ctypes.byref(wr))
    _user32().GetClientRect(hwnd, ctypes.byref(cr))
    return ((wr.left, wr.top, wr.right - wr.left, wr.bottom - wr.top),
            (cr.right - cr.left, cr.bottom - cr.top))


def _work_area(hwnd: int):
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    u = _user32()
    u.MonitorFromWindow.restype = ctypes.c_void_p
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    u.GetMonitorInfoW(ctypes.c_void_p(u.MonitorFromWindow(hwnd, 2)), ctypes.byref(mi))
    r = mi.rcWork
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def _zoomed(hwnd: int) -> bool:
    return bool(_user32().IsZoomed(hwnd))


def _style(hwnd: int) -> int:
    from ctypes import wintypes

    get_long = getattr(_user32(), "GetWindowLongPtrW", _user32().GetWindowLongW)
    get_long.restype = ctypes.c_ssize_t
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    return get_long(hwnd, -16)


def _qt_px(win):
    """Qt's size in device pixels: it reports logical (DPI scaled) units."""
    s = win.devicePixelRatio()
    return (round(win.width() * s), round(win.height() * s))


# ── the chain from Python to the page ───────────────────────────────────────
def test_the_page_is_up_and_the_bridge_is_on_the_channel(app, win):
    assert js(app, win, "document.title") == "SlantUI window test"
    assert js(app, win, "Bridge.ready") is True
    assert js(app, win, "typeof Bridge.obj.winIsMaximized") == "function"


def test_the_title_bar_wrote_the_credit_line(app, win):
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Layout by Federico Salerno" in lic
    assert js(app, win, "document.querySelector('.tbar-credit').textContent") == \
        "Layout by Federico Salerno"
    assert js(app, win, "document.querySelector('.tbar-band').style.clipPath").startswith("path(")


def test_the_page_asked_for_the_state_and_got_the_answer(app, win):
    assert js(app, win, "document.querySelector('.wbtn-max').title") == "Maximise"
    assert js(app, win, "document.body.classList.contains('maximized')") is False


def test_the_background_is_the_palette_surface(win):
    from slantui.tokens import DEFAULT

    assert win.background == DEFAULT["surface-0"]
    assert win.color().name().upper() == DEFAULT["surface-0"].upper()


def test_the_page_can_raise_the_minimum_width(app, win):
    """A step rail that keeps every label whole has the page measure
    what the row needs and the window refuses to go narrower. It has to
    survive a maximise: the minimum drops to nothing for the animation and
    is put back from the same field this writes."""
    was = win.minimumWidth()
    try:
        applied = win.set_min_width(1140)
        assert applied == 1140
        assert win.minimumWidth() == 1140
        win.showMaximized()
        wait(app, 900)
        win.showNormal()
        wait(app, 900)
        assert win.minimumWidth() == 1140, "a zoom lost the width the page set"
    finally:
        win.set_min_width(was)


def test_a_minimum_wider_than_the_screen_is_capped(win):
    """A window nobody can drag is worse than a cut label."""
    was = win.minimumWidth()
    try:
        applied = win.set_min_width(99_000)
        assert applied == win.screen().availableGeometry().width()
    finally:
        win.set_min_width(was)


# ── the native frame ────────────────────────────────────────────────────────
win_only = pytest.mark.skipif(sys.platform != "win32", reason="the Win32 frame")


@win_only
def test_the_hwnd_carries_the_frame_and_the_client_is_the_whole_window(win):
    from slantui.shell import win32

    hwnd = int(win.winId())
    style = _style(hwnd)
    wr, cr = _rects(hwnd)
    assert (style & win32.WS_FRAME) == win32.WS_FRAME, hex(style)
    assert cr == (wr[2], wr[3]), (wr, cr)
    assert _qt_px(win) == cr


@win_only
def test_maximise_stops_at_the_taskbar_and_the_page_hears_it(app, win):
    hwnd = int(win.winId())
    normal = _rects(hwnd)[0]
    win.showMaximized()
    wait(app, 900)                     # the animation, then the state change
    wr, cr = _rects(hwnd)
    assert win.isMaximized()
    assert not _zoomed(hwnd)           # never: a zoomed window overshoots the screen
    assert wr == _work_area(hwnd), (wr, _work_area(hwnd))
    assert cr == (wr[2], wr[3])
    assert _qt_px(win) == cr
    assert js(app, win, "document.body.classList.contains('maximized')") is True
    assert js(app, win, "document.querySelector('.wbtn-max').title") == "Restore"

    win.showNormal()
    wait(app, 900)
    wr, cr = _rects(hwnd)
    assert not win.isMaximized()
    assert wr == normal, (wr, normal)
    assert cr == (wr[2], wr[3])
    assert js(app, win, "document.body.classList.contains('maximized')") is False
    assert js(app, win, "window.__events.slice(-2)") == [True, False]


@win_only
def test_win_up_and_win_down_are_taken_over(app, win):
    """Win+Up, Win+Down and the taskbar menu arrive as WM_SYSCOMMAND. The
    window does them itself, so the HWND is never zoomed."""
    from slantui.shell import win32

    hwnd = int(win.winId())
    normal = _rects(hwnd)[0]
    _user32().PostMessageW(hwnd, win32.WM_SYSCOMMAND, win32.SC_MAXIMIZE, 0)
    wait(app, 900)
    assert win.isMaximized() and not _zoomed(hwnd)
    assert _rects(hwnd)[0] == _work_area(hwnd)
    assert js(app, win, "document.body.classList.contains('maximized')") is True

    _user32().PostMessageW(hwnd, win32.WM_SYSCOMMAND, win32.SC_RESTORE, 0)
    wait(app, 900)
    assert not win.isMaximized()
    assert _rects(hwnd)[0] == normal

    _user32().PostMessageW(hwnd, win32.WM_SYSCOMMAND, win32.SC_MINIMIZE, 0)
    wait(app, 900)
    assert win.isMinimized() and bool(_user32().IsIconic(hwnd))
    win.showNormal()
    wait(app, 900)
    assert not win.isMinimized()
    assert _rects(hwnd)[0] == normal


@win_only
def test_a_zoom_windows_did_by_itself_is_absorbed(app, win):
    """A drag to the top edge zooms the window without a system command.
    Qt reports the state, the zoom is undone and the window put on the work
    area, still maximised as far as the page knows."""
    hwnd = int(win.winId())
    normal = _rects(hwnd)[0]
    _user32().ShowWindow(hwnd, 3)      # SW_MAXIMIZE, straight to Windows
    wait(app, 900)
    wr, cr = _rects(hwnd)
    assert win.isMaximized() and not _zoomed(hwnd)
    assert wr == _work_area(hwnd), (wr, _work_area(hwnd))
    assert cr == (wr[2], wr[3])
    assert _qt_px(win) == cr
    assert js(app, win, "document.body.classList.contains('maximized')") is True

    win.showNormal()
    wait(app, 900)
    assert not win.isMaximized()
    assert _rects(hwnd)[0] == normal, (_rects(hwnd)[0], normal)


@win_only
def test_minimised_from_maximised_comes_back_maximised(app, win):
    hwnd = int(win.winId())
    normal = _rects(hwnd)[0]
    win.showMaximized()
    wait(app, 900)
    win.showMinimized()
    wait(app, 900)
    assert bool(_user32().IsIconic(hwnd))
    assert win.isMaximized()           # the page keeps its maximised look meanwhile
    win.showNormal()
    wait(app, 1200)
    assert win.isMaximized() and not _zoomed(hwnd)
    assert _rects(hwnd)[0] == _work_area(hwnd)
    win.showNormal()
    wait(app, 900)
    assert not win.isMaximized()
    assert _rects(hwnd)[0] == normal


def test_a_drag_from_maximised_restores_under_the_cursor(app, win):
    """The point is passed in: the real cursor belongs to whoever is at the
    machine while this runs."""
    from PyQt6.QtCore import QPoint

    win.showMaximized()
    wait(app, 900)
    before = win.geometry()
    normal = win._normal_rect
    hand = QPoint(before.left() + before.width() // 4, before.top() + 10)
    win._restore_under_cursor(hand)
    wait(app, 300)
    geo = win.geometry()
    assert not win.isMaximized()
    assert (geo.width(), geo.height()) == (normal.width(), normal.height())
    assert geo.top() == before.top()
    # the hand was a quarter of the way along the band; it still is
    assert abs((hand.x() - geo.left()) - normal.width() // 4) <= 1
    assert js(app, win, "document.body.classList.contains('maximized')") is False


@win_only
def test_minimise_reaches_the_taskbar_and_comes_back(app, win):
    hwnd = int(win.winId())
    normal = _rects(hwnd)[0]
    win.showMinimized()
    wait(app, 900)
    assert bool(_user32().IsIconic(hwnd))
    assert win.isMinimized()

    win.showNormal()
    wait(app, 900)
    wr, cr = _rects(hwnd)
    assert not _user32().IsIconic(hwnd)
    assert wr[2:] == normal[2:], (wr, normal)
    assert cr == (wr[2], wr[3])
    assert win.minimumSize().width() == 600


@win_only
def test_the_frame_styles_survive_the_state_changes(win):
    from slantui.shell import win32

    style = _style(int(win.winId()))
    assert (style & win32.WS_FRAME) == win32.WS_FRAME, hex(style)


# ── the chrome slots, called the way the page calls them ────────────────────
def test_the_bridge_slots_drive_the_window_from_the_page(app, win):
    if win.isMaximized():                  # whatever an earlier test left
        win.showNormal()
        wait(app, 900)
    js(app, win, "be('winMaximizeToggle'); 1")
    wait(app, 900)
    assert win.isMaximized()
    assert js(app, win, "document.body.classList.contains('maximized')") is True
    js(app, win, "be('winMaximizeToggle'); 1")
    wait(app, 900)
    assert not win.isMaximized()
    box: list = []
    js(app, win, "be('winIsMaximized', undefined, function (m) { window.__last = m; }); 1")
    wait(app, 200)
    box.append(js(app, win, "window.__last"))
    assert box == [False]


def test_shutdown_is_called_once_on_close(app, shell, tmp_path):
    calls: list = []

    class B(shell.Bridge):
        def shutdown(self):
            calls.append(1)

    w = shell.Window(_page(tmp_path), bridge=B(), title="close test", size=(700, 500),
                     min_size=(300, 200))
    w.setPosition(200, 200)
    w.show()
    wait(app, 600)
    w.close()
    wait(app, 300)
    assert calls == [1]
