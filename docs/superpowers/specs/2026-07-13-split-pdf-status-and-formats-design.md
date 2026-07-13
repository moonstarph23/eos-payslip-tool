# Split PDF Status and Additional Formats Design

## Goal

Extend Split PDF without regressing existing payslip layouts by adding a per-page `Status` worksheet, text extraction for RJ Supply payslips, and offline OCR extraction for image-only Strideforth payslips.

## Inputs

- Existing text PDFs using `EMPLOYEE'S NAME` and current fallback layouts.
- RJ Supply text PDF represented by `Payslip June 2026.pdf` (15 pages).
- Strideforth image-only PDF represented by `Payslip employees All_Jun 2026.pdf` (39 pages, one embedded image per page).

Each source page remains one employee output PDF.

## Extraction Pipeline

1. Extract text with pdfminer and fall back to PyPDF2, unchanged.
2. Run the existing exact and relaxed `EMPLOYEE'S NAME` rules first.
3. If RJ Supply markers are present, extract the name immediately before its `Name` and `Dept.` boundary. This runs before the generic proximity fallback because the current fallback returns `Dept.<employee code> Emp. No.` for this layout.
4. Run the existing generic proximity fallback for other text PDFs.
5. When a page has no extractable text, render/extract its page image and run bundled RapidOCR offline.
6. Apply the Strideforth name rule only when OCR text contains Strideforth-specific markers. Extract the value adjacent to `Name` using OCR coordinates, with a flattened-text fallback.

OCR loads lazily only for image-only pages. Existing text PDFs do not pay OCR runtime cost and do not enter the new Strideforth path.

## Matching

Keep existing HRIS exact and token-overlap matching. For the new adapters, normalize whitespace and honorifics for comparison while retaining the extracted source name for logs and workbook output.

## Status Worksheet

`employee_payslips.xlsx` retains `Payslips` and conditional `Errors`, and always adds `Status` with one row per source page:

1. `Employee Number`
2. `EMPLOYEE'S NAME`
3. `Pay. Period`
4. `filename`
5. `email_address`
6. `Password`
7. `Status`

Statuses are `Successful`, `Failed - Could not extract name`, `Failed - Employee not found in HRIS`, and `Failed - No valid Date of birth`.

## Packaging

Pin the OCR and page-rendering dependencies in the sidecar requirements. Update PyInstaller collection so OCR models and native runtime libraries are bundled. No Tesseract installation, cloud service, internet connection, or API credentials are required at runtime.

## Verification

- Unit-test all existing extraction layers and both new format adapters.
- Unit-test one status row for every success/failure branch and workbook column order.
- Run candidate-name extraction against both supplied local PDFs and require 15/15 RJ Supply names and 39/39 Strideforth names.
- Run frontend and Rust build checks.
- Build and smoke-test the packaged Windows sidecar before publishing v1.0.6.
