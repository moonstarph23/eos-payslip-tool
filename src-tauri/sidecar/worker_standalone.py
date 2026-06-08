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


def _extract_name(page_text):
    """Extract employee name from page text with fallback layers.

    Strip CJK characters first, then try three layers:
      L1 - Exact:       EMPLOYEE'S NAME\\n\\nName\\n
      L2 - Relaxed:     handles spacing, punctuation, case variations
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

    # L3: Keyword proximity — find line with NAME/EMPLOYEE, take next non-empty line
    lines = cleaned.split('\n')
    for i, line in enumerate(lines):
        if re.search(r'\b(?:EMPLOYEE|NAME)\b', line, re.IGNORECASE) and i + 1 < len(lines):
            candidate = lines[i + 1].strip()
            if candidate and not re.match(r'^[\d\s\-/,.:]+$', candidate) and len(candidate) > 2:
                return candidate, "L3"

    return None, None


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

    pdf_reader = PdfReader(file_path)

    # Read HRIS data — headers start at row 8 (skiprows=7)
    employee_df = pd.read_excel(employee_data, skiprows=7)
    employee_df.fillna("", inplace=True)

    # Filter active employees only
    if 'Employment status' in employee_df.columns:
        employee_df = employee_df[employee_df['Employment status'] == 'Active']

    # Build lookup: FULL NAME -> employee details
    employee_info = {}
    for _, row in employee_df.iterrows():
        first_name = str(row.get('First name', '')).strip()
        last_name = str(row.get('Last name', '')).strip()
        full_name = f"{first_name} {last_name}".strip().upper()
        if not full_name:
            continue

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
    employees_data = []
    error_logs = []
    total_pages = len(pdf_reader.pages)

    for page_num in range(total_pages):
        emit(f"Processing page {page_num + 1} of {total_pages}...")
        page_text = _extract_page_text(file_path, page_num, pdf_reader)

        name, layer = _extract_name(page_text)

        if not name:
            filename = f"Payslip - {pay_period}, Page {page_num + 1}.pdf"
            filepath = os.path.join(no_pw_dir, _sanitize_filename(filename))
            _save_raw_page(pdf_reader, page_num, filepath)
            error_logs.append({
                "Page Number": page_num + 1,
                "Employee Name": "Unknown",
                "Error": "Could not extract name from PDF"
            })
            emit(f"SKIP page {page_num + 1}: name extraction failed → No Password")
            continue

        name_upper = name.strip().upper()

        # Match against HRIS
        matched = None
        if name_upper in employee_info:
            matched = name_upper
        else:
            name_parts = set(name_upper.split())
            for hris_name in hris_names:
                hris_parts = set(hris_name.split())
                if name_parts and hris_parts:
                    overlap = len(name_parts & hris_parts) / max(len(name_parts), len(hris_parts))
                    if overlap >= 0.5:
                        matched = hris_name
                        break

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
            emit(f"SKIP page {page_num + 1}: {name_upper} [{layer}] - not in HRIS → No Password")

    excel_filepath = os.path.join(output_folder, 'employee_payslips.xlsx')
    with pd.ExcelWriter(excel_filepath, engine='openpyxl', mode='w') as writer:
        pd.DataFrame(employees_data).to_excel(writer, index=False, sheet_name='Payslips')
        if error_logs:
            pd.DataFrame(error_logs).to_excel(writer, index=False, sheet_name='Errors')

    emit(f"Complete. Processed: {len(employees_data)}, Errors: {len(error_logs)}")

    return {
        "success": True,
        "processed": len(employees_data),
        "errors": len(error_logs),
        "output_excel": excel_filepath
    }
