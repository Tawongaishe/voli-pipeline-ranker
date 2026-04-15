"""Google Sheets API integration — read/write with column normalization."""

import os
import pandas as pd
from config import SHEET_ID, CREDENTIALS_PATH, SHEET_TAB, COLUMN_ALIASES


def _normalize_columns(df):
    """Map actual sheet column names to canonical internal names."""
    rename_map = {}
    for col in df.columns:
        col_stripped = col.strip()
        if col_stripped in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col_stripped]
        elif col_stripped.lower() in {v.lower(): v for v in COLUMN_ALIASES.values()}:
            rename_map[col] = col_stripped.lower()
    df = df.rename(columns=rename_map)

    # Derive 'responded' from inbound/cold/warm columns if not present
    if "responded" not in df.columns:
        def _derive_responded(row):
            if str(row.get("inbound", "")).strip().upper() in ("Y", "YES", "TRUE", "1"):
                return "Inbound"
            if str(row.get("warm_intro", "")).strip().upper() in ("Y", "YES", "TRUE", "1"):
                return "Warm"
            if str(row.get("cold_outreach", "")).strip().upper() in ("Y", "YES", "TRUE", "1"):
                return "Cold"
            return ""
        df["responded"] = df.apply(_derive_responded, axis=1)

    return df


def load_from_sheets():
    """Load pipeline data from Google Sheets using gspread."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_path = os.path.abspath(CREDENTIALS_PATH)
        if not os.path.exists(creds_path):
            return None, "Credentials file not found"

        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)

        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet(SHEET_TAB)
        data = ws.get_all_records()

        if not data:
            return None, "No data in sheet"

        df = pd.DataFrame(data)
        df = _normalize_columns(df)
        return df, None

    except FileNotFoundError:
        return None, "Credentials file not found"
    except Exception as e:
        return None, str(e)


def load_from_csv(csv_path):
    """Load pipeline data from a local CSV cache."""
    try:
        df = pd.read_csv(csv_path, on_bad_lines="skip")
        df = _normalize_columns(df)
        return df, None
    except Exception as e:
        return None, str(e)


def load_data():
    """Try sheets first, fall back to CSV cache."""
    # Try Google Sheets
    df, err = load_from_sheets()
    if df is not None:
        return df, "Google Sheets", None

    # Fall back to CSV
    csv_path = os.path.join(os.path.dirname(__file__), "pipeline_cache.csv")
    if os.path.exists(csv_path):
        df, err2 = load_from_csv(csv_path)
        if df is not None:
            return df, "Local CSV cache", None
        return None, None, f"CSV error: {err2}"

    return None, None, f"Sheets error: {err}. No CSV cache found."


def write_status_to_sheet(company, new_status, notes=""):
    """Write a status update back to the Google Sheet."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_path = os.path.abspath(CREDENTIALS_PATH)
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)

        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet(SHEET_TAB)

        # Find the company row
        all_values = ws.get_all_values()
        headers = all_values[0]

        # Find column indices
        company_col = None
        status_col = None
        for i, h in enumerate(headers):
            h_stripped = h.strip()
            if h_stripped in ("Company", "Unique_ID_Company"):
                company_col = i
            if h_stripped in ("Current Status", "Status_dropdown"):
                status_col = i

        if company_col is None or status_col is None:
            return False, "Could not find company/status columns"

        for row_idx, row in enumerate(all_values[1:], start=2):
            if row[company_col].strip() == company.strip():
                ws.update_cell(row_idx, status_col + 1, new_status)
                return True, "Updated"

        return False, "Company not found in sheet"
    except Exception as e:
        return False, str(e)


def add_company_to_sheet(company_data):
    """Add a new company row to the Google Sheet."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_path = os.path.abspath(CREDENTIALS_PATH)
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)

        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet(SHEET_TAB)

        headers = ws.row_values(1)
        new_row = [""] * len(headers)
        col_map = {
            "company": ["Company", "Unique_ID_Company"],
            "status": ["Current Status", "Status_dropdown"],
            "use_case": ["Use case", "Canonical use case"],
            "tier": ["Tier"],
            "owner": ["Owner", "TG Owner"],
        }
        for key, possible_headers in col_map.items():
            val = company_data.get(key, "")
            for ph in possible_headers:
                if ph in headers:
                    new_row[headers.index(ph)] = val
                    break

        ws.append_row(new_row)
        return True, "Added"
    except Exception as e:
        return False, str(e)
