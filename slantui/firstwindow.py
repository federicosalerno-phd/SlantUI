"""The first window: what an application puts on screen the moment it is
started, before it has a toolkit to dress a real one with.

    from slantui import firstwindow

    app = firstwindow.application("Me.MyApp")
    first = firstwindow.FirstWindow(palette="gold-dark", logo="mark.svg",
                                    text="starting", size=(1280, 800),
                                    title="My App", band="band.png")
    first.shown.connect(start_the_application)   # told first.rect_text() and first.since
    first.show()
    app.exec()

A :class:`~slantui.shell.Window` and its loading screen are QtQuick, and
QtQuick costs a second and more on a computer that is busy: the QML engine,
its plugins, a graphics device, and then the browser. Someone who clicks an
icon and sees nothing for that long clicks it again. This is the same window
drawn with a painter and nothing else: at the size the application's Window
opens at, the band the application saved the last time it ran at the top,
the empty window in surface-0 under it, and over that the loading screen of
splash.qml in its waiting mode, with the same ring, mark, line and bar in the
same places. It needs QtWidgets and no more of the toolkit, so it is up in a
few tenths of a second.

The application is then started behind it, as a process of its own, and opens
its Window on exactly this rectangle with its own Splash over it, told when
this one began turning (``Splash(since=...)``) so the arc carries on where it
was. When that window is on screen this one is closed, under it, and what the
person saw was one window, loading. The application's process can block for as
long as its imports and its browser take: this window lives in another process
and keeps turning.

It sits outside ``slantui.shell`` on purpose. Importing that package imports
the browser and QtQuick, which is the cost this module exists to avoid. For
the same reason the tokens are read only when no ``look`` is given: the
application keeps :func:`look` of its palette beside the band, and the window
drawn from it needs no more of this library than this file.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

try:
    from PyQt6.QtCore import QByteArray, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import (QColor, QCursor, QFont, QFontMetricsF, QGuiApplication, QIcon, QImage,
                             QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient)
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtWidgets import QApplication, QWidget
    USE_QT6 = True
except ImportError:  # pragma: no cover - depends on the install
    from PyQt5.QtCore import QByteArray, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
    from PyQt5.QtGui import (QColor, QCursor, QFont, QFontMetricsF, QGuiApplication, QIcon, QImage,
                             QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient)
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtWidgets import QApplication, QWidget
    USE_QT6 = False

__all__ = ["FirstWindow", "application", "is_round", "logo_side", "look", "paint_screen", "place", "RING",
           "SPIN_MS", "SWEEP_MS"]

# The numbers of shell/splash.py and splash.qml, which this screen has to match
# to the pixel and to the millisecond (tests/test_firstwindow.py holds them
# together): the ring, one turn of the waiting arc, one crossing of the bar.
RING = 132.0
SPIN_MS = 1150.0
SWEEP_MS = 1750.0
FRAME_MS = 16
SHOWN_AFTER_MS = 50     # from the first paint to `shown`: the compositor's next frames, with room to spare

# splash.qml's column, in its waiting mode: the ring, a gap, the line, a gap,
# the bar. The figure is not drawn while waiting, and neither is its gap.
FIGURE_GAP = 17.0
BAR_GAP = 15.0
BAR_HEIGHT = 3.0

# Windows 11: round corners and no hairline border, as win32.dress gives the
# Window, so the two cannot be told apart at the handover.
_DWMWA_TRANSITIONS_FORCEDISABLED = 3       # no fade in: the first frame under it goes the moment this one is up
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWCP_ROUND = 2
_DWMWA_COLOR_NONE = 0xFFFFFFFE


def _thickness(ring: float) -> float:
    return max(3.0, round(ring / 34.0))


def logo_side(ring: float, round_logo: bool = False) -> int:
    """How wide the mark is drawn in the ring. A mark sits in a square half the ring wide; a round one, a picture
    that is a disc of its own (is_round), fills the ring, with a gap of one and a half arcs inside it, so the ring
    reads as its frame and not as a second circle round a small one. splash.qml is given the same number."""
    if round_logo:
        return round(ring - 5 * _thickness(ring))
    return round(ring * 0.52)


def is_round(logo, n: int = 64) -> bool:
    """Whether a mark (an .svg's path or bytes, a QSvgRenderer, a QImage) is a disc of its own: square, its four
    corners empty and its rim filled all the way round. The picture says it, so an application has nothing to
    declare for its loading screens."""
    if not isinstance(logo, (QSvgRenderer, QImage)):
        logo = FirstWindow._load_logo(logo)
    img = QImage(n, n, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    if isinstance(logo, QSvgRenderer) and logo.isValid():
        d = logo.defaultSize()
        if d.width() <= 0 or abs(d.width() - d.height()) > 0.01 * d.width():
            return False
        q = QPainter(img)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        logo.render(q, QRectF(0, 0, n, n))
        q.end()
    elif isinstance(logo, QImage) and not logo.isNull():
        if abs(logo.width() - logo.height()) > 0.01 * logo.width():
            return False
        img = logo.scaled(n, n, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_ARGB32)
    else:
        return False
    if any(img.pixelColor(x, y).alpha() > 16 for x in (1, n - 2) for y in (1, n - 2)):
        return False
    c, r = (n - 1) / 2, 0.9 * n / 2
    return all(img.pixelColor(round(c + r * math.cos(a)), round(c + r * math.sin(a))).alpha() > 240
               for a in (k * math.pi / 8 for k in range(16)))


def look(palette: str | None = None) -> dict:
    """What the screen is drawn with, out of the tokens: four roles of the
    palette, the band's height, the line's size and its face. Plain values,
    so an application can keep them in a file for the next start."""
    from .tokens import DEFAULT, PALETTES
    from .tokens.metrics import px, value
    roles = PALETTES[palette or DEFAULT.slug]
    return {"surface": roles["surface-0"], "accent": roles["accent"], "track": roles["control"],
            "text": roles["text-3"], "band": px("tbar-h"), "line": px("fs-sm"),
            "font": value("font").split(",")[0].strip("'\"")}


_look_of = look                             # FirstWindow has a parameter of the same name


def application(app_id: str = "", argv: list[str] | None = None) -> QApplication:
    """The application object of a first window: the taskbar identity the
    application will have, so its button is the application's from the first
    frame, and the high DPI policy of :class:`~slantui.shell.Application`, so
    a rectangle measured here is the same rectangle there. The browser is not
    loaded, but the one switch it needs before an application object exists is
    set, so the same process can still open a Window after this one."""
    if app_id and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass
    app = QApplication.instance()
    if app is None:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts if USE_QT6
                                  else Qt.AA_ShareOpenGLContexts, True)
    if USE_QT6:
        try:
            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            pass
    return app if app is not None else QApplication(list(sys.argv[:1] if argv is None else argv))


def place(size: tuple[int, int]) -> QRect:
    """Where a window of ``size`` opens: in the middle of the screen the
    pointer is on, and never larger than what that screen has free."""
    screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    area = screen.availableGeometry()
    w, h = min(int(size[0]), area.width()), min(int(size[1]), area.height())
    return QRect(area.x() + (area.width() - w) // 2, area.y() + (area.height() - h) // 2, w, h)


def _colour(hex_: str, alpha: float = 1.0) -> QColor:
    """A palette colour, ``#rrggbb`` or ``#rrggbbaa`` as the palette writes it."""
    v = hex_.lstrip("#")
    c = QColor(int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16),
               int(v[6:8], 16) if len(v) == 8 else 255)
    if alpha < 1.0:
        c.setAlphaF(c.alphaF() * alpha)
    return c


