import pytest

from exportkit import registry
from exportkit.errors import ExportError

RECORDS = [
    {"id": 1, "name": "apple", "value": 3.5},
    {"id": 2, "name": "banana", "value": 7},
]


@pytest.mark.parametrize("name", registry.available())
def test_export_returns_text(name):
    out = registry.get(name).export(RECORDS)
    assert isinstance(out, str) and out.strip() and out.endswith("\n")


@pytest.mark.parametrize("name", registry.available())
def test_empty_input_raises(name):
    with pytest.raises(ExportError):
        registry.get(name).export([])


@pytest.mark.parametrize("name", registry.available())
def test_missing_field_raises(name):
    with pytest.raises(ExportError):
        registry.get(name).export([{"id": 1, "name": "no-value"}])


def test_json_output():
    out = registry.get("json").export(RECORDS)
    assert out == (
        '[\n  {\n    "id": 1,\n    "name": "apple",\n    "value": 3.5\n  },'
        '\n  {\n    "id": 2,\n    "name": "banana",\n    "value": 7\n  }\n]\n'
    )


def test_csv_output():
    out = registry.get("csv").export(RECORDS)
    assert out == "id,name,value\n1,apple,3.5\n2,banana,7\n"


def test_xml_output():
    out = registry.get("xml").export(RECORDS)
    assert out == (
        "<records>\n"
        "  <record><id>1</id><name>apple</name><value>3.5</value></record>\n"
        "  <record><id>2</id><name>banana</name><value>7</value></record>\n"
        "</records>\n"
    )
