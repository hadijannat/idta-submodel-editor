import io

import pytest
from basyx.aas import model

from app.services.hydrator import HydratorService


@pytest.mark.asyncio
async def test_hydrator_clears_multilang_and_blob():
    hydrator = HydratorService()
    multilang = model.MultiLanguageProperty(id_short="ml")
    multilang.value = model.MultiLanguageTextType({"en": "Hello"})

    blob = model.Blob(id_short="blob", content_type="text/plain")
    blob.value = b"data"

    hydrator._hydrate_multilang(multilang, {"value": {"en": ""}})
    hydrator._hydrate_blob(blob, {"value": ""})

    assert multilang.value is None
    assert blob.value is None


@pytest.mark.asyncio
async def test_hydrator_clears_reference_and_relationship():
    hydrator = HydratorService()
    ref = model.ReferenceElement(id_short="ref")
    ref.value = model.ExternalReference(key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:old"),))

    rel = model.RelationshipElement(
        id_short="rel",
        first=model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:first"),)
        ),
        second=model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:second"),)
        ),
    )

    hydrator._hydrate_reference(ref, {"value": ""})
    hydrator._hydrate_relationship(rel, {"first": "", "second": ""})

    assert ref.value is None
    assert rel.first is None
    assert rel.second is None
