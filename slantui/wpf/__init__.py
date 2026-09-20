"""SlantUI for WPF: where the PowerShell module, its data and its splash live.

Two of his applications are WPF windows written in PowerShell, and neither
can import a Python package while it is running. What they get instead is a
set of files sitting inside the installed package, which they copy or dot
source:

    from slantui.wpf import FILES, path, install

    path("SlantUI.psm1")         the module, hand written
    path("SlantUI.Tokens.psd1")  the palettes and the metrics, generated
    path("SlantUI.Splash.cs")    the splash's drawing thread, compiled on
                                 first use into the user's local data
    install(somewhere)           all of them copied there, paths returned

``install`` is what an application's build step calls. It is the WPF answer
to the three lines ``examples/tour/main.py`` uses to put the stylesheets
next to its page: the files ship inside the package, and the application
puts a copy where its own code can reach it.

The C# file is not optional extra: Show-SlantSplash compiles it the first
time it runs, because WPF beats its animations on the Dispatcher and a
window that loads on its own thread stops every one of them. The splash
therefore draws on a thread of its own, and that thread is what this file
is.
"""
from __future__ import annotations

import shutil
from pathlib import Path

__all__ = ["FILES", "HERE", "MODULE", "DATA", "SPLASH", "path", "install"]

HERE = Path(__file__).resolve().parent

MODULE = "SlantUI.psm1"
DATA = "SlantUI.Tokens.psd1"
SPLASH = "SlantUI.Splash.cs"

# The module first, since it is the one an application imports.
FILES: tuple[str, ...] = (MODULE, DATA, SPLASH)


def path(name: str) -> Path:
    """The absolute path of one of the shipped files, inside the package."""
    if name not in FILES:
        raise KeyError(f"{name!r} is not a SlantUI WPF file. Known: {', '.join(FILES)}")
    return HERE / name


def install(folder: str | Path) -> list[Path]:
    """Copy the files into a folder and say where they landed."""
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(path(n), out / n)) for n in FILES]
