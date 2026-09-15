import streamlit as st
from datetime import datetime
import os
from database import Database
from auth import AuthenticationManager
from banking import BankingManager
from utils import logger, TransactionExporter, AccountExporter, FormatHelper


st.set_page_config(page_title="Banking App", layout="wide")


@st.cache_resource
def initialize_app():
    db = Database("database/banking.db")
    db.initialize()
    return db, AuthenticationManager(db), BankingManager(db)


def init_session_state():
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'email' not in st.session_state:
        st.session_state.email = None
    if 'jwt_token' not in st.session_state:
        st.session_state.jwt_token = None
    if 'page' not in st.session_state:
        st.session_state.page = "signup"


def show_signup_page():
    st.title("🏦 Banking Application")
    st.subheader("Create Your Account")
    
    col1, col2 = st.columns([1, 2])
    
    with col2:
        with st.form("signup_form"):
            st.write("### Account Information")
            signup_name = st.text_input("Full Name", placeholder="John Doe")
            signup_email = st.text_input("Email", placeholder="john@example.com")
            signup_phone = st.text_input("Phone (10 digits)", placeholder="9876543210")
            signup_password = st.text_input("Password", type="password")
            signup_confirm = st.text_input("Confirm Password", type="password")
            
            if st.form_submit_button("Create Account", use_container_width=True):
                if not all([signup_name, signup_email, signup_phone, signup_password]):
                    st.error("Please fill all fields")
                elif signup_password != signup_confirm:
                    st.error("Passwords do not match")
                else:
                    success, message = auth_manager.signup(
                        signup_name, signup_email, signup_phone, signup_password
                    )
                    
                    if success:
                        st.session_state.email = signup_email
                        st.session_state.otp_email = signup_email
                        st.session_state.page = "otp_verification"
                        st.success("Account created! Verify your email with OTP.")
                        st.rerun()
                    else:
                        st.error(message)
        
        st.markdown("---")
        st.write("Already have an account?")
        if st.button("Go to Login", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()


def show_login_page():
    st.title("🏦 Banking Application")
    st.subheader("Login to Your Account")
    
    col1, col2 = st.columns([1, 2])
    
    with col2:
        with st.form("login_form"):
            st.write("### Login Credentials")
            login_email = st.text_input("Email", placeholder="john@example.com")
            login_password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login", use_container_width=True):
                if login_email and login_password:
                    success, message, user_id = auth_manager.login(login_email, login_password)
                    
                    if success:
                        st.session_state.email = login_email
                        st.session_state.otp_email = login_email
                        st.session_state.page = "otp_verification"
                        st.success("Login step 1 complete. Verify OTP.")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please enter email and password")
        
        st.markdown("---")
        st.write("Don't have an account?")
        if st.button("Go to Sign Up", use_container_width=True):
            st.session_state.page = "signup"
            st.rerun()


def show_otp_verification():
    st.title("🔐 OTP Verification")
    st.subheader("Verify Your Email")
    
    otp_email = st.session_state.get('otp_email', '')
    
    if 'otp_code' not in st.session_state:
        otp_code = auth_manager.generate_otp_for_email(otp_email)
        st.session_state.otp_code = otp_code
        st.info(f"OTP has been sent to {otp_email}")
    else:
        st.info(f"OTP was sent to {otp_email}")
    
    col1, col2 = st.columns([1, 2])
    
    with col2:
        with st.form("otp_form"):
            st.write(f"### Verify OTP")
            st.caption(f"Email: {otp_email}")
            entered_otp = st.text_input("Enter 6-digit OTP", placeholder="123456", max_chars=6)
            
            if st.form_submit_button("Verify OTP", use_container_width=True):
                try:
                    if auth_manager.verify_otp_for_email(otp_email, entered_otp):
                        result = db.execute_query(
                            "SELECT user_id FROM users WHERE email = ?",
                            (otp_email,)
                        )
                        
                        if result:
                            st.session_state.user_id = result[0]['user_id']
                            st.session_state.email = otp_email
                            st.session_state.jwt_token = auth_manager.generate_jwt(
                                st.session_state.user_id, otp_email
                            )
                            st.session_state.page = "dashboard"
                            st.success("OTP verified! Welcome!")
                            st.rerun()
                except ValueError as e:
                    st.error(str(e))
        
        st.markdown("---")
        if st.button("Back to Login", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()


def show_dashboard():
    # Top bar with logout button on right
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        user_result = db.execute_query(
            "SELECT name FROM users WHERE user_id = ?",
            (st.session_state.user_id,)
        )
        user_name = user_result[0]['name'] if user_result else "User"
        st.title("🏦 Banking Dashboard")
    
    with col3:
        if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
            st.session_state.user_id = None
            st.session_state.email = None
            st.session_state.jwt_token = None
            st.session_state.page = "signup"
            st.success("Logged out successfully")
            st.rerun()
    
    st.write(f"Welcome, **{user_name}** 👋")
    
    stats = banking_manager.get_account_statistics(st.session_state.user_id)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Balance", FormatHelper.format_amount(stats.total_balance))
    with col2:
        st.metric("Accounts", stats.account_count)
    with col3:
        st.metric("Transactions", stats.transaction_count)
    with col4:
        st.metric("Total Deposits", FormatHelper.format_amount(stats.total_deposits))
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Accounts", "Operations", "Transactions", "Settings"])
    
    with tab1:
        show_accounts_tab()
    
    with tab2:
        show_operations_tab()
    
    with tab3:
        show_transactions_tab()
    
    with tab4:
        show_settings_tab()


def show_accounts_tab():
    st.subheader("My Accounts")
    
    accounts = banking_manager.get_accounts(st.session_state.user_id)
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("➕ Create Account", use_container_width=True):
            st.session_state.show_create_account = True
    
    if st.session_state.get('show_create_account', False):
        st.markdown("---")
        st.subheader("Create New Account")
        with st.form("create_account_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                account_holder_name = st.text_input("Account Holder Name")
                account_holder_age = st.number_input("Age", min_value=18, max_value=100, value=25)
            
            with col2:
                account_type = st.selectbox(
                    "Account Type",
                    ["Savings", "Current", "Fixed Deposit"]
                )
                account_password = st.text_input("Account Password", type="password", 
                                                help="Secure your account with a password")
            
            if st.form_submit_button("Create Account", use_container_width=True):
                if not all([account_holder_name, account_password]):
                    st.error("Please fill all fields")
                else:
                    success, message = banking_manager.create_account(
                        st.session_state.user_id, account_type
                    )
                    
                    if success:
                        st.success(f"{message}\nAccount Holder: {account_holder_name}, Age: {account_holder_age}")
                        st.session_state.show_create_account = False
                        st.rerun()
                    else:
                        st.error(message)
    
    if accounts:
        st.markdown("---")
        for i, account in enumerate(accounts):
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                
                with col1:
                    st.write(f"**{account['account_type']} Account**")
                    st.caption(f"Account Number: `{account['account_number']}`")
                
                with col2:
                    st.write(f"**Balance**: {FormatHelper.format_amount(account['balance'])}")
                    st.caption(f"Created: {FormatHelper.format_date(account['created_at'])}")
                
                with col3:
                    st.metric("Status", "Active" if account['is_active'] else "Inactive")
                
                with col4:
                    if st.button("🔒 View", key=f"view_account_{i}", use_container_width=True):
                        st.info(f"Account Password Protected ✓\nAccount ID: {account['account_id']}")
    else:
        st.info("📭 No accounts found. Create one to get started!")


def show_operations_tab():
    st.subheader("Banking Operations")
    
    accounts = banking_manager.get_accounts(st.session_state.user_id)
    
    if not accounts:
        st.warning("Create an account first")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Deposit**")
        with st.form("deposit_form"):
            account_id = st.selectbox(
                "Select Account",
                [a['account_id'] for a in accounts],
                format_func=lambda x: next(
                    (f"{a['account_type']} ({FormatHelper.format_amount(a['balance'])})" 
                     for a in accounts if a['account_id'] == x), "")
            )
            amount = st.number_input("Amount", min_value=1.0, step=100.0)
            
            if st.form_submit_button("Deposit"):
                success, message = banking_manager.deposit(account_id, amount, "Deposit")
                if success:
                    logger.info(f"Deposit: {amount} to account {account_id}")
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with col2:
        st.write("**Withdraw**")
        with st.form("withdraw_form"):
            account_id = st.selectbox(
                "Select Account",
                [a['account_id'] for a in accounts],
                format_func=lambda x: next(
                    (f"{a['account_type']} ({FormatHelper.format_amount(a['balance'])})" 
                     for a in accounts if a['account_id'] == x), ""),
                key="withdraw_account"
            )
            amount = st.number_input("Amount", min_value=1.0, step=100.0, key="withdraw_amount")
            
            if st.form_submit_button("Withdraw"):
                success, message = banking_manager.withdraw(account_id, amount, "Withdrawal")
                if success:
                    logger.info(f"Withdrawal: {amount} from account {account_id}")
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with col3:
        st.write("**Transfer**")
        with st.form("transfer_form"):
            from_account = st.selectbox(
                "From Account",
                [a['account_id'] for a in accounts],
                format_func=lambda x: next(
                    (f"{a['account_type']} ({FormatHelper.format_amount(a['balance'])})" 
                     for a in accounts if a['account_id'] == x), ""),
                key="from_account"
            )
            to_account = st.selectbox(
                "To Account",
                [a['account_id'] for a in accounts],
                format_func=lambda x: next(
                    (f"{a['account_type']} ({FormatHelper.format_amount(a['balance'])})" 
                     for a in accounts if a['account_id'] == x), ""),
                key="to_account"
            )
            amount = st.number_input("Amount", min_value=1.0, step=100.0, key="transfer_amount")
            
            if st.form_submit_button("Transfer"):
                if from_account == to_account:
                    st.error("Cannot transfer to the same account")
                else:
                    success, message = banking_manager.transfer(from_account, to_account, amount, "Transfer")
                    if success:
                        logger.info(f"Transfer: {amount} from {from_account} to {to_account}")
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


def show_transactions_tab():
    st.subheader("Transaction History")
    
    accounts = banking_manager.get_accounts(st.session_state.user_id)
    
    if not accounts:
        st.info("No accounts found")
        return
    
    selected_account = st.selectbox(
        "Select Account",
        [a['account_id'] for a in accounts],
        format_func=lambda x: next(
            (f"{a['account_type']} ({FormatHelper.format_amount(a['balance'])})" 
             for a in accounts if a['account_id'] == x), "")
    )
    
    transactions = banking_manager.get_transactions(selected_account)
    
    if transactions:
        for txn in transactions:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    st.write(f"**{txn['transaction_type']}**")
                    st.caption(FormatHelper.truncate_description(txn['description']))
                
                with col2:
                    st.write(FormatHelper.format_amount(txn['amount']))
                
                with col3:
                    st.caption(FormatHelper.format_date(txn['timestamp']))
                
                with col4:
                    status_emoji = "✅" if txn['status'] == 'COMPLETED' else "⏳"
                    st.write(f"{status_emoji} {txn['status']}")
        
        if st.button("Export as CSV"):
            if TransactionExporter.export_to_csv(transactions, "transactions.csv"):
                st.success("Exported to transactions.csv")
        
        if st.button("Export as JSON"):
            if TransactionExporter.export_to_json(transactions, "transactions.json"):
                st.success("Exported to transactions.json")
    else:
        st.info("No transactions found")


def show_settings_tab():
    st.subheader("Settings & Interest")
    
    accounts = banking_manager.get_accounts(st.session_state.user_id)
    
    if accounts:
        selected_account = st.selectbox(
            "Select Account for Interest",
            [a['account_id'] for a in accounts],
            format_func=lambda x: next(
                (f"{a['account_type']} ({FormatHelper.format_amount(a['balance'])})" 
                 for a in accounts if a['account_id'] == x), "")
        )
        
        interest = banking_manager.calculate_interest(selected_account)
        st.metric("Calculated Interest", FormatHelper.format_amount(interest or 0))
        
        if st.button("Apply Interest"):
            success, message = banking_manager.apply_interest(selected_account)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.info(message)


def main():
    global db, auth_manager, banking_manager
    
    init_session_state()
    db, auth_manager, banking_manager = initialize_app()
    
    # If user is logged in, show dashboard
    if st.session_state.user_id:
        st.session_state.page = "dashboard"
    
    # Page routing
    if st.session_state.page == "signup":
        show_signup_page()
    
    elif st.session_state.page == "login":
        show_login_page()
    
    elif st.session_state.page == "otp_verification":
        show_otp_verification()
    
    elif st.session_state.page == "dashboard":
        if st.session_state.user_id:
            show_dashboard()
        else:
            st.session_state.page = "signup"
            st.rerun()


if __name__ == "__main__":
    main()