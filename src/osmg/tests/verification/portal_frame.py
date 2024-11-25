"""
Single-bay single-story portal frame model.

Length units: in
Force units: lb
"""

import numpy as np

from osmg.analysis.common import UDL, PointLoad
from osmg.analysis.load_case import LoadCaseRegistry
from osmg.analysis.supports import FixedSupport
from osmg.core.model import Model2D
from osmg.creators.component import BeamColumnCreator
from osmg.creators.section import AISC_Database_Section_Creator
from osmg.model_objects.node import Node
from osmg.model_objects.section import ElasticSection

# Instantiate model object
frame = Model2D('Frame model')

# Add grid lines
grids = frame.grid_system
grids.add_level('Base', 0.00)
grids.add_level('Level 1', 15.00 * 12.00)
grids.add_grid('A', 0.00)
grids.add_grid('B', 25.00 * 12.00)

# Add primary nodes
for position in (('A', 'Base'), ('B', 'Base'), ('A', 'Level 1'), ('B', 'Level 1')):
    frame.nodes.add(
        Node(
            uid_generator=frame.uid_generator,
            coordinates=(
                grids.get_grid_location(position[0]),
                grids.get_level_elevation(position[1]),
            ),
        ),
    )

# Find the node at 'A'-'Base'
found_node = frame.nodes.search_by_coordinates_or_raise(
    (
        grids.get_grid_location('A'),
        grids.get_level_elevation('Base'),
    )
)

# Define a common section
simple_section = ElasticSection(
    frame.uid_generator,
    'Test Section',
    e_mod=1e3,
    area=1e3,
    i_y=1.00,
    i_x=1.00,
    g_mod=1.00,
    j_mod=1.00,
    sec_w=0.00,
)
# Define an AISC W section
section_creator = AISC_Database_Section_Creator(frame.uid_generator)
standard_section = section_creator.load_elastic_section('W14X38', 1.00, 1.00)
# Add members
bcg = BeamColumnCreator(frame, 'elastic')
for placement_data in (
    ('A', 'Level 1', 'A', 'Base', simple_section),
    ('B', 'Level 1', 'B', 'Base', simple_section),
    ('A', 'Level 1', 'B', 'Level 1', standard_section),
):
    bcg.generate_plain_component_assembly(
        tags={'column'},
        node_i=frame.nodes.search_by_coordinates_or_raise(
            (
                grids.get_grid_location(placement_data[0]),
                grids.get_level_elevation(placement_data[1]),
            )
        ),
        node_j=frame.nodes.search_by_coordinates_or_raise(
            (
                grids.get_grid_location(placement_data[2]),
                grids.get_level_elevation(placement_data[3]),
            )
        ),
        n_sub=3,
        eo_i=np.array((0.00, 0.0)),
        eo_j=np.array((0.00, 0.0)),
        section=placement_data[4],
        transf_type='Linear',
    )


# [X] Load case registry -> stores load cases.
# [X] Will have separate place for dead, live, seismic, other.

# [X] We'll have "analysis types": static, response spectrum, transient.

# On results... Need to figure out a clean way to set them up, like recorders.
# Each load case will run the analysis and store the results.
# Each load case will need to have configuration on what results to keep track of.


# It should still be possible to define a very simple load casea and run an analysis manually
#   Let's consider doing this with the loads defined in the `other` category.
# [X] load case registry -> should be able to run all analyses with one method.
#   and then be able to get basic forces and node displacements considering case combinations.

# Once a prototype is written,
#     Add another load case and a combination.
#     Write convenience code to retrieve basic force data for
#     **assembiles**, including combinations.

# [X] Add a load case,
# [X] Add supports,
# [X] update plotting.

# ~~~ I am here ~~~
# [X] Run a linear elastic analysis.
# Plot results.

# Plot combined basic forces.

# Fix "hinged" component assembly.
# Figure out a better way to manage "recorders" and store results.
# Add a quick nonlinear validation analysis.

# Improve design code.

# Continue working on study.

# Create the load case registry
load_case_registry = LoadCaseRegistry(frame)

# Add supports at level 'Base' for all load cases 'A', 'B', and 'C'
fixed_support = FixedSupport((True, True, True))
for tag in ('A', 'B', 'C'):
    # Note: the load cases of type `other` with the given tags are
    # automatically instantiated before the supports are added.
    load_case_registry.dead[tag].add_supports_at_level(frame, fixed_support, 'Base')


# Locate the nodes at 'A'-'Level 1' and 'B'-'Level 1'
node_a_level1 = frame.nodes.search_by_coordinates_or_raise(
    (grids.get_grid_location('A'), grids.get_level_elevation('Level 1'))
)
node_b_level1 = frame.nodes.search_by_coordinates_or_raise(
    (grids.get_grid_location('B'), grids.get_level_elevation('Level 1'))
)

# Search for the top beam (component assembly connected to these nodes)
top_beam = frame.components.search_by_nodes_or_raise([node_a_level1, node_b_level1])

# Add UDLs to the top beam in load cases 'A' and 'B'
load_case_registry.dead['A'].load_registry.element_udl[top_beam.uid] = UDL(
    (0.0, -10.00)
)  # lb/in

load_case_registry.dead['B'].load_registry.element_udl[top_beam.uid] = UDL(
    (0.0, +10.00)
)  # lb/in

# Add a concentrated point load at 'A'-'Level 1' in load case 'C'
load_case_registry.dead['C'].load_registry.nodal_loads[node_a_level1.uid] = (
    PointLoad(
        (10.00, 0.00, 0.00, 0.00)  # lb
    )
)

load_case_registry.run()

# fig = Figure3D(Figure3DConfiguration(num_space_dimensions=2))
# fig.add_nodes(list(frame.nodes.values()), 'primary')
# fig.add_components(list(frame.components.values()))
# fig.add_supports(frame.nodes, load_case_registry.dead['A'].fixed_supports, 12.00)
# fig.show()

# load_case_registry.dead['A'].analysis.settings.result_directory = '/tmp/check2'
# load_case_registry.dead['A'].analysis.define_model_in_opensees(frame, load_case_registry.dead['A'])
# load_case_registry.dead['A'].analysis.define_loads_in_opensees(frame, load_case_registry.dead['A'])


# import matplotlib.pyplot as plt
# import opsvis as opsv
# opsv.plot_model()
# plt.show()

# import openseespy.opensees as ops
# import openseespy.opensees as ops
# ops.constraints('Transformation')
# ops.numberer('RCM')
# ops.system('BandGeneral')
# ops.test('NormDispIncr', 1.0e-6, 6, 2)
# ops.algorithm('Linear')
# ops.integrator('LoadControl', 1)
# ops.analysis('Static')
# ops.analyze(1)
print(load_case_registry.result_setup.directory)  # noqa: T201