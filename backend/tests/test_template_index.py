"""Tests for the pure template index (parts, versions and file selection)."""

from pathlib import Path

import pytest

from app.services.template_index import (
    TemplateFile,
    build_template_units,
    find_unit_for_path,
    select_file_for_path,
    select_template_file,
    split_template_file_path,
)

SNAPSHOT = Path(__file__).parent / "fixtures" / "upstream" / "idta-aasx-paths.txt"


def _snapshot_files() -> list[TemplateFile]:
    return [
        TemplateFile(path=line)
        for line in SNAPSHOT.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]


def _files(*paths: str) -> list[TemplateFile]:
    return [TemplateFile(path=path) for path in paths]


@pytest.fixture(scope="module")
def published():
    return build_template_units(_snapshot_files(), "published")


@pytest.fixture(scope="module")
def deprecated():
    return build_template_units(_snapshot_files(), "deprecated")


class TestUpstreamSnapshot:
    """The real IDTA repository layout, frozen as a list of paths."""

    def test_every_template_is_listed(self, published, deprecated):
        assert len(published) == 66
        assert len(deprecated) == 8
        assert len({unit.folder for unit in published}) == 56

    def test_every_template_has_a_file_to_load(self, published, deprecated):
        for unit in [*published, *deprecated]:
            assert unit.latest_file is not None, unit.path
            assert unit.latest_file.path.startswith(unit.path + "/")

    def test_names_are_unique_url_segments(self, published):
        names = [unit.name for unit in published]
        assert len(set(names)) == len(names)
        assert not [name for name in names if "/" in name]

    def test_multi_part_folders_are_split(self, published):
        by_folder: dict[str, list] = {}
        for unit in published:
            by_folder.setdefault(unit.folder, []).append(unit)

        battery = by_folder["Digital Battery Passport"]
        assert [unit.part for unit in battery] == [
            "1_Digital Nameplate",
            "2_Handover Documentation",
            "3_Product Carbon Footprint",
            "4_Technical Data",
            "5_Product Condition",
            "6_Material Composition",
            "7_Circularity",
        ]
        assert battery[0].name == "Digital Battery Passport - 1_Digital Nameplate"
        assert battery[0].title == "Digital Battery Passport: Digital Nameplate"
        assert {unit.idta_number for unit in battery} == {"02035"}

        assert len(by_folder["Safety Instrumented Functions"]) == 4

        # A folder can hold its own template next to a part.
        bom = by_folder["Hierarchical Structures enabling Bills of Material"]
        assert [unit.part for unit in bom] == [None, "Extension based on IEC 81346"]
        assert bom[0].name == "Hierarchical Structures enabling Bills of Material"

    def test_newest_version_wins(self, published):
        expected = {
            "published/Digital nameplate": "3.0.3",
            "published/Asset Interfaces Description": "1.2.1",
            "published/Asset Interfaces Mapping Configuration": "2.0.1",
            "published/Provision of Simulation Models": "1.1.2",
            "published/Time Series Data": "1.1.3",
        }
        by_path = {unit.path: unit for unit in published}
        for path, version in expected.items():
            assert by_path[path].latest.label == version

    def test_template_file_is_preferred_over_variants(self, published):
        by_path = {unit.path: unit for unit in published}

        nameplate = by_path["published/Digital nameplate"].latest_file
        assert nameplate.name == "IDTA 02006-3-0-3_Template_Digital Nameplate.aasx"

        # Examples sit next to the template in the same directory.
        connector = by_path["published/Interface Connector"].latest_file
        assert connector.name == "IDTA 02062-1-0_Template_Interface Connector.aasx"

        time_series = by_path["published/Time Series Data"].latest_file
        assert time_series.name == "IDTA 02008-1-1-3_Template_TimeSeriesData.aasx"

        for unit in published:
            lowered = unit.latest_file.name.lower()
            assert "example" not in lowered and "sample" not in lowered, unit.path

    def test_deeply_nested_template_is_reachable(self, published):
        selected = select_file_for_path(
            published,
            "published/Digital Product Passport/Digital Product Passport Part-1",
        )
        assert selected is not None
        assert selected.path.endswith(
            "/1/0/2/IDTA 02099-1_Template Digital Product Passport - Part 1.aasx"
        )

    def test_idta_numbers_come_from_file_names(self, published):
        assert not [unit.path for unit in published if not unit.idta_number]
        by_path = {unit.path: unit for unit in published}
        assert by_path["published/Digital nameplate"].idta_number == "02006"
        assert by_path["published/Technical_Data"].idta_number == "02003"
        assert by_path["published/Technical_Data"].title == "Technical Data"


