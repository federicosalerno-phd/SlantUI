"""The Python shell, without opening a window.

The text level checks at the top always run. The rest import Qt, which is
the ``shell`` extra; without it they skip. None of them creates a
QApplication, so they run headless and in any order. The one test that opens
the real window is in test_window.py and is switched on by hand.
"""
from __future__ import annotations

import ctypes
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "slantui" / "shell"
TITLEBAR_JS = (ROOT / "slantui" / "js" / "titlebar.js").read_text(encoding="utf-8")
BRIDGE_PY = (SHELL / "bridge.py").read_text(encoding="utf-8")
WINDOW_PY = (SHELL / "window.py").read_text(encoding="utf-8")

# The six slots and the one signal the page's title bar uses.
WINDOW_SLOTS = ("winDrag", "winResize", "winMinimize", "winMaximizeToggle", "winClose",
                "winIsMaximized")
WINDOW_SIGNAL = "windowMaximized"


# ── text level ──────────────────────────────────────────────────────────────
def test_the_qml_shell_is_next_to_the_window():
    assert (SHELL / "shell.qml").is_file()


def test_the_qml_shell_is_packaged():
    toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"shell/*.qml"' in toml


def test_every_slot_the_page_calls_is_on_the_bridge():
    """titlebar.js is the only caller; whatever it asks for has to exist."""
    called = set(re.findall(r"'(win[A-Z][A-Za-z]+)'", TITLEBAR_JS))
    assert called == set(WINDOW_SLOTS)
    for slot in WINDOW_SLOTS:
        assert re.search(rf"@pyqtSlot\([^)]*\)\s*\n\s*def {slot}\(", BRIDGE_PY), slot


def test_the_signal_the_page_subscribes_to_is_on_the_bridge():
    assert f"Bridge.on('{WINDOW_SIGNAL}'" in TITLEBAR_JS
    assert re.search(rf"^\s+{WINDOW_SIGNAL} = pyqtSignal\(bool\)", BRIDGE_PY, re.M)


def test_the_channel_name_matches_the_script():
    bridge_js = (ROOT / "slantui" / "js" / "bridge.js").read_text(encoding="utf-8")
    assert "objectName: 'backend'" in bridge_js
    assert 'object_name: str = "backend"' in WINDOW_PY


def test_the_window_never_calls_the_base_native_event():
    """In PyQt6 that call aborts the process. The docstring says so; the
    code has to agree."""
    body = WINDOW_PY[WINDOW_PY.index("def nativeEvent"):]
    body = body[:body.index("def closeEvent")]
    code = re.sub(r'""".*?"""', "", body, flags=re.S)
    assert "super().nativeEvent" not in code


def test_the_qml_takes_its_page_and_background_from_the_window():
    qml = (SHELL / "shell.qml").read_text(encoding="utf-8")
    assert "url: uiUrl" in qml
    assert "backgroundColor: uiBackground" in qml
    assert 'objectName: "channel"' in qml
    assert "signal jsResult(int token, var value)" in qml
    assert 'setContextProperty("uiUrl"' in WINDOW_PY
    assert 'setContextProperty("uiBackground"' in WINDOW_PY


# ── win32 constants, no window needed ───────────────────────────────────────
def test_the_frame_styles_are_the_five_windows_wants():
    from slantui.shell import win32

    assert win32.WS_FRAME == 0x00C00000 | 0x00040000 | 0x00020000 | 0x00010000 | 0x00080000
    assert win32.SWP_FRAMECHANGED == 0x0037
    assert win32.DWMWA_COLOR_NONE == -2
    assert win32.WM_NCCALCSIZE == 0x83 and win32.WM_NCACTIVATE == 0x86


