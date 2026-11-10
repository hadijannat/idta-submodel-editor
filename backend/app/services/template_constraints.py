"""
Constraints an IDTA submodel template declares for its elements.

A template carries its requirements in three machine-readable places:

* **Qualifiers** on the element. Besides ``SMT/Cardinality`` the IDTA
  conventions define ``SMT/AllowedValue``, ``SMT/AllowedRange``,
  ``SMT/ExampleValue``, ``SMT/DefaultValue``, ``SMT/InitialValue``,
  ``SMT/RequiredLang``, ``SMT/EitherOr``, ``SMT/AllowedIdShort`` and
  ``SMT/AccessMode``; templates authored with the AASX Package Explorer add
  ``FormTitle``, ``FormInfo``, ``FormUrl`` and ``FormChoices``; and many
  templates use ad-hoc types such as ``enumeration``, ``Note`` or ``unit``.
  Published templates spell these inconsistently (``Cardinality``,
  ``Multiplicity``, ``SMT/SMT/Cardinality``, ``SMT/AllowedValue1``), so types
  are matched by a normalised family name.
* The **IEC 61360 data specification** of the ConceptDescription the element
  refers to: value list (enumeration), value format, unit, definition.
* The element itself: value type, value (an example in templates), valueId.

``extract_constraints`` reads the first two and returns plain JSON-ready data
for the UI schema and for validation.
"""

from __future__ import annotations

import re
from typing import Any

CARDINALITY_VALUES = {
    "zerotoone": "[0..1]",
    "zerotomany": "[0..*]",
    "onetomany": "[1..*]",
    "one": "[1]",
    "zero": "[0]",
}

_NOTE_FAMILIES = {"note", "comment", "constraint", "naming", "select"}
_LABELLED_NOTE_FAMILIES = {
    "datatype": "Data type",
    "predicaterelation": "Predicate relation",
    "predicaterelationtemplate": "Predicate relation",
    "requiredatdql": "Required at data quality level",
    "lifecyclequal": "Life cycle",
    "loadstatus": "Load status",
}

_REGEX_META_RE = re.compile(r"[\\^$*+?\[\]{}()]|\.\*|\.\+")
# Parentheses also occur in plain enumeration entries ("kg (kilogram)"), so
# they do not count as evidence of a regular expression in a ";" list.
_REGEX_STRONG_META_RE = re.compile(r"[\\^$*+?\[\]{}]|\.\*|\.\+")


def qualifier_family(qualifier_type: str | None) -> str:
    """
    Normalise a qualifier type to its family name.

    ``SMT/Cardinality`` -> ``cardinality``; ``SMT/SMT/Cardinality`` ->
    ``cardinality``; ``SMT/AllowedValue2`` -> ``allowedvalue``;
    ``SMT/ExampleValue/ECLASS`` -> ``examplevalue``; ``life cycle qual`` ->
    ``lifecyclequal``.
    """
    if not qualifier_type:
        return ""
    segments = [seg for seg in str(qualifier_type).split("/") if seg.strip()]
    segments = [seg for seg in segments if seg.strip().lower() != "smt"] or segments
    family = re.sub(r"[^a-z0-9]", "", segments[0].lower())
    stripped = re.sub(r"\d+$", "", family)
    return stripped or family


def normalize_cardinality(value: Any) -> str | None:
    """Normalise cardinality spellings to bracket notation (``[0..1]``)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    key = re.sub(r"[^a-z]", "", text.lower())
    if key in CARDINALITY_VALUES:
        return CARDINALITY_VALUES[key]
    compact = re.sub(r"\s+", "", text)
    if compact.startswith("[") and compact.endswith("]"):
        return compact
    if ".." in compact or compact.isdigit():
        return f"[{compact}]"
    return text


def _split_choices(value: str, separators: str) -> list[str]:
    parts = re.split(f"[{re.escape(separators)}]", value)
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        item = part.strip().strip('"').strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _parse_number(token: str) -> float | int | None:
    text = token.strip()
    if not text:
        return None
    try:
        if re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+", text):
            return int(text, 16)
        number = float(text.replace(",", "."))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def parse_allowed_range(value: Any) -> dict[str, float | int | None] | None:
    """Parse ``[0,63]``, ``[0x00 , 0xff]``, ``0..100`` or ``>= 0``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    match = re.fullmatch(r"[\[(]?\s*([^,;\]\[()]*?)\s*(?:,|;|\.\.)\s*([^,;\]\[()]*?)\s*[\])]?", text)
    if match:
        low, high = _parse_number(match.group(1)), _parse_number(match.group(2))
        if low is not None or high is not None:
            return {"min": low, "max": high}

    match = re.fullmatch(r"(>=|<=|>|<)\s*(\S+)", text)
    if match:
        number = _parse_number(match.group(2))
        if number is not None:
            return (
                {"min": number, "max": None}
                if match.group(1).startswith(">")
                else {"min": None, "max": number}
            )
    return None


