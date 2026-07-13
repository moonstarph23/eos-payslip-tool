import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from PyPDF2 import PdfReader, PdfWriter


SIDECAR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIDECAR_DIR))

import worker_standalone as worker


def _ocr_item(text, left, top, right, bottom, score=0.99):
    return [
        [[left, top], [right, top], [right, bottom], [left, bottom]],
        text,
        score,
    ]


def _write_blank_pdf(path, page_count):
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)


def _write_hris_workbook(path):
    employees = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E001",
                "Date of birth": "01/02/2000",
                "Email (Work)": "jane@example.com",
                "Employment status": "Active",
            },
            {
                "First name": "No",
                "Last name": "Birthday",
                "System ID": "E002",
                "Date of birth": "",
                "Email (Personal)": "no.birthday@example.com",
                "Employment status": "Active",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        employees.to_excel(writer, index=False, startrow=7)


def test_extract_name_preserves_exact_l1_behavior():
    assert worker._extract_name("EMPLOYEE'S NAME\n\nJane Doe\n") == ("Jane Doe", "L1")


def test_extract_name_preserves_relaxed_l2_behavior():
    assert worker._extract_name("Employee Name: Jane Doe\n") == ("Jane Doe", "L2")


def test_extract_name_preserves_keyword_proximity_l3_behavior():
    assert worker._extract_name("EMPLOYEE ID\nJane Doe\n") == ("Jane Doe", "L3")


def test_extract_name_uses_rj_supply_rule_before_l3():
    text = (
        "RJ Supply and Service Co., Ltd.\n"
        "Overtime*3 timeOvertime*1 timeRateEarning:-MR.AKRAWIN WONGPANICH Name\n"
        "Dept.EO004 Emp. No."
    )

    assert worker._extract_name(text) == ("MR.AKRAWIN WONGPANICH", "RJ")


def test_extract_name_handles_wrapped_rj_supply_name():
    text = (
        "RJ Supply and Service Co., Ltd.\n"
        "RateEarning:-MRS.PAULINA STEFANIA \n"
        "PORAY-WILCZYNSKIName\n"
        "Dept.EO033 Emp. No."
    )

    assert worker._extract_name(text) == (
        "MRS.PAULINA STEFANIA PORAY-WILCZYNSKI",
        "RJ",
    )


def test_strideforth_name_uses_value_to_right_of_name_label():
    raw_result = [
        _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
        _ocr_item("PAY SLIP", 10, 40, 100, 60),
        _ocr_item("Employee Code", 10, 70, 130, 90),
        _ocr_item("SF-0042", 160, 70, 230, 90),
        _ocr_item("Name", 10, 100, 60, 120),
        _ocr_item("Jane Alexandra Doe", 100, 100, 270, 120),
    ]

    lines = worker._normalize_ocr_lines((raw_result, 0.25))

    assert worker._extract_strideforth_name(lines) == "Jane Alexandra Doe"


def test_normalize_ocr_lines_preserves_confidence():
    lines = worker._normalize_ocr_lines([_ocr_item("Jane Doe", 10, 10, 90, 30, 0.73)])

    assert lines[0]["confidence"] == 0.73


def test_strideforth_name_concatenates_split_name_boxes():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Jane", 100, 100, 140, 120),
            _ocr_item("Alexandra", 145, 100, 220, 120),
            _ocr_item("Doe", 225, 100, 260, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) == "Jane Alexandra Doe"


def test_strideforth_name_stops_before_adjacent_field():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Jane", 100, 100, 140, 120),
            _ocr_item("Doe", 145, 100, 180, 120),
            _ocr_item("Department", 240, 100, 330, 120),
            _ocr_item("Finance", 350, 100, 410, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) == "Jane Doe"


def test_strideforth_name_rejects_low_confidence_candidate():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Jane", 100, 100, 140, 120),
            _ocr_item("Doe", 145, 100, 180, 120, score=0.31),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_strideforth_name_allows_high_confidence_merged_token():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("WanwisaPraditmon", 100, 100, 230, 120),
            _ocr_item("YTD Tax Income", 300, 100, 420, 120),
            _ocr_item("639,368.52", 500, 100, 580, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) == "WanwisaPraditmon"


def test_strideforth_name_rejects_low_confidence_merged_token():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("WanwisaPraditmon", 100, 100, 230, 120, score=0.31),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_strideforth_name_rejects_invalid_candidate():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("12345", 100, 100, 160, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_strideforth_name_rejects_numeric_fragment_in_candidate():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Jane 123 Doe", 100, 100, 200, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_strideforth_name_has_flattened_line_fallback():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code SF-0042", 10, 70, 220, 90),
            _ocr_item("Name Jane Alexandra Doe Department", 10, 100, 330, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) == "Jane Alexandra Doe"


def test_flattened_name_rejects_low_confidence_box_inside_value_region():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code SF-0042", 10, 70, 220, 90),
            _ocr_item("Name Jane", 10, 100, 90, 120),
            _ocr_item("Alexandra", 95, 100, 170, 120, score=0.31),
            _ocr_item("Doe", 175, 100, 210, 120),
            _ocr_item("Department", 240, 100, 330, 120),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_flattened_name_ignores_low_confidence_box_after_field_boundary():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code SF-0042", 10, 70, 220, 90),
            _ocr_item("Name Jane", 10, 100, 90, 120),
            _ocr_item("Doe", 95, 100, 130, 120),
            _ocr_item("Department", 240, 100, 330, 120),
            _ocr_item("Finance", 350, 100, 410, 120, score=0.31),
        ]
    )

    assert worker._extract_strideforth_name(lines) == "Jane Doe"