@pytest.mark.skipif(sys.platform != "win32", reason="a Win32 MSG")
def test_nccalcsize_is_answered_only_when_it_asks_for_a_rectangle():
    from ctypes import wintypes

    from slantui.shell import win32

    msg = wintypes.MSG()
    msg.message = win32.WM_NCCALCSIZE
    msg.wParam = 1
    assert win32.answer(ctypes.addressof(msg)) == (True, 0)
    msg.wParam = 0
    assert win32.answer(ctypes.addressof(msg)) is None
    msg.message = 0x0005          # WM_SIZE, none of our business
    msg.wParam = 1
    assert win32.answer(ctypes.addressof(msg)) is None


@pytest.mark.skipif(sys.platform != "win32", reason="a Win32 MSG")
def test_syscommand_reads_the_command_and_masks_the_low_bits():
    from ctypes import wintypes

    from slantui.shell import win32

    msg = wintypes.MSG()
    msg.message = win32.WM_SYSCOMMAND
    msg.wParam = win32.SC_MAXIMIZE | 0x0002        # the system uses the low four bits
    assert win32.syscommand(ctypes.addressof(msg)) == win32.SC_MAXIMIZE
    msg.wParam = win32.SC_MINIMIZE
    assert win32.syscommand(ctypes.addressof(msg)) == win32.SC_MINIMIZE
    msg.message = 0x0005                           # WM_SIZE: not a system command, not ours
    assert win32.syscommand(ctypes.addressof(msg)) is None
    assert win32.answer(ctypes.addressof(msg)) is None
    msg.message = win32.WM_NCCALCSIZE
    assert win32.syscommand(ctypes.addressof(msg)) is None
    assert win32.answer(ctypes.addressof(msg)) == (True, 0)


def test_the_window_never_zooms_the_hwnd():
    """Maximised is a state of the class: see the note in win32.py on what
    Windows does to a zoomed window that carries the frame styles."""
    code = re.sub(r'""".*?"""', "", WINDOW_PY, flags=re.S)
    assert "QQuickView.showMaximized" not in code
    assert "QQuickView.showNormal" in code           # the undo of a zoom Windows did
    assert "SC_MAXIMIZE" in code and "SC_MINIMIZE" in code and "SC_RESTORE" in code


@pytest.mark.skipif(sys.platform != "win32", reason="a Win32 MSG")
def test_ncactivate_goes_to_defwindowproc_with_no_repaint():
    """With no window behind the handle DefWindowProc answers 0, and the
    point is that the call is made and its answer returned, not swallowed."""
    from ctypes import wintypes

    from slantui.shell import win32

    msg = wintypes.MSG()
    msg.hWnd = None
    msg.message = win32.WM_NCACTIVATE
    msg.wParam = 1
    assert win32.answer(ctypes.addressof(msg)) == (True, 0)


def test_the_win32_helpers_do_nothing_off_windows(monkeypatch):
    from slantui.shell import win32

    monkeypatch.setattr(win32, "IS_WINDOWS", False)
    win32.dress(0)
    win32.set_transitions(0, False)
    assert win32.answer(0) is None
    assert win32.syscommand(0) is None


# ── the environment ─────────────────────────────────────────────────────────
def test_chromium_flags():
    from slantui.shell.application import chromium_flags

    assert chromium_flags(True, qt6=True) == ""
    assert chromium_flags(False, qt6=True) == "--disable-gpu"
    assert chromium_flags(False, qt6=False) == "--disable-gpu"
    assert chromium_flags(True, qt6=False) == "--disable-gpu-vsync --disable-frame-rate-limit"


def test_configure_environment_honours_the_software_switch(monkeypatch):
    from slantui.shell.application import SOFTWARE_RENDER_VAR, configure_environment

    monkeypatch.delenv(SOFTWARE_RENDER_VAR, raising=False)
    monkeypatch.delenv("QSG_RHI_PREFER_SOFTWARE_RENDERER", raising=False)
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "stale")
    configure_environment(True)
    import os
    assert "disable-gpu" not in os.environ["QTWEBENGINE_CHROMIUM_FLAGS"]
    assert "QSG_RHI_PREFER_SOFTWARE_RENDERER" not in os.environ

    monkeypatch.setenv(SOFTWARE_RENDER_VAR, "1")
    configure_environment(True)
    assert os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] == "--disable-gpu"
    assert os.environ["QSG_RHI_PREFER_SOFTWARE_RENDERER"] == "1"


