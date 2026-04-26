"""
Conformance API endpoints for exported AAS artifacts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import tempfile
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings
from app.dependencies import get_current_user
from app.dependencies import get_fetcher, get_hydrator, get_parser
from app.errors import APIError, ErrorCode
from app.schemas.form_data import SubmodelFormData
from app.schemas.pcf import PCFValidateRequest
from app.schemas.conformance import ConformanceCheckResponse
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService
from app.services.pcf import is_pcf_template, validate_pcf
from app.services.conformance import run_conformance_check
from app.services.validation import validate_form_data
from app.utils.upload_security import FileType, UploadValidator, read_upload_file

router = APIRouter(prefix="/api/conformance", tags=["conformance"])
logger = logging.getLogger(__name__)


class ConformanceTemplateRequest(BaseModel):
    """Run conformance check directly from template + form payload."""

    template_name: str = Field(description="Template name")
    form_data: SubmodelFormData = Field(description="Filled form payload")
    format_name: Literal["aasx", "json"] = Field(
        default="aasx",
        description="Artifact format used for conformance",
    )
    template_status: Literal["published", "deprecated"] = Field(
        default="published",
        description="Template status filter",
    )
    template_version: str | None = Field(
        default=None,
        description="Optional template version",
    )


def _infer_format(filename: str | None) -> Literal["aasx", "json"]:
    if not filename or "." not in filename:
        raise APIError(
            code=ErrorCode.INVALID_FILE_TYPE,
            message="Could not infer artifact format from filename",
            detail={"filename": filename},
        )
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "aasx":
        return "aasx"
    if ext == "json":
        return "json"
    raise APIError(
        code=ErrorCode.INVALID_FILE_TYPE,
        message="Unsupported conformance file type",
        detail={"filename": filename, "supported": [".aasx", ".json"]},
    )


def _to_response(
    format_name: Literal["aasx", "json"],
    content: bytes,
) -> ConformanceCheckResponse:
    suffix = f".{format_name}"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)

        try:
            result = run_conformance_check(temp_path, format_name)
        except APIError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error running conformance check")
            raise APIError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Conformance check failed",
            ) from exc
        return ConformanceCheckResponse(
            passed=result.passed,
            errors=result.errors,
            warnings=result.warnings,
            engine_version=result.engine_version,
            duration_ms=result.duration_ms,
            format=result.format,
        )
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.post("/check", response_model=ConformanceCheckResponse)
async def check_conformance(
    file: Annotated[UploadFile, File(...)],
    format_name: Annotated[Literal["aasx", "json"] | None, Form()] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ConformanceCheckResponse:
    """
    Validate exported AASX/JSON artifacts using aas-test-engines.
    """
    settings = get_settings()
    content = await read_upload_file(file, settings.max_upload_size_mb * 1024 * 1024)

    resolved_format = format_name or _infer_format(file.filename)
    if resolved_format == "aasx":
        validator = UploadValidator(
            allowed_types=[FileType.AASX],
            max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        )
        validator.validate_and_raise(content, file.filename)
    else:
        # JSON validation for conformance input.
        try:
            json.loads(content)
        except Exception as exc:
            raise APIError(
                code=ErrorCode.INVALID_FILE_TYPE,
                message="Uploaded JSON artifact is invalid",
                detail={"filename": file.filename},
            ) from exc

    return _to_response(resolved_format, content)


@router.post("/check/form", response_model=ConformanceCheckResponse)
async def check_conformance_for_form(
    request: ConformanceTemplateRequest,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)] = None,
    hydrator: Annotated[HydratorService, Depends(get_hydrator)] = None,
    parser: Annotated[ParserService, Depends(get_parser)] = None,
) -> ConformanceCheckResponse:
    """Run conformance check without artifact round-tripping through the client."""
    try:
        template_path = f"{request.template_status}/{request.template_name}"
        if request.template_version:
            template_path = f"{template_path}/{request.template_version}"
        template_bytes = await fetcher.fetch_template_aasx(template_path)

        form_payload = request.form_data.model_dump()
        schema = parser.parse_aasx_to_ui_schema(template_bytes)
        errors, warnings = validate_form_data(schema, form_payload)
        if errors:
            raise APIError(
                code=ErrorCode.VALIDATION_FAILED,
                message="Validation failed",
                detail={
                    "errors": [err.model_dump() for err in errors],
                    "warnings": [warning.model_dump() for warning in warnings],
                },
            )

        if is_pcf_template(schema):
            pcf_result = validate_pcf(
                PCFValidateRequest(
                    form_data=form_payload,
                    template_schema=schema,
                )
            )
            if not pcf_result.valid:
                raise APIError(
                    code=ErrorCode.VALIDATION_FAILED,
                    message="PCF validation failed",
                    detail={
                        "errors": [err.model_dump() for err in pcf_result.errors],
                        "warnings": [warning.model_dump() for warning in pcf_result.warnings],
                        "completeness_score": pcf_result.completeness_score,
                    },
                )

        if request.format_name == "aasx":
            content = hydrator.hydrate_submodel(template_bytes, form_payload)
        else:
            content = hydrator.hydrate_to_json(template_bytes, form_payload)

        return _to_response(request.format_name, content)
    except APIError:
        raise
    except ValueError as exc:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(exc),
            detail={"template_name": request.template_name},
        ) from exc
    except Exception as exc:
        logger.exception("Failed to run conformance check for template payload")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to run conformance check",
        ) from exc
