"""
module1_outward.py – Outward Supplies Reconciliation
Compares: Books (Sales – Credit Notes) vs GSTR-1 (Portal)
"""

import pandas as pd
import streamlit as st
from parser import aggregate_monthly, sort_months, MONTH_ORDER

# Added cdn_value and amendment_value to sync with new GSTR-1 parser
VALUE_COLS = ['sales_value', 'export_value', 'sez_value', 'cdn_value', 'amendment_value', 'igst', 'cgst', 'sgst']
DISPLAY_LABELS = {
    'sales_value': 'Gross Sales (B2B+B2CS)',
    'export_value': 'Total Exports (6A+6B+6C)',
    'sez_value': 'SEZ Value',
    'cdn_value': 'Credit/Debit Notes',
    'amendment_value': 'Amendments (9A)',
    'igst': 'IGST Liability',
    'cgst': 'CGST Liability',
    'sgst': 'SGST Liability',
    'total_tax': 'Total Tax',
}

def reconcile_outward(
    books_sales_df: pd.DataFrame,
    books_cn_df: pd.DataFrame,
    gstr1_df: pd.DataFrame,
) -> dict:
    sales_agg = aggregate_monthly(books_sales_df, VALUE_COLS)
    cn_agg = aggregate_monthly(books_cn_df, VALUE_COLS)
    portal_agg = aggregate_monthly(gstr1_df, VALUE_COLS)

    all_months = set()
    for df in [sales_agg, cn_agg, portal_agg]:
        if not df.empty and 'month' in df.columns:
            all_months.update(df['month'].tolist())

    all_months = sort_months(list(all_months))

    def get_row(agg_df, month):
        if agg_df.empty:
            return {col: 0.0 for col in VALUE_COLS + ['total_tax']}
        row = agg_df[agg_df['month'] == month]
        if row.empty:
            return {col: 0.0 for col in VALUE_COLS + ['total_tax']}
        return row.iloc[0].to_dict()

    result = {}
    for month in all_months:
        sales_row = get_row(sales_agg, month)
        cn_row = get_row(cn_agg, month)
        portal_row = get_row(portal_agg, month)

        books_net = {}
        for col in VALUE_COLS:
            books_net[col] = round(sales_row.get(col, 0) - cn_row.get(col, 0), 2)
        books_net['total_tax'] = round(books_net.get('igst', 0) + books_net.get('cgst', 0) + books_net.get('sgst', 0), 2)

        portal = {col: round(portal_row.get(col, 0), 2) for col in VALUE_COLS}
        portal['total_tax'] = round(portal.get('igst', 0) + portal.get('cgst', 0) + portal.get('sgst', 0), 2)

        diff = {}
        for col in VALUE_COLS + ['total_tax']:
            diff[col] = round(books_net.get(col, 0) - portal.get(col, 0), 2)

        result[month] = {'books': books_net, 'portal': portal, 'diff': diff}

    return result

def display_module1(reconciled: dict):
    if not reconciled:
        st.info("No reconciliation data available. Please upload the required files.")
        return

    st.markdown("### 📊 Module 1 — Outward Supplies Reconciliation")
    st.caption("Formula: **Net Books** = Sales − Credit Notes | **Difference** = Books − GSTR-1")

    summary_rows = []
    for month, data in reconciled.items():
        summary_rows.append({
            'Month': month,
            'Books Net Sales (₹)': data['books'].get('sales_value', 0),
            'Books Total Tax (₹)': data['books'].get('total_tax', 0),
            'GSTR-1 Gross Sales (₹)': data['portal'].get('sales_value', 0),
            'GSTR-1 CDNR (₹)': data['portal'].get('cdn_value', 0),
            'GSTR-1 Total Tax (₹)': data['portal'].get('total_tax', 0),
            'Diff Total Tax (₹)': data['diff'].get('total_tax', 0),
        })

    sum_df = pd.DataFrame(summary_rows)
    st.dataframe(
        sum_df.style.map(
            lambda v: 'color: red' if isinstance(v, (int, float)) and v < 0 else ('color: green' if isinstance(v, (int, float)) and v > 0 else ''),
            subset=['Diff Total Tax (₹)']
        ).format({c: '₹{:,.2f}' for c in sum_df.columns if '(₹)' in c}),
        use_container_width=True,
    )

    st.divider()
    st.markdown("#### 📅 Month-wise Detailed Breakdown")

    for month, data in reconciled.items():
        with st.expander(f"📆 {month}", expanded=False):
            col1, col2, col3 = st.columns(3)
            rows_books, rows_portal, rows_diff = [], [], []

            for col_key in VALUE_COLS + ['total_tax']:
                label = DISPLAY_LABELS.get(col_key, col_key)
                b_val = data['books'].get(col_key, 0)
                p_val = data['portal'].get(col_key, 0)
                d_val = data['diff'].get(col_key, 0)

                rows_books.append({'Field': label, 'Amount (₹)': b_val})
                rows_portal.append({'Field': label, 'Amount (₹)': p_val})
                rows_diff.append({'Field': label, 'Difference (₹)': d_val})

            with col1:
                st.markdown("**📚 Data as per Books (Net)**")
                st.dataframe(pd.DataFrame(rows_books).style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

            with col2:
                st.markdown("**🌐 Data as per GSTR-1**")
                st.dataframe(pd.DataFrame(rows_portal).style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

            with col3:
                st.markdown("**🔍 Difference (Books − GSTR-1)**")
                df_d = pd.DataFrame(rows_diff)

                def color_diff(val):
                    if isinstance(val, (int, float)):
                        if val < 0: return 'color: red; font-weight: bold'
                        elif val > 0: return 'color: orange; font-weight: bold'
                        return 'color: green'
                    return ''

                st.dataframe(
                    df_d.style.map(color_diff, subset=['Difference (₹)']).format({'Difference (₹)': '₹{:,.2f}'}),
                    use_container_width=True,
                )
