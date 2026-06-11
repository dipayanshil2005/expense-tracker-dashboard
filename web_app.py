import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. Data Access Functions ---

def init_db():
    """Creates the database and table if they don't exist yet."""
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()



def load_data():
    conn = sqlite3.connect('expenses.db')
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def add_expense_to_db(expense_date, amount, category, description):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expenses (date, amount, category, description)
        VALUES (?, ?, ?, ?)
    ''', (expense_date.strftime("%Y-%m-%d"), amount, category, description))
    conn.commit()
    conn.close()

def delete_expense_from_db(expense_id):
    """Deletes an expense from the database using its unique ID."""
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    conn.commit()
    conn.close()

# --- 2. Web App Interface ---
st.set_page_config(page_title="Expense Dashboard", page_icon="💰", layout="wide")

# --- Hide Streamlit Branding ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

st.title("💰 Advanced Expense Dashboard")

# Load our data
df = load_data()

# --- KPI Cards (Overview) ---
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

# --- TOP BAR: Filtering Options ---
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
        # We show the ID in the table now so the user knows what to delete
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
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
    
    # --- NEW: Delete Feature ---
    st.subheader("🗑️ Delete an Expense")
    if not df.empty:
        # Create a formatted list of strings for the dropdown menu
        # Example: "ID: 5 | 2023-10-27 | Food | $15.50"
        expense_options = df.apply(
            lambda row: f"ID: {row['id']} | {row['date']} | {row['category']} | ₹{row['amount']:.2f} | {row['description']}", 
            axis=1
        ).tolist()
        
        # Dropdown menu to select the expense
        selected_expense_str = st.selectbox("Select an expense to remove:", expense_options)
        
        # Delete button
        if st.button("Delete Selected Expense", type="primary"):
            # Extract the actual ID number from the string they selected
            # It splits the string by spaces and takes the second word (which is the number)
            expense_id = int(selected_expense_str.split(" ")[1])
            
            # Delete it from the database
            delete_expense_from_db(expense_id)
            
            st.success(f"Expense ID {expense_id} deleted successfully!")
            st.rerun() # Refresh the page immediately to show the update
    else:
        st.info("No expenses available to delete.")
