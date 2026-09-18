"""The targets outside the browser: data, WPF, PowerShell and Unity.

The point of the export layer is that a colour corrected by the auditor
reaches a WPF window in the same commit it reaches the page. So what is
checked here is not that the files parse. It is that every target carries
every role, every palette and the same values, and that the one conversion
any of them does, moving the alpha to the front for WPF, is right.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest

from slantui import __version__
from slantui.export import TARGETS, as_json, as_powershell, as_uss, as_xaml, render
from slantui.export.data import design
from slantui.export.powershell import ps_string
from slantui.export.uss import uss_class
from slantui.export.xaml import wpf_font, wpf_hex, xaml_key
from slantui.geometry import band_shape
from slantui.tokens import DEFAULT, PALETTES, color
from slantui.tokens.metrics import FONTS, LENGTHS, METRIC_NAMES, METRICS
from slantui.tokens.roles import ROLE_NAMES

ALL = list(PALETTES.values())


# ── the neutral data ────────────────────────────────────────────────────────
def test_the_data_carries_the_whole_vocabulary():
    d = design()
    assert d["slantui"] == __version__
    assert d["default"] == DEFAULT.slug
    assert [r["name"] for r in d["roles"]] == list(ROLE_NAMES)
    assert [m["name"] for m in d["metrics"]] == list(METRIC_NAMES)
    assert set(d["palettes"]) == set(PALETTES)


def test_every_palette_in_the_data_is_complete():
    for slug, p in design()["palettes"].items():
        assert set(p["values"]) == set(ROLE_NAMES), slug
        assert p["scheme"] in ("dark", "light"), slug


def test_the_data_carries_the_band():
    b, s = design()["band"], band_shape()
    assert (b["height"], b["thin"], b["slant"], b["join"]) == (
        s.height, s.thin, s.slant, s.join)
    assert b["drop"] == s.drop


def test_the_json_parses_and_round_trips():
    assert json.loads(as_json())["default"] == DEFAULT.slug


def test_the_json_ships_in_the_package():
    from pathlib import Path
    import slantui
    shipped = Path(slantui.__file__).resolve().parent / "design.json"
    assert shipped.is_file()
    assert shipped.read_text(encoding="utf-8") == as_json(), (
        "slantui/design.json is behind the Python. Run\n"
        "    python -m slantui.tokens json -o slantui/design.json")


# ── WPF ─────────────────────────────────────────────────────────────────────
def test_the_alpha_moves_to_the_front():
    assert wpf_hex("#0D0D0F") == "#0D0D0F"
    assert wpf_hex("#00000099") == "#99000000"
    assert wpf_hex("#101013F2") == "#F2101013"
    assert wpf_hex("#abc") == "#AABBCC"


@pytest.mark.parametrize("slug", sorted(PALETTES))
def test_the_wpf_form_is_the_same_colour(slug):
    """Moving the digits, never recomputing them: the channels come back
    exactly as the palette wrote them."""
    for role, value in PALETTES[slug].values.items():
        r, g, b, a = color.parse(value)
        h = wpf_hex(value).lstrip("#")
        if len(h) == 8:
            assert h[:2] == f"{round(a * 255):02X}", (slug, role)
            h = h[2:]
        else:
            assert a == 1.0, (slug, role)
        assert h == "".join(f"{round(c * 255):02X}" for c in (r, g, b)), (slug, role)


def test_a_key_is_the_role_in_pascal_case():
    assert xaml_key("surface-0") == "SlantSurface0"
    assert xaml_key("accent-surface-hover") == "SlantAccentSurfaceHover"
    assert xaml_key("r-md") == "SlantRMd"


def test_a_font_stack_loses_the_quotes_and_the_css_generics():
    assert wpf_font("'Segoe UI',system-ui,-apple-system,sans-serif") == "Segoe UI"
    assert wpf_font("Consolas,'Courier New',monospace") == "Consolas, Courier New"


def test_the_dictionary_is_well_formed_xml():
    ET.fromstring(as_xaml(DEFAULT))


def test_the_dictionary_keys_every_role_and_every_metric():
    root = ET.fromstring(as_xaml(DEFAULT))
    key = "{http://schemas.microsoft.com/winfx/2006/xaml}Key"
    keys = {el.attrib[key] for el in root if key in el.attrib}
    for role in ROLE_NAMES:
        assert xaml_key(role) in keys, role
        assert xaml_key(role) + "Color" in keys, role
    for name in METRIC_NAMES:
        assert xaml_key(name) in keys, name


def test_the_dictionary_holds_one_palette():
    with pytest.raises(ValueError):
        as_xaml(ALL)


@pytest.mark.parametrize("slug", sorted(PALETTES))
def test_the_dictionary_carries_that_palette_and_says_which(slug):
    text = as_xaml(PALETTES[slug])
    assert f'x:Key="SlantPaletteSlug">{slug}<' in text
    for role, value in PALETTES[slug].values.items():
        assert f'x:Key="{xaml_key(role)}Color">{wpf_hex(value)}<' in text, role


# ── PowerShell ──────────────────────────────────────────────────────────────
def test_the_data_file_carries_every_palette_twice_over():
    text = as_powershell()
    for slug, p in PALETTES.items():
        assert f"'{slug}' = @{{" in text
        for role, value in p.values.items():
            assert f"'{role}'" in text
            assert f"'{value}'" in text, (slug, role)
            assert f"'{wpf_hex(value)}'" in text, (slug, role)


def test_the_data_file_quotes_an_apostrophe():
    """A note is free text, and a single quote inside a single quoted
    PowerShell string is written twice or the file stops parsing."""
    assert ps_string("it's here") == "'it''s here'"
    quoted = DEFAULT.rename(DEFAULT.name, DEFAULT.slug, "on paper, and it's white")
    assert "it''s white" in as_powershell([quoted])


def test_the_data_file_holds_numbers_without_units():
    text = as_powershell()
    assert re.search(r"'tbar-h'\s*=\s*44\b", text)
    assert re.search(r"'tbar-h'\s*=\s*'44px'", text)


def test_the_data_file_ships_in_the_package():
    from slantui.wpf import DATA, path
    assert path(DATA).read_text(encoding="utf-8") == as_powershell(), (
        "slantui/wpf/SlantUI.Tokens.psd1 is behind the Python. Run\n"
        "    python -m slantui.tokens ps1 -o slantui/wpf/SlantUI.Tokens.psd1")


# ── Unity ───────────────────────────────────────────────────────────────────
def test_the_uss_keys_the_default_on_root_and_the_rest_on_a_class():
    text = as_uss()
    assert ":root {" in text
    for slug in PALETTES:
        if slug == DEFAULT.slug:
            continue
        assert "." + uss_class(slug) + " {" in text


def test_the_uss_carries_every_role_of_every_palette():
    text = as_uss()
    for slug, p in PALETTES.items():
        for role, value in p.values.items():
            assert f"--{role}: {value};" in text, (slug, role)


def test_the_uss_leaves_the_fonts_out():
    """USS wants a font asset and not a family name, so a family name in
    there would be a property that silently does nothing."""
    text = as_uss()
    for name in FONTS:
        assert f"--{name}:" not in text, name
    for name in LENGTHS:
        assert f"--{name}:" in text, name


def test_the_uss_carries_no_declaration_a_browser_needs():
    assert "color-scheme" not in as_uss()


# ── the dispatcher ──────────────────────────────────────────────────────────
def test_every_target_renders():
    for name in TARGETS:
        palettes = [DEFAULT] if name == "xaml" else ALL
        assert render(name, palettes, DEFAULT.slug).strip()


def test_an_unknown_target_says_which_ones_exist():
    with pytest.raises(KeyError) as e:
        render("swiftui", ALL)
    assert "json" in str(e.value)


def test_every_target_ends_in_one_newline():
    for name in TARGETS:
        palettes = [DEFAULT] if name == "xaml" else ALL
        text = render(name, palettes, DEFAULT.slug)
        assert text.endswith("\n") and not text.endswith("\n\n"), name


def test_nothing_in_the_export_layer_imports_anything_outside_the_library():
    """slantui.tokens promises a machine with nothing installed can still
    generate a palette. The export layer is on the same promise."""
    import ast
    from pathlib import Path
    import slantui.export
    allowed = {"json", "math", "textwrap", "dataclasses", "decimal",
               "__future__", "pathlib", "shutil", "re", "slantui"}
    for f in Path(slantui.export.__file__).parent.glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in allowed, (f.name, a.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] in allowed, (f.name, node.module)
