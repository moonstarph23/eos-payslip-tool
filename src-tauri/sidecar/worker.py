from PyQt6.QtCore import QThread, pyqtSignal
from PyPDF2 import PdfReader, PdfWriter
from pdfminer.high_level import extract_text
import pandas as pd
import os
import re

class Worker(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, file_path, output_folder, employee_data):
        super().__init__()
        self.file_path = file_path
        self.output_folder = output_folder
        self.employee_data = employee_data

    def run(self):
        try:
            self.update_signal.emit("Starting processing...")
            excel_filepath, employees_data, processed_count, error_count = self.process_payslips(
                self.file_path, self.output_folder, self.employee_data
            )
            self.update_signal.emit("Processing complete.")
            success_message = f"Payslips processed successfully.\nProcessed: {processed_count} pages\nFailed: {error_count} pages\nOutput at: {excel_filepath}"
            if error_count > 0:
                success_message += "\nCheck the 'Errors' sheet in the output Excel for details."
            self.finished_signal.emit(success_message)
        except Exception as e:
            self.finished_signal.emit(f"Processing Error: {str(e)}")

    def process_payslips(self, file_path, output_folder, employee_data):
        os.makedirs(output_folder, exist_ok=True)
        pdf_reader = PdfReader(file_path)
        employee_df = pd.read_excel(employee_data)
        employees_info = {row["EMPLOYEE'S NAME"].strip().upper(): row for index, row in employee_df.iterrows()}
        employees_data = []
        error_logs = []

        for page_num in range(len(pdf_reader.pages)):
            self.update_signal.emit(f"Processing page: {page_num + 1}")
            page_text = extract_text(file_path, page_numbers=[page_num])
            name_match = re.search(r"EMPLOYEE'S NAME\n\n(.+?)\n", page_text)
            pay_period_match = re.search(r"Pay\. Period\s+([\w\s-]+,\s*\d{4})", page_text)

            if not name_match or not pay_period_match:
                error_message = "Missing data" if not name_match and not pay_period_match else "Missing name" if not name_match else "Missing pay period"
                error_logs.append({"Page Number": page_num + 1, "Employee Name": "Unknown" if not name_match else name_match.group(1).strip().upper(), "Error": error_message})
                continue

            name = name_match.group(1).strip().upper()
            pay_period = pay_period_match.group(1).strip()
            month, year, days = self.parse_pay_period(pay_period)
            
            if name in employees_info:
                emp_info = employees_info[name]
                filename = f"Payslip - {emp_info['COUNTRY']}, {month}, {year}, {days}, {emp_info['LAST NAME']}, {emp_info['FIRST NAME']}.pdf"
                filepath = os.path.join(output_folder, self.sanitize_filename(filename))
                pdf_writer = PdfWriter()
                pdf_writer.add_page(pdf_reader.pages[page_num])
                birthday_password = self.format_birthday(emp_info['Birthday'])
                pdf_writer.encrypt(birthday_password)
                with open(filepath, 'wb') as out_file:
                    pdf_writer.write(out_file)
                employees_data.append({
                    "Employee Number": emp_info["Employee Number"],
                    "EMPLOYEE'S NAME": name,
                    "Pay. Period": pay_period,
                    "filename": filepath,
                    "email_address": emp_info["email_address"]
                })
            else:
                error_logs.append({"Page Number": page_num + 1, "Employee Name": name, "Error": "Employee not found in Excel"})

        excel_filepath = os.path.join(output_folder, 'employee_payslips.xlsx')
        processed_count = len(employees_data)
        error_count = len(error_logs)
        with pd.ExcelWriter(excel_filepath, engine='openpyxl', mode='w') as writer:
            pd.DataFrame(employees_data).to_excel(writer, index=False, sheet_name='Payslips')
            if error_logs:
                pd.DataFrame(error_logs).to_excel(writer, index=False, sheet_name='Errors')

        return excel_filepath, employees_data[:3] if employees_data else None, processed_count, error_count

    def sanitize_filename(self, filename):
        filename = filename.replace(",,", ",")
        return re.sub(r'[\\/*?:"<>|\n\r]+', '', filename)

    def parse_pay_period(self, pay_period):
        parts = pay_period.split()
        month = parts[0]
        days = parts[1]
        year = parts[2]
        return month, year, days

    def format_birthday(self, date):
        return date.strftime('%m%d%Y')
