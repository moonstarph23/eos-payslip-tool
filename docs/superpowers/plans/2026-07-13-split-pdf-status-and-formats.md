# Split PDF Status and Additional Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete per-page Status worksheet and support the supplied RJ Supply and image-only Strideforth combined PDFs without changing established PDF extraction behavior.

**Architecture:** Keep existing extraction rules first, insert a marker-gated RJ Supply adapter before the generic fallback, and lazily invoke a bundled OCR adapter only when normal text extraction is empty. Record status in the same branch that writes each output PDF, then package and publish the feature as v1.0.6.

**Tech Stack:** Python 3.12, PyPDF2, pdfminer.six, pandas/openpyxl, RapidOCR ONNX Runtime, pypdfium2, pytest, PyInstaller, Tauri 1, GitHub Actions/Releases.

---

### Task 1: Extraction Regression Tests

**Files:**
- Create: `src-tauri/sidecar/tests/test_worker_standalone.py`
- Modify: `src-tauri/sidecar/worker_standalone.py`

- [ ] Write failing tests for existing exact/relaxed/proximity inputs, RJ Supply text including a wrapped name, and Strideforth OCR-line coordinate selection.
- [ ] Run `python -m pytest src-tauri/sidecar/tests/test_worker_standalone.py -v` and confirm the RJ and Strideforth cases fail.
- [ ] Add marker-gated `_extract_rj_supply_name`, OCR result normalization, `_extract_strideforth_name`, and extraction orchestration. Keep L1/L2 before RJ and existing L3 after RJ.
- [ ] Run the focused tests and confirm all extraction cases pass.

### Task 2: Offline OCR Fallback

**Files:**
- Modify: `src-tauri/sidecar/worker_standalone.py`
- Modify: `src-tauri/sidecar/requirements.txt`
- Test: `src-tauri/sidecar/tests/test_worker_standalone.py`

- [ ] Add failing tests proving OCR is not called for text pages and is called once per image-only page through an injected/lazy OCR helper.
- [ ] Pin `rapidocr_onnxruntime`, `onnxruntime`, `pypdfium2`, and `Pillow` versions compatible with Python 3.12.
- [ ] Implement lazy OCR initialization, PDF page rendering at OCR-safe resolution, and Strideforth-only OCR extraction.
- [ ] Run focused tests, then run an extraction audit on the supplied files and require 15 RJ candidates and 39 Strideforth candidates.

### Task 3: Status Worksheet

**Files:**
- Modify: `src-tauri/sidecar/worker_standalone.py`
- Test: `src-tauri/sidecar/tests/test_worker_standalone.py`

- [ ] Add failing integration tests using temporary PDFs/HRIS workbooks for successful encryption, missing name, missing HRIS employee, and missing birthday.
- [ ] Build `status_rows` in each processing branch with columns `Employee Number`, `EMPLOYEE'S NAME`, `Pay. Period`, `filename`, `email_address`, `Password`, and `Status`.
- [ ] Always write `Status`; preserve `Payslips`, conditional `Errors`, output folders, counts, and sidecar payload.
- [ ] Run the focused tests and inspect the generated workbook sheet names, row count, statuses, and column order.

### Task 4: Sidecar Packaging

**Files:**
- Modify: `src-tauri/build-sidecar.bat`
- Modify: `src-tauri/build-sidecar.sh`
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/test.yml`

- [ ] Install sidecar requirements before PyInstaller in local and CI build paths.
- [ ] Collect RapidOCR model data, ONNX Runtime native libraries, pypdfium2 binaries, and dynamically imported worker modules.
- [ ] Build the Windows sidecar and run its `process_external` command against controlled test input.
- [ ] Add Python tests and sidecar dependency installation to CI before frontend/Tauri checks.

### Task 5: Version and Release

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `src-tauri/Cargo.toml`
- Modify: `src-tauri/tauri.conf.json`
- Modify: `src/components/tabs/SettingsTab.tsx`
- Verify: workflow-generated `latest.json` release metadata

- [ ] Set all application versions to `1.0.6` and update release notes for Status reporting, RJ Supply extraction, and offline Strideforth OCR.
- [ ] Run `python -m pytest src-tauri/sidecar/tests -v`, `npm run build`, and `cargo check --manifest-path src-tauri/Cargo.toml`.
- [ ] Build the Windows installer locally if signing credentials are available; otherwise use the signed GitHub release workflow.
- [ ] Review `git status`, `git diff`, and recent commits; commit only intended files.
- [ ] Push `master`, create and push tag `v1.0.6`, monitor GitHub Actions, publish the generated release, and verify `latest.json` plus the Windows installer assets are downloadable.
