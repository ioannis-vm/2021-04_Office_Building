"""
Defines objects associated with tributary area analysis for load
distribution.

"""


#
#   _|_|      _|_|_|  _|      _|    _|_|_|
# _|    _|  _|        _|_|  _|_|  _|
# _|    _|    _|_|    _|  _|  _|  _|  _|_|
# _|    _|        _|  _|      _|  _|    _|
#   _|_|    _|_|_|    _|      _|    _|_|_|
#
#
# https://github.com/ioannis-vm/OpenSees_Model_Generator

from __future__ import annotations
from typing import TYPE_CHECKING
from typing import no_type_check
from typing import Optional
from dataclasses import dataclass, field
import sys
from tqdm import tqdm
import numpy as np
import numpy.typing as npt
from .. import mesh
from ..ops.node import Node
from .. import common
from ..ops.element import ElasticBeamColumn
from ..ops.element import DispBeamColumn
from ..ops.element import TwoNodeLink
from ..ops.element import ZeroLength

if TYPE_CHECKING:
    from ..load_case import LoadCase
    from ..level import Level
    from ..mesh import Edge, Vertex, Halfedge

# pylint: disable=no-member
# pylint: disable=import-outside-toplevel

nparr = npt.NDArray[np.float64]
PolygonShape = list[tuple[float, float]]


@dataclass
class PolygonLoad:
    """
    Polygon-shaped loaded region.

    """

    name: str
    value: float
    outside_shape: Optional[PolygonShape]
    holes: Optional[list[PolygonShape]]
    massless: bool


@dataclass(repr=False)
class TributaryAreaAnalysisData:
    """
    Data generated by the tributary area analysis code.

    """

    # collects the defined edges
    edges: dict[int, Edge] = field(default_factory=dict)
    # collects the defined vertices
    vertices: dict[int, Vertex] = field(default_factory=dict)
    # maps an edge.uid to a node or line element
    edge_map: dict[int, Node | ElasticBeamColumn | DispBeamColumn] = field(
        default_factory=dict
    )
    # maps an edge.uid to its corresponding tributary area
    edge_area: dict[int, float] = field(default_factory=dict)
    # maps an edge.uid to its corresponding tributary polygon
    edge_polygons: dict[int, list[PolygonShape]] = field(default_factory=dict)
    # maps a node.uid to a vertex
    vertex_map: dict[int, Vertex] = field(default_factory=dict)
    # used to map zerolength element-induced coinciding nodes
    zn_map: dict[int, int] = field(default_factory=dict)
    # used to map panel zone nodes to their primary node
    pz_node: dict[int, dict[str, Node]] = field(default_factory=dict)


