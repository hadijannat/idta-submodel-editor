"""
XSD to HTML input type mapping.

Maps XML Schema datatypes to HTML5 input types for form rendering.
"""

# Mapping from XSD datatypes to HTML input types
XSD_TO_HTML_INPUT: dict[str, str] = {
    # String types
    "xs:string": "text",
    "xs:normalizedString": "text",
    "xs:token": "text",
    "xs:language": "text",
    "xs:Name": "text",
    "xs:NCName": "text",
    "xs:ID": "text",
    "xs:IDREF": "text",
    "xs:ENTITY": "text",
    "xs:NMTOKEN": "text",
    # Boolean
    "xs:boolean": "checkbox",
    # Numeric types (decimal-based)
    "xs:decimal": "number",
    "xs:float": "number",
    "xs:double": "number",
    # Integer types
    "xs:integer": "number",
    "xs:int": "number",
    "xs:long": "number",
    "xs:short": "number",
    "xs:byte": "number",
    "xs:nonPositiveInteger": "number",
    "xs:negativeInteger": "number",
    "xs:nonNegativeInteger": "number",
    "xs:positiveInteger": "number",
    "xs:unsignedInt": "number",
    "xs:unsignedLong": "number",
    "xs:unsignedShort": "number",
    "xs:unsignedByte": "number",
    # Date and time types
    "xs:date": "date",
    "xs:time": "time",
    "xs:dateTime": "datetime-local",
    "xs:gYear": "number",
    "xs:gYearMonth": "month",
    "xs:gMonth": "number",
    "xs:gMonthDay": "text",
    "xs:gDay": "number",
    "xs:duration": "text",
    "xs:yearMonthDuration": "text",
    "xs:dayTimeDuration": "text",
    # URI types
    "xs:anyURI": "url",
    # Binary types
    "xs:base64Binary": "file",
    "xs:hexBinary": "text",
    # QName
    "xs:QName": "text",
    "xs:NOTATION": "text",
}

# Mapping for step attributes in number inputs
XSD_STEP_MAPPING: dict[str, str] = {
    "xs:integer": "1",
    "xs:int": "1",
    "xs:long": "1",
    "xs:short": "1",
    "xs:byte": "1",
    "xs:nonPositiveInteger": "1",
    "xs:negativeInteger": "1",
    "xs:nonNegativeInteger": "1",
    "xs:positiveInteger": "1",
    "xs:unsignedInt": "1",
    "xs:unsignedLong": "1",
    "xs:unsignedShort": "1",
    "xs:unsignedByte": "1",
    "xs:decimal": "any",
    "xs:float": "any",
    "xs:double": "any",
}

# Mapping for min/max constraints
XSD_RANGE_CONSTRAINTS: dict[str, dict[str, int | None]] = {
    "xs:byte": {"min": -128, "max": 127},
    "xs:unsignedByte": {"min": 0, "max": 255},
    "xs:short": {"min": -32768, "max": 32767},
    "xs:unsignedShort": {"min": 0, "max": 65535},
    "xs:int": {"min": -2147483648, "max": 2147483647},
    "xs:unsignedInt": {"min": 0, "max": 4294967295},
    "xs:positiveInteger": {"min": 1, "max": None},
    "xs:nonNegativeInteger": {"min": 0, "max": None},
    "xs:negativeInteger": {"min": None, "max": -1},
    "xs:nonPositiveInteger": {"min": None, "max": 0},
}


def get_input_type(xsd_type: str | None) -> str:
    """
    Get HTML input type for an XSD datatype.

    Args:
        xsd_type: XSD datatype string (e.g., "xs:string")

    Returns:
        HTML input type (e.g., "text", "number", "date")
    """
    if xsd_type is None:
        return "text"

    # Normalize the type string
    type_str = str(xsd_type).strip()

    # Handle both "xs:" and "xsd:" prefixes
    if type_str.startswith("xsd:"):
        type_str = "xs:" + type_str[4:]

    return XSD_TO_HTML_INPUT.get(type_str, "text")


def get_step_attribute(xsd_type: str | None) -> str | None:
    """
    Get step attribute value for numeric inputs.

    Args:
        xsd_type: XSD datatype string

    Returns:
        Step value or None
    """
    if xsd_type is None:
        return None

    type_str = str(xsd_type).strip()
    if type_str.startswith("xsd:"):
        type_str = "xs:" + type_str[4:]

    return XSD_STEP_MAPPING.get(type_str)


def get_range_constraints(xsd_type: str | None) -> dict[str, int | None]:
    """
    Get min/max constraints for numeric types.

    Args:
        xsd_type: XSD datatype string

    Returns:
        Dict with 'min' and 'max' keys (values may be None)
    """
    if xsd_type is None:
        return {"min": None, "max": None}

    type_str = str(xsd_type).strip()
    if type_str.startswith("xsd:"):
        type_str = "xs:" + type_str[4:]

    return XSD_RANGE_CONSTRAINTS.get(type_str, {"min": None, "max": None})
