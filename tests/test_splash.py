"""The loading screen: its file, its vocabulary, and the way the arc moves.

Nothing here opens a window. The movement is arithmetic on three numbers and
is tested as such, which is the point of keeping it in Python instead of in
the QML: a screen whose arc stalls, or jumps, or arrives before the work does
is a screen nobody trusts again, and none of that is visible in a screenshot.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "slantui" / "shell"
SPLASH_PY = (SHELL / "splash.py").read_text(encoding="utf-8")
SPLASH_QML = (SHELL / "splash.qml").read_text(encoding="utf-8")


# ── the file ────────────────────────────────────────────────────────────────
def test_the_qml_is_next_to_the_python():
    assert (SHELL / "splash.qml").is_file()


def test_the_qml_is_packaged():
    """It is read at run time out of the installed package, like shell.qml."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "shell/*.qml" in pyproject


def test_the_screen_names_no_colour():
    """The house rule, on the one file that draws outside a stylesheet.

    The ring is a drawing, so it does build colours: it lifts the accent
    towards white and puts it behind an alpha. What it may not do is name one.
    Every ``Qt.rgba`` in it takes its three components from the palette, so a
    literal in the first of those three, or a hex string anywhere, is the
    failure this looks for.
    """
    hits = [line.strip() for line in SPLASH_QML.splitlines()
            if re.search(r"#[0-9a-fA-F]{3}\b|#[0-9a-fA-F]{6}\b", line)
            or re.search(r"\brgba?\(\s*[\d.]", line)]
    assert not hits, hits


def test_the_ring_builds_its_colours_from_the_palette():
    """Both roles reach the canvas as three numbers, and it reads all six."""
    for role in ("accent", "track"):
        for channel in "RGB":
            assert role + channel in SPLASH_QML, f"the screen never reads {role}{channel}"
    assert 'name + "R"' in SPLASH_PY, "the python never sets the components"


def test_the_screen_takes_its_lengths_from_the_python():
    """The ring, the gaps and the two type sizes are set where the metrics
    are, so the screen cannot drift from the widget set it stands in front
    of."""
    for name in ("ringSize", "ringThickness", "cornerRadius", "figureSize",
                 "lineSize", "figureGap", "lineGap", "barGap", "barHeight"):
        assert name in SPLASH_QML, f"the screen never reads {name}"
        assert f'"{name}"' in SPLASH_PY, f"the python never sets {name}"


# ── the movement ────────────────────────────────────────────────────────────
@pytest.fixture
def arc():
    """A screen with no window under it: only the numbers that move."""
    pytest.importorskip("slantui.shell")
    from slantui.shell.splash import Splash

    class Dummy:
        def __init__(self):
            self.props = {}

        def setProperty(self, name, value):     # noqa: N802  (Qt's name)
            self.props[name] = value

    s = Splash.__new__(Splash)
    s._root = Dummy()
    s._goal = 0.0
    s._pos = 0.0
    s._speed = 0.0
    s._elapsed = 0.0
    s._busy = False
    s._closing = None
    s._burst = None
    return s


def run(arc, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        arc._advance(dt)
    return arc._pos


def test_an_announced_step_is_crossed(arc):
    """Most of the gap goes in the first second and a half, and the rest at
    the floor, which is what keeps the end of a step visible. Past it the arc
    is drifting, so the goal is a place it reaches and not a place it sits."""
    arc._goal = 0.6
    assert 0.35 < run(arc, 1.5) < 0.58
    assert run(arc, 4.0) >= 0.6


def test_it_does_not_arrive_the_moment_the_step_is_announced(arc):
    """The arc is a speed, so a step announced now is not drawn now: a fifth
    of a second in it has left, and it is nowhere near the goal."""
    arc._goal = 0.6
    pos = run(arc, 0.2)
    assert 0.005 < pos < 0.2


def test_at_the_goal_it_drifts_and_never_reaches_the_next_step(arc):
    """A load with nothing to report for four seconds must not look like a
    load that has stopped, and the drift must not promise the step after."""
    arc._goal = 0.5
    run(arc, 2.0)
    before = arc._pos
    after = run(arc, 4.0)
    assert after > before + 0.02, "the arc stood still"
    assert after < 0.5 + (1 - 0.5) * 0.32 + 1e-6, "the drift promised the next step"


def test_the_end_closes_the_circle_and_stops(arc):
    arc._goal = 1.0
    assert run(arc, 3.0) == pytest.approx(1.0, abs=1e-6)
    arc._advance(1 / 60)
    assert arc._pos == pytest.approx(1.0, abs=1e-6)


def test_a_blocked_loop_does_not_teleport_the_arc(arc):
    """A frame that arrives two seconds late is one frame, not two seconds of
    movement: the screen catches up, it does not jump the work."""
    arc._goal = 1.0
    arc._advance(2.0)
    assert arc._pos < 0.3


def test_hiding_closes_the_circle_first(arc):
    """Work ends where it ends. A screen that vanishes with the arc a third
    of the way round reads as a load that was abandoned, so hiding sets the
    goal to the top and the arc gets there inside the time it has."""
    from slantui.shell.splash import BURST_S, CLOSE_MAX

    faded = []
    arc._fade = lambda ms: faded.append(arc._pos)

    arc._goal = 0.3
    run(arc, 2.0)
    arc._closing = (0, arc._elapsed + CLOSE_MAX + BURST_S)
    arc._goal = 1.0
    run(arc, CLOSE_MAX + BURST_S + 0.2)
    assert faded and faded[0] > 0.99, (faded, arc._pos)


def test_the_ring_lets_go_once_at_the_end(arc):
    """The flourish is the difference between a load that finished and a
    screen that was taken away, and it happens once."""
    arc._goal = 1.0
    run(arc, 3.0)
    assert arc._root.props["burst"] == pytest.approx(1.0)
    first = arc._burst
    run(arc, 1.0)
    assert arc._burst == first, "the ring let go twice"


class _Motor:
    def __init__(self):
        self.active = True

    def isActive(self):                          # noqa: N802  (Qt's name)
        return self.active

    def start(self):
        self.active = True

    def stop(self):
        self.active = False


class _Window:
    band_up = True


def _over_a_window(arc):
    arc.window = _Window()
    arc._veil = False
    arc._motor = _Motor()
    return arc


def test_the_handover_waits_for_the_window_band(arc):
    """While the window still draws its own band (band.py), the strip under
    the band's thin half is not the page's to carry across, so the page is
    not uncovered yet. It is as soon as the band is the page's."""
    arc = _over_a_window(arc)
    arc._fade(1600)
    assert arc._held is not None and arc._leaving is None
    run(arc, 0.5)
    assert arc._leaving is None, "the page was uncovered under the window's band"
    arc.window.band_up = False
    arc._advance(1 / 60)
    assert arc._held is None and arc._leaving is not None


def test_a_band_that_never_goes_does_not_hold_the_screen_for_good(arc):
    """A page that never says its band is drawn: the wait has an end."""
    from slantui.shell.splash import BAND_WAIT_S

    arc = _over_a_window(arc)
    arc._fade(1600)
    run(arc, BAND_WAIT_S + 0.1)
    assert arc._leaving is not None


def test_a_second_hide_does_not_cut_the_wait_short(arc):
    """An application that asks twice, from a timeout and from its ready
    signal, must not uncover the page under the window's band the second
    time, nor start the reveal over once it has begun."""
    arc = _over_a_window(arc)
    arc._fade(1600)
    run(arc, 0.2)
    arc._fade(1600)
    assert arc._leaving is None, "the second hide uncovered the page under the window's band"
    arc.window.band_up = False
    arc._advance(1 / 60)
    run(arc, 0.4)
    going = arc._leaving[0]
    arc._fade(1600)
    assert arc._leaving[0] == going, "a hide during the reveal started it over"


def test_a_veil_does_not_wait_for_the_band(arc):
    """Under a veil the page is in sight and its band has long been its own."""
    arc = _over_a_window(arc)
    arc._veil = True
    arc._fade(190)
    assert arc._held is None and arc._leaving is not None


def test_the_bar_travels_whatever_the_arc_does(arc):
    """The bar carries no scale: it says the load is alive, and it says it
    while the arc is standing still at its goal."""
    arc._goal = 0.0
    run(arc, 0.5)
    first = arc._root.props["phase"]
    run(arc, 0.5)
    assert arc._root.props["phase"] != first
