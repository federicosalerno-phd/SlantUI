"""The metric layer, and the stylesheet written from it.

The metrics moved into Python in phase 8, because a toolkit that is not a
browser cannot read a stylesheet and the band's profile is four of these
numbers. So the same two rules the palettes live under apply here: the Python
is the source, the CSS is generated, and a test fails while the file is
behind.
"""
from __future__ import annotations

import re

import pytest

from slantui.css import path
from slantui.tokens.css import metrics_stylesheet
from slantui.tokens.metrics import (BAND_METRICS, FONTS, GROUPS, LENGTHS,
                                    METRIC_NAMES, METRICS, TIMES, as_dict,
                                    metric, ms, px, value)
from slantui.tokens.roles import ROLE_NAMES

_DEF = re.compile(r"--([a-z0-9-]+)\s*:")


def _source() -> str:
    return path("metrics.css").read_text(encoding="utf-8")


# ── the file is the Python ──────────────────────────────────────────────────
def test_metrics_css_is_what_the_python_says():
    assert _source() == metrics_stylesheet(), (
        "slantui/css/metrics.css is behind slantui/tokens/metrics.py. Run\n"
        "    python -m slantui.tokens metrics -o slantui/css/metrics.css")


def test_the_stylesheet_defines_every_metric_and_nothing_else():
    code = re.sub(r"/\*.*?\*/", "", _source(), flags=re.DOTALL)
    assert tuple(_DEF.findall(code)) == METRIC_NAMES


def test_the_stylesheet_names_no_colour():
    """A hash here is a hex colour, and colour is the palette's business."""
    code = re.sub(r"/\*.*?\*/", "", _source(), flags=re.DOTALL)
    assert "#" not in code
    assert not re.search(r"\b(rgba?|hsla?|color-mix)\(", code)


# ── the vocabulary ──────────────────────────────────────────────────────────
def test_no_metric_is_named_after_a_role():
    """A metric defined with a role's name would shadow the palette on every
    palette at once."""
    assert not set(METRIC_NAMES) & set(ROLE_NAMES)


def test_every_name_is_unique():
    assert len(set(METRIC_NAMES)) == len(METRIC_NAMES)


def test_every_metric_says_what_it_is_for():
    for m in METRICS:
        assert m.purpose.strip(), m.name
        assert m.purpose[0].isupper(), m.name
        assert m.purpose.rstrip().endswith("."), m.name


def test_every_group_has_a_title():
    for m in METRICS:
        assert m.group in GROUPS, m.group


def test_a_metric_is_a_length_a_font_or_a_duration():
    assert set(LENGTHS) | set(FONTS) | set(TIMES) == set(METRIC_NAMES)
    assert not set(LENGTHS) & set(FONTS)
    assert not set(LENGTHS) & set(TIMES)


def test_every_duration_is_written_in_milliseconds():
    for name in TIMES:
        assert value(name).endswith("ms"), name
        assert ms(name) > 0, name


def test_ms_on_a_length_says_so():
    with pytest.raises(TypeError):
        ms("tbar-h")


def test_a_control_answers_faster_than_it_lets_go():
    """The whole point of having three durations instead of one."""
    assert ms("t-in") < ms("t-chg") < ms("t-out")


def test_every_length_is_written_in_pixels():
    """One unit across the design. A rem here would be relative to a root
    font size no application agrees on."""
    for name in LENGTHS:
        assert value(name).endswith("px"), name


# ── reading them ────────────────────────────────────────────────────────────
def test_px_gives_the_number():
    assert px("tbar-h") == 44.0
    assert px("fs") == 12.5


def test_px_on_a_font_says_so():
    with pytest.raises(TypeError):
        px("font-brand")


def test_an_unknown_name_is_a_key_error():
    with pytest.raises(KeyError):
        metric("no-such-metric")


def test_as_dict_is_in_order():
    assert tuple(as_dict()) == METRIC_NAMES


# ── the comb ────────────────────────────────────────────────────────────────
def test_a_block_is_a_whole_number_of_slots():
    """A block that were 2.5 slots tall would put the block under it half a
    slot off the comb, and the comb is the whole point of both numbers."""
    assert px("block") % px("slot") == 0
    assert px("block") > px("slot")


def test_the_slot_is_a_whole_number_of_the_spacing_scale():
    """The step is in the same family as the four spacings, so half a slot and
    a quarter of one are both on the scale."""
    assert px("slot") % px("sp-2") == 0


# ── the band ────────────────────────────────────────────────────────────────
def test_the_band_metrics_exist_and_are_lengths():
    for name in BAND_METRICS:
        assert name in LENGTHS, name


def test_the_band_is_thinner_at_the_thin_end():
    assert px("tbar-thin") < px("tbar-h")


def test_the_join_fits_inside_the_run():
    """A radius larger than half the oblique would be trimmed on every
    window, which is a number that does not mean what it says."""
    assert px("tbar-join") <= px("tbar-slant") / 2