def test_strideforth_name_uses_immediately_following_ocr_row():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Jane Doe", 100, 130, 180, 150),
            _ocr_item("Position", 10, 160, 80, 180),
        ]
    )

    assert worker._extract_strideforth_name(lines) == "Jane Doe"


def test_strideforth_name_rejects_low_confidence_following_row():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Jane Doe", 100, 130, 180, 150, score=0.31),
            _ocr_item("Position", 10, 160, 80, 180),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_strideforth_name_does_not_take_next_field_as_cross_row_name():
    lines = worker._normalize_ocr_lines(
        [
            _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
            _ocr_item("PAY SLIP", 10, 40, 100, 60),
            _ocr_item("Employee Code", 10, 70, 130, 90),
            _ocr_item("Name", 10, 100, 60, 120),
            _ocr_item("Position", 10, 130, 80, 150),
            _ocr_item("Sales Manager", 100, 130, 220, 150),
        ]
    )

    assert worker._extract_strideforth_name(lines) is None


def test_ocr_matching_rejects_ambiguous_duplicate_first_name():
    hris_names = ["JANE DOE", "JANE SMITH"]

    assert worker._match_hris_name("JANE", hris_names, is_ocr=True) is None


def test_ocr_matching_rejects_tracked_duplicate_full_name():
    assert worker._match_hris_name(
        "JANE DOE",
        ["JANE DOE"],
        is_ocr=True,
        duplicate_hris_names={"JANE DOE"},
    ) is None


def test_ocr_matching_accepts_unique_exact_compact_merged_name():
    assert worker._match_hris_name(
        "WANWISAPRADITMON",
        ["WANWISA PRADITMON", "JANE DOE"],
        is_ocr=True,
    ) == "WANWISA PRADITMON"


def test_ocr_matching_rejects_ambiguous_exact_compact_merged_name():
    assert worker._match_hris_name(
        "WANWISAPRADITMON",
        ["WANWISA PRADITMON", "WAN WISA PRADITMON"],
        is_ocr=True,
    ) is None


def test_ocr_matching_rejects_partial_merged_name():
    assert worker._match_hris_name(
        "WANWISA",
        ["WANWISA PRADITMON"],
        is_ocr=True,
    ) is None


def test_rj_matching_does_not_use_legacy_half_overlap():
    assert worker._match_hris_name(
        "MR.JOHN SMITH",
        ["JANE SMITH", "JOHN SMITH"],
        is_rj=True,
    ) == "JOHN SMITH"


