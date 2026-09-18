"""The shape of the title band, as maths instead of as a stylesheet.

The band is the one thing in SlantUI that is a drawing and not a rectangle,
and it is the part of the design that travels furthest: the page clips it out
of a div, a WPF window draws it as geometry, and anything else that
wants the look has to draw it too. Until now the profile lived in
``js/titlebar.js`` and anyone outside the browser had to work it out again
from a picture.

So the profile is here, in the one language every target can be generated
from. The output is a path in the SVG mini language, which the browser takes
through ``clip-path: path()`` and which WPF takes through ``Geometry.Parse``
without a character changing. One set of numbers, two renderers, and a test
that runs the JavaScript against this file so the two cannot drift.

The profile, measured down from the top edge of the window::

    0                        x1        x2                          W
    +------------------------------------------------------------+  0
    |                          \\                                  |
    |                            \\_____________________________   |  thin
    |                                                            |
    +--------------------------+                                 |  height
      thick, under the name      the oblique   thin, under the buttons

``x1`` is where the application's name ends, which is why the caller passes
it: it is a fact about the laid out page, not a constant.

    from slantui.geometry import band_path

    band_path(width=1280, brand_width=210)

"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .tokens.metrics import px

_CENTS = Decimal("0.01")

__all__ = ["Point", "BandShape", "band_shape", "band_points", "band_path",
           "rounded_poly_path", "fmt"]


@dataclass(frozen=True)
class Point:
    """A vertex of the profile. ``r`` is the radius its corner is rounded by."""
    x: float
    y: float
    r: float = 0.0


@dataclass(frozen=True)
class BandShape:
    """The four numbers the profile is built from, in pixels."""
    height: float                     # the thick end, on the left
    thin: float                       # the thin end, on the right
    slant: float                      # the horizontal run of the oblique
    join: float                       # the radius on the oblique's vertices

    @property
    def drop(self) -> float:
        """How far the band thins over the run of the oblique."""
        return self.height - self.thin

    @property
    def angle(self) -> float:
        """The oblique's angle from the horizontal, in degrees.

        A toolkit that draws the band as a rotated edge instead of a path
        wants this, and so does anyone matching the look by hand.
        """
        return math.degrees(math.atan2(self.drop, self.slant))


def band_shape(height: float | None = None, thin: float | None = None,
               slant: float | None = None, join: float | None = None) -> BandShape:
    """The shipped band, with any of the four numbers replaced.

    An application that redefines ``--tbar-h`` in its own stylesheet passes
    the same number here, and every target draws the band it actually has.
    """
    return BandShape(
        height=px("tbar-h") if height is None else float(height),
        thin=px("tbar-thin") if thin is None else float(thin),
        slant=px("tbar-slant") if slant is None else float(slant),
        join=px("tbar-join") if join is None else float(join),
    )


def band_points(width: float, brand_width: float,
                shape: BandShape | None = None) -> list[Point]:
    """The six vertices of the band, clockwise from the top left corner.

    ``width`` is the window's width and ``brand_width`` is where the name
    ends. The oblique is clamped to the right edge, so a window narrow enough
    to run out of room keeps a band and simply has less room to thin out in.
    """
    s = shape or band_shape()
    x1 = float(brand_width)
    x2 = min(float(width), x1 + s.slant)
    return [
        Point(0.0, 0.0),                       # the window's top left corner
        Point(float(width), 0.0),              # its top right corner
        Point(float(width), s.thin),           # the thin end, at the right edge
        Point(x2, s.thin, s.join),             # the top of the oblique
        Point(x1, s.height, s.join),           # the foot of the oblique
        Point(0.0, s.height),                  # back to the left edge
    ]


def fmt(v: float) -> str:
    """A coordinate, to two places, exactly as the browser writes it.

    ``Number.prototype.toFixed`` picks the two place number closest to the
    value the double actually holds, and takes the larger one on a tie. Two
    shortcuts look like that and are not. Python's own format rounds a tie to
    even, so 0.125 comes out 0.12 where the browser says 0.13. Multiplying by
    a hundred first is worse: 2.675 is really 2.67499999999999982, but the
    product rounds up to exactly 267.5 on the way, and the answer comes out
    2.68 where the browser says 2.67.

    Decimal sees the double for what it is, so neither happens. It costs a
    little, and nothing here is in a render loop: the page has its own copy
    of this in JavaScript, and this one writes files.
    """
    d = Decimal(float(v)).quantize(_CENTS, rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)                    # a negative zero prints as -0.00
    return str(d)


def rounded_poly_path(points: list[Point]) -> str:
    """A closed path through the points, each corner rounded by its own ``r``.

    The corner is a quadratic whose control point is the vertex itself,
    trimmed to half the shorter of the two sides so a small edge between two
    rounded corners cannot be eaten twice. This is the same construction as
    ``roundedPolyPath`` in ``js/titlebar.js``, and a test runs that one in V8
    against this one.
    """
    n = len(points)
    out: list[str] = []
    for i, cur in enumerate(points):
        prev, nxt = points[(i - 1) % n], points[(i + 1) % n]
        head = "M" if i == 0 else "L"
        if cur.r <= 0:
            out.append(f"{head}{fmt(cur.x)},{fmt(cur.y)} ")
            continue
        v1x, v1y = prev.x - cur.x, prev.y - cur.y
        v2x, v2y = nxt.x - cur.x, nxt.y - cur.y
        l1 = math.hypot(v1x, v1y) or 1.0
        l2 = math.hypot(v2x, v2y) or 1.0
        a, b = min(cur.r, l1 / 2), min(cur.r, l2 / 2)
        p1x, p1y = cur.x + v1x / l1 * a, cur.y + v1y / l1 * a
        p2x, p2y = cur.x + v2x / l2 * b, cur.y + v2y / l2 * b
        out.append(f"{head}{fmt(p1x)},{fmt(p1y)} ")
        out.append(f"Q{fmt(cur.x)},{fmt(cur.y)} {fmt(p2x)},{fmt(p2y)} ")
    return "".join(out) + "Z"


def band_path(width: float, brand_width: float,
              shape: BandShape | None = None) -> str:
    """The band as one path string, for a clip path or for ``Geometry.Parse``."""
    return rounded_poly_path(band_points(width, brand_width, shape))
