"""SlantUI's two level token system.

Level one is the palette: thirty concrete colours. Level two is the role: the
name a component is allowed to use. A component names a role and never a
colour, which is the whole reason the same stylesheet is right on a dark
palette and on a light one.

    from slantui.tokens import PALETTES, DEFAULT, audit, derive, render

    render(PALETTES["gold-dark"])          # a :root block
    failures(PALETTES["slate-light"])      # empty, and the tests keep it so
    derive(base=..., accent=..., text=..., ok=..., err=...)
"""
from __future__ import annotations

from .color import contrast, luminance, mix, over
from .contrast import Check, alpha_problems, audit, failures, report, worst
from .css import render, render_all, variable
from .generate import derive
from .palette import Palette
from .palettes import DEFAULT, PALETTES, by_scheme
from .roles import CORE, EXTENDED, MIN_RATIO, ROLES, ROLE_NAMES, SURFACES, TEXTS, Role

__all__ = [
    "Role", "ROLES", "ROLE_NAMES", "CORE", "EXTENDED", "SURFACES", "TEXTS",
    "MIN_RATIO",
    "Palette", "PALETTES", "DEFAULT", "by_scheme",
    "derive",
    "Check", "audit", "failures", "worst", "report", "alpha_problems",
    "render", "render_all", "variable",
    "contrast", "luminance", "mix", "over",
]
