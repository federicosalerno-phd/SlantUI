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

from pathlib import Path

__all__ = ["STYLESHEETS", "HERE", "path", "bundle"]

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
