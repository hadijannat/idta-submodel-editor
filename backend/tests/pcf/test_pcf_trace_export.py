"""Tests for PCF trace export artifacts."""

import json
import os

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.hydrator import HydratorService
from app.services.pcf.activity_list import ensure_activity_list_in_submodel


def test_pcf_trace_qualifier_and_file_added():
    submodel = model.Submodel(id_="urn:pcf-test", id_short="PCFTest")
    file_store = aasx.DictSupplementaryFileContainer()

    metadata = {
        "pcf": {
            "generatedAt": "2025-01-01T00:00:00Z",
            "totalCo2eKg": 12.34,
            "warnings": [],
            "activities": [
                {
                    "id": "act-1",
                    "name": "Electricity",
                    "category": "scope2",
                    "quantity": 100,
                    "unit": "kWh",
                    "factor_value": 0.123,
                    "factor_unit": "kg CO2e/kWh",
                }
            ],
        }
    }

    HydratorService()._apply_pcf_trace(submodel, file_store, metadata)

    trace_qualifier = submodel.get_qualifier_by_type("PCFCalculationTrace")
    payload = json.loads(trace_qualifier.value)
    assert payload["totalCo2eKg"] == 12.34
    assert payload["activities"][0]["name"] == "Electricity"

    file_qualifier = submodel.get_qualifier_by_type("PCFCalculationTraceFile")
    filename = file_qualifier.value
    assert filename in file_store


def test_pcf_activity_list_injected_from_metadata():
    submodel = model.Submodel(id_="urn:pcf-activity", id_short="PCFTest")
    form_data = {
        "metadata": {
            "pcf": {
                "activities": [
                    {
                        "id": "act-1",
                        "name": "Electricity",
                        "category": "scope2",
                        "quantity": 100,
                        "unit": "kWh",
                        "factor_value": 0.123,
                        "factor_unit": "kg CO2e/kWh",
                    }
                ]
            }
        },
        "elements": {},
    }

    ensure_activity_list_in_submodel(submodel, form_data)

    list_elements = [
        elem for elem in submodel.submodel_element if getattr(elem, "id_short", None) == "PCFActivities"
    ]
    assert list_elements, "PCFActivities list should be injected"

    activity_list = list_elements[0]
    assert isinstance(activity_list, model.SubmodelElementList)
    assert len(list(activity_list.value)) == 1


def test_hydrate_to_json_includes_pcf_activities():
    os.environ.setdefault("SECRET_KEY", "x" * 32)
    submodel = model.Submodel(id_="urn:pcf-export", id_short="CarbonFootprint")

    aasx_bytes = _build_aasx_bytes(submodel)

    form_data = {
        "metadata": {
            "pcf": {
                "activities": [
                    {
                        "id": "act-1",
                        "name": "Electricity",
                        "category": "scope2",
                        "quantity": 100,
                        "unit": "kWh",
                        "factor_value": 0.123,
                        "factor_unit": "kg CO2e/kWh",
                    }
                ]
            }
        },
        "elements": {},
    }

    json_output = HydratorService().hydrate_to_json(aasx_bytes, form_data)
    payload = json.loads(json_output)
    submodels = payload.get("submodels") or []
    assert submodels, "Hydrated JSON should include submodels"

    element_ids = []
    for sm in submodels:
        if sm.get("idShort") == "CarbonFootprint":
            for elem in sm.get("submodelElements", []):
                element_ids.append(elem.get("idShort"))

    assert "PCFActivities" in element_ids


def _build_aasx_bytes(submodel: model.Submodel) -> bytes:
    object_store = model.DictObjectStore()
    file_store = aasx.DictSupplementaryFileContainer()
    object_store.add(submodel)

    from io import BytesIO

    stream = BytesIO()
    with aasx.AASXWriter(stream) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml",
            object_store,
            file_store,
            write_json=False,
        )
    return stream.getvalue()
