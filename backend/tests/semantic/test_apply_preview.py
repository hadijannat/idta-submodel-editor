from app.schemas.semantic import SemanticEntry
from app.services.semantic.apply import preview_application


def test_apply_preview_prefers_iri():
    entry = SemanticEntry(
        provider="eclass_offline",
        kind="property",
        canonicalId="0173-1#02-AAO677#002",
        canonicalIri="https://api.eclass-cdp.com/0173-1#02-AAO677#002",
        preferredName="Torque",
    )

    semantic_id, element_type, value_type, warnings, notes = preview_application(
        entry,
        current_element_type="Property",
        current_value_type="xs:double",
        prefer_iri=True,
    )

    assert semantic_id == entry.canonicalIri
    assert warnings == []
    assert notes == []


def test_apply_preview_warns_on_mismatch():
    entry = SemanticEntry(
        provider="eclass_offline",
        kind="property",
        canonicalId="0173-1#02-AAB113#004",
        canonicalIri=None,
        preferredName="Manufacturer name",
        datatypeHint="STRING_TRANSLATABLE",
    )

    semantic_id, element_type, value_type, warnings, notes = preview_application(
        entry,
        current_element_type="Property",
        current_value_type="xs:string",
        prefer_iri=True,
    )

    assert semantic_id == entry.canonicalId
    assert element_type == "MultiLanguageProperty"
    assert warnings
