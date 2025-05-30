import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

from streamlit.runtime.uploaded_file_manager import UploadedFile

st.set_page_config(page_title="Simple Finance App", page_icon="💰", layout="wide")

CATEGORY_FILE = "categories.json"
CSV_FILES = "uploaded_files"
FILE_NAME = "bank_statements.parquet"


def save_categories():
    with open(CATEGORY_FILE, "w") as f:
        json.dump(st.session_state.categories, f)


def save_csv(file: UploadedFile):
    file_name = os.path.join(CSV_FILES, FILE_NAME)
    if not os.path.exists(CSV_FILES):
        os.makedirs(CSV_FILES, exist_ok=True)

    incoming_df = load_transactions(file)

    if st.session_state.dataframe is not None:
        combined_df = pd.concat(
            [st.session_state.dataframe, incoming_df], ignore_index=True
        )
        deduped_df = combined_df.drop_duplicates(
            subset=["Date", "Details", "Amount", "Debit/Credit", "Status"], keep="last"
        )
        st.session_state.dataframe = deduped_df

    incoming_df.to_parquet(file_name, index=False)


def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized" or not keywords:
            continue

        lowered_keywords = [keyword.lower().strip() for keyword in keywords]

        index = df["Details"].str.lower().str.strip().isin(lowered_keywords)
        df.loc[index, "Category"] = category

    return df


def load_transactions(file):
    try:
        df = pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]
        df["Amount"] = df["Amount"].str.replace(",", "").astype(float)
        df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")

        return categorize_transactions(df)
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None


def add_keyword_to_category(category, keyword):
    keyword = keyword.strip()
    if keyword and keyword not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()
        return True

    return False


def main():
    st.title("Simple Finance Dashboard")

    with st.form("upload", clear_on_submit=True):
        uploaded_file = st.file_uploader(
            "Upload your transaction CSV file", type=["csv"]
        )
        submit = st.form_submit_button("Upload")

    if uploaded_file and submit:
        save_csv(uploaded_file)
        st.rerun()

    if st.session_state.dataframe is not None:
        debits_df = st.session_state.dataframe[
            st.session_state.dataframe["Debit/Credit"] == "Debit"
        ].copy()
        credits_df = st.session_state.dataframe[
            st.session_state.dataframe["Debit/Credit"] == "Credit"
        ].copy()

        st.session_state.debits_df = debits_df.copy()

        tab1, tab2 = st.tabs(["Expenses (Debits)", "Payments (Credits)"])
        with tab1:
            new_category = st.text_input("New Category Name")
            add_button = st.button("Add Category")

            if add_button and new_category:
                if new_category not in st.session_state.categories:
                    st.session_state.categories[new_category] = []
                    save_categories()
                    st.rerun()

            st.subheader("Your Expenses")
            edited_df = st.data_editor(
                st.session_state.debits_df[["Date", "Details", "Amount", "Category"]],
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "Amount": st.column_config.NumberColumn(
                        "Amount", format="%.2f AED"
                    ),
                    "Category": st.column_config.SelectboxColumn(
                        "Category", options=list(st.session_state.categories.keys())
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key="category_editor",
            )

            save_button = st.button("Apply Changes", type="primary")
            if save_button:
                for idx, row in edited_df.iterrows():
                    new_category = row["Category"]
                    if new_category == st.session_state.debits_df.at[idx, "Category"]:
                        continue

                    details = row["Details"]
                    st.session_state.debits_df.at[idx, "Category"] = new_category
                    add_keyword_to_category(new_category, details)

            st.subheader("Expense Summary")
            category_totals = (
                st.session_state.debits_df.groupby("Category")["Amount"]
                .sum()
                .reset_index()
            )
            category_totals = category_totals.sort_values("Amount", ascending=False)

            st.dataframe(
                category_totals,
                column_config={
                    "Amount": st.column_config.NumberColumn("Amount", format="%.2f AED")
                },
                use_container_width=True,
                hide_index=True,
            )

            fig = px.pie(
                category_totals,
                values="Amount",
                names="Category",
                title="Expenses by Category",
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("Payments Summary")
            total_payments = credits_df["Amount"].sum()
            st.metric("Total Payments", f"{total_payments:,.2f} AED")
            st.write(credits_df)


if "categories" not in st.session_state:
    st.session_state.categories = {
        "Uncategorized": [],
    }

if "dataframe" not in st.session_state:
    st.session_state.dataframe = None

if os.path.exists(CATEGORY_FILE):
    with open(CATEGORY_FILE, "r") as f:
        st.session_state.categories = json.load(f)

if os.path.exists(os.path.join(CSV_FILES, FILE_NAME)):
    st.session_state.dataframe = pd.read_parquet(os.path.join(CSV_FILES, FILE_NAME))

main()
