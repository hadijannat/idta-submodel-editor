from pathlib import Path

import pytest

from app.services.semantic.offline_provider import OfflineSemanticProvider
from app.services.semantic.normalize import normalize_identifier


@pytest.mark.asyncio
async def test_offline_provider_search_and_resolve():
    data_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "semantic"
        / "data"
        / "eclass_sample.json"
    )
    provider = OfflineSemanticProvider(
        provider_id="eclass_offline",
        label="ECLASS",
        data_path=data_path,
        enabled=True,
    )

    results, total = await provider.search("Torque", "property", "en", 10, 0)
    assert total >= 1
    assert results[0].preferredName == "Torque"

    entry = await provider.resolve("0173-1#02-AAO677#002", "en")
    assert entry is not None
    assert entry.preferredName == "Torque"


def test_normalize_identifier_iri():
    canonical_id, canonical_iri = normalize_identifier(
        "https://api.eclass-cdp.com/0173-1#02-AAO677#002"
    )
    assert canonical_iri is not None
    assert canonical_id.endswith("#002")
