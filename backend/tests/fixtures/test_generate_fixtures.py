"""Tests for fixture generation helpers."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "generate_fixtures",
    Path(__file__).with_name("generate_fixtures.py"),
)
assert _SPEC and _SPEC.loader
generate_fixtures = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(generate_fixtures)
normalize_fixture_json = generate_fixtures.normalize_fixture_json


def test_normalize_fixture_json_sorts_value_reference_pairs_recursively():
    data = {
        "outer": [
            {
                "valueReferencePairs": [
                    {
                        "value": "ISO 14044",
                        "valueId": {
                            "keys": [
                                {
                                    "type": "GlobalReference",
                                    "value": "0173-1#07-ABV506#002",
                                }
                            ]
                        },
                    },
                    {
                        "value": "EN 15804",
                        "valueId": {
                            "keys": [
                                {
                                    "type": "GlobalReference",
                                    "value": "0173-1#07-ABU223#002",
                                }
                            ]
                        },
                    },
                ],
            }
        ]
    }

    normalized = normalize_fixture_json(data)

    pairs = normalized["outer"][0]["valueReferencePairs"]
    assert [pair["value"] for pair in pairs] == ["EN 15804", "ISO 14044"]
