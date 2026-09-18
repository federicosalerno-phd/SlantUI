"""The role vocabulary, and the rule that a palette fills all of it."""
from __future__ import annotations

import pytest

from slantui.tokens import PALETTES, Palette, color
from slantui.tokens.roles import (ALPHA_ROLES, CORE, EXTENDED, MIN_RATIO,
                                  ON_FILL, ROLE_NAMES, ROLES, SURFACES, TEXTS,
                                  tier_of)

# The vocabulary agreed before any of this was written. It is repeated here so
# that dropping or renaming a core role is a deliberate act with a test to
# change, and never a slip.
AGREED_CORE = (
    "surface-0", "surface-1", "surface-2", "surface-3",
    "control", "control-hover", "control-active",
    "text-1", "text-2", "text-3", "text-4",
    "accent", "accent-hover", "accent-active", "on-accent",
    "ok", "warn", "err",
    "scrim", "shadow", "overlay",
)


def test_the_core_set_is_the_agreed_one():
    assert set(CORE) == set(AGREED_CORE)


def test_every_extended_role_says_why_it_exists():
    assert EXTENDED, "the extended set should not be empty"
    for r in ROLES:
        if r.extended:
            assert len(r.purpose) > 20, f"{r.name} needs a reason"


def test_role_names_are_unique():
    assert len(ROLE_NAMES) == len(set(ROLE_NAMES))


def test_role_names_are_css_safe():
    for name in ROLE_NAMES:
        assert name.islower()
        assert name.replace("-", "").isalnum()


def test_the_contract_only_names_real_roles():
    for name in (*SURFACES, *TEXTS, *ON_FILL):
        assert name in ROLE_NAMES, f"{name} is in the contract but is not a role"
    for fills in ON_FILL.values():
        for name in fills:
            assert name in ROLE_NAMES


def test_no_role_is_both_a_text_and_a_surface():
    assert not set(TEXTS) & set(SURFACES)


def test_every_tier_has_a_threshold():
    for role in (*TEXTS, *ON_FILL):
        assert tier_of(role) in MIN_RATIO


def test_tier_of_refuses_a_surface():
    with pytest.raises(KeyError):
        tier_of("surface-0")


# ── what a palette has to satisfy ───────────────────────────────────────────
@pytest.mark.parametrize("slug", list(PALETTES))
def test_palette_fills_every_role(slug):
    assert set(PALETTES[slug].values) == set(ROLE_NAMES)


@pytest.mark.parametrize("slug", list(PALETTES))
def test_only_the_depth_roles_carry_alpha(slug):
    for name, value in PALETTES[slug].values.items():
        if name not in ALPHA_ROLES:
            assert color.alpha_of(value) == 1.0, f"{slug}: {name} = {value}"


@pytest.mark.parametrize("slug", list(PALETTES))
def test_the_surfaces_are_told_apart(slug):
    """Four surfaces that look the same are one surface with three names."""
    p = PALETTES[slug]
    steps = [p[f"surface-{i}"] for i in range(4)]
    for a, b in zip(steps, steps[1:]):
        assert a != b, f"{slug}: two surfaces carry the same value"
        assert abs(color.luminance(a) - color.luminance(b)) > 0.0008, \
            f"{slug}: {a} and {b} are the same shade"


@pytest.mark.parametrize("slug", list(PALETTES))
def test_the_control_states_differ(slug):
    p = PALETTES[slug]
    states = {p["control"], p["control-hover"], p["control-active"]}
    assert len(states) == 3, f"{slug}: two control states carry the same value"


@pytest.mark.parametrize("slug", list(PALETTES))
def test_the_text_ladder_goes_one_way(slug):
    """text-1 to text-4 has to fade, on a dark palette and on a light one."""
    p = PALETTES[slug]
    ramp = [color.contrast(p[f"text-{i}"], p["surface-0"]) for i in (1, 2, 3, 4)]
    assert ramp == sorted(ramp, reverse=True), f"{slug}: the text ladder is out of order"


def test_a_missing_role_is_refused():
    with pytest.raises(ValueError, match="no value for"):
        Palette(name="x", slug="x", scheme="dark", values={"surface-0": "#000000"})


def test_an_unknown_role_is_refused():
    values = dict(PALETTES["gold-dark"].values)
    values["surface-9"] = "#000000"
    with pytest.raises(ValueError, match="is not a role"):
        Palette(name="x", slug="x", scheme="dark", values=values)


def test_an_alpha_on_the_wrong_role_is_refused():
    values = dict(PALETTES["gold-dark"].values)
    values["surface-0"] = "#00000080"
    with pytest.raises(ValueError, match="may not carry an alpha"):
        Palette(name="x", slug="x", scheme="dark", values=values)


def test_an_unknown_scheme_is_refused():
    with pytest.raises(ValueError, match="dark or light"):
        Palette(name="x", slug="x", scheme="sepia",
                values=dict(PALETTES["gold-dark"].values))
