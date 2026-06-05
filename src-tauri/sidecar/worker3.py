from PyQt6.QtCore import QThread, pyqtSignal
import os
import pandas as pd
from PyPDF2 import PdfWriter, PdfReader
import win32com.client as win32
from datetime import datetime
from dateutil.parser import parse

import time

class Worker3(QThread):
    finished_signal = pyqtSignal(str)
    update_signal = pyqtSignal(str)

    def __init__(self, excel_path, output_folder=None, output_sheet='output'):
        super(Worker3, self).__init__()
        self.excel_path = excel_path
        # Set output_folder to the directory of excel_path if not provided
        self.output_folder = output_folder if output_folder else os.path.dirname(excel_path)
        self.output_sheet = output_sheet

    def run(self):
        try:
            self.open_and_run_macro(self.excel_path)
            self.process_output_files()
        except Exception as e:
            self.finished_signal.emit(f"Error: {str(e)}")

    def open_and_run_macro(self, path):
        excel = win32.gencache.EnsureDispatch('Excel.Application')
        excel.Visible = True
        wb = excel.Workbooks.Open(os.path.abspath(path))
        excel.Application.Run("createPDF.createPayslips")
        wb.Close(SaveChanges=False)
        excel.Quit()
        self.update_signal.emit("PDF created successfully.")

    def process_output_files(self):
        employees_data = []
        error_logs = []
        try:
            df = pd.read_excel(self.excel_path, sheet_name=self.output_sheet, engine='openpyxl', dtype={'Password': str,'Pay. Period': str,'Employee Number': str})
        
        except Exception as e:
            self.finished_signal.emit(f"Failed to read Excel file: {str(e)}")
            return
        
        success_rows = df[df['Status'] == 'Successful']
        if success_rows.empty:
            self.update_signal.emit("No successful entries found.")
            return

        for index, row in success_rows.iterrows():
            filename = row['filename']
            password = row['Password']
            pay_period_str = row['Pay. Period']  # Assuming the format is 'MMDDYYYY' e.g., '04302024'

            # Parse the string to datetime object
            try:
                pay_period_date = datetime.strptime(pay_period_str, '%m%d%Y')
            except:
                pay_period_date = parse(pay_period_str)
            
            # print(pay_period_date)
            # Parse the string to datetime object using dateutil for flexibility
            # try:
            #     pay_period_date = parse(pay_period_str)
            # except:
            #     pass
            
            # print(pay_period_date)

            # Format the datetime object to the desired string format
            formatted_pay_period = pay_period_date.strftime('%B %d, %Y')  # 'April 30, 2024'

            if row['Status'] == 'Successful':
                try:
                    self.apply_password_to_pdf(filename, password)
                    time.sleep(.3)
                    employees_data.append({
                        "Employee Number": row["Employee Number"],
                        "EMPLOYEE'S NAME": row["EMPLOYEE'S NAME"],
                        "Pay. Period": formatted_pay_period,
                        "filename": filename,
                        "email_address": row["email_address"]
                    })
                    self.update_signal.emit(f"Password applied successfully to: {filename}")
                except Exception as e:
                    self.update_signal.emit(f"Failed to apply password to {filename}: {str(e)}")
                    error_logs.append({"Error in File": filename})

        self.save_excel_output(employees_data, error_logs)

    def apply_password_to_pdf(self, file_path, password):
        try:
            pdf_reader = PdfReader(file_path)
            pdf_writer = PdfWriter()
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

            pdf_writer.encrypt(password)
            with open(file_path, 'wb') as out:
                pdf_writer.write(out)
        except Exception as e:
            # self.update_signal.emit(f"Failed to apply password to {file_path}: {str(e)}")
            pass

    def save_excel_output(self, employees_data, error_logs):
        excel_filepath = os.path.join(self.output_folder, 'payslips_to_email.xlsx')
        with pd.ExcelWriter(excel_filepath, engine='openpyxl', mode='w') as writer:
            pd.DataFrame(employees_data).to_excel(writer, index=False, sheet_name='Payslips')
            if error_logs:
                pd.DataFrame(error_logs).to_excel(writer, index=False, sheet_name='Errors')
        processed_count = len(employees_data)
        error_count = len(error_logs)
        self.finished_signal.emit(f"All files processed. Successful: {processed_count}, Errors: {error_count}")
