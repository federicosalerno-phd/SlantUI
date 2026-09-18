"""The Palette object: thirty one roles filled in, and the operations on them.

A palette is a plain mapping from role name to hex string, wrapped so that a
missing role, a typo in a role name and an alpha on a role that may not carry
one are all caught at construction instead of on screen.

``with_accent`` is here because four of the eight shipped palettes are one
line: the same dark neutrals with another hue in the seven accent roles.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import color
from .roles import ALPHA_ROLES, ROLE_NAMES, SURFACES

__all__ = ["Palette", "ACCENT_ROLES"]

# The roles with_accent rebuilds. Everything else is neutral and stays put.
ACCENT_ROLES = ("accent", "accent-hover", "accent-active", "on-accent",
                "accent-text", "accent-surface", "accent-surface-hover")


@dataclass(frozen=True)
class Palette:
    name: str
    slug: str
    scheme: str                       # "dark" or "light"
    values: dict[str, str] = field(default_factory=dict)
    note: str = ""

    def __post_init__(self) -> None:
        if self.scheme not in ("dark", "light"):
            raise ValueError(f"{self.slug}: scheme is dark or light, got {self.scheme!r}")
        missing = [r for r in ROLE_NAMES if r not in self.values]
        if missing:
            raise ValueError(f"{self.slug}: no value for {', '.join(missing)}")
        unknown = [r for r in self.values if r not in ROLE_NAMES]
        if unknown:
            raise ValueError(f"{self.slug}: {', '.join(unknown)} is not a role")
        for name, value in self.values.items():
            if not color.is_hex(value):
                raise ValueError(f"{self.slug}: {name} is not a hex colour: {value!r}")
            if color.alpha_of(value) < 1.0 and name not in ALPHA_ROLES:
                raise ValueError(f"{self.slug}: {name} may not carry an alpha")

    # ── reading ─────────────────────────────────────────────────────────────
    def __getitem__(self, role: str) -> str:
        return self.values[role]

    def get(self, role: str, default: str | None = None) -> str | None:
        return self.values.get(role, default)

    @property
    def is_dark(self) -> bool:
        return self.scheme == "dark"

    def surface(self, role: str) -> str:
        """A surface as text will actually see it, with any alpha resolved.

        ``overlay`` sits on content of an unknown colour, so the worse of the
        two extremes is what counts.
        """
        value = self.values[role]
        if color.alpha_of(value) >= 1.0:
            return value
        on_black = color.over(value, "#000000")
        on_white = color.over(value, "#FFFFFF")
        return on_black if self.is_dark else on_white

    def surfaces(self) -> dict[str, str]:
        """Every surface text may land on, resolved."""
        return {r: self.surface(r) for r in SURFACES}

    # ── writing ─────────────────────────────────────────────────────────────
    def edit(self, **changes: str) -> "Palette":
        """A copy with some roles changed. Validation runs again."""
        bad = [k for k in changes if k not in ROLE_NAMES]
        if bad:
            raise KeyError(f"not a role: {', '.join(bad)}")
        return replace(self, values={**self.values, **changes})

    def rename(self, name: str, slug: str, note: str = "") -> "Palette":
        return replace(self, name=name, slug=slug, note=note or self.note)

    def with_accent(self, accent: str, *, name: str, slug: str,
                    note: str = "") -> "Palette":
        """The same neutrals under another accent hue.

        The seven accent roles are rebuilt by the same formulas the generator
        uses, so a palette made this way is as sound as one written by hand.
        """
        from .generate import accent_roles
        inks = ((self.values["surface-0"], self.values["text-1"]) if self.is_dark
                else (self.values["text-1"], self.values["surface-0"]))
        return replace(self, name=name, slug=slug, note=note,
                       values={**self.values,
                               **accent_roles(accent, self.surfaces(), self.is_dark,
                                              self.values["surface-3"], inks)})

    # ── output ──────────────────────────────────────────────────────────────
    def css_variables(self) -> dict[str, str]:
        """``{"--surface-0": "#0D0D0F", ...}`` in the canonical role order."""
        return {f"--{r}": self.values[r] for r in ROLE_NAMES}
