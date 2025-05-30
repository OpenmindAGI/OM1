from unittest.mock import Mock, patch

import pytest

from backgrounds import load_background
from backgrounds.base import Background


class MockBackground(Background):
    def run(self):
        pass


def test_load_background_success():
    with (
        patch("os.path.dirname") as mock_dirname,
        patch("os.listdir") as mock_listdir,
        patch("importlib.import_module") as mock_import,
    ):
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = ["mock_background.py"]
        mock_module = Mock()
        mock_module.MockBackground = MockBackground
        mock_import.return_value = mock_module

        result = load_background("MockBackground")

        mock_import.assert_called_once_with("backgrounds.plugins.mock_background")
        assert result == MockBackground


def test_load_background_not_found():
    with patch("os.path.dirname") as mock_dirname, patch("os.listdir") as mock_listdir:
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = []

        with pytest.raises(
            ValueError, match="Background NonexistentBackground not found"
        ):
            load_background("NonexistentBackground")


def test_load_background_multiple_plugins():
    with (
        patch("os.path.dirname") as mock_dirname,
        patch("os.listdir") as mock_listdir,
        patch("importlib.import_module") as mock_import,
    ):
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = ["bg1.py", "bg2.py"]

        mock_module1 = Mock()
        mock_module1.Background1 = type("Background1", (Background,), {})
        mock_module2 = Mock()
        mock_module2.Background2 = type("Background2", (Background,), {})
        mock_import.side_effect = [mock_module1, mock_module2]

        result = load_background("Background2")

        assert mock_import.call_count == 2
        assert result == mock_module2.Background2


def test_load_background_invalid_type():
    with (
        patch("os.path.dirname") as mock_dirname,
        patch("os.listdir") as mock_listdir,
        patch("importlib.import_module") as mock_import,
    ):
        mock_dirname.return_value = "/test/dir"
        mock_listdir.return_value = ["invalid_background.py"]

        class InvalidBackground:
            pass

        mock_module = Mock()
        mock_module.InvalidBackground = InvalidBackground
        mock_import.return_value = mock_module

        with pytest.raises(ValueError, match="Background InvalidBackground not found"):
            load_background("InvalidBackground")
