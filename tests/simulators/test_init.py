from unittest.mock import Mock, patch

import pytest

from simulators import load_simulator
from simulators.base import Simulator


class MockSimulator(Simulator):
    def process_data(self):
        pass


def test_load_simulator_success():
    with (
        patch("os.path.dirname") as mock_dirname,
        patch("os.listdir") as mock_listdir,
        patch("importlib.import_module") as mock_import,
    ):
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = ["mock_simulator.py"]
        mock_module = Mock()
        mock_module.MockSimulator = MockSimulator
        mock_import.return_value = mock_module

        result = load_simulator("MockSimulator")

        mock_import.assert_called_once_with("simulators.plugins.mock_simulator")
        assert result == MockSimulator


def test_load_simulator_not_found():
    with patch("os.path.dirname") as mock_dirname, patch("os.listdir") as mock_listdir:
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = []

        with pytest.raises(
            ValueError, match="Simulator NonexistentSimulator not found"
        ):
            load_simulator("NonexistentSimulator")


def test_load_simulator_multiple_plugins():
    with (
        patch("os.path.dirname") as mock_dirname,
        patch("os.listdir") as mock_listdir,
        patch("importlib.import_module") as mock_import,
    ):
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = ["sim1.py", "sim2.py"]

        mock_module1 = Mock()
        mock_module1.Simulator1 = type("Simulator1", (Simulator,), {})
        mock_module2 = Mock()
        mock_module2.Simulator2 = type("Simulator2", (Simulator,), {})
        mock_import.side_effect = [mock_module1, mock_module2]

        result = load_simulator("Simulator2")

        assert mock_import.call_count == 2
        assert result == mock_module2.Simulator2


def test_load_simulator_non_simulator_class():
    with (
        patch("os.path.dirname") as mock_dirname,
        patch("os.listdir") as mock_listdir,
        patch("importlib.import_module") as mock_import,
    ):
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = ["mock.py"]

        class NonSimulator:
            pass

        mock_module = Mock()
        mock_module.NonSimulator = NonSimulator
        mock_import.return_value = mock_module

        with pytest.raises(ValueError, match="Simulator NonSimulator not found"):
            load_simulator("NonSimulator")
