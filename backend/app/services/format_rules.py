"""
Format standards referenced by IDTA submodel templates.

Template specifications state many value requirements only in prose — in the
element description of the template JSON/AASX and in the notes of the
specification PDF: "Country codes defined accord. to DIN EN ISO 3166-1
alpha-2 codes", "Format is YYYY-MM-DD", "three-letter ISO currency code".
This module recognises those statements and turns them into a machine-usable
*format hint* (label, pattern, example) so that the form can guide the user
and validation can point out values that do not follow the named standard.

Hints derived from prose are advisory: a mismatch is reported as a warning,
never as a blocking error, because the wording of a specification is not a
formal constraint. Constraints the template declares formally (qualifiers,
value lists, XSD value types) are handled in ``template_constraints``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ISO 3166-1 alpha-2 codes (officially assigned).
ISO_3166_ALPHA2 = frozenset(
    """
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ
    BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR
    CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR
    GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU
    ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ
    LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ
    MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF
    PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI
    SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR
    TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
    """.split()
)

# ISO 4217 currency codes in circulation.
ISO_4217 = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB
    BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP
    DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF
    IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK
    LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN
    NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF
    SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND
    TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VES VND VUV WST XAF XCD XOF XPF YER
    ZAR ZMW ZWG
    """.split()
)


@dataclass(frozen=True)
class FormatHint:
    """A recognised value format."""

    id: str
    label: str
    description: str
    pattern: str | None = None
    example: str | None = None
    options: str | None = None  # named code list the UI can offer: country|currency|language
    transform: str | None = None  # "uppercase" | "lowercase"
    source: str = "description"  # description | name | valueType

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "pattern": self.pattern,
            "example": self.example,
            "options": self.options,
            "transform": self.transform,
            "source": self.source,
        }


_HINTS: dict[str, FormatHint] = {
    "iso3166-1-alpha2": FormatHint(
        id="iso3166-1-alpha2",
        label="ISO 3166-1 alpha-2",
        description="Two-letter country code according to ISO 3166-1 alpha-2, e.g. DE, US, CN.",
        pattern=r"^[A-Z]{2}$",
        example="DE",
        options="country",
        transform="uppercase",
    ),
    "iso3166-1-alpha3": FormatHint(
        id="iso3166-1-alpha3",
        label="ISO 3166-1 alpha-3",
        description="Three-letter country code according to ISO 3166-1 alpha-3, e.g. DEU, USA.",
        pattern=r"^[A-Z]{3}$",
        example="DEU",
        transform="uppercase",
    ),
    "iso639": FormatHint(
        id="iso639",
        label="ISO 639 language code",
        description="Language code according to ISO 639-1, optionally with region (BCP 47), e.g. en, de, en-US.",
        pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$",
        example="en",
        options="language",
    ),
    "iso4217": FormatHint(
        id="iso4217",
        label="ISO 4217 currency code",
        description="Three-letter currency code according to ISO 4217, e.g. EUR, USD.",
        pattern=r"^[A-Z]{3}$",
        example="EUR",
        options="currency",
        transform="uppercase",
    ),
    "iso8601-date": FormatHint(
        id="iso8601-date",
        label="ISO 8601 date",
        description="Calendar date in the form YYYY-MM-DD (ISO 8601).",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(Z|[+-]\d{2}:\d{2})?$",
        example="2025-01-31",
    ),
    "iso8601-datetime": FormatHint(
        id="iso8601-datetime",
        label="ISO 8601 date and time",
        description="Timestamp in the form YYYY-MM-DDThh:mm:ss with optional fraction and time zone (ISO 8601), e.g. 2025-01-31T14:30:00Z.",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])T([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$",
        example="2025-01-31T14:30:00Z",
    ),
    "iso8601-duration": FormatHint(
        id="iso8601-duration",
        label="ISO 8601 duration",
        description="Duration in the form P[n]Y[n]M[n]DT[n]H[n]M[n]S (ISO 8601), e.g. P1DT12H or PT30M.",
        pattern=r"^-?P(?=\d|T\d)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$",
        example="PT30M",
    ),
    "iso8601-timezone": FormatHint(
        id="iso8601-timezone",
        label="ISO 8601 time zone",
        description="Offset from UTC in ISO 8601 notation: Z for UTC, otherwise +hh:mm or -hh:mm.",
        pattern=r"^(Z|[+-](0\d|1[0-4]):[0-5]\d)$",
        example="+01:00",
    ),
    "year": FormatHint(
        id="year",
        label="Year (YYYY)",
        description="Four-digit calendar year, e.g. 2025.",
        pattern=r"^\d{4}$",
        example="2025",
        source="name",
    ),
    "email": FormatHint(
        id="email",
        label="E-mail address",
        description="E-mail address in the form name@domain (RFC 5322).",
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$",
        example="info@example.com",
        source="name",
    ),
    "phone": FormatHint(
        id="phone",
        label="Phone number",
        description="Telephone number, preferably in international notation with country code (ITU-T E.123), e.g. +49 241 123456.",
        pattern=r"^\+?[0-9][0-9 ()./\-]{4,}$",
        example="+49 241 123456",
        source="name",
    ),
    "uri": FormatHint(
        id="uri",
        label="URI",
        description="Uniform Resource Identifier with a scheme (RFC 3986), e.g. https://example.com/item/123 or urn:example:item:123.",
        pattern=r"^[A-Za-z][A-Za-z0-9+.\-]*:\S+$",
        example="https://example.com/item/123",
    ),
    "url": FormatHint(
        id="url",
        label="URL",
        description="Web address starting with http:// or https://.",
        pattern=r"^https?://\S+$",
        example="https://www.example.com",
    ),
    "iec61406": FormatHint(
        id="iec61406",
        label="IEC 61406 identification link",
        description="Globally unique identification link according to IEC 61406 (DIN SPEC 91406): an http(s) URL without spaces, e.g. https://www.example.com/product/123?sn=456.",
        pattern=r"^https?://\S+$",
        example="https://www.example.com/id/1234",
    ),
    "uuid": FormatHint(
        id="uuid",
        label="UUID",
        description="Universally unique identifier (RFC 4122 / ISO/IEC 9834-8), e.g. 123e4567-e89b-12d3-a456-426614174000.",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        example="123e4567-e89b-12d3-a456-426614174000",
        source="name",
    ),
    "gtin": FormatHint(
        id="gtin",
        label="GTIN (GS1)",
        description="Global Trade Item Number: 8, 12, 13 or 14 digits including the check digit.",
        pattern=r"^(\d{8}|\d{12,14})$",
        example="04012345000016",
        source="name",
    ),
    "mime": FormatHint(
        id="mime",
        label="Media type (MIME)",
        description="IANA media type in the form type/subtype (RFC 2046), e.g. application/pdf.",
        pattern=r"^[A-Za-z0-9][\w.+\-]*/[A-Za-z0-9][\w.+\-]*(\s*;.*)?$",
        example="application/pdf",
    ),
}

