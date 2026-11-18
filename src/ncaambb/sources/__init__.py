"""Source adapters. Each module exposes one Source subclass."""

from .base import Source
from .bracketmatrix import BracketMatrix
from .cbbd import Cbbd
from .espn_bpi import EspnBpi
from .haslametrics import Haslametrics
from .ncaa_net import NcaaNet
from .teamrankings import TeamRankings
from .warrennolan import WarrenNolan
from .torvik import Torvik

REGISTRY: dict[str, type[Source]] = {
    cls.name: cls
    for cls in (Torvik, Haslametrics, EspnBpi, TeamRankings, Cbbd, WarrenNolan, NcaaNet, BracketMatrix)
}

__all__ = [
    "REGISTRY", "Source", "Torvik", "Haslametrics", "EspnBpi", "TeamRankings", "WarrenNolan", "NcaaNet",
    "Cbbd", "BracketMatrix",
]
