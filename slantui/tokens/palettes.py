"""The eight palettes SlantUI ships.

Four are written out in full, because a design system you cannot read off the
page is a design system nobody trusts. The other four are the default with
another accent hue, which `Palette.with_accent` builds from the same formulas
the generator uses.

Every value here has been through `slantui.tokens.contrast.audit`, and
`tests/test_contrast.py` puts them through it again on every run. Where a
value differs from the one the design was drawn with, the comment next to it
says what the auditor measured.
"""
from __future__ import annotations

from .palette import Palette

__all__ = ["PALETTES", "DEFAULT", "by_scheme", "GOLD_DARK", "GOLD_LIGHT",
           "TEAL_DARK", "BLUE_DARK", "PURPLE_DARK", "GREEN_DARK",
           "SLATE_LIGHT", "HIGH_CONTRAST"]


# ── the default ─────────────────────────────────────────────────────────────
GOLD_DARK = Palette(
    name="Gold Dark",
    slug="gold-dark",
    scheme="dark",
    note="Gold on near black. It's the palette the design was drawn in.",
    values={
        "surface-0": "#0D0D0F",
        "surface-1": "#101013",
        "surface-2": "#121216",
        "surface-3": "#16161B",

        "control": "#1E1E24",
        "control-hover": "#33333B",
        "control-active": "#26262B",

        "text-1": "#E6E6EC",
        "text-2": "#C8C8D0",
        "text-3": "#A0A0AA",        # was #8A8A94, measured 3.70 on control-hover
        "text-4": "#80808A",        # was #4E4E57, measured 1.45 on control-hover

        "accent": "#F5C542",
        "accent-hover": "#FFD45E",
        "accent-active": "#C9A033",
        "on-accent": "#0D0D0F",
        "accent-text": "#F5C542",   # gold reads at 12:1 on this backdrop, so it stays
        "accent-surface": "#2A2519",
        "accent-surface-hover": "#332C1D",

        "ok": "#2F7A46",
        "warn": "#8F6410",
        "err": "#B0524A",
        "on-status": "#FFFFFF",
        "ok-text": "#58B36B",
        "warn-text": "#E0A93C",
        "err-text": "#F77D67",      # was #E8705B, measured 4.11 on control-hover
        "warn-surface": "#282218",  # err-surface turned to amber
        "err-surface": "#2C1F1E",
        "err-surface-hover": "#3A2724",

        "scrim": "#0D0D0FB8",
        "shadow": "#00000099",
        "overlay": "#101013F2",
    },
)


# ── the light twin ──────────────────────────────────────────────────────────
GOLD_LIGHT = Palette(
    name="Gold Light",
    slug="gold-light",
    scheme="light",
    note="The same gold on paper. The surfaces and the text are the ones a "
         "printed report uses.",
    values={
        "surface-0": "#EFEFF2",     # the page
        "surface-1": "#F1F1F4",     # the chip
        "surface-2": "#F7F7F9",     # the panel
        "surface-3": "#FFFFFF",     # the paper

        "control": "#DDDDE0",
        "control-hover": "#CECED1",
        "control-active": "#D6D6D9",

        "text-1": "#17171B",        # report.py --ink
        "text-2": "#3B3C40",
        "text-3": "#545458",        # report.py --dim #7A7A85 measured 4.24 on paper
        "text-4": "#6E6E73",

        "accent": "#F5C542",
        "accent-hover": "#E4B52B",  # on paper the accent darkens under the pointer
        "accent-active": "#D2A300",
        "on-accent": "#17171B",
        "accent-text": "#764A00",   # report.py --gold-ink #8A6A12 measured 3.42 on a grey control
        "accent-surface": "#FFF8E4",  # report.py --tint
        "accent-surface-hover": "#FCEFCD",

        "ok": "#2F7A46",            # report.py --gt
        "warn": "#8F6410",
        "err": "#B0524A",           # report.py --auto
        "on-status": "#FFFFFF",
        "ok-text": "#0F612F",
        "warn-text": "#7F4600",
        "err-text": "#913630",
        "warn-surface": "#F2EBE0",  # err-surface turned to amber
        "err-surface": "#F7E8E8",
        "err-surface-hover": "#F1DCDC",

        "scrim": "#EFEFF2B8",
        "shadow": "#00000038",
        "overlay": "#F1F1F4F2",
    },
)


