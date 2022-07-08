"""
Model Generator for OpenSees ~ model
"""

#                          __
#   ____  ____ ___  ____ _/ /
#  / __ \/ __ `__ \/ __ `/ /
# / /_/ / / / / / / /_/ /_/
# \____/_/ /_/ /_/\__, (_)
#                /____/
#
# https://github.com/ioannis-vm/OpenSees_Model_Generator

from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass, field
import numpy as np
import numpy.typing as npt

from .gen.uid_gen import UIDGenerator
from .collections import Collection
from .collections import CollectionActive
from .collections import LevelCollection
from .collections import SectionCollection
from .collections import UniaxialMaterialCollection
from .collections import PhysicalMaterialCollection
from .level import Level

nparr = npt.NDArray[np.float64]

# pylint: disable=unsubscriptable-object
# pylint: disable=invalid-name


@dataclass
class Settings:
    """
    General customization of a model.
        imperial_units (bool):
            True for imperial <3:
                in, lb, lb/(in/s2)
            False for SI:
                m, N, kg
        ndm, ndf: change them to break the code.
    """
    imperial_units: bool = field(default=True)  # false for SI
    ndm: int = field(default=3)  # that's all we support
    ndf: int = field(default=6)  # that's all we support

    def __repr__(self):
        res = ''
        res += '~~~ Model Settings ~~~\n'
        res += f'  Imperial units: {self.imperial_units}\n'
        res += f'  ndm           : {self.ndm}\n'
        res += f'  ndf           : {self.ndf}\n'
        return res


@dataclass(repr=False)
class Model:
    """
    Model object.
    Attributes:
        levels (LevelCollection)
        elastic_sections (SectionCollection)
        fiber_sections (SectionCollection)
        physical_materials (PhysicalMaterialCollection)
        component_connectivity (dict[tuple[str, ...], int])
        uid_generator (UIDGenerator)
        settings
    """
    name: str
    levels: LevelCollection = field(
        init=False)
    elastic_sections: SectionCollection = field(
        init=False)
    fiber_sections: SectionCollection = field(
        init=False)
    uniaxial_materials: UniaxialMaterialCollection = field(
        init=False)
    physical_materials: PhysicalMaterialCollection = field(
        init=False)
    uid_generator: UIDGenerator = field(
        default_factory=UIDGenerator)
    settings: Settings = field(default_factory=Settings)

    def __post_init__(self):
        self.levels = LevelCollection(self)
        self.elastic_sections = SectionCollection(self)
        self.fiber_sections = SectionCollection(self)
        self.uniaxial_materials = UniaxialMaterialCollection(self)
        self.physical_materials = PhysicalMaterialCollection(self)

    def __repr__(self):
        res = ''
        res += '~~~ Model Object ~~~\n'
        res += f'ID: {id(self)}\n'
        res += f'levels: {self.levels.__srepr__()}\n'
        res += f'elastic_sections: {self.elastic_sections.__srepr__()}\n'
        res += f'fiber_sections: {self.fiber_sections.__srepr__()}\n'
        res += f'uniaxial_materials: {self.uniaxial_materials.__srepr__()}\n'
        res += f'physical_materials: {self.physical_materials.__srepr__()}\n'
        return res

    def component_connectivity(self) -> dict[tuple[str, ...], int]:
        res = {}
        components = self.list_of_components()
        for component in components:
            uids = [node.uid for node in component.external_nodes.registry.values()]
            uids.sort()
            uids_tuple = (*uids,)
            assert uids_tuple not in res, 'Error! Duplicate component found.'
            res[uids_tuple] = component
        return res


    def add_level(self,
                  uid: int,
                  elevation: float):
        lvl = Level(self, uid=uid, elevation=elevation)
        self.levels.add(lvl)

    def dict_of_primary_nodes(self):
        dict_of_nodes = {}
        for lvl in self.levels.registry.values():
            dict_of_nodes.update(lvl.nodes.registry)
        return dict_of_nodes

    def list_of_primary_nodes(self):
        list_of_nodes = []
        for lvl in self.levels.registry.values():
            for node in lvl.nodes.registry.values():
                list_of_nodes.append(node)
        return list_of_nodes

    def dict_of_internal_nodes(self):
        dict_of_nodes = {}
        for lvl in self.levels.registry.values():
            for component in lvl.components.registry.values():
                dict_of_nodes.update(component.internal_nodes.registry)
        return dict_of_nodes

    def list_of_internal_nodes(self):
        list_of_nodes = []
        for lvl in self.levels.registry.values():
            for component in lvl.components.registry.values():
                for inode in component.internal_nodes.registry.values():
                    list_of_nodes.append(inode)
        return list_of_nodes

    def dict_of_all_nodes(self):
        dict_of_nodes = {}
        dict_of_nodes.update(self.dict_of_primary_nodes())
        dict_of_nodes.update(self.dict_of_internal_nodes())
        return dict_of_nodes

    def list_of_all_nodes(self):
        list_of_nodes = []
        list_of_nodes.extend(self.list_of_primary_nodes())
        list_of_nodes.extend(self.list_of_internal_nodes())
        return list_of_nodes

    def dict_of_components(self):
        comps = {}
        for lvl in self.levels.registry.values():
            for component in lvl.components.registry.values():
                comps[component.uid] = component
        return comps

    def list_of_components(self):
        return list(self.dict_of_components().values())

    def dict_of_elastic_beamcolumn_elements(self):
        elems = {}
        for lvl in self.levels.registry.values():
            for component in lvl.components.registry.values():
                elems.update(component.elastic_beamcolumn_elements.registry)
        return elems

    def list_of_elastic_beamcolumn_elements(self):
        return list(self.dict_of_elastic_beamcolumn_elements().values())

    def dict_of_disp_beamcolumn_elements(self):
        elems = {}
        for lvl in self.levels.registry.values():
            for component in lvl.components.registry.values():
                elems.update(component.disp_beamcolumn_elements.registry)
        return elems

    def list_of_disp_beamcolumn_elements(self):
        return list(self.dict_of_disp_beamcolumn_elements().values())

    def dict_of_beamcolumn_elements(self):
        elems = {}
        elems.update(self.dict_of_elastic_beamcolumn_elements())
        elems.update(self.dict_of_disp_beamcolumn_elements())
        return elems

    def list_of_beamcolumn_elements(self):
        elems = []
        elems.extend(self.list_of_elastic_beamcolumn_elements())
        elems.extend(self.list_of_disp_beamcolumn_elements())
        return elems

    def reference_length(self):
        """
        Returns the largest dimension of the
        bounding box of the building
        (used in graphics)
        """
        p_min = np.full(3, np.inf)
        p_max = np.full(3, -np.inf)
        for nd in self.list_of_primary_nodes():
            p: nparr = np.array(nd.coords)
            p_min = np.minimum(p_min, p)
            p_max = np.maximum(p_max, p)
        ref_len = np.max(p_max - p_min)
        return ref_len
