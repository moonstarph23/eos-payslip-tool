import sys
from pathlib import Path

import pandas as pd


SIDECAR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIDECAR_DIR))

import worker4_standalone as worker


def test_encrypt_payslips_writes_manifest_with_bundled_excel_engine(tmp_path, monkeypatch):
    pdf_path = tmp_path / "Jane Doe.pdf"
    pdf_path.write_bytes(b"test pdf")

    hris_path = tmp_path / "hris.xlsx"
    employees = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "E001",
                "Date of birth": "01/02/2000",
                "Email (Work)": "jane@example.invalid",
                "Employment status": "Active",
            }
        ]
    )
    with pd.ExcelWriter(hris_path, engine="openpyxl") as writer:
        employees.to_excel(writer, index=False, startrow=7)

    monkeypatch.setattr(worker, "_encrypt_pdf", lambda *_args: True)

    result = worker.encrypt_payslips(tmp_path, "July 2026", hris_path)

    assert result["success"] is True
    manifest = pd.ExcelFile(result["output_excel"], engine="openpyxl")
    assert manifest.sheet_names == ["Payslips", "Status"]
    status = pd.read_excel(manifest, sheet_name="Status", dtype=str).fillna("")
    assert status.loc[0, "Status"] == "Successful"
    assert status.loc[0, "Password"] == "01022000"