# ── a neutral light palette, no gold in it anywhere ─────────────────────────
SLATE_LIGHT = Palette(
    name="Slate Light",
    slug="slate-light",
    scheme="light",
    note="Cool greys and a blue accent, for an application that should not "
         "look like the default.",
    values={
        "surface-0": "#E9EBEF",
        "surface-1": "#EDEFF3",
        "surface-2": "#F1F3F7",
        "surface-3": "#F5F7FB",

        "control": "#D7D9DD",
        "control-hover": "#C8CACE",
        "control-active": "#D0D2D6",

        "text-1": "#1A1C22",
        "text-2": "#373940",
        "text-3": "#4F5159",
        "text-4": "#696C73",

        "accent": "#3B72D9",
        "accent-hover": "#2D62C8",
        "accent-active": "#1C52B6",
        "on-accent": "#FFFFFF",
        "accent-text": "#164BAF",
        "accent-surface": "#E2EAF9",
        "accent-surface-hover": "#D7E3F8",

        "ok": "#2F7A46",
        "warn": "#8F6410",
        "err": "#AB4E46",
        "on-status": "#FFFFFF",
        "ok-text": "#095E2C",
        "warn-text": "#7C4300",
        "err-text": "#8E332E",
        "warn-surface": "#EBE5DD",  # err-surface turned to amber
        "err-surface": "#EEE3E5",
        "err-surface-hover": "#EBD9DA",

        "scrim": "#E9EBEFB8",
        "shadow": "#00000038",
        "overlay": "#EDEFF3F2",
    },
)


# ── the accessibility palette ───────────────────────────────────────────────
HIGH_CONTRAST = Palette(
    name="High Contrast",
    slug="high-contrast",
    scheme="dark",
    note="Pure black, pure white, saturated accents. Nothing in it is near a "
         "threshold, and the surfaces are far enough apart to be told apart "
         "without a divider.",
    values={
        "surface-0": "#000000",
        "surface-1": "#0A0A0A",
        "surface-2": "#141414",
        "surface-3": "#1E1E1E",

        "control": "#2B2B2B",
        "control-hover": "#3D3D3D",
        "control-active": "#333333",

        "text-1": "#FFFFFF",
        "text-2": "#F0F0F0",
        "text-3": "#DCDCDC",
        "text-4": "#B4B4B4",

        "accent": "#FFD400",
        "accent-hover": "#FFE44A",
        "accent-active": "#D9B400",
        "on-accent": "#000000",
        "accent-text": "#FFD400",
        "accent-surface": "#332B00",
        "accent-surface-hover": "#4A3E00",

        "ok": "#0A6B28",
        "warn": "#8A5200",
        "err": "#A81E16",
        "on-status": "#FFFFFF",
        "ok-text": "#3FD174",
        "warn-text": "#FFB020",
        "err-text": "#FF9080",
        "warn-surface": "#351700",  # err-surface turned to amber
        "err-surface": "#3A0F0C",
        "err-surface-hover": "#4F1612",

        "scrim": "#000000CC",
        "shadow": "#000000B3",
        "overlay": "#000000F2",
    },
)


# ── the four accent variants ────────────────────────────────────────────────
# Same neutrals, another hue. with_accent() rebuilds the seven accent roles and
# touches nothing else, which is the point of having the accent as a group.
TEAL_DARK = GOLD_DARK.with_accent(
    "#3FBFB0", name="Teal Dark", slug="teal-dark",
    note="Gold Dark with a teal accent in front.")

BLUE_DARK = GOLD_DARK.with_accent(
    "#5B8DEF", name="Blue Dark", slug="blue-dark",
    note="Gold Dark with a blue accent in front.")

PURPLE_DARK = GOLD_DARK.with_accent(
    "#B07CF0", name="Purple Dark", slug="purple-dark",
    note="Gold Dark with a purple accent in front.")

GREEN_DARK = GOLD_DARK.with_accent(
    "#57B26A", name="Green Dark", slug="green-dark",
    note="Gold Dark with a green accent in front. The accent and the "
         "ok colour share a hue here, so read the shape, not the colour.")


PALETTES: dict[str, Palette] = {
    p.slug: p for p in (
        GOLD_DARK, GOLD_LIGHT,
        TEAL_DARK, BLUE_DARK, PURPLE_DARK, GREEN_DARK,
        SLATE_LIGHT, HIGH_CONTRAST,
    )
}

DEFAULT: Palette = GOLD_DARK


def by_scheme(scheme: str) -> list[Palette]:
    """Every shipped palette of one scheme, in the order above."""
    return [p for p in PALETTES.values() if p.scheme == scheme]
