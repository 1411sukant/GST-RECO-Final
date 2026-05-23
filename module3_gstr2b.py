"""
module3_gstr2b.py – ITC Reconciliation (Books vs GSTR-2B)
"""

import pandas as pd
import streamlit as st
from parser import aggregate_monthly, sort_months

TAX_COLS = ['igst', 'cgst', 'sgst']
DISPLAY_LABELS = {'igst': 'IGST', 'cgst': 'CGST', 'sgst': 'SGST', 'total_tax': 'Total Tax'}

def aggregate_gstr2b(gstr2b_data: dict) -> pd.DataFrame:
    b2b_df = gstr2b_data.get('b2b', pd.DataFrame())
    cdnr_df = gstr2b_data.get('b2b_cdnr', pd.DataFrame())
    impz_df = gstr2b_data.get('impz', pd.DataFrame())

    all_months = set()
    for df in [b2b_df, cdnr_df, impz_df]:
        if not df.empty and 'month' in df.columns:
            all_months.update(df['month'].dropna().tolist())

    all_months = sort_months(list(all_months))
    if not all_months:
        return pd.DataFrame()

    b2b_agg = aggregate_monthly(b2b_df, TAX_COLS) if not b2b_df.empty else pd.DataFrame()
    impz_agg = aggregate_monthly(impz_df, TAX_COLS) if not impz_df.empty else pd.DataFrame()

    cdnr_debit = pd.DataFrame()
    cdnr_credit = pd.DataFrame()
    if not cdnr_df.empty and 'note_type' in cdnr_df.columns:
        cdnr_debit = aggregate_monthly(
            cdnr_df[cdnr_df['note_type'].str.lower() == 'debit'].copy(), TAX_COLS
        )
        cdnr_credit = aggregate_monthly(
            cdnr_df[cdnr_df['note_type'].str.lower() == 'credit'].copy(), TAX_COLS
        )
    elif not cdnr_df.empty:
        cdnr_debit = aggregate_monthly(cdnr_df, TAX_COLS)

    def get_val(agg_df, month, col):
        if agg_df.empty or 'month' not in agg_df.columns:
            return 0.0
        row = agg_df[agg_df['month'] == month]
        return float(row.iloc[0][col]) if not row.empty and col in row.columns else 0.0

    rows = []
    for month in all_months:
        row = {'month': month}
        for col in TAX_COLS:
            b2b_val  = get_val(b2b_agg, month, col)
            impz_val = get_val(impz_agg, month, col)
            cdn_d    = get_val(cdnr_debit, month, col)
            cdn_c    = get_val(cdnr_credit, month, col)
            row[col] = round(b2b_val + impz_val + cdn_d - cdn_c, 2)
        row['total_tax'] = round(row['igst'] + row['cgst'] + row['sgst'], 2)
        rows.append(row)

    return pd.DataFrame(rows)

def reconcile_gstr2b(
    purchase_df: pd.DataFrame,
    journal_df: pd.DataFrame,
    debit_notes_df: pd.DataFrame,
    gstr2b_data: dict,
) -> dict:
    purchase_agg = aggregate_monthly(purchase_df, TAX_COLS) if not purchase_df.empty else pd.DataFrame()
    journal_agg  = aggregate_monthly(journal_df, TAX_COLS)  if not journal_df.empty  else pd.DataFrame()
    dn_agg       = aggregate_monthly(debit_notes_df, TAX_COLS) if not debit_notes_df.empty else pd.DataFrame()

    portal_agg = aggregate_gstr2b(gstr2b_data)

    all_months = set()
    for df in [purchase_agg, journal_agg, dn_agg, portal_agg]:
        if not df.empty and 'month' in df.columns:
            all_months.update(df['month'].dropna().tolist())

    all_months = sort_months(list(all_months))

    def get_row(agg_df, month):
        if agg_df.empty or 'month' not in agg_df.columns:
            return {col: 0.0 for col in TAX_COLS + ['total_tax']}
        row = agg_df[agg_df['month'] == month]
        if row.empty:
            return {col: 0.0 for col in TAX_COLS + ['total_tax']}
        return row.iloc[0].to_dict()

    result = {}
    for month in all_months:
        pur = get_row(purchase_agg, month)
        jnl = get_row(journal_agg, month)
        dn  = get_row(dn_agg, month)
        por = get_row(portal_agg, month)

        books_net = {}
        for col in TAX_COLS:
            books_net[col] = round(pur.get(col, 0) + jnl.get(col, 0) - dn.get(col, 0), 2)
        books_net['total_tax'] = round(
            books_net['igst'] + books_net['cgst'] + books_net['sgst'], 2
        )

        portal = {col: round(por.get(col, 0), 2) for col in TAX_COLS}
        portal['total_tax'] = round(portal['igst'] + portal['cgst'] + portal['sgst'], 2)

        diff = {col: round(books_net[col] - portal[col], 2) for col in TAX_COLS + ['total_tax']}

        result[month] = {'books': books_net, 'portal': portal, 'diff': diff}

    return result

