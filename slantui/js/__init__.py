"""The browser side scripts, and where an application finds them.

    from slantui.js import SCRIPTS, path, bundle

    SCRIPTS              the six file names, in the order a page loads them
    path("bridge.js")    the absolute path of one, inside the installed package
    bundle()             all six in that order, as one string

They are classic scripts, not modules: a page served from file:// gets no
module loading, and the embedded browser serves from file://. Each one leaves
a few names on the window, listed at the top of the file.
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["SCRIPTS", "HERE", "path", "bundle"]

HERE = Path(__file__).resolve().parent

# Load order. icons.js stands alone and goes first, because widgets.js and
# titlebar.js both ask it for a drawing. theme.js stands alone. bridge.js
# stands alone. titlebar.js calls be() and Bridge.on() from bridge.js, so it
# comes after it. sounds.js puts its switch on the band and asks icons.js for
# its two drawings, so it comes last.
SCRIPTS: tuple[str, ...] = (
    "icons.js",
    "theme.js",
    "bridge.js",
    "widgets.js",
    "titlebar.js",
    "sounds.js",
)


def path(name: str) -> Path:
    """The absolute path of one script."""
    if name not in SCRIPTS:
        raise KeyError(f"{name!r} is not a SlantUI script. Known: {', '.join(SCRIPTS)}")
    return HERE / name


def bundle() -> str:
    """Every script, in load order, as one string a page can inline."""
    return "\n".join(path(n).read_text(encoding="utf-8") for n in SCRIPTS)
