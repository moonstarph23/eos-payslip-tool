#!/usr/bin/env python3
"""
EOS Payslip Tool - Python Sidecar
CLI wrapper for payroll processing workers.
Communicates with Tauri backend via JSON on stdout.
"""

# VERSION MARKER — change this to force cache refresh
SIDECAR_VERSION = "1.0.7"

import sys
import json
import os
import argparse
import traceback
from datetime import datetime

# Add the directory containing this script to path so we can import workers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log_json(level, message, data=None):
    """Emit a JSON log line to stdout for the Rust backend to parse."""
    entry = {
        "type": "log",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    }
    if data:
        entry["data"] = data
    print(json.dumps(entry), flush=True)

def output_json(data):
    """Emit a JSON result to stdout."""
    print(json.dumps({"type": "result", "data": data}), flush=True)

def main():
    parser = argparse.ArgumentParser(description="EOS Payslip Tool Sidecar")
    parser.add_argument("command", choices=[
        "process_external",
        "process_internal",
        "process_individual",
        "send_emails",
        "test_email",
        "get_aliases",
        "get_platform"
    ], help="Command to execute")
    parser.add_argument("--pdf", help="Path to PDF file or folder")
    parser.add_argument("--employee-data", help="Path to employee data Excel")
    parser.add_argument("--output-folder", help="Path to output folder")
    parser.add_argument("--template", help="Path to Excel template (.xlsm)")
    parser.add_argument("--manifest", help="Path to email manifest Excel")
    parser.add_argument("--config", help="JSON config string for email")
    parser.add_argument("--email", help="Email address for alias lookup")
    parser.add_argument("--password", help="App password for alias lookup")
    parser.add_argument("--period", help="Pay period string")
    parser.add_argument("--remove-phrases", help="Comma-separated list of phrases to strip from PDF filenames")
    
    args = parser.parse_args()
    
    log_json("INFO", f"Sidecar version: {SIDECAR_VERSION}")
    
    try:
        if args.command == "get_platform":
            import platform
            output_json({
                "platform": platform.system().lower(),
                "machine": platform.machine(),
                "version": platform.version()
            })
        
        elif args.command == "process_external":
            if not all([args.pdf, args.employee_data, args.output_folder]):
                log_json("ERROR", "Missing required arguments for external processing", {
                    "required": ["--pdf", "--employee-data", "--output-folder"]
                })
                sys.exit(1)
            
            pay_period = args.period or ""
            
            log_json("INFO", "Starting external payslip processing...")
            log_json("INFO", f"PDF: {args.pdf}")
            log_json("INFO", f"Employee Data: {args.employee_data}")
            log_json("INFO", f"Output Folder: {args.output_folder}")
            log_json("INFO", f"Pay Period: {pay_period}")
            
            try:
                from worker_standalone import process_external as process_external_worker
                
                def on_update(msg):
                    log_json("INFO", msg)
                
                result = process_external_worker(
                    args.pdf,
                    args.output_folder,
                    args.employee_data,
                    pay_period,
                    on_update=on_update
                )
                
                log_json("SUCCESS", f"External processing complete. {result['processed']} processed, {result['errors']} errors.")
                output_json(result)
                
            except Exception as e:
                log_json("ERROR", f"Processing failed: {str(e)}")
                output_json({"success": False, "error": str(e)})
        
        elif args.command == "process_internal":
            if not args.template:
                log_json("ERROR", "Missing required --template argument")
                sys.exit(1)
            
            # Internal generation requires Excel COM automation (Windows only)
            import platform as _platform
            if _platform.system() != "Windows":
                log_json("ERROR", "Internal payslip generation requires Microsoft Excel on Windows. This feature is not available on macOS/Linux.")
                output_json({"success": False, "error": "Internal generation requires Windows + Microsoft Excel"})
                sys.exit(1)
            
            log_json("INFO", "Starting internal payslip generation...")
            log_json("INFO", f"Template: {args.template}")
            
            try:
                from worker3_standalone import process_internal
                
                result = process_internal(args.template)
                output_json(result)
                
            except Exception as e:
                log_json("ERROR", f"Internal processing failed: {str(e)}")
                output_json({"success": False, "error": str(e)})
        
        elif args.command == "send_emails":
            if not args.manifest:
                log_json("ERROR", "Missing required --manifest argument")
                sys.exit(1)
            
            config = json.loads(args.config) if args.config else {}
            
            log_json("INFO", "Starting email distribution...")
            log_json("INFO", f"Manifest: {args.manifest}")
            log_json("INFO", f"SMTP login (AUTH): {config.get('email', 'N/A')}")
            log_json("INFO", f"Alias (From header): {config.get('alias', 'N/A')}")
            
            try:
                from worker2_standalone import send_emails as send_emails_worker
                
                def on_update(msg):
                    log_json("INFO", msg)
                
                result = send_emails_worker(
                    args.manifest,
                    config.get("body", ""),
                    config.get("email", ""),
                    config.get("app_password", ""),
                    config.get("alias", ""),
                    config.get("subject", "Payslip: {filename}"),
                    alias_name=config.get("alias_name", None),
                    on_update=on_update
                )
                
                log_json("SUCCESS", f"Email sending complete. {result['sent']} sent, {result['failed']} failed.")
                output_json(result)
                
            except Exception as e:
                log_json("ERROR", f"Email sending failed: {str(e)}")
                output_json({"success": False, "error": str(e)})
        
        elif args.command == "test_email":
            config = json.loads(args.config) if args.config else {}
            email = config.get("email", "")
            alias = config.get("alias", email)
            alias_name = config.get("alias_name", "")
            recipient = config.get("recipient", alias)
            app_password = config.get("app_password", "")
            subject = config.get("subject", "Test Email")
            body = config.get("body", "This is a test email.")

            if not all([email, app_password]):
                log_json("ERROR", "Missing email or app_password for test email")
                output_json({"success": False, "error": "Missing email or app_password"})
                sys.exit(1)

            log_json("INFO", f"Sending test email from {alias} to {recipient}")

            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                from email.header import Header
                from email.utils import formataddr

                message = MIMEMultipart()
                # 'From:' = alias with optional display name as plain literal string
                if alias_name:
                    message['From'] = f"{alias_name} <{alias}>"
                else:
                    message['From'] = alias
                # Reply-To ensures replies go to the alias, not the auth account
                message['Reply-To'] = alias
                message['To'] = formataddr((str(Header(recipient, 'utf-8')), recipient))
                message['Subject'] = Header(subject, 'utf-8')
                message.attach(MIMEText(body, 'plain'))

                log_json("INFO", f"SMTP connecting to smtp.gmail.com:465...")
                log_json("INFO", f"Message From={message['From']}, To={recipient}")

                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.set_debuglevel(1)  # Verbose SMTP logging to stderr
                    log_json("INFO", f"SMTP AUTH user: {email}")
                    server.login(email, app_password)
                    log_json("INFO", "SMTP login successful")
                    log_json("INFO", f"SMTP sending with envelope MAIL FROM: {alias}")
                    # Force envelope sender to alias
                    from email.utils import parseaddr
                    _, to_addr = parseaddr(message['To'])
                    to_addrs = [to_addr] if to_addr else []
                    result = server.sendmail(alias, to_addrs, message.as_string())
                    log_json("INFO", f"SMTP sendmail result: {result}")

                log_json("SUCCESS", f"Test email sent successfully to {recipient}!")
                output_json({"success": True, "recipient": recipient})

            except smtplib.SMTPAuthenticationError as e:
                log_json("ERROR", f"SMTP Authentication failed: {e.smtp_code} {e.smtp_error}")
                output_json({"success": False, "error": f"Authentication failed: {e.smtp_error}"})
            except smtplib.SMTPRecipientsRefused as e:
                log_json("ERROR", f"SMTP Recipient refused: {e.recipients}")
                output_json({"success": False, "error": f"Recipient refused: {e.recipients}"})
            except smtplib.SMTPSenderRefused as e:
                log_json("ERROR", f"SMTP Sender refused: {e.sender} - {e.smtp_error}")
                output_json({"success": False, "error": f"Sender refused: {e.smtp_error}"})
            except Exception as e:
                log_json("ERROR", f"Test email failed: {str(e)}")
                output_json({"success": False, "error": str(e)})

        elif args.command == "get_aliases":
            lookup_email = args.email or ""
            log_json("INFO", f"Looking up aliases for {lookup_email}")
            # Return the main email as the primary alias (Gmail API would be needed for full list)
            aliases = [lookup_email] if lookup_email else []
            output_json({"success": True, "aliases": aliases})
            log_json("SUCCESS", f"Found {len(aliases)} alias(es)")

        elif args.command == "process_individual":
            if not all([args.pdf, args.employee_data]):
                log_json("ERROR", "Missing required arguments for individual PDF processing", {
                    "required": ["--pdf", "--employee-data"]
                })
                sys.exit(1)
            
            log_json("INFO", "Starting individual PDF encryption...")
            log_json("INFO", f"PDF Folder: {args.pdf}")
            log_json("INFO", f"HRIS File: {args.employee_data}")
            
            # Parse custom phrases
            remove_phrases = None
            if args.remove_phrases:
                remove_phrases = [p.strip() for p in args.remove_phrases.split(',') if p.strip()]
                log_json("INFO", f"Custom phrases to remove: {remove_phrases}")
            
            try:
                from worker4_standalone import encrypt_payslips
                
                def on_update(msg):
                    log_json("INFO", msg)
                
                pay_period = args.period or "Pay Period"
                result = encrypt_payslips(
                    args.pdf,
                    pay_period,
                    args.employee_data,
                    remove_phrases=remove_phrases,
                    on_update=on_update
                )
                
                log_json("SUCCESS", f"Individual PDF encryption complete. {result['encrypted']} encrypted, {result['failed']} failed.")
                output_json(result)
                
            except Exception as e:
                tb = traceback.format_exc()
                log_json("ERROR", f"Individual PDF processing failed: {str(e)}")
                log_json("ERROR", f"Traceback: {tb}")
                output_json({"success": False, "error": str(e), "traceback": tb})
        
        else:
            log_json("ERROR", f"Unknown command: {args.command}")
            sys.exit(1)
            
    except Exception as e:
        tb = traceback.format_exc()
        log_json("ERROR", f"Sidecar error: {str(e)}")
        log_json("ERROR", f"Traceback: {tb}")
        sys.exit(1)

if __name__ == "__main__":
    main()