def test_an_empty_app_id_is_left_alone():
    from slantui.shell.application import set_app_user_model_id

    set_app_user_model_id("")      # must not raise, must not call into shell32


# ── the bridge against a stand in for the window ────────────────────────────
qt = pytest.importorskip("slantui.shell.qt")


class FakeWindow:
    """What Bridge asks of a window, recording every call."""

    def __init__(self):
        self.calls: list = []
        self.maximized = False
        self.handle = self

    def isMaximized(self):
        return self.maximized

    def showMaximized(self):
        self.calls.append("showMaximized")

    def showNormal(self):
        self.calls.append("showNormal")

    def showMinimized(self):
        self.calls.append("showMinimized")

    def close(self):
        self.calls.append("close")

    def windowHandle(self):
        return self.handle

    def startSystemMove(self):
        self.calls.append("startSystemMove")

    def startSystemResize(self, edges):
        self.calls.append(("startSystemResize", edges))


@pytest.fixture
def bridge():
    from slantui.shell import Bridge

    b = Bridge()
    b.window = FakeWindow()
    return b


def test_the_bridge_is_a_qobject_with_the_signal():
    from slantui.shell import Bridge

    b = Bridge()
    assert isinstance(b, qt.QObject)
    got = []
    b.windowMaximized.connect(got.append)
    b.windowMaximized.emit(True)
    assert got == [True]


def test_the_slots_reach_the_window(bridge):
    w = bridge.window
    bridge.winMinimize()
    bridge.winClose()
    bridge.winDrag()
    assert w.calls == ["showMinimized", "close", "startSystemMove"]


def test_maximize_toggles_on_the_window_state(bridge):
    w = bridge.window
    assert bridge.winIsMaximized() is False
    bridge.winMaximizeToggle()
    assert w.calls == ["showMaximized"]
    w.maximized = True
    assert bridge.winIsMaximized() is True
    bridge.winMaximizeToggle()
    assert w.calls == ["showMaximized", "showNormal"]


@pytest.mark.parametrize("edge, want", [
    ("n", ["TopEdge"]), ("s", ["BottomEdge"]), ("e", ["RightEdge"]), ("w", ["LeftEdge"]),
    ("ne", ["TopEdge", "RightEdge"]), ("nw", ["TopEdge", "LeftEdge"]),
    ("se", ["BottomEdge", "RightEdge"]), ("sw", ["BottomEdge", "LeftEdge"]),
])
def test_resize_maps_the_compass_onto_qt_edges(bridge, edge, want):
    Edge = qt.Qt.Edge
    expected = Edge(0)
    for name in want:
        expected |= getattr(Edge, name)
    bridge.winResize(edge)
    assert bridge.window.calls == [("startSystemResize", expected)]


def test_a_bridge_with_no_window_does_nothing():
    from slantui.shell import Bridge

    b = Bridge()
    b.winMinimize()
    b.winMaximizeToggle()
    b.winClose()
    b.winDrag()
    b.winResize("se")
    assert b.winIsMaximized() is False
    b.shutdown()


def test_a_window_with_no_handle_is_not_dragged(bridge):
    bridge.window.handle = None
    bridge.winDrag()
    bridge.winResize("n")
    assert bridge.window.calls == []


def test_a_subclass_keeps_the_chrome_and_adds_its_own():
    from slantui.shell import Bridge, pyqtSignal, pyqtSlot

    class Backend(Bridge):
        hello = pyqtSignal(str)

        @pyqtSlot(str, result=str)
        def greet(self, name):
            return "hello " + name

    b = Backend()
    b.window = FakeWindow()
    assert b.greet("you") == "hello you"
    b.winMinimize()
    assert b.window.calls == ["showMinimized"]
    for slot in WINDOW_SLOTS:
        assert callable(getattr(b, slot))
