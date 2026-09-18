"""Five values in, a whole palette out.

    derive(base="#0D0D0F", accent="#F5C542", text="#E6E6EC",
           ok="#57B26A", err="#B0524A")

Everything else follows by formula. Surfaces step away from the base in OKLab
lightness, controls step away from the page, ``warn`` is ``err`` rotated to
amber, and every foreground is solved against the same contrast function the
auditor uses. A derived palette therefore clears the audit by construction,
and there is no second set of rules to keep in agreement with the first.

Anyone who wants the other end of the trade writes all thirty one roles by hand
and gets the same Palette object.

Two decisions are baked into the formulas and worth knowing before reading
them.

A filled status indicator is always a deep colour with a light label, on every
palette, so that ok, warn and err read as one family and a single ``on-status``
serves all three. The lighter, more saturated version of each hue is a separate
role, ``ok-text`` and friends, and that is what a 6 px dot or a red icon
button uses.

Controls move away from the page, which means lighter on a dark palette and
darker on a light one. Surfaces move the other way and get lighter as they
rise, on both schemes, because that is what a sheet of paper does.
"""
from __future__ import annotations

from . import color
from .palette import Palette

__all__ = ["derive", "accent_roles", "status_roles", "solve_text",
           "keep_or_solve", "solve_ink"]

# How far each surface sits from the base, in OKLab lightness.
_SURFACE_STEPS_DARK = (0.020, 0.040, 0.062)
_SURFACE_STEPS_LIGHT = (0.011, 0.023, 0.036)

# Controls, measured from the base the same way. Positive moves away from a
# dark page, negative away from a light one.
_CONTROL_STEPS_DARK = (0.090, 0.175, 0.120)     # resting, hover, active
_CONTROL_STEPS_LIGHT = (-0.055, -0.100, -0.075)

# The ladder every text role is solved to. text-1 is given, never solved, and
# the three below it keep its hue and chroma and differ only in lightness.
_TEXT_TARGETS = {"text-2": 7.0, "text-3": 4.8, "text-4": 3.2}

# Foregrounds that carry a hue instead of a grey.
_HUE_TEXT_TARGET = 4.8
# The ink on a fill. Black and white bracket every colour, and the worst case
# over all of them, a mid grey at luminance 0.179, gives 4.58:1 to whichever of
# the two is better. So 4.55 is the highest target that is always reachable,
# and it still leaves the audit floor of 4.5 cleared.
_INK_TARGET = 4.55

# How much accent goes into a tinted surface.
_TINT = 0.10
_TINT_HOVER = 0.155
_TINT_ERR = 0.115
_TINT_ERR_HOVER = 0.175

# A status fill has to be dark enough for a light label on it.
_MAX_FILL_LUMINANCE = 0.155

# Amber, in OKLCH degrees.
_WARN_HUE = 78.0

# The alpha of the three depth roles. These are the values the design was
# drawn with, and the formula reproduces them exactly, which is the check that
# it matches the
# design it came from.
_SCRIM_ALPHA = 0.72
_SHADOW_ALPHA_DARK = 0.60
_SHADOW_ALPHA_LIGHT = 0.22
_OVERLAY_ALPHA = 0.95


# ── solvers ─────────────────────────────────────────────────────────────────
def solve_text(seed: str, surfaces: dict[str, str], target: float,
               is_dark: bool) -> str:
    """The value of ``seed`` closest to the surfaces that still clears ``target``.

    Hue and chroma are held. Only the OKLab lightness moves, coarsely first and
    then finely, and the first value that clears the threshold against every
    surface wins. Scanning from the surfaces outward, instead of stopping at
    the seed, makes the answer the same whatever seed was handed in.
    """
    backdrops = list(surfaces.values())

    def clears(value: str) -> bool:
        return all(color.contrast(value, s) >= target for s in backdrops)

    _, C, h = color.to_oklch(seed)
    lo, hi = (0.0, 1.0)
    span = [i / 100.0 for i in range(101)]
    if not is_dark:
        span.reverse()

    coarse = None
    for L in span:
        if clears(color.from_oklch((L, C, h))):
            coarse = L
            break
    if coarse is None:
        # Not reachable at this chroma. Drain the chroma and try once more,
        # which is what a very saturated seed on a light page needs.
        for frac in (0.75, 0.5, 0.3, 0.15, 0.0):
            for L in span:
                cand = color.from_oklch((L, C * frac, h))
                if clears(cand):
                    return cand
        return "#FFFFFF" if is_dark else "#000000"

    step = 0.01 if is_dark else -0.01
    fine = coarse - step
    for i in range(1, 11):
        L = max(lo, min(hi, coarse - step + step * i / 10.0))
        if clears(color.from_oklch((L, C, h))):
            fine = L
            break
    return color.from_oklch((max(lo, min(hi, fine)), C, h))


