"""The loading screen every application wearing this library shows while it
gets ready.

    splash = Splash(window=win, logo="brand.svg", text="starting", busy=True)
    splash.show()
    win.show()
    ...
    splash.set_progress(0.4, "reading the folders")
    ...
    splash.hide(190)

It is the screen the WPF half of the library draws through
``Show-SlantSplash``: the brand in the middle of a ring, a figure, a line
saying what is happening, and a thin bar under it. Same ring, same figure,
same line, same bar and the same three rules of movement on both sides, so an
application written in one and an application written in the other show one
screen and not two of them.

It comes in the same two forms, and they draw the same file:

* ``window=`` lays it over the body of a :class:`~slantui.shell.Window`, with
  the band left sharp above it, so the window can still be moved and closed
  while it loads, and the page out of focus under the veil. **This is the
  form an application uses**: the loading screen is the application's own
  window, a second before the application is in it, and not a separate little
  window that disappears and leaves the desktop empty for a moment.
* ``palette=`` and no window is a screen of its own, for the seconds before
  there is a window to dress at all. Paired with ``busy`` the two hand over
  without a seam.

**The ring measures and nothing else.** One arc, which moves when the work
moves. **The bar carries the other half** of what a load has to say, that it
is still going, and it has no scale precisely so that it cannot be read as a
quantity. **Waiting mode** (``busy``) drops the figure, because a figure with
nothing behind it is a lie, and turns the arc instead of filling it; the
first announced step turns it back into a measure by itself.

The arc has a speed, not a destination, which is what keeps it from starting
and stopping between two announced steps:

* far from the goal it moves quickly, proportionally to what is left, with a
  floor so a small gap is still crossed at a visible pace;
* at the goal it drifts on, slower and slower, towards a third of what
  remains: a load with nothing to report for four seconds must not look like
  a load that has stopped, and one per cent a second is movement without
  being a promise;
* at the end it closes the circle and stops, which is the one stop that means
  something.

The motion beats on the event loop, so work that blocks the loop for a second
holds the arc still for that second. Announce the steps around such work, or
do it where the loop keeps running: the screen is honest either way, since a
frozen arc is what a frozen application looks like.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..tokens import DEFAULT, PALETTES
from ..tokens.metrics import px, value
from .qt import QColor, QImage, QObject, QQuickView, QSize, QTimer, QUrl, Qt

__all__ = ["Splash", "SPLASH_QML", "HAZE_QML", "RING", "BLUR", "thickness",
           "screen_context"]

SPLASH_QML = Path(__file__).resolve().parent / "splash.qml"
HAZE_QML = Path(__file__).resolve().parent / "haze.qml"

# The ring the WPF screen draws, so the two are one screen. Its thickness
# follows its size, which is what keeps a ring asked for larger from coming
# out as a hoop of wire.
RING = 132.0

# How far the page behind the veil goes out of focus, as on the WPF side.
BLUR = 14.0

# The bar's band crosses its track in this, whatever else is happening.
SWEEP_MS = 1750.0

# One turn of the arc while it is waiting. Slower than a spinner in a page,
# because this one is large.
SPIN_MS = 1150.0

FRAME_MS = 16

# How often the page's own loading is read. It is a number that moves a few
# times a second at most, so reading it at every frame would be wasted work.
PAGE_MS = 120

# What the page's loading is worth on the arc. The first slice belongs to the
# application: its toolkit is up and its window is on screen, which is not
# nothing, and starting the page at zero would throw that away.
PAGE_FROM, PAGE_TO = 0.15, 0.95

# The flourish at the end: the ring lets a thin circle go outwards and fade,
# over this long. It is the one piece of decoration on the screen and it is
# there for a reason: it is what marks the difference between a load that
# finished and a screen that was taken away.
BURST_S = 0.5

# The longest the circle is given to close before the screen goes. An arc
# still climbing when the screen is taken away looks like something was
# skipped, so hiding closes it first; a load that ends at four per cent must
# not hold the finished application back for a second and a half either.
CLOSE_MAX = 0.9


def thickness(ring: float) -> float:
    return max(3.0, round(ring / 34.0))


def _components(colour: str) -> tuple[float, float, float]:
    """A palette's ``#rrggbb`` as three numbers between nought and one."""
    value = colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def screen_context(ctx, palette: str | None = None, ring: float = RING,
                   blur: float = BLUR) -> None:
    """Put the screen's vocabulary on a QML context.

    Both forms read the same names, and a window carries them whether or not
    it ever shows the screen, which is what lets one be raised on a window
    that is already up without reloading anything. Every colour is a role and
    every length is a metric: the screen cannot drift away from the widget set
    it stands in front of.
    """
    colours = PALETTES[palette or DEFAULT.slug]
    # The ring is drawn, not filled: it needs the accent and the track as
    # numbers, so it can lift them towards white and put them behind an alpha.
    # They are still the palette's, which is the whole rule; what changes is
    # that a canvas cannot be handed a role as a string and asked to lighten
    # it.
    for name, role in (("accent", "accent"), ("track", "control")):
        red, green, blue = _components(colours[role])
        ctx.setContextProperty(name + "R", red)
        ctx.setContextProperty(name + "G", green)
        ctx.setContextProperty(name + "B", blue)
    ctx.setContextProperty("splashSource", QUrl.fromLocalFile(str(SPLASH_QML)))
    ctx.setContextProperty("hazeSource", QUrl.fromLocalFile(str(HAZE_QML)))
    ctx.setContextProperty("splashBlur", float(blur))
    ctx.setContextProperty("splashBandHeight", px("tbar-h"))
    ctx.setContextProperty("surfaceColour", colours["surface-0"])
    ctx.setContextProperty("scrimColour", colours["scrim"])
    ctx.setContextProperty("accentColour", colours["accent"])
    ctx.setContextProperty("trackColour", colours["control"])
    ctx.setContextProperty("textColour", colours["text-3"])
    ctx.setContextProperty("fontFamily", value("font").split(",")[0].strip("'\""))
    ctx.setContextProperty("ringSize", float(ring))
    ctx.setContextProperty("ringThickness", thickness(ring))
    ctx.setContextProperty("cornerRadius", px("r-lg"))
    ctx.setContextProperty("figureSize", px("fs-lg"))
    ctx.setContextProperty("lineSize", px("fs-sm"))
    ctx.setContextProperty("figureGap", 17.0)
    ctx.setContextProperty("lineGap", 5.0)
    ctx.setContextProperty("barGap", 15.0)
    ctx.setContextProperty("barHeight", 3.0)


