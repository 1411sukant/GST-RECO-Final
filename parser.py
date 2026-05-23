"""
parser.py – Core file parsing utilities for GST Reconciliation
Handles Excel and PDF inputs, keyword-based column mapping, and month normalization.
"""

import re
import pandas as pd
import numpy as np
import pdfplumber
import streamlit as st
from io import BytesIO

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

MONTH_ORDER = {
    'Apr': 1, 'May': 2, 'Jun': 3, 'Jul': 4,
    'Aug': 5, 'Sep': 6, 'Oct': 7, 'Nov': 8,
    'Dec': 9, 'Jan': 10, 'Feb': 11, 'Mar': 12,
}

MONTH_ALIASES = {
    'january': 'Jan', 'jan': 'Jan',
    'february': 'Feb', 'feb': 'Feb',
    'march': 'Mar', 'mar': 'Mar',
    'april': 'Apr', 'apr': 'Apr',
    'may': 'May',
    'june': 'Jun', 'jun': 'Jun',
    'july': 'Jul', 'jul': 'Jul',
    'august': 'Aug', 'aug': 'Aug',
    'september': 'Sep', 'sep': 'Sep', 'sept': 'Sep',
    'october': 'Oct', 'oct': 'Oct',
    'november': 'Nov', 'nov': 'Nov',
    'december': 'Dec', 'dec': 'Dec',
}

KEYWORD_MAP = {
    'sales_value': ['sale', 'job work', 'jobwork', 'sales'],
    'export_value': ['export'],
    'sez_value': ['sez'],
    'igst': ['igst', 'integrated tax', 'gst-integrated', 'gst integrated'],
    'cgst': ['cgst', 'central tax', 'gst-central', 'gst central', 'gst- central'],
    'sgst': ['sgst', 'state tax', 'gst-state', 'gst state', 'gst- state', 'utgst', 'sgst/utgst'],
    'month': ['month', 'period', 'mon'],
    'invoice_no': ['invoice no', 'invoice number', 'inv no', 'inv number', 'bill no', 'voucher no'],
    'invoice_date': ['invoice date', 'inv date', 'bill date', 'date'],
    'gstin': ['gstin', 'gst no', 'gst number', 'supplier gstin', 'party gstin'],
    'taxable_value': ['taxable value', 'taxable amount', 'assessable value', 'value'],
    'total_value': ['total value', 'total amount', 'invoice value', 'gross value'],
    'note_type': ['note type', 'type'],
    'note_no': ['note no', 'note number', 'cdn no'],
}

# ─────────────────────────────────────────────────────────────
# MONTH HELPERS
# ─────────────────────────────────────────────────────────────

def normalize_month(raw: str) -> str | None:
    if pd.isna(raw):
        return None
    raw = str(raw).strip()

    text_only = re.sub(r'[\d\-/\s]', '', raw).lower()
    if text_only in MONTH_ALIASES:
        return MONTH_ALIASES[text_only]

    m = re.match(r'([a-zA-Z]+)[\-\s]?\d{2,4}', raw)
    if m:
        key = m.group(1).lower()
        if key in MONTH_ALIASES:
            return MONTH_ALIASES[key]

    patterns = [
        r'\d{4}[\-/](\d{1,2})[\-/]\d{1,2}', 
        r'\d{1,2}[\-/](\d{1,2})[\-/]\d{4}', 
        r'(\d{1,2})[\-/]\d{4}',               
    ]
    for pat in patterns:
        m = re.search(pat, raw)
        if m:
            month_num = int(m.group(1))
            if 1 <= month_num <= 12:
                num_to_abbr = {
                    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
                    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
                    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
                }
                return num_to_abbr.get(month_num)
    return None

def sort_months(months: list) -> list:
    return sorted(months, key=lambda m: MONTH_ORDER.get(m, 99))

