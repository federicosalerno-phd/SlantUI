"""The palettes and the metrics rendered as CSS.

The custom property for a role is the role name with two dashes in front, with
no prefix on it. SlantUI owns the page it is loaded into, and an unprefixed
name is what makes a stylesheet readable: `var(--surface-2)` says the thing,
`var(--sl-surface-2)` says the thing and the vendor. A metric is written the
same way, and the two vocabularies never overlap.

`color-scheme` is emitted alongside, because the engine draws a few controls
itself (the number field's stepper is the one that shows) and paints them from
that property alone.
"""
from __future__ import annotations

import textwrap

from .metrics import GROUP_NOTES, GROUPS, METRICS
from .palette import Palette
from .roles import ROLES

__all__ = ["render", "render_all", "stylesheet", "variable", "HEADER",
           "render_metrics", "metrics_stylesheet", "METRICS_HEADER"]

# The first lines of the file that ships in slantui/css. Anyone who opens it
# should learn in one glance that editing it is pointless.
HEADER = """\
/* SlantUI palettes.
   Written by `python -m slantui.tokens css -o slantui/css/palettes.css` from
   slantui/tokens/palettes.py. Edit the Python and run that; a test fails
   while this file is behind it. */
"""

METRICS_HEADER = """\
/* SlantUI metrics: radii, type, and the geometry of the shell.
   Written by `python -m slantui.tokens metrics -o slantui/css/metrics.css`
   from slantui/tokens/metrics.py. Edit the Python and run that; a test fails
   while this file is behind it.

   Everything here is a length or a font and is the same on every palette. The
   colours are in palettes.css. An application that wants a wider side panel or
   a taller band redefines the property after this file is loaded, and every
   rule that reads it follows.

   The Python holds them because a toolkit that is not a browser cannot read a
   stylesheet, and the four numbers under "the title band" are the shape of the
   band itself. slantui/export writes the same values for WPF, for Unity and as
   plain data. */
"""

_GROUP_TITLES = {
    "surface": "surfaces, furthest back first",
    "control": "controls",
    "text": "text, brightest to faintest",
    "accent": "accent",
    "status": "status",
    "depth": "depth. these three carry an alpha",
}


def variable(role: str) -> str:
    """The custom property a role is written as."""
    return f"--{role}"


def render(palette: Palette, selector: str = ":root", indent: str = "  ") -> str:
    """One palette as a single rule, grouped and commented."""
    lines = [f"/* {palette.name}"]
    if palette.note:
        lines.append(f"   {palette.note}")
    lines.append(f"   {palette.scheme}, {len(palette.values)} roles */")
    lines.append(f"{selector}{{")
    lines.append(f"{indent}color-scheme:{palette.scheme};")

    group = None
    width = max(len(variable(r.name)) for r in ROLES) + 1
    for r in ROLES:
        if r.group != group:
            group = r.group
            lines.append(f"{indent}/* {_GROUP_TITLES[group]} */")
        name = variable(r.name) + ":"
        lines.append(f"{indent}{name:<{width}}{palette[r.name]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_all(palettes: list[Palette], default_slug: str | None = None) -> str:
    """Every palette in one file: the default on `:root`, the rest keyed.

    A page switches palette by setting `data-palette` on the document element.
    Nothing else in the stylesheet changes, because nothing else names a
    colour.
    """
    default_slug = default_slug or palettes[0].slug
    out = []
    for p in palettes:
        if p.slug == default_slug:
            out.append(render(p, ":root"))
        else:
            out.append(render(p, f':root[data-palette="{p.slug}"]'))
    return "\n".join(out)


def stylesheet(palettes: list[Palette], default_slug: str | None = None) -> str:
    """`render_all` with the header on top: the text of slantui/css/palettes.css."""
    return HEADER + "\n" + render_all(palettes, default_slug)


# ── the metrics ─────────────────────────────────────────────────────────────
# A declaration carries its purpose next to it where the line stays readable,
# and above it where it does not. The width below is where that line is drawn.
_WIDE = 92


def render_metrics(selector: str = ":root", indent: str = "  ") -> str:
    """Every metric as a single rule, grouped, with each one's purpose on it."""
    lines = [f"{selector}{{"]
    # The column the purposes line up in, set by the short declarations. A
    # font stack is four times the length of a radius, and letting it set the
    # column would push every comment off the edge and lose them all to the
    # block form below.
    lengths = [len(variable(m.name)) + len(m.value) + 2 for m in METRICS]
    width = max([n for n in lengths if n <= 28] or lengths) + 2

    group = None
    for m in METRICS:
        if m.group != group:
            if group is not None:
                lines.append("")
            group = m.group
            lines.append(f"{indent}/* {GROUPS[group]} */")
            note = GROUP_NOTES.get(group)
            if note:
                for line in note.splitlines():
                    lines.append(f"{indent}/* {line} */" if line else f"{indent}/* */")
        decl = f"{variable(m.name)}:{m.value};"
        inline = f"{indent}{decl:<{width}}/* {m.purpose} */"
        if len(inline) <= _WIDE:
            lines.append(inline)
            continue
        for line in textwrap.wrap(m.purpose, _WIDE - len(indent) - 6):
            lines.append(f"{indent}/* {line} */")
        lines.append(f"{indent}{decl}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def metrics_stylesheet() -> str:
    """The text of slantui/css/metrics.css."""
    return METRICS_HEADER + "\n" + render_metrics()
