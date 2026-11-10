"""
Extract per-element requirements from IDTA Submodel Template specification PDFs.

IDTA specifications describe every Submodel and every nested collection/list in
a table that follows the "IDTA table convention" (explained in an annex of each
specification).  A table consists of

* a header block of ``label | value`` rows::

      idShort:      Markings__00__
      Class:        SubmodelElementCollection
      semanticId:   0112/2///61360_7#AAS009#001
      Parent:       Markings
      Explanation:  Note: CE marking is declared as mandatory ...

* a column header ``[SME type] idShort | semanticId Description@en |
  [valueType] example | card.``

* one row per SubmodelElement with four cells::

      [Prop]        | 0112/2///61987#ABO097#001              | [Date]     | 0..1
      IssueDate     | supplementalSemanticId: 0173-1#02-...  | 2022-01-01 |
                    | date, at which the certificate is issued
                    | Note: format by lexical representation: CCYY-MM-DD

Cells are narrow, so idShorts, semanticIds and examples are frequently
hard-wrapped in the middle of a word; tables continue over page breaks and the
same element is often described twice (overview table and detail table).

How the extraction works
------------------------
* ``pdfplumber`` supplies the words of a page (with coordinates) and the tables
  it can find from ruling lines.  Only the *row bands* (y ranges) of those
  tables are trusted.  Column boundaries are taken from the x positions of the
  column header words (``semanticId``, ``[valueType]``, ``card.``) because cell
  text is left aligned, whereas the ruling lines reported for Word-generated
  PDFs are sometimes misplaced.  Without a column header the cell edges of the
  ruled table are used.
* A row starts at a band whose first cell begins with an ``[SME type]`` tag (or
  that has a first cell and a cardinality); following bands without a tag are
  continuation lines of that row.  This copes with layouts in which every text
  line is reported as its own table row and with rows split by a page break.
* Lines are joined using their geometry: a line that is "full" (the next
  character would not have fitted) was hard-wrapped and is joined without a
  blank; a line that ends although the next word would have fitted ends a
  paragraph.  Paragraphs are then classified as semanticId, supplemental
  semanticId, ``Note:``/``Constraint`` sentence or description.
* Pages with element rows but without any ruled table fall back to a purely
  text-position based reading (rows start at the tag lines).  The same reading
  is used for a row that a page break cuts without closing rulings.
* Duplicate rows are merged by ``(parent, idShort)``; the header block of a
  table additionally yields an element for the described Submodel/collection.

Limits of the heuristics
------------------------
* Everything depends on the convention above.  Specifications that describe
  their elements in prose, UML diagrams or differently shaped tables yield
  nothing (an empty document plus, where detectable, a warning).
* Scanned PDFs (images without a text layer) and encrypted PDFs yield nothing.
* The column limit used for the wrap decisions is the right-most text position
  observed in that column.  In a column without a single full line a
  soft-wrapped two-word example could be joined without a blank, and
  deliberate line breaks may go unnoticed (the text is then joined by blanks).
* The parent of a row is the ``idShort:`` of the table header.  Tables without
  such a header yield rows with ``parent=None``; a table that continues on the
  next page is recognised by its position (first table, same width).
* Ruling-less tables are only read completely when their cells are top
  aligned; otherwise only idShort, SME type and cardinality are extracted.
* Word does not always fill a line before it breaks a long id, so a wrapped
  semanticId is recognised by its shape (single token, ``/``, ``#``, digits).
  A one-word description directly below an id that ends at the cell border
  can therefore be taken for the tail of the id, or the id is dropped as
  ambiguous.
* Fields that cannot be determined unambiguously (e.g. several alternative
  semanticIds, an unparsable cardinality) are left ``None`` rather than
  guessed.  The spec text itself is not validated against the template JSON:
  the extraction reports what the PDF says, including its inconsistencies.

The module is pure: no FastAPI imports, no network access.  Input PDFs are
untrusted; :func:`extract_spec_document` never raises for malformed input.
"""

from __future__ import annotations

import io
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "SpecDocument",
    "SpecElement",
    "extract_spec_document",
    "normalize_spec_key",
]


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

_COUNTER_RE = re.compile(r"\{\s*\d*\s*\}|__\d+__")
_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")


def normalize_spec_key(id_short: str) -> str:
    """Return the lookup key of an idShort.

    Lowercases, removes counters (``{00}``, ``__00__``) and strips every
    non-alphanumeric character, so that ``Markings__00__``, ``Markings{00}``
    and ``Markings`` share one key.
    """
    if not isinstance(id_short, str):
        return ""
    text = _COUNTER_RE.sub("", id_short.strip().lower())
    return _NON_ALNUM_RE.sub("", text)


@dataclass
class SpecElement:
    """One element row of an IDTA specification table."""

    id_short: str
    key: str
    sme_type: str | None = None
    semantic_id: str | None = None
    value_type: str | None = None
    cardinality: str | None = None
    description: str | None = None
    notes: list[str] = field(default_factory=list)
    example: str | None = None
    parent: str | None = None
    page: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id_short": self.id_short,
            "key": self.key,
            "sme_type": self.sme_type,
            "semantic_id": self.semantic_id,
            "value_type": self.value_type,
            "cardinality": self.cardinality,
            "description": self.description,
            "notes": list(self.notes),
            "example": self.example,
            "parent": self.parent,
            "page": self.page,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecElement:
        id_short = str(data.get("id_short") or "")
        notes = data.get("notes") or []
        page = data.get("page")
        return cls(
            id_short=id_short,
            key=str(data.get("key") or normalize_spec_key(id_short)),
            sme_type=_opt_str(data.get("sme_type")),
            semantic_id=_opt_str(data.get("semantic_id")),
            value_type=_opt_str(data.get("value_type")),
            cardinality=_opt_str(data.get("cardinality")),
            description=_opt_str(data.get("description")),
            notes=[str(n) for n in notes] if isinstance(notes, list) else [],
            example=_opt_str(data.get("example")),
            parent=_opt_str(data.get("parent")),
            page=page if isinstance(page, int) and not isinstance(page, bool) else 0,
        )


