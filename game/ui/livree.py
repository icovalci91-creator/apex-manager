"""Le livree delle squadre sulle monoposto 3D.

Per ora due tinte e uno schema; le livree vere, con gli sponsor, arrivano qui.
"""
from __future__ import annotations

from . import theme as T


def livrea_di(team) -> tuple:
    """(seconda tinta, schema) della livrea di una squadra."""
    seconda = T.hex_rgb(getattr(team, "accent", "") or "#202020")
    schema = sum(ord(c) for c in team.id) % 4
    return (seconda, schema)