class TestVersionSelection:
    def test_exact_version_is_not_replaced_by_its_patch(self, published):
        base = select_file_for_path(published, "published/Asset Interfaces Description/1/0")
        assert base.path.endswith(
            "/1/0/IDTA 02017-1-0_Template_Asset Interfaces Description.aasx"
        )
        patch = select_file_for_path(
            published, "published/Asset Interfaces Description/1/0/1"
        )
        assert "/1/0/1/" in patch.path

    def test_prefix_resolves_to_newest_below(self, published):
        selected = select_file_for_path(published, "published/Digital nameplate/3")
        assert "/3/0/3/" in selected.path

        older_minor = select_file_for_path(
            published, "published/Asset Interfaces Description/1/1"
        )
        assert "/1/1/" in older_minor.path

    def test_unknown_paths_resolve_to_nothing(self, published):
        assert select_file_for_path(published, "published/No Such Template") is None
        assert select_file_for_path(published, "published/Digital nameplate/9") is None
        assert select_file_for_path(published, "published/Digital nameplate/docs") is None
        # A folder that only holds parts has no template of its own.
        assert select_file_for_path(published, "published/Digital Battery Passport") is None

    def test_versions_compare_numerically(self):
        units = build_template_units(
            _files(
                "published/T/1/9/IDTA 02999_Template_T.aasx",
                "published/T/1/10/IDTA 02999_Template_T.aasx",
            ),
            "published",
        )
        assert units[0].latest.label == "1.10"

    def test_directory_with_only_an_example_is_not_the_newest_template(self):
        units = build_template_units(
            _files(
                "published/T/1/0/IDTA 02999_Template_T.aasx",
                "published/T/1/0/1/IDTA 02999_Example_T.aasx",
            ),
            "published",
        )
        assert units[0].latest.label == "1.0"
        assert units[0].latest_file.name == "IDTA 02999_Template_T.aasx"

    def test_example_is_used_when_nothing_else_exists(self):
        units = build_template_units(
            _files("published/T/1/0/IDTA 02999_Example_T.aasx"), "published"
        )
        assert units[0].latest_file.name == "IDTA 02999_Example_T.aasx"


class TestPathClassification:
    def test_split_part_and_version(self):
        assert split_template_file_path(["1", "0", "3"]) == (None, (1, 0, 3))
        assert split_template_file_path(["Part 1", "1", "0"]) == ("Part 1", (1, 0))
        assert split_template_file_path(["A", "B", "2"]) == ("A/B", (2,))
        assert split_template_file_path([]) == (None, ())

    def test_supporting_directories_are_ignored(self):
        assert split_template_file_path(["1", "0", "docs"]) is None
        units = build_template_units(
            _files(
                "published/T/1/0/IDTA 02999_Template_T.aasx",
                "published/T/1/0/examples/IDTA 02999_Template_Other.aasx",
            ),
            "published",
        )
        assert len(units) == 1
        assert [f.name for f in units[0].latest.files] == ["IDTA 02999_Template_T.aasx"]

    def test_other_roots_and_non_aasx_files_are_ignored(self):
        units = build_template_units(
            _files(
                "deprecated/T/1/0/IDTA 02999_Template_T.aasx",
                "published/T/1/0/IDTA 02999_Submodel_T.pdf",
                "published/stray.aasx",
            ),
            "published",
        )
        assert units == []

    def test_extension_is_case_insensitive(self):
        units = build_template_units(_files("published/T/1/0/T.AASX"), "published")
        assert units[0].latest_file.name == "T.AASX"

    def test_longest_unit_path_wins(self):
        units = build_template_units(
            _files(
                "published/Folder/1/0/a.aasx",
                "published/Folder/Part A/1/0/b.aasx",
            ),
            "published",
        )
        assert find_unit_for_path(units, "published/Folder/1").part is None
        assert find_unit_for_path(units, "published/Folder/Part A/1").part == "Part A"
        assert find_unit_for_path(units, "published/Folder2") is None


class TestFileSelection:
    def test_plain_template_beats_metamodel_variant(self):
        chosen = select_template_file(
            _files(
                "d/IDTA 02006-3-0-3_Template_Digital Nameplate_forAASMetamodelV3.1.aasx",
                "d/IDTA 02006-3-0-3_Template_Digital Nameplate.aasx",
            )
        )
        assert chosen.name == "IDTA 02006-3-0-3_Template_Digital Nameplate.aasx"

    def test_template_beats_example_and_sample(self):
        chosen = select_template_file(
            _files(
                "d/IDTA 02003_Sample_TechnicalData.aasx",
                "d/IDTA 02003_2-0-4_Template_TechnicalData.aasx",
                "d/IDTA 02003_Example.aasx",
            )
        )
        assert chosen.name == "IDTA 02003_2-0-4_Template_TechnicalData.aasx"

    def test_ties_keep_highest_name(self):
        chosen = select_template_file(_files("d/template_v1.aasx", "d/template_v2.aasx"))
        assert chosen.name == "template_v2.aasx"

    def test_no_aasx_means_no_selection(self):
        assert select_template_file(_files("d/readme.md")) is None
