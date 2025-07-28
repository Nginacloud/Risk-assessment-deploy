import streamlit as st
import pandas as pd
from collections import defaultdict
import re
import pdfplumber
import docx
import fitz

st.set_page_config(page_title="Risk Assessment Tool", layout="centered")
st.title("Risk Assessment Tool")

# FILE TEXT EXTRACTOR 
def extract_text(file, password=None):
    if file.type == "application/pdf":
        try:
            file_bytes = file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if doc.needs_pass and (not password or not doc.authenticate(password)):
                raise ValueError("PDF is encrypted and password is missing or incorrect.")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            st.error(f"Failed to extract text from PDF: {e}")
            return ""
    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        return file.read().decode("utf-8")


# M-PESA SECTION 
def categorize_mpesa(Details):
    Details_lower = Details.lower()
    if "airtime" in Details_lower:
        return "Airtime"
    if any(x in Details_lower for x in ["bet", "game", "betika", "sportpesa"]):
        return "Betting"
    if any(x in Details_lower for x in ["fuel", "petroleum", "gas", "diesel", "oil"]):
        return "Fuel"
    if any(x in Details_lower for x in ["loan", "fuliza", "overdraft"]):
        return "Loan"
    if "pay bill" in Details_lower or "paybill" in Details_lower:
        return "Pay Bill"
    if "buy goods" in Details_lower or "merchant payment" in Details_lower:
        return "Buy Goods"
    if "withdraw" in Details_lower or "agent" in Details_lower:
        return "Agent Withdrawal"
    else:
        return "Other"


def process_mpesa(df):
    transactions = []

    for _, row in df.iterrows():
        if str(row["Transaction Status"]).lower() != "completed":
            continue  # Only process completed transactions

        Details = str(row["Details"])
        paid_in = row.get("Paid In", 0) or 0
        withdrawn = row.get("Withdrawn", 0) or 0

        # Clean up amounts
        try:
            paid_in = float(str(paid_in).replace(",", ""))
        except ValueError:
            paid_in = 0.0
        try:
            withdrawn = float(str(withdrawn).replace(",", ""))
        except ValueError:
            withdrawn = 0.0

        # Determine net amount (positive for inflow, negative for outflow)
        amount = paid_in if paid_in > 0 else -withdrawn

        # Skip if both are zero
        if amount == 0:
            continue

        base_category = categorize_mpesa(Details)

        # Inflow or Outflow
        direction = "Inflow" if amount > 0 else "Outflow"

        # Overrides for Loan and Other
        if base_category == "Loan":
            category = "Loan Disbursement" if amount > 0 else "Loan Repayment"
        elif base_category == "Other":
            category = "Other (Inflow)" if amount > 0 else "Other (Outflow)"
        else:
            category = base_category

        transactions.append({
            "Details": Details.strip(),
            "Amount": abs(amount),
            # "Inflow/Outflow": direction,  # optional
            "Category": category
        })

    if not transactions:
        return None, None

    df_result = pd.DataFrame(transactions)

    # Group and summarize
    summary = df_result.groupby("Category")["Amount"].sum().reset_index()
    total = df_result["Amount"].sum()
    summary["Percentage"] = (summary["Amount"] / total * 100).round(2)

    return df_result, summary


