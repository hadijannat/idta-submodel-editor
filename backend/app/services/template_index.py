"""
Template index built from a listing of the upstream template repository.

The IDTA repository lays templates out as::

    published/<Folder>/<major>/<minor>[/<patch>]/<file>.aasx
    published/<Folder>/<Part>/<major>/<minor>[/<patch>]/<file>.aasx

A folder can therefore hold several templates ("parts"), each with several
versions, and the newest file usually sits in the deepest patch directory.
This module turns a flat list of repository file paths into that structure so
the fetcher can list every template and pick the newest file without walking
the tree one directory request at a time.

Everything here is pure: no network or filesystem access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

_IDTA_NUMBER_PATTERN = re.compile(r"IDTA[\s_-]*(\d{5})", re.IGNORECASE)
_VERSION_SEGMENT_PATTERN = re.compile(r"^\d+$")
_PART_ORDINAL_PREFIX = re.compile(r"^\d+[_\s-]+")

# Markers of files that sit next to a template but are not the template itself.
_NON_TEMPLATE_MARKERS = ("example", "sample")

PART_NAME_SEPARATOR = " - "


@dataclass(frozen=True)
class TemplateFile:
    """A file in the upstream repository."""

    path: str
    sha: str | None = None

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


@dataclass
class TemplateVersion:
    """One version directory of a template and the AASX files directly in it."""

    version: tuple[int, ...]
    path: str
    files: list[TemplateFile] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Dotted version, e.g. ``3.0.3``."""
        return ".".join(str(part) for part in self.version)

    @property
    def relative_path(self) -> str:
        """Version as a path fragment below the template, e.g. ``3/0/3``."""
        return "/".join(str(part) for part in self.version)


@dataclass
class TemplateUnit:
    """A single submodel template: a folder, or one part of a multi-part folder."""

    status: str
    folder: str
    part: str | None
    versions: list[TemplateVersion] = field(default_factory=list)

    @property
    def path(self) -> str:
        base = f"{self.status}/{self.folder}"
        return f"{base}/{self.part}" if self.part else base

    @property
    def name(self) -> str:
        """Flat, slash-free identifier that is safe to use as a URL path segment."""
        if not self.part:
            return self.folder
        return PART_NAME_SEPARATOR.join([self.folder, *self.part.split("/")])

    @property
    def title(self) -> str:
        folder_title = _humanize(self.folder)
        if not self.part:
            return folder_title
        part_title = " ".join(
            _humanize(_PART_ORDINAL_PREFIX.sub("", segment))
            for segment in self.part.split("/")
        )
        if part_title.lower().startswith(folder_title.lower()):
            return part_title
        return f"{folder_title}: {part_title}"

    @property
    def latest(self) -> TemplateVersion | None:
        """Newest version that has a template file."""
        return self.resolve_version()

    @property
    def latest_file(self) -> TemplateFile | None:
        latest = self.latest
        return select_template_file(latest.files) if latest else None

    @property
    def idta_number(self) -> str | None:
        """Five-digit IDTA number taken from the template's file names."""
        for version in self.versions:
            chosen = select_template_file(version.files)
            candidates = [chosen] if chosen else []
            candidates.extend(f for f in version.files if f is not chosen)
            for candidate in candidates:
                match = _IDTA_NUMBER_PATTERN.search(candidate.name)
                if match:
                    return match.group(1)
        return None

    def find_version(self, relative_path: str) -> list[TemplateVersion]:
        """
        Versions at or below ``relative_path`` (e.g. ``3`` or ``3/0``), newest first.

        Raises ``ValueError`` when ``relative_path`` is not made of numbers.
        """
        wanted = _parse_version_path(relative_path)
        return [v for v in self.versions if v.version[: len(wanted)] == wanted]

    def loadable_versions(self, relative_path: str = "") -> list[TemplateVersion]:
        """
        Versions at or below ``relative_path`` that have a file to load, newest first.

        Directories that only hold examples or samples are not releases of the
        template; they are listed only when the template has nothing better.

        Raises ``ValueError`` when ``relative_path`` is not made of numbers.
        """
        matching = self.find_version(relative_path)
        return [
            v for v in matching if select_template_file(v.files, allow_auxiliary=False)
        ] or [v for v in matching if select_template_file(v.files)]

    def resolve_version(self, relative_path: str = "") -> TemplateVersion | None:
        """
        The version to load for ``relative_path``.

        A version that is named exactly and has a template file of its own is
        used as is, so ``1/0`` means the unpatched 1.0 even when ``1/0/2``
        exists. Anything else (no version, or a prefix such as ``3``) resolves
        to the newest version below it. Directories that only hold examples
        or samples are passed over while a real template file exists.

        Raises ``ValueError`` when ``relative_path`` is not made of numbers.
        """
        wanted = _parse_version_path(relative_path)
        candidates = self.loadable_versions(relative_path)
        if not candidates:
            return None
        for candidate in candidates:
            if wanted and candidate.version == wanted:
                return candidate
        return candidates[0]


