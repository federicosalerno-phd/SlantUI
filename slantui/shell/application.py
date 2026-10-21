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

from . import win32
from .qt import QApplication, Qt, QtWebEngineQuick, USE_QT6, run_app

__all__ = ["Application", "BLIT_MODEL_VAR", "FONT_DATABASE_GDI", "GRAPHICS_API_VAR", "chromium_flags",
           "configure_environment", "keep_browser_data", "platform_arguments", "scene_graph_api",
           "set_app_user_model_id",
           "software_forced", "SOFTWARE_RENDER_VAR"]

# Set to 1 by a user whose machine has a broken graphics driver: every SlantUI
# application then draws through software, whatever the application asked.
SOFTWARE_RENDER_VAR = "SLANTUI_SOFTWARE_RENDER"

# Qt's switch for the blit model swap chain on Direct3D: see configure_environment.
BLIT_MODEL_VAR = "QT_D3D_NO_FLIP"

# Qt's switch for the graphics API the scene graph draws with: see scene_graph_api.
GRAPHICS_API_VAR = "QSG_RHI_BACKEND"

# The platform options on Windows: the fonts listed through GDI. See platform_arguments.
FONT_DATABASE_GDI = "windows:fontengine=gdi"


def software_forced() -> bool:
    return os.environ.get(SOFTWARE_RENDER_VAR, "") in ("1", "true", "True")