def extract_month_from_date(date_val) -> str | None:
    try:
        if pd.isna(date_val):
            return None
        dt = pd.to_datetime(date_val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return normalize_month(str(date_val))
        num_to_abbr = {
            1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
            5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
            9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
        }
        return num_to_abbr.get(dt.month)
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────
# COLUMN MAPPING
# ─────────────────────────────────────────────────────────────

def map_columns(df: pd.DataFrame) -> dict:
    mapping = {}
    cols_lower = {col: str(col).lower().strip() for col in df.columns}

    for std_name, keywords in KEYWORD_MAP.items():
        for actual_col, lower_col in cols_lower.items():
            if std_name in mapping:
                break
            for kw in keywords:
                if kw in lower_col:
                    mapping[std_name] = actual_col
                    break
    return mapping

def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)

# ─────────────────────────────────────────────────────────────
# EXCEL PARSERS
# ─────────────────────────────────────────────────────────────

def parse_books_excel(file_bytes: bytes, label: str = "Books") -> pd.DataFrame:
    try:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        frames = []

        for sheet in xl.sheet_names:
            try:
                df = xl.parse(sheet, header=None)
            except Exception:
                continue

            header_row = 0
            for i, row in df.iterrows():
                non_null = row.dropna()
                text_count = sum(1 for v in non_null if isinstance(v, str) and len(str(v).strip()) > 1)
                if text_count >= 3:
                    header_row = i
                    break

            df.columns = df.iloc[header_row].astype(str).str.strip()
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            df = df.dropna(how='all')

            col_map = map_columns(df)
            std_df = pd.DataFrame()

            if 'month' in col_map:
                std_df['month'] = df[col_map['month']].apply(normalize_month)
            elif 'invoice_date' in col_map:
                std_df['month'] = df[col_map['invoice_date']].apply(extract_month_from_date)
            else:
                m = normalize_month(sheet)
                if m:
                    std_df['month'] = m
                else:
                    std_df['month'] = None

            for field in ['sales_value', 'export_value', 'sez_value', 'igst', 'cgst', 'sgst', 'taxable_value', 'total_value']:
                if field in col_map:
                    std_df[field] = safe_numeric(df[col_map[field]])
                else:
                    std_df[field] = 0.0

            for field in ['invoice_no', 'invoice_date', 'gstin']:
                if field in col_map:
                    std_df[field] = df[col_map[field]].astype(str).str.strip()
                else:
                    std_df[field] = ''

            std_df['source'] = label
            std_df['sheet'] = sheet
            frames.append(std_df)

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        result = result[result['month'].notna()].copy()
        return result
    except Exception as e:
        raise ValueError(f"Error parsing Books Excel: {e}")

def parse_credit_ledger_excel(file_bytes: bytes) -> pd.DataFrame:
    try:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        frames = []

        for sheet in xl.sheet_names:
            try:
                df = xl.parse(sheet, header=None)
            except Exception:
                continue

            if df.shape[1] < 6:
                continue

            header_row = 0
            for i, row in df.iterrows():
                row_vals = [str(v).lower() for v in row if not pd.isna(v)]
                if any('credit' in v or 'debit' in v or 'igst' in v or 'date' in v for v in row_vals):
                    header_row = i
                    break

            df.columns = df.iloc[header_row].astype(str).str.strip()
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            df = df.dropna(how='all')

            col_map = map_columns(df)
            std_df = pd.DataFrame()

            col_f = df.iloc[:, 5] if df.shape[1] > 5 else pd.Series([''] * len(df))
            if 'note_type' in col_map:
                entry_col = df[col_map['note_type']]
            else:
                entry_col = col_f

            std_df['entry_type'] = entry_col.astype(str).str.strip().str.capitalize()

            if 'invoice_date' in col_map:
                std_df['month'] = df[col_map['invoice_date']].apply(extract_month_from_date)
            elif df.shape[1] > 0:
                std_df['month'] = df.iloc[:, 0].apply(extract_month_from_date)
            else:
                std_df['month'] = None

            for field in ['igst', 'cgst', 'sgst']:
                if field in col_map:
                    std_df[field] = safe_numeric(df[col_map[field]])
                else:
                    pos = {'igst': 3, 'cgst': 4, 'sgst': 5}
                    idx = pos[field]
                    if df.shape[1] > idx:
                        std_df[field] = safe_numeric(df.iloc[:, idx])
                    else:
                        std_df[field] = 0.0

            frames.append(std_df)

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        result = result[result['month'].notna()].copy()
        return result
    except Exception as e:
        raise ValueError(f"Error parsing Credit Ledger: {e}")