def keep_or_solve(seed: str, surfaces: dict[str, str], target: float,
                  is_dark: bool) -> str:
    """``seed`` untouched when it already clears ``target``, solved when it does not.

    This is what the hue foregrounds want. On a dark palette the accent reads
    perfectly well as text and there is no reason to dim it down to the
    threshold; on a light palette the same accent is unreadable and has to
    move. The grey text ladder wants the other behaviour and calls
    ``solve_text`` directly, so that its four steps are spaced by the contract
    and not by whichever seeds were handed in.
    """
    if all(color.contrast(seed, s) >= target for s in surfaces.values()):
        return seed
    return solve_text(seed, surfaces, target, is_dark)


def solve_ink(fills: list[str], dark_ink: str, light_ink: str,
              target: float = _INK_TARGET) -> str:
    """One foreground that clears ``target`` on all of ``fills``.

    The palette's own near black and near white are tried first, so the ink
    belongs to the palette when it can. Pure black or pure white is the
    fallback, and a fill that neither of them clears is a fill in the wrong
    place, which the auditor then says out loud.
    """
    for ink in (dark_ink, light_ink, "#000000", "#FFFFFF"):
        if all(color.contrast(ink, f) >= target for f in fills):
            return ink
    scored = [(min(color.contrast(i, f) for f in fills), i)
              for i in ("#000000", "#FFFFFF")]
    return max(scored)[1]


# ── the role groups, each usable on its own ─────────────────────────────────
def accent_roles(accent: str, surfaces: dict[str, str], is_dark: bool,
                 tint_base: str, inks: tuple[str, str] | None = None) -> dict[str, str]:
    """The seven accent roles, given the accent and the surfaces around it.

    ``inks`` is the palette's own near black and near white, tried first for
    ``on-accent`` so the label on a button belongs to the palette. Left out, the
    darkest and lightest surfaces stand in for them.
    """
    dark_ink, light_ink = inks or (_darkest(surfaces), _lightest(surfaces))
    L, C, h = color.to_oklch(accent)
    # Hover moves away from the page and active moves further, the same rule
    # the controls follow. On a light palette that means the accent button
    # darkens under the pointer, which is also what keeps one on-accent ink
    # working across all three fills.
    dL_hover, dL_active = (0.055, -0.080) if is_dark else (-0.050, -0.105)
    hover = color.from_oklch((min(1.0, max(0.0, L + dL_hover)), C, h))
    active = color.from_oklch((min(1.0, max(0.0, L + dL_active)), C, h))

    # One ink has to read on all three fills, so it is chosen for the accent
    # itself and the other two then move until they suit it. Without this an
    # accent sitting halfway up the range produces a hover that neither black
    # nor white can sit on.
    ink = solve_ink([accent], dark_ink, light_ink)
    hover = _fit_to_ink(hover, ink, _INK_TARGET)
    active = _fit_to_ink(active, ink, _INK_TARGET)

    tinted = color.mix(tint_base, accent, _TINT)
    tinted_hover = color.mix(tint_base, accent, _TINT_HOVER)

    # accent-text has to survive the tinted surfaces as well, since that is
    # exactly where it is used: the active tab, the selected row, the chip.
    around = dict(surfaces)
    around["accent-surface"] = tinted
    around["accent-surface-hover"] = tinted_hover

    return {
        "accent": accent,
        "accent-hover": hover,
        "accent-active": active,
        "on-accent": ink,
        "accent-text": keep_or_solve(accent, around, _HUE_TEXT_TARGET, is_dark),
        "accent-surface": tinted,
        "accent-surface-hover": tinted_hover,
    }


def status_roles(ok: str, err: str, surfaces: dict[str, str], is_dark: bool,
                 tint_base: str, inks: tuple[str, str] | None = None) -> dict[str, str]:
    """The nine status roles, from a success colour and a failure colour.

    ``warn`` is not asked for. It is ``err`` turned to amber, which keeps the
    three fills in one family whatever the two seeds are, and the same turn
    makes the caution surface out of the failure surface.
    """
    dark_ink, light_ink = inks or (_darkest(surfaces), _lightest(surfaces))
    warn_seed = _amber(err)
    fills = {k: _deepen(v) for k, v in (("ok", ok), ("warn", warn_seed), ("err", err))}

    err_surface = color.mix(tint_base, fills["err"], _TINT_ERR)
    err_surface_hover = color.mix(tint_base, fills["err"], _TINT_ERR_HOVER)
    # The caution fill is the failure fill turned to amber, which is the same
    # move that made warn out of err one level down. Mixing the surface toward
    # the warn fill instead lands a good deal darker than the other two tinted
    # surfaces, because a deepened amber is darker than a deepened red at the
    # same strength, and three tinted surfaces at three lightnesses read as a
    # mistake instead of as a family.
    warn_surface = color.with_hue(err_surface, color.hue(fills["warn"]))

    around = dict(surfaces)
    around["warn-surface"] = warn_surface
    around["err-surface"] = err_surface
    around["err-surface-hover"] = err_surface_hover

    out = dict(fills)
    out["on-status"] = solve_ink(list(fills.values()), dark_ink, light_ink)
    out["ok-text"] = keep_or_solve(ok, around, _HUE_TEXT_TARGET, is_dark)
    out["warn-text"] = keep_or_solve(warn_seed, around, _HUE_TEXT_TARGET, is_dark)
    out["err-text"] = keep_or_solve(err, around, _HUE_TEXT_TARGET, is_dark)
    out["warn-surface"] = warn_surface
    out["err-surface"] = err_surface
    out["err-surface-hover"] = err_surface_hover
    return out