def test_rj_matching_rejects_normalized_ambiguity():
    assert worker._match_hris_name(
        "MR.JOHN SMITH",
        ["JOHN SMITH", "MR JOHN SMITH"],
        is_rj=True,
    ) is None


def test_rj_matching_rejects_tracked_duplicate_full_name():
    assert worker._match_hris_name(
        "MR.JOHN SMITH",
        ["JOHN SMITH"],
        is_rj=True,
        duplicate_hris_names={"JOHN SMITH"},
    ) is None


def test_text_matching_keeps_first_legacy_overlap_match():
    hris_names = ["JANE DOE", "JANE SMITH"]

    assert worker._match_hris_name("JANE", hris_names, is_ocr=False) == "JANE DOE"


def test_legacy_matching_rejects_duplicate_exact_name():
    assert worker._match_hris_name(
        "JANE DOE",
        ["JANE DOE"],
        duplicate_hris_names={"JANE DOE"},
    ) is None


def test_legacy_matching_rejects_duplicate_overlap_name():
    assert worker._match_hris_name(
        "JANE",
        ["JANE DOE"],
        duplicate_hris_names={"JANE DOE"},
    ) is None


def test_page_name_does_not_call_ocr_when_normal_text_exists(monkeypatch):
    monkeypatch.setattr(
        worker,
        "_extract_page_text",
        lambda file_path, page_num, pdf_reader: "Employee Name: Jane Doe\n",
    )
    ocr_calls = []

    result = worker._extract_page_name(
        "payslips.pdf",
        0,
        object(),
        ocr_page=lambda file_path, page_num: ocr_calls.append((file_path, page_num)),
    )

    assert result == ("Jane Doe", "L2")
    assert ocr_calls == []


def test_page_name_calls_ocr_once_for_an_image_only_page(monkeypatch):
    monkeypatch.setattr(
        worker,
        "_extract_page_text",
        lambda file_path, page_num, pdf_reader: "",
    )
    ocr_calls = []
    raw_result = [
        _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
        _ocr_item("PAY SLIP", 10, 40, 100, 60),
        _ocr_item("Employee Code", 10, 70, 130, 90),
        _ocr_item("Name", 10, 100, 60, 120),
        _ocr_item("Jane Doe", 100, 100, 180, 120),
    ]

    def fake_ocr(file_path, page_num):
        ocr_calls.append((file_path, page_num))
        return raw_result

    result = worker._extract_page_name(
        "payslips.pdf", 12, object(), ocr_page=fake_ocr
    )

    assert result == ("Jane Doe", "OCR")
    assert ocr_calls == [("payslips.pdf", 12)]


def test_page_name_contains_ocr_failure(monkeypatch):
    monkeypatch.setattr(
        worker,
        "_extract_page_text",
        lambda file_path, page_num, pdf_reader: "",
    )

    def failed_ocr(file_path, page_num):
        raise RuntimeError("inference failed")

    assert worker._extract_page_name(
        "payslips.pdf", 0, object(), ocr_page=failed_ocr
    ) == (None, None)


def test_page_name_contains_malformed_ocr_confidence(monkeypatch):
    monkeypatch.setattr(
        worker,
        "_extract_page_text",
        lambda file_path, page_num, pdf_reader: "",
    )
    malformed_result = [_ocr_item("STRIDEFORTH", 10, 10, 130, 30, "invalid")]

    assert worker._extract_page_name(
        "payslips.pdf",
        0,
        object(),
        ocr_page=lambda file_path, page_num: malformed_result,
    ) == (None, None)


def test_page_name_contains_strideforth_post_processing_failure(monkeypatch):
    monkeypatch.setattr(
        worker,
        "_extract_page_text",
        lambda file_path, page_num, pdf_reader: "",
    )
    monkeypatch.setattr(
        worker,
        "_extract_strideforth_name",
        lambda lines: (_ for _ in ()).throw(RuntimeError("selection failed")),
    )

    assert worker._extract_page_name(
        "payslips.pdf",
        0,
        object(),
        ocr_page=lambda file_path, page_num: [],
    ) == (None, None)


