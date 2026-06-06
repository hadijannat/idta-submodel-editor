from pathlib import Path

from openpyxl import Workbook

from app.services.mapper.parsers import DatasetReader


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(["Name", "Weight", "Active"])
    sheet.append(["Widget", 12.5, True])
    sheet.append(["Gadget", 7, False])

    summary = workbook.create_sheet("Summary")
    summary.append(["Total"])
    summary.append([2])

    workbook.save(path)


def test_dataset_reader_lists_xlsx_sheets(tmp_path: Path) -> None:
    workbook_path = tmp_path / "sample.xlsx"
    _write_workbook(workbook_path)

    reader = DatasetReader(workbook_path, file_type="xlsx")

    assert reader.list_sheets() == [
        ("Products", 3, 3),
        ("Summary", 2, 1),
    ]


def test_dataset_reader_reads_xlsx_rows_from_selected_sheet(tmp_path: Path) -> None:
    workbook_path = tmp_path / "sample.xlsx"
    _write_workbook(workbook_path)

    reader = DatasetReader(workbook_path, file_type="xlsx", sheet="Products")

    assert reader.read_rows(max_rows=3) == [
        ["Name", "Weight", "Active"],
        ["Widget", 12.5, True],
        ["Gadget", 7, False],
    ]
