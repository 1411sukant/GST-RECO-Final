import streamlit as st
import pandas as pd

# Flat structure imports (ensure these files are in the same folder as app.py)
import parser
import module1_outward
import module2_itc
import module3_gstr2b
import module4_invoice

st.set_page_config(page_title="GST Reconciliation App", layout="wide", page_icon="📊")

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
            gstr1_files = st.file_uploader("Upload GSTR-1 (PDF)", type=['pdf'], accept_multiple_files=True)
            
        if st.button("Run Reconciliation"):
            if sales_files and gstr1_files:
                with st.spinner("Parsing files and reconciling..."):
                    
                    # 1. Parse Multiple Sales Files
                    sales_dfs = []
                    for f in sales_files:
                        if f.name.endswith('.pdf'):
                            sales_dfs.append(parser.parse_books_pdf(f.getvalue(), "Sales"))
                        else:
                            sales_dfs.append(parser.parse_books_excel(f.getvalue(), "Sales"))
                    sales_df = pd.concat(sales_dfs, ignore_index=True) if sales_dfs else pd.DataFrame()
                    
                    # 2. Parse Multiple Credit Note Files
                    cn_dfs = []
                    for f in cn_files:
                        if f.name.endswith('.pdf'):
                            cn_dfs.append(parser.parse_books_pdf(f.getvalue(), "Credit Notes"))
                        else:
                            cn_dfs.append(parser.parse_books_excel(f.getvalue(), "Credit Notes"))
                    cn_df = pd.concat(cn_dfs, ignore_index=True) if cn_dfs else pd.DataFrame()
                            
                    # 3. Parse Multiple GSTR-1 Files
                    gstr1_dfs = []
                    for f in gstr1_files:
                        gstr1_dfs.append(parser.parse_gstr1_pdf(f.getvalue()))
                    gstr1_df = pd.concat(gstr1_dfs, ignore_index=True) if gstr1_dfs else pd.DataFrame()
                    
                    # Reconcile and Display
                    results = module1_outward.reconcile_outward(sales_df, cn_df, gstr1_df)
                    module1_outward.display_module1(results)
            else:
                st.error("Please upload at least one Books Sales file and one GSTR-1 file.")

    elif app_mode == "Module 2: ITC Availment":
        st.title("Module 2: ITC Availment Reconciliation")
        st.markdown("Compares Books Purchase/Journal (net of Debit Notes) vs Electronic Credit Ledger")
        
        col1, col2 = st.columns(2)
        with col1:
            pur_file = st.file_uploader("Upload Purchase Register (Excel)", type=['xlsx'])
            dn_file = st.file_uploader("Upload Debit Notes (Excel) [Optional]", type=['xlsx'])
        with col2:
            jnl_file = st.file_uploader("Upload Journal Register (Excel) [Optional]", type=['xlsx'])
            credit_ledger_file = st.file_uploader("Upload Electronic Credit Ledger (Excel)", type=['xlsx'])
            
        if st.button("Run Reconciliation"):
            if pur_file and credit_ledger_file:
                with st.spinner("Parsing files and reconciling..."):
                    pur_df = parser.parse_books_excel(pur_file.getvalue(), "Purchase")
                    jnl_df = parser.parse_books_excel(jnl_file.getvalue(), "Journal") if jnl_file else pd.DataFrame()
                    dn_df = parser.parse_books_excel(dn_file.getvalue(), "Debit Notes") if dn_file else pd.DataFrame()
                    ledger_df = parser.parse_credit_ledger_excel(credit_ledger_file.getvalue())
                    
                    results = module2_itc.reconcile_itc(pur_df, jnl_df, dn_df, ledger_df)
                    module2_itc.display_module2(results)
            else:
                st.error("Please upload the Purchase Register and Electronic Credit Ledger.")

    elif app_mode == "Module 3: GSTR-2B ITC":
        st.title("Module 3: ITC Reconciliation (Books vs GSTR-2B)")
        st.markdown("Net Books (Purchase + Journal - Debit Notes) vs Aggregated GSTR-2B")
        
        col1, col2 = st.columns(2)
        with col1:
            pur_file = st.file_uploader("Upload Purchase Register (Excel)", type=['xlsx'], key='m3_pur')
            dn_file = st.file_uploader("Upload Debit Notes (Excel) [Optional]", type=['xlsx'], key='m3_dn')
        with col2:
            jnl_file = st.file_uploader("Upload Journal Register (Excel) [Optional]", type=['xlsx'], key='m3_jnl')
            gstr2b_file = st.file_uploader("Upload GSTR-2B (Excel)", type=['xlsx'], key='m3_2b')
            
        if st.button("Run Reconciliation"):
            if pur_file and gstr2b_file:
                with st.spinner("Parsing files and reconciling..."):
                    pur_df = parser.parse_books_excel(pur_file.getvalue(), "Purchase")
                    jnl_df = parser.parse_books_excel(jnl_file.getvalue(), "Journal") if jnl_file else pd.DataFrame()
                    dn_df = parser.parse_books_excel(dn_file.getvalue(), "Debit Notes") if dn_file else pd.DataFrame()
                    gstr2b_data = parser.parse_gstr2b_excel(gstr2b_file.getvalue())
                    
                    results = module3_gstr2b.reconcile_gstr2b(pur_df, jnl_df, dn_df, gstr2b_data)
                    module3_gstr2b.display_module3(results)
            else:
                st.error("Please upload the Purchase Register and GSTR-2B file.")

    elif app_mode == "Module 4: Invoice Matching":
        st.title("Module 4: Invoice-Level Reconciliation Report")
        st.markdown("Matches Books invoices vs GSTR-2B invoices by GSTIN + Invoice Number.")
        
        col1, col2 = st.columns(2)
        with col1:
            pur_file = st.file_uploader("Upload Purchase Register (Excel)", type=['xlsx'], key='m4_pur')
            dn_file = st.file_uploader("Upload Debit Notes (Excel) [Optional]", type=['xlsx'], key='m4_dn')
        with col2:
            jnl_file = st.file_uploader("Upload Journal Register (Excel) [Optional]", type=['xlsx'], key='m4_jnl')
            gstr2b_file = st.file_uploader("Upload GSTR-2B (Excel)", type=['xlsx'], key='m4_2b')
            
        if st.button("Run Reconciliation"):
            if pur_file and gstr2b_file:
                with st.spinner("Parsing files and reconciling at invoice level..."):
                    pur_df = parser.parse_books_excel(pur_file.getvalue(), "Purchase")
                    jnl_df = parser.parse_books_excel(jnl_file.getvalue(), "Journal") if jnl_file else pd.DataFrame()
                    dn_df = parser.parse_books_excel(dn_file.getvalue(), "Debit Notes") if dn_file else pd.DataFrame()
                    gstr2b_data = parser.parse_gstr2b_excel(gstr2b_file.getvalue())
                    
                    results = module4_invoice.reconcile_invoices(pur_df, jnl_df, dn_df, gstr2b_data)
                    module4_invoice.display_module4(results)
            else:
                st.error("Please upload the Purchase Register and GSTR-2B file.")

if __name__ == "__main__":
    main()
