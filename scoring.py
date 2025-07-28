import streamlit as st
import pdfplumber
import pandas as pd
import matplotlib.pyplot as plt
import re
from io import StringIO

st.set_page_config(page_title=" Credit Risk Analysis Tool", layout="wide")
st.title(" Credit Risk Analysis Dashboard")
st.markdown("""
Upload files and analyze:
-  MPESA Statement (PDF/CSV): Spending habits.
-  CRB Statement (PDF): Credit profile & PPI score.
-  Bank Statement (PDF/CSV): Inflows vs Outflows trend.
""")

#  HELPER FUNCTIONS
def categorize_mpesa(description):
    description_lower = description.lower()
    if "airtime" in description_lower:
        return "Airtime"
    if "bet" in description_lower or "game" in description_lower or "Betika" in description_lower or "Sportpesa" in description_lower:
        return "Betting"
    if "petroleum" in description_lower or "fuel" in description_lower or "gas" in description_lower or "diesel" in description_lower or "oil" in description_lower:
        return "Petroleum"
    if "loan" in description_lower or "overdraft" in description_lower or "fuliza" in description_lower:
        return "Loans"
    else:
        return "Other"

def extract_text_from_pdf(file, password=None):
    with pdfplumber.open(file, password=password) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
# extract_text_from_pdf(file):
 #   with pdfplumber.open(file) as pdf:
  #      return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

def parse_mpesa_from_text(text):
    lines = text.split('\n')
    transactions = []
    for line in lines:
        if "Ksh" in line:
            parts = line.split()
            try:
                amount = float(parts[-1].replace(",", "").replace("Ksh", ""))
                transactions.append({"Description": " ".join(parts[:-1]), "Amount": amount})
            except:
                continue
    return pd.DataFrame(transactions)

def parse_bank_from_text(text):
    lines = text.split('\n')
    transactions = []
    for line in lines:
        if "Ksh" in line:
            parts = line.split()
            try:
                amount = float(parts[-1].replace(",", "").replace("Ksh", ""))
                transactions.append({"Description": " ".join(parts[:-1]), "Amount": amount})
            except:
                continue
    return pd.DataFrame(transactions)

def extract_ppi(text):
    match = re.search(r"The metropol PPI.*?indicates an average late payment of 0 to 10 days.*?M(\d)", text, re.IGNORECASE)
    return f"M{match.group(1)}" if match else "Unknown"

def extract_accounts(text):
    pattern = r"Performing Account Without Default History.*?Principal Amount\s+(\d+\.\d+).*?Account Opened\s+(\d{4}-\d{2}-\d{2})"
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"amount": float(m[0]), "opened": pd.to_datetime(m[1])} for m in matches]

def assess_risk(ppi, accounts):
    if ppi == "M1" and all(a['amount'] < 1000 for a in accounts):
        return " LOW RISK"
    elif ppi in ["M2", "M3"]:
        return " MODERATE RISK"
    else:
        return " HIGH RISK"

# MPESA ANALYSIS
def mpesa_analysis():
    st.subheader("MPESA Statement Analysis")
    uploaded_file = st.file_uploader("Upload MPESA Statement (PDF or CSV):", type=["pdf", "csv"])

    pdf_password = st.text_input("Enter PDF Password (if any):", type="password")
    if uploaded_file:
        if uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
        else:
            text = extract_text_from_pdf(uploaded_file, password=pdf_password)
            df = parse_mpesa_from_text(text)

        st.write("MPESA Statement Loaded.")
        st.dataframe(df.head())

        if "Details" in df.columns and "Amount" in df.columns:
            df["Category"] = df["Details"].apply(categorize_mpesa)
            spend_data = df[df["Amount"] < 0].groupby("Category")["Amount"].sum().abs()
            st.write("Spending by Category:", spend_data)
            fig, ax = plt.subplots()
            spend_data.plot(kind="pie", autopct="%1.1f%%", ax=ax, title="Spending Habits")
            ax.set_ylabel("")
            st.pyplot(fig)

#  CRB ANALYSIS
def crb_analysis():
    st.subheader(" CRB Report Analyzer")
    uploaded_file = st.file_uploader("Upload CRB Report (PDF only):", type=["pdf"])
    if uploaded_file:
        text = extract_text_from_pdf(uploaded_file)
        ppi = extract_ppi(text)
        accounts = extract_accounts(text)
        risk_level = assess_risk(ppi, accounts)

        st.markdown(f"**Payment Performance Index (PPI):** `{ppi}`")
        st.markdown(f"**Number of Accounts:** `{len(accounts)}`")
        st.markdown(f"**Total Borrowed:** `KES {sum(a['amount'] for a in accounts):,.2f}`")
        st.markdown(f"**Risk Assessment:** `{risk_level}`")

        if accounts:
            df = pd.DataFrame(accounts).sort_values("opened")
            st.subheader(" Credit Activity Over Time")
            fig, ax = plt.subplots()
            ax.plot(df["opened"], df["amount"], marker='o', linestyle='-')
            ax.set_title("Loan Amounts vs. Date Opened")
            ax.set_xlabel("Date Opened")
            ax.set_ylabel("KES Amount")
            ax.grid(True)
            st.pyplot(fig)

            st.subheader(" Account Breakdown")
            st.dataframe(df.rename(columns={"amount": "Amount (KES)", "opened": "Date Opened"}))

#  BANK ANALYSIS
def bank_analysis():
    st.subheader(" Bank Statement Analysis")
    uploaded_file = st.file_uploader("Upload Bank Statement (PDF or CSV):", type=["pdf", "csv"])
    if uploaded_file:
        if uploaded_file.type == "text/csv":
            df = pd.read_csv(uploaded_file)
        else:
            text = extract_text_from_pdf(uploaded_file)
            df = parse_bank_from_text(text)

        st.write(" Bank Statement Loaded.")
        st.dataframe(df.head())

        if "Amount" in df.columns:
            total_inflow = df[df["Amount"] > 0]["Amount"].sum()
            total_outflow = df[df["Amount"] < 0]["Amount"].sum().abs()
            trend = df["Amount"].cumsum()

            st.write(f"**Total Inflow:** KSh {total_inflow:,.2f}")
            st.write(f"**Total Outflow:** KSh {total_outflow:,.2f}")

            fig, ax = plt.subplots()
            trend.plot(title="Cash Flow Trend Over Time", ax=ax, color="green")
            ax.set_xlabel("Transactions")
            ax.set_ylabel("Cumulative Balance")
            st.pyplot(fig)

# MAIN TABS
tabs = st.selectbox("Choose Analysis Type:", ["MPESA Statement", "CRB Report", "Bank Statement"])
if tabs == "MPESA Statement":
    mpesa_analysis()
elif tabs == "CRB Report":
    crb_analysis()
elif tabs == "Bank Statement":
    bank_analysis()
