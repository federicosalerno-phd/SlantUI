"""The generator, held to the same contract as the hand written palettes.

The point of this file is the property test at the bottom: a palette built
from five arbitrary values has to clear the audit, because the generator
solves against the same contrast function the auditor measures with. If those
two ever drift apart, this is where it shows.
"""
from __future__ import annotations

import random

import pytest

from slantui.tokens import PALETTES, color, derive, failures
from slantui.tokens.contrast import alpha_problems
from slantui.tokens.generate import keep_or_solve, solve_ink, solve_text
from slantui.tokens.roles import ROLE_NAMES

SEED = dict(base="#0D0D0F", accent="#F5C542", text="#E6E6EC",
            ok="#57B26A", err="#B0524A")


def test_five_values_fill_every_role():
    p = derive(**SEED)
    assert set(p.values) == set(ROLE_NAMES)


def test_the_scheme_comes_from_the_base():
    assert derive(**SEED).scheme == "dark"
    assert derive(**{**SEED, "base": "#EFEFF2", "text": "#17171B"}).scheme == "light"


def test_the_seeds_that_are_handed_over_are_kept():
    p = derive(**SEED)
    assert p["surface-0"] == SEED["base"]
    assert p["accent"] == SEED["accent"]
    assert p["text-1"] == SEED["text"]


def test_the_alpha_roles_come_out_at_the_drawn_values():
    """The formula was written from the values the design was drawn
    with, so it has to land back on them."""
    p = derive(**SEED)
    assert p["scrim"] == "#0D0D0FB8"
    assert p["shadow"] == "#00000099"
    assert p["overlay"].endswith("F2")
    assert color.alpha_of(p["overlay"]) == pytest.approx(0.95, abs=0.005)


def test_warn_is_amber_and_was_never_asked_for():
    p = derive(**SEED)
    assert 55.0 < color.hue(p["warn"]) < 100.0


def test_the_status_fills_take_one_ink():
    p = derive(**SEED)
    for fill in ("ok", "warn", "err"):
        assert color.contrast(p["on-status"], p[fill]) >= 4.5


def test_a_dark_base_lifts_the_controls_and_a_light_one_sinks_them():
    dark = derive(**SEED)
    light = derive(**{**SEED, "base": "#EFEFF2", "text": "#17171B"})
    assert color.luminance(dark["control"]) > color.luminance(dark["surface-0"])
    assert color.luminance(light["control"]) < color.luminance(light["surface-0"])


def test_the_surfaces_rise_on_both_schemes():
    for kw in (SEED, {**SEED, "base": "#EFEFF2", "text": "#17171B"}):
        p = derive(**kw)
        steps = [color.luminance(p[f"surface-{i}"]) for i in range(4)]
        assert steps == sorted(steps), f"{kw['base']}: the surfaces do not rise"


def test_a_white_base_has_to_step_the_other_way():
    """There is no headroom above white, so the surfaces go down instead."""
    p = derive(**{**SEED, "base": "#FFFFFF", "text": "#17171B"})
    assert color.luminance(p["surface-3"]) < color.luminance(p["surface-0"])
    assert not failures(p)


def test_the_accent_darkens_on_a_light_palette_and_brightens_on_a_dark_one():
    dark = derive(**SEED)
    light = derive(**{**SEED, "base": "#EFEFF2", "text": "#17171B"})
    assert color.luminance(dark["accent-hover"]) > color.luminance(dark["accent"])
    assert color.luminance(light["accent-hover"]) < color.luminance(light["accent"])


def test_a_dark_palette_keeps_the_accent_as_its_accent_text():
    assert derive(**SEED)["accent-text"] == SEED["accent"]


def test_a_light_palette_has_to_darken_the_accent_for_text():
    light = derive(**{**SEED, "base": "#EFEFF2", "text": "#17171B"})
    assert light["accent-text"] != light["accent"]
    assert color.luminance(light["accent-text"]) < color.luminance(light["accent"])


# ── the input checks ────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["", "gold", "#12345", "rgb(0,0,0)"])
def test_a_value_that_is_not_a_colour_is_refused(bad):
    with pytest.raises(ValueError):
        derive(**{**SEED, "accent": bad})


def test_a_seed_may_not_carry_an_alpha():
    with pytest.raises(ValueError, match="may not carry an alpha"):
        derive(**{**SEED, "accent": "#F5C54280"})


# ── the solvers on their own ────────────────────────────────────────────────
def test_solve_text_gives_the_same_answer_whatever_seed_it_starts_from():
    surfaces = {k: PALETTES["gold-dark"][k] for k in
                ("surface-0", "surface-3", "control-hover")}
    a = solve_text("#FFFFFF", surfaces, 4.5, True)
    b = solve_text("#222222", surfaces, 4.5, True)
    assert a == b


def test_solve_text_stops_as_close_to_the_surfaces_as_the_threshold_allows():
    surfaces = {"surface-0": "#0D0D0F"}
    loose = solve_text("#888888", surfaces, 3.0, True)
    tight = solve_text("#888888", surfaces, 7.0, True)
    assert color.luminance(loose) < color.luminance(tight)


def test_keep_or_solve_leaves_a_seed_that_already_works():
    surfaces = {"surface-0": "#0D0D0F"}
    assert keep_or_solve("#F5C542", surfaces, 4.5, True) == "#F5C542"


def test_keep_or_solve_moves_a_seed_that_does_not():
    surfaces = {"surface-0": "#FFFFFF"}
    assert keep_or_solve("#F5C542", surfaces, 4.5, False) != "#F5C542"


def test_solve_ink_prefers_the_palettes_own_ink():
    assert solve_ink(["#F5C542"], "#0D0D0F", "#E6E6EC") == "#0D0D0F"


def test_solve_ink_falls_back_to_pure_black_or_white():
    """A near white that falls short is dropped for the real thing.

    #E6E6EC reaches only 4.19:1 on this green, so the palette's own light ink
    loses to plain white at 5.26:1.
    """
    assert solve_ink(["#2F7A46"], "#0D0D0F", "#E6E6EC") == "#FFFFFF"


# ── the property that ties the generator to the auditor ─────────────────────
def _random_seed(rng: random.Random, dark: bool) -> dict:
    def hexc(lo, hi):
        return "#" + "".join(f"{rng.randint(lo, hi):02X}" for _ in range(3))
    return dict(
        base=hexc(0, 24) if dark else hexc(228, 250),
        accent=hexc(60, 255),
        text=hexc(215, 255) if dark else hexc(0, 45),
        ok=hexc(40, 200),
        err=hexc(40, 200),
    )


@pytest.mark.parametrize("dark", [True, False])
def test_a_derived_palette_clears_the_audit(dark):
    rng = random.Random(20260918 + int(dark))
    for i in range(12):
        seed = _random_seed(rng, dark)
        p = derive(name=f"Random {i}", slug=f"random-{i}", **seed)
        bad = failures(p)
        assert not bad, (f"seed {seed}\n" + "\n".join(str(c) for c in bad))
        assert not alpha_problems(p)


def test_a_grey_accent_still_produces_a_usable_palette():
    """The awkward input: an accent with no chroma to work with."""
    p = derive(**{**SEED, "accent": "#808080"})
    assert not failures(p)
