from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.mapper import MapperService
from app.services.parser import ParserService


def test_mapper_required_and_semantic_id():
    mapper = MapperService(
        fetcher=TemplateFetcherService(),
        parser=ParserService(),
        hydrator=HydratorService(),
    )

    field = mapper._make_target_field(
        {
            "idShort": "Foo",
            "modelType": "Property",
            "cardinality": "[1]",
            "semanticId": "urn:foo",
        },
        ["Foo"],
    )
    assert field.required is True
    assert field.semantic_id == "urn:foo"

    field_optional = mapper._make_target_field(
        {
            "idShort": "Bar",
            "modelType": "Property",
            "cardinality": "[0..1]",
            "semanticId": {"keys": [{"value": "urn:bar"}]},
        },
        ["Bar"],
    )
    assert field_optional.required is False
    assert field_optional.semantic_id == "urn:bar"
