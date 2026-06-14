import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- 1. Cloud Connection ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- 2. Initialize Session State ---
if 'user' not in st.session_state:
    st.session_state.user = None

# --- 3. Cloud Data Access Functions (Full CRUD) ---
def load_data():
    response = supabase.table('expenses').select("*").eq('user_id', st.session_state.user.id).execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def add_expense_to_db(expense_date, amount, category, description):
    data = {
        "user_id": st.session_state.user.id,
        "date": expense_date.strftime("%Y-%m-%d"),
        "amount": amount,
        "category": category,
        "description": description
    }
    supabase.table('expenses').insert(data).execute()

def update_expense_in_db(expense_id, expense_date, amount, category, description):
    data = {
        "date": expense_date.strftime("%Y-%m-%d"),
        "amount": amount,
        "category": category,
        "description": description
    }
    supabase.table('expenses').update(data).eq('id', expense_id).execute()

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

# --- 5. Authentication UI ---
if st.session_state.user is None:
    st.title("🔒 Welcome to Expense Tracker SaaS")
    st.write("Please log in or sign up to access your personal dashboard.")
    
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    
    with tab1:
        st.info("👋 New here? Click the **Sign Up** tab above to create an account!")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In")
            if submit:
                try:
                    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = response.user
                    st.rerun() 
                except Exception as e:
                    st.error("Invalid email or password.")
                    
    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign Up")
            if submit:
                try:
                    response = supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Account created successfully! You can now log in.")
                except Exception as e:
                    st.error(f"Error creating account: {e}")

# --- 6. Main Dashboard ---
else:
    st.sidebar.write(f"Logged in as: **{st.session_state.user.email}**")
    if st.sidebar.button("Log Out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.title("💰 Advanced Expense Dashboard")
    df = load_data()
    categories_list = ["Food", "Transport", "Utilities", "Entertainment", "Shopping", "Other"]

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
                categories_filter = ["All"] + list(df['category'].unique())
                selected_category = st.selectbox("Filter by Category", categories_filter)
                
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
            display_df = filtered_df.drop(columns=['user_id']) if 'user_id' in filtered_df.columns else filtered_df
            
            # ---> THE FIX IS RIGHT HERE <---
            display_df = display_df.sort_values(by='id', ascending=True)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # --- CSV Export Feature ---
            csv_data = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Filtered History to CSV",
                data=csv_data,
                file_name=f"expense_extract_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.write("No transactions found.")

    with tab2:
        # --- CREATE ---
        st.subheader("➕ Log a New Expense")
        with st.form("expense_form", clear_on_submit=True):
            expense_date = st.date_input("Date", datetime.today())
            amount = st.number_input("Amount (₹)", min_value=0.01, format="%.2f")
            category = st.selectbox("Category", categories_list)
            description = st.text_input("Short Description")
            
            if st.form_submit_button("Save Expense"):
                add_expense_to_db(expense_date, amount, category, description)
                st.success("Expense added successfully!")
                st.rerun()

        st.divider()
        
        # Only show Edit and Delete options if there is data
        if not df.empty:
            expense_options = df.apply(
                lambda row: f"ID: {row['id']} | {row['date']} | {row['category']} | ₹{row['amount']:.2f} | {row['description']}", 
                axis=1
            ).tolist()

            # --- UPDATE ---
            st.subheader("✏️ Edit an Existing Expense")
            selected_edit_str = st.selectbox("Select an expense to edit:", expense_options, key="edit_select")
            edit_expense_id = int(selected_edit_str.split(" ")[1])
            
            selected_row = df[df['id'] == edit_expense_id].iloc[0]
            
            with st.form("edit_form"):
                new_date = st.date_input("Date", selected_row['date'])
                new_amount = st.number_input("Amount (₹)", min_value=0.01, value=float(selected_row['amount']), format="%.2f")
                
                cat_index = categories_list.index(selected_row['category']) if selected_row['category'] in categories_list else 5
                new_category = st.selectbox("Category", categories_list, index=cat_index)
                new_description = st.text_input("Short Description", value=str(selected_row['description']))
                
                if st.form_submit_button("Update Expense"):
                    update_expense_in_db(edit_expense_id, new_date, new_amount, new_category, new_description)
                    st.success(f"Expense ID {edit_expense_id} updated successfully!")
                    st.rerun()

            st.divider()
            
            # --- DELETE ---
            st.subheader("🗑️ Delete an Expense")
            selected_del_str = st.selectbox("Select an expense to remove:", expense_options, key="del_select")
            
            if st.button("Delete Selected Expense", type="primary"):
                del_expense_id = int(selected_del_str.split(" ")[1])
                delete_expense_from_db(del_expense_id)
                st.success(f"Expense ID {del_expense_id} deleted successfully!")
                st.rerun()
        else:
            st.info("Add some expenses above to unlock editing and deleting options.")