@dataclass
class TributaryAreaAnaysis:
    """
    Tributary area analysis object.

    """

    parent_loadcase: LoadCase
    parent_level: Level
    polygon_loads: list[PolygonLoad] = field(default_factory=list)
    data: TributaryAreaAnalysisData = field(
        default_factory=TributaryAreaAnalysisData
    )

    @no_type_check
    def run(
        self, load_factor=1.00, massless_load_factor=1.00, perform_checks=True
    ):
        """
        Performs tributary area analysis

        Arguments:
          load_factor: Factor by which to multiply the surface
            loads that count as a mass source, found in the load case.
          massless_load_factor: Factor by which to multiply
            the massless loads found in the load case.
          perform_checks: Tributary area analysis works by
            generating a mesh defined by the horizontal elements of
            the floor plan and analyzing that mesh. The mesh should
            not contain any edges that cross or overlap with other
            edges. This can happen, for instance, if beam end offsets
            have been accidentally misspecified causing beams to
            overlap with or cross other members. The only shared
            points between the edges should be the end vertices. By
            default, we check if that is the case to avoid unexpected
            behavior. This flag can be used to disable the checks for
            subsequent analyses to enhance performance if that a prior
            analysis has verified that the checks are satisfied.

        """

        try:
            import skgeom as sg
        except ModuleNotFoundError:
            msg = "One day, a custom implementation of the "
            msg += "straight skeleton algorithm might be added to osmg...\n"
            msg += "Until that day, the scikit-geometry package is required.\n"
            msg += "Please install scikit-geometry.\n"
            msg += "  $ conda install scikit-geometry -c conda-forge\n"
            msg += "https://github.com/scikit-geometry/scikit-geometry"
            print("~ skgeom is not installed ~")
            print()
            print(msg)
            sys.exit()

        lvl = self.parent_level
        all_components = list(lvl.components.values())
        horizontal_elements = []
        panel_zones = []
        for component in all_components:
            if component.component_purpose == "horizontal_component":
                horizontal_elements.append(component)
            elif component.component_purpose == "steel_W_panel_zone":
                panel_zones.append(component)

        # # plotting - used while developing the code
        # subset_model = mdl.initialize_empty_copy('subset_1')
        # for component in horizontal_elements+panel_zones:
        #     mdl.transfer_component(subset_model, component)
        # show(subset_model)

        # define vertices, edges, mapping
        # we "flatten" the components in the xy plane.
        # for joints, we only consider the top-most line elements
        # and we treat them the same as rigid offsets.

        # clear any previous results
        self.data.edges = {}
        self.data.vertices = {}
        self.data.edge_map = {}
        self.data.edge_area = {}
        self.data.edge_polygons = {}
        self.data.vertex_map = {}
        self.data.zn_map = {}
        self.data.pz_node = {}

        edges = self.data.edges
        vertices = self.data.vertices
        edge_map = self.data.edge_map
        edge_area = self.data.edge_area
        edge_polygons = self.data.edge_polygons
        vertex_map = self.data.vertex_map
        zn_map = self.data.zn_map
        pz_node = self.data.pz_node

        for panel_zone in panel_zones:
            back_nd = panel_zone.external_nodes.named_contents["middle_back"]
            front_nd = panel_zone.external_nodes.named_contents["middle_front"]
            main_nd = panel_zone.external_nodes.named_contents["top_node"]
            back_offset: nparr = np.array(main_nd.coords) - np.array(
                back_nd.coords
            )
            front_offset: nparr = np.array(main_nd.coords) - np.array(
                front_nd.coords
            )
            pz_node[back_nd.uid] = {
                "substitute_node": main_nd,
                "additional_offset": -back_offset[0:2],
            }
            pz_node[front_nd.uid] = {
                "substitute_node": main_nd,
                "additional_offset": -front_offset[0:2],
            }

        for comp in horizontal_elements:

            line_elements = [
                elm for elm in comp.elements.values()
                if isinstance(
                    elm, (ElasticBeamColumn, DispBeamColumn, TwoNodeLink))]

            zerolength_elements = [
                elm for elm in comp.elements.values()
                if isinstance(elm, ZeroLength)]
            for zelm in zerolength_elements:
                zn_map[zelm.nodes[1].uid] = zelm.nodes[0].uid

            for elm in line_elements:
                n_i = elm.nodes[0]
                if hasattr(elm, 'geomtransf'):
                    eo_i = elm.geomtransf.offset_i[0:2]
                else:
                    eo_i = np.zeros(2)
                if n_i.uid in zn_map:
                    n_i = comp.internal_nodes[zn_map[n_i.uid]]
                n_j = elm.nodes[1]
                if hasattr(elm, 'geomtransf'):
                    eo_j = elm.geomtransf.offset_j[0:2]
                else:
                    eo_j = np.zeros(2)
                if n_j.uid in zn_map:
                    n_j = comp.internal_nodes[zn_map[n_j.uid]]
                if n_i.uid in pz_node:
                    sub_data = pz_node[n_i.uid]
                    n_i = sub_data["substitute_node"]
                    eo_i = eo_i.copy() + sub_data["additional_offset"]
                if n_j.uid in pz_node:
                    sub_data = pz_node[n_j.uid]
                    n_j = sub_data["substitute_node"]
                    eo_j = eo_j.copy() + sub_data["additional_offset"]

                if n_i.uid not in vertex_map:
                    vrt_i = mesh.Vertex((n_i.coords[0], n_i.coords[1]))
                    vertex_map[n_i.uid] = vrt_i
                    vertices[vrt_i.uid] = vrt_i
                else:
                    vrt_i = vertex_map[n_i.uid]
                if n_j.uid not in vertex_map:
                    vrt_j = mesh.Vertex((n_j.coords[0], n_j.coords[1]))
                    vertex_map[n_j.uid] = vrt_j
                    vertices[vrt_j.uid] = vrt_j
                else:
                    vrt_j = vertex_map[n_j.uid]

                if np.linalg.norm(eo_i) >= common.EPSILON:
                    # there is a rigid offset and/or panel zone
                    point = np.array(vrt_i.coords) + eo_i
                    vrt_oi = mesh.Vertex((point[0], point[1]))
                    vertices[vrt_oi.uid] = vrt_oi
                    edg_oi = mesh.Edge(vrt_i, vrt_oi)
                    edges[edg_oi.uid] = edg_oi
                    edge_map[edg_oi.uid] = n_i
                    connecting_vertex_i = vrt_oi
                else:
                    connecting_vertex_i = vrt_i
                if np.linalg.norm(eo_j) >= common.EPSILON:
                    # there is a rigid offset and/or panel zone
                    point = np.array(vrt_j.coords) + eo_j
                    vrt_oj = mesh.Vertex((point[0], point[1]))
                    vertices[vrt_oj.uid] = vrt_oj
                    edg_oj = mesh.Edge(vrt_j, vrt_oj)
                    edges[edg_oj.uid] = edg_oj
                    edge_map[edg_oj.uid] = n_j
                    connecting_vertex_j = vrt_oj
                else:
                    connecting_vertex_j = vrt_j
                edg_interior = mesh.Edge(
                    connecting_vertex_i, connecting_vertex_j
                )
                edge_map[edg_interior.uid] = elm
                edges[edg_interior.uid] = edg_interior

        # # plotting - used while developing the code
        # import pandas as pd
        # edf = pd.DataFrame(np.zeros((len(edges)*3, 2)))
        # edf.columns = ['x', 'y']
        # enames = []
        # for i, edge_key in enumerate(edges):
        #     edge = edges[edge_key]
        #     edf.loc[i*3+0, 'x':'y'] = edge.v_i.coords
        #     edf.loc[i*3+1, 'x':'y'] = edge.v_j.coords
        #     edf.loc[i*3+2, 'x':'y'] = (None, None)
        #     enames.extend((f'E{edge.uid} to V{edge.v_i.uid}',
        #                    f'E{edge.uid} to V{edge.v_j.uid}', None))
        # vdf = pd.DataFrame(np.zeros((len(vertices), 2)))
        # vdf.columns = ['x', 'y']
        # vnames = []
        # for i, vertex_key in enumerate(vertices):
        #     vertex = vertices[vertex_key]
        #     vdf.loc[i, 'x':'y'] = vertex.coords
        #     vnames.append(vertex.uid)
        # edf = edf + np.random.normal(0.00, 0.10, edf.shape)
        # import plotly.express as px
        # import plotly.graph_objects as go
        # fig1 = px.line(edf, x='x', y='y', hover_name=enames)
        # fig2 = px.scatter(vdf, x='x', y='y', hover_name=vnames,
        #                   color=['red']*len(vnames))
        # fig = go.Figure(data=fig1.data + fig2.data)
        # fig.show()

        if perform_checks:
            # verify that no edges overlap
            all_edges_list = list(edges.values())
            for index, considered_edge in enumerate(
                tqdm(
                    all_edges_list, desc="Checking plan's edges", unit="edges"
                )
            ):
                if index == len(all_edges_list):
                    # we are done.
                    continue
                remaining_edges = all_edges_list[(index + 1)::]
                for other_edge in remaining_edges:
                    # check if the two edges overlap or cross each other
                    if considered_edge.overlaps_or_crosses(other_edge):
                        # the two edges overlap or cross each other
                        msg = "Error: Analysis of the floor plan geometry "
                        msg += "indicates the presence of "
                        msg += "overlapping elements.\n"
                        msg += "Check the model at the following locations:\n"
                        msg += f"{considered_edge.v_i.coords}"
                        msg += f"{considered_edge.v_j.coords}"
                        msg += f"{other_edge.v_i.coords}"
                        msg += f"{other_edge.v_j.coords}"
                        raise ValueError(msg)

        halfedges = mesh.define_halfedges(list(edges.values()))
        loops = mesh.obtain_closed_loops(halfedges)
        external, internal, trivial = mesh.orient_loops(loops)
        # Sanity checks.
        mesh.sanity_checks(external, trivial)

        for internal_loop in internal:
            poly = sg.Polygon([h.vertex.coords for h in internal_loop])
            skel = sg.skeleton.create_interior_straight_skeleton(poly)
            # todo: what we need to get rid of this is to end up with a list
            # of halfedges defining the subloops.

            # something like:
            # subloops = mesh.bisector_subdivision(internal_loop)

            subloops: list[list[Halfedge]] = []

            def is_in_some_subloop(halfedge, loops):
                for loop in loops:
                    for other_halfedge in loop:
                        if (
                            other_halfedge.vertex.point
                            == halfedge.vertex.point
                            and other_halfedge.next.vertex.point
                            == halfedge.next.vertex.point
                        ):
                            return True
                return False

            for halfedge in skel.halfedges:
                if subloops:
                    if is_in_some_subloop(halfedge, subloops):
                        continue
                subloop = [halfedge]
                nxt = halfedge.next
                while nxt.vertex.point != halfedge.vertex.point:
                    subloop.append(nxt)
                    nxt = nxt.next
                subloops.append(subloop)

            subloop_areas = [
                float(sg.Polygon([h.vertex.point for h in subloop]).area())
                for subloop in subloops
            ]
            outer = min(subloop_areas)  # Remove the exterior loop
            index = subloop_areas.index(outer)
            del subloops[index]
            del subloop_areas[index]

            for i, subloop in enumerate(subloops):
                area = subloop_areas[i]
                loop_edges = [h.edge for h in internal_loop]
                for halfedge in subloop:
                    for edge in loop_edges:
                        v_i = sg.Point2(*edge.v_i.coords)
                        v_j = sg.Point2(*edge.v_j.coords)
                        pt_1 = halfedge.vertex.point
                        pt_2 = halfedge.next.vertex.point
                        if (pt_1 == v_i and pt_2 == v_j) or (
                            pt_1 == v_j and pt_2 == v_i
                        ):
                            if edge.uid in edge_area:
                                edge_area[edge.uid] += area
                            else:
                                edge_area[edge.uid] = area
                            if edge.uid in edge_polygons:
                                edge_polygons[edge.uid].append(
                                    [
                                        (
                                            float(h.vertex.point.x()),
                                            float(h.vertex.point.y()),
                                        )
                                        for h in subloop
                                    ]
                                )
                            else:
                                edge_polygons[edge.uid] = [
                                    [
                                        (
                                            float(h.vertex.point.x()),
                                            float(h.vertex.point.y()),
                                        )
                                        for h in subloop
                                    ]
                                ]

        # # plotting - used while developing the code
        # import pandas as pd
        # import plotly.express as px
        # import plotly.graph_objects as go

        # x_vals = []
        # y_vals = []
        # colors = []
        # for edge in edges.values():
        #     x_vals.extend([edge.v_i.coords[0], edge.v_j.coords[0], None])
        #     y_vals.extend([edge.v_i.coords[1], edge.v_j.coords[1], None])
        #     colors.extend(['black', 'black', None])

        # fig1 = go.Figure(go.Scatter(x=x_vals, y=y_vals,
        #                             mode='lines',
        #                             line_color='black',
        #                             name='Elements'))

        # x_vals = []
        # y_vals = []
        # for edge in edges.values():
        #     for poly in edge_polygons[edge.uid]:
        #         poly_rot = poly[1:]+poly[:1]
        #         for vi, vj in zip(poly, poly_rot):
        #             x_vals.extend((vi[0], vj[0], None))
        #             y_vals.extend((vi[1], vj[1], None))

        # fig2 = go.Figure(go.Scatter(x=x_vals, y=y_vals,
        #                             mode='lines',
        #                             line_color='blue',
        #                             name='Regions'))

        # fig = go.Figure(data=fig2.data + fig1.data)
        # fig.update_yaxes(
        #     scaleanchor = "x",
        #     scaleratio = 1,
        #   )
        # fig.show()

        # apply loads and mass
        # todo (future): account for the shape of the loaded area
        mdl = self.parent_level.parent_model
        if mdl.settings.imperial_units:
            g_const = common.G_CONST_IMPERIAL
        else:
            g_const = common.G_CONST_SI
        lcase = self.parent_loadcase
        for uid, edge in edges.items():
            area = edge_area[uid]
            loaded_elm = edge_map[uid]
            for load in self.polygon_loads:
                if load.massless:
                    cmult = massless_load_factor
                else:
                    cmult = load_factor
                surf_load = load.value
                load_val = surf_load * area

                if isinstance(loaded_elm, Node):
                    lcase.node_loads[loaded_elm.uid].add(
                        np.array(
                            [0.00, 0.00, -load_val * cmult, 0.00, 0.00, 0.00]
                        )
                    )
                    if not load.massless:
                        lcase.node_mass[loaded_elm.uid].add(
                            np.array(
                                [
                                    load_val / g_const,
                                    load_val / g_const,
                                    load_val / g_const,
                                    0.00,
                                    0.00,
                                    0.00,
                                ]
                            )
                        )

                elif isinstance(
                    loaded_elm, (ElasticBeamColumn, DispBeamColumn)
                ):
                    length = loaded_elm.clear_length()
                    load_per_length = load_val / length
                    udl_obj = lcase.line_element_udl[loaded_elm.uid]
                    udl_obj.add_glob(
                        np.array([0.00, 0.00, -load_per_length * cmult])
                    )
                    if not load.massless:
                        half_mass = load_val / 2.00 / g_const
                        lcase.node_mass[loaded_elm.nodes[0].uid].add(
                            np.array([half_mass] * 3 + [0.00] * 3)
                        )
                        lcase.node_mass[loaded_elm.nodes[1].uid].add(
                            np.array([half_mass] * 3 + [0.00] * 3)
                        )

                elif isinstance(loaded_elm, TwoNodeLink):
                    for node in loaded_elm.nodes:
                        lcase.node_loads[node.uid].add(
                            np.array(
                                [0.00, 0.00,
                                 -load_val * cmult / 2.00,
                                 0.00, 0.00, 0.00]
                            )
                        )
                        if not load.massless:
                            lcase.node_mass[node.uid].add(
                                np.array(
                                    [
                                        load_val / g_const / 2.00,
                                        load_val / g_const / 2.00,
                                        load_val / g_const / 2.00,
                                        0.00,
                                        0.00,
                                        0.00,
                                    ]
                                )
                            )

                else:
                    raise TypeError("This should never happen!")
