"""Nothing in this repository is allowed to read like machine writing.

The repository is public and carries one person's name, so the standard
applies to the README, to the licence, to commit ready documentation and to
every code comment and docstring. There is no exemption for comments.

The list below is not a style preference. Each entry is a phrase that shows up
constantly in generated text and almost never in someone's own writing, so a
reader who finds three of them stops believing the rest. Anything caught here
has a plain replacement: an em dash is a comma, a colon or a full stop,
"rather than" is "instead of" or nothing at all, and a throat clearing
connective is a deleted word.

This file exempts itself, because it has to name the words to find them.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

TEXT_SUFFIXES = {".py", ".md", ".css", ".js", ".html", ".toml", ".cfg", ".txt",
                 ".yml", ".yaml", ".json", ".ps1", ".psm1", ".psd1", ".xaml",
                 ".uss", ".qml", ""}

# Punctuation that gives it away at a glance.
BANNED_CHARS = {
    "—": "em dash. Use a comma, a colon or two sentences.",
    "–": "en dash. Use a plain hyphen or the word 'to'.",
    "…": "ellipsis character. Use three full stops if it is really needed.",
    "“": "curly quote. Use a straight one.",
    "”": "curly quote. Use a straight one.",
    "’": "curly apostrophe. Use a straight one.",
}

# Phrases, matched case insensitively on a word boundary.
BANNED_PHRASES = (
    "rather than",
    "not only",
    "it is worth noting",
    "it's worth noting",
    "it is important to note",
    "delve",
    "seamless",
    "leverage",
    "leveraging",
    "in today's",
    "in the world of",
    "a testament to",
    "navigate the complexities",
    "unlock the",
    "unleash",
    "elevate your",
    "game changer",
    "game-changer",
    "cutting edge",
    "cutting-edge",
    "moreover",
    "furthermore",
    "deep dive",
    "dive into",
    "plethora",
    "myriad",
    "harness the power",
    "streamline",
    "boasts",
    "tapestry",
    "showcase",
    "showcasing",
    "pivotal",
    "holistic",
    "synergy",
    "paradigm",
    "revolutionize",
    "revolutionise",
    "empower",
    "robust and",
    "but rather",
    "not merely",
    "at its core",
    "when it comes to",
    "the key is",
    "best practices",
)

# Nothing in a tracked file says a tool was involved.
BANNED_CREDITS = ("co-authored-by", "generated with", "ai-generated",
                  "written by an ai")

# A phrase is matched across a line break too: "rather" at the end of one line
# and "than" at the start of the next is still the phrase.
_PHRASE = re.compile(
    "|".join(r"\b" + r"\s+".join(re.escape(w) for w in p.split()) + r"\b"
             for p in BANNED_PHRASES),
    re.IGNORECASE)
_CREDIT = re.compile("|".join(re.escape(c) for c in BANNED_CREDITS), re.IGNORECASE)


def _tracked_files() -> list[Path]:
    """Every text file that would end up in the repository.

    `--others --exclude-standard` picks up files that are staged for nothing
    yet, so the check works before the first commit, and honours .gitignore, so
    a virtual environment sitting in the working tree is not scanned.
    """
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
                  if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
                  and p.resolve() != SELF)


FILES = _tracked_files()


def test_there_is_something_to_check():
    assert len(FILES) > 10, "the scan found almost nothing, so it is not scanning"


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_banned_punctuation(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = []
    for n, line in enumerate(text.splitlines(), start=1):
        for ch, why in BANNED_CHARS.items():
            if ch in line:
                hits.append(f"{path.relative_to(ROOT)}:{n}  {why}\n    {line.strip()}")
    assert not hits, "\n" + "\n".join(hits)


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_banned_phrases(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    hits = []
    for m in _PHRASE.finditer(text):
        n = text.count("\n", 0, m.start()) + 1
        hits.append(f"{path.relative_to(ROOT)}:{n}  {m.group(0)!r}\n"
                    f"    {lines[n - 1].strip()}")
    assert not hits, "\n" + "\n".join(hits)


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_nothing_credits_a_tool(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = [f"{path.relative_to(ROOT)}: {m.group(0)!r}" for m in _CREDIT.finditer(text)]
    assert not hits, "\n" + "\n".join(hits)


def test_the_check_would_catch_something(tmp_path: Path):
    """A linter that cannot fire is decoration."""
    sample = "This approach is seamless — rather than the old one."
    assert any(ch in sample for ch in BANNED_CHARS)
    assert len(_PHRASE.findall(sample)) == 2
    assert len(_PHRASE.findall("written out rather\n  than pulled in")) == 1
