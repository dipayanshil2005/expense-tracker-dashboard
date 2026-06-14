import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- 1. Supabase Connection ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 2. Initialize Session State ---
# This keeps track of who is currently logged in
if 'user' not in st.session_state:
    st.session_state.user = None

# --- 3. Cloud Data Access Functions ---
def load_data():
    # Only fetch rows where the user_id matches the person logged in!
    response = supabase.table('expenses').select("*").eq('user_id', st.session_state.user.id).execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def add_expense_to_db(expense_date, amount, category, description):
    data = {
        "user_id": st.session_state.user.id, # Tag this expense with their unique ID
        "date": expense_date.strftime("%Y-%m-%d"),
        "amount": amount,
        "category": category,
        "description": description
    }
    supabase.table('expenses').insert(data).execute()

def delete_expense_from_db(expense_id):
    supabase.table('expenses').delete().eq('id', expense_id).execute()

# --- 4. Web App UI Settings ---
st.set_page_config(page_title="Expense Dashboard", page_icon="💰", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 5. Authentication UI (The Front Door) ---
if st.session_state.user is None:
    st.title("🔒 Welcome to Expense Tracker SaaS")
    st.write("Please log in or sign up to access your personal dashboard.")
    
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In")
            if submit:
                try:
                    # Try to log them in
                    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = response.user
                    st.rerun() # Refresh page to show the dashboard
                except Exception as e:
                    st.error("Invalid email or password.")
                    
    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign Up")
            if submit:
                try:
                    # Create the new user account
                    response = supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Account created successfully! You can now log in.")
                except Exception as e:
                    st.error(f"Error creating account: {e}")

# --- 6. Main Dashboard (Only shows if logged in) ---
else:
    # Sidebar Logout Button
    st.sidebar.write(f"Logged in as: **{st.session_state.user.email}**")
    if st.sidebar.button("Log Out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.title("💰 Advanced Expense Dashboard")
    df = load_data()

    # --- KPI Cards ---
    st.subheader("Overview")
    kpi1, kpi2, kpi3 = st.columns(3)

    with kpi1:
        total_spent = df['amount'].sum() if not df.empty else 0
        st.metric(label="Total Spent", value=f"₹{total_spent:,.2f}")

    with kpi2:
        total_transactions = len(df)
        st.metric(label="Total Transactions", value=total_transactions)

    with kpi3:
        if not df.empty:
            top_category = df.groupby('category')['amount'].sum().idxmax()
            st.metric(label="Highest Spend Category", value=top_category)
        else:
            st.metric(label="Highest Spend Category", value="N/A")

    st.divider()

    # --- TOP BAR: Filtering ---
    with st.expander("🔍 Filter Your Data", expanded=True):
        filter_col1, filter_col2 = st.columns(2)
        
        if not df.empty:
            with filter_col1:
                categories = ["All"] + list(df['category'].unique())
                selected_category = st.selectbox("Filter by Category", categories)
                
            with filter_col2:
                min_date = df['date'].min()
                max_date = df['date'].max()
                date_range = st.date_input("Date Range", [min_date, max_date])
                
            if len(date_range) == 2:
                start_date, end_date = date_range
                mask = (df['date'] >= start_date) & (df['date'] <= end_date)
                if selected_category != "All":
                    mask = mask & (df['category'] == selected_category)
                filtered_df = df[mask]
            else:
                filtered_df = df
        else:
            filtered_df = df
            st.info("Add some data to see filtering options!")

    st.divider()

    # --- MAIN SCREEN: Tabs Layout ---
    tab1, tab2 = st.tabs(["📊 Dashboard View", "⚙️ Manage Data"])

    with tab1:
        st.subheader("Spending by Category (Filtered)")
        if not filtered_df.empty:
            summary_df = filtered_df.groupby('category')['amount'].sum()
            st.bar_chart(summary_df)
        else:
            st.info("No data matches your current filters.")

        st.divider()
        st.subheader("Transaction History")
        if not filtered_df.empty:
            # We drop the user_id column here just so it doesn't clutter the UI table
            display_df = filtered_df.drop(columns=['user_id']) if 'user_id' in filtered_df.columns else filtered_df
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.write("No transactions found.")

    with tab2:
        st.subheader("Log a New Expense")
        with st.form("expense_form", clear_on_submit=True):
            expense_date = st.date_input("Date", datetime.today())
            amount = st.number_input("Amount (₹)", min_value=0.01, format="%.2f")
            category = st.selectbox("Category", ["Food", "Transport", "Utilities", "Entertainment", "Shopping", "Other"])
            description = st.text_input("Short Description")
            
            submitted = st.form_submit_button("Save Expense")
            if submitted:
                add_expense_to_db(expense_date, amount, category, description)
                st.success("Expense added successfully!")
                st.rerun()

        st.divider()
        
        st.subheader("🗑️ Delete an Expense")
        if not df.empty:
            expense_options = df.apply(
                lambda row: f"ID: {row['id']} | {row['date']} | {row['category']} | ₹{row['amount']:.2f} | {row['description']}", 
                axis=1
            ).tolist()
            
            selected_expense_str = st.selectbox("Select an expense to remove:", expense_options)
            
            if st.button("Delete Selected Expense", type="primary"):
                expense_id = int(selected_expense_str.split(" ")[1])
                delete_expense_from_db(expense_id)
                st.success(f"Expense ID {expense_id} deleted successfully!")
                st.rerun()
        else:
            st.info("No expenses available to delete.")
