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

The window's own top left corner is the band's too, and it is round about the
mark. The mark's button is a disc of radius 15 whose centre sits half the thick
end in from the left and half the thick end down, so a corner of radius
``height / 2`` is concentric with it: the same 7 pixels of band between the
disc and the edge of the window all the way round the arc. That radius is
:attr:`BandShape.corner`. The corner is a true arc, not the quadratic the
oblique's joints are rounded with, because a quadratic drifts almost a pixel
off the circle at 45 degrees and the ring round the mark would show it.

Whether the corner is cut is the window's business, so the caller passes it:
a window that can cut its corner passes ``shape.corner``, and a maximised
one, or one whose compositor rounds every corner the same, passes nothing.

    from slantui.geometry import band_path, band_shape

    band_path(width=1280, brand_width=210)
    band_path(width=1280, brand_width=210, corner=band_shape().corner)

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
    """A vertex of the profile. ``r`` is the radius its corner is rounded by
    with a quadratic, ``a`` the radius of a true circular arc cut into it
    instead. A vertex carries one or the other."""
    x: float
    y: float
    r: float = 0.0
    a: float = 0.0


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
    def corner(self) -> float:
        """The radius of the window's top left corner: half the thick end.

        Not a fifth number. The mark's disc is centred half the thick end in
        and half the thick end down, so this is the one radius whose arc is
        concentric with it, and a band drawn at another height keeps the mark
        on the centre of its own corner.
        """
        return self.height / 2

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
                shape: BandShape | None = None, corner: float = 0.0) -> list[Point]:
    """The six vertices of the band, clockwise from the top left corner.

    ``width`` is the window's width and ``brand_width`` is where the name
    ends. The oblique is clamped to the right edge, so a window narrow enough
    to run out of room keeps a band and simply has less room to thin out in.
    ``corner`` is the radius the window's top left corner is cut to, and 0
    leaves it square (see the note at the top).
    """
    s = shape or band_shape()
    x1 = float(brand_width)
    x2 = min(float(width), x1 + s.slant)
    return [
        Point(0.0, 0.0, a=float(corner)),      # the window's top left corner
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
    """A closed path through the points, each corner rounded by its own ``r``
    or cut by its own arc ``a``.

    ``r`` makes a quadratic whose control point is the vertex itself, trimmed
    to half the shorter of the two sides so a small edge between two rounded
    corners cannot be eaten twice. ``a`` makes a circular arc tangent to both
    sides, trimmed the same way: where it would need more than half a side,
    the radius shrinks until it fits. This is the same construction as
    ``roundedPolyPath`` in ``js/titlebar.js``, and a test runs that one in V8
    against this one.
    """
    n = len(points)
    out: list[str] = []
    for i, cur in enumerate(points):
        prev, nxt = points[(i - 1) % n], points[(i + 1) % n]
        head = "M" if i == 0 else "L"
        if cur.r <= 0 and cur.a <= 0:
            out.append(f"{head}{fmt(cur.x)},{fmt(cur.y)} ")
            continue
        v1x, v1y = prev.x - cur.x, prev.y - cur.y
        v2x, v2y = nxt.x - cur.x, nxt.y - cur.y
        l1 = math.hypot(v1x, v1y) or 1.0
        l2 = math.hypot(v2x, v2y) or 1.0
        if cur.a > 0:
            # The two tangent points sit a / tan(half the angle) from the
            # vertex; clockwise on screen, where y grows down, is sweep 1.
            cos = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (l1 * l2)))
            t = math.tan(math.acos(cos) / 2) or 1.0
            d = min(cur.a / t, l1 / 2, l2 / 2)
            p1x, p1y = cur.x + v1x / l1 * d, cur.y + v1y / l1 * d
            p2x, p2y = cur.x + v2x / l2 * d, cur.y + v2y / l2 * d
            sweep = 1 if v1y * v2x - v1x * v2y > 0 else 0
            out.append(f"{head}{fmt(p1x)},{fmt(p1y)} ")
            out.append(f"A{fmt(d * t)},{fmt(d * t)} 0 0 {sweep} {fmt(p2x)},{fmt(p2y)} ")
            continue
        a, b = min(cur.r, l1 / 2), min(cur.r, l2 / 2)
        p1x, p1y = cur.x + v1x / l1 * a, cur.y + v1y / l1 * a
        p2x, p2y = cur.x + v2x / l2 * b, cur.y + v2y / l2 * b
        out.append(f"{head}{fmt(p1x)},{fmt(p1y)} ")
        out.append(f"Q{fmt(cur.x)},{fmt(cur.y)} {fmt(p2x)},{fmt(p2y)} ")
    return "".join(out) + "Z"


def band_path(width: float, brand_width: float,
              shape: BandShape | None = None, corner: float = 0.0) -> str:
    """The band as one path string, for a clip path or for ``Geometry.Parse``.
    ``corner`` is the radius of the window's own top left corner, or 0."""
    return rounded_poly_path(band_points(width, brand_width, shape, corner))
