"""The CSS a palette turns into, and the switching mechanism above it."""
from __future__ import annotations

import re

import pytest

from slantui.tokens import DEFAULT, PALETTES, render, render_all, variable
from slantui.tokens.roles import ROLE_NAMES

SLUGS = list(PALETTES)


@pytest.mark.parametrize("slug", SLUGS)
def test_every_role_reaches_the_stylesheet(slug):
    out = render(PALETTES[slug])
    for role in ROLE_NAMES:
        assert f"{variable(role)}:" in out, f"{slug}: {role} is missing"


@pytest.mark.parametrize("slug", SLUGS)
def test_the_values_survive_the_trip(slug):
    p = PALETTES[slug]
    out = render(p)
    for role in ROLE_NAMES:
        assert re.search(rf"{re.escape(variable(role))}:\s*{re.escape(p[role])};", out)


@pytest.mark.parametrize("slug", SLUGS)
def test_the_engine_is_told_which_scheme_it_is_painting(slug):
    """Without this the number field's own stepper comes out white on black."""
    p = PALETTES[slug]
    assert f"color-scheme:{p.scheme};" in render(p)


def test_braces_balance():
    for slug in SLUGS:
        out = render(PALETTES[slug])
        assert out.count("{") == out.count("}") == 1


def test_the_default_owns_the_root_selector():
    out = render_all(list(PALETTES.values()), DEFAULT.slug)
    assert re.search(r"(?m)^:root\{", out)
    assert f':root[data-palette="{DEFAULT.slug}"]' not in out


def test_every_other_palette_is_keyed():
    out = render_all(list(PALETTES.values()), DEFAULT.slug)
    for slug in SLUGS:
        if slug == DEFAULT.slug:
            continue
        assert f':root[data-palette="{slug}"]{{' in out


def test_the_variable_name_carries_no_vendor_prefix():
    assert variable("surface-0") == "--surface-0"