_STANDARD_RE = re.compile(
    r"\b(?:DIN\s+EN\s+ISO|DIN\s+EN\s+IEC|DIN\s+EN|DIN\s+SPEC|DIN\s+DKE\s+SPEC|EN\s+ISO|EN\s+IEC|"
    r"ISO/IEC|ISO/TS|ISO|IEC|RFC|VDI/VDE|VDI|VDE|DIN|EN|NAMUR\s+NE|ITU-T\s+E\.)"
    r"[\s]?[-/]?\s?\d{2,6}(?:[-:/.]\d+)*",
    re.IGNORECASE,
)

_IRDI_ENUM_RE = re.compile(
    r"(\d{4}-\d#\d{2}-[A-Z0-9]{6}#\d{3})\s*\(([^()]{1,80})\)"
)


def get_hint(hint_id: str) -> FormatHint | None:
    return _HINTS.get(hint_id)


def _text_blob(texts: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(t for t in texts if t)).strip()


def detect_format_hint(
    *,
    id_short: str | None,
    model_type: str | None,
    value_type: str | None,
    texts: list[str],
) -> FormatHint | None:
    """
    Recognise a format standard for a Property from its specification text.

    Args:
        id_short: idShort of the element
        model_type: AAS model type name
        value_type: XSD value type (``xs:string`` ...)
        texts: description, definition and notes of the element (any order)
    """
    if model_type != "Property":
        return None

    vt = (value_type or "xs:string").lower()
    is_string = vt in ("xs:string", "xs:normalizedstring", "xs:anyuri", "xs:token")
    if not is_string:
        # Typed values (dates, numbers, booleans) are validated by their XSD type.
        return None

    name = id_short or ""
    lowered_name = name.lower()
    text = _text_blob(texts)
    lowered = text.lower()

    # --- Standards named in the specification text -------------------------
    if re.search(r"iso\s?3166", lowered) or "country code" in lowered:
        if "alpha-3" in lowered or "alpha 3" in lowered:
            return _HINTS["iso3166-1-alpha3"]
        return _HINTS["iso3166-1-alpha2"]

    if re.search(r"iso\s?639", lowered) or "language code" in lowered:
        return _HINTS["iso639"]

    if re.search(r"iso\s?4217", lowered) or re.search(
        r"(three|3)[- ]letter (iso )?currency code|iso currency code", lowered
    ):
        return _HINTS["iso4217"]

    if re.search(r"61406|91406", lowered):
        return _HINTS["iec61406"]

    mentions_8601 = bool(re.search(r"iso\s?8601", lowered))
    if mentions_8601 or re.search(r"p\[n\]y\[n\]m", lowered):
        if "duration" in lowered_name or re.search(r"p\[n\]y|\bduration\b", lowered):
            return _HINTS["iso8601-duration"]
        if "timezone" in lowered_name or "time zone" in lowered or "zone designator" in lowered:
            return _HINTS["iso8601-timezone"]
        if re.search(r"timestamp|date and time|datetime|point in time", lowered) or re.search(
            r"time(stamp)?$", lowered_name
        ):
            return _HINTS["iso8601-datetime"]
        if "date" in lowered_name or "date" in lowered:
            return _HINTS["iso8601-date"]

    if re.search(r"\b(yyyy|ccyy)-mm-dd\b", lowered):
        if re.search(r"-dd[t ]hh", lowered):
            return _HINTS["iso8601-datetime"]
        return _HINTS["iso8601-date"]

    if re.search(r"rfc\s?2046|mime[- ]?type|media type", lowered) and re.search(
        r"content|mime|media", lowered_name
    ):
        return _HINTS["mime"]

    # --- Value type ---------------------------------------------------------
    if vt == "xs:anyuri":
        return _replace_source(_HINTS["uri"], "valueType")

    # --- Naming conventions -------------------------------------------------
    if not lowered_name.startswith(("typeof", "kindof", "roleof")):
        if re.search(r"e-?mail(address)?$", lowered_name):
            return _HINTS["email"]
        if re.search(r"(telephone|phone|fax|mobile)(number|no)?$", lowered_name):
            return _HINTS["phone"]
        if "uuid" in lowered_name:
            return _HINTS["uuid"]
        if re.search(r"gtin", lowered_name):
            return _HINTS["gtin"]
        if re.search(r"(mimetype|mediatype|contenttype)$", lowered_name):
            return _replace_source(_HINTS["mime"], "name")
        if re.search(r"^year(of|$)|yearofconstruction|yearofmanufacture", lowered_name):
            return _HINTS["year"]
        if re.search(r"(url|homepage|website|weblink|addressofadditionallink)$", lowered_name):
            return _replace_source(_HINTS["url"], "name")
        if lowered_name.startswith("uri") or lowered_name.endswith("uri"):
            if "universal resource identifier" in lowered or "uri" in lowered or not text:
                return _replace_source(_HINTS["uri"], "name")

    return None


