"""What an installed copy of the library has to carry.

Everything in ``slantui`` that is not Python is carried by a pattern in
``[tool.setuptools.package-data]``. A file that no pattern matches is in the
repository, passes every other test here, and is missing from the wheel, where
the first person to find it is somebody who installed the package. So the
patterns are checked against what is actually in the folder.

The version is written in two places, because a build backend reads the one in
``pyproject.toml`` and the library reports the other. They have to agree, and
``slantui/design.json`` carries it into every export, so it comes third.

``PYPI.md`` is the description an index shows. It is generated, and it is the
one file here that nothing renders until the package is published, which is
the definition of a file that goes stale in silence.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

import slantui

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(slantui.__file__).resolve().parent
PYPROJECT = ROOT / "pyproject.toml"

sys.path.insert(0, str(ROOT / "tools"))
import pypi_readme  # noqa: E402  the generator of the file two tests below check

# Files that belong to the checkout and not to the package. The README in each
# folder is a note to somebody reading the source; the documentation people
# read is on the repository, and none of it is used at run time.
IGNORED = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".py", ".pyc", ".pyo", ".md"}

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
_HTML_IMAGE = re.compile(r"<img[^>]*?src=\"([^\"]+)\"", re.IGNORECASE)
_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")


def _package_data_patterns() -> list[str]:
    """The globs under [tool.setuptools.package-data] for the slantui package."""
    text = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"\[tool\.setuptools\.package-data\](.*?)(\n\[|\Z)", text, re.DOTALL)
    assert block, "pyproject.toml has no package-data section any more"
    entry = re.search(r"slantui\s*=\s*\[(.*?)\]", block.group(1), re.DOTALL)
    assert entry, "the slantui package carries no data patterns any more"
    return re.findall(r'"([^"]+)"', entry.group(1))


def _version_in_pyproject() -> str:
    """Read without tomllib, which Python 3.10 does not have."""
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml has no version"
    return m.group(1)


def test_the_two_versions_agree():
    assert _version_in_pyproject() == slantui.__version__, (
        "pyproject.toml and slantui/__init__.py give different versions. An "
        "install then reports one number and the index carries another.")


def test_the_design_data_carries_the_version():
    """``design.json`` is generated, and every export target stamps it."""
    import json

    data = json.loads((PKG / "design.json").read_text(encoding="utf-8"))
    assert data["slantui"] == slantui.__version__, (
        "slantui/design.json was written by another version. Run: "
        "python -m slantui.tokens json -o slantui/design.json")


def test_the_description_the_index_shows_is_current():
    assert (ROOT / "PYPI.md").read_text(encoding="utf-8") == pypi_readme.current(), (
        "PYPI.md is behind README.md. Run: python tools/pypi_readme.py")


def test_the_description_the_index_shows_points_at_nothing_relative():
    """An index is not a repository. A relative path in the description draws
    a broken image on the project page and a dead link under it."""
    text = (ROOT / "PYPI.md").read_text(encoding="utf-8")
    refs = _MD_IMAGE.findall(text) + _HTML_IMAGE.findall(text) + _MD_LINK.findall(text)
    assert len(refs) > 20, "almost no links found, so this is reading the wrong file"
    relative = [r for r in refs
                if not r.startswith(("http:", "https:", "data:", "mailto:", "#"))]
    assert not relative, ("the index would draw these as broken:\n  "
                          + "\n  ".join(relative))


def test_the_readme_itself_stays_relative():
    """The other half of the deal. GitHub resolves repository relative paths,
    the pictures live in this repository, and docs/publish.py is what puts them
    there, so the README keeps them relative and only the generated copy moves.
    """
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    images = _MD_IMAGE.findall(text) + _HTML_IMAGE.findall(text)
    absolute = [i for i in images if i.startswith(("http:", "https:"))]
    assert not absolute, ("README.md points at pictures outside the repository, "
                          "which docs/publish.py cannot carry:\n  "
                          + "\n  ".join(absolute))


def test_every_file_the_package_carries_is_in_the_wheel():
    patterns = _package_data_patterns()
    assert patterns, "no patterns, so this test is checking nothing"

    missed = []
    for path in sorted(PKG.rglob("*")):
        if not path.is_file() or path.suffix in IGNORED_SUFFIXES:
            continue
        if IGNORED & set(path.parts):
            continue
        rel = path.relative_to(PKG).as_posix()
        if not any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            missed.append(rel)
    assert not missed, (
        "these files are in slantui/ and no package-data pattern matches them, "
        "so pip would install the package without them:\n  "
        + "\n  ".join(missed)
        + "\nAdd a pattern in pyproject.toml.")


def test_the_patterns_all_match_something():
    """A pattern for a folder that was renamed is a file quietly left out."""
    patterns = _package_data_patterns()
    empty = [pat for pat in patterns
             if not any(fnmatch.fnmatch(p.relative_to(PKG).as_posix(), pat)
                        for p in PKG.rglob("*") if p.is_file())]
    assert not empty, ("these package-data patterns match nothing: "
                       + ", ".join(empty))
