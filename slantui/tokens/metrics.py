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
    "LENGTHS", "FONTS", "TIMES", "NUMBERS", "CURVES", "BAND_METRICS",
    "metric", "value", "px", "ms", "number", "curve", "as_dict",
]


@dataclass(frozen=True)
class Metric:
    name: str
    group: str
    value: str
    purpose: str
    kind: str = "length"              # "length", "font", "time", "number" or "curve"


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

    # -- spacing ------------------------------------------------------------
    Metric("sp-1", "spacing", "4px",
           "Between two controls of one section."),
    Metric("sp-2", "spacing", "8px",
           "Between a control and something that is not one, and the gap "
           "inside a row of controls."),
    Metric("sp-3", "spacing", "12px",
           "Before a section that starts a new subject."),

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
           "library speaking and not the application, so it is set in the "
           "text face of the platform and not in the one the application "
           "reads in.", kind="font"),
    Metric("mono", "type", "Consolas,'Courier New',monospace",
           "Numbers in a column, paths, anything measured.", kind="font"),
    Metric("fs", "type", "12.5px", "Body."),
    Metric("fs-sm", "type", "11.5px", "Captions."),
    Metric("fs-xs", "type", "10px", "Uppercase section labels."),
    Metric("fs-lg", "type", "13.5px", "Panel titles."),
    Metric("fs-brand", "type", "14.5px", "The application's name in the title band."),
    Metric("fs-credit", "type", "11px",
           "The credit line in the title band, which the licence keeps at this size."),
    Metric("ls-brand", "type", ".15px", "The spacing between the letters of the name."),
    Metric("ls-strong", "type", ".4px",
           "The spacing between the letters of the name's strong word, a little wider "
           "because a heavier face closes up."),
    Metric("ls-credit", "type", ".25px", "The spacing between the letters of the credit line."),
    Metric("w", "type", "400", "The weight of text that is not strong.", kind="number"),
    Metric("w-strong", "type", "600",
           "Strong text: a label that heads something, a title, the application's own "
           "word in its name.", kind="number"),
    Metric("lh", "type", "1.45", "The height of a line of text, as a multiple of its size.",
           kind="number"),

    # ── the title band ──────────────────────────────────────────────────────
    Metric("tbar-h", "band", "44px",
           "The thick end, on the left, under the logo and the name."),
    Metric("tbar-thin", "band", "28px",
           "The thin end, on the right, under the window buttons."),
    Metric("tbar-slant", "band", "38px",
           "The horizontal run of the oblique between the two."),
    Metric("tbar-join", "band", "8px",
           "The radius the oblique's two vertices are rounded by."),
    Metric("tbar-mark", "band", "22px", "The mark's square at the start of the band."),
    Metric("tbar-mark-gap", "band", "14px", "Between the mark and the name."),
    Metric("tbar-name-end", "band", "16px",
           "Between the end of the name and the foot of the oblique."),
    Metric("tbar-ring", "band", "4px",
           "How far the round button the mark sits in reaches past the mark, all round."),
    Metric("tbar-lift", "band", "1px", "How far the shadow under that button falls."),
    Metric("tbar-lift-blur", "band", "3px", "How soft that shadow is."),
    Metric("tbar-button", "band", "42px",
           "The width of a window button, at the thin end: minimise, maximise, close."),
    Metric("tbar-glyph", "band", "12px", "The drawing on a window button, square."),
    Metric("tbar-stroke", "band", "1.35",
           "The width of that drawing's strokes, in its own units, which at --tbar-glyph "
           "are pixels.", kind="number"),

    # ── the edges the window is resized from ────────────────────────────────
    Metric("rz", "frame", "5px",
           "How deep the strip along each edge of the window is that resizes it."),
    Metric("rz-corner", "frame", "12px",
           "How far along the edges each corner resizes both ways at once."),

    # ── the step rail under it ──────────────────────────────────────────────
    Metric("tab-h", "rail", "42px", "The height of the rail and of a step tab."),
    Metric("tab-w", "rail", "132px",
           "Every step tab is this wide, so the numbers line up in one column "
           "and the initials in another. They shrink together, never one at a "
           "time, when the window is narrow."),

    # ── the side panel ──────────────────────────────────────────────────────
    Metric("rp-w", "panel", "244px", "The width of the panel down the right."),

    # ── the comb the panel is laid on ───────────────────────────────────────
    Metric("slot", "comb", "32px",
           "The step a panel's controls sit on: one control takes one slot, "
           "or as many whole slots as its ink needs."),
    Metric("block", "comb", "96px",
           "How tall a block of controls is. A block that needs more is two "
           "of these, or three."),

    # ── what opens over the page ────────────────────────────────────────────
    Metric("blur", "overlay", "14px",
           "How far the page behind a veil goes out of focus."),
    Metric("sheet-w", "overlay", "520px",
           "The width of a sheet, the one surface that opens beside a control "
           "to say what that control is for."),
    Metric("sheet-wide", "overlay", "660px",
           "The width of a sheet docked down the side of the work area, the "
           "one that holds a picture and the controls that work on it."),

    # ── motion ──────────────────────────────────────────────────────────────
    Metric("t-in", "motion", "120ms",
           "A control answering the pointer.", kind="time"),
    Metric("t-out", "motion", "180ms",
           "The same control letting go.", kind="time"),
    Metric("t-chg", "motion", "140ms",
           "A state changing on its own: a status dot, a step marked done.",
           kind="time"),
    Metric("t-reveal", "motion", "1600ms",
           "The loading screen handing the window over: the ring leaves and "
           "the page comes into focus.", kind="time"),
    Metric("t-scene", "motion", "850ms",
           "One screen of the window giving way to the next, with something "
           "carried across from the one to the other.", kind="time"),
    Metric("ease-travel", "motion", "cubic-bezier(.65,0,.35,1)",
           "Something going from one place to another: it leaves slowly and "
           "arrives slowly.", kind="curve"),
    Metric("ease-arrive", "motion", "cubic-bezier(.22,1,.36,1)",
           "Something arriving: quick at first, then settling into its place.",
           kind="curve"),
    Metric("ease-leave", "motion", "cubic-bezier(.4,0,1,1)",
           "Something leaving: it gathers speed as it goes and is gone at full "
           "speed.", kind="curve"),
    Metric("ease-resize", "motion", "cubic-bezier(.45,0,.2,1)",
           "The size of something travelling: it changes ahead of the travel, "
           "so the thing lands already the size it will be.", kind="curve"),
)