def _replace_source(hint: FormatHint, source: str) -> FormatHint:
    if hint.source == source:
        return hint
    return FormatHint(**{**hint.__dict__, "source": source})


def find_referenced_standards(texts: list[str], limit: int = 6) -> list[str]:
    """List the standards (ISO, IEC, DIN, EN, RFC, VDI ...) a text refers to."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _STANDARD_RE.finditer(_text_blob(texts)):
        label = re.sub(r"\s+", " ", match.group(0)).strip(" .,:;-/")
        # "ISO8601" -> "ISO 8601"
        label = re.sub(r"^([A-Za-z/\- ]*[A-Za-z])(\d)", r"\1 \2", label)
        prefix, _, number = label.rpartition(" ")
        label = f"{prefix.upper()} {number}" if prefix else label.upper()
        # The same standard is cited with and without its adopting bodies
        # ("DIN EN ISO 3166-1" / "ISO 3166-1"); the number identifies it.
        key = number if prefix else label
        if key in seen or not re.search(r"\d{3,}", label):
            continue
        seen.add(key)
        found.append(label)
        if len(found) >= limit:
            break
    return found


def find_irdi_enumeration(texts: list[str]) -> list[dict[str, str]]:
    """
    Extract an enumeration written as ``IRDI (label), IRDI (label)`` in prose.

    IDTA specifications describe ECLASS/IEC CDD value lists this way, e.g.
    "enumeration: 0173-1#07-AAS927#001 (administrativ contact), ...".
    """
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _IRDI_ENUM_RE.finditer(_text_blob(texts)):
        irdi, label = match.group(1), match.group(2).strip()
        if irdi in seen or not label:
            continue
        seen.add(irdi)
        options.append({"value": irdi, "label": label, "valueId": irdi})
    return options if len(options) >= 2 else []


def check_format(hint_id: str, value: Any) -> str | None:
    """
    Check a value against a format hint.

    Returns None when the value conforms, otherwise a short explanation.
    """
    hint = _HINTS.get(hint_id)
    if hint is None or value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if hint.pattern and not re.match(hint.pattern, text):
        return f"does not look like a valid {hint.label} (expected e.g. {hint.example})"

    if hint_id == "iso3166-1-alpha2" and text not in ISO_3166_ALPHA2:
        return f"'{text}' is not an assigned ISO 3166-1 alpha-2 country code"
    if hint_id == "iso4217" and text not in ISO_4217:
        return f"'{text}' is not a current ISO 4217 currency code"
    if hint_id == "gtin" and not _gtin_check_digit_ok(text):
        return "GTIN check digit is not correct"
    if hint_id == "year" and not 1000 <= int(text) <= 2999:
        return "is not a plausible calendar year"
    return None


def _gtin_check_digit_ok(digits: str) -> bool:
    if not digits.isdigit():
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(
        int(char) * (3 if index % 2 == 0 else 1)
        for index, char in enumerate(reversed(body))
    )
    return (10 - total % 10) % 10 == check
