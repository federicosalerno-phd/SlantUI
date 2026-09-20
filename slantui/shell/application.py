"""The application object, with the process set up in the order Qt wants.

Three things have to happen before ``QApplication`` exists and one before the
first window: the Chromium flags and the renderer go into the environment,
the high DPI policy is chosen, ``QtWebEngineQuick.initialize()`` is called,
and the process gets its taskbar identity. :class:`Application` does them in
its constructor, so an application is:

    app = Application("My App", app_id="Me.MyApp")
    win = Window("ui/index.html", bridge=MyBridge(), title="My App")
    win.show()
    sys.exit(app.run())
"""
from __future__ import annotations

import os
import sys

from .qt import QApplication, Qt, QtWebEngineQuick, USE_QT6, run_app

__all__ = ["Application", "chromium_flags", "configure_environment", "set_app_user_model_id",
           "software_forced", "SOFTWARE_RENDER_VAR"]

# Set to 1 by a user whose machine has a broken graphics driver: every SlantUI
# application then draws through software, whatever the application asked.
SOFTWARE_RENDER_VAR = "SLANTUI_SOFTWARE_RENDER"


def software_forced() -> bool:
    return os.environ.get(SOFTWARE_RENDER_VAR, "") in ("1", "true", "True")


def chromium_flags(gpu: bool = True, qt6: bool = USE_QT6, extra: str = "") -> str:
    """Flags for the embedded Chromium.

    Chromium's own defaults are kept on purpose. Its GPU blocklist stays in
    force, so a machine whose driver Chromium knows to be broken falls back to
    software compositing and still shows the application, and rasterisation
    is left to Chromium. ``extra`` is whatever the application wants on top,
    and it comes last, so a flag passed in wins over one set here.
    """
    if not gpu:
        out = "--disable-gpu"
    elif not qt6:
        # The Qt5/Chromium-83 compositor starves its vsync source; drive frames
        # from a timer there. Qt6's compositor does not want this.
        out = "--disable-gpu-vsync --disable-frame-rate-limit"
    else:
        out = ""
    return (out + " " + extra).strip() if extra else out


def configure_environment(gpu: bool = True, extra: str = "") -> None:
    """Must run before ``QApplication`` is created.

    The window follows the display's scale (a 150 % display gets a 150 % UI
    and the page sees devicePixelRatio 1.5), so a page that sizes canvas
    backing stores from that ratio is never blurry on a scaled display.

    The scene graph keeps vsync: without it, Windows 11 hands the window's
    flip model swap chain straight to the screen and a pan tears into a
    horizontal wave. With the Quick shell a vsynced resize is one frame per
    step anyway.
    """
    if software_forced():
        gpu = False
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = chromium_flags(gpu, extra=extra)
    if not gpu:
        # Qt's side on the software (WARP) device; Chromium's side is software
        # through the flag above. For machines with a broken driver.
        os.environ.setdefault("QSG_RHI_PREFER_SOFTWARE_RENDERER", "1")


def set_app_user_model_id(app_id: str) -> None:
    """Give the process its own taskbar identity (Windows only).

    Without it the taskbar files the window under pythonw.exe: the button
    gets Python's icon once the window is gone, and "Pin to taskbar" pins a
    bare interpreter that opens nothing. An installer writes the same id on
    the Start Menu shortcut, so a pinned application starts the application.
    Must run before the first window is created.
    """
    if not app_id or sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


class Application(QApplication):
    """``QApplication`` with the process set up first.

    ``name`` is the application name Qt reports. ``app_id`` is the taskbar
    identity, in the form ``Company.Product``; leave it empty and the
    process is filed under the interpreter. ``gpu=False`` draws through
    software, and so does ``SLANTUI_SOFTWARE_RENDER=1`` in the environment
    whatever is passed. ``chromium`` is one flag more for the embedded
    browser, or several: a tool that saves pictures of a window asks for
    ``--disable-lcd-text`` with it, so the glyphs in them carry no colour of
    their own. ``style`` is the widget style, which only the file dialogs
    show; Fusion looks the same everywhere.
    """

    def __init__(self, name: str, *, app_id: str = "", gpu: bool = True,
                 chromium: str = "", argv: list[str] | None = None,
                 style: str | None = "Fusion"):
        set_app_user_model_id(app_id)
        configure_environment(gpu, extra=chromium)
        if USE_QT6:
            try:
                QApplication.setHighDpiScaleFactorRoundingPolicy(
                    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
            except Exception:
                pass
        else:
            QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, False)
        QtWebEngineQuick.initialize()     # before the application object, as Qt requires
        super().__init__(list(sys.argv if argv is None else argv))
        self.setApplicationName(name)
        if style:
            self.setStyle(style)

    def run(self) -> int:
        """Run the event loop until the last window closes."""
        return run_app(self)