class Splash(QObject):
    """The loading screen, over a window's body or on its own.

    ``window`` is the :class:`~slantui.shell.Window` to lay it over, which is
    what an application does. With no window it opens one of its own, in
    ``palette``, for the seconds before the application's window exists.

    ``logo`` is what goes in the middle of the ring: a path to an ``.svg`` or
    a picture, or a ``QIcon`` / ``QPixmap`` / ``QImage`` an application drew
    for itself out of the palette. ``text`` is the first line under it, and
    ``busy`` starts in the waiting mode, where the arc turns instead of
    filling.
    """

    def __init__(self, *, window=None, palette: str | None = None, logo=None,
                 text: str = "", busy: bool = False, ring: float = RING,
                 blur: float = BLUR, follow_page: bool = True,
                 page_text: str = "loading the interface"):
        super().__init__(window)
        self.window = window
        self._own: QQuickView | None = None
        self._loader = None
        self._mark_file: str | None = None
        self._goal = 0.0
        self._pos = 0.0
        self._speed = 0.0
        self._elapsed = 0.0
        self._busy = bool(busy)
        self._visible = False
        self._closing = None
        self._burst = None

        if window is not None:
            self._root = self._over_window(window)
        else:
            self._root = self._own_window(palette, ring, blur)

        self._root.setProperty("busy", self._busy)
        self._root.setProperty("line", text)
        self._set_logo(logo)

        self._motor = QTimer(self)
        self._motor.setInterval(FRAME_MS)
        self._motor.timeout.connect(self._step)

        # Over a window, the page loading IS the wait, in every application
        # built this way: the toolkit is up, the window is on screen, and what
        # is left is a browser reading the files. So the screen follows it by
        # itself, and an application that announces nothing at all still shows
        # a load that moves because something is happening, which is the whole
        # rule. An application with steps of its own announces them on top.
        self._page = None
        if window is not None and follow_page:
            self._page_text = page_text
            self._page = QTimer(self)
            self._page.setInterval(PAGE_MS)
            self._page.timeout.connect(self._from_page)
            self._page.start()

    # ── the two forms ────────────────────────────────────────────────────
    def _over_window(self, window):
        """The screen over an application's body, under its band."""
        root = window.rootObject()
        loader = root.findChild(QObject, "splash") if root is not None else None
        if loader is None:
            raise RuntimeError("this window's shell has no loading screen in it")
        self._loader = loader
        loader.setProperty("active", True)
        item = loader.property("item")
        if item is None:
            raise RuntimeError("the loading screen did not load: "
                               f"{SPLASH_QML} is missing or would not parse")
        item.setProperty("opacity", 0.0)      # put up by show(), not by loading
        return item

    def _own_window(self, palette, ring, blur):
        """The screen as a window of its own, for before there is one."""
        view = QQuickView()
        view.setFlag(Qt.WindowType.FramelessWindowHint, True)
        view.setFlag(Qt.WindowType.Tool, True)        # no taskbar button of its own
        view.setColor(QColor(0, 0, 0, 0))             # the rounded corner needs the hole
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        screen_context(view.rootContext(), palette, ring, blur)
        if not SPLASH_QML.is_file():
            raise FileNotFoundError(f"loading screen not found: {SPLASH_QML}")
        view.setSource(QUrl.fromLocalFile(str(SPLASH_QML)))
        if view.status() != QQuickView.Status.Ready:
            raise RuntimeError("loading screen failed to load: "
                               + "; ".join(e.toString() for e in view.errors()))
        view.resize(int(ring * 1.3 + 72),
                    int(ring + 17 + px("fs-lg") + 5 + px("fs-sm") + 15 + 3 + 72))
        screen = view.screen()
        if screen is not None:
            area = screen.availableGeometry()
            view.setPosition(area.center().x() - view.width() // 2,
                             area.center().y() - view.height() // 2)
        self._own = view
        return view.rootObject()

    def _set_logo(self, logo) -> None:
        """A path, or a picture already in memory: an icon, a pixmap, an image.

        An application whose mark is drawn at run time out of the palette,
        which is what an application with no artwork of its own does for its
        taskbar icon, has a picture and no file to point QML at. That picture
        is written once, among the temporary files, and the file goes when the
        screen does: shorter than asking every such application to keep a PNG
        on disk for the two seconds it is looked at.
        """
        if logo is None:
            return
        if isinstance(logo, (str, Path)):
            path = Path(logo)
            if path.is_file():
                self._root.setProperty("logo", QUrl.fromLocalFile(str(path.resolve())))
            return
        image = logo
        if hasattr(image, "pixmap"):                      # a QIcon
            image = image.pixmap(QSize(512, 512))
        if hasattr(image, "toImage"):                     # a QPixmap
            image = image.toImage()
        if not isinstance(image, QImage) or image.isNull():
            return
        handle, name = tempfile.mkstemp(prefix="slantui-mark-", suffix=".png")
        os.close(handle)
        if image.save(name, "PNG"):
            self._mark_file = name
            self._root.setProperty("logo", QUrl.fromLocalFile(name))
        else:
            os.unlink(name)

    # ── what an application says to it ───────────────────────────────────
    def show(self) -> None:
        """Put the screen up and start the movement."""
        self._root.setProperty("opacity", 1.0)
        if self._own is not None:
            self._own.show()
        self._visible = True
        self._motor.start()

    def set_progress(self, fraction: float, text: str | None = None) -> None:
        """Announce a step: how far along, and what is happening now.

        The arc is not moved here, only its goal: the movement itself is the
        timer's, which is what keeps one announced step from jumping to the
        next. The first call leaves the waiting mode, since a step that can be
        announced is a step that can be measured.
        """
        self._goal = min(1.0, max(0.0, float(fraction)))
        if text is not None:
            self.set_text(text)
        if self._busy:
            self.set_busy(False)

    def set_text(self, text: str) -> None:
        """The line under the figure, without touching the arc."""
        self._root.setProperty("line", text)

    def set_busy(self, on: bool) -> None:
        """Waiting mode on or off: no figure, and the arc turns."""
        self._busy = bool(on)
        self._root.setProperty("busy", self._busy)

    def is_busy(self) -> bool:
        return self._busy

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def progress(self) -> float:
        """Where the arc is now, which is not where it was told to go."""
        return self._pos

    def hide(self, ms: int = 190, close: bool = True) -> None:
        """Take the screen away, over ``ms``.

        The circle is closed first. Work ends where it ends, usually with the
        arc some way short of the top, and a screen that vanishes from there
        reads as a load that was abandoned: the one stop that means something
        is the full circle. It is given ``CLOSE_MAX`` to get there and then
        goes anyway, so a fast start is not made to wait for its own
        animation. ``close=False`` skips it, for a screen being taken down
        because something failed.

        About two hundred milliseconds of fade is what hands over to a window
        already drawn underneath. Zero takes it away at once, which is what a
        screen with nothing behind it should do.
        """
        if not self._visible:
            return
        if close and self._pos < 0.995:
            self.set_progress(1.0)
            self._closing = (ms, self._elapsed + CLOSE_MAX + BURST_S * 0.62)
            return                     # the motor fades it once the circle is closed
        self._fade(ms)

    def _fade(self, ms: int) -> None:
        self._motor.stop()
        if ms <= 0:
            self._gone()
            return
        steps = max(1, int(ms / FRAME_MS))
        left = {"n": steps}
        fade = QTimer(self)

        def dim():
            left["n"] -= 1
            share = max(0.0, left["n"] / steps)
            self._root.setProperty("opacity", share)
            if self._own is not None:
                self._own.setOpacity(share)
            if left["n"] <= 0:
                fade.stop()
                self._gone()

        fade.timeout.connect(dim)
        fade.setInterval(FRAME_MS)
        fade.start()

    def _gone(self) -> None:
        """Nothing is showing the screen any more: put it all down."""
        self._visible = False
        if self._page is not None:
            self._page.stop()
        if self._own is not None:
            self._own.hide()
        if self._loader is not None:
            self._loader.setProperty("active", False)
        name, self._mark_file = self._mark_file, None
        if name:
            try:
                os.unlink(name)
            except OSError:
                pass

    def _from_page(self) -> None:
        """The page's own loading, as an announced step.

        An application that announces a step further on keeps it: the goal
        only ever moves forward, so the page cannot pull the arc back.
        """
        root = self.window.rootObject() if self.window is not None else None
        web = root.findChild(QObject, "web") if root is not None else None
        if web is None:
            self._page.stop()
            return
        share = web.property("loadProgress")
        if share is None:
            return
        want = PAGE_FROM + (PAGE_TO - PAGE_FROM) * max(0.0, min(100.0, float(share))) / 100.0
        if want > self._goal:
            self.set_progress(want, self._page_text)

    # ── the movement ─────────────────────────────────────────────────────
    def _step(self) -> None:
        self._advance(FRAME_MS / 1000.0)

    def _advance(self, dt: float) -> None:
        """One frame of the arc and of the bar. Arithmetic on three numbers,
        so it can be read and tested without a screen."""
        if dt <= 0:
            return
        dt = min(dt, 0.25)                 # a blocked loop must not teleport the arc
        self._elapsed += dt

        ceiling = 1.0 if self._goal >= 1.0 else self._goal + (1.0 - self._goal) * 0.32
        if self._pos < self._goal - 0.0005:
            # what is left, crossed in about a second and a half, never slower
            # than six per cent a second. The last stretch is quicker: the
            # screen is taken away shortly after the work ends, and an arc
            # still climbing when it goes looks like something was skipped.
            floor = 0.55 if self._goal >= 1.0 else 0.06
            if self._closing is not None:
                # closing: fast enough to actually get there in the time the
                # screen has left, so the circle closes instead of being cut
                # off wherever the work happened to end
                left = max(0.05, self._closing[1] - self._elapsed)
                floor = max(floor, (1.0 - self._pos) / left)
            want = max(floor, (self._goal - self._pos) * 0.68)
        elif self._pos < ceiling:
            want = 0.011                   # the drift: alive, and no promise
        else:
            want = 0.0

        # the speed is what is eased, so the movement has no corners even when
        # the goal jumps
        self._speed += (want - self._speed) * min(1.0, dt * 6.0)
        pos = self._pos + self._speed * dt
        if pos > ceiling:
            pos, self._speed = ceiling, want
        self._pos = min(1.0, pos)

        self._root.setProperty("progress", self._pos)
        self._root.setProperty("phase", (self._elapsed * 1000.0 % SWEEP_MS) / SWEEP_MS)
        if self._busy:
            self._root.setProperty("spin", (self._elapsed * 1000.0 % SPIN_MS) / SPIN_MS)

        # the circle closed: let the ring go once, and only once
        if self._burst is None and self._pos >= 0.999:
            self._burst = 0.0
        if self._burst is not None and self._burst < 1.0:
            self._burst = min(1.0, self._burst + dt / BURST_S)
            self._root.setProperty("burst", self._burst)

        if self._closing is not None:
            ms, deadline = self._closing
            # the flourish is half the reason the end reads as an end, so it
            # is given most of its half second before the screen fades
            flourished = self._burst is not None and self._burst >= 0.62
            if (self._pos >= 0.995 and flourished) or self._elapsed >= deadline:
                self._closing = None
                self._fade(ms)
