"""The first window: the loading screen drawn by a painter, which has to be the
splash it hands over to, to the pixel and to the millisecond.

The numbers are read out of splash.py and splash.qml themselves, so a ring
made larger there and not here fails here. The module has to stay cheap: it is
the first thing an application shows, so importing it must not import the
browser or QtQuick (slantui.shell), nor the tokens.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "slantui" / "shell"
SPLASH_PY = (SHELL / "splash.py").read_text(encoding="utf-8")
SPLASH_QML = (SHELL / "splash.qml").read_text(encoding="utf-8")


def _number(text: str, name: str) -> float:
    m = re.search(rf"^{name}\s*=\s*([0-9.]+)", text, re.MULTILINE)
    assert m, name
    return float(m.group(1))


def test_the_motion_is_the_splash_s():
    from slantui import firstwindow
    for name in ("RING", "SPIN_MS", "SWEEP_MS"):
        assert getattr(firstwindow, name) == _number(SPLASH_PY, name), name


def test_the_column_is_the_splash_s():
    """splash.py hands these to splash.qml; the painter has them as constants."""
    from slantui import firstwindow
    for qml, ours in (("figureGap", "FIGURE_GAP"), ("barGap", "BAR_GAP"), ("barHeight", "BAR_HEIGHT")):
        m = re.search(rf'"{qml}",\s*([0-9.]+)', SPLASH_PY)
        assert m and float(m.group(1)) == getattr(firstwindow, ours), qml


def test_importing_it_loads_neither_the_shell_nor_the_tokens():
    code = ("import sys; import slantui.firstwindow; "
            "print(any(m.startswith('slantui.shell') or m.startswith('slantui.tokens') for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_the_look_is_plain_values_of_the_palette():
    from slantui import firstwindow
    from slantui.tokens import PALETTES
    lk = firstwindow.look("gold-dark")
    assert lk["surface"] == PALETTES["gold-dark"]["surface-0"]
    assert lk["accent"] == PALETTES["gold-dark"]["accent"]
    assert all(isinstance(v, (str, float, int)) for v in lk.values())


_KEPT = []      # the application and its windows live to the end of the session: Qt dies of the other order


@pytest.fixture(scope="module")
def offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from slantui import firstwindow
    _KEPT.append(firstwindow.application())
    return _KEPT[0]


def test_it_draws_the_empty_window_under_the_band(offscreen):
    from PyQt6.QtGui import QColor, QImage
    from slantui import firstwindow
    band = QImage(640, 44, QImage.Format.Format_RGB32)
    band.fill(QColor("#336699"))
    lk = firstwindow.look("gold-dark")
    w = firstwindow.FirstWindow(look=lk, band=band, size=(640, 480), text="starting")
    _KEPT.append(w)
    w.resize(640, 480)
    img = w.grab().toImage()
    assert img.pixelColor(300, 10).name() == "#336699"
    assert img.pixelColor(20, 300).name().lower() == lk["surface"].lower()


def test_a_band_of_another_width_is_left_out(offscreen):
    from PyQt6.QtGui import QColor, QImage
    from slantui import firstwindow
    band = QImage(900, 44, QImage.Format.Format_RGB32)
    band.fill(QColor("#336699"))
    lk = firstwindow.look("gold-dark")
    w = firstwindow.FirstWindow(look=lk, band=band, size=(640, 480))
    _KEPT.append(w)
    w.resize(640, 480)
    assert w.grab().toImage().pixelColor(300, 10).name().lower() == lk["surface"].lower()


def test_a_splash_taking_over_carries_on_the_turn(offscreen):
    """Splash(since=) starts its clock where the first window's is."""
    assert "since: float | None = None" in SPLASH_PY
    assert "time.time() - since" in SPLASH_PY
    from slantui import firstwindow
    w = firstwindow.FirstWindow(look=firstwindow.look(), size=(320, 240))
    _KEPT.append(w)
    assert abs(w.since - time.time()) < 5


def test_the_first_frame_as_a_picture_is_the_window_s_first_frame(offscreen):
    """picture() is what a start shows before it has a toolkit: the band, the
    empty window, the ring at the start of its turn, at the scale asked for."""
    from PyQt6.QtGui import QColor, QImage
    from slantui import firstwindow
    band = QImage(960, 66, QImage.Format.Format_RGB32)
    band.fill(QColor("#336699"))
    lk = firstwindow.look("gold-dark")
    w = firstwindow.FirstWindow(look=lk, band=[band], size=(640, 480))
    _KEPT.append(w)
    w.resize(640, 480)
    img = w.picture(1.5)
    assert (img.width(), img.height()) == (960, 720)
    assert img.pixelColor(450, 10).name() == "#336699"
    assert img.pixelColor(30, 600).name().lower() == lk["surface"].lower()


def test_pictures_given_late_are_drawn(offscreen):
    from PyQt6.QtGui import QColor, QImage
    from slantui import firstwindow
    lk = firstwindow.look("gold-dark")
    w = firstwindow.FirstWindow(look=lk, size=(640, 480))
    _KEPT.append(w)
    w.resize(640, 480)
    assert w.grab().toImage().pixelColor(300, 10).name().lower() == lk["surface"].lower()
    band = QImage(640, 44, QImage.Format.Format_RGB32)
    band.fill(QColor("#336699"))
    w.set_pictures(band=band)
    assert w.grab().toImage().pixelColor(300, 10).name() == "#336699"
