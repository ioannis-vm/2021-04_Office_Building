"""Load cases."""

from __future__ import annotations
from dataclasses import dataclass, field

from typing import TYPE_CHECKING

import numpy as np

from osmg.core.common import EPSILON
from osmg.analysis.supports import FixedSupport
from osmg.analysis.supports import ElasticSupport

if TYPE_CHECKING:
    from osmg.core.model import Model3D, Model2D


@dataclass(repr=False)
class ConcentratedValue:
    """Concentrated value, such as a point load or mass."""

    value: tuple(float)


@dataclass(repr=False)
class PointLoad(ConcentratedValue):
    """Point load."""

    pass


@dataclass(repr=False)
class PointMass(ConcentratedValue):
    """Point load."""

    pass


@dataclass(repr=False)
class UDL:
    """Beamcolumn element UDL."""

    value: tuple(float)


@dataclass(repr=False)
class LoadRegistry:
    """Load registry."""

    nodal_loads: dict[int, PointLoad] = field(default_factory=dict)
    nodal_mass: dict[int, PointMass] = field(default_factory=dict)
    element_udl: dict[int, UDL] = field(default_factory=dict)


@dataclass(repr=False)
class LoadCase:
    """Load case."""

    fixed_supports: dict[int, FixedSupport] = field(default_factory=dict)
    elastic_supports: dict[int, ElasticSupport] = field(default_factory=dict)
    load_registry: LoadRegistry = field(default_factory=LoadRegistry)

    def add_supports_at_level(
        self, model: Model2D | Model3D, support, level_tag
    ) -> None:
        """
        Add the given support at the specified level.

        Determines all primary nodes that have an elevation equal to
        the specified level's elevation and assigns the specified
        support to them.

        Assumes that the last coordinate of the nodes correponds to
        elevation.

        Raises:
          TypeError: If the provided support is not a known support
            type.
        """
        nodes = list(model.nodes.values())
        level_elevation = model.grid_system.get_level_elevation(level_tag)
        for node in nodes:
            if np.abs(node.coordinates[-1] - level_elevation) < EPSILON:
                if isinstance(support, FixedSupport):
                    self.fixed_supports[node.uid] = support
                elif isinstance(support, ElasticSupport):
                    self.elastic_supports[node.uid] = support
                else:
                    msg = f'Unsupported object type: {type(support)}'
                    raise TypeError(msg)


@dataclass(repr=False)
class DeadLoadCase(LoadCase):
    """Dead load case."""

    pass


@dataclass(repr=False)
class LiveLoadCase(LoadCase):
    """Live load case."""

    pass


@dataclass(repr=False)
class SeismicLoadCase(LoadCase):
    """Seismic load case base class."""

    pass


@dataclass(repr=False)
class SeismicELFLoadCase(SeismicLoadCase):
    """Seismic ELF load case."""

    pass


@dataclass(repr=False)
class SeismicRSLoadCase(SeismicLoadCase):
    """Seismic RS load case."""

    pass


@dataclass(repr=False)
class SeismicTransientLoadCase(SeismicLoadCase):
    """Seismic transient load case."""

    pass


@dataclass(repr=False)
class OtherLoadCase(LoadCase):
    """Other load case."""

    pass


@dataclass(repr=False)
class LoadCaseRegistry:
    """Load case registry."""

    dead: dict[str, DeadLoadCase]
    live: dict[str, LiveLoadCase]
    seismic: dict[str, SeismicLoadCase]
    other: dict[str, OtherLoadCase]
