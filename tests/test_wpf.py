"""The PowerShell module, run by PowerShell.

Two of his applications are WPF windows written in PowerShell, so the module
in ``slantui/wpf`` is the face the library shows them. It holds the only
second implementation of anything in this repository: the band's profile,
written again in PowerShell because a window being built cannot call Python.

Phase 2 took the same trade for ``theme.js`` against ``color.py`` and paid
for it the same way, with a test that runs both and compares them. This is
that test. It needs Windows PowerShell, which is where these applications
run, and skips anywhere else.

The rounding is worth one line of warning to whoever edits either side. The
machine this was written on formats a number as ``2,67``, so every number
the module writes goes through InvariantCulture. A path with a comma in it
parses as a different shape, or as none.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from slantui.export.xaml import wpf_hex
from slantui.geometry import band_path, band_shape
from slantui.tokens import DEFAULT, PALETTES
from slantui.tokens.metrics import LENGTHS, px
from slantui.wpf import DATA, FILES, MODULE, install, path

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell"),
    reason="the module is for WPF, which is Windows PowerShell")

# The same spread as tests/test_geometry.py, so the three implementations are
# compared on one set of windows and not on three.
CASES = ((1280, 210), (1024, 187.4), (2480, 333.333), (640, 620), (300, 296),
         (1440, 0), (900, 12.5))

_PROBE = r"""
$ErrorActionPreference = 'Stop'
Import-Module '{module}' -Force
$out = [ordered]@{{}}
$out.Default   = (Get-SlantTokens).Default
$out.Palettes  = @(Get-SlantPaletteNames)
$out.Roles     = @((Get-SlantTokens).Roles)
$out.Colors    = @{{}}
foreach ($r in (Get-SlantTokens).Roles) {{ $out.Colors[$r] = Get-SlantColor $r }}
$out.Metrics   = @{{}}
foreach ($m in @({lengths})) {{ $out.Metrics[$m] = Get-SlantMetric $m }}
$out.Bands     = @()
foreach ($c in @({cases})) {{
    $out.Bands += Get-SlantBandPath -Width $c[0] -BrandWidth $c[1]
}}
$out.Tall = Get-SlantBandPath -Width 1000 -BrandWidth 200 -Height 60
$out.Refs = @{{}}
foreach ($r in @('surface-0', 'accent', 'text-2', 'scrim')) {{
    $out.Refs[$r] = ConvertTo-SlantColorRef (Get-SlantColor $r)
}}
$out | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.fixture(scope="module")
def probe(tmp_path_factory) -> dict:
    """One PowerShell run, everything read out of it. Starting the shell
    costs more than every check in this file put together."""
    folder = tmp_path_factory.mktemp("slantwpf")
    install(folder)
    lengths = ",".join(f"'{n}'" for n in LENGTHS)
    cases = ",".join(f"@({w},{b})" for w, b in CASES)
    script = folder / "probe.ps1"
    script.write_text(
        _PROBE.format(module=(folder / MODULE).as_posix(), lengths=lengths,
                      cases=cases),
        encoding="utf-8")
    run = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(script)],
        capture_output=True, text=True)
    if run.returncode != 0:
        pytest.fail(f"the module did not load:\n{run.stdout}\n{run.stderr}")
    return json.loads(run.stdout)


# ── the files ───────────────────────────────────────────────────────────────
def test_both_files_are_in_the_package():
    for name in FILES:
        assert path(name).is_file(), name


def test_install_puts_both_of_them_somewhere(tmp_path):
    landed = install(tmp_path / "vendor")
    assert sorted(p.name for p in landed) == sorted(FILES)
    assert all(p.is_file() for p in landed)


def test_the_module_documents_what_it_exports():
    text = path(MODULE).read_text(encoding="utf-8")
    exported = text.split("Export-ModuleMember -Function", 1)[1]
    for name in ("Get-SlantPalette", "Get-SlantBrushes", "Get-SlantBandPath",
                 "Get-SlantBandGeometry", "Get-SlantMetric"):
        assert name in exported, name
        assert f"function {name} " in text or f"function {name}(" in text, name


def test_the_module_never_formats_a_number_without_a_culture():
    """An Italian machine writes 2,67. A path with a comma in it is a
    different shape, or is not a path at all."""
    text = path(MODULE).read_text(encoding="utf-8")
    body = text.split("function Format-SlantCoord", 1)[1].split("\nfunction ", 1)[0]
    assert body.count("$inv") >= 3


# ── the data, read by PowerShell ────────────────────────────────────────────
def test_the_data_file_parses(probe):
    assert probe["Default"] == DEFAULT.slug
    assert sorted(probe["Palettes"]) == sorted(PALETTES)


def test_powershell_reads_every_role(probe):
    assert sorted(probe["Roles"]) == sorted(PALETTES[DEFAULT.slug].values)


def test_every_colour_comes_back_in_the_wpf_form(probe):
    for role, value in PALETTES[DEFAULT.slug].values.items():
        assert probe["Colors"][role] == wpf_hex(value), role


def test_every_length_comes_back_as_a_number(probe):
    for name in LENGTHS:
        assert float(probe["Metrics"][name]) == px(name), name


# ── the band, drawn by PowerShell ───────────────────────────────────────────
@pytest.mark.parametrize("i,case", list(enumerate(CASES)), ids=[f"{w}x{b}" for w, b in CASES])
def test_powershell_draws_the_same_band(probe, i, case):
    """The cases go over by position. Naming them by the number would put
    the number through PowerShell's own formatting, and on this machine that
    writes 187,4."""
    assert probe["Bands"][i] == band_path(*case), (
        "slantui/wpf/SlantUI.psm1 and slantui/geometry.py no longer draw the "
        "same band")


def test_powershell_takes_a_band_of_another_height(probe):
    assert probe["Tall"] == band_path(1000, 200, band_shape(height=60))


@pytest.mark.parametrize("role", ["surface-0", "accent", "text-2", "scrim"])
def test_a_colour_as_the_dwm_wants_it(probe, role):
    """Windows takes a colour by number for the caption, the caption's text
    and the border, and it puts the channels the other way round. Getting
    that wrong paints the caption in the complement of what was meant, which
    reads as a broken window and not as a typo."""
    h = PALETTES[DEFAULT.slug][role].lstrip("#")
    if len(h) == 8:
        h = h[:6]                      # the alpha has no place in a COLORREF
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    assert probe["Refs"][role] == (b << 16) | (g << 8) | r


def test_the_data_file_is_the_one_the_python_writes():
    from slantui.export import as_powershell
    assert path(DATA).read_text(encoding="utf-8") == as_powershell()