@dataclass
class SpecDocument:
    """All element requirements extracted from one specification PDF."""

    elements: list[SpecElement]
    page_count: int
    title: str | None = None
    warnings: list[str] = field(default_factory=list)

    def lookup(self, id_short: str, parent: str | None = None) -> SpecElement | None:
        """Find an element by normalized idShort.

        When several elements share the key, the one whose parent matches
        ``parent`` (normalized) wins; otherwise the first occurrence is
        returned.
        """
        key = normalize_spec_key(id_short)
        if not key:
            return None
        matches = [el for el in self.elements if el.key == key]
        if not matches:
            return None
        if parent is not None:
            parent_key = normalize_spec_key(parent)
            for el in matches:
                if el.parent is not None and normalize_spec_key(el.parent) == parent_key:
                    return el
        # no (matching) parent: prefer an element row over a bare table header
        return next((el for el in matches if el.cardinality is not None), matches[0])

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "page_count": self.page_count,
            "warnings": list(self.warnings),
            "elements": [el.to_dict() for el in self.elements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpecDocument:
        raw_elements = data.get("elements") or []
        raw_warnings = data.get("warnings") or []
        page_count = data.get("page_count")
        return cls(
            elements=[
                SpecElement.from_dict(item)
                for item in (raw_elements if isinstance(raw_elements, list) else [])
                if isinstance(item, dict) and item.get("id_short")
            ],
            page_count=page_count
            if isinstance(page_count, int) and not isinstance(page_count, bool)
            else 0,
            title=_opt_str(data.get("title")),
            warnings=[str(w) for w in raw_warnings] if isinstance(raw_warnings, list) else [],
        )


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

_SME_TYPES: dict[str, str] = {
    "prop": "Property",
    "property": "Property",
    "mlp": "MultiLanguageProperty",
    "multilanguageproperty": "MultiLanguageProperty",
    "smc": "SubmodelElementCollection",
    "submodelelementcollection": "SubmodelElementCollection",
    "sml": "SubmodelElementList",
    "submodelelementlist": "SubmodelElementList",
    "file": "File",
    "blob": "Blob",
    "range": "Range",
    "ref": "ReferenceElement",
    "reference": "ReferenceElement",
    "referenceelement": "ReferenceElement",
    "ent": "Entity",
    "entity": "Entity",
    "rel": "RelationshipElement",
    "relationship": "RelationshipElement",
    "relationshipelement": "RelationshipElement",
    "arel": "AnnotatedRelationshipElement",
    "annotatedrelationshipelement": "AnnotatedRelationshipElement",
    "cap": "Capability",
    "capability": "Capability",
    "opr": "Operation",
    "op": "Operation",
    "operation": "Operation",
    "evt": "BasicEventElement",
    "event": "BasicEventElement",
    "basicevent": "BasicEventElement",
    "basiceventelement": "BasicEventElement",
    "sme": "SubmodelElement",
    "submodelelement": "SubmodelElement",
    "de": "DataElement",
    "dataelement": "DataElement",
    "sm": "Submodel",
    "submodel": "Submodel",
}

# Bracketed tokens that look like an SME tag but are not one.
_NOT_A_TAG = {
    "iri",
    "irdi",
    "custom",
    "id",
    "uri",
    "url",
    "idtype",
    "idtypevalue",
    "valuetype",
    "qualifier",
    "globalreference",
    "modelreference",
    "smetype",
    "variablekind",
}

_HEADER_VOCAB = {
    "[sme",
    "type]",
    "[variable",
    "kind",
    "/",
    "variable",
    "value",
    "idshort",
    "semanticid",
    "=",
    "[idtype]value",
    "[idtype]",
    "description@en",
    "description",
    "@en",
    "[valuetype]",
    "example",
    "card.",
    "card",
}

_LABELS = {
    "idshort": "idShort",
    "class": "class",
    "semanticid": "semanticId",
    "parent": "parent",
    "explanation": "explanation",
    "element": "details",
    "elementdetails": "details",
    "details": "details",
    "iscaseof": "isCaseOf",
    "allowduplicates": "other",
    "allowduplicate": "other",
    "kind": "other",
    "version": "other",
    "revision": "other",
    "ordered": "other",
}
# Left-most words that mark a header-block band at the very start of a table.
_LABEL_STARTS = {
    "idShort:",
    "Class:",
    "semanticId:",
    "Parent:",
    "Explanation:",
    "Element",
    "details:",
    "isCaseOf",
    "isCaseOf:",
    "AllowDuplicates",
    "AllowDuplicate",
    "Kind:",
}

_TAG_RE = re.compile(r"^\[\s*([A-Za-z][A-Za-z0-9 _/\-]*)\]\s*(.*)$", re.S)
_ID_PREFIX_RE = re.compile(
    r"^(?:\[+\s*(?:IRI|IRDI|Custom|ID|URI|GlobalReference|ModelReference)\s*\]+\s*)+", re.I
)
_ID_PREFIX_ANY_RE = re.compile(
    r"\[+\s*(?:IRI|IRDI|Custom|ID|URI|GlobalReference|ModelReference)\s*\]+", re.I
)
_IRDI_RE = re.compile(r"^\d{4}[-/]\S*#\S+$")
_ID_START_RE = re.compile(r"^(?:\d{4}[-/]\S*|[A-Za-z][A-Za-z0-9+.\-]{1,15}://\S*|urn:\S+)$")
_OR_RE = re.compile(r"^(?:or|oder)\b\s*", re.I)
_XSD_TYPES = {
    "string", "langstring", "boolean", "decimal", "integer", "int", "long", "short", "byte",
    "double", "float", "date", "datetime", "time", "duration", "anyuri", "base64binary",
    "hexbinary", "gyear", "gyearmonth", "gmonth", "gmonthday", "gday", "nonnegativeinteger",
    "positiveinteger", "negativeinteger", "nonpositiveinteger", "unsignedint", "unsignedlong",
    "unsignedshort", "unsignedbyte",
}
_URL_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]{1,15}://\S+|urn:\S+)$")
_ID_SHORT_RE = re.compile(r"^[A-Za-z{][A-Za-z0-9_{}\-]*$")
_CARD_RE = re.compile(r"^\[?\s*(\d+|\*|n)\s*(?:\.\.\s*(\d+|\*|n|∞))?\s*\]?$", re.I)
_NOTE_START_RE = re.compile(r"^note(?:\s+\d+)?\s*(?::|[–—-](?=\s))\s*", re.I)
_CONSTRAINT_START_RE = re.compile(r"^constraint\b[^:]{0,60}:", re.I)
_INLINE_NOTE_RE = re.compile(r"(?:(?<=[.;:!?)\]\"”])|^)\s*(?=Note(?:\s+\d+)?\s*:\s)")
_SUPPLEMENTAL_RE = re.compile(r"^(supplemental\s*semantic\s*ids?|iscaseof)\s*:?\s*", re.I)
# Line starts that always begin a new paragraph, whatever the geometry says.
_FORCED_BREAK_RE = re.compile(
    r"^(note(\s+\d+)?\s*(:|[–—-]\s)|constraint\b|supplemental\s*semantic\s*ids?\b|iscaseof\b"
    r"|\[+\s*(iri|irdi|custom)\s*\]|(preferredname|shortname|definition)\s*@|@[a-z]{2}\s*:"
    r"|enumeration\s*:|(ordered|allowduplicates)\s*=)",
    re.I,
)
_NO_EXAMPLE_RE = re.compile(
    r"^(n\s*/\s*a|n\.a\.?|-+|–|—|\.{2,}|\w+\s+elements?|\[\s*\])$", re.I
)
_GENERIC_TITLES = {"details of the administration shell - part 1", "untitled", ""}
_DATE_LINE_RE = re.compile(
    r"^(\d{1,2}\.?\s+)?(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+\d{4}$",
    re.I,
)


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

_X_TOLERANCE = 1.5


@dataclass
class _Word:
    text: str
    base: str  # text without a trailing superscript (footnote) marker
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    first_width: float  # width of the first character
    char_boxes: tuple[tuple[float, float], ...] = ()  # (x0, x1) per character of ``text``

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class _Line:
    words: list[_Word]
    top: float
    bottom: float

    @property
    def x0(self) -> float:
        return self.words[0].x0

    @property
    def x1(self) -> float:
        return self.words[-1].x1

    def text(self, base: bool = False) -> str:
        if base:
            return " ".join(w.base for w in self.words if w.base)
        return " ".join(w.text for w in self.words)


@dataclass
class _Columns:
    """Left boundaries of the (up to four) columns of an element table."""

    bounds: list[float]  # words with x0 >= bounds[k] belong to column >= k
    text_starts: list[float]  # x of left-aligned text per column
    right: float
    ref_x0: float  # x0 of the table the columns were measured on

    def key(self) -> tuple[int, ...]:
        return tuple(round(b) for b in self.bounds)

    def shifted(self, dx: float, ref_x0: float, right: float) -> _Columns:
        if abs(dx) < 0.01 and abs(right - self.right) < 0.01:
            return self
        return _Columns(
            bounds=[b + dx for b in self.bounds],
            text_starts=[s + dx for s in self.text_starts],
            right=right,
            ref_x0=ref_x0,
        )

    def column_of(self, x0: float) -> int:
        idx = 0
        for k in range(1, len(self.bounds)):
            if x0 >= self.bounds[k]:
                idx = k
        return idx


@dataclass
class _RawRow:
    page: int
    parent: str | None
    columns: _Columns
    cells: list[list[_Line]]  # four lists of lines
    full: bool = True  # False: only the first cell and the cardinality are reliable
    card_text: str | None = None  # used by the minimal ruling-less fallback
    seq: int = 0  # document order


@dataclass
class _Header:
    page: int
    seq: int = 0
    value_x: float | None = None
    label: str | None = None
    fields: dict[str, list[_Line]] = field(default_factory=dict)


def _convert_words(raw_words: list[dict[str, Any]]) -> list[_Word]:
    words: list[_Word] = []
    for raw in raw_words:
        text = str(raw.get("text") or "")
        if not text.strip():
            continue
        try:
            x0 = float(raw["x0"])
            x1 = float(raw["x1"])
            top = float(raw["top"])
            bottom = float(raw["bottom"])
        except (KeyError, TypeError, ValueError):
            continue
        chars = raw.get("chars") or []
        base = text
        size = bottom - top
        first_width = (x1 - x0) / max(len(text), 1)
        boxes: tuple[tuple[float, float], ...] = ()
        if chars and len(chars) == len(text):
            try:
                sizes = [float(c.get("size") or 0.0) for c in chars]
                boxes = tuple((float(c["x0"]), float(c["x1"])) for c in chars)
                main = max(sizes)
                if main > 0:
                    size = main
                first_width = boxes[0][1] - boxes[0][0]
                cut = len(text)
                while cut > 0 and text[cut - 1].isdigit() and sizes[cut - 1] < 0.8 * main:
                    cut -= 1
                if 0 < cut < len(text):
                    base = text[:cut]
            except (KeyError, TypeError, ValueError):
                base = text
                boxes = ()
        words.append(
            _Word(
                text=text,
                base=base,
                x0=x0,
                x1=x1,
                top=top,
                bottom=bottom,
                size=size,
                first_width=max(first_width, 0.1),
                char_boxes=boxes,
            )
        )
    return words


