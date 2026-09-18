"""The frameless window that still animates and snaps like a native one.

The window is a Qt Quick window (``QQuickView``) holding one QML
``WebEngineView`` (``shell.qml``). It is not a widget ``QWebEngineView``
inside a ``QMainWindow``, for one measured reason: with widgets, every resize
of the window goes through Qt's widget backing store, which on Qt 6 presents
through the GPU three times per resize with a vsync wait each time, 50 to 80
ms per step whatever the graphics backend, so a live resize of the window
stuttered at under 20 fps. A Qt Quick window has one swap chain and a resize
costs one frame: the content follows the window edge at the display's rate,
with vsync on (presenting without it tore the image into a horizontal wave on
Windows 11).

The title bar is part of the page (``slantui/js/titlebar.js``), which is what
lets it carry the application's own look instead of a second, differently
styled strip on top of it. Moving and resizing are handed back to the window
manager through ``startSystemMove`` / ``startSystemResize``, so Windows keeps
doing snapping, edge magnetism and the drop shadow. The Win32 side of that is
``win32.py``.

Maximised is a state of this class, not of the HWND. The window is never
zoomed: maximised means a normal window animated onto the work area that
reports itself maximised to the page. ``win32.py`` says why a zoomed window
cannot be put on the work area. The paths by which Windows would zoom it
are covered: Win+Up and the taskbar menu arrive as a system command and are
routed to the window's own maximise; a drag to the top edge zooms without
asking, and that zoom is undone the moment Qt reports it. Dragging the band
of a maximised window restores it under the cursor first, as Windows does.
"""
from __future__ import annotations

from pathlib import Path

from ..tokens import DEFAULT, PALETTES
from . import win32
from .bridge import Bridge
from .qt import (QColor, QCursor, QEasingCurve, QIcon, QMetaObject, QObject, QQuickView, QRect,
                 QSize, QUrl, QVariant, QVariantAnimation, Q_ARG, Qt)

__all__ = ["Window", "SHELL_QML", "STATE_ANIM_MS"]

SHELL_QML = Path(__file__).resolve().parent / "shell.qml"

# The window animates its own maximise, restore and minimise. Windows' own
# transitions scale a snapshot of the last frame over a fixed curve and, for
# a window like this one, showed up as a jump. The geometry is animated here
# instead: the content is laid out and drawn at every intermediate size
# (cheap since the Quick shell), so the ramp is gradual and alive. The DWM
# transition is switched off only around the state change itself, so nothing
# animates twice.
STATE_ANIM_MS = 240