# CRB SECTION 
def extract_crb_data(text):
    name_match = re.search(r'REPORTED NAMES:\s+(.*)', text)
    id_match = re.search(r'NATIONAL ID\s+:\s+(\d+)', text)
    phone_match = re.search(r'Phone Number\(s\)[^\n]*\n\s*([\d, ]+)', text)
    email_match = re.search(r'Email Address[^\n]*\n\s*([^\s]+@[^\s]+)', text)

    bio_data = {
        "Name": name_match.group(1).strip() if name_match else "N/A",
        "National ID": id_match.group(1).strip() if id_match else "N/A",
        "Phone Number(s)": phone_match.group(1).strip() if phone_match else "N/A",
        "Email": email_match.group(1).strip() if email_match else "N/A",
    }

    metro = re.search(r'Metro-Score©\s+(\d+)', text)
    ppi = re.search(r'PPI©\s+(M\d)', text)
    pd = re.search(r'Probability Of Default©\s+(\d+\s?%)', text)

    credit_scores = {
        "Metro Score": int(metro.group(1)) if metro else "N/A",
        "PPI": ppi.group(1) if ppi else "N/A",
        "Probability of Default": pd.group(1).strip() if pd else "N/A",
        "Interpretation": ""
    }

    metro_val = int(metro.group(1)) if metro else None
    ppi_val = ppi.group(1) if ppi else None
    if metro_val:
        if metro_val < 400:
            credit_scores["Interpretation"] += "High Risk: Credit score indicates possible defaults.\n"
        elif metro_val < 600:
            credit_scores["Interpretation"] += "Medium Risk: Caution advised.\n"
        else:
            credit_scores["Interpretation"] += "Low Risk: Good credit standing.\n"
    if ppi_val:
        if ppi_val in ["M1", "M2"]:
            credit_scores["Interpretation"] += "Positive repayment behavior."
        elif ppi_val in ["M3", "M4", "M5"]:
            credit_scores["Interpretation"] += "Watch for occasional delays."
        else:
            credit_scores["Interpretation"] += "Poor repayment trend."

    emp_match = re.search(r'Employer\s*:\s*(.*)', text, re.IGNORECASE)
    salary_match = re.search(r'Salary\s*:\s*K?([\d,]+)', text, re.IGNORECASE)
    dept_match = re.search(r'Department\s*:\s*(.*)', text, re.IGNORECASE)

    employment = {
        "Employer": emp_match.group(1).strip() if emp_match else "N/A",
        "Salary": salary_match.group(1).replace(",", "") if salary_match else "N/A",
        "Department": dept_match.group(1).strip() if dept_match else "N/A"
    }

    account_match = re.search(r'Total\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', text)
    balance_match = re.search(r'Total Outstanding Balance\s+([\d,]+\.\d+)', text)

    account_summary = {
        "Total Accounts": int(account_match.group(1)) if account_match else 0,
        "Non-Performing Accounts": int(account_match.group(2)) if account_match else 0,
        "Performing Accounts With Default History": int(account_match.group(3)) if account_match else 0,
        "Performing Accounts Without Default History": int(account_match.group(4)) if account_match else 0,
        "Total Outstanding Balance": float(balance_match.group(1).replace(",", "")) if balance_match else 0.0
    }

    return {
        "Bio Data": bio_data,
        "Employment": employment,
        "Credit Scores": credit_scores,
        "Account Summary": account_summary
    }

def extract_crb_scores(text):
    metro = re.search(r'Metro-Score©\s+(\d+)', text, re.IGNORECASE)
    ppi = re.search(r'PPI©\s+([A-Z0-9]+)', text, re.IGNORECASE)
    pd = re.search(r'Probability Of Default©\s+(\d+ ?%)', text, re.IGNORECASE)

    return {
        "Metro Score": metro.group(1) if metro else "N/A",
        "PPI": ppi.group(1) if ppi else "N/A",
        "Probability of Default": pd.group(1) if pd else "N/A"
    }

# FILE UPLOAD + DISPLAY 
st.header("Upload M-PESA Statement (.txt, .pdf, .docx)")
mpesa_file = st.file_uploader("Upload M-PESA Statement", type=["txt", "pdf", "docx"], key="mpesa")

st.header("Upload CRB Report (.txt, .pdf, .docx)")
crb_file = st.file_uploader("Upload CRB Report", type=["txt", "pdf", "docx"], key="crb")

st.info("If your file is encrypted, enter the password below.")
pdf_password = st.text_input("Enter PDF Password (optional):", type="password")

# Process M-PESA
if mpesa_file:
    mpesa_text = extract_text(mpesa_file, password=pdf_password)
    #st.expander("View Extracted M-PESA Text").write(mpesa_text)  # Optional debug
    mpesa_df, mpesa_summary = process_mpesa(mpesa_text)

    if mpesa_summary is not None:
        st.subheader("M-PESA Expense Analysis")
        st.dataframe(mpesa_summary)
        st.bar_chart(mpesa_summary.set_index("Category")["Percentage"])
    else:
        st.warning("No valid M-PESA transactions found.")

# Process CRB
if crb_file:
    crb_text = extract_text(crb_file, password=pdf_password)
    crb_summary = extract_crb_data(crb_text)
    crb_scores = extract_crb_scores(crb_text)

    st.subheader("CRB Summary")
    st.json(crb_summary)

    st.subheader("Credit Risk Scores")
    st.json(crb_scores)
