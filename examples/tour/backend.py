"""The tour's Python side: four slots and two signals on a SlantUI bridge.

The window chrome is not here. The six slots the title bar calls (minimise,
maximise, close, drag, resize, and the state query) are on :class:`Bridge`
already, so an application adds to them and never repeats them.

What is here is the shape of any application's backend:

    a slot that answers with JSON          appInfo, read with beJson()
    a slot that starts work                runJob
    a slot that stops it                   cancelJob
    a slot that drives the window          setPalette
    signals that report back               progress, jobDone
    shutdown(), called once when the window closes

The job is a ``QTimer`` counting on the GUI thread, which is enough to show
the round trip. Work that takes real time goes in a ``QThread`` and emits
``progress`` from there; the page cannot tell the two apart, since a signal
is a signal either way. What the page must never see is a slot that blocks:
the channel is answered on this thread, so a slot that sleeps freezes the
window.
"""
from __future__ import annotations

import json
import sys

from slantui import __version__
from slantui.shell import USE_QT6, Bridge, pyqtSignal, pyqtSlot
from slantui.shell.qt import QTimer, qVersion

# How often the job reports, and the stage names it reports, each with the
# percentage it runs to.
TICK_MS = 60
STAGES = ((18, "Reading the file"),
          (45, "Measuring"),
          (72, "Building the patch"),
          (100, "Writing the results"))


class Tour(Bridge):
    """The backend of the example application.

    ``progress(percent, stage)`` fires while a job runs, ``jobDone(finished)``
    once at the end, with ``False`` when the job was cancelled. Two signals
    instead of one sentinel value, so the page reads what happened without
    knowing a convention.
    """

    progress = pyqtSignal(int, str)
    jobDone = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._ticks = 1          # how many ticks the running job lasts
        self._n = 0              # how many it has had
        # Whether a job is running is this class's own state and not a
        # reading off the timer. The page can cancel one, and a cancel has to
        # answer the same way whether or not Qt has an event loop under it.
        self._running = False

        # Called once, when the page first speaks. main.py hangs the loading
        # screen on it: the page asking for this is the page being alive, and
        # is the one moment that says the window has something on it.
        self.on_page_ready = None

    # ── what the page asks ───────────────────────────────────────────────
    @pyqtSlot(result=str)
    def appInfo(self) -> str:
        """Versions for the side panel, as a JSON string.

        A slot can answer with any type QWebChannel knows, and JSON is the
        one that carries a whole record in a single call. The page reads it
        with ``beJson('appInfo', undefined, fn)``.
        """
        if self.on_page_ready is not None:
            ready, self.on_page_ready = self.on_page_ready, None
            ready()
        return json.dumps({
            "slantui": __version__,
            "python": "%d.%d.%d" % sys.version_info[:3],
            "qt": qVersion(),
            "binding": "PyQt6" if USE_QT6 else "PyQt5",
        })

    @pyqtSlot(int)
    def runJob(self, ms: int) -> None:
        """Start a job that takes ``ms`` milliseconds and reports as it goes."""
        self._ticks = max(1, round(ms / TICK_MS))
        self._n = 0
        self._running = True
        self._report(0)
        self._timer.start()

    @pyqtSlot()
    def cancelJob(self) -> None:
        """Stop a running job. Doing nothing when none is running is on
        purpose: the page may cancel twice, and a backend that raised inside a
        slot would take the window down with it."""
        if not self._running:
            return
        self._running = False
        self._timer.stop()
        self.jobDone.emit(False)

    @pyqtSlot(str)
    def setPalette(self, palette: str) -> None:
        """The page moved to another palette, so the window follows it.

        The colour behind the page is the window's, not the page's, and it
        shows during a live resize. ``Window.set_palette`` is the one line
        that keeps the two in step.
        """
        if self.window is not None:
            self.window.set_palette(palette)

    # ── the job itself ───────────────────────────────────────────────────
    def _tick(self) -> None:
        self._n += 1
        pct = min(100, round(self._n * 100 / self._ticks))
        self._report(pct)
        if pct >= 100:
            self._running = False
            self._timer.stop()
            self.jobDone.emit(True)

    def _report(self, pct: int) -> None:
        stage = next(name for end, name in STAGES if pct <= end)
        self.progress.emit(pct, stage)

    # ── the window is closing ────────────────────────────────────────────
    def shutdown(self) -> None:
        """Called once by the window on close. A timer left running here is
        harmless; a worker thread left running is not, and this is where it
        gets stopped."""
        self._running = False
        self._timer.stop()
