"""Tests for the template repository index (versions, parts, documents)."""

from app.services.template_repo import (
    RepoFile,
    TemplateRepoIndex,
    extract_idta_number,
    parse_version,
)

NAMEPLATE = "published/Digital nameplate"
DBP = "published/Digital Battery Passport"

PATHS = [
    # A release line whose base folder also holds newer patch folders.
    f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Template_Digital Nameplate.aasx",
    f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Template_Digital Nameplate.json",
    f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Submodel_Digital Nameplate.pdf",
    f"{NAMEPLATE}/3/0/README.md",
    f"{NAMEPLATE}/3/0/docs/modules/ROOT/pages/index.adoc",
    f"{NAMEPLATE}/3/0/2/IDTA 02006-3-0-2_Template_Digital Nameplate.aasx",
    f"{NAMEPLATE}/3/0/2/IDTA 02006-3-0_Submodel_Digital Nameplate.pdf",
    f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.aasx",
    f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.json",
    f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate_forAASMetamodelV3.1.aasx",
    f"{NAMEPLATE}/2/0/IDTA 02006-2-0_Template_Digital Nameplate.aasx",
    # Multi-part template.
    f"{DBP}/1_Digital Nameplate/1/0/IDTA 02035-1_DBP-Part-1_Digital Nameplate.aasx",
    f"{DBP}/1_Digital Nameplate/1/0/1/IDTA 02035-1_DBP-Part-1_Digital Nameplate.aasx",
    f"{DBP}/1_Digital Nameplate/1/0/1/IDTA 02035-1_DBP-Part-1_Digital Nameplate.pdf",
    f"{DBP}/7_Circularity/1/0/2/IDTA 02035-7_DBP-Part-7_Circularity.aasx",
    # Newest folder holds only a filled sample.
    "published/Technical_Data/2/0/IDTA 02003_Template_TechnicalData.aasx",
    "published/Technical_Data/2/0/5/IDTA 02003_Sample_TechnicalData.aasx",
    # Deprecated template and unrelated files.
    "deprecated/Carbon Footprint/0/9/IDTA_2023-0-9_Template_CarbonFootprint.aasx",
    "README.md",
    "tools/script.py",
    "published/Empty Template/1/0/README.md",
]


def build_index() -> TemplateRepoIndex:
    return TemplateRepoIndex(RepoFile(path=path, sha=f"sha-{i}") for i, path in enumerate(PATHS))


def test_lists_templates_and_parts_per_status():
    index = build_index()

    published = [entry.name for entry in index.entries("published")]
    assert published == [
        "Digital Battery Passport~1_Digital Nameplate",
        "Digital Battery Passport~7_Circularity",
        "Digital nameplate",
        "Technical_Data",
    ]
    assert [entry.name for entry in index.entries("deprecated")] == ["Carbon Footprint"]


def test_latest_version_is_newest_patch_not_first_folder():
    entry = build_index().find_entry("published", "Digital nameplate")

    assert entry is not None
    assert [version.label for version in entry.versions] == ["3.0.3", "3.0.2", "3.0", "2.0"]
    assert entry.latest is not None
    assert entry.latest.label == "3.0.3"
    # The plain template is preferred over the metamodel V3.1 variant.
    assert entry.latest.aasx is not None
    assert entry.latest.aasx.name == "IDTA 02006-3-0-3_Template_Digital Nameplate.aasx"
    assert [variant.name for variant in entry.latest.variants] == [
        "IDTA 02006-3-0-3_Template_Digital Nameplate_forAASMetamodelV3.1.aasx"
    ]
    assert entry.idta_number == "02006"


def test_patch_release_inherits_specification_of_its_release_line():
    entry = build_index().find_entry("published", "Digital nameplate")
    assert entry is not None
    by_label = {version.label: version for version in entry.versions}

    # 3.0.3 ships no PDF: the closest older one of the 3.0 line applies.
    assert by_label["3.0.3"].pdf is not None
    assert by_label["3.0.3"].pdf.path.startswith(f"{NAMEPLATE}/3/0/2/")
    assert by_label["3.0"].pdf is not None
    assert by_label["3.0"].pdf.path.startswith(f"{NAMEPLATE}/3/0/IDTA")
    # Another release line does not borrow it.
    assert by_label["2.0"].pdf is None
    # JSON with the same stem as the package is paired with it.
    assert by_label["3.0.3"].json is not None
    assert by_label["3.0.3"].json.name == "IDTA 02006-3-0-3_Template_Digital Nameplate.json"


