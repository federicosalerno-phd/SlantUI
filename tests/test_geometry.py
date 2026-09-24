"""The band's profile: the maths, and the browser agreeing with it.

The profile used to live only in js/titlebar.js, so a toolkit that is not a
browser had to work it out from a picture. It lives in slantui/geometry.py
now, and the test that matters here is the last one: the JavaScript that
actually clips the band, run in V8, against the Python every other target is
written from. If those two ever disagree, a WPF window and a page drawn from
the same numbers stop looking alike.
"""
from __future__ import annotations

import math
import re

import pytest

from slantui.geometry import (BandShape, Point, band_path, band_points,
                              band_shape, fmt, rounded_poly_path)
from slantui.js import path as jspath
from slantui.tokens.metrics import px

# A spread of windows: the shipped size, a narrow one, a wide one, a fractional
# brand width, and two where the oblique runs out of room at the right edge.
CASES = ((1280, 210), (1024, 187.4), (2480, 333.333), (640, 620), (300, 296),
         (1440, 0), (900, 12.5))


def test_the_shape_is_the_metrics():
    s = band_shape()
    assert (s.height, s.thin, s.slant, s.join) == (
        px("tbar-h"), px("tbar-thin"), px("tbar-slant"), px("tbar-join"))


def test_the_drop_and_the_angle():
    s = band_shape()
    assert s.drop == s.height - s.thin
    assert math.isclose(s.angle, math.degrees(math.atan2(s.drop, s.slant)))


def test_an_application_can_change_any_of_the_four():
    s = band_shape(height=60, join=0)
    assert (s.height, s.join) == (60.0, 0.0)
    assert s.thin == px("tbar-thin")


@pytest.mark.parametrize("width,brand", CASES)
def test_six_points_in_the_right_places(width, brand):
    s = band_shape()
    pts = band_points(width, brand, s)
    assert len(pts) == 6
    assert (pts[0].x, pts[0].y) == (0.0, 0.0)
    assert (pts[1].x, pts[1].y) == (float(width), 0.0)
    assert pts[2].y == s.thin and pts[2].x == float(width)
    assert pts[3].y == s.thin and pts[3].r == s.join
    assert pts[4].y == s.height and pts[4].r == s.join
    assert (pts[5].x, pts[5].y) == (0.0, s.height)


@pytest.mark.parametrize("width,brand", CASES)
def test_the_oblique_never_leaves_the_window(width, brand):
    """A window too narrow to fit the run keeps a band. It just has less
    room to thin out in."""
    pts = band_points(width, brand, band_shape())
    assert pts[3].x <= float(width)
    assert pts[4].x <= pts[3].x


def test_a_corner_with_no_radius_is_a_line():
    d = rounded_poly_path([Point(0, 0), Point(10, 0), Point(10, 10)])
    assert "Q" not in d
    assert d.endswith("Z")


def test_a_corner_with_a_radius_is_a_quadratic_through_the_vertex():
    d = rounded_poly_path([Point(0, 0), Point(10, 0, 2), Point(10, 10)])
    assert "Q10.00,0.00" in d


def test_the_radius_never_eats_more_than_half_a_side():
    """Two rounded corners two units apart would each want four, and the
    edge between them would be drawn twice."""
    d = rounded_poly_path([Point(0, 0), Point(2, 0, 9), Point(2, 2, 9), Point(0, 2)])
    xs = [float(v) for v in re.findall(r"[-\d.]+(?=,)", d)]
    assert max(xs) <= 2.0


def test_coordinates_carry_two_places():
    assert fmt(0) == "0.00"
    assert fmt(-0.0) == "0.00"           # never -0.00
    assert fmt(1) == "1.00"
    assert fmt(2.344) == "2.34"
    assert fmt(1280) == "1280.00"


def test_a_real_tie_goes_away_from_zero():
    """0.125 is a tie a double can hold exactly, so this one is decided by
    the rule and not by the binary."""
    assert fmt(0.125) == "0.13"
    assert fmt(-0.125) == "-0.13"


@pytest.mark.parametrize("value,want", [(1.005, "1.00"), (2.675, "2.67"),
                                        (1.115, "1.11"), (0.005, "0.01")])
def test_a_tie_that_is_not_one_is_not_treated_as_one(value, want):
    """Three of these sit just under the halfway mark and one just over.
    1.005 is really 1.00499999999999989 and 2.675 is really
    2.67499999999999982, so both round down, and a shortcut that multiplies
    by a hundred first turns the second one into a tie and answers 2.68.
    0.005 is really 0.005000000000000000104, which does round up."""
    assert fmt(value) == want


def test_the_path_starts_at_the_corner_and_closes():
    d = band_path(1280, 210)
    assert d.startswith("M0.00,0.00 ")
    assert d.endswith("Z")


def test_a_taller_band_draws_a_taller_band():
    tall = band_path(1000, 200, BandShape(height=60, thin=28, slant=38, join=8))
    assert "60.00" in tall and "44.00" not in tall


# ── the browser, run against the Python ─────────────────────────────────────
racer = pytest.importorskip("py_mini_racer")


def _js_rounded_poly_path():
    """roundedPolyPath out of titlebar.js, in a bare V8 with no DOM."""
    src = jspath("titlebar.js").read_text(encoding="utf-8")
    start = src.index("function roundedPolyPath")
    end = src.index("/* Cut the band")
    ctx = racer.MiniRacer()
    ctx.eval(src[start:end])
    return ctx


@pytest.mark.parametrize("width,brand", CASES)
def test_the_browser_draws_the_same_path(width, brand):
    ctx = _js_rounded_poly_path()
    pts = band_points(width, brand, band_shape())
    js = ctx.call("roundedPolyPath",
                  [{"x": p.x, "y": p.y, "r": p.r} for p in pts])
    assert js == band_path(width, brand), (
        "slantui/geometry.py and js/titlebar.js no longer draw the same band")


def test_the_browser_builds_the_same_six_points():
    """The points are built in shapeTitleBar, which needs a DOM, so the
    numbers it would use are checked here instead: the metrics, and a brand
    width the caller measures."""
    src = jspath("titlebar.js").read_text(encoding="utf-8")
    for name, default in (("--tbar-thin", 28), ("--tbar-slant", 38),
                          ("--tbar-join", 8)):
        assert f"num('{name}', {default:g})" in src, name
        assert px(name[2:]) == default, name
