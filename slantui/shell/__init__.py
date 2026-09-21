"""The Python side: the frameless window, its native Windows frame, and the
bridge the page talks to.

    from slantui.shell import Application, Bridge, Window

    class Backend(Bridge):
        hello = pyqtSignal(str)

        @pyqtSlot(str, result=str)
        def greet(self, name):
            return "hello " + name

    app = Application("My App", app_id="Me.MyApp")
    win = Window("ui/index.html", bridge=Backend(), title="My App")
    win.show()
    sys.exit(app.run())

The page loads SlantUI's stylesheets and scripts, puts a `.titlebar` in its
markup, and calls `Bridge.init()` and `initTitlebar()`. Everything the window
chrome needs is then wired: the six slots on :class:`Bridge` answer the
page's title bar, and :class:`Window` tells the page when Windows maximised
or restored it.

Importing this package needs PyQt6 with QtWebEngine (or PyQt5 with
PyQtWebEngine): ``pip install "slantui[shell]"``. The rest of SlantUI does
not, so ``slantui.tokens`` stays importable anywhere.

Qt names are imported from ``slantui.shell.qt``, which is where the PyQt6
first, PyQt5 fallback lives. An application that takes its own Qt names from
there gets the same fallback.
"""
from __future__ import annotations

from .application import Application, chromium_flags, configure_environment, set_app_user_model_id
from .bridge import Bridge, edges_of
from .qt import USE_QT6, pyqtSignal, pyqtSlot
from .splash import SPLASH_QML, Splash
from .window import SHELL_QML, STATE_ANIM_MS, Window

__all__ = [
    "Application", "Bridge", "Window", "Splash",
    "pyqtSignal", "pyqtSlot", "USE_QT6",
    "chromium_flags", "configure_environment", "set_app_user_model_id", "edges_of",
    "SHELL_QML", "STATE_ANIM_MS",
]
