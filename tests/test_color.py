"""The colour maths, checked against values that can be looked up."""
from __future__ import annotations


import pytest

from slantui.tokens import color


# ── parsing ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text, expected", [
    ("#000", (0.0, 0.0, 0.0, 1.0)),
    ("#FFFFFF", (1.0, 1.0, 1.0, 1.0)),
    ("#ffffff", (1.0, 1.0, 1.0, 1.0)),
    ("#00000080", (0.0, 0.0, 0.0, 128 / 255)),
])
def test_parse(text, expected):
    assert color.parse(text) == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("text", ["", "abc", "#gggggg", "#12345", "rgb(1,2,3)"])
def test_parse_rejects_junk(text):
    assert not color.is_hex(text)
    with pytest.raises(ValueError):
        color.parse(text)


def test_hex_round_trip():
    for value in ("#0D0D0F", "#F5C542", "#E6E6EC", "#3FBFB0", "#00000099"):
        assert color.to_hex(color.parse(value)) == value.upper()


def test_alpha_is_written_only_when_it_bites():
    assert color.to_hex((0.0, 0.0, 0.0), 1.0) == "#000000"
    assert color.to_hex((0.0, 0.0, 0.0), 0.6) == "#00000099"


# ── WCAG ────────────────────────────────────────────────────────────────────
def test_luminance_endpoints():
    assert color.luminance("#000000") == pytest.approx(0.0)
    assert color.luminance("#FFFFFF") == pytest.approx(1.0)


def test_contrast_endpoints():
    assert color.contrast("#000000", "#FFFFFF") == pytest.approx(21.0, abs=1e-6)
    assert color.contrast("#777777", "#777777") == pytest.approx(1.0)


def test_contrast_does_not_care_about_order():
    a, b = "#0D0D0F", "#F5C542"
    assert color.contrast(a, b) == pytest.approx(color.contrast(b, a))


def test_contrast_against_a_known_pair():
    # 0.7 grey on white, the value every online checker reports for this pair.
    assert color.contrast("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)


def test_compositing():
    assert color.over("#FFFFFF00", "#123456") == "#123456"
    assert color.over("#FFFFFFFF", "#123456") == "#FFFFFF"
    half = color.over("#FFFFFF80", "#000000")
    assert color.parse(half)[0] == pytest.approx(128 / 255, abs=0.01)


# ── OKLab ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("value", [
    "#000000", "#FFFFFF", "#0D0D0F", "#F5C542", "#3B72D9", "#57B26A", "#B0524A",
])
def test_oklab_round_trip(value):
    assert color.from_oklab(color.to_oklab(value)) == value


@pytest.mark.parametrize("value", ["#0D0D0F", "#F5C542", "#E6E6EC", "#B07CF0"])
def test_oklch_round_trip(value):
    assert color.from_oklch(color.to_oklch(value)) == value


def test_oklab_lightness_endpoints():
    assert color.lightness("#000000") == pytest.approx(0.0, abs=1e-6)
    assert color.lightness("#FFFFFF") == pytest.approx(1.0, abs=1e-3)


def test_lightness_is_monotone_in_luminance():
    ramp = ["#111111", "#333333", "#666666", "#999999", "#CCCCCC", "#EEEEEE"]
    lightnesses = [color.lightness(v) for v in ramp]
    assert lightnesses == sorted(lightnesses)


def test_with_lightness_holds_the_hue_inside_the_gamut():
    before = color.hue("#F5C542")
    after = color.hue(color.with_lightness("#F5C542", 0.78))
    assert abs(before - after) < 1.0


def test_a_lightness_the_gamut_cannot_hold_is_clipped():
    """Gold has no room left at a quarter of its lightness.

    from_oklab clips each channel into range, and clipping moves the hue. The
    solvers all measure the colour they actually got back, so this costs
    nothing there, but it is worth knowing before reading a surprising value.
    """
    moved = color.with_lightness("#F5C542", 0.4)
    assert abs(color.hue("#F5C542") - color.hue(moved)) > 5.0
    assert color.luminance(moved) < color.luminance("#F5C542")


def test_shift_lightness_goes_the_way_it_says():
    assert color.luminance(color.shift_lightness("#555555", 0.1)) > color.luminance("#555555")
    assert color.luminance(color.shift_lightness("#555555", -0.1)) < color.luminance("#555555")


def test_with_hue_wraps():
    assert color.with_hue("#F5C542", 400.0) == color.with_hue("#F5C542", 40.0)


# ── mixing ──────────────────────────────────────────────────────────────────
def test_mix_endpoints():
    assert color.mix("#000000", "#FFFFFF", 0.0) == "#000000"
    assert color.mix("#000000", "#FFFFFF", 1.0) == "#FFFFFF"


def test_mix_is_clamped():
    assert color.mix("#000000", "#FFFFFF", -3.0) == "#000000"
    assert color.mix("#000000", "#FFFFFF", 9.0) == "#FFFFFF"


def test_mix_lands_between_the_two():
    mid = color.mix("#0D0D0F", "#F5C542", 0.5)
    assert color.luminance("#0D0D0F") < color.luminance(mid) < color.luminance("#F5C542")


def test_mix_carries_the_alpha():
    assert color.alpha_of(color.mix("#00000000", "#FFFFFFFF", 0.5)) == pytest.approx(0.5, abs=0.01)


def test_is_dark():
    assert color.is_dark("#0D0D0F")
    assert color.is_dark("#2B2B2B")
    assert not color.is_dark("#EFEFF2")
    assert not color.is_dark("#FFFFFF")
