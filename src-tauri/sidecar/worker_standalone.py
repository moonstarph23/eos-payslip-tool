"""
Worker Standalone - External PDF Processing
Qt-free version for CLI/sidecar use.
No PyQt dependencies.
"""

from PyPDF2 import PdfReader, PdfWriter
from pdfminer.high_level import extract_text
import pandas as pd
import os
import re


def process_external(file_path, output_folder, employee_data, on_update=None):
    """
    Process external PDF payslips: split by employee, encrypt with birthday, match against Excel data.
    
    Args:
        file_path: Path to PDF file with multiple payslips
        output_folder: Where to save individual PDFs and output Excel
        employee_data: Path to employee data Excel file
        on_update: Callback for progress updates (msg)
    
    Returns:
        dict with success, processed, errors, output_excel keys
    """
    def emit(msg):
        if on_update:
            on_update(msg)

    emit("Starting external processing...")
    
    os.makedirs(output_folder, exist_ok=True)
    pdf_reader = PdfReader(file_path)
    employee_df = pd.read_excel(employee_data)
    employees_info = {
        row["EMPLOYEE'S NAME"].strip().upper(): row 
        for _, row in employee_df.iterrows()
    }
    employees_data = []
    error_logs = []

    total_pages = len(pdf_reader.pages)
    for page_num in range(total_pages):
        emit(f"Processing page {page_num + 1} of {total_pages}...")
        page_text = extract_text(file_path, page_numbers=[page_num])
        name_match = re.search(r"EMPLOYEE'S NAME\n\n(.+?)\n", page_text)
        pay_period_match = re.search(r"Pay\. Period\s+([\w\s-]+,\s*\d{4})", page_text)

        if not name_match or not pay_period_match:
            error_msg = "Missing data" if not name_match and not pay_period_match else ("Missing name" if not name_match else "Missing pay period")
            error_logs.append({
                "Page Number": page_num + 1,
                "Employee Name": "Unknown" if not name_match else name_match.group(1).strip().upper(),
                "Error": error_msg
            })
            continue

        name = name_match.group(1).strip().upper()
        pay_period = pay_period_match.group(1).strip()
        
        parts = pay_period.split()
        month = parts[0] if len(parts) > 0 else ""
        days = parts[1] if len(parts) > 1 else ""
        year = parts[2] if len(parts) > 2 else ""

        if name in employees_info:
            emp_info = employees_info[name]
            filename = f"Payslip - {emp_info['COUNTRY']}, {month}, {year}, {days}, {emp_info['LAST NAME']}, {emp_info['FIRST NAME']}.pdf"
            filepath = os.path.join(output_folder, sanitize_filename(filename))
            
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_num])
            birthday_password = emp_info['Birthday'].strftime('%m%d%Y')
            pdf_writer.encrypt(birthday_password)
            
            with open(filepath, 'wb') as out_file:
                pdf_writer.write(out_file)
            
            employees_data.append({
                "Employee Number": emp_info.get("Employee Number", ""),
                "EMPLOYEE'S NAME": name,
                "Pay. Period": pay_period,
                "filename": filepath,
                "email_address": emp_info.get("email_address", "")
            })
            emit(f"OK page {page_num + 1}: {name}")
        else:
            error_logs.append({
                "Page Number": page_num + 1,
                "Employee Name": name,
                "Error": "Employee not found in Excel"
            })
            emit(f"SKIP page {page_num + 1}: {name} - not in employee data")

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


def sanitize_filename(filename):
    filename = filename.replace(",,", ",")
    return re.sub(r'[\\/*?:"<>|\n\r]+', '', filename)
