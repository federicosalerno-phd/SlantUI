"""The metric layer: the lengths and the fonts, on the Python side.

Colour is one half of the design and shape is the other. A palette says what
a surface is filled with; a metric says how tall the band is, how far the
taper runs, how round a card's corner is, and which font the name in the
title bar is set in. They are the same on every palette, which is why they
were left in a hand written stylesheet until now.

Phase 2 wrote down what would move them here: "if phase 3 or phase 5 needs a
metric on the Python side, it reads the file with a one line regex, and only
then is it worth moving them into Python and generating the CSS." Phase 8 is
where that happens. A toolkit that is not a browser cannot read
``metrics.css``, and the band's profile is four of these numbers, so anything
that draws the band outside the page needs them as data. WPF needs them,
Unity's UI Toolkit needs them, and so does the installer that already draws
the band in WPF geometry.

So the metrics live here, ``slantui/css/metrics.css`` is written from them,
and every other target is written from them too.

    from slantui.tokens.metrics import METRICS, px, value

    px("tbar-h")          44.0
    value("font-brand")   "'Abadi', ... ,system-ui,sans-serif"
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Metric", "METRICS", "METRIC_NAMES", "GROUPS", "GROUP_NOTES",
    "LENGTHS", "FONTS", "TIMES", "BAND_METRICS",
    "metric", "value", "px", "ms", "as_dict",
]


@dataclass(frozen=True)
class Metric:
    name: str
    group: str
    value: str
    purpose: str
    kind: str = "length"              # "length", "font" or "time"


# The order is the order the stylesheet is written in, and the order every
# other target follows, so two exports of the same palette can be read side
# by side.
METRICS: tuple[Metric, ...] = (
    # ── radii ───────────────────────────────────────────────────────────────
    Metric("r-xs", "radius", "4px", "A field you type or pick into."),
    Metric("r", "radius", "5px", "Anything you press: buttons, tabs, chips, rows."),
    Metric("r-md", "radius", "6px", "A raised card, or a plate over the stage."),
    Metric("r-lg", "radius", "7px", "A framed pane, a dialog, an image."),
    Metric("r-pill", "radius", "99px", "A pill: any height, fully round ends."),

    # ── type ────────────────────────────────────────────────────────────────
    Metric("font", "type", "'Segoe UI',system-ui,-apple-system,sans-serif",
           "Every piece of text but the application name.", kind="font"),
    Metric("font-brand", "type",
           "'Abadi','Abadi MT Std','Segoe UI Variable Display','Selawik',"
           "'Segoe UI',system-ui,sans-serif",
           "The application name in the title bar, and nothing else. A modern "
           "humanist sans if the machine has one, Segoe UI Variable next on "
           "Windows 11, plain Segoe UI last.", kind="font"),
    Metric("font-credit", "type",
           "'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif",
           "The credit line the licence asks for, and nothing else. It is the "
           "library speaking rather than the application, so it is set in the "
           "text face of the platform rather than in the one the application "
           "reads in.", kind="font"),
    Metric("mono", "type", "Consolas,'Courier New',monospace",
           "Numbers in a column, paths, anything measured.", kind="font"),
    Metric("fs", "type", "12.5px", "Body."),
    Metric("fs-sm", "type", "11.5px", "Captions."),
    Metric("fs-xs", "type", "10px", "Uppercase section labels."),
    Metric("fs-lg", "type", "13.5px", "Panel titles."),

    # ── the title band ──────────────────────────────────────────────────────
    Metric("tbar-h", "band", "44px",
           "The thick end, on the left, under the logo and the name."),
    Metric("tbar-thin", "band", "28px",
           "The thin end, on the right, under the window buttons."),
    Metric("tbar-slant", "band", "38px",
           "The horizontal run of the oblique between the two."),
    Metric("tbar-join", "band", "8px",
           "The radius the oblique's two vertices are rounded by."),

    # ── the step rail under it ──────────────────────────────────────────────
    Metric("tab-h", "rail", "42px", "The height of the rail and of a step tab."),
    Metric("tab-w", "rail", "132px",
           "Every step tab is this wide, so the numbers line up in one column "
           "and the initials in another. They shrink together, never one at a "
           "time, when the window is narrow."),

    # ── the side panel ──────────────────────────────────────────────────────
    Metric("rp-w", "panel", "244px", "The width of the panel down the right."),

    # ── motion ──────────────────────────────────────────────────────────────
    Metric("t-in", "motion", "120ms",
           "A control answering the pointer.", kind="time"),
    Metric("t-out", "motion", "180ms",
           "The same control letting go.", kind="time"),
    Metric("t-chg", "motion", "140ms",
           "A state changing on its own: a status dot, a step marked done.",
           kind="time"),
)

# What each group is, for the comment the stylesheet carries over it.
GROUPS: dict[str, str] = {
    "radius": "radii, on one scale: 4 inputs, 5 buttons, 6 cards, 7 panels",
    "type": "type",
    "band": "the title band",
    "rail": "the step rail under it",
    "panel": "the side panel",
    "motion": "motion. One material, three durations",
}

# A note printed above a group where the numbers need the picture.
GROUP_NOTES: dict[str, str] = {
    "motion": (
        "A control answers the pointer faster than it lets go, which is what\n"
        "makes it feel like a thing and not a slide. The rule the components\n"
        "keep: everything transitions over --t-out, and the :hover state\n"
        "overrides the duration to --t-in."
    ),
    "band": (
        "The band runs the whole width of the window. Its lower profile,\n"
        "measured down from the window's top edge, is --tbar-h on the left\n"
        "(where the logo and the name are), then a straight oblique run of\n"
        "--tbar-slant, then --tbar-thin all the way to the right edge (where\n"
        "the window buttons are). The two vertices of that run are rounded by\n"
        "--tbar-join. slantui/geometry.py turns these four into the profile,\n"
        "and js/titlebar.js cuts the band to it."
    ),
}

METRIC_NAMES: tuple[str, ...] = tuple(m.name for m in METRICS)
LENGTHS: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "length")
FONTS: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "font")
TIMES: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "time")

# The four the band's profile is built from, in the order geometry.py wants.
BAND_METRICS: tuple[str, ...] = ("tbar-h", "tbar-thin", "tbar-slant", "tbar-join")

_BY_NAME = {m.name: m for m in METRICS}


def metric(name: str) -> Metric:
    """One metric by name, with no leading dashes."""
    return _BY_NAME[name]


def value(name: str) -> str:
    """The metric's value exactly as the stylesheet writes it."""
    return _BY_NAME[name].value


def px(name: str) -> float:
    """A length in pixels, as a number.

    Anything that draws the design outside a browser wants the number and not
    the string. A font stack has no number and asking for one is a mistake
    worth hearing about.
    """
    m = _BY_NAME[name]
    if m.kind != "length":
        raise TypeError(f"{name} is a {m.kind}, not a length: {m.value!r}")
    if not m.value.endswith("px"):
        raise ValueError(f"{name} is not written in pixels: {m.value!r}")
    return float(m.value[:-2])


def ms(name: str) -> float:
    """A duration in milliseconds, as a number."""
    m = _BY_NAME[name]
    if m.kind != "time":
        raise TypeError(f"{name} is a {m.kind}, not a duration: {m.value!r}")
    if not m.value.endswith("ms"):
        raise ValueError(f"{name} is not written in milliseconds: {m.value!r}")
    return float(m.value[:-2])


def as_dict() -> dict[str, str]:
    """``{"r-xs": "4px", ...}`` in the canonical order."""
    return {m.name: m.value for m in METRICS}
