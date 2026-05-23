"""
module1_outward.py – Outward Supplies Reconciliation
Compares: Books (Sales – Credit Notes) vs GSTR-1 (Portal)
"""

import pandas as pd
import streamlit as st
from modules.parser import aggregate_monthly, sort_months, MONTH_ORDER

VALUE_COLS = ['sales_value', 'export_value', 'sez_value', 'igst', 'cgst', 'sgst']
DISPLAY_LABELS = {
    'sales_value': 'Sales Value',
    'export_value': 'Export Value',
    'sez_value': 'SEZ Value',
    'igst': 'IGST',
    'cgst': 'CGST',
    'sgst': 'SGST',
    'total_tax': 'Total Tax',
}


def reconcile_outward(
    books_sales_df: pd.DataFrame,
    books_cn_df: pd.DataFrame,
    gstr1_df: pd.DataFrame,
) -> dict:
    """
    Core reconciliation logic for Module 1.
    Returns a dict keyed by month with 'books', 'portal', 'diff' sub-dicts.
    """
    # Aggregate
    sales_agg = aggregate_monthly(books_sales_df, VALUE_COLS)
    cn_agg = aggregate_monthly(books_cn_df, VALUE_COLS)
    portal_agg = aggregate_monthly(gstr1_df, VALUE_COLS)

    # All months across sources
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

        # Net Books = Sales - Credit Notes
        books_net = {}
        for col in VALUE_COLS:
            books_net[col] = round(sales_row.get(col, 0) - cn_row.get(col, 0), 2)
        books_net['total_tax'] = round(
            books_net.get('igst', 0) + books_net.get('cgst', 0) + books_net.get('sgst', 0), 2
        )

        portal = {col: round(portal_row.get(col, 0), 2) for col in VALUE_COLS}
        portal['total_tax'] = round(
            portal.get('igst', 0) + portal.get('cgst', 0) + portal.get('sgst', 0), 2
        )

        diff = {}
        for col in VALUE_COLS + ['total_tax']:
            diff[col] = round(books_net.get(col, 0) - portal.get(col, 0), 2)

        result[month] = {'books': books_net, 'portal': portal, 'diff': diff}

    return result


def _format_val(val: float) -> str:
    """Format float as Indian-style currency string."""
    if val == 0:
        return '—'
    color = 'red' if val < 0 else ('green' if val > 0 else '')
    formatted = f"₹{abs(val):,.2f}"
    if val < 0:
        formatted = f"-{formatted}"
    return formatted


def display_module1(reconciled: dict):
    """Render Module 1 results in Streamlit with vertical month-wise tabulation."""
    if not reconciled:
        st.info("No reconciliation data available. Please upload the required files.")
        return

    st.markdown("### 📊 Module 1 — Outward Supplies Reconciliation")
    st.caption("Formula: **Net Books** = Sales − Credit Notes | **Difference** = Books − GSTR-1")

    # Summary table across all months
    summary_rows = []
    for month, data in reconciled.items():
        summary_rows.append({
            'Month': month,
            'Books Sales (₹)': data['books'].get('sales_value', 0),
            'Books IGST (₹)': data['books'].get('igst', 0),
            'Books CGST (₹)': data['books'].get('cgst', 0),
            'Books SGST (₹)': data['books'].get('sgst', 0),
            'Books Total Tax (₹)': data['books'].get('total_tax', 0),
            'GSTR-1 IGST (₹)': data['portal'].get('igst', 0),
            'GSTR-1 CGST (₹)': data['portal'].get('cgst', 0),
            'GSTR-1 SGST (₹)': data['portal'].get('sgst', 0),
            'GSTR-1 Total Tax (₹)': data['portal'].get('total_tax', 0),
            'Diff IGST (₹)': data['diff'].get('igst', 0),
            'Diff CGST (₹)': data['diff'].get('cgst', 0),
            'Diff SGST (₹)': data['diff'].get('sgst', 0),
            'Diff Total Tax (₹)': data['diff'].get('total_tax', 0),
        })

    sum_df = pd.DataFrame(summary_rows)
    st.dataframe(
        sum_df.style.applymap(
            lambda v: 'color: red' if isinstance(v, (int, float)) and v < 0 else (
                'color: green' if isinstance(v, (int, float)) and v > 0 else ''
            ),
            subset=[c for c in sum_df.columns if 'Diff' in c]
        ).format({c: '₹{:,.2f}' for c in sum_df.columns if '(₹)' in c}),
        use_container_width=True,
    )

    st.divider()

    # Vertical month-wise detailed cards
    st.markdown("#### 📅 Month-wise Detailed Breakdown")

    for month, data in reconciled.items():
        with st.expander(f"📆 {month}", expanded=False):
            col1, col2, col3 = st.columns(3)

            rows_books = []
            rows_portal = []
            rows_diff = []

            for col_key in ['sales_value', 'export_value', 'sez_value', 'igst', 'cgst', 'sgst', 'total_tax']:
                label = DISPLAY_LABELS.get(col_key, col_key)
                b_val = data['books'].get(col_key, 0)
                p_val = data['portal'].get(col_key, 0)
                d_val = data['diff'].get(col_key, 0)

                rows_books.append({'Field': label, 'Amount (₹)': b_val})
                rows_portal.append({'Field': label, 'Amount (₹)': p_val})
                rows_diff.append({'Field': label, 'Difference (₹)': d_val})

            with col1:
                st.markdown("**📚 Data as per Books (Net)**")
                df_b = pd.DataFrame(rows_books)
                st.dataframe(df_b.style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

            with col2:
                st.markdown("**🌐 Data as per GSTR-1**")
                df_p = pd.DataFrame(rows_portal)
                st.dataframe(df_p.style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

            with col3:
                st.markdown("**🔍 Difference (Books − GSTR-1)**")
                df_d = pd.DataFrame(rows_diff)

                def color_diff(val):
                    if isinstance(val, (int, float)):
                        if val < 0:
                            return 'color: red; font-weight: bold'
                        elif val > 0:
                            return 'color: orange; font-weight: bold'
                        return 'color: green'
                    return ''

                st.dataframe(
                    df_d.style.applymap(color_diff, subset=['Difference (₹)'])
                              .format({'Difference (₹)': '₹{:,.2f}'}),
                    use_container_width=True,
                )

    # Grand totals
    st.divider()
    st.markdown("#### 🔢 Grand Totals")
    gt_cols = ['igst', 'cgst', 'sgst', 'total_tax', 'sales_value']
    gt_data = {'Category': ['Books (Net)', 'GSTR-1', 'Difference']}
    for col_key in gt_cols:
        total_books = sum(d['books'].get(col_key, 0) for d in reconciled.values())
        total_portal = sum(d['portal'].get(col_key, 0) for d in reconciled.values())
        total_diff = round(total_books - total_portal, 2)
        label = DISPLAY_LABELS.get(col_key, col_key)
        gt_data[f'{label} (₹)'] = [total_books, total_portal, total_diff]

    gt_df = pd.DataFrame(gt_data)
    st.dataframe(gt_df.style.format({c: '₹{:,.2f}' for c in gt_df.columns if '(₹)' in c}),
                 use_container_width=True)
