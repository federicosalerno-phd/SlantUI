"""SlantUI for WPF: where the PowerShell module and its data live.

Two of his applications are WPF windows written in PowerShell, and neither
can import a Python package while it is running. What they get instead is a
pair of files sitting inside the installed package, which they copy or dot
source:

    from slantui.wpf import FILES, path, install

    path("SlantUI.psm1")        the module, hand written
    path("SlantUI.Tokens.psd1") the palettes and the metrics, generated
    install(somewhere)          both of them copied there, paths returned

``install`` is what an application's build step calls. It is the WPF answer
to the three lines ``examples/tour/main.py`` uses to put the stylesheets
next to its page: the files ship inside the package, and the application
puts a copy where its own code can reach it.
"""
from __future__ import annotations

import shutil
from pathlib import Path

__all__ = ["FILES", "HERE", "MODULE", "DATA", "path", "install"]

HERE = Path(__file__).resolve().parent

MODULE = "SlantUI.psm1"
DATA = "SlantUI.Tokens.psd1"

# The module first, since it is the one an application imports.
FILES: tuple[str, ...] = (MODULE, DATA)


def path(name: str) -> Path:
    """The absolute path of one of the two files, inside the package."""
    if name not in FILES:
        raise KeyError(f"{name!r} is not a SlantUI WPF file. Known: {', '.join(FILES)}")
    return HERE / name


def install(folder: str | Path) -> list[Path]:
    """Copy both files into a folder and say where they landed."""
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(path(n), out / n)) for n in FILES]
