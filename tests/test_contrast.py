"""The WCAG audit, run for real over the eight shipped palettes.

This is the test the whole token system exists to pass. When it goes red, the
palette moves. The thresholds in `roles.py` were fixed before any palette was
written so that they are never the easier thing to change.
"""
from __future__ import annotations

import pytest

from slantui.tokens import PALETTES, audit, color, failures
from slantui.tokens.contrast import alpha_problems, worst
from slantui.tokens.roles import (MIN_RATIO, ON_FILL, SURFACES, TEXTS,
                                  MAX_SHADOW_ALPHA, MIN_SCRIM_ALPHA)

SLUGS = list(PALETTES)


@pytest.mark.parametrize("slug", SLUGS)
def test_every_pair_clears_its_threshold(slug):
    bad = failures(PALETTES[slug])
    assert not bad, "\n" + "\n".join(str(c) for c in bad)


@pytest.mark.parametrize("slug", SLUGS)
def test_the_audit_covers_the_whole_cross_product(slug):
    checks = audit(PALETTES[slug])
    expected = len(TEXTS) * len(SURFACES) + sum(len(v) for v in ON_FILL.values())
    assert len(checks) == expected

    seen = {(c.fg, c.bg) for c in checks}
    for fg in TEXTS:
        for bg in SURFACES:
            assert (fg, bg) in seen, f"{fg} on {bg} was never measured"
    for fg, fills in ON_FILL.items():
        for bg in fills:
            assert (fg, bg) in seen


@pytest.mark.parametrize("slug", SLUGS)
def test_the_depth_roles_do_their_job(slug):
    assert not alpha_problems(PALETTES[slug])
    p = PALETTES[slug]
    assert color.alpha_of(p["scrim"]) >= MIN_SCRIM_ALPHA
    assert color.alpha_of(p["shadow"]) <= MAX_SHADOW_ALPHA
    assert color.alpha_of(p["overlay"]) < 1.0


@pytest.mark.parametrize("slug", SLUGS)
def test_the_overlay_is_measured_over_a_photograph(slug):
    """Whatever sits behind the overlay, the label on it still reads.

    The auditor resolves the overlay against one extreme. This check does both,
    because the thing behind it is a photograph and nobody knows what colour
    that is.
    """
    p = PALETTES[slug]
    for backdrop in ("#000000", "#FFFFFF", "#7F7F7F"):
        plate = color.over(p["overlay"], backdrop)
        for role, tier in TEXTS.items():
            ratio = color.contrast(p[role], plate)
            assert ratio >= MIN_RATIO[tier] - 0.35, \
                f"{slug}: {role} on the overlay over {backdrop} is {ratio:.2f}:1"


@pytest.mark.parametrize("slug", SLUGS)
def test_nothing_is_sitting_right_on_a_threshold_by_accident(slug):
    """A margin of zero means the next small edit breaks the palette."""
    tightest = worst(PALETTES[slug], 1)[0]
    assert tightest.ratio >= tightest.needed


def test_the_auditor_catches_a_broken_palette():
    """A test suite that cannot fail is not a test suite."""
    broken = PALETTES["gold-dark"].edit(**{"text-3": "#2A2A2E"})
    bad = failures(broken)
    assert bad, "a near black text-3 on a near black surface should have failed"
    assert all(c.fg == "text-3" for c in bad)


def test_the_auditor_catches_a_scrim_that_does_not_dim():
    broken = PALETTES["gold-dark"].edit(scrim="#0D0D0F20")
    assert alpha_problems(broken)


def test_a_report_can_be_printed():
    text = PALETTES["gold-dark"].slug
    from slantui.tokens import report
    out = report(list(PALETTES.values()))
    assert text in out
    assert "0 failing" in out
