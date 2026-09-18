"""The role layer: the names components are allowed to use.

A role says what a colour is for. It never says what the colour is, and it
never says which way the lightness goes. ``surface-3`` is the most raised
surface, which is lighter than the page on a dark palette and can be either on
a light one. A component that asks for ``surface-3`` is correct on all eight
palettes without knowing which one is loaded.

The core set is the agreed vocabulary. The extended set covers the cases the
core cannot express, and every one of them was added because a real widget
needed it, not because the set looked incomplete.

The contrast contract at the bottom of this file is what the auditor reads.
It is fixed before any palette is written, on purpose. When a palette fails
it, the palette moves.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Role", "ROLES", "ROLE_NAMES", "CORE", "EXTENDED",
    "SURFACES", "TEXTS", "ALPHA_ROLES", "ON_FILL",
    "TIERS", "MIN_RATIO", "tier_of",
]


@dataclass(frozen=True)
class Role:
    name: str
    group: str
    purpose: str
    extended: bool = False
    alpha: bool = False


ROLES: tuple[Role, ...] = (
    # ── surfaces, by how far forward they sit ───────────────────────────────
    Role("surface-0", "surface",
         "The window backdrop, the plane everything else sits on."),
    Role("surface-1", "surface",
         "Bands fixed to the window edge: title bar, step rail, side panel."),
    Role("surface-2", "surface",
         "Strips and toolbars inside the work area."),
    Role("surface-3", "surface",
         "The most raised plane: cards, popups, dialogs, panel headers."),

    # ── controls ────────────────────────────────────────────────────────────
    Role("control", "control",
         "The resting fill of a secondary control: buttons, tracks, thumbs."),
    Role("control-hover", "control",
         "The same control under the pointer."),
    Role("control-active", "control",
         "The same control while it is being pressed."),

    # ── text, brightest to faintest ─────────────────────────────────────────
    Role("text-1", "text",
         "Primary text: values, titles, the label on a hovered button."),
    Role("text-2", "text",
         "Secondary text: body copy, the label on a resting button."),
    Role("text-3", "text",
         "Captions, row labels, units, hints."),
    Role("text-4", "text",
         "The faintest text allowed: uppercase section labels, placeholders, "
         "disabled controls. Never a sentence."),

    # ── accent ──────────────────────────────────────────────────────────────
    Role("accent", "accent",
         "The one colour that marks the action moving the workflow forward."),
    Role("accent-hover", "accent",
         "The accent fill under the pointer."),
    Role("accent-active", "accent",
         "The accent fill while it is being pressed."),
    Role("on-accent", "accent",
         "Text and glyphs drawn on an accent fill."),
    Role("accent-text", "accent",
         "The accent used as a text colour, and as the focus ring. On light "
         "palettes this is a darker shade of the same hue than the fill.",
         extended=True),
    Role("accent-surface", "accent",
         "A surface tinted toward the accent: active tab, selected row, chip.",
         extended=True),
    Role("accent-surface-hover", "accent",
         "The same tinted surface under the pointer.", extended=True),

    # ── status ──────────────────────────────────────────────────────────────
    Role("ok", "status", "A filled indicator that something succeeded."),
    Role("warn", "status", "A filled indicator that something needs attention."),
    Role("err", "status", "A filled indicator that something failed."),
    Role("on-status", "status",
         "Text and glyphs drawn on an ok, warn or err fill.", extended=True),
    Role("ok-text", "status",
         "A success colour used as text, with no fill behind it.", extended=True),
    Role("warn-text", "status",
         "A warning colour used as text, with no fill behind it.", extended=True),
    Role("err-text", "status",
         "A failure colour used as text, with no fill behind it.", extended=True),
    Role("warn-surface", "status",
         "A surface tinted toward warn: the caution note, the chip on a "
         "condition the user should see before going on.", extended=True),
    Role("err-surface", "status",
         "A surface tinted toward err: the destructive button.", extended=True),
    Role("err-surface-hover", "status",
         "The same tinted surface under the pointer.", extended=True),

    # ── depth, the three that carry alpha ───────────────────────────────────
    Role("scrim", "depth",
         "Covers the work area while the application is busy.", alpha=True),
    Role("shadow", "depth",
         "The colour a popup casts. Used inside a box-shadow.", alpha=True),
    Role("overlay", "depth",
         "A plate drawn over content of an unknown colour, such as the label "
         "over a photograph.", alpha=True),
)

ROLE_NAMES: tuple[str, ...] = tuple(r.name for r in ROLES)
CORE: tuple[str, ...] = tuple(r.name for r in ROLES if not r.extended)
EXTENDED: tuple[str, ...] = tuple(r.name for r in ROLES if r.extended)
ALPHA_ROLES: tuple[str, ...] = tuple(r.name for r in ROLES if r.alpha)

_BY_NAME = {r.name: r for r in ROLES}


# ── the contrast contract ───────────────────────────────────────────────────
# Every surface a text role is allowed to land on. `overlay` is in the list
# because text really is drawn on it; it carries alpha, so the auditor
# composites it over black and over white and scores the worse of the two.
SURFACES: tuple[str, ...] = (
    "surface-0", "surface-1", "surface-2", "surface-3",
    "control", "control-hover", "control-active",
    "accent-surface", "accent-surface-hover",
    "warn-surface", "err-surface", "err-surface-hover",
    "overlay",
)

# Every text role, and the tier it is held to.
TEXTS: dict[str, str] = {
    "text-1": "body",
    "text-2": "body",
    "text-3": "body",
    "text-4": "minor",
    "accent-text": "body",
    "ok-text": "body",
    "warn-text": "body",
    "err-text": "body",
}

# The two foregrounds that belong to one fill each and are measured only there.
ON_FILL: dict[str, tuple[str, ...]] = {
    "on-accent": ("accent", "accent-hover", "accent-active"),
    "on-status": ("ok", "warn", "err"),
}

TIERS: dict[str, str] = {
    "body": "WCAG 2.2 AA for normal text.",
    "minor": "WCAG 2.2 AA for large text and for non text contrast. Only "
             "text-4 sits here, and only because it is barred from carrying "
             "a sentence.",
    "on-fill": "WCAG 2.2 AA for normal text, measured on its own fill.",
}

MIN_RATIO: dict[str, float] = {
    "body": 4.5,
    "minor": 3.0,
    "on-fill": 4.5,
}

# A scrim that does not dim is not a scrim, and a shadow that is opaque is a
# rectangle. Neither is a contrast question, so the auditor checks the alpha.
MIN_SCRIM_ALPHA = 0.60
MAX_SHADOW_ALPHA = 0.95


def tier_of(role: str) -> str:
    """The tier a text role is held to."""
    if role in TEXTS:
        return TEXTS[role]
    if role in ON_FILL:
        return "on-fill"
    raise KeyError(f"{role} is not a text role")


def role(name: str) -> Role:
    return _BY_NAME[name]
