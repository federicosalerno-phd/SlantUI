"""The object the page talks to over ``QWebChannel``, with the window chrome
already on it.

An application subclasses :class:`Bridge`, adds its own slots and signals,
and hands an instance to :class:`slantui.shell.Window`, which registers it on
the channel under the name the page's ``bridge.js`` expects (``backend``
unless both sides agree on another).

The seven slots and the two signals here are the entire Python side of a
frameless window, and they are what ``titlebar.js`` calls. Their names are
the contract: a page written against them works with any application built
on this class.

What the slots ask of ``self.window`` is small and is listed next to
``Bridge.window`` below. A :class:`slantui.shell.Window` answers all of it,
and so does a ``QMainWindow``, which is what lets an application keep a
widget window and still use this bridge.
"""
from __future__ import annotations

from . import win32
from .qt import QCursor, QObject, Qt, pyqtSignal, pyqtSlot

__all__ = ["Bridge"]


class Bridge(QObject):
    """Subclass this. Add ``pyqtSlot`` methods for what the page may ask and
    ``pyqtSignal`` attributes for what Python pushes back."""

    # Emitted whenever the window is maximised or restored, by Python or by
    # Windows (snap, Win+Up, a double click on the band). titlebar.js swaps
    # the button's glyph on it.
    windowMaximized = pyqtSignal(bool)

    # Emitted when Windows opens its move or size loop on the window (True)
    # and when it closes it (False): a drag of the band, a resize from an
    # edge, a move from the keyboard. titlebar.js puts it on the page as
    # `windowMoving()` and a `windowmoving` event, and a page holds its idle
    # animations while it is true (see window.py, _set_moving).
    windowMoving = pyqtSignal(bool)

    # Set by the window that registers the bridge. Whatever it is, the slots
    # below call these on it: isMaximized(), showMaximized(), showNormal(),
    # showMinimized(), close(), and windowHandle(), which answers with the
    # object that has startSystemMove() and startSystemResize(). On a QWindow
    # that is the window itself; on a QWidget it is the QWindow behind it.
    window = None

    def shutdown(self) -> None:
        """Called once by the window when it closes. Stop worker threads
        here. The base does nothing."""

    # ── window chrome (the title bar is drawn by the page) ───────────────
    @pyqtSlot()
    def winMinimize(self) -> None:
        if self.window is not None:
            self.window.showMinimized()

    @pyqtSlot()
    def winMaximizeToggle(self) -> None:
        if self.window is None:
            return
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    @pyqtSlot()
    def winClose(self) -> None:
        if self.window is not None:
            self.window.close()

    @pyqtSlot()
    def winDrag(self) -> None:
        """Hand the drag to the window manager: snapping keeps working."""
        if self.window is None:
            return
        handle = self.window.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    @pyqtSlot(float, float)
    def winDragFrom(self, x: float, y: float) -> None:
        """The same, for a press that has already travelled. (x, y) is where
        the press landed, in the page's pixels from the window's corner.

        The title bar hands a press over only once it has moved
        (``titlebar.js``, ``DRAG_START_PX``), and Windows holds the window by
        wherever the cursor is when the move starts. By then the hand has gone
        some way, so the window would trail it by that much for the whole drag,
        the point that was taken no longer under the cursor: measured, thirty
        pixels at a brisk start. So that point goes back under the cursor
        first. A maximised window is left alone, and so is a snapped one:
        Windows restores either under the cursor itself, and a snapped window
        moved by a program first would forget it was snapped and keep its half
        screen size (``win32.is_arranged``)."""
        if self.window is None:
            return
        handle = self.window.windowHandle()
        if handle is None:
            return
        if not self.window.isMaximized() and not win32.is_arranged(int(handle.winId())):
            c = QCursor.pos()
            handle.setPosition(round(c.x() - x), round(c.y() - y))
        handle.startSystemMove()

    @pyqtSlot(str)
    def winResize(self, edge: str) -> None:
        """``edge`` is one of n, s, e, w, ne, nw, se, sw."""
        if self.window is None:
            return
        handle = self.window.windowHandle()
        if handle is None:
            return
        handle.startSystemResize(edges_of(edge))

    @pyqtSlot(result=bool)
    def winIsMaximized(self) -> bool:
        return bool(self.window is not None and self.window.isMaximized())


def edges_of(edge: str) -> Qt.Edge:
    """The ``Qt.Edge`` flags for a compass string such as ``"ne"``."""
    edges = Qt.Edge(0)
    if "n" in edge:
        edges |= Qt.Edge.TopEdge
    if "s" in edge:
        edges |= Qt.Edge.BottomEdge
    if "w" in edge:
        edges |= Qt.Edge.LeftEdge
    if "e" in edge:
        edges |= Qt.Edge.RightEdge
    return edges