def test_ocr_reader_reuses_document_and_closes_page_resources():
    documents = []

    class FakeBitmap:
        def __init__(self):
            self.closed = False

        def to_pil(self):
            return [[0]]

        def close(self):
            self.closed = True

    class FakePage:
        def __init__(self):
            self.bitmap = FakeBitmap()
            self.closed = False

        def render(self, scale):
            assert scale == 300 / 72
            return self.bitmap

        def close(self):
            self.closed = True

    class FakeDocument:
        def __init__(self, file_path):
            self.file_path = file_path
            self.pages = [FakePage(), FakePage()]
            self.closed = False
            documents.append(self)

        def __getitem__(self, page_num):
            return self.pages[page_num]

        def close(self):
            self.closed = True

    reader = worker._OcrPageReader(
        "payslips.pdf",
        pdf_document_factory=FakeDocument,
        ocr_engine=lambda image: ([], 0.1),
    )

    reader("payslips.pdf", 0)
    reader("payslips.pdf", 1)
    reader.close()

    assert len(documents) == 1
    assert documents[0].closed is True
    assert all(page.closed and page.bitmap.closed for page in documents[0].pages)


def test_process_external_caches_ocr_init_failure_and_emits_one_diagnostic(
    monkeypatch, tmp_path
):
    real_read_excel = pd.read_excel
    engine_attempts = []
    document_attempts = []
    raw_pages = []
    updates = []

    class FakePage:
        def extract_text(self):
            return ""

    class FakePdfReader:
        pages = [FakePage(), FakePage(), FakePage()]

    def fail_engine_init():
        engine_attempts.append(True)
        raise RuntimeError("ONNX runtime unavailable")

    def unexpected_document_open(file_path):
        document_attempts.append(file_path)
        raise AssertionError("rendering must not start after OCR init failure")

    ocr_reader = worker._OcrPageReader(
        "payslips.pdf",
        pdf_document_factory=unexpected_document_open,
        ocr_engine_factory=fail_engine_init,
    )
    monkeypatch.setattr(worker, "PdfReader", lambda file_path: FakePdfReader())
    monkeypatch.setattr(worker, "_OcrPageReader", lambda file_path: ocr_reader)
    monkeypatch.setattr(worker, "extract_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(
        worker,
        "_save_raw_page",
        lambda pdf_reader, page_num, filepath: raw_pages.append(page_num),
    )

    result = worker.process_external(
        "payslips.pdf",
        str(tmp_path),
        "employees.xlsx",
        "June 2026",
        on_update=updates.append,
    )

    diagnostics = [message for message in updates if "OCR unavailable" in message]
    status = real_read_excel(result["output_excel"], sheet_name="Status", dtype=str)
    assert engine_attempts == [True]
    assert document_attempts == []
    assert raw_pages == [0, 1, 2]
    assert result["errors"] == 3
    assert len(diagnostics) == 1
    assert "ONNX runtime unavailable" in diagnostics[0]
    assert status["Status"].tolist() == [
        "Failed - Could not extract name",
        "Failed - Could not extract name",
        "Failed - Could not extract name",
    ]


