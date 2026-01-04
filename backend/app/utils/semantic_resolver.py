"""
Semantic ID resolution utilities.

Resolves human-readable labels from ConceptDescriptions linked via semantic IDs.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basyx.aas import model

logger = logging.getLogger(__name__)

# Default language priority for label resolution
DEFAULT_LANGUAGE_PRIORITY = ["en", "en-US", "en-GB", "de", "de-DE"]


def resolve_semantic_label(
    element: "model.SubmodelElement",
    object_store: "model.DictObjectStore",
    language_priority: list[str] | None = None,
) -> str | None:
    """
    Resolve human-readable label from ConceptDescription.

    Attempts to find the ConceptDescription referenced by the element's
    semantic ID and extract the preferred name in the requested language.

    Args:
        element: SubmodelElement with semantic_id
        object_store: Object store containing ConceptDescriptions
        language_priority: List of language codes in preference order

    Returns:
        Human-readable label or None if not found
    """
    from basyx.aas import model

    if language_priority is None:
        language_priority = DEFAULT_LANGUAGE_PRIORITY

    # Check if element has semantic ID
    if not hasattr(element, "semantic_id") or element.semantic_id is None:
        return None

    semantic_ref = element.semantic_id

    concept_description = _resolve_concept_description(semantic_ref, object_store)
    if concept_description is not None:
        label = _extract_preferred_name(concept_description, language_priority)
        if label:
            return label
        label = _extract_display_name(concept_description, language_priority)
        if label:
            return label

    return None


def resolve_semantic_description(
    element: "model.SubmodelElement",
    object_store: "model.DictObjectStore",
) -> dict[str, str] | None:
    """
    Resolve a multi-language description from ConceptDescriptions.

    Falls back to ConceptDescription.description or IEC61360 definition.
    """
    from basyx.aas import model

    if not hasattr(element, "semantic_id") or element.semantic_id is None:
        return None

    semantic_ref = element.semantic_id
    concept_description = _resolve_concept_description(semantic_ref, object_store)
    if concept_description is None:
        return None

    for eds in concept_description.embedded_data_specifications or []:
        content = eds.data_specification_content
        if isinstance(content, model.DataSpecificationIEC61360):
            definition = content.definition
            if definition:
                return dict(definition)

    if getattr(concept_description, "description", None):
        return dict(concept_description.description)

    return None


def _extract_preferred_name(
    concept_description: "model.ConceptDescription",
    language_priority: list[str],
) -> str | None:
    """
    Extract preferred name from ConceptDescription.

    Checks EmbeddedDataSpecifications for IEC61360 content and
    extracts the preferred name in the preferred language.
    """
    from basyx.aas import model

    if not hasattr(concept_description, "embedded_data_specifications"):
        return None

    for eds in concept_description.embedded_data_specifications or []:
        content = eds.data_specification_content
        if isinstance(content, model.DataSpecificationIEC61360):
            preferred_name = content.preferred_name
            if preferred_name:
                # Try to get label in preferred language order
                for lang in language_priority:
                    if lang in preferred_name:
                        return preferred_name[lang]

                # Fallback to any available language
                if preferred_name:
                    return next(iter(preferred_name.values()), None)

    return None


def _extract_display_name(
    concept_description: "model.ConceptDescription",
    language_priority: list[str],
) -> str | None:
    """
    Extract display name from ConceptDescription in preferred language.
    """
    display_name = getattr(concept_description, "display_name", None)
    if not display_name:
        return None

    for lang in language_priority:
        if lang in display_name:
            return display_name[lang]

    if display_name:
        return next(iter(display_name.values()), None)

    return None


def _resolve_concept_description(
    semantic_ref,
    object_store: "model.DictObjectStore",
) -> "model.ConceptDescription" | None:
    """
    Resolve a ConceptDescription from a semantic reference.
    """
    from basyx.aas import model

    if isinstance(semantic_ref, model.ModelReference):
        try:
            resolved_cd = semantic_ref.resolve(object_store)
            if isinstance(resolved_cd, model.ConceptDescription):
                return resolved_cd
        except (KeyError, model.UnexpectedTypeError) as e:
            logger.debug(f"Could not resolve semantic ID: {e}")

    if isinstance(semantic_ref, model.ExternalReference):
        for key in semantic_ref.key or ():
            cd = _find_concept_description_by_identifier(object_store, key.value)
            if cd:
                return cd

    return None


def _find_concept_description_by_identifier(
    object_store: "model.DictObjectStore",
    identifier: str,
) -> "model.ConceptDescription" | None:
    from basyx.aas import model

    for obj in object_store:
        if isinstance(obj, model.ConceptDescription):
            if getattr(obj, "id", None) == identifier:
                return obj
            if getattr(obj, "id_short", None) == identifier:
                return obj
    return None


def _extract_semantic_id_value(semantic_ref) -> str | None:
    """
    Extract the raw value from a semantic ID reference.

    Returns the key value (e.g., ECLASS IRDI) as a string.
    """
    if hasattr(semantic_ref, "key") and semantic_ref.key:
        return semantic_ref.key[0].value
    return str(semantic_ref) if semantic_ref else None


def get_description_text(
    element: "model.SubmodelElement",
    language_priority: list[str] | None = None,
) -> str | None:
    """
    Get description text from element in preferred language.

    Args:
        element: SubmodelElement with description
        language_priority: List of language codes in preference order

    Returns:
        Description text or None
    """
    if language_priority is None:
        language_priority = DEFAULT_LANGUAGE_PRIORITY

    if not hasattr(element, "description") or element.description is None:
        return None

    description = element.description

    # Try preferred languages
    for lang in language_priority:
        if lang in description:
            return description[lang]

    # Fallback to any available
    if description:
        return next(iter(description.values()), None)

    return None


def get_unit_from_concept_description(
    element: "model.SubmodelElement",
    object_store: "model.DictObjectStore",
) -> str | None:
    """
    Extract unit information from linked ConceptDescription.

    Args:
        element: SubmodelElement with semantic_id
        object_store: Object store containing ConceptDescriptions

    Returns:
        Unit string or None
    """
    from basyx.aas import model

    if not hasattr(element, "semantic_id") or element.semantic_id is None:
        return None

    semantic_ref = element.semantic_id

    if isinstance(semantic_ref, model.ModelReference):
        try:
            resolved_cd = semantic_ref.resolve(object_store)
            if isinstance(resolved_cd, model.ConceptDescription):
                for eds in resolved_cd.embedded_data_specifications or []:
                    content = eds.data_specification_content
                    if isinstance(content, model.DataSpecificationIEC61360):
                        return content.unit
        except (KeyError, model.UnexpectedTypeError):
            pass

    return None
