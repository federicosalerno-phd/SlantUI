"""SlantUI for WPF: where the PowerShell module, its data and its splash live.

Two of his applications are WPF windows written in PowerShell, and neither
can import a Python package while it is running. They import the PowerShell
module instead, FROM WHERE THE LIBRARY IS INSTALLED, and never from a copy of
their own: a copy is a second SlantUI, it is behind the first the day the
library changes, and the whole point of the library is that there is one.

    from slantui.wpf import FILES, path, where, register

    path("SlantUI.psm1")         the module, hand written
    path("SlantUI.Tokens.psd1")  the palettes and the metrics, generated
    path("SlantUI.Splash.cs")    the splash's drawing thread, compiled on
                                 first use into the user's local data
    where()                      the folder all three are in
    register()                   that folder written down where a PowerShell
                                 application can read it, POINTER

A PowerShell script cannot ask Python where a package is without starting
Python, which costs a noticeable part of a second at every start. So the
library writes its own address once, in the user's local data, and an
application reads one line:

    python -m slantui.wpf register

    $dove = Get-Content "$env:LOCALAPPDATA\\SlantUI\\wpf.path"
    Import-Module (Join-Path $dove 'SlantUI.psm1')

Installed editable (``pip install -e``), which is how the library is used on
its author's machine, the address is the checkout, so an edit to the module
reaches every application at its next start and nothing is copied anywhere.
An application that finds the pointer missing, or pointing at nothing, runs
the register command itself before it gives up.

The C# file is not optional extra: Show-SlantSplash compiles it the first
time it runs, because WPF beats its animations on the Dispatcher and a
window that loads on its own thread stops every one of them. The splash
therefore draws on a thread of its own, and that thread is what this file
is. It is compiled into the user's local data, not beside the module, so the
library's folder is only ever read.

``install`` copies the three files into a folder. It is here for the
library's own tests, which build windows out of a throwaway folder, and for a
build that has to carry the files to a machine the library is not installed
on. An application on a machine that has the library does not call it.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

__all__ = ["FILES", "HERE", "MODULE", "DATA", "SPLASH", "POINTER", "path",
           "where", "register", "install"]

HERE = Path(__file__).resolve().parent

MODULE = "SlantUI.psm1"
DATA = "SlantUI.Tokens.psd1"
SPLASH = "SlantUI.Splash.cs"

# The module first, since it is the one an application imports.
FILES: tuple[str, ...] = (MODULE, DATA, SPLASH)

# Where the library's address is written for PowerShell to read: beside the
# compiled splash, in the one folder that is the library's in the user's data.
POINTER = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") \
    / "SlantUI" / "wpf.path"


def path(name: str) -> Path:
    """The absolute path of one of the shipped files, inside the package."""
    if name not in FILES:
        raise KeyError(f"{name!r} is not a SlantUI WPF file. Known: {', '.join(FILES)}")
    return HERE / name


def where() -> Path:
    """The folder the module, its data and its splash are in."""
    return HERE


def register(pointer: str | Path | None = None) -> Path:
    """Write the library's address where a PowerShell application reads it.

    One line, the folder, in UTF-8 with no byte order mark and no newline, so
    ``Get-Content -Raw`` and ``.Trim()`` read the same thing. Returns the file
    written.
    """
    out = Path(pointer) if pointer is not None else POINTER
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(str(HERE), encoding="utf-8")
    return out


def install(folder: str | Path) -> list[Path]:
    """Copy the files into a folder and say where they landed. For the
    library's tests and for a build carried to a machine without the library;
    not for an application that can import the module where it is."""
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(path(n), out / n)) for n in FILES]