# What each group is, for the comment the stylesheet carries over it.
GROUPS: dict[str, str] = {
    "radius": "radii, on one scale: 4 inputs, 5 buttons, 6 cards, 7 panels",
    "spacing": "spacing, on one scale: 0, 4, 8, 12",
    "type": "type",
    "band": "the title band",
    "frame": "the edges the window is resized from",
    "rail": "the step rail under it",
    "panel": "the side panel",
    "comb": "the comb the panel is laid on",
    "overlay": "what opens over the page",
    "motion": "motion. One material, three durations, a handover, a scene and four curves",
}

# A note printed above a group where the numbers need the picture.
GROUP_NOTES: dict[str, str] = {
    "spacing": (
        "Four steps and no others, counting the zero: nothing, a sibling, a\n"
        "neighbour, a new subject. A panel that needs a fifth is a panel whose\n"
        "grouping is wrong, and the way to mend it is a section, not a number.\n"
        "An application that reads these draws a panel spaced like every other\n"
        "panel by construction, and not by review."
    ),
    "motion": (
        "A control answers the pointer faster than it lets go, which is what\n"
        "makes it feel like a thing and not a slide. The rule the components\n"
        "keep: everything transitions over --t-out, and the :hover state\n"
        "overrides the duration to --t-in. --t-reveal is ten times longer on\n"
        "purpose: it is the one moment the whole window changes at once, the\n"
        "loading screen going and the page arriving in focus, and a change\n"
        "that large read in two hundred milliseconds reads as a cut.\n"
        "--t-scene sits between the two: one screen giving way to the next\n"
        "while something is carried across, which is long enough for the eye\n"
        "to follow the thing that travels and short enough not to wait for it.\n"
        "Every delay inside such a scene is a fraction of it, so a scene made\n"
        "longer or shorter keeps its order. The four curves are the four ways\n"
        "a thing moves in it: it travels, it arrives, it leaves, or it changes\n"
        "size on the way."
    ),
    "overlay": (
        "One blur and two widths. The blur is the loading screen's, which is\n"
        "the one thing that does put the page out of focus, because until it\n"
        "goes there is nothing behind it to look at: shell/splash.py takes\n"
        "--blur from here, and the screen drawn in WPF takes it from the same\n"
        "place. A sheet veils nothing and blurs nothing. It opens beside the\n"
        "control it is about, at --sheet-w, or docked down the side of the\n"
        "work area at --sheet-wide."
    ),
    "comb": (
        "A panel is a column of slots, and a control does not pick where it\n"
        "sits: it sits in a slot, centred, and it is never made shorter to fit.\n"
        "The tallest control that cannot be shortened is 28.68px, so 32 is the\n"
        "smallest step that holds every one of them with air left around it,\n"
        "and it is four times --sp-2. A block is three slots because that is\n"
        "what the sections of a real application asked for: six in ten fit in\n"
        "one, and the rest fit in exactly two or three. The top of every block\n"
        "falls on a multiple of --block FROM THE TOP OF THE COLUMN, which is at\n"
        "the same height on every page because the head above it is always one\n"
        "block tall. So the teeth are in the same places on every page, and a\n"
        "block taken off one page and dropped on another lands exactly on a\n"
        "block; only what is written in them changes."
    ),
    "band": (
        "The band runs the whole width of the window. Its lower profile,\n"
        "measured down from the window's top edge, is --tbar-h on the left\n"
        "(where the logo and the name are), then a straight oblique run of\n"
        "--tbar-slant, then --tbar-thin all the way to the right edge (where\n"
        "the window buttons are). The two vertices of that run are rounded by\n"
        "--tbar-join. slantui/geometry.py turns these four into the profile,\n"
        "and js/titlebar.js cuts the band to it. The rest are what sits on it:\n"
        "the mark, the round button it becomes, the room after the name and the\n"
        "window buttons. The window draws the same band itself until the page\n"
        "has drawn its own (shell/band.py), and WPF draws it for good, both from\n"
        "these and not from numbers of their own."
    ),
}

