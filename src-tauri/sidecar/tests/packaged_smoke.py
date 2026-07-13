"""Exercise OCR extraction through a packaged sidecar using synthetic data."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader


STATUS_COLUMNS = [
    "Employee Number",
    "EMPLOYEE'S NAME",
    "Pay. Period",
    "filename",
    "email_address",
    "Password",
    "Status",
]


def _font():
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), 32)
    raise RuntimeError("No supported smoke-test font was found")


def _write_image_pdf(path):
    image = Image.new("RGB", (612, 792), "white")
    draw = ImageDraw.Draw(image)
    font = _font()
    items = [
        ((50, 60), "STRIDEFORTH"),
        ((50, 140), "PAY"),
        ((230, 140), "SLIP"),
        ((50, 220), "Employee"),
        ((260, 220), "Code"),
        ((420, 220), "SF-0001"),
        ((50, 300), "Name"),
        ((220, 300), "Jane"),
        ((380, 300), "Doe"),
        ((50, 380), "Department"),
        ((300, 380), "Test"),
    ]
    for position, text in items:
        draw.text(position, text, fill="black", font=font)
    image.save(path, "PDF", resolution=72.0)


def _write_hris(path):
    employees = pd.DataFrame(
        [
            {
                "First name": "Jane",
                "Last name": "Doe",
                "System ID": "SF-0001",
                "Date of birth": "01/02/2000",
                "Email (Work)": "jane@example.invalid",
                "Employment status": "Active",
            }
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        employees.to_excel(writer, index=False, startrow=7)


def run_smoke(executable):
    executable = executable.resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"Packaged sidecar not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="payslip-sidecar-smoke-") as temp:
        root = Path(temp)
        pdf_path = root / "synthetic-image-payslip.pdf"
        hris_path = root / "synthetic-hris.xlsx"
        output_dir = root / "output"
        output_dir.mkdir()
        _write_image_pdf(pdf_path)
        _write_hris(hris_path)

        completed = subprocess.run(
            [
                str(executable),
                "process_external",
                "--pdf",
                str(pdf_path),
                "--employee-data",
                str(hris_path),
                "--output-folder",
                str(output_dir),
                "--period",
                "Smoke Test",
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Sidecar exited with {completed.returncode}: {completed.stderr}"
            )

        messages = []
        for line in completed.stdout.splitlines():
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        results = [message["data"] for message in messages if message.get("type") == "result"]
        if not results:
            raise AssertionError(f"Sidecar emitted no JSON result: {completed.stdout}")
        result = results[-1]
        assert result["success"] is True
        assert result["processed"] == 1
        assert result["errors"] == 0

        workbook_path = Path(result["output_excel"])
        assert workbook_path.resolve().is_relative_to(root.resolve())
        status = pd.read_excel(workbook_path, sheet_name="Status", dtype=str).fillna("")
        assert list(status.columns) == STATUS_COLUMNS
        assert status.to_dict("records") == [
            {
                "Employee Number": "SF-0001",
                "EMPLOYEE'S NAME": "JANE DOE",
                "Pay. Period": "Smoke Test",
                "filename": str(
                    output_dir
                    / "With Password"
                    / "Payslip - SF-0001, Smoke Test, Doe, Jane.pdf"
                ),
                "email_address": "jane@example.invalid",
                "Password": "01022000",
                "Status": "Successful",
            }
        ]

        encrypted_path = Path(status.loc[0, "filename"])
        assert encrypted_path.resolve().is_relative_to(root.resolve())
        encrypted_pdf = PdfReader(encrypted_path)
        assert encrypted_pdf.is_encrypted
        assert encrypted_pdf.decrypt("01022000")

    print("Packaged OCR smoke passed: processed=1, errors=0, encrypted=True")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True, type=Path)
    args = parser.parse_args()
    run_smoke(args.executable)


if __name__ == "__main__":
    main()
