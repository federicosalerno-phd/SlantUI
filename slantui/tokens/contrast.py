"""The WCAG auditor.

It measures every text role against every surface role of a palette and says
which pairs fall short. It is not advisory: `tests/test_contrast.py` fails the
build on a single shortfall, and the fix goes into the palette.

The thresholds live in `roles.py` and were fixed before any palette was
written, so that a palette is never the argument for lowering one.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import color
from .palette import Palette
from .roles import (MAX_SHADOW_ALPHA, MIN_RATIO, MIN_SCRIM_ALPHA, ON_FILL,
                    SURFACES, TEXTS, tier_of)

__all__ = ["Check", "audit", "failures", "report", "worst"]


@dataclass(frozen=True)
class Check:
    palette: str
    fg: str
    bg: str
    ratio: float
    needed: float
    tier: str

    @property
    def passed(self) -> bool:
        return self.ratio >= self.needed

    def __str__(self) -> str:
        mark = "ok  " if self.passed else "FAIL"
        return (f"{mark} {self.palette:<14} {self.fg:<20} on {self.bg:<22} "
                f"{self.ratio:5.2f} : 1   needs {self.needed:.1f}")


def audit(palette: Palette) -> list[Check]:
    """Every pair the contract covers, passing and failing alike."""
    out: list[Check] = []
    surfaces = palette.surfaces()

    for fg, tier in TEXTS.items():
        needed = MIN_RATIO[tier]
        value = palette[fg]
        for bg in SURFACES:
            out.append(Check(palette.slug, fg, bg,
                             color.contrast(value, surfaces[bg]), needed, tier))

    needed = MIN_RATIO["on-fill"]
    for fg, fills in ON_FILL.items():
        value = palette[fg]
        for bg in fills:
            out.append(Check(palette.slug, fg, bg,
                             color.contrast(value, palette[bg]), needed, "on-fill"))
    return out


def failures(palette: Palette) -> list[Check]:
    """Only the pairs that fall short, worst first."""
    bad = [c for c in audit(palette) if not c.passed]
    bad.sort(key=lambda c: c.ratio)
    return bad


def alpha_problems(palette: Palette) -> list[str]:
    """The two depth checks that are not contrast questions.

    A scrim that does not dim is not a scrim, and an opaque shadow is a
    rectangle drawn next to the popup.
    """
    out: list[str] = []
    scrim = color.alpha_of(palette["scrim"])
    if scrim < MIN_SCRIM_ALPHA:
        out.append(f"scrim is {scrim:.2f} opaque, needs at least {MIN_SCRIM_ALPHA:.2f}")
    shadow = color.alpha_of(palette["shadow"])
    if shadow > MAX_SHADOW_ALPHA:
        out.append(f"shadow is {shadow:.2f} opaque, needs at most {MAX_SHADOW_ALPHA:.2f}")
    return out


def worst(palette: Palette, count: int = 5) -> list[Check]:
    """The tightest pairs, whether they pass or not. Useful while tuning."""
    checks = sorted(audit(palette), key=lambda c: c.ratio / c.needed)
    return checks[:count]


def report(palettes: list[Palette], verbose: bool = False) -> str:
    """A printable summary, one block per palette."""
    lines: list[str] = []
    total = bad_total = 0
    for p in palettes:
        checks = audit(p)
        bad = [c for c in checks if not c.passed]
        alpha = alpha_problems(p)
        total += len(checks)
        bad_total += len(bad) + len(alpha)
        head = f"{p.slug:<14} {len(checks):>4} checks"
        if bad or alpha:
            lines.append(f"{head}   {len(bad) + len(alpha)} FAILING")
            lines.extend("    " + str(c) for c in sorted(bad, key=lambda c: c.ratio))
            lines.extend("    " + a for a in alpha)
        else:
            tight = worst(p, 1)[0]
            lines.append(f"{head}   all pass, tightest {tight.ratio:.2f}:1 "
                         f"({tight.fg} on {tight.bg})")
        if verbose:
            lines.extend("    " + str(c) for c in checks if c.passed)
    lines.append("")
    lines.append(f"{total} checks over {len(palettes)} palettes, {bad_total} failing")
    return "\n".join(lines)