def display_module3(reconciled: dict):
    if not reconciled:
        st.info("No reconciliation data available. Please upload the required files.")
        return

    st.markdown("### 📋 Module 3 — ITC Reconciliation (Books vs GSTR-2B)")
    st.caption(
        "**GSTR-2B** = B2B + IMPZ + CDNR-Debit − CDNR-Credit  |  "
        "**Net Books** = Purchase + Journal − Debit Notes  |  "
        "**Difference** = Books − GSTR-2B"
    )

    summary_rows = []
    for month, data in reconciled.items():
        summary_rows.append({
            'Month': month,
            'Books IGST (₹)': data['books'].get('igst', 0),
            'Books CGST (₹)': data['books'].get('cgst', 0),
            'Books SGST (₹)': data['books'].get('sgst', 0),
            'Books Total (₹)': data['books'].get('total_tax', 0),
            'GSTR-2B IGST (₹)': data['portal'].get('igst', 0),
            'GSTR-2B CGST (₹)': data['portal'].get('cgst', 0),
            'GSTR-2B SGST (₹)': data['portal'].get('sgst', 0),
            'GSTR-2B Total (₹)': data['portal'].get('total_tax', 0),
            'Diff IGST (₹)': data['diff'].get('igst', 0),
            'Diff CGST (₹)': data['diff'].get('cgst', 0),
            'Diff SGST (₹)': data['diff'].get('sgst', 0),
            'Diff Total (₹)': data['diff'].get('total_tax', 0),
        })

    sum_df = pd.DataFrame(summary_rows)
    diff_cols = [c for c in sum_df.columns if 'Diff' in c]

    st.dataframe(
        sum_df.style.map(
            lambda v: 'color: red' if isinstance(v, (int, float)) and v < 0
            else ('color: orange; font-weight: bold' if isinstance(v, (int, float)) and v > 0 else ''),
            subset=diff_cols
        ).format({c: '₹{:,.2f}' for c in sum_df.columns if '(₹)' in c}),
        use_container_width=True,
    )

    st.divider()
    st.markdown("#### 📅 Month-wise Detailed Breakdown")

    for month, data in reconciled.items():
        with st.expander(f"📆 {month}", expanded=False):
            col1, col2, col3 = st.columns(3)

            def make_rows(d):
                return [{'Field': DISPLAY_LABELS.get(k, k), 'Amount (₹)': d.get(k, 0)}
                        for k in ['igst', 'cgst', 'sgst', 'total_tax']]

            with col1:
                st.markdown("**📚 Books (Net ITC)**")
                st.dataframe(pd.DataFrame(make_rows(data['books']))
                             .style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)
            with col2:
                st.markdown("**📄 GSTR-2B Total**")
                st.dataframe(pd.DataFrame(make_rows(data['portal']))
                             .style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)
            with col3:
                st.markdown("**🔍 Difference (Books − 2B)**")
                diff_rows = [{'Field': DISPLAY_LABELS.get(k, k), 'Difference (₹)': data['diff'].get(k, 0)}
                             for k in ['igst', 'cgst', 'sgst', 'total_tax']]
                df_d = pd.DataFrame(diff_rows)

                def color_diff(val):
                    if isinstance(val, (int, float)):
                        if val < 0:
                            return 'color: red; font-weight: bold'
                        elif val > 0:
                            return 'color: orange; font-weight: bold'
                        return 'color: green'
                    return ''

                st.dataframe(
                    df_d.style.map(color_diff, subset=['Difference (₹)'])
                              .format({'Difference (₹)': '₹{:,.2f}'}),
                    use_container_width=True,
                )

    st.divider()
    st.markdown("#### 🔢 Grand Totals")
    gt_data = {'Category': ['Books (Net)', 'GSTR-2B', 'Difference']}
    for col_key in ['igst', 'cgst', 'sgst', 'total_tax']:
        gt_data[DISPLAY_LABELS[col_key] + ' (₹)'] = [
            sum(d['books'].get(col_key, 0) for d in reconciled.values()),
            sum(d['portal'].get(col_key, 0) for d in reconciled.values()),
            sum(d['diff'].get(col_key, 0) for d in reconciled.values()),
        ]
    gt_df = pd.DataFrame(gt_data)
    st.dataframe(gt_df.style.format({c: '₹{:,.2f}' for c in gt_df.columns if '(₹)' in c}),
                 use_container_width=True)
