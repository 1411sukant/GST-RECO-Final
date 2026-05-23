import streamlit as st
import pandas as pd

# Flat structure imports (ensure these files are in the same folder as app.py)
import parser
import module1_outward
import module2_itc
import module3_gstr2b
import module4_invoice

st.set_page_config(page_title="GST Reconciliation App", layout="wide", page_icon="📊")

# --- HELPER FUNCTIONS FOR MULTIPLE FILES ---

def process_multiple_books(files, label):
    """Parses and concatenates multiple Books files (Excel or PDF)."""
    dfs = []
    if files:
        for f in files:
            if f.name.endswith('.pdf'):
                dfs.append(parser.parse_books_pdf(f.getvalue(), label))
            else:
                dfs.append(parser.parse_books_excel(f.getvalue(), label))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def process_multiple_gstr2b(files):
    """Parses and concatenates multiple GSTR-2B Excel files into a single dictionary."""
    b2b_dfs, cdnr_dfs, impz_dfs = [], [], []
    if files:
        for f in files:
            data = parser.parse_gstr2b_excel(f.getvalue())
            b2b_dfs.append(data.get('b2b', pd.DataFrame()))
            cdnr_dfs.append(data.get('b2b_cdnr', pd.DataFrame()))
            impz_dfs.append(data.get('impz', pd.DataFrame()))
    return {
        'b2b': pd.concat(b2b_dfs, ignore_index=True) if b2b_dfs else pd.DataFrame(),
        'b2b_cdnr': pd.concat(cdnr_dfs, ignore_index=True) if cdnr_dfs else pd.DataFrame(),
        'impz': pd.concat(impz_dfs, ignore_index=True) if impz_dfs else pd.DataFrame()
    }

def process_multiple_gstr1(files):
    """Parses and concatenates multiple GSTR-1 files (Excel or PDF)."""
    dfs = []
    if files:
        for f in files:
            if f.name.endswith('.pdf'):
                dfs.append(parser.parse_gstr1_pdf(f.getvalue()))
            else:
                dfs.append(parser.parse_books_excel(f.getvalue(), "GSTR-1"))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def process_multiple_ledgers(files):
    """Parses and concatenates multiple Electronic Credit Ledger files."""
    dfs = []
    if files:
        for f in files:
            dfs.append(parser.parse_credit_ledger_excel(f.getvalue()))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# --- MAIN APPLICATION ---

