"""
module2_itc.py – ITC Availment Reconciliation
Compares: Books Purchase/Journal (net of Debit Notes) vs Electronic Credit Ledger
"""

import pandas as pd
import streamlit as st
from modules.parser import aggregate_monthly, sort_months

TAX_COLS = ['igst', 'cgst', 'sgst']
DISPLAY_LABELS = {
    'igst': 'IGST',
    'cgst': 'CGST',
    'sgst': 'SGST',
    'total_tax': 'Total Tax',
}


def reconcile_itc(
    purchase_df: pd.DataFrame,
    journal_df: pd.DataFrame,
    debit_notes_df: pd.DataFrame,
    credit_ledger_df: pd.DataFrame,
) -> dict:
    """
    Module 2 reconciliation logic.
    Net Books = Purchase + Journal - Debit Notes
    Portal Credit = Credit entries in the Electronic Credit Ledger
    Portal Debit (Utilized) = Debit entries (informational only)
    Difference = Net Books - Portal Credit
    """

    # Aggregate each books source
    purchase_agg = aggregate_monthly(purchase_df, TAX_COLS) if not purchase_df.empty else pd.DataFrame()
    journal_agg = aggregate_monthly(journal_df, TAX_COLS) if not journal_df.empty else pd.DataFrame()
    dn_agg = aggregate_monthly(debit_notes_df, TAX_COLS) if not debit_notes_df.empty else pd.DataFrame()

    # Aggregate Credit Ledger separately for Credit and Debit entries
    all_months = set()

    def months_from(df):
        if not df.empty and 'month' in df.columns:
            all_months.update(df['month'].dropna().tolist())

    months_from(purchase_agg)
    months_from(journal_agg)
    months_from(dn_agg)

    ledger_credit = pd.DataFrame()
    ledger_debit = pd.DataFrame()

    if not credit_ledger_df.empty and 'entry_type' in credit_ledger_df.columns:
        credit_mask = credit_ledger_df['entry_type'].str.lower().str.contains('credit', na=False)
        debit_mask = credit_ledger_df['entry_type'].str.lower().str.contains('debit', na=False)

        ledger_credit = aggregate_monthly(credit_ledger_df[credit_mask].copy(), TAX_COLS)
        ledger_debit = aggregate_monthly(credit_ledger_df[debit_mask].copy(), TAX_COLS)

        months_from(ledger_credit)
        months_from(ledger_debit)

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
        dn = get_row(dn_agg, month)
        lc = get_row(ledger_credit, month)
        ld = get_row(ledger_debit, month)

        # Net Books ITC = Purchase + Journal - Debit Notes
        books_net = {}
        for col in TAX_COLS:
            books_net[col] = round(
                pur.get(col, 0) + jnl.get(col, 0) - dn.get(col, 0), 2
            )
        books_net['total_tax'] = round(
            books_net.get('igst', 0) + books_net.get('cgst', 0) + books_net.get('sgst', 0), 2
        )

        # Portal Credit (ITC Availed)
        portal_credit = {col: round(lc.get(col, 0), 2) for col in TAX_COLS}
        portal_credit['total_tax'] = round(
            portal_credit.get('igst', 0) + portal_credit.get('cgst', 0) + portal_credit.get('sgst', 0), 2
        )

        # Portal Debit (ITC Utilized — informational)
        portal_debit = {col: round(ld.get(col, 0), 2) for col in TAX_COLS}
        portal_debit['total_tax'] = round(
            portal_debit.get('igst', 0) + portal_debit.get('cgst', 0) + portal_debit.get('sgst', 0), 2
        )

        # Difference
        diff = {}
        for col in TAX_COLS + ['total_tax']:
            diff[col] = round(books_net.get(col, 0) - portal_credit.get(col, 0), 2)

        result[month] = {
            'books': books_net,
            'portal_credit': portal_credit,
            'portal_debit': portal_debit,
            'diff': diff,
        }

    return result


