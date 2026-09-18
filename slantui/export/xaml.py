"""A palette and the metrics as a WPF ResourceDictionary.

A WPF window that wears this design carries its colours as hex literals in a
PowerShell function, or as a brush per role typed out by hand. What it wants
instead is the palette as resources it can merge, so a colour the auditor
corrects arrives without anyone retyping it.

Three things differ from the CSS and each one has a reason.

**The keys are prefixed.** Phase 2 decided the CSS custom properties carry no
prefix, because SlantUI owns the page it is loaded into. A ResourceDictionary
is merged into an application SlantUI does not own, next to the application's
own keys and the framework's, so the same reasoning gives the opposite
answer here. Every key starts with ``Slant``.

**A role is a brush and a colour.** ``{StaticResource SlantSurface0}`` is the
brush, which is what a Background wants, and ``SlantSurface0Color`` is the
Color behind it, which is what an animation and a hand built brush want.

**The alpha moves.** CSS writes ``#RRGGBBAA`` and WPF writes ``#AARRGGBB``,
so the three roles that carry an alpha are rewritten on the way out. A target
that gets this wrong shows a scrim in the wrong colour and nobody can see
why, so ``wpf_hex`` is tested against the palettes directly.

One palette per file. A ResourceDictionary keys a resource once, so a second
palette in the same file would overwrite the first. An application that
switches palette at run time merges another dictionary.
"""
from __future__ import annotations

from ..geometry import band_shape
from ..tokens import color
from ..tokens.metrics import METRICS, Metric
from ..tokens.palette import Palette
from ..tokens.palettes import DEFAULT
from ..tokens.roles import role as _role

__all__ = ["as_xaml", "wpf_hex", "wpf_font", "xaml_key", "PREFIX"]

PREFIX = "Slant"

# The families CSS names and WPF has never heard of. Left in the list they
# would be looked up as typefaces, fail, and cost a font fallback pass.
_CSS_GENERICS = {
    "system-ui", "-apple-system", "ui-sans-serif", "ui-monospace",
    "sans-serif", "serif", "monospace", "cursive", "fantasy",
}


def xaml_key(name: str) -> str:
    """``surface-0`` to ``SlantSurface0``. The rule is: split on the dashes,
    capitalise each piece, join, and put the prefix in front."""
    return PREFIX + "".join(part[:1].upper() + part[1:] for part in name.split("-"))


def wpf_hex(value: str) -> str:
    """A CSS colour as WPF writes it: ``#AARRGGBB``, alpha first.

    Opaque colours come back as six digits, which is what the rest of a
    hand written dictionary looks like, and the three alpha roles come back
    as eight with the alpha moved to the front. The digits are moved, never
    recomputed: a round trip through channels in 0 to 1 and back can land a
    byte off, and a palette is not the place to lose one.
    """
    if not color.is_hex(value):
        raise ValueError(f"not a hex colour: {value!r}")
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        return "#" + h.upper()
    return "#" + (h[6:8] + h[0:6]).upper()


def wpf_font(stack: str) -> str:
    """A CSS font stack as a WPF FontFamily.

    WPF takes a comma separated list of real family names. It does not take
    quotes and it does not know the CSS generics, so both go.
    """
    names = []
    for part in stack.split(","):
        part = part.strip().strip("'\"").strip()
        if part and part.lower() not in _CSS_GENERICS and part not in names:
            names.append(part)
    return ", ".join(names) if names else "Segoe UI"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _double(m: Metric) -> str:
    """A length metric as the number WPF wants, with no unit on it."""
    return f"{float(m.value[:-2]):g}"


def _duration(m: Metric) -> str:
    """A duration metric as a WPF Duration: hours, minutes, seconds."""
    return f"0:0:{float(m.value[:-2]) / 1000.0:.3f}"


def as_xaml(palette: Palette | list[Palette] | None = None,
            default_slug: str | None = None) -> str:
    """One palette, the metrics and the band, as a ResourceDictionary."""
    if isinstance(palette, list):
        if len(palette) != 1:
            raise ValueError(
                "XAML keys a resource once, so one palette per file. Name the "
                "one you want: python -m slantui.tokens xaml gold-dark")
        palette = palette[0]
    p = palette or DEFAULT
    band = band_shape()

    out: list[str] = [
        "<!-- SlantUI " + _escape(p.name) + " (" + p.slug + "), " + p.scheme + ".",
        "     Written by `python -m slantui.tokens xaml " + p.slug + " -o PATH`",
        "     from slantui/tokens/palettes.py and slantui/tokens/metrics.py.",
        "     Edit the Python and run it again; nothing here is written by hand.",
        "",
        "     Merge it and name a role:",
        "       <Border Background=\"{StaticResource " + xaml_key("surface-1") + "}\"",
        "               CornerRadius=\"{StaticResource " + xaml_key("r-md") + "Corner}\"/>",
        "-->",
        '<ResourceDictionary xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"',
        '                    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"',
        '                    xmlns:sys="clr-namespace:System;assembly=mscorlib"',
        '                    xmlns:po="http://schemas.microsoft.com/winfx/2006/xaml/'
        'presentation/options"',
        '                    xmlns:mc="http://schemas.openxmlformats.org/markup-'
        'compatibility/2006"',
        '                    mc:Ignorable="po">',
        "",
        "  <!-- Which palette this is, for an application that reports it. -->",
        f'  <sys:String x:Key="{PREFIX}PaletteSlug">{p.slug}</sys:String>',
        f'  <sys:String x:Key="{PREFIX}PaletteName">{_escape(p.name)}</sys:String>',
        f'  <sys:String x:Key="{PREFIX}PaletteScheme">{p.scheme}</sys:String>',
    ]

    group = None
    for role_name, value in p.values.items():
        r = _role(role_name)
        if r.group != group:
            group = r.group
            out.append("")
            out.append(f"  <!-- {group} -->")
        key = xaml_key(role_name)
        out.append(f'  <Color x:Key="{key}Color">{wpf_hex(value)}</Color>')
        out.append(f'  <SolidColorBrush x:Key="{key}" po:Freeze="True"'
                   f' Color="{{StaticResource {key}Color}}"/>')

    out.append("")
    out.append("  <!-- metrics: lengths as Double, radii also as CornerRadius,"
               " fonts as FontFamily, durations as Duration -->")
    for m in METRICS:
        key = xaml_key(m.name)
        if m.kind == "font":
            out.append(f'  <FontFamily x:Key="{key}">{_escape(wpf_font(m.value))}'
                       f"</FontFamily>")
            continue
        if m.kind == "time":
            out.append(f'  <Duration x:Key="{key}">{_duration(m)}</Duration>')
            continue
        out.append(f'  <sys:Double x:Key="{key}">{_double(m)}</sys:Double>')
        if m.group == "radius":
            out.append(f'  <CornerRadius x:Key="{key}Corner">{_double(m)}'
                       f"</CornerRadius>")

    out += [
        "",
        "  <!-- The band's profile. Width and brand width are known only at run",
        "       time, so the path itself is built by Get-SlantBandPath in",
        "       slantui/wpf/SlantUI.psm1, from these four numbers. -->",
        f'  <sys:Double x:Key="{PREFIX}BandDrop">{band.drop:g}</sys:Double>',
        f'  <sys:Double x:Key="{PREFIX}BandAngle">{band.angle:.4f}</sys:Double>',
        "",
        "</ResourceDictionary>",
    ]
    return "\n".join(out) + "\n"
