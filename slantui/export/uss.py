"""The palettes and the metrics as Unity UI Toolkit style sheets.

Unity styles with USS, which is a subset of CSS with custom properties in it,
so the token layer crosses over almost unchanged: a role is a custom property
and a component reads it with ``var()``, exactly as on the web. The palettes
keep their switch as well. USS has no attribute selector, so where the page
keys a palette on ``data-palette`` a Unity project keys it on a class, and
switching palette is adding ``slant-teal-dark`` to the root visual element.

Two things do not cross and are left out on purpose.

**The fonts.** USS wants a font asset, through ``resource()`` or ``url()``,
and a family name means nothing to it. A project points the property at its
own asset, and the file says where. The lengths and the durations do cross:
USS takes both in the units the stylesheet writes.

**``color-scheme``.** It tells a browser engine how to paint the controls it
draws itself. Unity draws all of its own, so there is nothing to tell.

This target has not been opened in a Unity project. The syntax is USS and the
values are the same ones every other target gets, and that is as far as the
claim goes until someone builds with it.
"""
from __future__ import annotations

from ..tokens.metrics import GROUPS, METRICS
from ..tokens.palette import Palette
from ..tokens.palettes import DEFAULT, PALETTES
from ..tokens.roles import ROLES

__all__ = ["as_uss", "uss_class"]

_HEADER = """\
/* SlantUI for Unity's UI Toolkit.
   Written by `python -m slantui.tokens uss -o PATH` from
   slantui/tokens/palettes.py and slantui/tokens/metrics.py.

   The first block is the default palette and applies everywhere. Every other
   palette is a class: put it on the root visual element and every var() under
   it follows.

       root.AddToClassList("slant-high-contrast");

   The fonts are not here. USS wants a font asset and not a family name, so a
   project sets -unity-font-definition on its own root from its own asset. The
   names the design uses are in the metrics: font, font-brand, font-credit
   and mono. */
"""


def uss_class(slug: str) -> str:
    """The class a palette is switched on with."""
    return f"slant-{slug}"


def _roles_block(p: Palette, selector: str, indent: str = "    ") -> str:
    lines = [f"/* {p.name}, {p.scheme} */", f"{selector} {{"]
    group = None
    for r in ROLES:
        if r.group != group:
            group = r.group
            lines.append(f"{indent}/* {group} */")
        lines.append(f"{indent}--{r.name}: {p[r.name]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _metrics_block(indent: str = "    ") -> str:
    lines = ["/* metrics. The same on every palette. */", ":root {"]
    group = None
    for m in METRICS:
        if m.kind == "font":
            continue
        if m.group != group:
            group = m.group
            lines.append(f"{indent}/* {GROUPS[group]} */")
        lines.append(f"{indent}--{m.name}: {m.value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def as_uss(palettes: list[Palette] | None = None,
           default_slug: str | None = None) -> str:
    """Every palette given, or all eight, with the metrics under them."""
    chosen = list(palettes if palettes is not None else PALETTES.values())
    default_slug = default_slug or (DEFAULT.slug if len(chosen) > 1 else chosen[0].slug)

    out = [_HEADER]
    for p in chosen:
        selector = ":root" if p.slug == default_slug else "." + uss_class(p.slug)
        out.append(_roles_block(p, selector))
    out.append(_metrics_block())
    return "\n".join(out)