def scene_graph_api(vendor: int | None) -> str | None:
    """The graphics API the window's scene graph should draw with on an
    adapter of this PCI vendor, or ``None`` for Qt's own choice (Direct3D 11
    on Windows).

    The page reaches the window through QtWebEngine, which hands each frame
    Chromium has composed to Qt's scene graph as a texture of Chromium's own
    device. On Direct3D 11 (QtWebEngine 6.11, the Direct3D 11 output device)
    it is opened on Qt's device through a shared handle, with no keyed mutex
    and no fence, so Qt can sample it before Chromium's GPU has finished
    writing it. On an Intel UHD 630 that is what the screen showed: now and
    then, for one refresh, a frame older than the one before it (frame n,
    then n - 1, then n + 2), as many as 40 times in 2.6 seconds of a window
    at rest, in every one of ten launches, with either swap chain model
    and with Qt on the other adapter, and only where a WebGL canvas had just
    drawn. On OpenGL the same texture goes through WGL_NV_DX_interop and is
    locked before Qt reads it: in twelve launches on the same machine no older
    frame came back at rest. On an NVIDIA adapter (a Quadro T2000 driving a
    4K display at 150 %) the Direct3D 11 hand over came out clean with the
    blit model, and OpenGL is no choice there: the window being dragged moved
    on screen only every 100 ms. So Intel's adapters get OpenGL, and every
    other adapter keeps Direct3D 11. Measured from outside the process with
    the screen's own capture and a clock the page writes into every frame,
    on 2026-10-05.
    """
    return "opengl" if vendor == win32.VENDOR_INTEL else None


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

    And on Windows it presents through the blit model, not the flip model
    (``QT_D3D_NO_FLIP``). Measured from outside the process while a window
    was dragged, on a 3840 by 2160 display at 150 %: with the flip model the
    window changed place on screen every other refresh, 30 times a second,
    even with the page drawing nothing, the screen showed 60 to 65 % of the
    page's frames, a frame took 50 ms to reach it, and now and then an older
    one came back for a refresh. A plain window of the same size on the same
    display moved at 60. With the blit model the window moves at 60 too, the
    screen shows 97 to 100 % of the frames, one takes 18 to 27 ms, and none
    comes back. ``setdefault``: an application that wants the flip model
    says so in its own environment first.

    And the scene graph draws with the graphics API the adapter hands frames
    over cleanly with (``scene_graph_api``): OpenGL on Intel's adapters,
    where Direct3D 11 showed older frames for a refresh. ``setdefault`` again,
    and never on the software path, which is Direct3D's own WARP.
    """
    if software_forced():
        gpu = False
    if sys.platform == "win32":
        os.environ.setdefault(BLIT_MODEL_VAR, "1")
        api = scene_graph_api(win32.first_adapter_vendor()) if gpu else None
        if api:
            os.environ.setdefault(GRAPHICS_API_VAR, api)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = chromium_flags(gpu, extra=extra)
    if not gpu:
        # Qt's side on the software (WARP) device; Chromium's side is software
        # through the flag above. For machines with a broken driver.
        os.environ.setdefault("QSG_RHI_PREFER_SOFTWARE_RENDERER", "1")


def platform_arguments(argv: list[str]) -> list[str]:
    """``argv`` with the platform options a SlantUI window wants on Windows:
    the installed fonts listed through GDI.

    The first browser of a process makes its settings, and they ask Qt for the
    default font of each generic family (QWebEngineSettings, then
    QFont::defaultFamily). Qt's generic fallback then opens every family
    installed, and with Qt's DirectWrite font database, the default since Qt
    6.8, each font file is read into DirectWrite's cache inside the process,
    on the window's thread, with the window not yet drawn. On a machine with
    2,030 fonts (1,449 of them the user's own) the first browser held the
    thread 5 s at the median and 37 s at worst, and 27 to 40 s while another
    program held most of the memory. With the fonts listed through GDI
    (``fontengine=gdi``; DirectWrite still draws the glyphs) it was 2.5 s at
    the median and 2.8 s at worst, in alternating runs on 2026-10-21. An
    option on the command line, not the environment: programs the
    application starts do not inherit it. Nothing is added when the platform
    is chosen already, in ``QT_QPA_PLATFORM`` or with ``-platform``.
    """
    argv = list(argv)
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") or "-platform" in argv:
        return argv
    return (argv[:1] or [""]) + ["-platform", FONT_DATABASE_GDI] + argv[1:]


def keep_browser_data(folder: str | os.PathLike) -> bool:
    """The browser's profile (the one every window's page uses) kept on disk
    in ``folder``, which must be a local folder, never a synced one. Must run
    after the application object exists and before the first window.

    Qt's default profile keeps everything in memory, and with it the GPU's
    compiled shaders: every start compiled them again, on the page's thread.
    A page that shows a 3D model stood still for that: 0.2 to 1 s for a
    small model and 4.3 to 6 s for a large lit scene on an NVIDIA Quadro
    T2000 through Direct3D 11; 0.6 s for the large one with the profile on
    disk, in a start after one that had written its cache (2026-10-21; the
    browser writes it a while after compiling, so a process killed at once
    leaves it unwritten). Cookies are not kept and the HTTP cache stays in
    memory: an application's page has no use for them. Returns False where
    the profile cannot be set (PyQt5).
    """
    if not USE_QT6:
        return False
    from pathlib import Path

    from PyQt6.QtWebEngineQuick import QQuickWebEngineProfile

    root = Path(folder)
    root.mkdir(parents=True, exist_ok=True)
    p = QQuickWebEngineProfile.defaultProfile()
    p.setStorageName("SlantUI")
    p.setOffTheRecord(False)
    p.setPersistentStoragePath(str(root / "storage"))
    p.setCachePath(str(root / "cache"))
    p.setDownloadPath(str(root / "downloads"))
    p.setHttpCacheType(QQuickWebEngineProfile.HttpCacheType.MemoryHttpCache)
    p.setPersistentCookiesPolicy(QQuickWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    return not p.isOffTheRecord()


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
    show; Fusion looks the same everywhere. ``storage`` is a local folder
    the browser keeps its data in (keep_browser_data); without it the
    browser keeps nothing on disk.
    """

    def __init__(self, name: str, *, app_id: str = "", gpu: bool = True,
                 chromium: str = "", argv: list[str] | None = None,
                 style: str | None = "Fusion", storage: str | os.PathLike | None = None):
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
        super().__init__(platform_arguments(sys.argv if argv is None else argv))
        self.setApplicationName(name)
        if style:
            self.setStyle(style)
        if storage is not None:
            keep_browser_data(storage)

    def run(self) -> int:
        """Run the event loop until the last window closes."""
        return run_app(self)