def display_module2(reconciled: dict):
    """Render Module 2 results in Streamlit."""
    if not reconciled:
        st.info("No reconciliation data available. Please upload the required files.")
        return

    st.markdown("### 💳 Module 2 — ITC Availment Reconciliation")
    st.caption(
        "**Net Books ITC** = Purchase + Journal − Debit Notes  |  "
        "**Portal Credit** = 'Credit' entries in Electronic Credit Ledger  |  "
        "**Portal Debit** = ITC Utilized (informational)"
    )

    # Summary table
    summary_rows = []
    for month, data in reconciled.items():
        summary_rows.append({
            'Month': month,
            'Books IGST (₹)': data['books'].get('igst', 0),
            'Books CGST (₹)': data['books'].get('cgst', 0),
            'Books SGST (₹)': data['books'].get('sgst', 0),
            'Books Total (₹)': data['books'].get('total_tax', 0),
            'Portal Credit IGST (₹)': data['portal_credit'].get('igst', 0),
            'Portal Credit CGST (₹)': data['portal_credit'].get('cgst', 0),
            'Portal Credit SGST (₹)': data['portal_credit'].get('sgst', 0),
            'Portal Credit Total (₹)': data['portal_credit'].get('total_tax', 0),
            'Diff IGST (₹)': data['diff'].get('igst', 0),
            'Diff CGST (₹)': data['diff'].get('cgst', 0),
            'Diff SGST (₹)': data['diff'].get('sgst', 0),
            'Diff Total (₹)': data['diff'].get('total_tax', 0),
            'Utilized IGST (₹)': data['portal_debit'].get('igst', 0),
            'Utilized CGST (₹)': data['portal_debit'].get('cgst', 0),
            'Utilized SGST (₹)': data['portal_debit'].get('sgst', 0),
        })

    sum_df = pd.DataFrame(summary_rows)
    diff_cols = [c for c in sum_df.columns if 'Diff' in c]

    st.dataframe(
        sum_df.style.applymap(
            lambda v: 'color: red' if isinstance(v, (int, float)) and v < 0 else (
                'color: green' if isinstance(v, (int, float)) and v > 0 else ''
            ),
            subset=diff_cols
        ).format({c: '₹{:,.2f}' for c in sum_df.columns if '(₹)' in c}),
        use_container_width=True,
    )

    st.divider()
    st.markdown("#### 📅 Month-wise Detailed Breakdown")

    for month, data in reconciled.items():
        with st.expander(f"📆 {month}", expanded=False):
            col1, col2, col3, col4 = st.columns(4)

            def make_rows(data_dict):
                rows = []
                for col_key in ['igst', 'cgst', 'sgst', 'total_tax']:
                    rows.append({
                        'Field': DISPLAY_LABELS.get(col_key, col_key),
                        'Amount (₹)': data_dict.get(col_key, 0),
                    })
                return rows

            with col1:
                st.markdown("**📚 Books (Net ITC)**")
                df_b = pd.DataFrame(make_rows(data['books']))
                st.dataframe(df_b.style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

            with col2:
                st.markdown("**✅ Portal Credit (Availed)**")
                df_c = pd.DataFrame(make_rows(data['portal_credit']))
                st.dataframe(df_c.style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

            with col3:
                st.markdown("**🔍 Difference**")
                df_d = pd.DataFrame(make_rows(data['diff']))
                df_d.columns = ['Field', 'Difference (₹)']

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

            with col4:
                st.markdown("**ℹ️ ITC Utilized (Debit)**")
                df_u = pd.DataFrame(make_rows(data['portal_debit']))
                st.dataframe(df_u.style.format({'Amount (₹)': '₹{:,.2f}'}), use_container_width=True)

    # Grand totals
    st.divider()
    st.markdown("#### 🔢 Grand Totals")
    gt_cols = ['igst', 'cgst', 'sgst', 'total_tax']
    gt_data = {'Category': ['Books (Net)', 'Portal Credit', 'Difference', 'Utilized']}
    for col_key in gt_cols:
        gt_data[DISPLAY_LABELS[col_key] + ' (₹)'] = [
            sum(d['books'].get(col_key, 0) for d in reconciled.values()),
            sum(d['portal_credit'].get(col_key, 0) for d in reconciled.values()),
            sum(d['diff'].get(col_key, 0) for d in reconciled.values()),
            sum(d['portal_debit'].get(col_key, 0) for d in reconciled.values()),
        ]

    gt_df = pd.DataFrame(gt_data)
    st.dataframe(gt_df.style.format({c: '₹{:,.2f}' for c in gt_df.columns if '(₹)' in c}),
                 use_container_width=True)
