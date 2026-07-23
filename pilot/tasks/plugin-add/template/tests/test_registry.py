import pytest

from exportkit import registry
from exportkit.base import Exporter
from exportkit.errors import ExportError


def test_builtin_formats_are_registered():
    assert {"csv", "json", "xml"} <= set(registry.available())


def test_unknown_format_raises_export_error():
    with pytest.raises(ExportError):
        registry.get("parquet")


def test_registered_instances_match_their_name():
    for name in registry.available():
        exporter = registry.get(name)
        assert isinstance(exporter, Exporter)
        assert exporter.format_name == name
        assert exporter.file_extension.startswith(".")
