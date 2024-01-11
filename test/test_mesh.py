import festim as F
from dolfinx import mesh as fenics_mesh
from mpi4py import MPI
import pytest
import numpy as np
import os
from dolfinx.io import XDMFFile
from dolfinx.mesh import meshtags

mesh_1D = fenics_mesh.create_unit_interval(MPI.COMM_WORLD, 10)
mesh_2D = fenics_mesh.create_unit_square(MPI.COMM_WORLD, 10, 10)
mesh_3D = fenics_mesh.create_unit_cube(MPI.COMM_WORLD, 10, 10, 10)


@pytest.mark.parametrize("mesh", [mesh_1D, mesh_2D, mesh_3D])
def test_get_fdim(mesh):
    my_mesh = F.Mesh(mesh)

    assert my_mesh.fdim == mesh.topology.dim - 1


def test_fdim_changes_when_mesh_changes():
    my_mesh = F.Mesh()

    for mesh in [mesh_1D, mesh_2D, mesh_3D]:
        my_mesh.mesh = mesh
        assert my_mesh.fdim == mesh.topology.dim - 1


@pytest.mark.parametrize("mesh", [mesh_1D, mesh_2D, mesh_3D])
def test_get_vdim(mesh):
    my_mesh = F.Mesh(mesh)

    assert my_mesh.vdim == mesh.topology.dim


def test_vdim_changes_when_mesh_changes():
    my_mesh = F.Mesh()

    for mesh in [mesh_1D, mesh_2D, mesh_3D]:
        my_mesh.mesh = mesh
        assert my_mesh.vdim == mesh.topology.dim


@pytest.mark.parametrize("mesh", [mesh_1D, mesh_2D, mesh_3D])
def test_meshtags_from_xdmf(tmp_path, mesh):
    """Test that the facet and volume meshtags are read correctly from the mesh XDMF files"""
    # create mesh functions
    fdim = mesh.topology.dim - 1
    vdim = mesh.topology.dim

    # create facet meshtags
    facet_indices = []
    for i in range(vdim):
        # add the boundary entities at 0 and 1 in each dimension
        facets_zero = fenics_mesh.locate_entities_boundary(
            mesh, fdim, lambda x: np.isclose(x[i], 0)
        )
        facets_one = fenics_mesh.locate_entities_boundary(
            mesh, fdim, lambda x: np.isclose(x[i], 1)
        )

        facet_indices += [facets_zero, facets_one]

    facet_tags = []

    for idx, _ in enumerate(facet_indices):
        # add tags for each boundary
        facet_tag = np.full(len(facet_indices[i]), idx + 1, dtype=np.int32)
        facet_tags.append(facet_tag)

    facet_meshtags = fenics_mesh.meshtags(mesh, fdim, facet_indices, facet_tags)

    # create volume meshtags
    num_cells = mesh.topology.index_map(vdim).size_local
    mesh_cell_indices = np.arange(num_cells, dtype=np.int32)
    # tag all volumes with 0
    tags_volumes = np.full(num_cells, 0, dtype=np.int32)
    # create 2 volumes for x<0.5 and x>0.5
    volume_indices_left = fenics_mesh.locate_entities(
        mesh,
        vdim,
        lambda x: x[0] <= 0.5,
    )

    volume_indices_right = fenics_mesh.locate_entities(
        mesh,
        vdim,
        lambda x: x[0] >= 0.5,
    )
    tags_volumes[volume_indices_left] = 2
    tags_volumes[volume_indices_right] = 3

    volume_meshtags = fenics_mesh.meshtags(mesh, vdim, mesh_cell_indices, tags_volumes)

    # write files
    surface_file_path = os.path.join(tmp_path, "facets_file.xdmf")
    surface_file = XDMFFile(MPI.COMM_WORLD, surface_file_path, "w")
    surface_file.write_mesh(mesh)
    surface_file.write_meshtags(facet_meshtags, mesh.geometry)

    volume_file_path = os.path.join(tmp_path, "volumes_file.xdmf")
    volume_file = XDMFFile(MPI.COMM_WORLD, volume_file_path, "w")
    volume_file.write_mesh(mesh)
    volume_file.write_meshtags(volume_meshtags, mesh.geometry)

    # read files
    my_model = F.HydrogenTransportProblem(
        mesh=F.MeshFromXDMF(
            volume_file=volume_file_path,
            facet_file=surface_file_path,
            mesh_name="mesh",
            surface_meshtags_name="mesh_tags",
            volume_meshtags_name="mesh_tags",
        )
    )
    my_model.define_meshtags_and_measures()

    # TEST
    assert volume_meshtags.dim == my_model.volume_meshtags.dim
    assert volume_meshtags.values.all() == my_model.volume_meshtags.values.all()
    assert facet_meshtags.dim == my_model.facet_meshtags.dim
    assert facet_meshtags.values.all() == my_model.facet_meshtags.values.all()


@pytest.mark.parametrize("vertices", [[1, 2, 3, 4], [0, 0.1, 0.2, 0.3, 0.4, 0.5]])
def test_mesh_vertices_from_list(vertices):
    """Check that giving vertices as a list is correctly processed and ends up as a np.ndarray for the mesh"""
    my_mesh = F.Mesh1D(vertices=vertices)

    assert isinstance(my_mesh.vertices, np.ndarray)


def test_mesh_custom_fenics_type_hints():
    """Test that the custom fenics mesh is correctly processed"""

    # BULD
    surface_indices = np.array([], dtype=np.int32)
    surface_tags = np.array([], dtype=np.int32)
    surface_meshtags = meshtags(mesh_1D, 0, surface_indices, surface_tags)

    num_cells = mesh_1D.topology.index_map(1).size_local
    mesh_cell_indices = np.arange(num_cells, dtype=np.int32)
    tags_volumes = np.full(num_cells, 1, dtype=np.int32)
    volume_meshtags = meshtags(mesh_1D, 1, mesh_cell_indices, tags_volumes)

    # TEST
    F.CustomFenicsMesh(
        mesh=mesh_1D, surface_meshtags=surface_meshtags, volume_meshtags=volume_meshtags
    )
