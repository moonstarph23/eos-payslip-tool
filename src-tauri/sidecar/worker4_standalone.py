"""
Worker4 Standalone - Encrypt Individual PDFs with HRIS Data
Qt-free version for CLI/sidecar use.
Takes a folder of individual PDFs, matches filenames with HRIS data,
password-protects each PDF with birthday in MMDDYYYY format,
and generates payslips_to_email.xlsx manifest.
"""

import os
import re
from datetime import datetime
from dateutil.parser import parse as dateutil_parse
import pandas as pd
import PyPDF2

try:
    from rapidfuzz import process as rf_process
    _use_rapidfuzz = True
except ImportError:
    _use_rapidfuzz = False


def encrypt_payslips(pdf_folder, pay_period, hris_file,
                     remove_phrases=None,
                     on_update=None, on_error=None, on_finished=None):
    """
    Process individual PDF payslips by matching with HRIS data,
    encrypting each with birthday password, and generating manifest.
    
    Args:
        remove_phrases: Optional list of phrases to strip from PDF filenames.
                          When provided, skips all hardcoded patterns and uses
                          only these user-defined phrases.
    """
    def emit(msg):
        if on_update:
            on_update(msg)

    try:
        # 1. Build initial DataFrame from PDFs in folder
        emit("Scanning PDF folder...")
        rows = []
        pdf_files = sorted([f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')])
        if not pdf_files:
            raise ValueError("No PDF files found in the selected folder")

        for file in pdf_files:
            full_path = os.path.join(pdf_folder, file)
            rows.append({
                'Employee Number': None,
                "EMPLOYEE'S NAME": full_path,
                'Pay. Period': pay_period,
                'filename': full_path,
                'email_address': None,
                'Birthday': None,
            })

        df = pd.DataFrame(rows, columns=[
            'Employee Number', "EMPLOYEE'S NAME", 'Pay. Period',
            'filename', 'email_address', 'Birthday'
        ])

        # 2. Clean names from filenames
        emit(f"Found {len(df)} PDF(s). Cleaning filenames...")
        if remove_phrases:
            emit(f"Using custom phrases: {remove_phrases}")
        df["EMPLOYEE'S NAME"] = df["EMPLOYEE'S NAME"].apply(lambda p: _clean_name(p, remove_phrases=remove_phrases))
        df.fillna("", inplace=True)

        # 3. Load HRIS data
        emit("Loading HRIS data...")
        df_Hris = pd.read_excel(hris_file, skiprows=7)
        df_Hris.fillna("", inplace=True)

        # Filter active employees
        if 'Employment status' in df_Hris.columns:
            df_Hris = df_Hris[df_Hris['Employment status'] == 'Active']

        # Build full name
        if 'First name' in df_Hris.columns and 'Last name' in df_Hris.columns:
            df_Hris["EMPLOYEE'S NAME"] = (df_Hris['First name'].astype(str).str.strip() + " " +
                                            df_Hris['Last name'].astype(str).str.strip())
            df_Hris["EMPLOYEE'S NAME"] = df_Hris["EMPLOYEE'S NAME"].str.replace(r'\s+', ' ', regex=True).str.strip()

        # Dedupe
        df_Hris = df_Hris.drop_duplicates(subset=["EMPLOYEE'S NAME"])

        # Extract relevant columns
        email_col = 'Email (Personal)' if 'Email (Personal)' in df_Hris.columns else None
        id_col = 'System ID' if 'System ID' in df_Hris.columns else None
        dob_col = 'Date of birth' if 'Date of birth' in df_Hris.columns else None

        if not email_col or not id_col or not dob_col:
            raise ValueError("HRIS file missing required columns: 'Email (Personal)', 'System ID', 'Date of birth'")

        df_Hris['email_address'] = df_Hris[email_col].fillna("")
        df_Hris['Date of birth'] = df_Hris[dob_col].fillna("")

        # Map name to details
        name_to_details = df_Hris.set_index("EMPLOYEE'S NAME")[
            ['email_address', id_col, 'Date of birth']
        ].to_dict('index')

        # 4. Fuzzy match PDF names to HRIS names
        emit("Matching PDF names with HRIS data...")
        hris_names = list(name_to_details.keys())
        matched_count = 0
        for i, row in df.iterrows():
            match = _fuzzy_match(row["EMPLOYEE'S NAME"], hris_names, score_cutoff=80)
            if match:
                details = name_to_details[match]
                df.at[i, 'email_address'] = details['email_address']
                df.at[i, 'Employee Number'] = details[id_col]
                df.at[i, 'Birthday'] = details['Date of birth']
                matched_count += 1
            else:
                df.at[i, 'email_address'] = ""
                df.at[i, 'Employee Number'] = None
                df.at[i, 'Birthday'] = ""
            name = row["EMPLOYEE'S NAME"]
            emit(f"  Matched {matched_count}/{len(df)}: {name}")

        # 5. Build status DataFrame (with password)
        df_status = df.copy()
        df = df[df['Birthday'] != ""]
        df.drop('Birthday', axis=1, inplace=True)

        # Format birthday as MMDDYYYY password
        def _format_date(date_str):
            if pd.isna(date_str) or date_str == "":
                return ""
            s = str(date_str).strip()
            # Try explicit formats to avoid pandas guessing day vs month
            for fmt in ('%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y',
                        '%m/%d/%y', '%d/%m/%y', '%Y/%m/%d'):
                try:
                    from datetime import datetime as _dt
                    date_obj = _dt.strptime(s, fmt)
                    return date_obj.strftime('%m%d%Y')
                except ValueError:
                    continue
            # Fallback: let pandas guess, but force month-first for ambiguous dates
            try:
                date_obj = pd.to_datetime(s, dayfirst=False)
                return date_obj.strftime('%m%d%Y')
            except Exception:
                return ""

        df_status['Password'] = df_status['Birthday'].apply(_format_date)
        df_status['Status'] = ""
        df_status.drop('Birthday', axis=1, inplace=True)

        # 6. Encrypt PDFs with password
        emit("Encrypting PDFs with birthday passwords...")
        encrypted_count = 0
        failed_count = 0
        for index, row in df_status.iterrows():
            pwd = row['Password']
            filepath = row['filename']
            if pwd:
                if _encrypt_pdf(filepath, filepath, pwd):
                    df_status.at[index, 'Status'] = "Successful"
                    encrypted_count += 1
                    emit(f"  Encrypted: {os.path.basename(filepath)}")
                else:
                    df_status.at[index, 'Status'] = "Failed"
                    failed_count += 1
                    emit(f"  Failed: {os.path.basename(filepath)}")
            else:
                df_status.at[index, 'Status'] = "Failed due to no match in HRIS or no birthday"

        # 7. Filter df to only rows with email
        df = df[df['email_address'] != ""]

        # 8. Write Excel manifest
        excel_path = os.path.join(pdf_folder, 'payslips_to_email.xlsx')
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Payslips', index=False)
            df_status.to_excel(writer, sheet_name='Status', index=False)

        emit(f"Manifest saved: {excel_path}")
        emit(f"Processed {len(df_status)} PDFs. Encrypted: {encrypted_count}, Failed: {failed_count}")

        if on_finished:
            on_finished(f"Encrypt payslips complete.", encrypted_count, failed_count, excel_path)

        return {
            "success": failed_count == 0,
            "encrypted": encrypted_count,
            "failed": failed_count,
            "output_excel": excel_path,
        }

    except Exception as e:
        if on_error:
            on_error(str(e))
        raise


def _clean_name(path, remove_phrases=None):
    # Start with just the filename, no directory path
    path = os.path.basename(path)
    
    # Remove .pdf extension
    path = re.sub(r'\.pdf$', '', path, flags=re.IGNORECASE)
    
    # Remove PDFs/ prefix (legacy convention)
    path = re.sub(r'.*PDFs[\\/]', '', path)

    if remove_phrases:
        # User-defined mode: only strip custom phrases (case-insensitive)
        for phrase in remove_phrases:
            if phrase:
                path = path.replace(phrase, ' ')
                # Also try case-insensitive replacement
                path = re.sub(re.escape(phrase), ' ', path, flags=re.IGNORECASE)
    else:
        # Default mode: use hardcoded patterns
        # Remove known phrases
        phrases = [
            ' PH ', ' TH ', ' ISP ', ' Jamaica ', ' SK ', ' Taiwan ', ' Vietnam ',
            ' China ', ' Indonesia ', ' KSA ', 'Salary ', ' salary ', ' PNG ', ' Latvia ',
            ' UK ', ' Portugal ', ' Ireland ', ' Germany ', ' Romania ', ' Austria ',
            ' Netherlands ', ' AA GMS ', ' AA-GMS ', ' Payslip ', 'Pay Slip',
        ]
        for phrase in phrases:
            path = path.replace(phrase, ' ')

        # Regex removals
        patterns = [
            # Remove leading month name (e.g. "May DARREL BISPO")
            r"^\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+",
            r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+",
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2} to (January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}\b",
            r"Payslip in \b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b \d{4}_",
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)_Payslip_",
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)_Payslip_",
            r"\(\d+\)",
            r"\b\d{4}(0[1-9]|1[0-2])_",
            r"\b\d{4}(0[1-9]|1[0-2])",
            r"Payslip-EOS\d+",
            r"EOS_TW",
            r"_payslip_",
            r"\b(0[1-9]|1[0-2])-\d{4}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}\b",
            r"\b\d{4}\b",
            r"_{2,}",
            r"_(?=[A-Za-z])",
            r"\bpayslip\b",
            r"\bv\d+\b",
            r"\(EO\d+\)",
            r"_\d+",
            r"\bMr\.\s*",
            r"\bMrs\.\s*",
            r"\b(Ms|Mr)\.",
        ]
        for pat in patterns:
            path = re.sub(pat, ' ', path)

        # Remove date words
        try:
            words = path.split()
            cleaned_words = [w for w in words if not _is_date_word(w)]
            path = ' '.join(cleaned_words)
        except ValueError:
            pass

    # Normalize whitespace
    path = path.replace("-", " ")
    path = ' '.join(path.split())
    return path.strip()