def test_process_external_continues_after_malformed_ocr_and_closes_reader(
    monkeypatch, tmp_path
):
    instances = []
    raw_pages = []
    encrypted_pages = []

    class FakePdfReader:
        pages = [object(), object()]

    class FakeOcrReader:
        def __init__(self, file_path):
            self.calls = []
            self.closed = False
            instances.append(self)

        def __call__(self, file_path, page_num):
            self.calls.append(page_num)
            if page_num == 0:
                return [_ocr_item("STRIDEFORTH", 10, 10, 130, 30, "invalid")]
            return [
                _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
                _ocr_item("PAY SLIP", 10, 40, 100, 60),
                _ocr_item("Employee Code", 10, 70, 130, 90),
                _ocr_item("Name", 10, 100, 60, 120),
                _ocr_item("Jane", 100, 100, 140, 120),
                _ocr_item("Doe", 145, 100, 180, 120),
            ]

        def close(self):
            self.closed = True

    employee_df = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E001",
                "Date of birth": "01/02/2000",
                "Email (Work)": "jane@example.com",
                "Employment status": "Active",
            }
        ]
    )
    monkeypatch.setattr(worker, "PdfReader", lambda file_path: FakePdfReader())
    monkeypatch.setattr(worker, "_OcrPageReader", FakeOcrReader)
    monkeypatch.setattr(worker, "extract_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: employee_df)
    monkeypatch.setattr(
        worker,
        "_save_raw_page",
        lambda pdf_reader, page_num, filepath: raw_pages.append(page_num),
    )
    monkeypatch.setattr(
        worker,
        "_save_encrypted_page",
        lambda pdf_reader, page_num, password, filepath: encrypted_pages.append(page_num),
    )

    result = worker.process_external(
        "payslips.pdf", str(tmp_path), "employees.xlsx", "June 2026"
    )

    assert result["processed"] == 1
    assert result["errors"] == 1
    assert raw_pages == [0]
    assert encrypted_pages == [1]
    assert instances[0].calls == [0, 1]
    assert instances[0].closed is True


def test_process_external_rejects_duplicate_ocr_full_name_without_encryption(
    monkeypatch, tmp_path
):
    raw_pages = []
    encrypted_pages = []

    class FakePdfReader:
        pages = [object()]

    class FakeOcrReader:
        def __init__(self, file_path):
            pass

        def __call__(self, file_path, page_num):
            return [
                _ocr_item("STRIDEFORTH", 10, 10, 130, 30),
                _ocr_item("PAY SLIP", 10, 40, 100, 60),
                _ocr_item("Employee Code", 10, 70, 130, 90),
                _ocr_item("Name", 10, 100, 60, 120),
                _ocr_item("Jane", 100, 100, 140, 120),
                _ocr_item("Doe", 145, 100, 180, 120),
            ]

        def close(self):
            pass

    employee_df = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E001",
                "Date of birth": "01/02/2000",
                "Employment status": "Active",
            },
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E999",
                "Date of birth": "12/31/1999",
                "Employment status": "Active",
            },
        ]
    )
    monkeypatch.setattr(worker, "PdfReader", lambda file_path: FakePdfReader())
    monkeypatch.setattr(worker, "_OcrPageReader", FakeOcrReader)
    monkeypatch.setattr(worker, "extract_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: employee_df)
    monkeypatch.setattr(
        worker,
        "_save_raw_page",
        lambda pdf_reader, page_num, filepath: raw_pages.append(page_num),
    )
    monkeypatch.setattr(
        worker,
        "_save_encrypted_page",
        lambda pdf_reader, page_num, password, filepath: encrypted_pages.append(
            (page_num, password)
        ),
    )

    result = worker.process_external(
        "payslips.pdf", str(tmp_path), "employees.xlsx", "June 2026"
    )

    assert result["processed"] == 0
    assert result["errors"] == 1
    assert raw_pages == [0]
    assert encrypted_pages == []


def test_process_external_rejects_duplicate_legacy_name_without_password(
    monkeypatch, tmp_path
):
    real_read_excel = pd.read_excel
    raw_pages = []
    encrypted_passwords = []

    class FakePdfReader:
        pages = [object()]

    class FakeOcrReader:
        def __init__(self, file_path):
            pass

        def close(self):
            pass

    employee_df = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E001",
                "Date of birth": "01/02/2000",
                "Employment status": "Active",
            },
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E999",
                "Date of birth": "12/31/1999",
                "Employment status": "Active",
            },
        ]
    )
    monkeypatch.setattr(worker, "PdfReader", lambda file_path: FakePdfReader())
    monkeypatch.setattr(worker, "_OcrPageReader", FakeOcrReader)
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: employee_df)
    monkeypatch.setattr(
        worker,
        "_extract_page_name",
        lambda *args, **kwargs: ("Jane Doe", "L2"),
    )
    monkeypatch.setattr(
        worker,
        "_save_raw_page",
        lambda pdf_reader, page_num, filepath: raw_pages.append(page_num),
    )
    monkeypatch.setattr(
        worker,
        "_save_encrypted_page",
        lambda pdf_reader, page_num, password, filepath: encrypted_passwords.append(
            password
        ),
    )

    result = worker.process_external(
        "payslips.pdf", str(tmp_path), "employees.xlsx", "June 2026"
    )

    errors = real_read_excel(result["output_excel"], sheet_name="Errors")
    status = real_read_excel(
        result["output_excel"], sheet_name="Status", dtype=str
    ).fillna("")
    assert result["processed"] == 0
    assert result["errors"] == 1
    assert raw_pages == [0]
    assert encrypted_passwords == []
    assert errors.loc[0, "Error"] == "Employee not found in HRIS"
    assert status.loc[0, "Password"] == ""
    assert status.loc[0, "Status"] == "Failed - Employee not found in HRIS"