def _split_at(word: _Word, bound: float) -> list[_Word]:
    """Split a word that straddles a column boundary (cells without a gap)."""
    boxes = word.char_boxes
    if not boxes or not (word.x0 < bound - 1.0 and word.x1 > bound + 3.0):
        return [word]
    # Two cells glued into one word show a small gap at the boundary; a word that
    # merely overflows its cell has none and must stay in one piece.
    cut = None
    widest = 0.5
    for i in range(1, len(boxes)):
        gap = boxes[i][0] - boxes[i - 1][1]
        if gap > widest and abs(boxes[i][0] - bound) <= 6.0:
            widest = gap
            cut = i
    if cut is None:
        return [word]
    base_cut = min(cut, len(word.base))
    left = _Word(
        text=word.text[:cut],
        base=word.base[:base_cut],
        x0=word.x0,
        x1=boxes[cut - 1][1],
        top=word.top,
        bottom=word.bottom,
        size=word.size,
        first_width=word.first_width,
        char_boxes=boxes[:cut],
    )
    right = _Word(
        text=word.text[cut:],
        base=word.base[base_cut:] if len(word.base) > base_cut else word.text[cut:],
        x0=boxes[cut][0],
        x1=word.x1,
        top=word.top,
        bottom=word.bottom,
        size=word.size,
        first_width=max(boxes[cut][1] - boxes[cut][0], 0.1),
        char_boxes=boxes[cut:],
    )
    return [left, right]


def _page_words(page: Any) -> list[_Word]:
    # x_tolerance below pdfplumber's default (3): the text of two neighbouring cells can
    # be less than 3pt apart, while the characters of one word touch each other.
    try:
        raw = page.extract_words(
            x_tolerance=_X_TOLERANCE, keep_blank_chars=False, use_text_flow=False, return_chars=True
        )
    except TypeError:  # pdfplumber without return_chars
        raw = page.extract_words(
            x_tolerance=_X_TOLERANCE, keep_blank_chars=False, use_text_flow=False
        )
    return _convert_words(raw)


def _group_lines(words: list[_Word]) -> list[_Line]:
    lines: list[_Line] = []
    for word in sorted(words, key=lambda w: (w.mid, w.x0)):
        for line in reversed(lines[-4:]):
            if line.top - 0.5 <= word.mid <= line.bottom + 0.5:
                line.words.append(word)
                break
        else:
            lines.append(_Line(words=[word], top=word.top, bottom=word.bottom))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    lines.sort(key=lambda ln: (ln.top, ln.x0))
    return lines