def _is_date_word(word):
    """Check if a word is a date."""
    try:
        dateutil_parse(word, fuzzy=False)
        return True
    except (ValueError, OverflowError):
        return False


def _fuzzy_match(query, choices, score_cutoff=80):
    """Find best fuzzy match. Uses rapidfuzz if available, falls back to simple ratio."""
    if not query or not choices:
        return None
    if _use_rapidfuzz:
        result = rf_process.extractOne(query, choices, score_cutoff=score_cutoff)
        if result:
            return result[0]
        return None
    # Fallback to simple containment
    query_lower = query.lower().strip()
    best_score = 0
    best_match = None
    for choice in choices:
        choice_lower = choice.lower().strip()
        # Simple overlap score
        query_words = set(query_lower.split())
        choice_words = set(choice_lower.split())
        if not query_words:
            continue
        overlap = len(query_words & choice_words) / len(query_words) * 100
        if overlap >= score_cutoff and overlap > best_score:
            best_score = overlap
            best_match = choice
    return best_match


def _encrypt_pdf(input_path, output_path, password):
    """Encrypt a PDF file in-place with a password."""
    try:
        with open(input_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            writer = PyPDF2.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(password)
            with open(output_path, "wb") as outfile:
                writer.write(outfile)
        return True
    except Exception as e:
        print(f"Failed to encrypt {input_path}: {e}")
        return False