def test_process_external_uses_strict_rj_match_instead_of_first_overlap(
    monkeypatch, tmp_path
):
    encrypted_passwords = []

    class FakePdfReader:
        pages = [object()]

    class FakeOcrReader:
        def __init__(self, file_path):
            pass

        def close(self):
            pass

    employee_df = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Smith",
                "System ID": "E001",
                "Date of birth": "01/02/2000",
                "Employment status": "Active",
            },
            {
                "First name": "John",
                "Last name": "Smith",
                "System ID": "E002",
                "Date of birth": "12/31/1999",
                "Employment status": "Active",
            },
        ]
    )
    monkeypatch.setattr(worker, "PdfReader", lambda file_path: FakePdfReader())
    monkeypatch.setattr(worker, "_OcrPageReader", FakeOcrReader)
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: employee_df)
    monkeypatch.setattr(
        worker,
        "_extract_page_name",
        lambda *args, **kwargs: ("MR.JOHN SMITH", "RJ"),
    )
    monkeypatch.setattr(
        worker,
        "_save_encrypted_page",
        lambda pdf_reader, page_num, password, filepath: encrypted_passwords.append(
            password
        ),
    )

    result = worker.process_external(
        "payslips.pdf", str(tmp_path), "employees.xlsx", "June 2026"
    )

    assert result["processed"] == 1
    assert encrypted_passwords == ["12311999"]


def test_process_external_closes_ocr_reader_when_processing_raises(
    monkeypatch, tmp_path
):
    instances = []

    class OwnedStream:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class FakePdfReader:
        pages = [object()]

        def __init__(self):
            self.stream = OwnedStream()

    class FakeOcrReader:
        def __init__(self, file_path):
            self.closed = False
            instances.append(self)

        def close(self):
            self.closed = True

    pdf_reader = FakePdfReader()
    monkeypatch.setattr(worker, "PdfReader", lambda file_path: pdf_reader)
    monkeypatch.setattr(worker, "_OcrPageReader", FakeOcrReader)
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(
        worker,
        "_extract_page_name",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("processing failed")),
    )

    with pytest.raises(RuntimeError, match="processing failed"):
        worker.process_external(
            "payslips.pdf", str(tmp_path), "employees.xlsx", "June 2026"
        )

    assert instances[0].closed is True
    assert pdf_reader.stream.closed is True


def test_process_external_does_not_close_caller_owned_pdf_stream(
    monkeypatch, tmp_path
):
    source = BytesIO(b"caller-owned")

    class FakePdfReader:
        pages = [object()]

        def __init__(self, stream):
            self.stream = stream

    class FakeOcrReader:
        def __init__(self, file_path):
            pass

        def close(self):
            pass

    monkeypatch.setattr(worker, "PdfReader", FakePdfReader)
    monkeypatch.setattr(worker, "_OcrPageReader", FakeOcrReader)
    monkeypatch.setattr(worker.pd, "read_excel", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(
        worker,
        "_extract_page_name",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("processing failed")),
    )

    with pytest.raises(RuntimeError, match="processing failed"):
        worker.process_external(
            source, str(tmp_path), "employees.xlsx", "June 2026"
        )

    assert source.closed is False


