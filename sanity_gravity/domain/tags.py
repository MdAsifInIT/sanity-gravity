"""Tag value object for dimension-based image identifiers.

A :class:`Tag` parses ``agent-desktop-connector`` strings (e.g.
``ag-xfce-kasm``). Constraint validation lives in the parser callable
passed to :meth:`Tag.parse`; the dataclass itself is purely a frozen
record so it round-trips cleanly through events / JSONL streams.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    """Parsed dimension tag (``agent``-``desktop``-``connector``)."""

    agent: str
    desktop: str
    connector: str

    @classmethod
    def parse(cls, s: str, parser=None) -> "Tag":
        """Parse ``s`` via ``parser`` (constraint-checked entry point)."""
        if parser is None:
            raise ValueError("Tag.parse requires a parser callable")
        agent, desktop, connector = parser(s)
        return cls(agent=agent, desktop=desktop, connector=connector)

    def __str__(self) -> str:
        return f"{self.agent}-{self.desktop}-{self.connector}"
