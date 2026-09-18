"""The design, written out for a toolkit that is not a browser.

SlantUI started as two implementations of one design: the Python side, which
is the tokens and the Qt shell, and the web side, which is the stylesheets
and the scripts. That was enough while every application was a Qt window with
a page in it. It stopped being enough the moment the same look was wanted in
WPF, where a window draws the oblique band by hand and carries twenty one hex
values copied out of a stylesheet it cannot read.

The fix is not a second implementation of the design. It is one more output
of the one that exists. Every target here is written from
``slantui.tokens.palettes``, ``slantui.tokens.metrics`` and
``slantui.geometry``, so a colour corrected by the auditor reaches WPF in the
same commit it reaches the page.

    python -m slantui.tokens json                    the whole design as data
    python -m slantui.tokens xaml gold-dark          a WPF ResourceDictionary
    python -m slantui.tokens ps1                     a PowerShell data file
    python -m slantui.tokens uss gold-dark           Unity's UI Toolkit

None of it imports anything outside the standard library, which is the same
promise ``slantui.tokens`` makes: a machine with nothing installed can still
generate the palette for the toolkit it is about to build in.
"""
from __future__ import annotations

from .data import as_json, design
from .powershell import as_powershell
from .uss import as_uss
from .xaml import as_xaml, wpf_hex, xaml_key

__all__ = ["TARGETS", "render", "design", "as_json", "as_xaml", "as_powershell",
           "as_uss", "wpf_hex", "xaml_key"]

# Every target, by the name the command line uses, with the extension the
# file it writes usually carries.
TARGETS: dict[str, str] = {
    "json": ".json",
    "xaml": ".xaml",
    "ps1": ".psd1",
    "uss": ".uss",
}


def render(target: str, palettes: list, default_slug: str | None = None) -> str:
    """One target, by name. ``palettes`` is a list of ``Palette``."""
    if target == "json":
        return as_json(palettes, default_slug)
    if target == "xaml":
        return as_xaml(palettes, default_slug)
    if target == "ps1":
        return as_powershell(palettes, default_slug)
    if target == "uss":
        return as_uss(palettes, default_slug)
    raise KeyError(f"{target!r} is not a target. Known: {', '.join(TARGETS)}")
