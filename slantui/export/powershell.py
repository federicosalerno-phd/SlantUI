"""Every palette, the metrics and the band, as a PowerShell data file.

A WPF window written in PowerShell, and an installer that opens one before
there is a Python on the machine, cannot import a Python package at run time,
and neither should have to: what they need is the numbers, in a file their own
language reads.

A ``.psd1`` is that file. ``Import-PowerShellDataFile`` reads it in the
restricted language, so it holds literals and nothing that runs, which is
the right amount of trust to put in a generated file. The module in
``slantui/wpf`` reads it and hands out brushes.

Every colour appears twice, once as CSS hex and once as the ``#AARRGGBB``
WPF writes. The conversion is four lines and putting it in the generator
instead of in the PowerShell keeps the colour maths in one language.
"""
from __future__ import annotations

from ..css import band_roles
from ..geometry import band_shape
from ..tokens.metrics import METRICS
from ..tokens.palette import Palette
from ..tokens.palettes import DEFAULT, PALETTES
from ..tokens.roles import ROLE_NAMES
from .xaml import wpf_font, wpf_hex

__all__ = ["as_powershell", "ps_string"]

_HEADER = """\
# SlantUI: the palettes, the metrics and the band, as data.
#
# Written by `python -m slantui.tokens ps1 -o PATH` from
# slantui/tokens/palettes.py, slantui/tokens/metrics.py and
# slantui/geometry.py. Nothing here is written by hand.
#
# Read it with Import-PowerShellDataFile, or let the module do it:
#
#     Import-Module .\\SlantUI.psm1
#     $p = Get-SlantPalette 'gold-dark'
#     $b = Get-SlantBrushes 'gold-dark'
#     $window.Background = $b['surface-0']
#
# Values holds the CSS hex a stylesheet would carry, Wpf the same colour with
# the alpha moved to the front, which is the form WPF parses.
"""


def ps_string(text: str) -> str:
    """A PowerShell single quoted string. The one escape is a doubled quote."""
    return "'" + text.replace("'", "''") + "'"


def _number(value: str) -> str:
    """A length with the unit taken off, for a file that holds numbers."""
    return f"{float(value[:-2]):g}"


def as_powershell(palettes: list[Palette] | None = None,
                  default_slug: str | None = None) -> str:
    """The data file: every palette given, or all eight."""
    chosen = list(palettes if palettes is not None else PALETTES.values())
    band = band_shape()
    pad = max(len(r) for r in ROLE_NAMES) + 2

    out = [_HEADER, "@{", f"    Default  = {ps_string(default_slug or DEFAULT.slug)}",
           "", "    # The role vocabulary, in the order the library lists it.",
           "    Roles = @("]
    for name in ROLE_NAMES:
        out.append(f"        {ps_string(name)}")
    out.append("    )")

    out += ["", "    # Lengths carry their unit, the way the stylesheet writes",
            "    # them. MetricNumbers is the same set with the unit taken off.",
            "    Metrics = @{"]
    for m in METRICS:
        out.append(f"        {ps_string(m.name):<{pad + 2}} = {ps_string(m.value)}")
    out.append("    }")

    out.append("    MetricNumbers = @{")
    for m in METRICS:
        if m.kind == "length":
            out.append(f"        {ps_string(m.name):<{pad + 2}} = {_number(m.value)}")
    out.append("    }")

    out.append("    # Plain numbers: weights, a line height, a stroke width.")
    out.append("    Numbers = @{")
    for m in METRICS:
        if m.kind == "number":
            out.append(f"        {ps_string(m.name):<{pad + 2}} = {float(m.value):g}")
    out.append("    }")

    out.append("    # Durations in milliseconds, for a storyboard or a timer.")
    out.append("    Times = @{")
    for m in METRICS:
        if m.kind == "time":
            out.append(f"        {ps_string(m.name):<{pad + 2}} = {_number(m.value)}")
    out.append("    }")

    out.append("    Fonts = @{")
    for m in METRICS:
        if m.kind == "font":
            out.append(f"        {ps_string(m.name):<{pad + 2}} = "
                       f"{ps_string(wpf_font(m.value))}")
    out.append("    }")

    out += ["", "    # The role each part of the title band is in, read out of the rule",
            "    # the page uses for it (slantui.css.BAND_PARTS).",
            "    BandRoles = @{"]
    for part, role in band_roles().items():
        out.append(f"        {ps_string(part):<{pad + 2}} = {ps_string(role)}")
    out.append("    }")

    out += ["", "    # The four numbers the oblique band is built from.",
            "    Band = @{",
            f"        Height = {band.height:g}",
            f"        Thin   = {band.thin:g}",
            f"        Slant  = {band.slant:g}",
            f"        Join   = {band.join:g}",
            f"        Drop   = {band.drop:g}",
            f"        Angle  = {band.angle:.4f}",
            "    }", ""]

    out.append("    Palettes = @{")
    for p in chosen:
        out.append(f"        {ps_string(p.slug)} = @{{")
        out.append(f"            Name   = {ps_string(p.name)}")
        out.append(f"            Scheme = {ps_string(p.scheme)}")
        out.append(f"            Note   = {ps_string(p.note)}")
        out.append("            Values = @{")
        for name in ROLE_NAMES:
            out.append(f"                {ps_string(name):<{pad}} = "
                       f"{ps_string(p[name])}")
        out.append("            }")
        out.append("            Wpf = @{")
        for name in ROLE_NAMES:
            out.append(f"                {ps_string(name):<{pad}} = "
                       f"{ps_string(wpf_hex(p[name]))}")
        out.append("            }")
        out.append("        }")
    out.append("    }")
    out.append("}")
    return "\n".join(out) + "\n"