def parse_gstr2b_excel(file_bytes: bytes) -> dict:
    result = {'b2b': pd.DataFrame(), 'b2b_cdnr': pd.DataFrame(), 'impz': pd.DataFrame()}
    try:
        xl = pd.ExcelFile(BytesIO(file_bytes))
        sheet_names_lower = {s.lower().strip().replace(' ', '').replace('-', ''): s for s in xl.sheet_names}

        for target_key, aliases in [
            ('b2b', ['b2b', 'b2bsupplies', 'b2binvoices']),
            ('b2b_cdnr', ['b2bcdnr', 'cdnr', 'b2bcdnr', 'creditdebitnotes']),
            ('impz', ['impz', 'importofservices', 'imports', 'imp']),
        ]:
            sheet_name = None
            for alias in aliases:
                if alias in sheet_names_lower:
                    sheet_name = sheet_names_lower[alias]
                    break

            if not sheet_name:
                continue

            try:
                df = xl.parse(sheet_name, header=None)
            except Exception:
                continue

            header_row = 0
            for i, row in df.iterrows():
                non_null = [str(v).strip() for v in row if not pd.isna(v)]
                if len(non_null) >= 4:
                    header_row = i
                    break

            df.columns = df.iloc[header_row].astype(str).str.strip()
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            df = df.dropna(how='all')

            col_map = map_columns(df)
            std_df = pd.DataFrame()

            if 'invoice_date' in col_map:
                std_df['month'] = df[col_map['invoice_date']].apply(extract_month_from_date)
            else:
                if df.shape[1] > 3:
                    std_df['month'] = df.iloc[:, 3].apply(extract_month_from_date)
                else:
                    std_df['month'] = None

            for field in ['igst', 'cgst', 'sgst']:
                if field in col_map:
                    std_df[field] = safe_numeric(df[col_map[field]])
                else:
                    std_df[field] = 0.0

            for field in ['invoice_no', 'gstin']:
                if field in col_map:
                    std_df[field] = df[col_map[field]].astype(str).str.strip().str.upper()
                else:
                    std_df[field] = ''

            if target_key == 'b2b_cdnr':
                if 'note_type' in col_map:
                    std_df['note_type'] = df[col_map['note_type']].astype(str).str.strip().str.capitalize()
                else:
                    std_df['note_type'] = 'Debit'

            std_df = std_df[std_df['month'].notna()].copy()
            result[target_key] = std_df
    except Exception as e:
        raise ValueError(f"Error parsing GSTR-2B: {e}")

    return result

# ─────────────────────────────────────────────────────────────
# PDF PARSERS
# ─────────────────────────────────────────────────────────────

def _extract_pdf_tables(file_bytes: bytes) -> list[pd.DataFrame]:
    tables = []
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if table and len(table) > 1:
                        cleaned_table = [[str(cell).replace('\n', ' ').strip() if cell else '' for cell in row] for row in table]
                        df = pd.DataFrame(cleaned_table[1:], columns=cleaned_table[0])
                        df.columns = [str(c).strip() if c else f'col_{i}'
                                      for i, c in enumerate(df.columns)]
                        tables.append(df)
    except Exception as e:
        st.error(f"PDF Extraction Error: The file may be password-protected or unreadable. Details: {e}")
    return tables

