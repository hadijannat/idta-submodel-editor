"""
Index of the IDTA submodel-templates repository layout.

The upstream repository (admin-shell-io/submodel-templates) organises
templates as::

    <status>/<Template>/<major>/<minor>[/<patch>]/<files>
    <status>/<Template>/<Part>/<major>/<minor>[/<patch>]/<files>

where ``<files>`` are the template package (``.aasx``), its JSON
serialisation, the specification PDF and a README. Several AASX files can sit
in one version directory (the template itself, a variant for AAS metamodel
V3.1, filled samples), and newer patch directories often omit the PDF because
the specification text did not change.

This module turns a flat list of repository paths into resolved template
entries: every template and every part of a multi-part template, each with
its versions sorted newest first and the files that belong to each version.
It performs no I/O, so it can be fed from the GitHub git-trees API, from a
local checkout, or from a test fixture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

TEMPLATE_STATUSES = ("published", "deprecated")

# Separator between a template directory and a part directory in template
# names. Template names travel as a single URL path segment, so the "/" of the
# repository path cannot be used.
PART_SEPARATOR = "~"

_IDTA_NUMBER_RE = re.compile(r"IDTA[\s_-]*(\d{4,5})((?:-\d+)*)", re.IGNORECASE)
_SAMPLE_NAME_RE = re.compile(r"sample|example|filled|demo", re.IGNORECASE)
_PART_PREFIX_RE = re.compile(r"^(?:part[\s_-]*)?(\d+)[\s_-]+(.*)$", re.IGNORECASE)
_TRAILING_PART_RE = re.compile(r"^(.*?)[\s_-]*part[\s_-]*(\d+)$", re.IGNORECASE)
_VERSION_SEGMENT_RE = re.compile(r"^\d+(?:\.\d+)*$")


@dataclass(frozen=True)
class RepoFile:
    """A file in the template repository."""

    path: str
    sha: str | None = None
    size: int | None = None

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def directory(self) -> str:
        return self.path.rsplit("/", 1)[0] if "/" in self.path else ""


@dataclass
class TemplateVersion:
    """One published version of a template (or template part)."""

    version: tuple[int, ...]
    path: str
    aasx: RepoFile | None = None
    variants: list[RepoFile] = field(default_factory=list)
    json: RepoFile | None = None
    pdf: RepoFile | None = None
    readme: RepoFile | None = None

    @property
    def label(self) -> str:
        return ".".join(str(part) for part in self.version)

    @property
    def is_sample_only(self) -> bool:
        return self.aasx is not None and is_sample_name(self.aasx.name)


@dataclass
class TemplateEntry:
    """A selectable template: a template directory or one part of it."""

    status: str
    name: str
    directory: str
    title: str
    idta_number: str | None = None
    group: str | None = None
    part: str | None = None
    versions: list[TemplateVersion] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"{self.status}/{self.name}"

    @property
    def latest(self) -> TemplateVersion | None:
        """Newest version that ships a real template (not just a sample)."""
        for version in self.versions:
            if version.aasx is not None and not version.is_sample_only:
                return version
        for version in self.versions:
            if version.aasx is not None:
                return version
        return None


@dataclass
class ResolvedTemplate:
    """Result of resolving a template path (optionally with a version)."""

    entry: TemplateEntry
    version: TemplateVersion


def is_sample_name(filename: str) -> bool:
    """Whether a file name denotes a filled sample rather than the template."""
    return bool(_SAMPLE_NAME_RE.search(filename))


def parse_version(value: str | None) -> tuple[int, ...] | None:
    """Parse ``"3.0.2"``, ``"3/0/2"`` or ``"v3.0"`` into ``(3, 0, 2)``."""
    if value is None:
        return None
    text = str(value).strip().strip("/")
    if not text or text.lower() == "latest":
        return None
    if text[:1] in ("v", "V"):
        text = text[1:]
    parts = [part for part in re.split(r"[./]", text) if part != ""]
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _pretty_title(name: str) -> str:
    title = re.sub(r"[_]+", " ", name)
    return re.sub(r"\s+", " ", title).strip()


def _pretty_part(part: str) -> str:
    """Turn ``"1_Digital Nameplate"`` into ``"Part 1: Digital Nameplate"``."""
    text = _pretty_title(part.replace("/", " / "))
    match = _PART_PREFIX_RE.match(text)
    if match and match.group(2).strip():
        return f"Part {int(match.group(1))}: {match.group(2).strip()}"
    match = _TRAILING_PART_RE.match(text)
    if match:
        return f"Part {int(match.group(2))}"
    return text


def _natural_key(value: str) -> list:
    return [
        (0, int(token)) if token.isdigit() else (1, token.lower())
        for token in re.split(r"(\d+)", value)
        if token != ""
    ]


def extract_idta_number(filename: str) -> str | None:
    """
    Extract the IDTA document number from a template file name.

    ``IDTA 02006-3-0-3_Template_...`` -> ``02006`` (number-major-minor-patch),
    ``IDTA 02035-1_DBP-Part-1_...`` -> ``02035-1`` (number-part).
    """
    match = _IDTA_NUMBER_RE.search(filename)
    if not match:
        return None
    number = match.group(1).zfill(5)
    suffix_groups = [group for group in match.group(2).split("-") if group]
    if len(suffix_groups) == 1:
        return f"{number}-{suffix_groups[0]}"
    return number


def _file_rank(file: RepoFile) -> tuple:
    """Sort key selecting the canonical template file of a directory (lowest wins)."""
    name = file.name
    lowered = name.lower()
    return (
        1 if is_sample_name(name) else 0,
        1 if "foraasmetamodel" in lowered else 0,
        0 if "template" in lowered else 1,
        1 if "without" in lowered else 0,
        len(name),
        lowered,
    )


def _stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0]


class TemplateRepoIndex:
    """Resolved view of the template repository."""

    def __init__(self, files: Iterable[RepoFile], *, source: str = "github") -> None:
        self.source = source
        self._files = [file for file in files if file.path]
        self._entries: dict[str, list[TemplateEntry]] = {
            status: [] for status in TEMPLATE_STATUSES
        }
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        grouped: dict[tuple[str, str, str], dict[tuple[int, ...], list[RepoFile]]] = {}

        for file in self._files:
            segments = file.path.split("/")
            if len(segments) < 3 or segments[0] not in TEMPLATE_STATUSES:
                continue
            status, template_dir = segments[0], segments[1]
            inner = segments[2:-1]

            prefix_len = 0
            while prefix_len < len(inner) and not inner[prefix_len].isdigit():
                prefix_len += 1
            version_len = 0
            while (
                prefix_len + version_len < len(inner)
                and inner[prefix_len + version_len].isdigit()
            ):
                version_len += 1
            if prefix_len + version_len != len(inner):
                # Files below a version directory (docs/, images/) are not
                # part of the template payload.
                continue

            prefix = "/".join(inner[:prefix_len])
            version = tuple(int(part) for part in inner[prefix_len:])
            grouped.setdefault((status, template_dir, prefix), {}).setdefault(
                version, []
            ).append(file)

        for (status, template_dir, prefix), by_version in grouped.items():
            if not any(
                file.name.lower().endswith(".aasx")
                for files in by_version.values()
                for file in files
            ):
                continue
            entry = self._build_entry(status, template_dir, prefix, by_version)
            if entry.versions:
                self._entries[status].append(entry)

        for status in TEMPLATE_STATUSES:
            self._entries[status].sort(
                key=lambda entry: (
                    _natural_key(entry.group or entry.name),
                    _natural_key(entry.part or ""),
                )
            )

    def _build_entry(
        self,
        status: str,
        template_dir: str,
        prefix: str,
        by_version: dict[tuple[int, ...], list[RepoFile]],
    ) -> TemplateEntry:
        base_dir = f"{status}/{template_dir}"
        directory = f"{base_dir}/{prefix}" if prefix else base_dir

        versions: list[TemplateVersion] = []
        for version, files in by_version.items():
            aasx_files = sorted(
                (f for f in files if f.name.lower().endswith(".aasx")), key=_file_rank
            )
            if not aasx_files:
                continue
            version_path = "/".join([directory, *[str(part) for part in version]])
            primary = aasx_files[0]
            versions.append(
                TemplateVersion(
                    version=version,
                    path=version_path,
                    aasx=primary,
                    variants=aasx_files[1:],
                    json=self._pick_json(primary, files),
                    pdf=self._pick_pdf(files),
                    readme=next(
                        (f for f in files if f.name.lower() == "readme.md"), None
                    ),
                )
            )
        versions.sort(key=lambda item: item.version, reverse=True)
        self._inherit_documents(versions, by_version)

        name = template_dir
        title = _pretty_title(template_dir)
        group: str | None = None
        part: str | None = None
        if prefix:
            name = PART_SEPARATOR.join([template_dir, *prefix.split("/")])
            group = _pretty_title(template_dir)
            part = _pretty_part(prefix)
            title = f"{group} – {part}"

        idta_number = None
        for version in versions:
            if version.aasx is None:
                continue
            idta_number = extract_idta_number(version.aasx.name)
            if idta_number:
                break

        return TemplateEntry(
            status=status,
            name=name,
            directory=directory,
            title=title,
            idta_number=idta_number,
            group=group,
            part=part,
            versions=versions,
        )

    @staticmethod
    def _pick_json(primary: RepoFile, files: list[RepoFile]) -> RepoFile | None:
        json_files = [f for f in files if f.name.lower().endswith(".json")]
        if not json_files:
            return None
        stem = _stem(primary.name).lower()
        for candidate in json_files:
            if _stem(candidate.name).lower() == stem:
                return candidate
        return sorted(json_files, key=_file_rank)[0]

    @staticmethod
    def _pick_pdf(files: list[RepoFile]) -> RepoFile | None:
        pdf_files = [f for f in files if f.name.lower().endswith(".pdf")]
        if not pdf_files:
            return None
        return sorted(
            pdf_files,
            key=lambda f: (
                1 if is_sample_name(f.name) else 0,
                0 if "submodel" in f.name.lower() else 1,
                len(f.name),
                f.name.lower(),
            ),
        )[0]

    @staticmethod
    def _inherit_documents(
        versions: list[TemplateVersion],
        by_version: dict[tuple[int, ...], list[RepoFile]],
    ) -> None:
        """
        Give versions without their own PDF the nearest applicable one.

        Patch releases routinely ship only the corrected AASX/JSON; the
        specification PDF of the same major.minor line still applies. Prefer
        the closest older release of that line, then the closest newer one.
        """
        pdf_by_version: dict[tuple[int, ...], RepoFile] = {}
        for version, files in by_version.items():
            pdf = TemplateRepoIndex._pick_pdf(files)
            if pdf is not None:
                pdf_by_version[version] = pdf

        for item in versions:
            if item.pdf is not None:
                continue
            line = item.version[:2]
            same_line = [v for v in pdf_by_version if v[:2] == line]
            older = sorted((v for v in same_line if v <= item.version), reverse=True)
            newer = sorted(v for v in same_line if v > item.version)
            chosen = (older or newer or [None])[0]
            if chosen is not None:
                item.pdf = pdf_by_version[chosen]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return sum(len(entries) for entries in self._entries.values())

    def entries(self, status: str) -> list[TemplateEntry]:
        return list(self._entries.get(status, []))

    def find_entry(self, status: str, name: str) -> TemplateEntry | None:
        """Find an entry by name, tolerating case and punctuation differences."""
        entries = self._entries.get(status, [])
        if not entries:
            return None

        candidate = name.strip().strip("/")
        variants = {candidate, candidate.replace("/", PART_SEPARATOR)}
        for entry in entries:
            if entry.name in variants:
                return entry
        lowered = {variant.lower() for variant in variants}
        for entry in entries:
            if entry.name.lower() in lowered:
                return entry
        keys = {_normalize_key(variant) for variant in variants}
        keys.discard("")
        for entry in entries:
            if _normalize_key(entry.name) in keys:
                return entry

        # A multi-part template addressed by its directory resolves to its
        # first part so that legacy links keep working.
        for entry in entries:
            if entry.group and _normalize_key(entry.name.split(PART_SEPARATOR)[0]) in keys:
                return entry
        return None

    def resolve(
        self, template_path: str, version: str | None = None
    ) -> ResolvedTemplate | None:
        """
        Resolve ``<status>/<name>[/<version>]`` to a template version.

        The version may be given in the path (``.../3/0/2``) or separately
        (``"3.0.2"``). A single-number version selects the newest release of
        that major line; longer versions select that exact release when it
        exists, otherwise the newest release they are a prefix of.
        """
        cleaned = template_path.strip().strip("/")
        status, _, rest = cleaned.partition("/")
        if status not in TEMPLATE_STATUSES or not rest:
            return None

        segments = [segment for segment in rest.split("/") if segment != ""]
        path_version: list[int] = []
        # Trailing version segments: "3/0/2" as in the repository, or a single
        # dotted "3.0.2". The first segment is always the template name.
        while len(segments) > 1 and _VERSION_SEGMENT_RE.match(segments[-1]):
            path_version[0:0] = [int(part) for part in segments.pop().split(".")]
        if not segments:
            return None

        entry = self.find_entry(status, "/".join(segments))
        if entry is None:
            return None

        requested = parse_version(version) or (tuple(path_version) or None)
        selected = self.select_version(entry, requested)
        if selected is None:
            return None
        return ResolvedTemplate(entry=entry, version=selected)

    @staticmethod
    def select_version(
        entry: TemplateEntry, requested: tuple[int, ...] | None
    ) -> TemplateVersion | None:
        if requested is None:
            return entry.latest

        if len(requested) >= 2:
            for item in entry.versions:
                if item.version == requested and item.aasx is not None:
                    return item

        matching = [
            item
            for item in entry.versions
            if item.version[: len(requested)] == requested and item.aasx is not None
        ]
        for item in matching:
            if not item.is_sample_only:
                return item
        return matching[0] if matching else None
