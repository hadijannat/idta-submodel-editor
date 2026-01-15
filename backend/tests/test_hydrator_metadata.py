from basyx.aas import model

from app.services.hydrator import HydratorService


def test_apply_metadata_updates_submodel_fields():
    submodel = model.Submodel(
        id_="urn:old-submodel",
        id_short="OldId",
        submodel_element=[],
    )
    hydrator = HydratorService()

    metadata = {
        "idShort": "NewId",
        "submodelId": "urn:new-submodel",
        "administration": {
            "version": "2.1",
            "revision": "5",
            "templateId": "template-42",
        },
    }

    hydrator._apply_metadata(submodel, metadata)

    assert submodel.id_short == "NewId"
    assert submodel.id_ == "urn:new-submodel"
    assert submodel.administration is not None
    assert submodel.administration.version == "2.1"
    assert submodel.administration.revision == "5"
    assert submodel.administration.template_id == "template-42"
