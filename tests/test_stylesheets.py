"""The stylesheets: on the roles, on the metrics, and on nothing else.

A stylesheet may read a role, a metric, or one local property with a fallback
next to it, and may write no colour of its own. Two of the five are written by
the Python and have to match it: palettes.css since phase 1, metrics.css since
phase 8, when the lengths moved into Python so a toolkit that is not a browser
could have them too.
"""
from __future__ import annotations

import re

import pytest

from slantui.css import STYLESHEETS, bundle, path
from slantui.tokens import DEFAULT, PALETTES
from slantui.tokens.css import metrics_stylesheet, stylesheet
from slantui.tokens.metrics import METRIC_NAMES
from slantui.tokens.roles import ROLE_NAMES

# Every stylesheet that may not write a colour of its own. palettes.css is
# the one that writes them all, and is left out.
NO_COLOUR = ("metrics.css", "base.css", "layout.css", "components.css")
# The three hand written ones, which are the ones that read the vocabulary.
ROLE_READERS = ("base.css", "layout.css", "components.css")
# Written by python -m slantui.tokens, and checked against it below.
GENERATED = ("palettes.css", "metrics.css")

# Properties a page sets on an element for a rule to pick up, always with a
# fallback in the rule. --gc is the group colour a metric row carries; --k and
# --bk are counts, how many slots a control asked for and how many sizes its
# block grew to, which is how the comb keeps every length in the metrics.
LOCAL = {"gc", "k", "bk"}

# Borders that are not dividers: the spinner's ring, and the transparent
# border that insets the side panel's scrollbar thumb.
ALLOWED_BORDERS = ("border:2px solid var(--control)", "border:3px solid transparent")

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_VAR = re.compile(r"var\(--([a-z0-9-]+)(,)?")
_DEF = re.compile(r"--([a-z0-9-]+)\s*:")
# A property the stylesheet registers itself, with a type and a starting
# value, so that the page can move it frame by frame (layout.css says why).
# Its starting value is its fallback, and it needs no other.
_REGISTERED = re.compile(r"@property\s+--([a-z0-9-]+)")


def _source(name: str) -> str:
    return path(name).read_text(encoding="utf-8")


def _code(name: str) -> str:
    """The stylesheet with its comments blanked, line numbers kept."""
    return _COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), _source(name))


def _lines(name: str):
    return enumerate(_code(name).splitlines(), start=1)


def _metrics() -> set[str]:
    return set(_DEF.findall(_code("metrics.css")))


def test_the_metric_names_are_the_python_ones():
    assert _metrics() == set(METRIC_NAMES)


# ── the files ───────────────────────────────────────────────────────────────
def test_every_stylesheet_exists():
    for name in STYLESHEETS:
        assert path(name).is_file(), name


def test_palettes_css_is_what_the_python_says():
    want = stylesheet(list(PALETTES.values()), DEFAULT.slug)
    assert _source("palettes.css") == want, (
        "slantui/css/palettes.css is behind slantui/tokens/palettes.py. Run\n"
        "    python -m slantui.tokens css -o slantui/css/palettes.css")


def test_bundle_is_in_load_order():
    b = bundle()
    starts = [b.index(_source(n)) for n in STYLESHEETS]
    assert starts == sorted(starts)


@pytest.mark.parametrize("name", STYLESHEETS)
def test_braces_balance(name):
    code = _code(name)
    assert code.count("{") == code.count("}"), name


# ── no colour of their own ──────────────────────────────────────────────────
@pytest.mark.parametrize("name", NO_COLOUR)
def test_no_hash_outside_a_comment(name):
    """A hash in a hand written stylesheet is a hex colour or an id selector.
    The first bypasses the roles and the second makes the shell one per page
    by decree, so neither is allowed."""
    hits = [f"{name}:{n}  {line.strip()}" for n, line in _lines(name) if "#" in line]
    assert not hits, "\n" + "\n".join(hits)


