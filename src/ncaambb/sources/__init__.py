"""Source adapters. Each module exposes one Source subclass."""

from .base import Source
from .espn_bpi import EspnBpi
from .haslametrics import Haslametrics
from .torvik import Torvik

REGISTRY: dict[str, type[Source]] = {
    cls.name: cls for cls in (Torvik, Haslametrics, EspnBpi)
}

__all__ = ["REGISTRY", "Source", "Torvik", "Haslametrics", "EspnBpi"]
