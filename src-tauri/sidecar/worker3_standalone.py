"""
Standalone internal payslip processor - no Qt dependencies.
Called by the Python sidecar (sidecar.py) via CLI.
Replaces QThread/pyqtSignal with stdout logging for Tauri integration.
"""
import os
import sys
import json
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
from dateutil.parser import parse
import time

try:
    import win32com.client as win32
except ImportError:
    win32 = None


def log(level, message):
    """Emit JSON log line to stdout for the Rust sidecar."""
    print(json.dumps({
        "type": "log",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    }), flush=True)


def process_internal(excel_path, output_folder=None, output_sheet='output'):
    """
    Full internal payslip pipeline:
      1. Open Excel via COM and run createPDF.createPayslips macro
      2. Read the output sheet, apply PDF passwords
      3. Build payslips_to_email.xlsx summary
    """
    if not output_folder:
        output_folder = os.path.dirname(excel_path)

    # ---- Step 1: Open Excel & run macro ----
    if win32 is None:
        log("ERROR", "win32com not available. Internal processing requires Windows + Excel.")
        return {"success": False, "error": "win32com not available"}

    log("INFO", f"Opening Excel template: {excel_path}")
    try:
        excel = win32.gencache.EnsureDispatch('Excel.Application')
        excel.Visible = True
        wb = excel.Workbooks.Open(os.path.abspath(excel_path))
        log("INFO", "Running macro: createPDF.createPayslips")
        excel.Application.Run("createPDF.createPayslips")
        wb.Close(SaveChanges=False)
        excel.Quit()
        log("SUCCESS", "Excel macro completed.")
    except Exception as e:
        log("ERROR", f"Macro execution failed: {str(e)}")
        return {"success": False, "error": str(e)}

    # ---- Step 2: Read output sheet ----
    log("INFO", f"Reading output sheet '{output_sheet}' from workbook...")
    try:
        df = pd.read_excel(
            excel_path,
            sheet_name=output_sheet,
            engine='openpyxl',
            dtype={
                'Password': str,
                'Pay. Period': str,
                'Employee Number': str
            }
        )
    except Exception as e:
        log("ERROR", f"Failed to read output sheet: {str(e)}")
        return {"success": False, "error": str(e)}

    success_rows = df[df['Status'] == 'Successful']
    if success_rows.empty:
        log("WARNING", "No successful entries found in output sheet.")
        return {"success": True, "processed": 0}

    # ---- Step 3: Apply PDF passwords & build summary ----
    employees_data = []
    error_logs = []
    processed = 0

    for _, row in success_rows.iterrows():
        filename = row['filename']
        password = str(row['Password'])
        pay_period_str = str(row['Pay. Period'])

        # Parse pay period
        try:
            pay_period_date = datetime.strptime(pay_period_str, '%m%d%Y')
        except Exception:
            try:
                pay_period_date = parse(pay_period_str)
            except Exception:
                pay_period_date = datetime.now()

        formatted_pay_period = pay_period_date.strftime('%B %d, %Y')

        # Apply password to PDF
        try:
            _apply_password_to_pdf(filename, password)
            time.sleep(0.3)
            employees_data.append({
                "Employee Number": row["Employee Number"],
                "EMPLOYEE'S NAME": row["EMPLOYEE'S NAME"],
                "Pay. Period": formatted_pay_period,
                "filename": filename,
                "email_address": row["email_address"]
            })
            processed += 1
            log("INFO", f"Password applied to: {os.path.basename(filename)}")
        except Exception as e:
            log("WARNING", f"Failed to apply password to {os.path.basename(filename)}: {str(e)}")
            error_logs.append({"Error in File": filename})

    # ---- Step 4: Save summary Excel ----
    excel_filepath = os.path.join(output_folder, 'payslips_to_email.xlsx')
    try:
        with pd.ExcelWriter(excel_filepath, engine='openpyxl', mode='w') as writer:
            pd.DataFrame(employees_data).to_excel(writer, index=False, sheet_name='Payslips')
            if error_logs:
                pd.DataFrame(error_logs).to_excel(writer, index=False, sheet_name='Errors')
        log("SUCCESS", f"Summary saved: {excel_filepath}")
    except Exception as e:
        log("ERROR", f"Failed to save summary Excel: {str(e)}")
        return {"success": False, "error": str(e)}

    return {
        "success": True,
        "processed": processed,
        "errors": len(error_logs),
        "output_excel": excel_filepath
    }


def _apply_password_to_pdf(file_path, password):
    """Encrypt a PDF with the given password."""
    pdf_reader = PdfReader(file_path)
    pdf_writer = PdfWriter()
    for page in pdf_reader.pages:
        pdf_writer.add_page(page)
    pdf_writer.encrypt(password)
    with open(file_path, 'wb') as out:
        pdf_writer.write(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker3_standalone.py <excel_path> [output_folder]", file=sys.stderr)
        sys.exit(1)

    result = process_internal(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps({"type": "result", "data": result}), flush=True)
