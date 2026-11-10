"""
AAS JSON output that respects "no empty arrays".

The AAS JSON schema forbids empty arrays: an attribute without entries is
left out. The SDK's JSON serializer writes ``"specificAssetIds": []`` for
every entity without specific asset IDs, which makes each export that
contains such an entity fail conformance checks. The helpers here remove
empty arrays from serialized output, both for plain JSON and for the JSON
part inside an AASX package.
"""

from __future__ import annotations

import io
import json
from typing import Any, BinaryIO

from basyx.aas.adapter import aasx

_JSON_CONTENT_TYPE = "application/json"


def drop_empty_arrays(node: Any) -> Any:
    """Remove every object member whose value is an empty array, at any depth."""
    if isinstance(node, dict):
        return {
            key: drop_empty_arrays(value)
            for key, value in node.items()
            if not (isinstance(value, list) and not value)
        }
    if isinstance(node, list):
        return [drop_empty_arrays(item) for item in node]
    return node


def normalize_aas_json(text: str) -> str:
    """Return ``text`` without empty arrays; text that is not JSON is returned as is."""
    try:
        document = json.loads(text)
    except ValueError:
        return text
    return json.dumps(drop_empty_arrays(document))


class _NormalizingJsonPart(io.BytesIO):
    """Buffers a JSON part and writes the normalized document when closed."""

    def __init__(self, target: BinaryIO) -> None:
        super().__init__()
        self._target = target

    def close(self) -> None:
        if self.closed:
            return
        data = self.getvalue()
        super().close()
        try:
            self._target.write(normalize_aas_json(data.decode("utf-8")).encode("utf-8"))
        finally:
            self._target.close()


class NormalizingAASXWriter(aasx.AASXWriter):
    """AASXWriter whose JSON parts contain no empty arrays."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        open_part = self.writer.open_part

        def open_normalized_part(name: str, content_type: str) -> BinaryIO:
            part = open_part(name, content_type)
            if content_type.split(";")[0].strip() != _JSON_CONTENT_TYPE:
                return part
            return _NormalizingJsonPart(part)

        self.writer.open_part = open_normalized_part
