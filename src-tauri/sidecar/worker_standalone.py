"""
Worker Standalone - External PDF Processing
Qt-free version for CLI/sidecar use.
No PyQt dependencies.

Splits a combined multi-page PDF into individual encrypted PDFs.
Extracts only employee name from each page (pay period is user-provided).
Matches against HRIS data and encrypts with birthday password (MMDDYYYY).

Output structure:
  output_folder/
  ├── employee_payslips.xlsx   (manifest)
  ├── With Password/            (encrypted PDFs — matched + valid birthday)
  └── No Password/              (raw pages — no match / no birthday / no name)
"""

from PyPDF2 import PdfReader, PdfWriter
from pdfminer.high_level import extract_text
import pandas as pd
import os
import re
from datetime import datetime


_OCR_ENGINE = None
_OCR_MIN_CONFIDENCE = 0.5
_OCR_FIELD_LABELS = (
    "Department",
    "Position",
    "Start Date",
    "Employee Code",
    "YTD Tax Income",
    "Date Joined",
    "Pay Period",
    "Basic Salary",
)


def _strip_cjk(text):
    """Remove CJK characters from text so Chinese labels don't corrupt name extraction."""
    return re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]+', '', text)


def _extract_page_text(file_path, page_num, pdf_reader):
    """Extract text from a single PDF page with fallback methods.

    Tries pdfminer first (best quality). Falls back to PyPDF2 if pdfminer
    crashes on malformed objects (e.g. 'PDFObjRef' is not iterable).
    """
    try:
        text = extract_text(file_path, page_numbers=[page_num])
        if text and text.strip():
            return text.strip()
    except Exception:
        pass

    try:
        text = pdf_reader.pages[page_num].extract_text()
        if text and text.strip():
            return text.strip()
    except Exception:
        pass

    return ""


