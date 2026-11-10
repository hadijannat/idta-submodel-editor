"""
Repeatable elements.

Many submodel templates allow an element to occur several times without
putting it into a SubmodelElementList: the element carries a cardinality of
``ZeroToMany`` or ``OneToMany`` and each further occurrence is a sibling with
an idShort of its own (``MailAddress__00__``, ``MailAddress__01__`` ...).

In form data the first occurrence stays where it always was, under the
template's idShort. Further occurrences are listed in its ``occurrences``
member::

    {"elements": {"Phone": {"value": "1", "occurrences": [{"value": "2"}]}}}

This module holds the rules both validation and hydration follow.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

OCCURRENCES_KEY = "occurrences"

# A list repeats through its items; the other three are read-only in the editor.
_NOT_REPEATABLE_MODEL_TYPES = frozenset(
    {"SubmodelElementList", "Operation", "Capability", "BasicEventElement"}
)

_CARDINALITY_PATTERN = re.compile(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$")
_COUNTER_SUFFIX = re.compile(r"^(?P<stem>.*?)__(?P<number>\d+)__$")
_DEFAULT_COUNTER_WIDTH = 2


def max_occurrences(cardinality: str | None) -> int | None:
    """
    Upper bound of a normalized cardinality such as ``[0..*]``; ``None`` if unbounded.

    Anything that is not a recognised cardinality counts as exactly one.
    """
    match = _CARDINALITY_PATTERN.match((cardinality or "").strip())
    if not match:
        return 1
    lower, upper = match.group(1), match.group(2)
    if upper is None:
        return int(lower)
    if upper == "*":
        return None
    return int(upper)


def is_repeatable(model_type: str | None, cardinality: str | None) -> bool:
    """Whether an element of this type and cardinality may occur more than once."""
    if model_type in _NOT_REPEATABLE_MODEL_TYPES:
        return False
    limit = max_occurrences(cardinality)
    return limit is None or limit > 1


def additional_occurrences(form_element: Any) -> list[Any]:
    """The further occurrences given for an element in form data (never ``None``)."""
    if not isinstance(form_element, dict):
        return []
    occurrences = form_element.get(OCCURRENCES_KEY)
    return occurrences if isinstance(occurrences, list) else []


def occurrence_id_shorts(
    template_id_short: str, count: int, taken: Iterable[str]
) -> list[str]:
    """
    idShorts for ``count`` further occurrences of an element.

    A template idShort that ends in a counter (``Mode__00__``) is counted up
    with the same width. Any other idShort gets such a counter appended,
    starting at ``__01__`` since the first occurrence keeps the plain name.
    Names in ``taken`` are skipped, so siblings never collide.
    """
    used = set(taken)
    match = _COUNTER_SUFFIX.match(template_id_short)
    if match:
        stem = match.group("stem")
        width = len(match.group("number"))
        number = int(match.group("number"))
    else:
        stem, width, number = template_id_short, _DEFAULT_COUNTER_WIDTH, 0

    names: list[str] = []
    while len(names) < count:
        number += 1
        candidate = f"{stem}__{number:0{width}d}__"
        if candidate in used:
            continue
        used.add(candidate)
        names.append(candidate)
    return names