def _lifted(c: QColor, k: float, alpha: float = 1.0) -> QColor:
    """The accent lifted towards white, as splash.qml's lifted()."""
    return QColor.fromRgbF(c.redF() + (1 - c.redF()) * k, c.greenF() + (1 - c.greenF()) * k,
                           c.blueF() + (1 - c.blueF()) * k, alpha)


def _ease(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 4 * t * t * t if t < 0.5 else 1 - math.pow(-2 * t + 2, 3) / 2


def _clamp(t: float) -> float:
    return max(0.0, min(1.0, t))


def _fit(w: float, h: float, side: float) -> tuple[float, float]:
    k = min(side / w, side / h)
    return w * k, h * k


def paint_screen(p: QPainter, area: QRectF, lk: dict, *, spin: float = 0.0, phase: float = 0.0,
                 text: str = "", logo=None, ring: float = RING, round_logo: bool = False) -> None:
    """splash.qml in its waiting mode, painted into ``area`` (the body of a
    window, under its band): the track, a fifth of the circle turning with its
    lit head, the mark in the middle, the line, and the bar's two lozenges.
    ``lk`` is a :func:`look`; ``spin`` and ``phase`` are the turn and the
    bar's travel, nought to one; ``logo`` a QSvgRenderer or a QImage, and ``round_logo`` whether it is a disc of
    its own, which fills the ring (logo_side)."""
    accent = _colour(lk["accent"])
    track = _colour(lk["track"])
    t = _thickness(ring)
    font = QFont(lk["font"])
    # a whole number, as QML's font.pixelSize takes it: rounded half up (11.5 is 12 there), never cut
    font.setPixelSize(int(math.floor(float(lk["line"]) + 0.5)))
    p.setFont(font)
    line_h = QFontMetricsF(font).height()
    column = ring + FIGURE_GAP + line_h + BAR_GAP + BAR_HEIGHT
    cx = area.center().x()
    # on a whole pixel of the screen: the ring and the mark land on the very pixels splash.qml puts them on
    dpr = p.device().devicePixelRatioF() if p.device() is not None else 1.0
    top = round((area.y() + (area.height() - column) / 2) * dpr) / dpr
    cy = top + ring / 2
    r = (ring - t) / 2
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # the track, thinner than the arc
    tc = QColor(track)
    tc.setAlphaF(0.38)
    p.setPen(QPen(tc, max(1.0, t * 0.55)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(rect)

    # the arc: from a lighter accent to the accent, along a gradient laid on
    # the box and not on the arc, so it does not swing round as it turns
    grad = QLinearGradient(QPointF(cx - ring * 0.40, cy - ring * 0.50), QPointF(cx + ring * 0.40, cy + ring * 0.50))
    grad.setColorAt(0.0, _lifted(accent, 0.38))
    grad.setColorAt(0.65, accent)
    grad.setColorAt(1.0, accent)
    pen = QPen(grad, t)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    # a canvas measures clockwise from three o'clock, a painter counter-clockwise
    start = (spin % 1.0 - 0.25) * 360.0
    p.drawArc(rect, int(round(-start * 16)), int(round(-0.2 * 360.0 * 16)))

    # the head, where the eye goes: a glow and a lit dot
    a = ((spin + 0.2) % 1.0 - 0.25) * 2 * math.pi
    head = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
    glow = QRadialGradient(head, t * 2.3)
    for at, alpha in ((0.0, 0.30), (0.55, 0.09), (1.0, 0.0)):
        c = QColor(accent)
        c.setAlphaF(alpha)
        glow.setColorAt(at, c)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(head, t * 2.3, t * 2.3)
    p.setBrush(_lifted(accent, 0.30))
    p.drawEllipse(head, t * 0.46, t * 0.46)

    # the mark, fitted in a square half the ring wide, or a round one filling the ring
    side = logo_side(ring, round_logo)
    if isinstance(logo, QSvgRenderer) and logo.isValid():
        d = logo.defaultSize()
        w, h = _fit(d.width(), d.height(), side) if d.width() > 0 and d.height() > 0 else (side, side)
        logo.render(p, QRectF(cx - w / 2, cy - h / 2, w, h))
    elif isinstance(logo, QImage) and not logo.isNull():
        dpr = logo.devicePixelRatio() or 1.0
        w, h = _fit(logo.width() / dpr, logo.height() / dpr, side)
        p.drawImage(QRectF(cx - w / 2, cy - h / 2, w, h), logo)

    # the line
    y = top + ring + FIGURE_GAP
    p.setPen(_colour(lk["text"]))
    p.drawText(QRectF(area.x(), y, area.width(), line_h),
               int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), text)

    # the bar: a rail and two lozenges half a turn apart
    y += line_h + BAR_GAP
    bw = ring * 1.3
    x0 = cx - bw / 2
    inset = BAR_HEIGHT / 2
    span = bw - 2 * inset
    rail = max(1.0, BAR_HEIGHT * 0.5)
    p.setPen(Qt.PenStyle.NoPen)
    rc = QColor(track)
    rc.setAlphaF(0.30)
    p.setBrush(rc)
    p.drawRoundedRect(QRectF(x0 + inset, y + (BAR_HEIGHT - rail) / 2, span, rail), rail / 2, rail / 2)
    for at, ink, thin in ((0.5, 0.30, 0.8), (0.0, 0.92, 1.0)):
        u = (phase + at) % 1.0
        lo = _ease(_clamp((u - 0.34) / 0.66))
        hi = _ease(_clamp(u / 0.66))
        if hi - lo <= 0.006:
            continue
        h = BAR_HEIGHT * thin
        c = QColor(accent)
        c.setAlphaF(ink)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(x0 + inset + span * lo, y + (BAR_HEIGHT - h) / 2, span * (hi - lo), h),
                          h / 2, h / 2)


class FirstWindow(QWidget):
    """The application's window, empty and loading, drawn by a painter.

    ``palette`` is the application's, or ``look`` what :func:`look` made of
    it (then the tokens are not read at all). ``logo`` is the mark in the ring
    (an .svg or a picture, or an .svg's bytes), ``icon`` the taskbar's (an
    icon file, a QIcon, or an .svg's bytes), ``text`` the line under it. ``band`` is the band
    as the application's Window drew it, a picture the application saved the
    last time it ran, or a list of them, one per screen scale: one is drawn
    only when it is exactly as wide as this window at this screen's scale,
    and without one the top of the window is the
    empty window's colour too. ``close_rect`` is where the band's close button
    is, ``[x, y, w, h]`` in the band's pixels: a press there closes the window.
    ``size`` is the size the application's Window opens at, placed by
    :func:`place`. ``since`` is when the motion began (at the first frame on
    screen), ``time.time()``, which a Splash taking over is given.

    ``shown`` is emitted once, when the first frame has been painted: the
    moment to start the application, which would otherwise compete with this
    window for the computer while it is being put on screen. ``closed`` is
    emitted when the person closes it (that button, Alt+F4, the taskbar),
    never when the application does: it means the start is called off.
    """

    shown = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, *, palette: str | None = None, look: dict | None = None, logo=None, text: str = "",
                 band=None, size: tuple[int, int] = (1280, 800), title: str = "", icon=None, close_rect=None):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.look = dict(look) if look else _look_of(palette)
        self.text = text
        self.setWindowTitle(title)
        icon = self._load_icon(icon)
        if icon is not None:
            self.setWindowIcon(icon)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._ground = _colour(self.look["surface"])
        self._logo_src = self._load_logo(logo)
        self._round = is_round(self._logo_src)      # a disc of its own fills the ring
        self._logo = None                   # the mark drawn once at this screen's scale
        # one picture, or several (one per screen scale the application has been on): the one that fits is drawn
        bands = band if isinstance(band, (list, tuple)) else [band]
        self._bands = [b if isinstance(b, QImage) else QImage(str(b)) for b in bands if b is not None]
        self._bands = [b for b in self._bands if not b.isNull()]
        self._close_rect = None
        if close_rect is not None and len(close_rect) == 4:
            self._close_rect = QRectF(*(float(v) for v in close_rect))
        self.setGeometry(place(size))
        self.since = time.time()
        self._t0 = time.perf_counter()
        self._painted = False
        self._motor = QTimer(self)
        self._motor.setInterval(FRAME_MS)
        self._motor.timeout.connect(self._tick)
        self._dressed = False

    def set_pictures(self, *, logo=None, icon=None, band=None) -> None:
        """The mark, the icon or the band given after the window is up, for an application whose pictures are on a
        drive slower than this window is allowed to be: the window does not wait for them."""
        icon = self._load_icon(icon)
        if icon is not None:
            self.setWindowIcon(icon)
        if logo is not None:
            self._logo_src = self._load_logo(logo)
            self._round = is_round(self._logo_src)
            self._logo = None
        if band is not None:
            bands = band if isinstance(band, (list, tuple)) else [band]
            self._bands = [b for b in (x if isinstance(x, QImage) else QImage(str(x)) for x in bands) if not b.isNull()]
        self.update()

    def _tick(self) -> None:
        """A frame of the motion: only the ring with the air around it and the bar are drawn again, since the rest
        of the window does not move (the whole window at every frame cost a core of a busy computer)."""
        band_h = float(self.look["band"])
        halo = max(_thickness(RING) * 1.9, RING * 0.16) + 4
        w = max(RING * 1.3, RING) + 2 * halo
        h = RING + FIGURE_GAP + 2 * float(self.look["line"]) + BAR_GAP + BAR_HEIGHT + 2 * halo
        cx, cy = self.width() / 2, band_h + (self.height() - band_h) / 2
        self.update(QRect(int(cx - w / 2), int(cy - h / 2), int(math.ceil(w)), int(math.ceil(h))))

    @staticmethod
    def _load_logo(logo):
        """A path to an .svg or a picture, the bytes of an .svg, or a renderer or a picture already made."""
        if isinstance(logo, (QSvgRenderer, QImage)):
            return logo
        if isinstance(logo, (bytes, bytearray)):
            r = QSvgRenderer(QByteArray(bytes(logo)))
            return r if r.isValid() else None
        if logo is None or not Path(logo).is_file():
            return None
        if Path(logo).suffix.lower() == ".svg":
            r = QSvgRenderer(str(logo))
            return r if r.isValid() else None
        img = QImage(str(logo))
        return None if img.isNull() else img

    @staticmethod
    def _load_icon(icon):
        """The taskbar's icon: a QIcon, a path to an icon file, or the bytes of an .svg drawn at the sizes the
        taskbar asks for, the way an application draws its own from its .svg."""
        if icon is None or isinstance(icon, QIcon):
            return icon
        if isinstance(icon, (bytes, bytearray)):
            r = QSvgRenderer(QByteArray(bytes(icon)))
            if not r.isValid():
                return None
            out = QIcon()
            for side in (16, 24, 32, 48, 64, 128, 256):
                img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
                img.fill(Qt.GlobalColor.transparent)
                q = QPainter(img)
                q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                r.render(q, QRectF(0, 0, side, side))
                q.end()
                out.addPixmap(QPixmap.fromImage(img))
            return out
        return QIcon(str(icon)) if Path(icon).is_file() else None

    def _mark(self, dpr: float | None = None):
        """The mark as a picture at this screen's scale, drawn once: an SVG
        read again at every frame is work for nothing."""
        dpr = self.devicePixelRatioF() if dpr is None else dpr
        if self._logo is not None and abs(self._logo.devicePixelRatio() - dpr) < 1e-3:
            return self._logo
        src = self._logo_src
        if not isinstance(src, QSvgRenderer):
            return src
        side = logo_side(RING, self._round)
        d = src.defaultSize()
        w, h = _fit(d.width(), d.height(), side) if d.width() > 0 and d.height() > 0 else (side, side)
        img = QImage(max(1, math.ceil(w * dpr)), max(1, math.ceil(h * dpr)), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        src.render(q, QRectF(0, 0, img.width(), img.height()))
        q.end()
        img.setDevicePixelRatio(dpr)
        self._logo = img
        return img

    def _band_image(self, dpr: float | None = None) -> QImage | None:
        """The saved band that was drawn for this width at this scale, if one was."""
        dpr = self.devicePixelRatioF() if dpr is None else dpr
        for img in self._bands:
            if abs(img.width() - math.ceil(self.width() * dpr - 1e-6)) <= 1:
                img.setDevicePixelRatio(dpr)
                return img
        return None

    def rect_text(self) -> str:
        """``x,y,w,h`` of this window, in the toolkit's own (device independent)
        pixels: where the application's Window is to open."""
        g = self.geometry()
        return f"{g.x()},{g.y()},{g.width()},{g.height()}"

    def showEvent(self, event) -> None:      # noqa: N802  (Qt's name)
        super().showEvent(event)
        if not self._dressed:
            self._dressed = True
            self._dress()
        self._motor.start()

    def hideEvent(self, event) -> None:      # noqa: N802
        self._motor.stop()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:     # noqa: N802
        if event.spontaneous():
            self.closed.emit()
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position() if USE_QT6 else QPointF(event.pos())
        if (self._close_rect is not None and self._band_image() is not None
                and self._close_rect.contains(pos)):
            self.closed.emit()
            self.close()
            return
        super().mousePressEvent(event)

    def _dress(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            hwnd = wintypes.HWND(int(self.winId()))
            for attr, val in ((_DWMWA_TRANSITIONS_FORCEDISABLED, 1),
                              (_DWMWA_WINDOW_CORNER_PREFERENCE, _DWMWCP_ROUND),
                              (_DWMWA_BORDER_COLOR, _DWMWA_COLOR_NONE)):
                v = ctypes.c_uint(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)
        except Exception:
            pass                            # older Windows: square corners, nothing else changes

    def _draw(self, p: QPainter, elapsed: float, dpr: float | None = None) -> None:
        p.fillRect(QRectF(0, 0, self.width(), self.height()), self._ground)
        band_h = float(self.look["band"])
        band = self._band_image(dpr)
        if band is not None:
            p.drawImage(QPointF(0, 0), band)
        paint_screen(p, QRectF(0, band_h, self.width(), self.height() - band_h), self.look,
                     spin=(elapsed % SPIN_MS) / SPIN_MS, phase=(elapsed % SWEEP_MS) / SWEEP_MS,
                     text=self.text, logo=self._mark(dpr), round_logo=self._round)

    def picture(self, scale: float) -> QImage:
        """The first frame, the motion at its start, as a picture of this
        window at ``scale``: what a start can put on screen before it has a
        toolkit at all. The window's own first frame is this one, since its
        motion starts when it is first painted."""
        img = QImage(math.ceil(self.width() * scale - 1e-6), math.ceil(self.height() * scale - 1e-6),
                     QImage.Format.Format_RGB32)
        img.setDevicePixelRatio(scale)
        p = QPainter(img)
        self._draw(p, 0.0, scale)
        p.end()
        self._logo = None                   # drawn at that scale: drawn again at the screen's
        return img

    def paintEvent(self, event) -> None:     # noqa: N802
        if not self._painted:               # the motion starts at the first frame on screen
            self._t0, self.since = time.perf_counter(), time.time()
        p = QPainter(self)
        self._draw(p, (time.perf_counter() - self._t0) * 1000.0)
        p.end()
        if not self._painted:
            self._painted = True
            # painted is not yet on screen: the compositor shows it at its next frame or two, and whatever is
            # under this window (a first frame of the start's own) must stay until then, or the desktop shows
            QTimer.singleShot(SHOWN_AFTER_MS, self.shown.emit)