def _drop_footnote_marks(words: list[_Word]) -> list[_Word]:
    """Remove superscript digits (footnote markers such as ``[MLP]¹``)."""
    if len(words) < 2:
        return words
    sizes = sorted(w.size for w in words)
    median = sizes[len(sizes) // 2]
    kept = [w for w in words if not (w.text.isdigit() and w.size < 0.8 * median)]
    return kept or words


def _tag_key(line: _Line) -> str | None:
    """Normalized content of an ``[SME type]`` tag starting the line, else None.

    Wrapped tags (``[SubmodelElem`` / ``entCollection]``) return the visible
    part.  Bracketed non-tags such as ``[IRI]`` or ``[SME type]`` return None.
    """
    first = line.words[0].base
    if len(first) < 2 or first[0] != "[" or not first[1].isalpha():
        return None
    collected = ""
    for word in line.words[:5]:
        collected += word.base
        if "]" in word.base:
            break
    content = collected[1:].split("]", 1)[0]
    key = re.sub(r"[^a-z/]", "", content.lower())
    if not key:
        return None
    if key in _NOT_A_TAG or key.startswith(("smetype", "variablekind")):
        return None
    return key


def _is_header_vocab(words: list[_Word]) -> bool:
    return bool(words) and all(w.text.lower() in _HEADER_VOCAB for w in words)


def _normalize_cardinality(text: str | None) -> str | None:
    if not text:
        return None
    candidate = re.sub(r"\s+", "", text)
    match = _CARD_RE.match(candidate)
    if not match:
        return None
    low, high = match.group(1).lower(), match.group(2)
    if high is None:
        if low.isdigit():
            return f"[{int(low)}]"
        if low == "*":
            return "[0..*]"
        return None
    high = high.lower()
    if not low.isdigit():
        return None
    if high in {"*", "n", "∞"}:
        return f"[{int(low)}..*]"
    if int(high) < int(low):
        return None
    if int(high) == int(low):
        return f"[{int(low)}]"
    return f"[{int(low)}..{int(high)}]"


def _normalize_sme_type(raw: str | None) -> str | None:
    if not raw:
        return None
    text = re.sub(r"\(.*?\)", "", raw)
    part = text.split("/")[-1]
    key = re.sub(r"[^a-z]", "", part.lower())
    return _SME_TYPES.get(key)


def _parse_id_short(text: str) -> str | None:
    """idShort from the (already de-wrapped) text following the SME tag."""
    rest = re.sub(r"^\d+\s*", "", text.strip())  # footnote marker after the tag
    counter = re.fullmatch(r"([A-Za-z][A-Za-z0-9_\-]*?)\s+(\d{1,3})", rest)
    if counter:
        # "IPCommunication 00": a counter whose braces did not survive in the PDF text
        rest = f"{counter.group(1)}{{{counter.group(2)}}}"
    id_short = re.sub(r"\s+", "", rest)
    if not _ID_SHORT_RE.match(id_short) or not normalize_spec_key(id_short):
        return None
    return id_short


def _looks_like_id(token: str) -> bool:
    return bool(_IRDI_RE.match(token) or _URL_RE.match(token))


def _clean(text: str) -> str:
    # literal "\n" sequences occur in generated specifications
    return re.sub(r"\s+", " ", text.replace("\\n", " ")).strip()


# ---------------------------------------------------------------------------
# Wrap-aware text assembly
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Geometry:
    """Horizontal extent of the text of one table column."""

    start: float | None  # x of the left-aligned text
    limit: float | None  # right-most text position seen in the column (a lower bound)
    fit_limit: float | None  # estimate of the right text limit for "would have fitted"


_NO_GEOMETRY = _Geometry(start=None, limit=None, fit_limit=None)
# Cell paddings are small; text is assumed to reach at least this close to the next column.
_MAX_COLUMN_GAP = 13.0


def _slack_margin(line: _Line) -> float:
    """Tolerance for wrap decisions.

    Word processors do not always fill a line to the last possible character
    (a hard-wrapped URL was observed to end ~13pt early), so "would have
    fitted" is only accepted with some room to spare.
    """
    return 1.4 * max(line.words[-1].size, 1.0)


def _is_full(line: _Line, nxt: _Line, limit: float | None) -> bool:
    """True when the next character would not have fitted on ``line``."""
    if limit is None:
        return False
    return line.x1 + nxt.words[0].first_width > limit + 0.3


def _nearly_full(line: _Line, nxt: _Line, limit: float | None) -> bool:
    """Like :func:`_is_full` but tolerant: used for ids, which contain no blanks."""
    if limit is None:
        return False
    return line.x1 + nxt.words[0].first_width + 2.2 * max(line.words[-1].size, 1.0) > limit


def _would_fit(line: _Line, nxt: _Line, geo: _Geometry) -> bool:
    """True when the first word of ``nxt`` would clearly have fitted on ``line``.

    A positive answer means a deliberate line break.  Unknown geometry
    (no limit, indented or centred lines) answers False.
    """
    limit, start = geo.fit_limit, geo.start
    if limit is None or start is None:
        return False
    if abs(line.x0 - start) > 3.0 or abs(nxt.x0 - start) > 3.0:
        return False
    word = nxt.words[0]
    space = 0.3 * max(line.words[-1].size, 1.0)
    return line.x1 + space + (word.x1 - word.x0) + _slack_margin(line) <= limit


def _joiner(so_far: str, line: _Line, nxt: _Line, limit: float | None) -> str:
    """Separator between two lines of one paragraph ('' for hard wraps)."""
    last = line.words[-1].text
    if last.endswith("-") and len(last) > 1:
        return ""  # wrapped after a hyphen: "0173-1#07-" / "AAS930#001"
    tail = so_far.split()[-1] if so_far.split() else ""
    if tail.endswith("/") and "://" in tail:
        return ""  # URL wrapped after a slash
    if len(line.words) == 1 and _is_full(line, nxt, limit):
        return ""  # a single token longer than the cell, broken mid-word
    head = nxt.words[0].text
    if (
        "://" in tail
        and _nearly_full(line, nxt, limit)
        and re.fullmatch(r"[\w\-./#?=&%~+:]+", head)
        and (len(nxt.words) == 1 or re.search(r"[./#?=&_\d-]", head))
    ):
        return ""  # URL broken mid-word: "…/query/aggr" / "egators.html"
    return " "


def _paragraphs(lines: list[_Line], geo: _Geometry) -> list[list[_Line]]:
    paragraphs: list[list[_Line]] = []
    for line in lines:
        if not paragraphs:
            paragraphs.append([line])
            continue
        prev = paragraphs[-1][-1]
        last = prev.words[-1].text
        hyphen_wrap = last.endswith("-") and len(last) > 1  # nobody ends a paragraph like this
        if _FORCED_BREAK_RE.match(line.text()) or (
            not hyphen_wrap and _would_fit(prev, line, geo)
        ):
            paragraphs.append([line])
        else:
            paragraphs[-1].append(line)
    return paragraphs


def _join_paragraph(lines: list[_Line], limit: float | None, *, base: bool = False) -> str:
    out = ""
    for idx, line in enumerate(lines):
        if idx:
            out += _joiner(out, lines[idx - 1], line, limit)
        out += line.text(base=base)
    return _clean(out)


_PREFIX_TOKEN = "\x00"


def _id_tokens(line: _Line) -> list[str]:
    """Tokens of a line with ``[IRI]``/``[IRDI]`` markers replaced by a sentinel."""
    return _ID_PREFIX_ANY_RE.sub(f" {_PREFIX_TOKEN} ", line.text()).split()


def _take_semantic_id(
    lines: list[_Line], geo: _Geometry
) -> tuple[str | None, str, list[_Line]]:
    """Read the semanticId at the top of a description cell.

    Returns ``(semantic_id, prose_on_the_id_lines, remaining_lines)``.  The id
    may be wrapped over several lines.  Alternatives ("<id> or <id>",
    "<id> or other suitable semantic id") are ambiguous and yield ``None``.
    """
    if not lines:
        return None, "", lines
    first = _id_tokens(lines[0])
    probe = [t for t in first if t != _PREFIX_TOKEN]
    if first[:1] != [_PREFIX_TOKEN] and not (probe and _ID_START_RE.match(probe[0].rstrip(",;"))):
        return None, "", lines

    ids: list[str] = []
    leftover: list[str] = []
    current: str | None = None  # id under construction (may continue on the next line)
    alternatives = False
    ambiguous = False
    expecting = True  # an id may start at this position
    index = 0
    while index < len(lines):
        line = lines[index]
        tokens = _id_tokens(line)
        position = 0
        if current is not None:
            previous = lines[index - 1]
            fragment = tokens[0]
            single = len(tokens) == 1
            continues = False
            blocked = (
                fragment == _PREFIX_TOKEN
                or _OR_RE.fullmatch(fragment) is not None
                or _FORCED_BREAK_RE.match(line.text()) is not None
                or (not current.endswith("-") and _would_fit(previous, line, geo))
            )
            if blocked:
                pass
            elif current.endswith("-"):
                continues = True  # an id never ends with a hyphen
            elif not single and current.endswith("/") and re.search(r"[/#]", fragment):
                continues = True  # "…/a/" + "1/0/First or": wrapped after a slash
            elif single:
                if (
                    current.endswith("/")
                    or _is_full(previous, line, geo.limit)
                    or re.search(r"[/#:\d]", fragment)
                ):
                    continues = True
                elif _nearly_full(previous, line, geo.limit):
                    if fragment[:1].isupper():
                        # id tail or a one-word description?  Undecidable: drop both.
                        ambiguous = True
                        index += 1
                    else:
                        continues = True
            if continues:
                current += fragment
                position = 1
                if single:
                    index += 1
                    continue
            ids.append(current)
            current = None
            expecting = False
            if ambiguous:
                break

        rest = tokens[position:]
        used = position > 0
        stop = False
        while rest:
            head = rest[0]
            if _OR_RE.fullmatch(head) and ids:
                after = [t for t in rest[1:] if t != _PREFIX_TOKEN]
                if after and not _ID_START_RE.match(after[0].rstrip(",;")):
                    # "<id> or other suitable semantic id ...": keep the wording
                    alternatives = True
                    leftover.append(" ".join(t for t in rest if t != _PREFIX_TOKEN))
                    used = True
                    stop = True
                    break
                alternatives = True
                expecting = True
                used = True
                rest = rest[1:]
                continue
            if head == _PREFIX_TOKEN:
                expecting = True
                used = True
                rest = rest[1:]
                continue
            if expecting and _ID_START_RE.match(head.rstrip(",;")):
                if ids:
                    alternatives = True
                used = True
                expecting = False
                if len(rest) == 1:
                    current = head
                    rest = []
                else:
                    ids.append(head)
                    rest = rest[1:]
                continue
            # prose
            if used:
                leftover.append(" ".join(t for t in rest if t != _PREFIX_TOKEN))
            stop = True
            break
        if used:
            index += 1
        if stop or not used:
            break
    if current is not None:
        ids.append(current)

    semantic_id: str | None = None
    if len(ids) == 1 and not alternatives and not ambiguous:
        candidate = ids[0].rstrip(",;")
        if _looks_like_id(candidate):
            semantic_id = candidate
    return semantic_id, _clean(" ".join(leftover)), lines[index:]


def _add_notes(target: list[str], notes: list[str]) -> None:
    """Append notes that are not yet present (ignoring whitespace and case)."""
    seen = {re.sub(r"\s+", "", note).lower() for note in target}
    for note in notes:
        fingerprint = re.sub(r"\s+", "", note).lower()
        if fingerprint and fingerprint not in seen:
            seen.add(fingerprint)
            target.append(note)


def _split_notes(text: str) -> tuple[str, list[str]]:
    """Split ``text`` into leading prose and the ``Note:`` sentences in it."""
    parts = [p for p in _INLINE_NOTE_RE.split(text) if p and p.strip()]
    prose: list[str] = []
    notes: list[str] = []
    for part in parts:
        part = part.strip()
        if _NOTE_START_RE.match(part):
            note = _NOTE_START_RE.sub("", part, count=1).strip()
            if note:
                notes.append(note)
        elif notes:
            # text after a note inside one paragraph belongs to that note
            notes[-1] = f"{notes[-1]} {part}"
        else:
            prose.append(part)
    return " ".join(prose), notes


# ---------------------------------------------------------------------------
# Extraction state machine
# ---------------------------------------------------------------------------


class _Extractor:
    def __init__(self) -> None:
        self.rows: list[_RawRow] = []
        self.header_elements: list[tuple[int, SpecElement]] = []
        self.seq = 0
        self.warnings: list[str] = []
        self.limits: dict[tuple[int, ...], list[float]] = {}
        self.cur: _RawRow | None = None
        self.header: _Header | None = None
        self.parent: str | None = None
        self.cols: _Columns | None = None
        self.cols_from_header = False
        self.open_sig: tuple[float, float] | None = None
        self.ruleless_open = False
        self.tail_open = False
        self.tail_bottom: float | None = None

    # -- helpers -----------------------------------------------------------

    def warn(self, message: str) -> None:
        if message not in self.warnings and len(self.warnings) < 50:
            self.warnings.append(message)

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def flush_row(self) -> None:
        if self.cur is not None:
            self.rows.append(self.cur)
            self.cur = None

    def reset_context(self) -> None:
        self.flush_row()
        self.finish_header()
        self.parent = None
        self.cols = None
        self.cols_from_header = False

    def observe(self, cols: _Columns, cells: list[list[_Word]]) -> None:
        limits = self.limits.setdefault(cols.key(), [0.0, 0.0, 0.0, 0.0])
        for idx, words in enumerate(cells):
            cap = cols.bounds[idx + 1] if idx + 1 < len(cols.bounds) else cols.right + 1.0
            for word in words:
                if word.x1 <= cap and word.x1 > limits[idx]:
                    limits[idx] = word.x1

    # -- header block ------------------------------------------------------

    def header_band(self, page_no: int, lines: list[_Line], left: float) -> None:
        if self.header is None:
            self.header = _Header(page=page_no, seq=self.next_seq())
        header = self.header
        if header.value_x is None:
            for line in lines:
                if (
                    len(line.words) >= 2
                    and line.words[0].x0 <= left + 3.0
                    and line.words[0].text.endswith(":")
                ):
                    header.value_x = line.words[1].x0
                    break
            if header.value_x is None:
                for line in lines:
                    if len(line.words) >= 2 and line.words[0].x0 <= left + 3.0:
                        header.value_x = line.words[1].x0
                        break
        value_x = header.value_x
        label_parts: list[str] = []
        value_lines: list[_Line] = []
        for line in lines:
            if value_x is None:
                label_words = [w for w in line.words if w.x0 <= left + 3.0]
                value_words = [w for w in line.words if w.x0 > left + 3.0]
            else:
                label_words = [w for w in line.words if w.x0 < value_x - 1.0]
                value_words = [w for w in line.words if w.x0 >= value_x - 1.0]
            label_parts.extend(w.text for w in label_words)
            if value_words:
                value_lines.append(_Line(words=value_words, top=line.top, bottom=line.bottom))
        label_key = re.sub(r"[^a-z]", "", "".join(label_parts).lower())
        if label_key in _LABELS:
            canonical = _LABELS[label_key]
            # "Element" + "details:" on two bands: stay on the same field
            if not (canonical == "details" and header.label == "details"):
                header.label = canonical
        elif label_key and label_key != "s":
            header.label = "other"
        if header.label and value_lines:
            header.fields.setdefault(header.label, []).extend(value_lines)

    def finish_header(self) -> None:
        header = self.header
        self.header = None
        if header is None:
            return
        id_lines = header.fields.get("idShort") or []
        id_short: str | None = None
        if id_lines:
            first = _clean(id_lines[0].text()).strip("“”\"',.; ")
            id_short = _parse_id_short(first)
            if id_short is None and first:
                id_short = _parse_id_short(first.split(" ")[0].strip("“”\"',.;"))
        self.parent = id_short
        if id_short is None:
            return
        sme_type = _normalize_sme_type(
            _clean(" ".join(line.text() for line in header.fields.get("class") or []))
        )
        semantic_id: str | None = None
        sem_lines = header.fields.get("semanticId") or []
        if sem_lines:
            # the semanticId may wrap; a following "Note:" line ends it
            id_part: list[_Line] = []
            for line in sem_lines:
                if id_part and _FORCED_BREAK_RE.match(line.text()):
                    break
                id_part.append(line)
            raw = _ID_PREFIX_RE.sub("", "".join(line.text().strip() for line in id_part))
            if _looks_like_id(raw):
                semantic_id = raw
        description: str | None = None
        notes: list[str] = []
        exp_lines = header.fields.get("explanation") or []
        if exp_lines:
            prose, notes = _split_notes(_join_paragraph(exp_lines, None))
            description = prose or None
        parent = self._parse_parent_field(header.fields.get("parent") or [], id_short)
        self.header_elements.append(
            (
                header.seq,
                SpecElement(
                    id_short=id_short,
                    key=normalize_spec_key(id_short),
                    sme_type=sme_type,
                    semantic_id=semantic_id,
                    description=description,
                    notes=notes,
                    parent=parent,
                    page=header.page,
                ),
            )
        )

    @staticmethod
    def _parse_parent_field(lines: list[_Line], own_id_short: str) -> str | None:
        text = _clean(" ".join(line.text() for line in lines))
        if not text:
            return None
        text = re.sub(r"\(.*?\)", " ", text)
        text = re.sub(r"[“”\"'‘’]", " ", text)
        tokens = [t.strip(".,;:") for t in text.split()]
        class_words = {"submodel", "sm", "smc", "sml", "submodelelementcollection",
                       "submodelelementlist", "collection", "list", "the", "of"}
        candidates = [t for t in tokens if t and t.lower() not in class_words]
        if len(candidates) != 1:
            return None
        candidate = candidates[0]
        if not _ID_SHORT_RE.match(candidate) or len(candidate) < 2:
            return None
        if candidate == own_id_short:
            return None  # some specifications repeat the idShort in "Parent:"
        return candidate

    # -- column detection --------------------------------------------------

    @staticmethod
    def columns_from_header_line(
        lines: list[_Line], left: float, table_x0: float, table_x1: float
    ) -> _Columns | None:
        for line in lines:
            value_type = [w for w in line.words if w.text.lower() == "[valuetype]"]
            if not value_type:
                continue
            c2 = value_type[0].x0
            sem = [
                w
                for w in line.words
                if w.text.lower() in {"semanticid", "description@en"} and w.x0 < c2
            ]
            if not sem:
                continue
            c1 = sem[0].x0
            if not left < c1 < c2:
                continue
            starts = [left, c1, c2]
            card = [w for w in line.words if w.text.lower() in {"card.", "card"} and w.x0 > c2]
            if card:
                starts.append(card[0].x0)
            bounds = [starts[0] - 2.0] + [s - 2.0 for s in starts[1:]]
            return _Columns(bounds=bounds, text_starts=starts, right=table_x1, ref_x0=table_x0)
        return None

    @staticmethod
    def columns_from_rules(table: Any) -> _Columns | None:
        best: list[float] | None = None
        counts: dict[tuple[int, ...], int] = {}
        edges_by_key: dict[tuple[int, ...], list[float]] = {}
        for row in getattr(table, "rows", []):
            cells = [c for c in row.cells if c is not None]
            if len(cells) < 3 or len(cells) != len(row.cells):
                continue
            edges = [float(c[0]) for c in cells]
            key = tuple(round(e) for e in edges)
            counts[key] = counts.get(key, 0) + 1
            edges_by_key[key] = edges
        if counts:
            key = max(counts, key=lambda k: (len(k), counts[k]))
            best = edges_by_key[key][:4]
        if not best:
            return None
        x0, _, x1, _ = table.bbox
        return _Columns(
            bounds=[b - 0.5 for b in best],
            text_starts=list(best),
            right=float(x1),
            ref_x0=float(x0),
        )

    # -- element rows ------------------------------------------------------

    def row_band(self, page_no: int, words: list[_Word], *, allow_untagged: bool = True) -> None:
        cols = self.cols
        if cols is None or not words:
            return
        for bound in cols.bounds[1:]:
            if any(w.x0 < bound - 1.0 and w.x1 > bound + 3.0 for w in words):
                words = [piece for w in words for piece in _split_at(w, bound)]
        cells: list[list[_Word]] = [[], [], [], []]
        for word in words:
            cells[cols.column_of(word.x0)].append(word)
        for idx in (0, 2, 3):
            cells[idx] = _drop_footnote_marks(cells[idx])
        first_lines = _group_lines(cells[0])
        tag_indexes: list[int] = []
        unclosed = False
        for idx, line in enumerate(first_lines):
            text = line.text(base=True)
            if not unclosed and _tag_key(line) is not None:
                tag_indexes.append(idx)
                unclosed = "]" not in text
            elif unclosed and "]" in text:
                unclosed = False
        if len(tag_indexes) > 1:
            # several rows inside one band (no horizontal rulings): split at the tag lines
            cuts = [first_lines[i].top - 1.0 for i in tag_indexes[1:]]
            groups: list[list[_Word]] = [[] for _ in range(len(cuts) + 1)]
            for word in words:
                pos = sum(1 for cut in cuts if word.mid >= cut)
                groups[pos].append(word)
            for group in groups:
                self.row_band(page_no, group, allow_untagged=False)
            return

        self.observe(cols, cells)
        lines = [first_lines] + [_group_lines(cells[i]) for i in (1, 2, 3)]
        starts_row = bool(tag_indexes)
        if not starts_row and allow_untagged and first_lines:
            card_text = _clean(" ".join(line.text(base=True) for line in lines[3]))
            starts_row = _normalize_cardinality(card_text) is not None
        if starts_row:
            self.flush_row()
            self.cur = _RawRow(
                page=page_no, parent=self.parent, columns=cols, cells=lines, seq=self.next_seq()
            )
        elif self.cur is not None:
            for idx in range(4):
                self.cur.cells[idx].extend(lines[idx])

    # -- ruled tables ------------------------------------------------------

    def process_table(
        self, page_no: int, table: Any, words: list[_Word], *, may_continue: bool
    ) -> bool:
        x0, top, x1, bottom = (float(v) for v in table.bbox)
        table_words = [
            w for w in words if top - 1.0 <= w.mid <= bottom + 1.0 and x0 - 2.0 <= w.x0 <= x1 + 2.0
        ]
        if not table_words:
            return False
        left = min(w.x0 for w in table_words)
        all_lines = _group_lines(table_words)
        has_label = any(
            line.words[0].x0 <= left + 3.0 and line.words[0].text == "idShort:" for line in all_lines
        )
        has_colheader = (
            self.columns_from_header_line(all_lines, left, x0, x1) is not None
        )
        has_tag = any(
            line.words[0].x0 <= left + 3.0 and _tag_key(line) in _SME_TYPES for line in all_lines
        )
        first_left = next(
            (ln.words[0].text for ln in all_lines if ln.words[0].x0 <= left + 3.0), ""
        )
        grid = max(
            (sum(1 for c in r.cells if c is not None) for r in table.rows), default=0
        )
        continuation = bool(
            may_continue
            and self.open_sig is not None
            and abs((x1 - x0) - (self.open_sig[1] - self.open_sig[0])) <= 6.0
            and (grid >= 3 or first_left in _LABEL_STARTS or has_tag)
        )
        if not continuation and not (has_label or has_colheader or has_tag):
            return False

        if continuation:
            if self.cols is not None:
                self.cols = self.cols.shifted(x0 - self.cols.ref_x0, x0, x1)
            if self.header is not None and self.header.value_x is not None and self.open_sig:
                self.header.value_x += x0 - self.open_sig[0]
        else:
            self.reset_context()

        mode: str | None = "header" if (continuation and self.header is not None) else None
        # row tops as cut points: rows reported with differing heights must not overlap
        tops = sorted({round(float(r.bbox[1]), 1) for r in table.rows})
        if not tops:
            tops = [top]
        tops[0] = min(tops[0], top - 1.0)
        bands = list(zip(tops, tops[1:] + [bottom + 1.0], strict=True))
        for band_top, band_bottom in bands:
            band_words = [w for w in table_words if band_top <= w.mid < band_bottom]
            if not band_words:
                continue
            band_lines = _group_lines(band_words)
            left_lines = [ln for ln in band_lines if ln.words[0].x0 <= left + 3.0]
            first_text = left_lines[0].words[0].text if left_lines else ""

            if first_text == "idShort:" and mode != "header_started_here":
                # a new header block (also when two tables were glued together)
                if not (mode == "header" and self.header is not None and not self.header.fields):
                    self.reset_context()
                mode = "header"
            elif mode is None:
                mode = "header" if first_text in _LABEL_STARTS else "rows"

            band_cols = self.columns_from_header_line(band_lines, left, x0, x1)
            if band_cols is not None:
                self.flush_row()
                self.finish_header()
                self.cols = band_cols
                self.cols_from_header = True
                mode = "rows"
                continue
            if mode == "header":
                if _is_header_vocab(band_words):
                    continue
                self.header_band(page_no, band_lines, left)
                continue
            if _is_header_vocab(band_words):
                continue
            if self.cols is None:
                self.cols = self.columns_from_rules(table)
                self.cols_from_header = False
                if self.cols is None:
                    self.warn(
                        f"page {page_no}: element table without recognisable columns skipped"
                    )
                    return True
            self.row_band(page_no, band_words)
        return True

    # -- ruling-less fallback ----------------------------------------------

    def process_ruleless(self, page_no: int, words: list[_Word], page_height: float) -> bool:
        lines = _group_lines(words)
        tag_lines = [ln for ln in lines if _tag_key(ln) in _SME_TYPES and len(ln.words) >= 2]
        if not tag_lines:
            return False
        buckets: dict[int, int] = {}
        for line in tag_lines:
            buckets[round(line.x0)] = buckets.get(round(line.x0), 0) + 1
        left = float(max(buckets, key=lambda k: buckets[k]))
        tag_lines = [ln for ln in tag_lines if abs(ln.x0 - left) <= 2.0]
        if not tag_lines:
            return False
        first_top = tag_lines[0].top

        # region: from the first tag line down to the first large vertical gap
        body = [ln for ln in lines if ln.top >= first_top - 0.5]
        heights = sorted(ln.bottom - ln.top for ln in body)
        line_height = heights[len(heights) // 2] if heights else 10.0
        region_bottom = body[0].bottom if body else first_top
        for line in body:
            if line.top - region_bottom > 2.5 * line_height:
                break
            region_bottom = max(region_bottom, line.bottom)
        region_bottom = min(region_bottom, page_height)

        header_lines = [ln for ln in lines if ln.bottom <= first_top + 0.5]
        right = max(w.x1 for w in words)
        cols = self.columns_from_header_line(header_lines, left, left, right)
        continuing = self.ruleless_open and first_top < 0.3 * page_height
        parent: str | None = None
        label = [
            ln
            for ln in header_lines
            if ln.words[0].text == "idShort:" and len(ln.words) >= 2
        ]
        if label:
            token = label[-1].words[1].text.strip("“”\"',.;")
            parent = token if _ID_SHORT_RE.match(token) else None
            self.flush_row()
        elif continuing:
            parent = self.parent
            if cols is None and self.cols is not None and abs(self.cols.text_starts[0] - left) <= 3:
                cols = self.cols
        else:
            self.flush_row()
        self.finish_header()
        self.parent = parent

        region_words = [w for w in words if first_top - 0.5 <= w.mid <= region_bottom + 0.5]
        top_aligned = True
        if cols is not None and header_lines:
            header_bottom = max(
                (ln.bottom for ln in header_lines if _is_header_vocab(ln.words)), default=None
            )
            if header_bottom is not None:
                # body text above the first tag line means vertically centred cells
                stray = [
                    w
                    for w in words
                    if header_bottom + 1.0 < w.top and w.bottom < first_top - 1.0
                    and w.x0 >= cols.bounds[1]
                ]
                if stray:
                    top_aligned = False
        if cols is not None and top_aligned:
            self.cols = cols
            self.cols_from_header = True
            cuts = [ln.top - 1.0 for ln in tag_lines[1:]]
            groups: list[list[_Word]] = [[] for _ in range(len(cuts) + 1)]
            for word in region_words:
                groups[sum(1 for cut in cuts if word.mid >= cut)].append(word)
            for group in groups:
                self.row_band(page_no, group, allow_untagged=False)
            self.ruleless_open = region_bottom > 0.8 * page_height
            if not self.ruleless_open:
                self.flush_row()
            return True

        # minimal mode: only the first cell and the cardinality are reliable
        self.flush_row()
        self.warn(
            f"page {page_no}: table without rulings read partially "
            "(idShort, type and cardinality only)"
        )
        second = [ln.words[1].x0 for ln in tag_lines if ln.words[1].x0 - ln.words[0].x1 > 6.0]
        col1 = min(second) if second else None
        for idx, line in enumerate(tag_lines):
            lower = tag_lines[idx + 1].top - 1.0 if idx + 1 < len(tag_lines) else region_bottom
            cell_words = [
                w
                for w in region_words
                if line.top - 0.5 <= w.mid < lower and (col1 is None or w.x0 < col1 - 1.0)
                and (col1 is not None or abs(w.x0 - left) <= 2.0 or w in line.words[:1])
            ]
            if col1 is None:
                # keep only left-aligned words (first word of each line)
                cell_words = [w for w in cell_words if abs(w.x0 - left) <= 2.0]
            card = line.words[-1].base if len(line.words) >= 3 else None
            dummy = _Columns(bounds=[left - 2.0], text_starts=[left], right=right, ref_x0=left)
            self.rows.append(
                _RawRow(
                    page=page_no,
                    parent=parent,
                    columns=dummy,
                    cells=[_group_lines(_drop_footnote_marks(cell_words)), [], [], []],
                    full=False,
                    card_text=card,
                    seq=self.next_seq(),
                )
            )
        self.ruleless_open = False
        return True

    # -- page driver -------------------------------------------------------

    # -- rows cut by a page break without closing rulings -------------------

    @staticmethod
    def _contiguous(lines: list[_Line], max_bottom: float) -> float:
        """Bottom of the block of lines that starts at ``lines[0]`` (no large gaps)."""
        heights = sorted(ln.bottom - ln.top for ln in lines)
        line_height = heights[len(heights) // 2] if heights else 10.0
        bottom = lines[0].bottom
        for line in lines:
            if line.top - bottom > 2.5 * line_height or line.bottom > max_bottom:
                break
            bottom = max(bottom, line.bottom)
        return bottom

    def process_tail(
        self, page_no: int, words: list[_Word], table_bottom: float, page_height: float
    ) -> None:
        """Rows directly below a ruled table whose cells are open at the page end."""
        cols = self.cols
        if cols is None or not words:
            return
        lines = _group_lines(words)
        tag_lines = [
            ln
            for ln in lines
            if _tag_key(ln) in _SME_TYPES and abs(ln.x0 - cols.text_starts[0]) <= 1.5
        ]
        if not tag_lines:
            return
        first_top = tag_lines[0].top
        body = [ln for ln in lines if ln.top >= first_top - 0.5]
        line_height = tag_lines[0].bottom - tag_lines[0].top
        if first_top - table_bottom > 3.0 * max(line_height, 1.0):
            return
        bottom = self._contiguous(body, page_height)
        region = [w for w in words if first_top - 0.5 <= w.mid <= bottom + 0.5]
        cuts = [ln.top - 1.0 for ln in tag_lines[1:] if ln.top <= bottom]
        groups: list[list[_Word]] = [[] for _ in range(len(cuts) + 1)]
        for word in region:
            groups[sum(1 for cut in cuts if word.mid >= cut)].append(word)
        for group in groups:
            self.row_band(page_no, group, allow_untagged=False)
        self.tail_open = bottom > 0.75 * page_height

    def continue_tail(
        self, page_no: int, words: list[_Word], max_bottom: float, page_height: float
    ) -> bool:
        """Text at the top of a page that continues a row cut by the page break.

        Returns True when the row is still open at the bottom of this page.
        """
        cols = self.cols
        self.tail_open = False
        if cols is None or self.cur is None or not words:
            return False
        lines = [ln for ln in _group_lines(words) if ln.bottom <= max_bottom]
        # cell text is left aligned: the block starts at a line that begins exactly
        # at a column (running page headers start at the page margin instead)
        start = next(
            (
                i
                for i, ln in enumerate(lines)
                if any(abs(ln.x0 - s) <= 1.0 for s in cols.text_starts)
            ),
            None,
        )
        if start is None or _tag_key(lines[start]) is not None:
            return False
        block = lines[start:]
        bottom = self._contiguous(block, max_bottom)
        region = [
            w
            for w in words
            if block[0].top - 0.5 <= w.mid <= bottom + 0.5
            and cols.bounds[0] - 1.0 <= w.x0 <= cols.right + 2.0
        ]
        self.row_band(page_no, region, allow_untagged=False)
        self.tail_bottom = bottom
        return max_bottom >= page_height and bottom > 0.75 * page_height

    # -- page driver -------------------------------------------------------

    def process_page(self, page_no: int, page: Any) -> None:
        words = _page_words(page)
        trigger = any(
            w.text in ("idShort:", "[valueType]")
            or (len(w.text) > 2 and w.text[0] == "[" and w.text[1].isalpha())
            for w in words
        )
        if (
            not trigger
            and self.open_sig is None
            and not self.ruleless_open
            and not self.tail_open
        ):
            self.flush_row()
            return
        tables: list[Any] = []
        try:
            tables = sorted(page.find_tables(), key=lambda t: (t.bbox[1], t.bbox[0]))
        except Exception as exc:  # noqa: BLE001 - untrusted input, never raise
            self.warn(f"page {page_no}: table detection failed ({type(exc).__name__})")
        page_height = float(getattr(page, "height", 0.0) or 0.0)
        boxes = [tuple(float(v) for v in t.bbox) for t in tables]
        outside = [
            w
            for w in words
            if not any(b[0] - 2 <= w.x0 <= b[2] + 2 and b[1] - 1 <= w.mid <= b[3] + 1 for b in boxes)
        ]

        self.tail_bottom = None
        if self.tail_open:
            first_top = min((b[1] for b in boxes), default=page_height)
            if self.continue_tail(page_no, outside, first_top, page_height):
                self.tail_open = True  # the row runs on to the next page
                return

        handled_last = False
        handled_any = False
        last_box: tuple[float, ...] | None = None
        for index, table in enumerate(tables):
            table_top = float(table.bbox[1])
            may_continue = (
                not handled_any
                and self.open_sig is not None
                and (
                    table_top < 0.35 * page_height
                    or (self.tail_bottom is not None and table_top - self.tail_bottom < 30.0)
                )
            )
            try:
                handled = self.process_table(page_no, table, words, may_continue=may_continue)
            except Exception as exc:  # noqa: BLE001
                self.warn(f"page {page_no}: table skipped ({type(exc).__name__})")
                handled = False
            if handled:
                handled_any = True
                last_box = boxes[index]
            if index == len(tables) - 1:
                handled_last = handled
        if handled_any and handled_last and last_box is not None:
            self.open_sig = (last_box[0], last_box[2])
            below = [
                w
                for w in outside
                if w.mid > last_box[3] and last_box[0] - 2 <= w.x0 <= last_box[2] + 2
            ]
            if below:
                self.process_tail(page_no, below, last_box[3], page_height)
        else:
            self.open_sig = None
            if handled_any:
                self.flush_row()
                self.finish_header()

        # element rows on a page without any ruled element table
        was_open = self.ruleless_open
        used_fallback = False
        if outside and not handled_any:
            try:
                used_fallback = self.process_ruleless(page_no, outside, page_height)
            except Exception as exc:  # noqa: BLE001
                self.warn(f"page {page_no}: text fallback failed ({type(exc).__name__})")
        if not used_fallback:
            if was_open:
                self.ruleless_open = False
            if not handled_any:
                self.flush_row()

    # -- element construction ----------------------------------------------

    def build_element(self, row: _RawRow) -> SpecElement | None:
        cols = row.columns
        limits = self.limits.get(cols.key(), [0.0, 0.0, 0.0, 0.0])

        def geometry(idx: int) -> _Geometry:
            if idx >= len(cols.text_starts):
                return _NO_GEOMETRY
            observed = limits[idx] if limits[idx] > 0 else None
            following = cols.text_starts[idx + 1] if idx + 1 < len(cols.text_starts) else cols.right
            estimate = max(observed or 0.0, following - _MAX_COLUMN_GAP)
            return _Geometry(start=cols.text_starts[idx], limit=observed, fit_limit=estimate)

        first = "".join(line.text(base=True) for line in row.cells[0])
        first = first.strip()
        sme_type: str | None = None
        match = _TAG_RE.match(first)
        if match:
            sme_type = _normalize_sme_type(match.group(1))
            rest = match.group(2)
        else:
            rest = first
        id_short = _parse_id_short(rest)
        if id_short is None:
            if first:
                self.warn(f"page {row.page}: row with unreadable idShort skipped ({first[:40]!r})")
            return None
        key = normalize_spec_key(id_short)

        if not row.full:
            return SpecElement(
                id_short=id_short,
                key=key,
                sme_type=sme_type,
                cardinality=_normalize_cardinality(row.card_text),
                parent=row.parent,
                page=row.page,
            )

        cardinality = _normalize_cardinality(
            _clean(" ".join(line.text(base=True) for line in row.cells[3]))
        )
        value_type, example = self._parse_value_cell(row.cells[2], geometry(2))
        semantic_id, description, notes = self._parse_description_cell(
            row.cells[1], geometry(1)
        )
        return SpecElement(
            id_short=id_short,
            key=key,
            sme_type=sme_type,
            semantic_id=semantic_id,
            value_type=value_type,
            cardinality=cardinality,
            description=description,
            notes=notes,
            example=example,
            parent=row.parent,
            page=row.page,
        )

    @staticmethod
    def _parse_value_cell(lines: list[_Line], geo: _Geometry) -> tuple[str | None, str | None]:
        if not lines:
            return None, None
        value_type: str | None = None
        rest_lines = list(lines)
        head = lines[0].text(base=True)
        inline_rest = ""
        if head.startswith("["):
            consumed = 1
            while "]" not in head and consumed < min(len(lines), 3):
                head += lines[consumed].text(base=True)
                consumed += 1
            if "]" in head:
                inside, inline_rest = head[1:].split("]", 1)
                inside = _clean(inside)
                value_type = inside or None
                rest_lines = lines[consumed:]
                inline_rest = re.sub(r"^\s*\d\s*$", "", inline_rest).strip()
        elif (
            len(lines[0].words) == 1
            and head.lower().removeprefix("xs:") in _XSD_TYPES
            and len(lines) > 1
        ):
            # value type written without brackets on its own line ("Date" / "2020-11-19")
            value_type = head
            rest_lines = lines[1:]
        parts: list[str] = []
        if inline_rest:
            parts.append(_clean(inline_rest))
        for paragraph in _paragraphs(rest_lines, geo):
            text = _join_paragraph(paragraph, geo.limit)
            if text:
                parts.append(text)
        example = "; ".join(parts) if parts else None
        if example is not None:
            # several language variants in one cell: "Data@en Daten@de"
            example = re.sub(r"(@[a-z]{2}(?:-[A-Za-z]{2})?) (?=\S)", r"\1; ", example)
        if example is not None and _NO_EXAMPLE_RE.match(example):
            example = None
        return value_type, example

    @staticmethod
    def _parse_description_cell(
        lines: list[_Line], geo: _Geometry
    ) -> tuple[str | None, str | None, list[str]]:
        description_parts: list[str] = []
        notes: list[str] = []

        def add_prose(text: str) -> None:
            prose, inline = _split_notes(text)
            if prose:
                description_parts.append(prose)
            notes.extend(inline)

        semantic_id, same_line, rest = _take_semantic_id(lines, geo)
        if same_line:
            add_prose(same_line)
        for paragraph in _paragraphs(rest, geo):
            text = _join_paragraph(paragraph, geo.limit)
            if not text:
                continue
            supplemental = _SUPPLEMENTAL_RE.match(text)
            if supplemental:
                # drop the ids; keep prose that was not separable by geometry
                tokens = text[supplemental.end():].split()
                while tokens and (
                    _ID_START_RE.match(tokens[0].rstrip(",;"))
                    or tokens[0] in {",", ";", "and", "or"}
                    or _ID_PREFIX_RE.sub("", tokens[0]) == ""
                    or not re.search(r"[A-Za-z]{2,}", tokens[0])
                    or re.search(r"[#/]", tokens[0])
                    or re.fullmatch(r"(?=.*\d)[A-Z0-9~_.:,;-]+", tokens[0])  # id fragment
                ):
                    tokens.pop(0)
                remainder = " ".join(tokens)
                if re.search(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}", remainder):
                    add_prose(remainder)
                continue
            if _NOTE_START_RE.match(text):
                notes.extend(_split_notes(text)[1])
                continue
            if _CONSTRAINT_START_RE.match(text):
                notes.append(text)
                continue
            add_prose(text)

        description = _clean(" ".join(description_parts)) or None
        return semantic_id, description, [_clean(n) for n in notes if _clean(n)]

    def build(self) -> list[SpecElement]:
        self.flush_row()
        self.finish_header()
        ordered: list[tuple[int, SpecElement]] = []
        index: dict[tuple[str, str], SpecElement] = {}
        for row in self.rows:
            try:
                element = self.build_element(row)
            except Exception as exc:  # noqa: BLE001
                self.warn(f"page {row.page}: row skipped ({type(exc).__name__})")
                continue
            if element is None:
                continue
            ident = (normalize_spec_key(element.parent or ""), element.key)
            existing = index.get(ident)
            if existing is None:
                index[ident] = element
                ordered.append((row.seq, element))
            else:
                self._merge(existing, element)

        # header blocks describe the Submodel / collection itself
        for seq, header_element in self.header_elements:
            ident = (normalize_spec_key(header_element.parent or ""), header_element.key)
            target = index.get(ident) if header_element.parent is not None else None
            if target is None and header_element.parent is None:
                same = [
                    el
                    for _, el in ordered
                    if el.key == header_element.key and el.id_short == header_element.id_short
                ]
                if len(same) == 1:
                    target = same[0]
                elif len(same) > 1:
                    continue  # ambiguous: several rows carry this idShort
            if target is not None:
                self._fill_missing(target, header_element)
            elif ident in index:
                self._fill_missing(index[ident], header_element)
            else:
                index[ident] = header_element
                ordered.append((seq, header_element))
        ordered.sort(key=lambda item: item[0])
        return [element for _, element in ordered]

    def _merge(self, target: SpecElement, other: SpecElement) -> None:
        """Merge a duplicate row into ``target`` keeping the richest data."""
        if (
            target.cardinality
            and other.cardinality
            and target.cardinality != other.cardinality
        ):
            self.warn(
                f"{target.id_short}: conflicting cardinalities "
                f"{target.cardinality} (page {target.page}) and {other.cardinality} "
                f"(page {other.page}); kept the first"
            )
        for name in ("sme_type", "semantic_id", "value_type", "cardinality", "example"):
            if getattr(target, name) is None and getattr(other, name) is not None:
                setattr(target, name, getattr(other, name))
        if other.description and (
            target.description is None or len(other.description) > len(target.description)
        ):
            target.description = other.description
        _add_notes(target.notes, other.notes)
        if len(other.id_short) > len(target.id_short):
            # keep the spelling that carries the counter, e.g. "Markings__00__"
            target.id_short = other.id_short

    @staticmethod
    def _fill_missing(target: SpecElement, header: SpecElement) -> None:
        for name in ("sme_type", "semantic_id", "description"):
            if getattr(target, name) is None and getattr(header, name) is not None:
                setattr(target, name, getattr(header, name))
        _add_notes(target.notes, header.notes)


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


def _extract_title(metadata: Any, first_page_text: str | None) -> str | None:
    if isinstance(metadata, dict):
        raw = metadata.get("Title")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        if isinstance(raw, str):
            candidate = _clean(raw)
            if candidate.lower() not in _GENERIC_TITLES:
                return candidate[:300]
    if not first_page_text:
        return None
    # cover page: "IDTA 02006-3-0" / "Digital Nameplate for" / "Industrial Equipment" /
    # "November 2024" / "S P E C I F I C A T I O N"
    lines = [_clean(line) for line in first_page_text.splitlines()]
    collected: list[str] = []
    started = False
    terminated = False
    for line in lines:
        if not line:
            continue
        if re.match(r"^S\s*P\s*E\s*C", line) or line.lower().startswith("submodel template of"):
            terminated = started
            break
        if not started:
            if "IDTA" not in line:
                continue
            started = True
        if _DATE_LINE_RE.match(line):
            continue
        collected.append(line)
        if len(collected) > 8:
            break
    if not collected:
        return None
    title = _clean(" ".join(collected)) if terminated else collected[0]
    return title[:300] or None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def extract_spec_document(
    pdf_bytes: bytes,
    *,
    max_pages: int = 300,
    time_budget_seconds: float = 60.0,
) -> SpecDocument:
    """Extract the element requirements of an IDTA specification PDF.

    Never raises for malformed, encrypted or non-PDF input: an empty
    :class:`SpecDocument` with a warning is returned instead.  Processing
    stops (with a warning) after ``max_pages`` pages or once
    ``time_budget_seconds`` have elapsed; elements found so far are kept.
    """
    started = time.monotonic()
    if not isinstance(pdf_bytes, (bytes, bytearray, memoryview)) or len(pdf_bytes) == 0:
        return SpecDocument(elements=[], page_count=0, warnings=["empty or invalid input"])
    data = bytes(pdf_bytes)
    if b"%PDF-" not in data[:1024]:
        return SpecDocument(elements=[], page_count=0, warnings=["input is not a PDF document"])

    try:
        import pdfplumber
    except Exception as exc:  # noqa: BLE001 - dependency missing/broken
        return SpecDocument(
            elements=[], page_count=0, warnings=[f"pdfplumber unavailable ({type(exc).__name__})"]
        )

    extractor = _Extractor()
    page_count = 0
    title: str | None = None
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = pdf.pages
            page_count = len(pages)
            first_text: str | None = None
            limit = max(0, int(max_pages))
            if page_count > limit:
                extractor.warn(
                    f"document has {page_count} pages; only the first {limit} were read"
                )
            for index, page in enumerate(pages[:limit]):
                page_no = index + 1
                if time.monotonic() - started > time_budget_seconds:
                    extractor.warn(
                        f"time budget of {time_budget_seconds:g}s exceeded; "
                        f"stopped before page {page_no} of {page_count}"
                    )
                    break
                try:
                    if index == 0:
                        try:
                            first_text = page.extract_text() or ""
                        except Exception:  # noqa: BLE001
                            first_text = None
                    extractor.process_page(page_no, page)
                except Exception as exc:  # noqa: BLE001 - keep going on broken pages
                    extractor.warn(f"page {page_no}: skipped ({type(exc).__name__})")
                finally:
                    try:
                        page.close()
                    except Exception:  # noqa: BLE001
                        pass
            try:
                title = _extract_title(pdf.metadata, first_text)
            except Exception:  # noqa: BLE001
                title = None
    except Exception as exc:  # noqa: BLE001 - malformed / encrypted / not a PDF
        logger.info("spec_pdf_unreadable", extra={"error": type(exc).__name__})
        extractor.warn(f"PDF could not be read ({type(exc).__name__})")
        if page_count == 0:
            return SpecDocument(elements=[], page_count=0, warnings=list(extractor.warnings))

    try:
        elements = extractor.build()
    except Exception as exc:  # noqa: BLE001
        extractor.warn(f"element assembly failed ({type(exc).__name__})")
        elements = []
    if not elements and page_count and not extractor.warnings:
        extractor.warn("no element tables following the IDTA table convention were found")
    return SpecDocument(
        elements=elements,
        page_count=page_count,
        title=title,
        warnings=list(extractor.warnings),
    )
