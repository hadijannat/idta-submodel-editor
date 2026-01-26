"""Smart Mapper service for profiling and mapping datasets."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.services.semantic import SemanticService

from fastapi import UploadFile

from app.config import get_settings
from app.errors import APIError, ErrorCode
from app.schemas.form_data import SubmodelFormData
from app.schemas.mapper import (
    DatasetColumnProfile,
    DatasetFileInfo,
    DatasetProfile,
    DatasetSheetInfo,
    MapperAutoSuggestRequest,
    MapperAutoSuggestResponse,
    MapperDiagnostic,
    MapperRecipe,
    MapperRunRequest,
    MapperRunResponse,
    MapperSuggestedMapping,
    MapperTargetFieldInfo,
)
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService, PDFExportService
from app.services.mapper.apply import apply_mapping, apply_mapping_into
from app.services.mapper.parsers import (
    DatasetReader,
    build_examples,
    normalize_header,
    summarize_types,
)
from app.services.parser import ParserService
from app.services.validation import validate_form_data

logger = logging.getLogger(__name__)


class MapperService:
    def __init__(
        self,
        fetcher: TemplateFetcherService,
        parser: ParserService,
        hydrator: HydratorService,
        pdf_service: PDFExportService | None = None,
        semantic_service: "SemanticService | None" = None,
    ) -> None:
        self.fetcher = fetcher
        self.parser = parser
        self.hydrator = hydrator
        self.pdf_service = pdf_service
        self.semantic_service = semantic_service
        self.settings = get_settings()
        self.base_dir = self.settings.mapper_cache_dir
        self.upload_dir = self.base_dir / "uploads"
        self.profile_dir = self.base_dir / "profiles"
        self.recipe_dir = self.base_dir / "recipes"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.recipe_dir.mkdir(parents=True, exist_ok=True)

    async def profile(
        self,
        file: UploadFile,
        sheet: str | None,
        header_row: int | None,
        sample_rows: int,
    ) -> DatasetProfile:
        file_type = self._detect_file_type(file.filename, file.content_type)
        if file_type not in {"csv", "xlsx"}:
            raise APIError(
                code=ErrorCode.INVALID_FILE_TYPE,
                message="Unsupported file type. Only CSV and XLSX files are supported.",
            )

        profile_id = uuid.uuid4().hex
        suffix = ".xlsx" if file_type == "xlsx" else ".csv"
        file_path = self.upload_dir / f"{profile_id}{suffix}"
        contents = await file.read()
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(contents) > max_bytes:
            raise APIError(
                code=ErrorCode.FILE_TOO_LARGE,
                message=f"File too large. Maximum size is {self.settings.max_upload_size_mb}MB",
            )
        file_path.write_bytes(contents)

        reader = DatasetReader(file_path, file_type, sheet=sheet, header_row=header_row or 1)
        sheets = [
            DatasetSheetInfo(name=name, rows=rows, cols=cols)
            for name, rows, cols in reader.list_sheets()
        ]

        rows = reader.read_rows(max_rows=(header_row or 1) + sample_rows)
        if not rows:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="No rows found in file",
            )

        header_index = (header_row or 1) - 1
        if header_index >= len(rows):
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="Header row out of range",
            )

        header = rows[header_index]
        header_values = [str(cell).strip() if cell is not None else "" for cell in header]
        normalized_headers = [
            normalize_header(text) if text else f"column_{idx+1}"
            for idx, text in enumerate(header_values)
        ]

        data_rows = rows[header_index + 1 :]
        if data_rows:
            from itertools import zip_longest

            column_values = list(zip_longest(*data_rows, fillvalue=None))
        else:
            column_values = []

        columns: list[DatasetColumnProfile] = []
        for idx, name in enumerate(header_values):
            values = list(column_values[idx]) if idx < len(column_values) else []
            inferred_type = summarize_types(values)
            examples = build_examples(values)
            null_count = sum(1 for v in values if v is None or str(v).strip() == "")
            null_rate = (null_count / len(values)) if values else 0.0
            distinct_count = len({str(v) for v in values if v is not None})
            columns.append(
                DatasetColumnProfile(
                    name_original=name or f"Column {idx+1}",
                    name_normalized=normalized_headers[idx],
                    index=idx,
                    inferred_type=inferred_type,
                    null_rate=null_rate,
                    distinct_count=distinct_count,
                    examples=examples,
                )
            )

        header_fingerprint = hashlib.sha256(
            "|".join(normalized_headers).encode("utf-8")
        ).hexdigest()

        profile = DatasetProfile(
            profile_id=profile_id,
            file=DatasetFileInfo(
                name=file.filename or file_path.name,
                size=len(contents),
                type=file.content_type,
            ),
            sheets=sheets,
            columns=columns,
            sample_rows=[[str(v) if v is not None else None for v in row] for row in data_rows[:sample_rows]],
            row_count=None,
            header_row=header_row or 1,
            warnings=[],
        )

        self._store_profile(
            profile,
            file_path,
            file_type=file_type,
            sheet=sheet,
            header_fingerprint=header_fingerprint,
        )

        return profile

    async def run(self, request: MapperRunRequest) -> MapperRunResponse:
        profile_meta = self._load_profile(request.profile_id)
        file_path = Path(profile_meta["file_path"])
        file_type = profile_meta["file_type"]
        sheet = profile_meta.get("sheet")
        header_row = profile_meta.get("header_row", 1)

        reader = DatasetReader(file_path, file_type, sheet=sheet, header_row=header_row)
        rows = reader.read_rows()
        if not rows:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="No rows found in file",
            )

        header_index = header_row - 1
        header = rows[header_index]
        header_map = {}
        for idx, cell in enumerate(header):
            if cell is None:
                continue
            raw = str(cell).strip()
            if not raw:
                continue
            header_map[raw] = idx
            header_map[normalize_header(raw)] = idx

        data_rows = rows[header_index + 1 :]
        mode = request.recipe.mode

        if mode.type == "single":
            row_index = request.row_index or 1
            if row_index < 1 or row_index > len(data_rows):
                raise APIError(
                    code=ErrorCode.BAD_REQUEST,
                    message="Row index out of range",
                    detail={"row_index": row_index, "max_rows": len(data_rows)},
                )
            row = data_rows[row_index - 1]
            form_data, diagnostics = apply_mapping(
                row,
                request.recipe.mappings,
                header_map,
                row_index,
            )
            return MapperRunResponse(
                mode=mode,
                diagnostics=diagnostics,
                form_data=form_data,
                row_count=len(data_rows),
            )

        if mode.type == "row-per-submodel":
            batch_data: list[dict] = []
            diagnostics: list[MapperDiagnostic] = []
            for idx, row in enumerate(data_rows, start=1):
                form_data, row_diagnostics = apply_mapping(
                    row,
                    request.recipe.mappings,
                    header_map,
                    idx,
                )
                batch_data.append(form_data)
                diagnostics.extend(row_diagnostics)
            return MapperRunResponse(
                mode=mode,
                diagnostics=diagnostics,
                form_data_batch=batch_data,
                row_count=len(data_rows),
            )

        if mode.type == "grouped":
            if not mode.group_by:
                raise APIError(
                    code=ErrorCode.BAD_REQUEST,
                    message="Grouped mode requires group_by columns",
                )

            group_indices: list[int] = []
            for name in mode.group_by:
                idx = header_map.get(name)
                if idx is None:
                    idx = header_map.get(normalize_header(name))
                if idx is None:
                    raise APIError(
                        code=ErrorCode.BAD_REQUEST,
                        message=f"Group-by column '{name}' not found",
                        detail={"column": name},
                    )
                group_indices.append(idx)

            grouped_rows: dict[tuple[str, ...], list[tuple[int, list]]] = {}
            for row_index, row in enumerate(data_rows, start=1):
                key = tuple(
                    ""
                    if idx >= len(row) or row[idx] is None
                    else str(row[idx]).strip()
                    for idx in group_indices
                )
                grouped_rows.setdefault(key, []).append((row_index, row))

            batch_data: list[dict] = []
            diagnostics: list[MapperDiagnostic] = []
            for rows_in_group in grouped_rows.values():
                form_data = {"elements": {}}
                for row_index, row in rows_in_group:
                    list_context: dict[str, int] = {}
                    diagnostics.extend(
                        apply_mapping_into(
                            form_data,
                            row,
                            request.recipe.mappings,
                            header_map,
                            row_index,
                            list_context=list_context,
                            preserve_existing=True,
                        )
                    )
                form_data.pop("_mapper_values", None)
                batch_data.append(form_data)

            return MapperRunResponse(
                mode=mode,
                diagnostics=diagnostics,
                form_data_batch=batch_data,
                row_count=len(data_rows),
            )

        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Unsupported mapping mode",
            detail={"mode_type": mode.type},
        )

    async def auto_suggest(
        self, request: MapperAutoSuggestRequest
    ) -> MapperAutoSuggestResponse:
        """Auto-suggest column-to-field mappings using semantic enrichment."""
        # Load profile and template schema
        profile_meta = self._load_profile(request.profile_id)
        columns = profile_meta.get("columns", [])

        template_bytes = await self._fetch_template_bytes(
            request.template_name, request.status, request.version
        )
        schema = self.parser.parse_aasx_to_ui_schema(template_bytes)

        # Extract target fields from schema
        target_fields = self._extract_target_fields(schema.get("elements", []))

        # Gather semantic IDs to resolve
        semantic_ids: list[str] = []
        for field in target_fields:
            if field.semantic_id:
                semantic_ids.append(field.semantic_id)

        # Resolve semantic IDs to enrich with synonyms
        semantic_resolved = 0
        semantic_errors = 0

        if request.use_semantics and self.semantic_service and semantic_ids:
            sem_map: dict[str, dict] = {}
            for sem_id in set(semantic_ids):
                try:
                    entry = await self.semantic_service.resolve(sem_id, None, "en")
                    if entry:
                        sem_map[sem_id] = {
                            "preferred_name": entry.preferredName,
                            "synonyms": entry.synonyms or [],
                            "labels": entry.labels or {},
                        }
                        semantic_resolved += 1
                except Exception as exc:
                    logger.debug("Semantic resolve failed for %s: %s", sem_id, exc)
                    semantic_errors += 1

            # Enrich target fields with resolved semantic info
            for field in target_fields:
                if field.semantic_id and field.semantic_id in sem_map:
                    info = sem_map[field.semantic_id]
                    if info["preferred_name"]:
                        field.semantic_label = info["preferred_name"]
                    field.semantic_synonyms = info.get("synonyms", [])
                    # Add labels in different languages as synonyms
                    for label in info.get("labels", {}).values():
                        if label and label not in field.semantic_synonyms:
                            field.semantic_synonyms.append(label)

        # Score columns against targets
        suggestions: list[MapperSuggestedMapping] = []
        used_targets: set[str] = set()

        for col in columns:
            col_name = col.get("name_original", "")
            col_idx = col.get("index", 0)
            col_normalized = col.get("name_normalized", "")

            best_match: MapperSuggestedMapping | None = None
            best_score = 0.0

            for field in target_fields:
                if field.id_short_path in used_targets:
                    continue

                score, reason = self._compute_match_score(
                    col_name, col_normalized, field
                )

                if score > best_score and score >= request.min_confidence:
                    best_score = score
                    best_match = MapperSuggestedMapping(
                        source_column=col_name,
                        source_index=col_idx,
                        target_path=field.id_short_path,
                        target_type=field.element_type,
                        target_value_type=field.value_type,
                        confidence=round(score, 3),
                        match_reason=reason,
                    )

            if best_match:
                suggestions.append(best_match)
                used_targets.add(best_match.target_path)

        return MapperAutoSuggestResponse(
            suggestions=suggestions,
            target_fields=target_fields,
            semantic_resolved=semantic_resolved,
            semantic_errors=semantic_errors,
        )

    def _extract_target_fields(
        self, elements: list[dict], path: list[str] | None = None
    ) -> list[MapperTargetFieldInfo]:
        """Recursively extract target fields from schema elements."""
        if path is None:
            path = []

        result: list[MapperTargetFieldInfo] = []
        leaf_types = {"Property", "MultiLanguageProperty", "Range", "File", "ReferenceElement"}

        for element in elements:
            model_type = element.get("modelType", "")
            id_short = element.get("idShort", "")

            if model_type == "SubmodelElementList":
                list_path = [*path, f"{id_short}[]"]
                template = element.get("itemTemplate") or (
                    element.get("items", [{}])[0] if element.get("items") else None
                )
                if template:
                    if template.get("modelType") in leaf_types:
                        template_id_short = template.get("idShort") or "value"
                        leaf_path = list_path + [template_id_short]
                        result.append(self._make_target_field(template, leaf_path))
                    else:
                        template_id_short = template.get("idShort") or ""
                        base_path = list_path + [template_id_short]
                        if template.get("elements"):
                            result.extend(self._extract_target_fields(template["elements"], base_path))
                        if template.get("statements"):
                            result.extend(self._extract_target_fields(template["statements"], base_path))
                continue

            next_path = [*path, id_short]

            if model_type in leaf_types:
                result.append(self._make_target_field(element, next_path))

            if element.get("elements"):
                result.extend(self._extract_target_fields(element["elements"], next_path))
            if element.get("statements"):
                result.extend(self._extract_target_fields(element["statements"], next_path))

        return result

    @staticmethod
    def _min_cardinality(cardinality: str) -> int:
        """Parse minimum cardinality from bracket or legacy formats."""
        import re

        value = str(cardinality or "").strip()
        mapping = {
            "ZeroToOne": "[0..1]",
            "ZeroToMany": "[0..*]",
            "OneToMany": "[1..*]",
            "One": "[1]",
            "Zero": "[0]",
        }
        if value in mapping:
            value = mapping[value]
        if value.startswith("[") and value.endswith("]"):
            match = re.match(r"^\[(\d+)", value)
            if match:
                return int(match.group(1))
        if value.isdigit():
            return int(value)
        return 1

    def _make_target_field(
        self, element: dict, path: list[str]
    ) -> MapperTargetFieldInfo:
        """Create a MapperTargetFieldInfo from an element."""
        cardinality = element.get("cardinality", "")
        required = self._min_cardinality(cardinality) >= 1

        semantic_id = None
        sem_ref = element.get("semanticId")
        if isinstance(sem_ref, str):
            semantic_id = sem_ref
        elif sem_ref and isinstance(sem_ref, dict):
            keys = sem_ref.get("keys", [])
            if keys and isinstance(keys, list):
                semantic_id = keys[-1].get("value")
        elif sem_ref is not None:
            semantic_id = str(sem_ref)

        return MapperTargetFieldInfo(
            id_short_path=".".join(path),
            element_type=element.get("modelType", "Property"),
            value_type=element.get("valueType"),
            label=element.get("idShort") or (path[-1] if path else ""),
            required=required,
            semantic_id=semantic_id,
            semantic_label=element.get("semanticLabel"),
            semantic_synonyms=[],
            languages=element.get("supportedLanguages"),
        )

    def _compute_match_score(
        self,
        col_name: str,
        col_normalized: str,
        field: MapperTargetFieldInfo,
    ) -> tuple[float, str]:
        """Compute match score between column and target field."""
        # Tokenize column name
        col_tokens = set(self._tokenize(col_name))
        if not col_tokens:
            return 0.0, ""

        # Build vocabulary for target
        vocab_parts = [field.id_short_path, field.label]
        if field.semantic_label:
            vocab_parts.append(field.semantic_label)
        vocab_parts.extend(field.semantic_synonyms)

        vocab_tokens: set[str] = set()
        for part in vocab_parts:
            vocab_tokens.update(self._tokenize(part))

        if not vocab_tokens:
            return 0.0, ""

        # Jaccard similarity
        intersection = col_tokens & vocab_tokens
        union = col_tokens | vocab_tokens
        jaccard = len(intersection) / len(union) if union else 0.0

        # Check for exact matches (boost)
        col_lower = col_name.lower().strip()
        exact_matches = [
            field.label.lower().strip(),
            field.semantic_label.lower().strip() if field.semantic_label else "",
        ]
        exact_matches.extend(s.lower().strip() for s in field.semantic_synonyms)

        match_reason = "token_similarity"

        if col_lower in exact_matches:
            jaccard = max(jaccard, 0.95)
            match_reason = "exact_match"

        # Boost for semantic match
        if field.semantic_synonyms and intersection:
            sem_tokens = set()
            for syn in field.semantic_synonyms:
                sem_tokens.update(self._tokenize(syn))
            if col_tokens & sem_tokens:
                jaccard = min(jaccard + 0.15, 1.0)
                match_reason = "semantic_match"

        return jaccard, match_reason

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text for comparison."""
        if not text:
            return []
        # Normalize: lowercase, split on non-alphanumeric
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        return [t for t in normalized.split() if t]

    async def export(self, request: MapperRunRequest):
        response = await self.run(request)
        template_bytes = await self._fetch_template_bytes(
            request.template_name, request.status, request.version
        )
        schema = self.parser.parse_aasx_to_ui_schema(template_bytes)

        mode = request.recipe.mode

        if mode.type == "single":
            if response.form_data is None:
                raise APIError(
                    code=ErrorCode.BAD_REQUEST,
                    message="No form data produced",
                )
            errors, warnings = validate_form_data(schema, response.form_data)
            if errors:
                raise APIError(
                    code=ErrorCode.VALIDATION_FAILED,
                    message="Validation failed",
                    detail={
                        "errors": [e.model_dump() for e in errors],
                        "warnings": [w.model_dump() for w in warnings],
                    },
                )
            return self._export_single(
                request.template_name,
                template_bytes,
                response.form_data,
                request.output_format,
            )

        if mode.type == "row-per-submodel":
            return self._export_batch(
                request.template_name,
                template_bytes,
                schema,
                response,
                request.output_format,
            )

        if mode.type == "grouped":
            return self._export_batch(
                request.template_name,
                template_bytes,
                schema,
                response,
                request.output_format,
            )

        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Unsupported mapping mode",
            detail={"mode_type": mode.type},
        )

    def _export_single(
        self,
        template_name: str,
        template_bytes: bytes,
        form_data: dict,
        output_format: Literal["aasx", "json", "pdf"],
    ) -> tuple[bytes, str, str]:
        if output_format == "aasx":
            content = self.hydrator.hydrate_submodel(template_bytes, form_data)
            return (
                content,
                "application/asset-administration-shell-package+xml",
                f"{template_name}.aasx",
            )
        if output_format == "json":
            content = self.hydrator.hydrate_to_json(template_bytes, form_data).encode(
                "utf-8"
            )
            return content, "application/json", f"{template_name}.json"
        if output_format == "pdf":
            if self.pdf_service is None:
                raise APIError(
                    code=ErrorCode.FEATURE_DISABLED,
                    message="PDF export not enabled",
                )
            content = self.pdf_service.generate_pdf_from_form(template_bytes, form_data)
            return content, "application/pdf", f"{template_name}.pdf"
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Unsupported export format",
            detail={"format": output_format},
        )

    def _export_batch(
        self,
        template_name: str,
        template_bytes: bytes,
        schema: dict,
        response: MapperRunResponse,
        output_format: Literal["aasx", "json", "pdf"],
    ) -> tuple[bytes, str, str]:
        import io
        import zipfile

        outputs = response.form_data_batch or []
        zip_buffer = io.BytesIO()
        errors_report: list[dict] = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for idx, form_data in enumerate(outputs, start=1):
                errors, warnings = validate_form_data(schema, form_data)
                if errors:
                    errors_report.append(
                        {
                            "row": idx,
                            "errors": [e.model_dump() for e in errors],
                            "warnings": [w.model_dump() for w in warnings],
                        }
                    )
                    continue
                content, _, filename = self._export_single(
                    template_name,
                    template_bytes,
                    form_data,
                    output_format,
                )
                zipf.writestr(f"{idx}-{filename}", content)

            if errors_report or response.diagnostics:
                zipf.writestr(
                    "errors.json",
                    json.dumps(
                        {
                            "validation": errors_report,
                            "mapping": [d.model_dump() for d in response.diagnostics],
                        },
                        indent=2,
                    ),
                )

        return (
            zip_buffer.getvalue(),
            "application/zip",
            f"{template_name}-batch.zip",
        )

    async def _fetch_template_bytes(
        self, template_name: str, status: str, version: str | None
    ) -> bytes:
        template_path = f"{status}/{template_name}"
        if version:
            template_path = f"{template_path}/{version}"
        return await self.fetcher.fetch_template_aasx(template_path)

    def _store_profile(
        self,
        profile: DatasetProfile,
        file_path: Path,
        file_type: str,
        sheet: str | None,
        header_fingerprint: str | None,
    ) -> None:
        data = profile.model_dump()
        data.update(
            {
                "file_path": str(file_path),
                "file_type": file_type,
                "sheet": sheet,
                "header_row": profile.header_row,
                "header_fingerprint": header_fingerprint,
            }
        )
        (self.profile_dir / f"{profile.profile_id}.json").write_text(
            json.dumps(data, indent=2)
        )

    def _load_profile(self, profile_id: str) -> dict:
        profile_path = self.profile_dir / f"{profile_id}.json"
        if not profile_path.exists():
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Profile not found",
                detail={"profile_id": profile_id},
            )
        return json.loads(profile_path.read_text())

    def list_recipes(self, user: dict | None) -> list[MapperRecipe]:
        recipe_dir = self._recipe_dir(user)
        recipes: list[MapperRecipe] = []
        for path in recipe_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                recipes.append(MapperRecipe(**data))
            except Exception:
                logger.warning("Skipping invalid recipe file: %s", path)
        return sorted(recipes, key=lambda recipe: recipe.name.lower())

    def get_recipe(self, name: str, user: dict | None) -> MapperRecipe:
        recipe_path = self._recipe_path(name, user)
        if not recipe_path.exists():
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Recipe not found",
                detail={"recipe_name": name},
            )
        return MapperRecipe(**json.loads(recipe_path.read_text()))

    def save_recipe(self, recipe: MapperRecipe, user: dict | None) -> MapperRecipe:
        recipe_path = self._recipe_path(recipe.name, user)
        recipe_path.write_text(recipe.model_dump_json(indent=2))
        return recipe

    def delete_recipe(self, name: str, user: dict | None) -> None:
        recipe_path = self._recipe_path(name, user)
        if not recipe_path.exists():
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Recipe not found",
                detail={"recipe_name": name},
            )
        recipe_path.unlink()

    @staticmethod
    def _detect_file_type(filename: str | None, content_type: str | None) -> str:
        if filename:
            lower = filename.lower()
            if lower.endswith(".xlsx"):
                return "xlsx"
            if lower.endswith(".csv"):
                return "csv"
        if content_type and "excel" in content_type:
            return "xlsx"
        return "csv"

    def _recipe_dir(self, user: dict | None) -> Path:
        scope = self._recipe_scope(user)
        recipe_dir = self.recipe_dir / scope
        recipe_dir.mkdir(parents=True, exist_ok=True)
        return recipe_dir

    def _recipe_path(self, name: str, user: dict | None) -> Path:
        safe_id = self._safe_recipe_id(name)
        return self._recipe_dir(user) / f"{safe_id}.json"

    @staticmethod
    def _safe_recipe_id(name: str) -> str:
        slug = "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in name.lower()
        ).strip("-")
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        return f"{slug}-{digest}" if slug else digest

    @staticmethod
    def _recipe_scope(user: dict | None) -> str:
        if user and user.get("sub"):
            digest = hashlib.sha256(str(user["sub"]).encode("utf-8")).hexdigest()[:12]
            return f"user-{digest}"
        return "public"