METRIC_NAMES: tuple[str, ...] = tuple(m.name for m in METRICS)
LENGTHS: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "length")
FONTS: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "font")
TIMES: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "time")
NUMBERS: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "number")
CURVES: tuple[str, ...] = tuple(m.name for m in METRICS if m.kind == "curve")

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


def number(name: str) -> float:
    """A plain number, as a number: a weight, a line height, a stroke."""
    m = _BY_NAME[name]
    if m.kind != "number":
        raise TypeError(f"{name} is a {m.kind}, not a plain number: {m.value!r}")
    return float(m.value)


def curve(name: str) -> tuple[float, float, float, float]:
    """A curve as its four numbers, the two control points of a cubic Bezier
    from (0, 0) to (1, 1): what a storyboard or a timer outside a browser
    wants, since only a browser reads ``cubic-bezier()``."""
    m = _BY_NAME[name]
    if m.kind != "curve":
        raise TypeError(f"{name} is a {m.kind}, not a curve: {m.value!r}")
    inside = m.value.strip()
    if not (inside.startswith("cubic-bezier(") and inside.endswith(")")):
        raise ValueError(f"{name} is not written as cubic-bezier(): {m.value!r}")
    x1, y1, x2, y2 = (float(v) for v in inside[len("cubic-bezier("):-1].split(","))
    return x1, y1, x2, y2


def as_dict() -> dict[str, str]:
    """``{"r-xs": "4px", ...}`` in the canonical order."""
    return {m.name: m.value for m in METRICS}