class Window(QQuickView):
    """A frameless window showing one page, with a bridge on its channel.

    ``page`` is the HTML file to show, or a ``QUrl``. A file path is loaded as
    a ``file://`` URL, which is what makes the page's own relative ``css/``
    and ``js/`` references resolve and keeps the UI a set of ordinary
    editable files. The page has to load ``qrc:///qtwebchannel/qwebchannel.js``
    before SlantUI's ``bridge.js``; Qt serves it from its resources.

    ``bridge`` is registered on the channel as ``object_name``; ``bridge.js``
    looks for ``backend`` unless told otherwise, so the defaults match. With
    no bridge given, a bare :class:`Bridge` is used, which is enough for the
    window chrome.

    ``background`` is the colour behind the page while it loads and while the
    window is resized. It defaults to ``surface-0`` of ``palette``, or of the
    default palette, so nothing flashes a different shade. Give it the same
    palette the page sets in ``data-palette``, and call :meth:`set_palette`
    when the page moves to another one.

    ``icon`` is best a ``.ico`` carrying 16 to 256 px renditions: Windows
    then picks a real 16 px icon for the taskbar instead of squashing a
    large one.
    """

    # Defaults on the class, so the event handlers below are safe to run
    # before __init__ has finished.
    _maximized = False              # covers the work area and says so; never zoomed
    _anim = None                    # the running geometry animation, if any
    _normal_rect = None             # where to come back to from maximised
    _pre_min = None                 # (rect, was maximised) before a minimise
    _native_frame = False           # set once the HWND carries the frame styles

    def __init__(self, page: str | Path | QUrl, *, bridge: Bridge | None = None,
                 title: str = "", icon: str | Path | None = None,
                 background: str | None = None, palette: str | None = None,
                 size: tuple[int, int] = (1280, 800), min_size: tuple[int, int] = (1024, 640),
                 object_name: str = "backend"):
        super().__init__()
        self.setTitle(title)              # the taskbar label
        self.setFlag(Qt.WindowType.FramelessWindowHint, True)
        if icon is not None and Path(icon).is_file():
            self.setIcon(QIcon(str(icon)))
        if background is None:
            background = PALETTES[palette or DEFAULT.slug]["surface-0"]
        self.background = background
        self.setColor(QColor(background))
        self._default_size = QSize(*size)
        self._min_size = QSize(*min_size)
        self.resize(self._default_size)
        self.setMinimumSize(self._min_size)
        self.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)

        self.bridge = bridge if bridge is not None else Bridge()
        self.bridge.window = self
        self.object_name = object_name
        self._js_callbacks: dict[int, object] = {}
        self._js_token = 0

        self._load(page)
        self.windowStateChanged.connect(self._on_state_changed)

    def _load(self, page: str | Path | QUrl) -> None:
        """Load ``shell.qml``, which points its WebEngineView at the page."""
        if isinstance(page, QUrl):
            url = page
        else:
            path = Path(page)
            if not path.is_file():
                raise FileNotFoundError(f"page not found: {path}")
            url = QUrl.fromLocalFile(str(path.resolve()))
        if not SHELL_QML.is_file():
            raise FileNotFoundError(f"window shell not found: {SHELL_QML}")
        self.page_url = url
        ctx = self.rootContext()
        ctx.setContextProperty("uiUrl", url)
        ctx.setContextProperty("uiBackground", self.background)
        self.setSource(QUrl.fromLocalFile(str(SHELL_QML)))
        if self.status() != QQuickView.Status.Ready:
            raise RuntimeError("window shell failed to load: "
                               + "; ".join(e.toString() for e in self.errors()))
        root = self.rootObject()
        self.channel = root.findChild(QObject, "channel")
        self.channel.registerObject(self.object_name, self.bridge)
        root.jsResult.connect(self._on_js_result)

    # ── the page, for tools and tests ────────────────────────────────────
    def run_js(self, script: str, callback=None) -> None:
        """Run ``script`` in the page; ``callback(value)`` gets its result
        (a JSON string, usually) on the GUI thread, once."""
        self._js_token += 1
        token = self._js_token
        if callback is not None:
            self._js_callbacks[token] = callback
        QMetaObject.invokeMethod(self.rootObject(), "run",
                                 Q_ARG("QVariant", QVariant(script)),
                                 Q_ARG("QVariant", QVariant(token)))

    def _on_js_result(self, token: int, value) -> None:
        cb = self._js_callbacks.pop(int(token), None)
        if cb is not None:
            cb(value)

    # ── the palette, when the page changes it ────────────────────────────
    def set_palette(self, palette: str) -> None:
        """Follow the page onto another palette.

        The page switches palette by itself (``Theme.setPalette``), but the
        colour behind it belongs to the window: it is what the screen shows
        while the page loads and, during a live resize, in the strip the page
        has not painted yet. On the wrong palette that strip flashes the old
        shade on every drag of the window edge. An application that lets the
        user change palette calls this from a slot of its own with the same
        slug it gave the page.
        """
        if palette not in PALETTES:
            raise KeyError(f"{palette!r} is not a SlantUI palette. "
                           f"Known: {', '.join(PALETTES)}")
        self.background = PALETTES[palette]["surface-0"]
        self.setColor(QColor(self.background))
        # The QML view reads this as a binding, so the web view's own
        # background follows the assignment.
        self.rootContext().setContextProperty("uiBackground", self.background)

    # ── the minimum width, when the page has measured itself ─────────────
    def set_min_width(self, width: int) -> int:
        """Stop the window being dragged narrower than the page needs.

        A shell whose step rail keeps every label whole has a width below
        which it cannot go, and only the page knows it: it depends on the
        text, the font the machine actually has, and how many steps the
        application declares. So the page measures the row once it is laid
        out and tells the window, which is the one that can refuse the drag.

        The number is capped to the screen, since a minimum wider than the
        display is a window nobody can use, and the applied width comes back
        so a caller can see what it got. It is kept as the window's minimum,
        not just set on it: a maximise drops the minimum to nothing for the
        length of the animation and puts it back afterwards, and a width set
        the other way would be lost on the first zoom.

        The slot that calls this is the application's. The six chrome slots
        on :class:`Bridge` are the contract ``titlebar.js`` calls and nothing
        else belongs in that list, the same way ``set_palette`` is reached
        through a slot of the application's own.
        """
        width = max(0, int(width))
        screen = self.screen()
        if screen is not None:
            width = min(width, screen.availableGeometry().width())
        self._min_size = QSize(width, self._min_size.height())
        if self._anim is None:
            self.setMinimumSize(self._min_size)
        return width

    # ── what the bridge asks of a "window" ───────────────────────────────
    def isMaximized(self) -> bool:
        return self._maximized

    def isMinimized(self) -> bool:
        return bool(self.windowState() & Qt.WindowState.WindowMinimized)

    def windowHandle(self):
        """The bridge hands drags and resizes to ``windowHandle()``; here that
        is the window itself."""
        return self

    def setWindowTitle(self, title: str) -> None:
        self.setTitle(title)

    def startSystemMove(self) -> bool:
        """A drag on the band. From maximised, the window first comes back to
        its normal size under the cursor, which is what Windows does with a
        real maximised window."""
        if self._maximized and self._anim is None:
            self._restore_under_cursor()
        return super().startSystemMove()

    # ── maximised, as a state of this class ──────────────────────────────
    def _work_area(self) -> QRect:
        return self.screen().availableGeometry()

    def _set_maximized(self, on: bool) -> None:
        if self._maximized != on:
            self._maximized = on
            self.bridge.windowMaximized.emit(on)

    def _track_normal(self) -> None:
        """Remember the last geometry the window had as a normal window, for
        the restore. Read off the events, because Qt reports geometry
        through a queue and a rectangle read right after a state change can
        be the old one. A rectangle covering the whole work area is a zoom
        in progress, not a normal size."""
        if self._maximized or self._anim is not None:
            return
        geo = self.geometry()
        if geo.width() <= 0 or geo.contains(self._work_area()):
            return
        self._normal_rect = geo

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._track_normal()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._track_normal()

    def _restore_under_cursor(self, cursor=None) -> None:
        """Back to the normal size at once, keeping the cursor at the same
        fraction of the width, so the band stays under the hand."""
        geo = self.geometry()
        normal = self._normal_rect or QRect(0, 0, self._default_size.width(),
                                            self._default_size.height())
        cur = QCursor.pos() if cursor is None else cursor
        frac = (cur.x() - geo.x()) / geo.width() if geo.width() > 0 else 0.5
        x = round(cur.x() - normal.width() * frac)
        self._set_maximized(False)
        self.setGeometry(QRect(x, geo.y(), normal.width(), normal.height()))
        self._restore_min_size()

    def _absorb_zoom(self) -> None:
        """Windows zoomed the window without asking (a drag to the top edge).
        A zoomed window sits with its frame past the screen and cannot be
        moved from there, so the zoom is undone at once, with the DWM
        transition off so nothing plays twice, and the window is put on the
        work area as the normal window it is everywhere else."""
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self._dwm_transitions(False)
        QQuickView.showNormal(self)
        self.setGeometry(self._work_area())
        self._dwm_transitions(True)
        self._restore_min_size()
        self._set_maximized(True)

    def _system_command(self, cmd: int) -> bool:
        """Win+Up, Win+Down and the taskbar menu send system commands. The
        three state changes are done here, animated, instead of by Windows.
        From the taskbar, restoring a minimised window stays the system's:
        ``_on_state_changed`` takes it from there."""
        if self.isMinimized():
            return False
        if cmd == win32.SC_MAXIMIZE:
            self.showMaximized()
            return True
        if cmd == win32.SC_MINIMIZE:
            self.showMinimized()
            return True
        if cmd == win32.SC_RESTORE and self._maximized:
            self.showNormal()
            return True
        return False

    def _on_state_changed(self, state) -> None:
        """Qt's own state changes: a zoom Windows did by itself, and the
        return from the taskbar, which grows from the small rectangle the
        window was minimised at."""
        if state & Qt.WindowState.WindowMaximized:
            self._absorb_zoom()
            return
        if self._pre_min is not None and not self.isMinimized():
            rect, was_max = self._pre_min
            self._pre_min = None
            if was_max:
                self._normal_rect = rect
                self._animate(self.geometry(), self._work_area(), self._finish_maximise)
            else:
                self._animate(self.geometry(), rect, self._restore_min_size)

    # ── animated state changes ───────────────────────────────────────────
    def _dwm_transitions(self, enabled: bool) -> None:
        win32.set_transitions(int(self.winId()), enabled)

    def _animate(self, start: QRect, end: QRect, done) -> None:
        """Move the window's geometry from ``start`` to ``end`` over
        STATE_ANIM_MS with an ease out, then call ``done``."""
        if self._anim is not None:
            self._anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setDuration(STATE_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self.setGeometry)

        def finished():
            self._anim = None
            self.setGeometry(end)
            done()
        anim.finished.connect(finished)
        self._anim = anim
        anim.start()

    def _restore_min_size(self) -> None:
        self.setMinimumSize(self._min_size)

    def _finish_maximise(self) -> None:
        self._restore_min_size()
        self._set_maximized(True)

    def showMaximized(self) -> None:
        if self._maximized or self._anim is not None or self.isMinimized():
            return
        self._normal_rect = self.geometry()
        self._animate(self.geometry(), self._work_area(), self._finish_maximise)

    def showNormal(self) -> None:
        if self._anim is not None:
            return
        if self.isMinimized() or not self._maximized:
            QQuickView.showNormal(self)
            return
        start = self.geometry()
        target = self._normal_rect or QRect(start.x() + 80, start.y() + 60,
                                            self._default_size.width(),
                                            self._default_size.height())
        self._set_maximized(False)
        self._animate(start, target, self._restore_min_size)

    def showMinimized(self) -> None:
        if self.isMinimized() or self._anim is not None:
            return
        start = self.geometry()
        was_max = self._maximized
        self._pre_min = (self._normal_rect if was_max and self._normal_rect else start, was_max)
        # Shrink towards the bottom edge, where the taskbar is, to a quarter.
        w, h = start.width() // 4, start.height() // 4
        end = QRect(start.center().x() - w // 2, self._work_area().bottom() - h, w, h)
        self.setMinimumSize(QSize(0, 0))

        def done():
            self._dwm_transitions(False)
            QQuickView.showMinimized(self)
            self._dwm_transitions(True)
        self._animate(start, end, done)

    # ── the native frame ─────────────────────────────────────────────────
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._native_frame:
            # nativeEvent() must already answer WM_NCCALCSIZE when the frame
            # change sends it, so the flag goes up first.
            self._native_frame = True
            win32.dress(int(self.winId()))

    def nativeEvent(self, eventType, message):
        """Answer the two messages that make the framed HWND look frameless
        (``win32.answer``) and take over the three system commands that would
        change the window's state (``win32.syscommand``). Everything else
        answers (False, 0), which is what the base implementation answers.
        It is not called: in PyQt6, calling ``super().nativeEvent()`` from an
        override crashes the process."""
        if self._native_frame:
            answer = win32.answer(int(message))
            if answer is not None:
                return answer
            cmd = win32.syscommand(int(message))
            if cmd is not None and self._system_command(cmd):
                return True, 0
        return False, 0

    def closeEvent(self, event) -> None:
        self.bridge.shutdown()
        super().closeEvent(event)
