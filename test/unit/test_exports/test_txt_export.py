from festim import TXTExport, Stepsize
import fenics as f
import os
import pytest
from pathlib import Path


class TestWrite:
    @pytest.fixture
    def function(self):
        mesh = f.UnitIntervalMesh(10)
        V = f.FunctionSpace(mesh, "P", 1)
        u = f.Function(V)

        return u

    @pytest.fixture
    def function_subspace(self):
        mesh = f.UnitIntervalMesh(10)
        V = f.VectorFunctionSpace(mesh, "P", 1, 2)
        u = f.Function(V)

        return u.sub(0)

    @pytest.fixture
    def my_export(self, tmpdir):
        d = tmpdir.mkdir("test_folder")
        my_export = TXTExport("solute", "solute_label", str(Path(d)), times=[1, 2, 3])

        return my_export

    def test_file_exists(self, my_export, function):
        current_time = 1
        nb_iteration = 1
        my_export.function = function
        my_export.write(current_time=current_time, nb_iteration=nb_iteration, steady=False)
        my_export.write(current_time=current_time, nb_iteration=nb_iteration, steady=True)
        
        assert os.path.exists(
            "{}/{}_transient.txt".format(my_export.folder, my_export.label)
        )
        assert os.path.exists(
            "{}/{}_steady.txt".format(my_export.folder, my_export.label)
        )

    def test_file_doesnt_exist(self, my_export, function):
        current_time = 10
        nb_iteration = 1
        my_export.function = function
        my_export.write(current_time=current_time, nb_iteration=nb_iteration, steady=False)

        assert not os.path.exists(
            "{}/{}_transient.txt".format(my_export.folder, my_export.label)
        )

    def test_create_folder(self, my_export, function):
        """Checks that write() creates the folder if it doesn't exist"""
        current_time = 1
        nb_iteration = 1
        my_export.function = function
        my_export.folder += "/folder2"
        my_export.write(current_time=current_time, nb_iteration=nb_iteration, steady=False)

        assert os.path.exists(
            "{}/{}_transient.txt".format(my_export.folder, my_export.label)
        )

    def test_subspace(self, my_export, function_subspace):
        current_time = 1
        nb_iteration = 1
        my_export.function = function_subspace
        my_export.write(current_time=current_time, nb_iteration=nb_iteration, steady=False)

        assert os.path.exists(
            "{}/{}_transient.txt".format(my_export.folder, my_export.label)
        )


class TestIsItTimeToExport:
    @pytest.fixture
    def my_export(self, tmpdir):
        d = tmpdir.mkdir("test_folder")
        my_export = TXTExport("solute", "solute_label", str(Path(d)), times=[1, 2, 3])

        return my_export

    def test_true(self, my_export):
        assert my_export.is_it_time_to_export(2)
        assert my_export.is_it_time_to_export(3)
        assert my_export.is_it_time_to_export(1)

    def test_false(self, my_export):
        assert not my_export.is_it_time_to_export(-1)
        assert not my_export.is_it_time_to_export(0)
        assert not my_export.is_it_time_to_export(5)
        assert not my_export.is_it_time_to_export(1.5)


class TestWhenIsNextTime:
    @pytest.fixture
    def my_export(self, tmpdir):
        d = tmpdir.mkdir("test_folder")
        my_export = TXTExport("solute", "solute_label", str(Path(d)), times=[1, 2, 3])

        return my_export

    def test_there_is_a_next_time(self, my_export):
        assert my_export.when_is_next_time(2) == 3
        assert my_export.when_is_next_time(1) == 2
        assert my_export.when_is_next_time(0) == 1
        assert my_export.when_is_next_time(0.5) == 1

    def test_last(self, my_export):
        assert my_export.when_is_next_time(3) is None
        assert my_export.when_is_next_time(4) is None


class TestIsItFirstTimeToExport:
    @pytest.fixture
    def my_export(self, tmpdir):
        d = tmpdir.mkdir("test_folder1")
        my_export = TXTExport("solute", "solute_label", str(Path(d)), times=[1, 2, 3])
        
        return my_export

    @pytest.fixture
    def my_export_all_times(self, tmpdir):
        d = tmpdir.mkdir("test_folder2")
        my_export_all_times = TXTExport("solute", "solute_label", str(Path(d)))
        
        return my_export_all_times

    def test_true(self, my_export, my_export_all_times):
        assert my_export.is_it_first_time_to_export(1, 0)
        assert my_export.is_it_first_time_to_export(1, 0)
        assert my_export_all_times.is_it_first_time_to_export(1, 0)
        assert my_export_all_times.is_it_first_time_to_export(5, 0)

    def test_false(self, my_export, my_export_all_times):
        assert not my_export.is_it_first_time_to_export(2, 0)
        assert not my_export.is_it_first_time_to_export(3, 0)
        assert not my_export.is_it_first_time_to_export(0, 0)
        assert not my_export.is_it_first_time_to_export(0, 0)
        assert not my_export_all_times.is_it_first_time_to_export(1, 1)
        assert not my_export_all_times.is_it_first_time_to_export(5, 2)
