"""The stylesheets, and where an application finds them.

    from slantui.css import STYLESHEETS, path, bundle

    STYLESHEETS          the five file names, in the order a page loads them
    path("base.css")     the absolute path of one, inside the installed package
    bundle()             all five in that order, as one string

palettes.css is written by ``python -m slantui.tokens css -o`` from the
palettes in Python; the other four are written by hand. A test fails when the
written one is behind the Python.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

__all__ = ["STYLESHEETS", "HERE", "path", "bundle", "BAND_PARTS", "declarations", "band_roles"]

HERE = Path(__file__).resolve().parent

# Load order. The first two define the custom properties, base resets the
# document and reads them, layout builds the shell, components the widgets.
# A later file may read anything an earlier one defined.
STYLESHEETS: tuple[str, ...] = (
    "palettes.css",
    "metrics.css",
    "base.css",
    "layout.css",
    "components.css",
)


def path(name: str) -> Path:
    """The absolute path of one stylesheet."""
    if name not in STYLESHEETS:
        raise KeyError(f"{name!r} is not a SlantUI stylesheet. Known: {', '.join(STYLESHEETS)}")
    return HERE / name


def bundle() -> str:
    """Every stylesheet, in load order, as one string a page can inline."""
    return "\n".join(path(n).read_text(encoding="utf-8") for n in STYLESHEETS)


# The title band's parts, and the rule and the property that fill or ink each
# one. Two things draw the band that are not the page: the window, until the
# page has drawn its own (shell/band.py), and a WPF window, for good
# (wpf/SlantUI.psm1, through the data file). Both ask here which role a part
# is in, and the answer is read out of the stylesheet, so the role is written
# once, in the rule the page itself uses.
BAND_PARTS: dict[str, tuple[str, str]] = {
    "band": (".tbar-band", "background"),
    "name": (".tbar-name", "color"),
    "strong": (".tbar-name b", "color"),
    "credit": (".tbar-credit", "color"),
    "disc": (".tbar-logo-btn", "background"),
    "disc-hover": (".tbar-logo-btn:hover", "background"),
    "disc-down": (".tbar-logo-btn:active", "background"),
    "lift": (".tbar-logo-btn", "box-shadow"),
    "glyph": (".wbtn", "color"),
    "hover": (".wbtn:hover", "background"),
    "hover-glyph": (".wbtn:hover", "color"),
    "close": (".wbtn-close:hover", "background"),
    "close-glyph": (".wbtn-close:hover", "color"),
    # under the thin half while the window is empty, which is what the window
    # is while its own band is up
    "strip": ("html[data-splash=up] .titlebar", "background"),
}


def declarations(selector: str) -> dict[str, str]:
    """What the stylesheets declare for one selector, as the cascade has it
    when the specificity is the same: every rule whose selector list holds
    it, in load order, a later declaration winning over an earlier one."""
    out: dict[str, str] = {}
    code = re.sub(r"/\*.*?\*/", "", bundle(), flags=re.S)
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", code):
        if selector in [s.strip() for s in sel.split(",")]:
            for decl in body.split(";"):
                if ":" in decl:
                    k, v = decl.split(":", 1)
                    out[k.strip()] = " ".join(v.split())
    return out


@functools.lru_cache(maxsize=None)
def band_roles() -> dict[str, str]:
    """``{"band": "control", "name": "text-2", ...}``: the role each part of
    the band is in, read out of the rule in BAND_PARTS."""
    from ..tokens.roles import ROLE_NAMES
    out = {}
    for part, (selector, prop) in BAND_PARTS.items():
        value = declarations(selector).get(prop, "")
        roles = [r for r in re.findall(r"var\(--([a-z0-9-]+)\)", value) if r in ROLE_NAMES]
        if len(roles) != 1:
            raise RuntimeError(f"{selector} {{{prop}}} is not one role: {value!r}")
        out[part] = roles[0]
    return out