def _parse_version_path(relative_path: str) -> tuple[int, ...]:
    return tuple(
        int(segment) for segment in relative_path.strip("/").split("/") if segment
    )


def _humanize(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip()


def is_aasx(path: str) -> bool:
    return path.lower().endswith(".aasx")


def template_file_rank(name: str) -> tuple[int, int, int]:
    """
    Rank a file name for "is this the template itself"; lower is better.

    Examples and samples lose to anything else, a name that says "template"
    wins among the rest, and shorter names win after that so that the plain
    file is preferred over variants such as ``..._forAASMetamodelV3.1.aasx``
    or ``..._withOperations_...aasx``.
    """
    says_template = "template" in name.lower()
    return (1 if is_auxiliary_file(name) else 0, 0 if says_template else 1, len(name))


def is_auxiliary_file(name: str) -> bool:
    """Whether a file is an example or sample rather than the template itself."""
    lowered = name.lower()
    return any(marker in lowered for marker in _NON_TEMPLATE_MARKERS)


def select_template_file(
    files: Iterable[TemplateFile], *, allow_auxiliary: bool = True
) -> TemplateFile | None:
    """
    Pick the template AASX among the AASX files of one version directory.

    With ``allow_auxiliary=False`` a directory that only holds examples or
    samples yields nothing.
    """
    candidates = [
        f
        for f in files
        if is_aasx(f.path) and (allow_auxiliary or not is_auxiliary_file(f.name))
    ]
    if not candidates:
        return None
    # Reverse name order first so that ties keep the historic "highest name wins".
    candidates.sort(key=lambda f: f.name, reverse=True)
    candidates.sort(key=lambda f: template_file_rank(f.name))
    return candidates[0]


def split_template_file_path(
    relative_segments: list[str],
) -> tuple[str | None, tuple[int, ...]] | None:
    """
    Split the directories between a template folder and one of its files.

    Leading non-numeric directories name a part, the numeric ones after them
    are the version. Returns ``None`` when a non-numeric directory follows the
    version: such files (``docs/``, ``examples/`` ...) are supporting material.
    """
    part_segments: list[str] = []
    version: list[int] = []
    for segment in relative_segments:
        if _VERSION_SEGMENT_PATTERN.match(segment):
            version.append(int(segment))
        elif version:
            return None
        else:
            part_segments.append(segment)
    return ("/".join(part_segments) or None), tuple(version)


def build_template_units(files: Iterable[TemplateFile], status: str) -> list[TemplateUnit]:
    """
    Group the AASX files below ``<status>/`` into templates.

    Units are ordered by folder and part, with a folder's own template before
    its parts; versions within a unit are newest first.
    """
    prefix = f"{status}/"
    units: dict[tuple[str, str | None], dict[tuple[int, ...], TemplateVersion]] = {}

    for file in files:
        if not file.path.startswith(prefix) or not is_aasx(file.path):
            continue
        segments = file.path[len(prefix) :].split("/")
        if len(segments) < 2:
            continue  # an AASX directly below the status root belongs to no template
        folder, directories = segments[0], segments[1:-1]
        split = split_template_file_path(directories)
        if split is None:
            continue
        part, version = split
        versions = units.setdefault((folder, part), {})
        entry = versions.get(version)
        if entry is None:
            entry = TemplateVersion(
                version=version,
                path="/".join([status, folder, *directories]),
            )
            versions[version] = entry
        entry.files.append(file)

    result = [
        TemplateUnit(
            status=status,
            folder=folder,
            part=part,
            versions=sorted(versions.values(), key=lambda v: v.version, reverse=True),
        )
        for (folder, part), versions in units.items()
    ]
    result.sort(key=lambda u: (u.folder.lower(), u.part is not None, (u.part or "").lower()))
    return result


def find_unit_for_path(units: Iterable[TemplateUnit], path: str) -> TemplateUnit | None:
    """The unit whose directory is ``path`` or contains it (longest match wins)."""
    normalized = path.strip("/")
    best: TemplateUnit | None = None
    for unit in units:
        if normalized == unit.path or normalized.startswith(unit.path + "/"):
            if best is None or len(unit.path) > len(best.path):
                best = unit
    return best


def select_file_for_path(units: Iterable[TemplateUnit], path: str) -> TemplateFile | None:
    """
    Resolve a template path to the AASX file to load.

    ``path`` is a unit directory, optionally followed by a (partial) version
    such as ``published/Digital nameplate/3``; see
    :meth:`TemplateUnit.resolve_version` for how the version is chosen.
    """
    normalized = path.strip("/")
    unit = find_unit_for_path(units, normalized)
    if unit is None:
        return None
    remainder = normalized[len(unit.path) :].strip("/")
    try:
        version = unit.resolve_version(remainder)
    except ValueError:
        return None  # the remainder is not a version (e.g. an unknown sub-folder)
    return select_template_file(version.files) if version else None
