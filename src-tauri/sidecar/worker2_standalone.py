"""
Worker2 Standalone - Email Distribution
Qt-free version for CLI/sidecar use.
No PyQt dependencies.
"""

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


def send_emails(excel_path, body_template, email, app_password, alias, subject_template,
                alias_name=None,
                on_update=None, on_error=None, on_finished=None):
    """
    Process an email manifest Excel file and send emails to all recipients.
    
    Args:
        excel_path: Path to the Excel manifest file
        body_template: Email body template with {variables}
        email: SMTP login email
        app_password: SMTP app password
        alias: Display From email address
        subject_template: Subject template with {variables}
        on_update: Callback for progress updates (msg)
        on_error: Callback for errors (msg)
        on_finished: Callback when done (msg, success_count, error_count, output_excel)
    
    Returns:
        dict with success, sent, failed, output_excel keys
    """
    def emit(msg):
        if on_update:
            on_update(msg)

    df = pd.read_excel(excel_path)
    success_count = 0
    error_count = 0
    success_logs = []
    error_logs = []

    for index, row in df.iterrows():
        recipient = row['email_address']
        name = row.get("EMPLOYEE'S NAME", "")
        period = row.get('Pay. Period', "")
        raw_filename = row.get('filename', '')
        filename = os.path.basename(raw_filename).split('Payslip - ')[-1] if 'Payslip - ' in raw_filename else os.path.basename(raw_filename)
        subject = subject_template.replace("{filename}", filename).replace("{EMPLOYEE'S NAME}", name)
        body = body_template.replace("{EMPLOYEE'S NAME}", name).replace("{Pay. Period}", period)
        file_path = row['filename'] if 'filename' in row and row['filename'] else None

        message = _create_message(alias, alias_name, recipient, subject, body, file_path)
        
        try:
            _send_email(email, app_password, message, alias)
            success_count += 1
            success_logs.append({
                "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "email_address": recipient,
                "subject": subject
            })
            emit(f"OK {index + 1}/{len(df)}: {name} <{recipient}>")
            time.sleep(2)
        except Exception as e:
            error_count += 1
            err_msg = str(e)
            error_logs.append({
                "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "email_address": recipient,
                "subject": subject,
                "Error": err_msg
            })
            emit(f"FAIL {index + 1}/{len(df)}: {name} <{recipient}> - {err_msg}")

    output_path = os.path.splitext(excel_path)[0] + '_emailoutput.xlsx'
    with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
        if success_logs:
            pd.DataFrame(success_logs).to_excel(writer, index=False, sheet_name='Success')
        if error_logs:
            pd.DataFrame(error_logs).to_excel(writer, index=False, sheet_name='Error')

    if on_finished:
        on_finished("Email Sending Completed.", success_count, error_count, output_path)

    return {
        "success": error_count == 0,
        "sent": success_count,
        "failed": error_count,
        "output_excel": output_path
    }


def _create_message(sender, sender_name, recipient, subject, body, file_path):
    message = MIMEMultipart()
    # The 'From:' header is what the recipient sees — this is the alias
    # Set as plain literal string: "Display Name <email@domain.com>"
    if sender_name:
        message['From'] = f"{sender_name} <{sender}>"
    else:
        message['From'] = sender
    # Reply-To ensures replies go to the alias, not the auth account
    message['Reply-To'] = sender
    message['To'] = formataddr((str(Header(recipient, 'utf-8')), recipient))
    message['Subject'] = Header(subject, 'utf-8')
    message.attach(MIMEText(body, 'plain'))

    if file_path and os.path.exists(file_path):
        attachment_name = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", 'attachment', filename=(Header(attachment_name, 'utf-8').encode()))
                message.attach(part)
        except Exception as e:
            print(f"Could not attach file {file_path}. Error: {e}")

    return message


def _send_email(email, app_password, message, alias):
    # Force envelope MAIL FROM to be the alias (not derived from msg['From'])
    from email.utils import parseaddr
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.set_debuglevel(1)  # Full SMTP transcript to stderr
        print(f"[SMTP-DEBUG] AUTH user: {email}", flush=True)
        print(f"[SMTP-DEBUG] Envelope MAIL FROM: {alias}", flush=True)
        print(f"[SMTP-DEBUG] Message From header: {message['From']}", flush=True)
        server.login(email, app_password)
        print(f"[SMTP-DEBUG] Login successful", flush=True)
        # Extract raw recipient email from formatted To header
        _, to_addr = parseaddr(message['To'])
        to_addrs = [to_addr] if to_addr else []
        result = server.sendmail(alias, to_addrs, message.as_string())
        print(f"[SMTP-DEBUG] sendmail result: {result}", flush=True)