@pytest.mark.parametrize("name", NO_COLOUR)
def test_no_colour_function(name):
    hits = [f"{name}:{n}  {line.strip()}" for n, line in _lines(name)
            if re.search(r"\b(rgba?|hsla?|color-mix|color)\(", line)]
    assert not hits, "\n" + "\n".join(hits)


def test_metrics_define_no_role():
    """metrics.css is lengths and fonts. A role defined there would shadow
    the palette for every palette."""
    assert not _metrics() & set(ROLE_NAMES)


# ── the roles and the metrics are the whole vocabulary ─────────────────────
def test_every_property_read_is_defined():
    roles = set(ROLE_NAMES)
    metrics = _metrics()
    bad = []
    for name in ROLE_READERS:
        registered = set(_REGISTERED.findall(_code(name)))
        for n, line in _lines(name):
            for prop, fallback in _VAR.findall(line):
                if prop in roles or prop in metrics or prop in registered:
                    continue
                if prop in LOCAL and fallback:
                    continue
                bad.append(f"{name}:{n}  --{prop}")
    assert not bad, "not a role, not a metric:\n" + "\n".join(bad)


def test_no_filter_moves_on_the_compositor():
    """A transition or an animation of filter or backdrop-filter runs on the
    engine's compositor, and while one runs the engine draws every piece of
    text in the page in grey scale instead of ClearType, the title band's
    included: the loading screen's reveal made the band look out of focus for
    a second and a half. A filter that has to move reads a registered
    property, and the property is what moves (layout.css, under the loading
    screen)."""
    bad = []
    for name in ROLE_READERS:
        code = _code(name)
        for m in re.finditer(r"(transition(?:-property)?|animation(?:-name)?)\s*:([^;{}]*)", code):
            if re.search(r"(?<![\w-])(backdrop-)?filter\b", m.group(2)):
                line = code.count("\n", 0, m.start()) + 1
                bad.append(f"{name}:{line}  {m.group(0).strip()}")
        for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{(.*?)\}\s*\}", code, re.S):
            if re.search(r"(?<![\w-])(backdrop-)?filter\s*:", m.group(2)):
                bad.append(f"{name}: @keyframes {m.group(1)} moves a filter")
    assert not bad, "\n" + "\n".join(bad)


def test_a_registered_property_is_read():
    """A property registered and never read is a registration for nothing."""
    for name in ROLE_READERS:
        code = _code(name)
        read = {prop for prop, _ in _VAR.findall(code)}
        for prop in _REGISTERED.findall(code):
            assert prop in read, f"{name} registers --{prop} and never reads it"


def test_every_role_is_read_somewhere():
    """A role no stylesheet reads is a role the vocabulary does not need."""
    used = set()
    for name in ROLE_READERS:
        used |= {prop for prop, _ in _VAR.findall(_code(name))}
    unused = [r for r in ROLE_NAMES if r not in used]
    assert not unused, f"no stylesheet reads {unused}"


# ── the house rules ─────────────────────────────────────────────────────────
def test_no_hairline_dividers():
    """Fills, never outlines. A solid border is a divider, and a side border
    is a divider whatever its width."""
    hits = []
    for name in ROLE_READERS:
        for n, line in _lines(name):
            probe = line
            for ok in ALLOWED_BORDERS:
                probe = probe.replace(ok, "")
            if re.search(r"\b(solid|dashed|dotted)\b", probe):
                hits.append(f"{name}:{n}  {line.strip()}")
            if re.search(r"border-(top|bottom|left|right)\s*:", probe):
                hits.append(f"{name}:{n}  {line.strip()}")
            if re.search(r"outline\s*:\s*(?!none)", probe):
                hits.append(f"{name}:{n}  {line.strip()}")
    assert not hits, "\n" + "\n".join(hits)


