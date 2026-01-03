"""
Export endpoints for generating various output formats.

Supports AASX, JSON, and PDF export formats.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.config import get_settings
from app.dependencies import get_fetcher, get_hydrator, get_parser, get_pdf_service
from app.schemas.form_data import ExportRequest, SubmodelFormData
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService, PDFExportService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/{template_name}")
async def export_submodel(
    template_name: str,
    form_data: SubmodelFormData,
    format: Annotated[
        Literal["aasx", "json", "pdf"],
        Query(description="Export format"),
    ] = "aasx",
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)] = None,
    hydrator: Annotated[HydratorService, Depends(get_hydrator)] = None,
    parser: Annotated[ParserService, Depends(get_parser)] = None,
    pdf_service: Annotated[PDFExportService | None, Depends(get_pdf_service)] = None,
) -> Response:
    """
    Export a filled submodel in the specified format.

    Formats:
    - aasx: AASX package (default)
    - json: JSON serialization
    - pdf: PDF report
    """
    try:
        template_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")

        if format == "aasx":
            content = hydrator.hydrate_submodel(template_bytes, form_data.model_dump())
            return Response(
                content=content,
                media_type="application/asset-administration-shell-package+xml",
                headers={
                    "Content-Disposition": f'attachment; filename="{template_name}.aasx"'
                },
            )

        elif format == "json":
            content = hydrator.hydrate_to_json(template_bytes, form_data.model_dump())
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{template_name}.json"'
                },
            )

        elif format == "pdf":
            settings = get_settings()
            if not settings.pdf_enabled or pdf_service is None:
                raise HTTPException(
                    status_code=501,
                    detail="PDF export is not enabled",
                )

            content = pdf_service.generate_pdf_from_form(
                template_bytes, form_data.model_dump()
            )
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{template_name}.pdf"'
                },
            )

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to export {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_name}/preview")
async def preview_submodel(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> dict:
    """
    Get a preview of the template structure without form data.

    Useful for displaying template information before editing.
    """
    try:
        aasx_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Return summary information
        return {
            "submodelId": schema["submodelId"],
            "idShort": schema["idShort"],
            "semanticId": schema.get("semanticId"),
            "description": schema.get("description"),
            "elementCount": len(schema.get("elements", [])),
            "elements": _summarize_elements(schema.get("elements", [])),
        }
    except Exception as e:
        logger.exception(f"Failed to preview {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


def _summarize_elements(elements: list[dict], depth: int = 0, max_depth: int = 2) -> list[dict]:
    """Create a summary of elements for preview."""
    if depth > max_depth:
        return []

    summary = []
    for elem in elements:
        elem_summary = {
            "idShort": elem["idShort"],
            "modelType": elem["modelType"],
            "semanticLabel": elem.get("semanticLabel"),
            "cardinality": elem.get("cardinality", "[1]"),
        }

        # Include nested elements for collections
        if elem["modelType"] == "SubmodelElementCollection":
            nested = elem.get("elements", [])
            elem_summary["childCount"] = len(nested)
            if depth < max_depth:
                elem_summary["children"] = _summarize_elements(
                    nested, depth + 1, max_depth
                )

        elif elem["modelType"] == "SubmodelElementList":
            elem_summary["listType"] = elem.get("typeValueListElement")
            elem_summary["itemCount"] = len(elem.get("items", []))

        summary.append(elem_summary)

    return summary


@router.post("/batch")
async def batch_export(
    requests: list[ExportRequest],
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
) -> Response:
    """
    Export multiple submodels as a ZIP archive.
    """
    import io
    import zipfile

    try:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, req in enumerate(requests):
                template_bytes = await fetcher.fetch_template_aasx(
                    f"published/{req.template_name}"
                )

                if req.format == "aasx":
                    content = hydrator.hydrate_submodel(
                        template_bytes, req.form_data.model_dump()
                    )
                    filename = req.filename or f"{req.template_name}_{idx}.aasx"
                elif req.format == "json":
                    content = hydrator.hydrate_to_json(
                        template_bytes, req.form_data.model_dump()
                    ).encode()
                    filename = req.filename or f"{req.template_name}_{idx}.json"
                else:
                    continue

                zf.writestr(filename, content)

        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="submodels.zip"'},
        )
    except Exception as e:
        logger.exception("Failed to create batch export")
        raise HTTPException(status_code=500, detail=str(e))