def parse_books_pdf(file_bytes: bytes, label: str = "Books") -> pd.DataFrame:
    tables = _extract_pdf_tables(file_bytes)
    frames = []

    for df in tables:
        col_map = map_columns(df)
        if not any(k in col_map for k in ['igst', 'cgst', 'sgst', 'sales_value', 'taxable_value']):
            continue

        std_df = pd.DataFrame()

        if 'month' in col_map:
            std_df['month'] = df[col_map['month']].apply(normalize_month)
        elif 'invoice_date' in col_map:
            std_df['month'] = df[col_map['invoice_date']].apply(extract_month_from_date)
        else:
            std_df['month'] = None

        for field in ['sales_value', 'export_value', 'sez_value', 'igst', 'cgst', 'sgst', 'taxable_value', 'total_value']:
            if field in col_map:
                std_df[field] = safe_numeric(df[col_map[field]])
            else:
                std_df[field] = 0.0

        for field in ['invoice_no', 'invoice_date', 'gstin']:
            if field in col_map:
                std_df[field] = df[col_map[field]].astype(str).str.strip()
            else:
                std_df[field] = ''

        std_df['source'] = label
        frames.append(std_df)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result[result['month'].notna()].copy()
    return result

def parse_gstr1_pdf(file_bytes: bytes) -> pd.DataFrame:
    tables = _extract_pdf_tables(file_bytes)
    frames = []

    if not tables:
        st.warning("⚠️ No data extracted from GSTR-1 PDF. Try uploading the GSTR-1 Excel export instead.")
        return pd.DataFrame()

    for df in tables:
        text_dump = df.to_string().lower()
        has_tax = any(kw in text_dump for kw in ['igst', 'cgst', 'sgst', 'integrated', 'central', 'state'])
        has_val = any(kw in text_dump for kw in ['value', 'amount', 'taxable'])
        
        if not (has_tax or has_val):
            continue

        col_map = map_columns(df)
        std_df = pd.DataFrame()

        if 'month' in col_map:
            std_df['month'] = df[col_map['month']].apply(normalize_month)
        elif 'invoice_date' in col_map:
            std_df['month'] = df[col_map['invoice_date']].apply(extract_month_from_date)
        else:
            std_df['month'] = df.iloc[:, 0].apply(
                lambda x: normalize_month(str(x)) if not pd.isna(x) else None
            )

        for field in ['sales_value', 'export_value', 'sez_value', 'igst', 'cgst', 'sgst']:
            if field in col_map:
                std_df[field] = safe_numeric(df[col_map[field]])
            else:
                std_df[field] = 0.0

        for field in ['invoice_no', 'gstin']:
            if field in col_map:
                std_df[field] = df[col_map[field]].astype(str).str.strip()
            else:
                std_df[field] = ''

        std_df['source'] = 'GSTR-1'
        frames.append(std_df)

    if not frames:
        st.warning("⚠️ Tables found in GSTR-1 PDF lacked recognizable tax columns. Try the Excel export.")
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result[result['month'].notna()].copy()
    return result

# ─────────────────────────────────────────────────────────────
# AGGREGATION HELPERS
# ─────────────────────────────────────────────────────────────

def aggregate_monthly(df: pd.DataFrame, value_cols: list) -> pd.DataFrame:
    if df.empty or 'month' not in df.columns:
        return pd.DataFrame()

    agg_dict = {col: 'sum' for col in value_cols if col in df.columns}
    result = df.groupby('month', as_index=False).agg(agg_dict)

    for col in value_cols:
        if col not in result.columns:
            result[col] = 0.0

    result['total_tax'] = (
        result.get('igst', pd.Series(0, index=result.index)) +
        result.get('cgst', pd.Series(0, index=result.index)) +
        result.get('sgst', pd.Series(0, index=result.index))
    )

    result['sort_order'] = result['month'].map(lambda m: MONTH_ORDER.get(m, 99))
    result = result.sort_values('sort_order').drop(columns='sort_order').reset_index(drop=True)
    return result
