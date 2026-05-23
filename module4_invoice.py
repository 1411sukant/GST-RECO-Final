"""
module4_invoice.py – Invoice-Level Reconciliation Report
Matches Books invoices vs GSTR-2B invoices by GSTIN + Invoice Number.
"""

import pandas as pd
import streamlit as st
import numpy as np

AMOUNT_TOLERANCE = 1.0   
TAX_COLS = ['igst', 'cgst', 'sgst']
DISPLAY_COLS = ['gstin', 'invoice_no', 'invoice_date', 'igst', 'cgst', 'sgst', 'total_tax']

def _prepare_books(purchase_df: pd.DataFrame, journal_df: pd.DataFrame,
                   debit_notes_df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for df in [purchase_df, journal_df]:
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    books = pd.concat(frames, ignore_index=True)

    books['gstin_key'] = books['gstin'].astype(str).str.strip().str.upper()
    books['inv_key'] = books['invoice_no'].astype(str).str.strip().str.upper()
    books['match_key'] = books['gstin_key'] + '||' + books['inv_key']

    for col in TAX_COLS:
        if col not in books.columns:
            books[col] = 0.0

    books_agg = books.groupby(['match_key', 'gstin_key', 'inv_key'], as_index=False).agg(
        invoice_date=('invoice_date', 'first'),
        igst=('igst', 'sum'),
        cgst=('cgst', 'sum'),
        sgst=('sgst', 'sum'),
        month=('month', 'first'),
    )
    books_agg['total_tax'] = books_agg['igst'] + books_agg['cgst'] + books_agg['sgst']

    if debit_notes_df is not None and not debit_notes_df.empty:
        dn = debit_notes_df.copy()
        dn['gstin_key'] = dn['gstin'].astype(str).str.strip().str.upper()
        dn['inv_key'] = dn['invoice_no'].astype(str).str.strip().str.upper()
        dn['match_key'] = dn['gstin_key'] + '||' + dn['inv_key']
        dn_agg = dn.groupby('match_key', as_index=False).agg(
            igst=('igst', 'sum'),
            cgst=('cgst', 'sum'),
            sgst=('sgst', 'sum'),
        )
        dn_agg.columns = ['match_key', 'dn_igst', 'dn_cgst', 'dn_sgst']
        books_agg = books_agg.merge(dn_agg, on='match_key', how='left')
        for col, dn_col in [('igst', 'dn_igst'), ('cgst', 'dn_cgst'), ('sgst', 'dn_sgst')]:
            books_agg[col] = books_agg[col] - books_agg[dn_col].fillna(0)
        books_agg = books_agg.drop(columns=['dn_igst', 'dn_cgst', 'dn_sgst'], errors='ignore')
        books_agg['total_tax'] = books_agg['igst'] + books_agg['cgst'] + books_agg['sgst']

    return books_agg

def _prepare_gstr2b(gstr2b_data: dict) -> pd.DataFrame:
    frames = []

    b2b = gstr2b_data.get('b2b', pd.DataFrame())
    if not b2b.empty:
        df = b2b.copy()
        df['note_type'] = 'Invoice'
        df['sign'] = 1
        frames.append(df)

    impz = gstr2b_data.get('impz', pd.DataFrame())
    if not impz.empty:
        df = impz.copy()
        df['note_type'] = 'Import'
        df['sign'] = 1
        frames.append(df)

    cdnr = gstr2b_data.get('b2b_cdnr', pd.DataFrame())
    if not cdnr.empty:
        df = cdnr.copy()
        if 'note_type' not in df.columns:
            df['note_type'] = 'Debit'
        df['sign'] = df['note_type'].apply(
            lambda x: -1 if str(x).lower() == 'credit' else 1
        )
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    for col in TAX_COLS:
        if col not in combined.columns:
            combined[col] = 0.0
        combined[col] = combined[col] * combined.get('sign', 1)

    combined['gstin_key'] = combined.get('gstin', pd.Series('')).astype(str).str.strip().str.upper()
    combined['inv_key'] = combined.get('invoice_no', pd.Series('')).astype(str).str.strip().str.upper()
    combined['match_key'] = combined['gstin_key'] + '||' + combined['inv_key']

    portal_agg = combined.groupby(['match_key', 'gstin_key', 'inv_key'], as_index=False).agg(
        invoice_date=('invoice_date', 'first'),
        igst=('igst', 'sum'),
        cgst=('cgst', 'sum'),
        sgst=('sgst', 'sum'),
        month=('month', 'first'),
    )
    portal_agg['total_tax'] = portal_agg['igst'] + portal_agg['cgst'] + portal_agg['sgst']
    return portal_agg

def reconcile_invoices(
    purchase_df: pd.DataFrame,
    journal_df: pd.DataFrame,
    debit_notes_df: pd.DataFrame,
    gstr2b_data: dict,
) -> dict:
    books = _prepare_books(purchase_df, journal_df, debit_notes_df)
    portal = _prepare_gstr2b(gstr2b_data)

    buckets = {
        'matched': [],
        'not_in_books': [],
        'not_in_2b': [],
        'amount_mismatch': [],
    }

    if books.empty and portal.empty:
        return {k: pd.DataFrame() for k in buckets}

    books_keys = set(books['match_key'].tolist()) if not books.empty else set()
    portal_keys = set(portal['match_key'].tolist()) if not portal.empty else set()

    books_dict  = {row['match_key']: row for _, row in books.iterrows()} if not books.empty else {}
    portal_dict = {row['match_key']: row for _, row in portal.iterrows()} if not portal.empty else {}

    common_keys = books_keys & portal_keys
    for key in common_keys:
        b_row = books_dict[key]
        p_row = portal_dict[key]

        igst_diff = abs(b_row['igst'] - p_row['igst'])
        cgst_diff = abs(b_row['cgst'] - p_row['cgst'])
        sgst_diff = abs(b_row['sgst'] - p_row['sgst'])

        if igst_diff <= AMOUNT_TOLERANCE and cgst_diff <= AMOUNT_TOLERANCE and sgst_diff <= AMOUNT_TOLERANCE:
            buckets['matched'].append({
                'GSTIN': b_row['gstin_key'],
                'Invoice No': b_row['inv_key'],
                'Date (Books)': b_row.get('invoice_date', ''),
                'Month': b_row.get('month', ''),
                'Books IGST': round(b_row['igst'], 2),
                'Books CGST': round(b_row['cgst'], 2),
                'Books SGST': round(b_row['sgst'], 2),
                '2B IGST': round(p_row['igst'], 2),
                '2B CGST': round(p_row['cgst'], 2),
                '2B SGST': round(p_row['sgst'], 2),
            })
        else:
            buckets['amount_mismatch'].append({
                'GSTIN': b_row['gstin_key'],
                'Invoice No': b_row['inv_key'],
                'Date (Books)': b_row.get('invoice_date', ''),
                'Month': b_row.get('month', ''),
                'Books IGST': round(b_row['igst'], 2),
                'Books CGST': round(b_row['cgst'], 2),
                'Books SGST': round(b_row['sgst'], 2),
                '2B IGST': round(p_row['igst'], 2),
                '2B CGST': round(p_row['cgst'], 2),
                '2B SGST': round(p_row['sgst'], 2),
                'Diff IGST': round(b_row['igst'] - p_row['igst'], 2),
                'Diff CGST': round(b_row['cgst'] - p_row['cgst'], 2),
                'Diff SGST': round(b_row['sgst'] - p_row['sgst'], 2),
            })

    for key in portal_keys - books_keys:
        p_row = portal_dict[key]
        buckets['not_in_books'].append({
            'GSTIN': p_row['gstin_key'],
            'Invoice No': p_row['inv_key'],
            'Date (2B)': p_row.get('invoice_date', ''),
            'Month': p_row.get('month', ''),
            '2B IGST': round(p_row['igst'], 2),
            '2B CGST': round(p_row['cgst'], 2),
            '2B SGST': round(p_row['sgst'], 2),
            '2B Total Tax': round(p_row['total_tax'], 2),
        })

    for key in books_keys - portal_keys:
        b_row = books_dict[key]
        buckets['not_in_2b'].append({
            'GSTIN': b_row['gstin_key'],
            'Invoice No': b_row['inv_key'],
            'Date (Books)': b_row.get('invoice_date', ''),
            'Month': b_row.get('month', ''),
            'Books IGST': round(b_row['igst'], 2),
            'Books CGST': round(b_row['cgst'], 2),
            'Books SGST': round(b_row['sgst'], 2),
            'Books Total Tax': round(b_row['total_tax'], 2),
        })

    return {k: pd.DataFrame(v) for k, v in buckets.items()}

def display_module4(buckets: dict):
    if not buckets or all(df.empty for df in buckets.values()):
        st.info("No invoice-level reconciliation data available. Please upload the required files.")
        return

    st.markdown("### 🔎 Module 4 — Invoice-Level Reconciliation Report")
    st.caption("Matching Key: **GSTIN + Invoice Number**  |  Amount Tolerance: ₹1.00")

    matched      = buckets.get('matched', pd.DataFrame())
    not_in_books = buckets.get('not_in_books', pd.DataFrame())
    not_in_2b    = buckets.get('not_in_2b', pd.DataFrame())
    mismatch     = buckets.get('amount_mismatch', pd.DataFrame())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Matched", len(matched))
    c2.metric("📥 Not in Books", len(not_in_books), delta=f"-{len(not_in_books)}" if len(not_in_books) else None, delta_color="inverse")
    c3.metric("📤 Not in GSTR-2B", len(not_in_2b), delta=f"-{len(not_in_2b)}" if len(not_in_2b) else None, delta_color="inverse")
    c4.metric("⚠️ Amount Mismatch", len(mismatch), delta=f"-{len(mismatch)}" if len(mismatch) else None, delta_color="inverse")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        f"✅ Matched ({len(matched)})",
        f"📥 Not in Books ({len(not_in_books)})",
        f"📤 Not in GSTR-2B ({len(not_in_2b)})",
        f"⚠️ Amount Mismatch ({len(mismatch)})",
    ])

    with tab1:
        st.markdown("**Invoices that match perfectly in both Books and GSTR-2B.**")
        if matched.empty:
            st.success("No data or all invoices matched perfectly.")
        else:
            num_cols = [c for c in matched.columns if any(x in c for x in ['IGST', 'CGST', 'SGST'])]
            st.dataframe(
                matched.style.format({c: '₹{:,.2f}' for c in num_cols}),
                use_container_width=True,
            )
            _download_button(matched, "matched_invoices.csv")

    with tab2:
        st.markdown("**Invoices present in GSTR-2B but NOT found in Books (Purchase/Journal Register).**")
        if not_in_books.empty:
            st.success("No such invoices found.")
        else:
            num_cols = [c for c in not_in_books.columns if any(x in c for x in ['IGST', 'CGST', 'SGST', 'Tax'])]
            st.dataframe(
                not_in_books.style.format({c: '₹{:,.2f}' for c in num_cols}),
                use_container_width=True,
            )
            _download_button(not_in_books, "not_in_books.csv")

    with tab3:
        st.markdown("**Invoices present in Books but NOT found in GSTR-2B.**")
        if not_in_2b.empty:
            st.success("No such invoices found.")
        else:
            num_cols = [c for c in not_in_2b.columns if any(x in c for x in ['IGST', 'CGST', 'SGST', 'Tax'])]
            st.dataframe(
                not_in_2b.style.format({c: '₹{:,.2f}' for c in num_cols}),
                use_container_width=True,
            )
            _download_button(not_in_2b, "not_in_gstr2b.csv")

    with tab4:
        st.markdown("**Invoices found in both, but with differing tax / value amounts.**")
        if mismatch.empty:
            st.success("No amount mismatches found.")
        else:
            diff_cols = [c for c in mismatch.columns if c.startswith('Diff')]
            num_cols  = [c for c in mismatch.columns if any(x in c for x in ['IGST', 'CGST', 'SGST'])]

            def highlight_diff(val):
                if isinstance(val, (int, float)) and val != 0:
                    return 'color: red; font-weight: bold'
                return ''

            st.dataframe(
                mismatch.style.map(highlight_diff, subset=diff_cols)
                              .format({c: '₹{:,.2f}' for c in num_cols}),
                use_container_width=True,
            )
            _download_button(mismatch, "amount_mismatch.csv")

def _download_button(df: pd.DataFrame, filename: str):
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=f"⬇️ Download {filename}",
        data=csv,
        file_name=filename,
        mime='text/csv',
    )