def _extract_rj_supply_name(page_text):
    """Extract the name from an RJ Supply payslip's earning/name boundary."""
    if not re.search(r'RJ Supply and Service Co\., Ltd\.', page_text, re.IGNORECASE):
        return None

    match = re.search(
        r'Earning\s*:\s*-\s*(.+?)\s*Name\s*\n\s*Dept\.',
        page_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    return re.sub(r'\s+', ' ', match.group(1)).strip()


def _extract_name(page_text):
    """Extract employee name from page text with fallback layers.

    Strip CJK characters first, then try four layers:
      L1 - Exact:       EMPLOYEE'S NAME\\n\\nName\\n
      L2 - Relaxed:     handles spacing, punctuation, case variations
      RJ - RJ Supply:   marker-gated earning/name boundary extraction
      L3 - Keyword proximity:  finds "NAME"/"EMPLOYEE" token, takes next non-empty line

    Returns:
        (name, layer) tuple, or (None, None) if all layers fail.
    """
    cleaned = _strip_cjk(page_text)

    # L1: Exact match
    m = re.search(r"EMPLOYEE'S NAME\n\n(.+?)\n", cleaned)
    if m:
        return m.group(1).strip(), "L1"

    # L2: Relaxed — handle EMPLOYEE NAME:, EMPLOYEE'S NAME:, Employee Name, etc.
    m = re.search(r"EMPLOYEE'?S?\s*NAME\s*[:\-]?\s*(.+?)(?:\n|$)", cleaned, re.IGNORECASE)
    if m:
        return m.group(1).strip(), "L2"

    rj_name = _extract_rj_supply_name(cleaned)
    if rj_name:
        return rj_name, "RJ"

    # L3: Keyword proximity — find line with NAME/EMPLOYEE, take next non-empty line
    lines = cleaned.split('\n')
    for i, line in enumerate(lines):
        if re.search(r'\b(?:EMPLOYEE|NAME)\b', line, re.IGNORECASE) and i + 1 < len(lines):
            candidate = lines[i + 1].strip()
            if candidate and not re.match(r'^[\d\s\-/,.:]+$', candidate) and len(candidate) > 2:
                return candidate, "L3"

    return None, None


def _normalize_ocr_lines(ocr_result):
    """Convert RapidOCR output into sorted text boxes for focused selection tests."""
    if isinstance(ocr_result, tuple):
        ocr_result = ocr_result[0]

    lines = []
    for item in ocr_result or []:
        if not item or len(item) < 2 or not item[1]:
            continue
        box = item[0]
        if not box or len(box) < 4:
            continue
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        lines.append({
            "text": re.sub(r'\s+', ' ', str(item[1])).strip(),
            "confidence": float(item[2]) if len(item) > 2 else 0.0,
            "left": min(xs),
            "right": max(xs),
            "top": min(ys),
            "bottom": max(ys),
        })

    return sorted(lines, key=lambda line: (line["top"], line["left"]))


def _extract_strideforth_name(lines):
    """Select the Strideforth name beside its label, then try flattened OCR text."""
    reliable_lines = [
        line for line in lines if line["confidence"] >= _OCR_MIN_CONFIDENCE
    ]
    flattened = ' '.join(line["text"] for line in reliable_lines)
    markers = flattened.upper()
    if not all(marker in markers for marker in ("STRIDEFORTH", "PAY SLIP", "EMPLOYEE CODE")):
        return None

    for label in lines:
        if (
            label["confidence"] < _OCR_MIN_CONFIDENCE
            or not re.fullmatch(r'Name\s*:?', label["text"], re.IGNORECASE)
        ):
            continue
        label_center = (label["top"] + label["bottom"]) / 2
        label_height = label["bottom"] - label["top"]
        same_row = []
        for line in lines:
            line_center = (line["top"] + line["bottom"]) / 2
            line_height = line["bottom"] - line["top"]
            if abs(line_center - label_center) <= max(label_height, line_height) / 2:
                same_row.append(line)

        boundaries = [
            line for line in same_row
            if line["left"] >= label["right"]
            and any(
                re.fullmatch(rf'{re.escape(field)}\s*:?', line["text"], re.IGNORECASE)
                for field in _OCR_FIELD_LABELS
            )
        ]
        right_boundary = min(
            (line["left"] for line in boundaries),
            default=float("inf"),
        )
        candidates = sorted(
            (
                line for line in same_row
                if label["right"] <= line["left"] < right_boundary
            ),
            key=lambda line: line["left"],
        )
        if candidates:
            if any(line["confidence"] < _OCR_MIN_CONFIDENCE for line in candidates):
                return None
            candidate = ' '.join(line["text"] for line in candidates)
            return candidate if _is_valid_ocr_name(candidate, allow_single=True) else None

        following_lines = [
            line for line in lines if line["top"] >= label["bottom"]
        ]
        if not following_lines:
            continue
        first_next = min(following_lines, key=lambda line: (line["top"], line["left"]))
        next_center = (first_next["top"] + first_next["bottom"]) / 2
        next_height = first_next["bottom"] - first_next["top"]
        next_row = []
        for line in following_lines:
            line_center = (line["top"] + line["bottom"]) / 2
            line_height = line["bottom"] - line["top"]
            if abs(line_center - next_center) <= max(next_height, line_height) / 2:
                next_row.append(line)

        next_boundaries = [line for line in next_row if _is_ocr_field_label(line["text"])]
        right_boundary = min(
            (line["left"] for line in next_boundaries),
            default=float("inf"),
        )
        candidates = sorted(
            (
                line for line in next_row
                if label["right"] <= line["left"] < right_boundary
            ),
            key=lambda line: line["left"],
        )
        if candidates:
            if any(line["confidence"] < _OCR_MIN_CONFIDENCE for line in candidates):
                return None
            candidate = ' '.join(line["text"] for line in candidates)
            return candidate if _is_valid_ocr_name(candidate, allow_single=True) else None
        if next_boundaries:
            return None

    for anchor in lines:
        if (
            anchor["confidence"] < _OCR_MIN_CONFIDENCE
            or not re.search(r'\bName\s*:?\s+\S', anchor["text"], re.IGNORECASE)
        ):
            continue
        anchor_center = (anchor["top"] + anchor["bottom"]) / 2
        anchor_height = anchor["bottom"] - anchor["top"]
        same_row = []
        for line in lines:
            line_center = (line["top"] + line["bottom"]) / 2
            line_height = line["bottom"] - line["top"]
            if abs(line_center - anchor_center) <= max(anchor_height, line_height) / 2:
                same_row.append(line)

        boundaries = [
            line for line in same_row
            if line["left"] >= anchor["right"]
            and any(
                re.fullmatch(rf'{re.escape(field)}\s*:?', line["text"], re.IGNORECASE)
                for field in _OCR_FIELD_LABELS
            )
        ]
        right_boundary = min(
            (line["left"] for line in boundaries),
            default=float("inf"),
        )
        value_region = sorted(
            (
                line for line in same_row
                if line is anchor
                or anchor["right"] <= line["left"] < right_boundary
            ),
            key=lambda line: line["left"],
        )
        if any(line["confidence"] < _OCR_MIN_CONFIDENCE for line in value_region):
            return None

        match = re.search(
            r'\bName\s*:?\s+(.+?)(?=\s+(?:Department|Position|Employee\s+Code|'
            r'Date\s+Joined|Pay\s+Period|Basic\s+Salary)\b|$)',
            ' '.join(line["text"] for line in value_region),
            re.IGNORECASE,
        )
        if match:
            candidate = match.group(1).strip()
            return candidate if _is_valid_ocr_name(candidate, allow_single=True) else None

    return None


def _is_ocr_field_label(text):
    """Identify labels that bound a Strideforth name value region."""
    if text.upper().startswith("YTD "):
        return True
    return any(
        re.fullmatch(rf'{re.escape(field)}\s*:?', text, re.IGNORECASE)
        for field in _OCR_FIELD_LABELS
    )


def _normalized_name_parts(name):
    """Return uppercase alphabetic name parts without honorifics."""
    honorifics = {"MR", "MRS", "MS", "MISS", "DR"}
    return [
        part.upper()
        for part in re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", name, re.UNICODE)
        if part.upper() not in honorifics
    ]


def _compact_name(name):
    """Normalize a name for exact merged-token comparison."""
    return ''.join(_normalized_name_parts(name))


def _is_valid_ocr_name(candidate, allow_single=False):
    """Require a plausible alphabetic name from OCR."""
    if (
        any(char.isdigit() or char == "_" for char in candidate)
        or re.search(r'[^\w\s.\'\-(),]', candidate, re.UNICODE)
    ):
        return False
    parts = _normalized_name_parts(candidate)
    if len(parts) >= 2:
        return True
    return allow_single and len(parts) == 1 and len(parts[0]) >= 6


def _match_hris_name(
    name_upper, hris_names, is_ocr=False, is_rj=False, duplicate_hris_names=None
):
    """Match OCR names conservatively while preserving legacy text matching."""
    duplicate_hris_names = duplicate_hris_names or set()
    if is_rj:
        name_parts = _normalized_name_parts(name_upper)
        candidates = [
            hris_name for hris_name in hris_names
            if _normalized_name_parts(hris_name) == name_parts
        ]
        if len(candidates) == 1 and candidates[0] not in duplicate_hris_names:
            return candidates[0]
        return None

    if is_ocr:
        normalized_parts = _normalized_name_parts(name_upper)
        if not normalized_parts:
            return None
        if len(normalized_parts) == 1:
            compact_name = _compact_name(name_upper)
            candidates = [
                hris_name for hris_name in hris_names
                if _compact_name(hris_name) == compact_name
            ]
            if len(candidates) == 1 and candidates[0] not in duplicate_hris_names:
                return candidates[0]
            return None

        name_parts = set(normalized_parts)
        candidates = []
        for hris_name in hris_names:
            hris_parts = set(_normalized_name_parts(hris_name))
            if name_parts == hris_parts:
                candidates.append(hris_name)
        if len(candidates) == 1 and candidates[0] not in duplicate_hris_names:
            return candidates[0]
        return None

    if name_upper in hris_names:
        return None if name_upper in duplicate_hris_names else name_upper
    name_parts = set(name_upper.split())
    for hris_name in hris_names:
        hris_parts = set(hris_name.split())
        if name_parts and hris_parts:
            overlap = len(name_parts & hris_parts) / max(len(name_parts), len(hris_parts))
            if overlap >= 0.5:
                return None if hris_name in duplicate_hris_names else hris_name
    return None


def _get_ocr_engine():
    """Initialize bundled RapidOCR only when an image-only page needs it."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


class _OcrPageReader:
    """Lazily render OCR pages through one reusable PDFium document."""

    def __init__(
        self,
        file_path,
        pdf_document_factory=None,
        ocr_engine=None,
        ocr_engine_factory=None,
    ):
        self.file_path = file_path
        self._pdf_document_factory = pdf_document_factory
        self._ocr_engine = ocr_engine
        self._ocr_engine_factory = ocr_engine_factory or _get_ocr_engine
        self._ocr_initialization_exception = None
        self.initialization_error = None
        self._pdf = None

    def _get_engine(self):
        if self._ocr_engine is not None:
            return self._ocr_engine
        if self._ocr_initialization_exception is not None:
            raise RuntimeError(self.initialization_error) from self._ocr_initialization_exception
        try:
            self._ocr_engine = self._ocr_engine_factory()
        except Exception as exc:
            self._ocr_initialization_exception = exc
            self.initialization_error = str(exc) or exc.__class__.__name__
            raise
        return self._ocr_engine

    def _get_pdf(self):
        if self._pdf is None:
            if self._pdf_document_factory is None:
                import pypdfium2 as pdfium

                self._pdf_document_factory = pdfium.PdfDocument
            self._pdf = self._pdf_document_factory(self.file_path)
        return self._pdf

    def __call__(self, file_path, page_num):
        engine = self._get_engine()

        import numpy as np

        page = self._get_pdf()[page_num]
        try:
            bitmap = page.render(scale=300 / 72)
            try:
                image = np.asarray(bitmap.to_pil())
            finally:
                bitmap.close()
        finally:
            page.close()

        return engine(image)

    def close(self):
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None


def _ocr_pdf_page(file_path, page_num):
    """Render and OCR one page outside a processing run."""
    reader = _OcrPageReader(file_path)
    try:
        return reader(file_path, page_num)
    finally:
        reader.close()


def _extract_page_name(file_path, page_num, pdf_reader, ocr_page=None):
    """Extract a page name, invoking OCR only when normal text is empty."""
    page_text = _extract_page_text(file_path, page_num, pdf_reader)
    if page_text:
        return _extract_name(page_text)

    try:
        raw_ocr_result = (ocr_page or _ocr_pdf_page)(file_path, page_num)
        lines = _normalize_ocr_lines(raw_ocr_result)
        name = _extract_strideforth_name(lines)
    except Exception:
        return None, None
    return (name, "OCR") if name else (None, None)


def _sanitize_filename(filename):
    """Remove invalid filename characters."""
    filename = filename.replace(",,", ",")
    return re.sub(r'[\\/*?:"<>|\n\r]+', '', filename)


def _save_raw_page(pdf_reader, page_num, filepath):
    """Save a single PDF page without encryption."""
    writer = PdfWriter()
    writer.add_page(pdf_reader.pages[page_num])
    with open(filepath, 'wb') as f:
        writer.write(f)


def _save_encrypted_page(pdf_reader, page_num, password, filepath):
    """Save a single PDF page encrypted with a password."""
    writer = PdfWriter()
    writer.add_page(pdf_reader.pages[page_num])
    writer.encrypt(password)
    with open(filepath, 'wb') as f:
        writer.write(f)


def _parse_date_of_birth(value):
    """Parse Date of birth to MMDDYYYY password string. Returns None on failure."""
    if pd.isna(value) or value == "" or value is None:
        return None

    s = str(value).strip()

    for fmt in ('%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y',
                '%m/%d/%y', '%d/%m/%y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%m%d%Y')
        except ValueError:
            continue

    try:
        return pd.to_datetime(s, dayfirst=False).strftime('%m%d%Y')
    except Exception:
        return None


def process_external(file_path, output_folder, employee_data, pay_period, on_update=None):
    """Own and close path-based PDF streams around external processing."""
    owns_pdf_stream = isinstance(file_path, (str, bytes, os.PathLike))
    pdf_reader = PdfReader(file_path)
    try:
        return _process_external_with_reader(
            file_path,
            output_folder,
            employee_data,
            pay_period,
            pdf_reader,
            on_update,
        )
    finally:
        if owns_pdf_stream:
            stream = getattr(pdf_reader, "stream", None)
            if stream is not None and not getattr(stream, "closed", False):
                stream.close()


def _process_external_with_reader(
    file_path,
    output_folder,
    employee_data,
    pay_period,
    pdf_reader,
    on_update=None,
):
    """
    Split a combined PDF into individual encrypted payslips.

    Args:
        file_path: Path to multi-page PDF payslip file
        output_folder: Where to save individual encrypted PDFs and manifest
        employee_data: Path to HRIS Excel file (headers at row 8)
        pay_period: User-specified pay period string (e.g. "May 1-15, 2025")
        on_update: Callback for progress updates (msg)

    Returns:
        dict with success, processed, errors, output_excel keys
    """
    def emit(msg):
        if on_update:
            on_update(msg)

    emit("Starting external processing...")

    os.makedirs(output_folder, exist_ok=True)
    with_pw_dir = os.path.join(output_folder, "With Password")
    no_pw_dir = os.path.join(output_folder, "No Password")
    os.makedirs(with_pw_dir, exist_ok=True)
    os.makedirs(no_pw_dir, exist_ok=True)

    # Read HRIS data — headers start at row 8 (skiprows=7)
    employee_df = pd.read_excel(employee_data, skiprows=7)
    employee_df.fillna("", inplace=True)

    # Filter active employees only
    if 'Employment status' in employee_df.columns:
        employee_df = employee_df[employee_df['Employment status'] == 'Active']

    # Build lookup: FULL NAME -> employee details
    employee_info = {}
    hris_name_counts = {}
    for _, row in employee_df.iterrows():
        first_name = str(row.get('First name', '')).strip()
        last_name = str(row.get('Last name', '')).strip()
        full_name = f"{first_name} {last_name}".strip().upper()
        if not full_name:
            continue

        hris_name_counts[full_name] = hris_name_counts.get(full_name, 0) + 1

        system_id = str(row.get('System ID', '')).strip()
        dob = row.get('Date of birth', '')
        work_email = str(row.get('Email (Work)', '')).strip()
        personal_email = str(row.get('Email (Personal)', '')).strip()
        email = work_email if work_email else personal_email

        employee_info[full_name] = {
            'system_id': system_id,
            'birthday': dob,
            'email_address': email,
            'first_name': first_name,
            'last_name': last_name,
        }

    hris_names = list(employee_info.keys())
    duplicate_hris_names = {
        name for name, count in hris_name_counts.items() if count > 1
    }
    employees_data = []
    error_logs = []
    status_columns = [
        "Employee Number",
        "EMPLOYEE'S NAME",
        "Pay. Period",
        "filename",
        "email_address",
        "Password",
        "Status",
    ]
    status_rows = []
    total_pages = len(pdf_reader.pages)

    ocr_reader = _OcrPageReader(file_path)
    ocr_diagnostic_emitted = False
    try:
        for page_num in range(total_pages):
            emit(f"Processing page {page_num + 1} of {total_pages}...")
            name, layer = _extract_page_name(
                file_path, page_num, pdf_reader, ocr_page=ocr_reader
            )
            initialization_error = getattr(ocr_reader, "initialization_error", None)
            if initialization_error and not ocr_diagnostic_emitted:
                emit(
                    "OCR unavailable: failed to initialize the offline OCR engine "
                    f"({initialization_error}). Image-only pages will be saved to No Password."
                )
                ocr_diagnostic_emitted = True

            if not name:
                filename = f"Payslip - {pay_period}, Page {page_num + 1}.pdf"
                filepath = os.path.join(no_pw_dir, _sanitize_filename(filename))
                _save_raw_page(pdf_reader, page_num, filepath)
                error_logs.append({
                    "Page Number": page_num + 1,
                    "Employee Name": "Unknown",
                    "Error": "Could not extract name from PDF"
                })
                status_rows.append({
                    "Employee Number": "",
                    "EMPLOYEE'S NAME": "Unknown",
                    "Pay. Period": pay_period,
                    "filename": filepath,
                    "email_address": "",
                    "Password": "",
                    "Status": "Failed - Could not extract name",
                })
                emit(f"SKIP page {page_num + 1}: name extraction failed → No Password")
                continue

            name_upper = name.strip().upper()

            # OCR must be exact and unambiguous; text keeps the established overlap fallback.
            matched = _match_hris_name(
                name_upper,
                hris_names,
                is_ocr=layer == "OCR",
                is_rj=layer == "RJ",
                duplicate_hris_names=duplicate_hris_names,
            )

            if matched:
                emp = employee_info[matched]
                password = _parse_date_of_birth(emp['birthday'])

                if password:
                    filename = f"Payslip - {emp['system_id']}, {pay_period}, {emp['last_name']}, {emp['first_name']}.pdf"
                    filepath = os.path.join(with_pw_dir, _sanitize_filename(filename))
                    _save_encrypted_page(pdf_reader, page_num, password, filepath)

                    employees_data.append({
                        "Employee Number": emp['system_id'],
                        "EMPLOYEE'S NAME": name_upper,
                        "Pay. Period": pay_period,
                        "filename": filepath,
                        "email_address": emp['email_address']
                    })
                    status_rows.append({
                        "Employee Number": emp['system_id'],
                        "EMPLOYEE'S NAME": name_upper,
                        "Pay. Period": pay_period,
                        "filename": filepath,
                        "email_address": emp['email_address'],
                        "Password": password,
                        "Status": "Successful",
                    })
                    emit(f"OK page {page_num + 1}: {name_upper} [{layer}]")
                else:
                    filename = f"Payslip - {pay_period}, {name.strip()}.pdf"
                    filepath = os.path.join(no_pw_dir, _sanitize_filename(filename))
                    _save_raw_page(pdf_reader, page_num, filepath)
                    error_logs.append({
                        "Page Number": page_num + 1,
                        "Employee Name": name_upper,
                        "Error": "No valid Date of birth in HRIS"
                    })
                    status_rows.append({
                        "Employee Number": emp['system_id'],
                        "EMPLOYEE'S NAME": name_upper,
                        "Pay. Period": pay_period,
                        "filename": filepath,
                        "email_address": emp['email_address'],
                        "Password": "",
                        "Status": "Failed - No valid Date of birth",
                    })
                    emit(f"SKIP page {page_num + 1}: {name_upper} [{layer}] - no birthday → No Password")
            else:
                filename = f"Payslip - {pay_period}, {name.strip()}.pdf"
                filepath = os.path.join(no_pw_dir, _sanitize_filename(filename))
                _save_raw_page(pdf_reader, page_num, filepath)
                error_logs.append({
                    "Page Number": page_num + 1,
                    "Employee Name": name_upper,
                    "Error": "Employee not found in HRIS"
                })
                status_rows.append({
                    "Employee Number": "",
                    "EMPLOYEE'S NAME": name_upper,
                    "Pay. Period": pay_period,
                    "filename": filepath,
                    "email_address": "",
                    "Password": "",
                    "Status": "Failed - Employee not found in HRIS",
                })
                emit(f"SKIP page {page_num + 1}: {name_upper} [{layer}] - not in HRIS → No Password")
    finally:
        ocr_reader.close()

    excel_filepath = os.path.join(output_folder, 'employee_payslips.xlsx')
    with pd.ExcelWriter(excel_filepath, engine='openpyxl', mode='w') as writer:
        pd.DataFrame(employees_data).to_excel(writer, index=False, sheet_name='Payslips')
        if error_logs:
            pd.DataFrame(error_logs).to_excel(writer, index=False, sheet_name='Errors')
        pd.DataFrame(status_rows, columns=status_columns).to_excel(
            writer, index=False, sheet_name='Status'
        )

    emit(f"Complete. Processed: {len(employees_data)}, Errors: {len(error_logs)}")

    return {
        "success": True,
        "processed": len(employees_data),
        "errors": len(error_logs),
        "output_excel": excel_filepath
    }