def parse_allowed_value(value: str) -> tuple[list[str], str | None]:
    """
    Interpret an ``SMT/AllowedValue`` qualifier.

    The convention defines the value as a regular expression, but published
    templates mostly write plain enumerations (``pass;fail``). Returns
    ``(choices, pattern)`` with exactly one of them set.
    """
    text = value.strip()
    if not text:
        return [], None
    if ";" in text and not _REGEX_STRONG_META_RE.search(text):
        return _split_choices(text, ";"), None
    if "|" in text and not _REGEX_META_RE.search(text):
        return _split_choices(text, "|"), None
    if _REGEX_META_RE.search(text):
        try:
            re.compile(text)
        except re.error:
            return [], None
        return [], text
    return [text], None


def describe_value_format(value_format: str | None) -> dict[str, Any] | None:
    """
    Interpret an IEC 61360 / ISO 13584 value format such as ``X..10`` or
    ``NR1..7``.

    Returns a dict with a human-readable ``description`` and, where the
    format bounds the value, ``maxLength``/``minLength`` (characters or
    digits).
    """
    if not value_format:
        return None
    text = value_format.strip()
    match = re.fullmatch(r"(?i)([XANM])\s*(\.\.)?\s*(\d+)", text)
    if match:
        kind = {
            "X": "characters",
            "A": "letters",
            "N": "digits",
            "M": "characters",
        }[match.group(1).upper()]
        length = int(match.group(3))
        if match.group(2):
            return {
                "format": text,
                "description": f"up to {length} {kind}",
                "maxLength": length,
                "minLength": None,
            }
        return {
            "format": text,
            "description": f"exactly {length} {kind}",
            "maxLength": length,
            "minLength": length,
        }

    match = re.fullmatch(r"(?i)NR1\s*(S)?\s*(\.\.)?\s*(\d+)", text)
    if match:
        digits = int(match.group(3))
        return {
            "format": text,
            "description": f"integer with up to {digits} digits",
            "maxLength": None,
            "minLength": None,
            "maxDigits": digits,
        }

    match = re.fullmatch(r"(?i)NR2\s*(S)?\s*(\.\.)?\s*(\d+)\.(\d+)", text)
    if match:
        return {
            "format": text,
            "description": (
                f"decimal number with up to {match.group(3)} integer and "
                f"{match.group(4)} fractional digits"
            ),
            "maxLength": None,
            "minLength": None,
        }

    if re.match(r"(?i)NR3", text):
        return {
            "format": text,
            "description": "number in exponent notation",
            "maxLength": None,
            "minLength": None,
        }
    return {"format": text, "description": None, "maxLength": None, "minLength": None}


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def extract_constraints(
    qualifiers: list[dict[str, Any]],
    *,
    value_list: list[dict[str, Any]] | None = None,
    value_format: str | None = None,
) -> dict[str, Any]:
    """
    Derive UI/validation constraints from serialized qualifiers and the
    IEC 61360 content of the element's ConceptDescription.

    Args:
        qualifiers: ``[{"type", "value", "valueType", "kind"}]``
        value_list: IEC 61360 value list as ``[{"value", "valueId"}]``
        value_format: IEC 61360 value format

    Returns:
        Dict with only the keys that apply (see ``ElementSchema``).
    """
    result: dict[str, Any] = {}
    examples: list[str] = []
    notes: list[str] = []
    choices: list[dict[str, Any]] = []
    choice_values: set[str] = set()
    strict = False
    required_languages: list[str] = []

    def add_choice(value: str, label: str | None = None, value_id: str | None = None) -> None:
        if value in choice_values:
            return
        choice_values.add(value)
        choices.append({"value": value, "label": label, "valueId": value_id})

    for qualifier in qualifiers or []:
        family = qualifier_family(qualifier.get("type"))
        raw = qualifier.get("value")
        value = "" if raw is None else str(raw).strip()

        if family in ("cardinality", "multiplicity"):
            continue

        if family in ("examplevalue", "example"):
            # Several examples are written as "ECLASS|IEC CDD|UNSPSC".
            candidates = _split_choices(value, "|") if " | " in value or (
                "|" in value and not _REGEX_META_RE.search(value)
            ) else [value]
            for candidate in candidates:
                if candidate and candidate not in examples:
                    examples.append(candidate)
        elif family == "defaultvalue":
            if value:
                result["defaultValue"] = value
        elif family == "initialvalue":
            if value:
                result["initialValue"] = value
        elif family == "allowedvalue":
            options, pattern = parse_allowed_value(value)
            for option in options:
                add_choice(option)
            if options:
                strict = True
            if pattern:
                result["pattern"] = pattern
        elif family == "formchoices":
            for option in _split_choices(value, ";"):
                add_choice(option)
        elif family == "enumeration":
            for option in _split_choices(value, ",;"):
                add_choice(option)
        elif family == "allowedrange":
            allowed_range = parse_allowed_range(value)
            if allowed_range:
                result["allowedRange"] = allowed_range
            elif value:
                notes.append(f"Allowed range: {value}")
        elif family == "allowedidshort":
            if value:
                result["allowedIdShort"] = value
        elif family == "editidshort":
            result["editIdShort"] = _truthy(value)
        elif family == "requiredlang":
            for lang in _split_choices(value, ",; "):
                if lang not in required_languages:
                    required_languages.append(lang)
        elif family == "eitheror":
            if value:
                result["eitherOr"] = value
        elif family == "accessmode":
            if value:
                result["accessMode"] = value
                if re.sub(r"[^a-z]", "", value.lower()) in ("readonly", "read"):
                    result["readOnly"] = True
        elif family == "formtitle":
            if value:
                result["formTitle"] = value
        elif family == "forminfo":
            if value:
                result["formInfo"] = value
        elif family == "formurl":
            if value:
                result["formUrl"] = value
        elif family == "unit":
            if value:
                result["qualifierUnit"] = value
        elif family in _NOTE_FAMILIES:
            if value and value not in notes:
                notes.append(value)
        elif family in _LABELLED_NOTE_FAMILIES:
            if value:
                note = f"{_LABELLED_NOTE_FAMILIES[family]}: {value}"
                if note not in notes:
                    notes.append(note)

    # A value list with a single entry is an example, not an enumeration.
    usable_pairs = [
        pair
        for pair in value_list or []
        if pair.get("value") is not None and str(pair.get("value")).strip() != ""
    ]
    if len(usable_pairs) >= 2:
        for pair in usable_pairs:
            add_choice(str(pair["value"]).strip(), value_id=pair.get("valueId"))
    elif len(usable_pairs) == 1 and not choices:
        single = str(usable_pairs[0]["value"]).strip()
        if single not in examples:
            examples.append(single)

    if choices:
        result["allowedValues"] = choices
        result["allowedValuesStrict"] = strict
    if examples:
        result["exampleValues"] = examples
    if notes:
        result["notes"] = notes
    if required_languages:
        result["requiredLanguages"] = required_languages

    format_info = describe_value_format(value_format)
    if format_info:
        result["valueFormat"] = format_info["format"]
        if format_info.get("description"):
            result["valueFormatDescription"] = format_info["description"]
        if format_info.get("maxLength") is not None:
            result["maxLength"] = format_info["maxLength"]
        if format_info.get("minLength") is not None:
            result["minLength"] = format_info["minLength"]

    return result