# ── the whole thing ─────────────────────────────────────────────────────────
def derive(base: str, accent: str, text: str, ok: str, err: str, *,
           name: str = "Derived", slug: str = "derived",
           note: str = "") -> Palette:
    """Build a complete palette from the five values that carry the intent.

    ``base`` is the window backdrop and decides whether the palette is dark or
    light. ``text`` is the brightest text; the three fainter steps are solved
    from it. ``ok`` and ``err`` seed the status family, and ``warn`` comes out
    of ``err``.
    """
    for label, value in (("base", base), ("accent", accent), ("text", text),
                         ("ok", ok), ("err", err)):
        if not color.is_hex(value):
            raise ValueError(f"{label} is not a hex colour: {value!r}")
        if color.alpha_of(value) < 1.0:
            raise ValueError(f"{label} may not carry an alpha: {value!r}")

    is_dark = color.is_dark(base)
    v: dict[str, str] = {"surface-0": base}

    steps = _SURFACE_STEPS_DARK if is_dark else _SURFACE_STEPS_LIGHT
    base_L = color.lightness(base)
    if base_L + steps[-1] > 1.0:                   # no headroom, so step down
        steps = tuple(-s for s in steps)
    for i, step in enumerate(steps, start=1):
        v[f"surface-{i}"] = color.shift_lightness(base, step)

    csteps = _CONTROL_STEPS_DARK if is_dark else _CONTROL_STEPS_LIGHT
    for role_name, step in zip(("control", "control-hover", "control-active"), csteps):
        v[role_name] = color.shift_lightness(base, step)

    plain = {k: v[k] for k in ("surface-0", "surface-1", "surface-2", "surface-3",
                               "control", "control-hover", "control-active")}

    inks = (base, text) if is_dark else (text, base)
    v.update(status_roles(ok, err, plain, is_dark, v["surface-3"], inks))
    v.update(accent_roles(accent, plain, is_dark, v["surface-3"], inks))

    # Every surface is known now, so the text ladder can be solved against all
    # of them at once.
    all_surfaces = dict(plain)
    for extra in ("accent-surface", "accent-surface-hover",
                  "warn-surface", "err-surface", "err-surface-hover"):
        all_surfaces[extra] = v[extra]
    overlay = color.to_hex(color.parse(v["surface-1"])[:3], _OVERLAY_ALPHA)
    all_surfaces["overlay"] = color.over(overlay, "#000000" if is_dark else "#FFFFFF")

    v["text-1"] = text
    for role_name, target in _TEXT_TARGETS.items():
        v[role_name] = solve_text(text, all_surfaces, target, is_dark)

    v["scrim"] = color.to_hex(color.parse(base)[:3], _SCRIM_ALPHA)
    v["shadow"] = color.to_hex((0.0, 0.0, 0.0),
                               _SHADOW_ALPHA_DARK if is_dark else _SHADOW_ALPHA_LIGHT)
    v["overlay"] = overlay

    return Palette(name=name, slug=slug, scheme="dark" if is_dark else "light",
                   values=v, note=note)


# ── small helpers ───────────────────────────────────────────────────────────
def _fit_to_ink(value: str, ink: str, target: float) -> str:
    """Move a fill in lightness until ``ink`` reads on it.

    The fill goes away from the ink: lighter under a dark label, darker under a
    light one. It stops at the first step that clears the threshold, so a fill
    that was already fine is handed back untouched.
    """
    if color.contrast(ink, value) >= target:
        return value
    L, C, h = color.to_oklch(value)
    away = 1.0 if color.luminance(ink) < color.luminance(value) else -1.0
    out = value
    for i in range(1, 101):
        out = color.from_oklch((max(0.0, min(1.0, L + away * 0.01 * i)), C, h))
        if color.contrast(ink, out) >= target:
            break
    return out


def _amber(err: str) -> str:
    """The failure hue turned to amber, a little lighter and a little louder."""
    L, C, _ = color.to_oklch(err)
    return color.from_oklch((min(1.0, L + 0.060), C * 1.15, _WARN_HUE))


def _deepen(value: str) -> str:
    """Pull a status colour down until a light label sits on it comfortably."""
    L, C, h = color.to_oklch(value)
    out = value
    for _ in range(40):
        if color.luminance(out) <= _MAX_FILL_LUMINANCE:
            return out
        L -= 0.015
        out = color.from_oklch((max(0.0, L), C, h))
    return out


def _darkest(surfaces: dict[str, str]) -> str:
    return min(surfaces.values(), key=color.luminance)


def _lightest(surfaces: dict[str, str]) -> str:
    return max(surfaces.values(), key=color.luminance)
