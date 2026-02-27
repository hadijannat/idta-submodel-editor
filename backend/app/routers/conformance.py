"""
Conformance API endpoints for exported AAS artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile

from app.config import get_settings
from app.errors import APIError, ErrorCode
from app.schemas.conformance import ConformanceCheckResponse
from app.services.conformance import run_conformance_check
from app.utils.upload_security import FileType, UploadValidator, read_upload_file

router = APIRouter(prefix="/api/conformance", tags=["conformance"])


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


@router.post("/check", response_model=ConformanceCheckResponse)
async def check_conformance(
    file: Annotated[UploadFile, File(...)],
    format_name: Annotated[Literal["aasx", "json"] | None, Form()] = None,
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
            decoded = content.decode("utf-8")
            json.loads(decoded)
        except Exception as exc:
            raise APIError(
                code=ErrorCode.INVALID_FILE_TYPE,
                message="Uploaded JSON artifact is invalid",
                detail={"filename": file.filename},
            ) from exc

    suffix = f".{resolved_format}"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)

        result = run_conformance_check(temp_path, resolved_format)
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