def main():
    st.sidebar.title("📊 GST Reconciliation")
    st.sidebar.markdown("Select a module to perform reconciliation.")
    
    app_mode = st.sidebar.radio("Navigation", [
        "Home",
        "Module 1: Outward Supplies",
        "Module 2: ITC Availment",
        "Module 3: GSTR-2B ITC",
        "Module 4: Invoice Matching"
    ])

    if app_mode == "Home":
        st.title("GST Reconciliation System")
        st.markdown("""
        Welcome to the GST Reconciliation System. Please use the sidebar to navigate between the different modules:
        * **Module 1**: Outward Supplies (Books vs GSTR-1)
        * **Module 2**: ITC Availment (Books vs Electronic Credit Ledger)
        * **Module 3**: ITC Reconciliation (Books vs GSTR-2B)
        * **Module 4**: Invoice-Level Reconciliation (Books vs GSTR-2B)
        """)

    elif app_mode == "Module 1: Outward Supplies":
        st.title("Module 1: Outward Supplies Reconciliation")
        st.markdown("Compares Books (Sales – Credit Notes) vs GSTR-1 (Portal)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            sales_files = st.file_uploader("Upload Books Sales (Excel/PDF)", type=['xlsx', 'pdf'], accept_multiple_files=True)
        with col2:
            cn_files = st.file_uploader("Upload Books Credit Notes (Excel/PDF)", type=['xlsx', 'pdf'], accept_multiple_files=True)
        with col3:
            gstr1_files = st.file_uploader("Upload GSTR-1 (Excel/PDF)", type=['xlsx', 'pdf'], accept_multiple_files=True)
            
        if st.button("Run Reconciliation"):
            if sales_files and gstr1_files:
                with st.spinner("Parsing files and reconciling..."):
                    sales_df = process_multiple_books(sales_files, "Sales")
                    cn_df = process_multiple_books(cn_files, "Credit Notes")
                    gstr1_df = process_multiple_gstr1(gstr1_files)
                    
                    results = module1_outward.reconcile_outward(sales_df, cn_df, gstr1_df)
                    module1_outward.display_module1(results)
            else:
                st.error("Please upload at least one Books Sales file and one GSTR-1 file.")

    elif app_mode == "Module 2: ITC Availment":
        st.title("Module 2: ITC Availment Reconciliation")
        st.markdown("Compares Books Purchase/Journal (net of Debit Notes) vs Electronic Credit Ledger")
        
        col1, col2 = st.columns(2)
        with col1:
            pur_files = st.file_uploader("Upload Purchase Register (Excel)", type=['xlsx'], accept_multiple_files=True)
            dn_files = st.file_uploader("Upload Debit Notes (Excel) [Optional]", type=['xlsx'], accept_multiple_files=True)
        with col2:
            jnl_files = st.file_uploader("Upload Journal Register (Excel) [Optional]", type=['xlsx'], accept_multiple_files=True)
            ledger_files = st.file_uploader("Upload Electronic Credit Ledger (Excel)", type=['xlsx'], accept_multiple_files=True)
            
        if st.button("Run Reconciliation"):
            if pur_files and ledger_files:
                with st.spinner("Parsing files and reconciling..."):
                    pur_df = process_multiple_books(pur_files, "Purchase")
                    jnl_df = process_multiple_books(jnl_files, "Journal")
                    dn_df = process_multiple_books(dn_files, "Debit Notes")
                    ledger_df = process_multiple_ledgers(ledger_files)
                    
                    results = module2_itc.reconcile_itc(pur_df, jnl_df, dn_df, ledger_df)
                    module2_itc.display_module2(results)
            else:
                st.error("Please upload the Purchase Register and Electronic Credit Ledger.")

    elif app_mode == "Module 3: GSTR-2B ITC":
        st.title("Module 3: ITC Reconciliation (Books vs GSTR-2B)")
        st.markdown("Net Books (Purchase + Journal - Debit Notes) vs Aggregated GSTR-2B")
        
        col1, col2 = st.columns(2)
        with col1:
            pur_files = st.file_uploader("Upload Purchase Register (Excel)", type=['xlsx'], key='m3_pur', accept_multiple_files=True)
            dn_files = st.file_uploader("Upload Debit Notes (Excel) [Optional]", type=['xlsx'], key='m3_dn', accept_multiple_files=True)
        with col2:
            jnl_files = st.file_uploader("Upload Journal Register (Excel) [Optional]", type=['xlsx'], key='m3_jnl', accept_multiple_files=True)
            gstr2b_files = st.file_uploader("Upload GSTR-2B (Excel)", type=['xlsx'], key='m3_2b', accept_multiple_files=True)
            
        if st.button("Run Reconciliation"):
            if pur_files and gstr2b_files:
                with st.spinner("Parsing files and reconciling..."):
                    pur_df = process_multiple_books(pur_files, "Purchase")
                    jnl_df = process_multiple_books(jnl_files, "Journal")
                    dn_df = process_multiple_books(dn_files, "Debit Notes")
                    gstr2b_data = process_multiple_gstr2b(gstr2b_files)
                    
                    results = module3_gstr2b.reconcile_gstr2b(pur_df, jnl_df, dn_df, gstr2b_data)
                    module3_gstr2b.display_module3(results)
            else:
                st.error("Please upload the Purchase Register and GSTR-2B file.")

    elif app_mode == "Module 4: Invoice Matching":
        st.title("Module 4: Invoice-Level Reconciliation Report")
        st.markdown("Matches Books invoices vs GSTR-2B invoices by GSTIN + Invoice Number.")
        
        col1, col2 = st.columns(2)
        with col1:
            pur_files = st.file_uploader("Upload Purchase Register (Excel)", type=['xlsx'], key='m4_pur', accept_multiple_files=True)
            dn_files = st.file_uploader("Upload Debit Notes (Excel) [Optional]", type=['xlsx'], key='m4_dn', accept_multiple_files=True)
        with col2:
            jnl_files = st.file_uploader("Upload Journal Register (Excel) [Optional]", type=['xlsx'], key='m4_jnl', accept_multiple_files=True)
            gstr2b_files = st.file_uploader("Upload GSTR-2B (Excel)", type=['xlsx'], key='m4_2b', accept_multiple_files=True)
            
        if st.button("Run Reconciliation"):
            if pur_files and gstr2b_files:
                with st.spinner("Parsing files and reconciling at invoice level..."):
                    pur_df = process_multiple_books(pur_files, "Purchase")
                    jnl_df = process_multiple_books(jnl_files, "Journal")
                    dn_df = process_multiple_books(dn_files, "Debit Notes")
                    gstr2b_data = process_multiple_gstr2b(gstr2b_files)
                    
                    results = module4_invoice.reconcile_invoices(pur_df, jnl_df, dn_df, gstr2b_data)
                    module4_invoice.display_module4(results)
            else:
                st.error("Please upload the Purchase Register and GSTR-2B file.")

if __name__ == "__main__":
    main()
