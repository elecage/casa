"""Specification for the YAML export format (not yet implemented).

YAML output is a block sequence of mappings, two-space indent, fields in
records.FIELD_ORDER, scalar values rendered with str():

- id: 1
  name: apple
  value: 3.5
"""

import pytest

from exportkit import registry
from exportkit.errors import ExportError

RECORDS = [
    {"id": 1, "name": "apple", "value": 3.5},
    {"id": 2, "name": "banana", "value": 7},
]

EXPECTED = (
    "- id: 1\n"
    "  name: apple\n"
    "  value: 3.5\n"
    "- id: 2\n"
    "  name: banana\n"
    "  value: 7\n"
)


def test_yaml_is_registered():
    assert "yaml" in registry.available()


def test_yaml_file_extension():
    assert registry.get("yaml").file_extension == ".yaml"


def test_yaml_renders_records_in_field_order():
    scrambled = [dict(reversed(list(r.items()))) for r in RECORDS]
    assert registry.get("yaml").export(scrambled) == EXPECTED


def test_yaml_empty_input_raises():
    exporter = registry.get("yaml")
    with pytest.raises(ExportError):
        exporter.export([])


def test_yaml_missing_field_raises():
    exporter = registry.get("yaml")
    with pytest.raises(ExportError):
        exporter.export([{"id": 3, "value": 1}])