def test_sample_only_folder_does_not_become_latest():
    entry = build_index().find_entry("published", "Technical_Data")

    assert entry is not None
    assert entry.title == "Technical Data"
    assert entry.versions[0].label == "2.0.5"
    assert entry.versions[0].is_sample_only
    assert entry.latest is not None
    assert entry.latest.label == "2.0"


def test_parts_are_separate_entries_grouped_by_template():
    index = build_index()
    part = index.find_entry("published", "Digital Battery Passport~7_Circularity")

    assert part is not None
    assert part.group == "Digital Battery Passport"
    assert part.part == "Part 7: Circularity"
    assert part.title == "Digital Battery Passport – Part 7: Circularity"
    assert part.idta_number == "02035-7"
    assert part.path == "published/Digital Battery Passport~7_Circularity"


def test_resolve_accepts_version_forms_and_loose_names():
    index = build_index()

    def resolved(path: str, version: str | None = None) -> str | None:
        result = index.resolve(path, version)
        return result.version.label if result else None

    assert resolved("published/Digital nameplate") == "3.0.3"
    assert resolved("published/digital-nameplate") == "3.0.3"
    assert resolved("published/Digital nameplate", "3") == "3.0.3"
    assert resolved("published/Digital nameplate", "2") == "2.0"
    # Two or more numbers select that exact release when it exists.
    assert resolved("published/Digital nameplate", "3.0") == "3.0"
    assert resolved("published/Digital nameplate/3/0/2") == "3.0.2"
    assert resolved("published/Digital nameplate/3.0.2") == "3.0.2"
    assert resolved("published/Digital nameplate", "v3.0.2") == "3.0.2"
    assert resolved("published/Digital nameplate", "9") is None
    assert resolved("published/Unknown") is None
    assert resolved("local/Something") is None


def test_resolve_part_by_repository_path_and_by_template_directory():
    index = build_index()

    by_path = index.resolve("published/Digital Battery Passport/1_Digital Nameplate/1/0")
    assert by_path is not None
    assert by_path.entry.name == "Digital Battery Passport~1_Digital Nameplate"
    assert by_path.version.label == "1.0"

    # Legacy links to the template directory resolve to its first part.
    first_part = index.resolve("published/Digital Battery Passport")
    assert first_part is not None
    assert first_part.entry.name == "Digital Battery Passport~1_Digital Nameplate"
    assert first_part.version.label == "1.0.1"


def test_template_named_like_a_version_is_not_mistaken_for_one():
    index = TemplateRepoIndex(
        [RepoFile(path="published/sensor4.0/Part 1 Measurement Value/1/0/t.aasx")]
    )

    result = index.resolve("published/sensor4.0~Part 1 Measurement Value")

    assert result is not None
    assert result.entry.group == "sensor4.0"


def test_extract_idta_number_distinguishes_parts_from_versions():
    assert extract_idta_number("IDTA 02006-3-0-3_Template_Digital Nameplate.aasx") == "02006"
    assert extract_idta_number("IDTA 02035-1_DBP-Part-1_Digital Nameplate.aasx") == "02035-1"
    assert extract_idta_number("IDTA_2023-0-9_Template_CarbonFootprint.aasx") == "02023"
    assert extract_idta_number("IDTA-02050-1-0-1_Template_PurchaseOrder.aasx") == "02050"
    assert extract_idta_number("SMT_pure_ZVEI_Digital_Nameplate_V10.aasx") is None


def test_parse_version():
    assert parse_version("3.0.2") == (3, 0, 2)
    assert parse_version("3/0") == (3, 0)
    assert parse_version("v2") == (2,)
    assert parse_version("latest") is None
    assert parse_version("") is None
    assert parse_version("abc") is None
