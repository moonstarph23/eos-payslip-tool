from PyQt6.QtCore import QThread, pyqtSignal
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime
import time
from email.header import Header
from email.utils import formataddr


class Worker2(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str, int, int, str)

    def __init__(self, excel_path, body_template, email, app_password, alias, subject_template):
        super().__init__()
        self.excel_path = excel_path
        self.body_template = body_template
        self.email = email
        self.app_password = app_password
        # self.email = "astigxtutorials@gmail.com"
        # self.app_password = "sutuqwqmdgfpcwnm"
        self.alias = alias
        self.subject_template = subject_template
        self.success_logs = []
        self.error_logs = []

    def run(self):
        df = pd.read_excel(self.excel_path)
        success_count = 0
        error_count = 0

        for index, row in df.iterrows():
            recipient = row['email_address']
            name = row.get("EMPLOYEE'S NAME", "")
            period = row.get('Pay. Period', "")
            filename = row['filename'].split('Payslip - ')[1] if 'Payslip - ' in row.get('filename', '') else row.get('filename', '')
            subject = self.subject_template.replace("{filename}", filename).replace("{EMPLOYEE'S NAME}", name)
            body = self.body_template.replace("{EMPLOYEE'S NAME}", name).replace("{Pay. Period}", period)
            file_path = row['filename'] if 'filename' in row and row['filename'] else None

            message = self.create_message(self.alias, recipient, subject, body, file_path)
            
            try:
                self.send_email(message)
                success_count += 1
                self.success_logs.append({
                    "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "email_address": recipient,
                    "subject": subject
                })
                time.sleep(2)
            except Exception as e:
                error_count += 1
                self.error_logs.append({
                    "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "email_address": recipient,
                    "subject": subject,
                    "Error": str(e)
                })

            self.update_signal.emit(f"Sending Email {index + 1} of {len(df)}: {subject}")

        excel_filepath = self.create_excel_output()
        self.finished_signal.emit("Email Sending Completed.", success_count, error_count, excel_filepath)
    
    


    def create_message(self, sender, recipient, subject, body, file_path):
        message = MIMEMultipart()
        message['From'] = formataddr((str(Header(sender, 'utf-8')), sender))
        message['To'] = formataddr((str(Header(recipient, 'utf-8')), recipient))
        message['Subject'] = Header(subject, 'utf-8')
        message.attach(MIMEText(body, 'plain'))

        if file_path:
            filename = os.path.basename(file_path)  # Extracts the filename from the file path
            try:
                with open(file_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    # Properly format the filename in the header to handle special characters and spaces
                    part.add_header("Content-Disposition", 'attachment', filename=(Header(filename, 'utf-8').encode()))
                    message.attach(part)
                    time.sleep(1)  # Sleep may not be necessary unless you have a specific reason for it
            except Exception as e:
                print(f"Could not attach file {file_path}. Error: {e}")

        return message


    def send_email(self, message):
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(self.email, self.app_password)
            server.send_message(message)

    def create_excel_output(self):
        output_path = os.path.splitext(self.excel_path)[0] + '_emailoutput.xlsx'
        with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
            if self.success_logs:
                pd.DataFrame(self.success_logs).to_excel(writer, index=False, sheet_name='Success')
            if self.error_logs:
                pd.DataFrame(self.error_logs).to_excel(writer, index=False, sheet_name='Error')
        return output_path
