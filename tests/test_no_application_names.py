"""Nothing in this repository names an application that uses it.

The attribution runs one way. An application built on SlantUI says so, in its
own README and its own about box, and the licence makes the credit line part
of the deal. SlantUI says nothing about who uses it: not in the README, not in
a docstring, not in a comment, not in a palette note that ships inside the
package, not in a test fixture.

The names are held here as SHA-256 of the lowercased word, because writing one
of them into this file is the thing the file exists to prevent. A word and the
pair of words either side of it are both checked, so a two word name is caught
as well.

To add one:

    python -c "import hashlib; print(hashlib.sha256(input().strip().lower().encode()).hexdigest())"

and paste the digest below with a comment saying what kind of thing it is.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

BANNED = {
    # the applications this design was worn by before it was a library, one
    # digest per name and one for the two word name written as one word
    "7ab686e3c43cffc6e35fe68ca3db0349648d47d7dca4903b6c922bd31a75b55f",
    "0b5e00d0feffa91e534d7144df43d09c40d754d0c46b331b01cc92bce0cea91e",
    "cbdb0f811392ef0aef6a961a749af93154b6111de4133fa62dfda14f0b2018e7",
    "55a8f4f0b845f79e36973d3f6c1edc7231259fecaa941b8eb395e2bc0460e34a",
    # two words out of what they are for, which is not what this library is for
    "0ff9a28899c7e3d06cc5134bf825cd989c70c984ba0f00f74e3d60c1d20260c3",
    "f0732c6150d99ef8800fe8b489c767dfc7835d5242d098a6c730b8e3c4922851",
}

SUFFIXES = {".py", ".md", ".css", ".js", ".html", ".toml", ".cfg", ".txt",
            ".yml", ".yaml", ".json", ".ps1", ".psm1", ".psd1", ".xaml",
            ".uss", ".qml", ""}

_WORD = re.compile(r"[a-z][a-z0-9]*")


def digest(word: str) -> str:
    return hashlib.sha256(word.strip().lower().encode()).hexdigest()


def _tracked() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split("\0")
        paths = [ROOT / p for p in out if p]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in ROOT.rglob("*")
                 if not {".git", ".venv", "__pycache__"} & set(p.parts)]
    return sorted(p for p in paths
                  if p.is_file() and p.suffix.lower() in SUFFIXES
                  and p.resolve() != SELF)


FILES = _tracked()
IDS = [p.relative_to(ROOT).as_posix() for p in FILES]


def names_in(text: str) -> set[str]:
    """Every banned name the text holds, as the digest that caught it."""
    words = _WORD.findall(text.lower())
    found = {digest(w) for w in set(words)} & BANNED
    pairs = {f"{a} {b}" for a, b in zip(words, words[1:])}
    return found | ({digest(p) for p in pairs} & BANNED)


def test_the_check_would_catch_something():
    """A linter that cannot fire is decoration. The word below is built from
    its characters so that this file does not contain it."""
    word = "".join(chr(c) for c in (105, 109, 116, 111, 112))
    assert digest(word) in BANNED
    assert names_in(f"ported from {word} last") == {digest(word)}
    assert not names_in("a window look, as a library")


def test_there_is_something_to_check():
    assert len(FILES) > 10, "the scan found almost nothing, so it is not scanning"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_no_file_names_an_application(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = names_in(text + " " + path.relative_to(ROOT).as_posix().replace("/", " "))
    assert not hits, (
        f"{path.relative_to(ROOT).as_posix()} names an application that uses "
        f"this library ({len(hits)} of them). The attribution runs the other "
        f"way: an application credits SlantUI, and SlantUI credits nobody.")
