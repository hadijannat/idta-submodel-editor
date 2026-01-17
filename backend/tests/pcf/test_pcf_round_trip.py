"""Golden round-trip tests for PCF values."""

import json
import os

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.hydrator import HydratorService


def test_pcf_co2eq_round_trip():
    os.environ.setdefault("SECRET_KEY", "x" * 32)

    submodel = model.Submodel(id_="urn:pcf-roundtrip", id_short="CarbonFootprint")
    pcf_co2eq = model.Property(id_short="PcfCO2eq", value_type=model.datatypes.Double)
    submodel.submodel_element.add(pcf_co2eq)

    aasx_bytes = _build_aasx_bytes(submodel)

    form_data = {"elements": {"PcfCO2eq": {"value": "123.45"}}}

    json_output = HydratorService().hydrate_to_json(aasx_bytes, form_data)
    payload = json.loads(json_output)

    submodels = payload.get("submodels") or []
    assert submodels, "Hydrated JSON should include submodels"

    values = []
    for sm in submodels:
        if sm.get("idShort") != "CarbonFootprint":
            continue
        for elem in sm.get("submodelElements", []):
            if elem.get("idShort") == "PcfCO2eq":
                values.append(elem.get("value"))

    assert values, "PcfCO2eq should be present in hydrated submodel"
    assert values[0] == "123.45"


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