def test_the_shell_is_classes():
    code = _code("layout.css")
    for cls in (".app", ".titlebar", ".tbar-band", ".tbar-brand", ".tbar-drag",
                ".tbar-credit", ".tbar-btns", ".topbar", ".tabbar", ".tb-gap", ".tb-r",
                ".work", ".main", ".toolbar", ".stage",
                ".rp", ".rp-page", ".rp-hd", ".rp-scroll", ".rp-foot"):
        assert re.search(rf"(^|[\s,}}]){re.escape(cls)}[\s{{.:>,]", code, re.M), cls


def _length(expr: str) -> float:
    """A length the stylesheet writes with metrics, worked out: every
    var(--metric) is its number, calc() is the arithmetic it says."""
    from slantui.tokens.metrics import px as metric
    text = re.sub(r"var\(--([a-z0-9-]+)\)", lambda m: repr(metric(m.group(1))), expr)
    text = text.replace("calc(", "(").replace("px", "")
    assert re.fullmatch(r"[\d.\s()+\-*/]+", text), f"not arithmetic: {expr!r}"
    return float(eval(text, {"__builtins__": {}}))


def _sides(value: str) -> list[float]:
    """The four lengths of a margin or a padding, top right bottom left."""
    parts, depth, cur = [], 0, ""
    for ch in value + " ":
        if ch == " " and depth == 0:
            if cur:
                parts.append(cur)
            cur = ""
            continue
        depth += (ch == "(") - (ch == ")")
        cur += ch
    assert len(parts) == 4, value
    return [_length(v) for v in parts]


def test_the_credit_line_has_a_size_and_takes_no_pointer():
    """The licence says the line keeps the size SlantUI sets, so SlantUI has
    to set one. And the bar has to drag under it."""
    from slantui.css import declarations
    credit = declarations(".tbar-credit")
    assert _length(credit["font-size"]) > 0
    assert credit["pointer-events"] == "none"


def test_the_ring_round_the_mark_gives_back_the_room_it_takes():
    """The width of .tbar-brand is where the taper starts, so a button put
    around the mark may not widen the block, and may not move the mark inside
    it either. The rules are read and the arithmetic done here on the metrics,
    so the day someone writes the ring into one side and not the other the
    shape of the band does not move quietly behind them."""
    from slantui.css import declarations
    logo, button = declarations(".tbar-logo"), declarations(".tbar-logo-btn")
    top, right, bottom, left = _sides(button["margin"])
    assert left + _length(button["width"]) + right == \
        _length(logo["width"]) + _length(logo["margin-right"])
    assert top + _length(button["height"]) + bottom == _length(logo["height"])
    # and the mark stops holding the name away from itself once it is inside
    assert declarations(".tbar-logo-btn>.tbar-logo")["margin-right"] == "0"


def test_the_mark_is_as_far_from_the_left_as_from_the_top_and_the_bottom():
    """The mark's centre is half the band in and half the band down, so the
    disc round it is 7 px from the left edge, the top and the bottom of the
    band, and the name stays 47 px in, where the taper is measured from."""
    from slantui.css import declarations
    from slantui.tokens.metrics import px as metric
    brand, logo = declarations(".tbar-brand"), declarations(".tbar-logo")
    button = declarations(".tbar-logo-btn")
    half = metric("tbar-h") / 2
    mark, disc = _length(logo["width"]), _length(button["width"])
    left = _sides(brand["padding"])[3]
    assert left + mark / 2 == half                            # centre at half the band
    assert brand["align-items"] == "center"                   # and half way down
    assert half - disc / 2 == 7                               # left, top, bottom
    assert left + mark + _length(logo["margin-right"]) == 47  # the name did not move


def test_hidden_scrim_means_display_none():
    """Not opacity 0: an invisible spinner keeps the compositor busy."""
    m = re.search(r"\.scrim\{([^}]*)\}", _code("components.css"))
    assert m and "display:none" in m.group(1)
    assert re.search(r"\.scrim\.show\{display:flex\}", _code("components.css"))


def test_the_focus_ring_is_the_text_shade_of_the_accent():
    """On a light palette the fill can vanish against a grey control."""
    assert re.search(r":focus-visible\{[^}]*var\(--accent-text\)", _code("base.css"))