def test_process_external_writes_status_row_for_every_source_page(
    monkeypatch, tmp_path
):
    source_pdf = tmp_path / "source.pdf"
    hris_workbook = tmp_path / "employees.xlsx"
    output_folder = tmp_path / "output"
    _write_blank_pdf(source_pdf, 4)
    _write_hris_workbook(hris_workbook)

    page_text = {
        0: "Employee Name: Jane Doe\n",
        2: "Employee Name: Missing Person\n",
        3: "Employee Name: No Birthday\n",
    }
    monkeypatch.setattr(
        worker,
        "_extract_page_text",
        lambda file_path, page_num, pdf_reader: page_text.get(page_num, ""),
    )

    class FailingOcrReader:
        def __init__(self, file_path):
            self.closed = False

        def __call__(self, file_path, page_num):
            raise RuntimeError("OCR source could not be read")

        def close(self):
            self.closed = True

    monkeypatch.setattr(worker, "_OcrPageReader", FailingOcrReader)

    result = worker.process_external(
        source_pdf, output_folder, hris_workbook, "June 2026"
    )

    expected_payload = {
        "success": True,
        "processed": 1,
        "errors": 3,
        "output_excel": str(output_folder / "employee_payslips.xlsx"),
    }
    assert result == expected_payload

    workbook = pd.ExcelFile(result["output_excel"])
    assert workbook.sheet_names == ["Payslips", "Errors", "Status"]

    status = pd.read_excel(
        result["output_excel"], sheet_name="Status", dtype=str
    ).fillna("")
    assert list(status.columns) == [
        "Employee Number",
        "EMPLOYEE'S NAME",
        "Pay. Period",
        "filename",
        "email_address",
        "Password",
        "Status",
    ]
    assert len(status) == 4
    assert status.to_dict("records") == [
        {
            "Employee Number": "E001",
            "EMPLOYEE'S NAME": "JANE DOE",
            "Pay. Period": "June 2026",
            "filename": str(
                output_folder
                / "With Password"
                / "Payslip - E001, June 2026, Doe, Jane.pdf"
            ),
            "email_address": "jane@example.com",
            "Password": "01022000",
            "Status": "Successful",
        },
        {
            "Employee Number": "",
            "EMPLOYEE'S NAME": "Unknown",
            "Pay. Period": "June 2026",
            "filename": str(
                output_folder
                / "No Password"
                / "Payslip - June 2026, Page 2.pdf"
            ),
            "email_address": "",
            "Password": "",
            "Status": "Failed - Could not extract name",
        },
        {
            "Employee Number": "",
            "EMPLOYEE'S NAME": "MISSING PERSON",
            "Pay. Period": "June 2026",
            "filename": str(
                output_folder
                / "No Password"
                / "Payslip - June 2026, Missing Person.pdf"
            ),
            "email_address": "",
            "Password": "",
            "Status": "Failed - Employee not found in HRIS",
        },
        {
            "Employee Number": "E002",
            "EMPLOYEE'S NAME": "NO BIRTHDAY",
            "Pay. Period": "June 2026",
            "filename": str(
                output_folder
                / "No Password"
                / "Payslip - June 2026, No Birthday.pdf"
            ),
            "email_address": "no.birthday@example.com",
            "Password": "",
            "Status": "Failed - No valid Date of birth",
        },
    ]

    payslips = pd.read_excel(result["output_excel"], sheet_name="Payslips")
    errors = pd.read_excel(result["output_excel"], sheet_name="Errors")
    assert len(payslips) == 1
    assert len(errors) == 3

    encrypted_pdf = PdfReader(status.iloc[0]["filename"])
    assert encrypted_pdf.is_encrypted
    assert encrypted_pdf.decrypt("01022000")
    for filepath in status.iloc[1:]["filename"]:
        raw_pdf = PdfReader(filepath)
        assert raw_pdf.is_encrypted is False
