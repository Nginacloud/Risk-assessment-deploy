import streamlit as st
import pandas as pd
import re
import fitz  # PyMuPDF
import docx

#st.set_page_config(page_title="Universal Statement Analyzer", layout="centered")
#st.title("Universal M-PESA & Bank Statement Analyzer")

#  TEXT EXTRACTOR 
def extract_text(file, password=None):
    try:
        if file.type == "application/pdf":
            file_bytes = file.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if doc.needs_pass and (not password or not doc.authenticate(password)):
                raise ValueError("PDF is encrypted and password is missing or incorrect.")
            return "\n".join(page.get_text() for page in doc)

        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            docx_file = docx.Document(file)
            return "\n".join(p.text for p in docx_file.paragraphs)

        else:
            return file.read().decode("utf-8")

    except Exception as e:
        st.error(f"Error extracting text from {file.name}: {e}")
        return ""

#  CATEGORIZATION LOGIC 
def categorize_mpesa(details):
    text = details.lower().strip()
    patterns = {
        "Fuel": r"\b(fuel|petroleum|gas|diesel|oil|petrol|rubis|shell|totalenergies)\b",
        "Shopping": r"(supermarket|quickmart|naivas|chandarana|magunas|carrefour)",
        "Utilities": r"(kplc|electric|prepaid|expressway|water)",
        "Airtime/Data": r"\bairtime\b|\bbundle\b",
        "Betting": r"(betika|sportpesa|odibet|jackpot)",
        "Pay Bill": r"(pay bill|paybill)",
        "Buy Goods": r"(buy goods|merchant payment|till)",
        "Agent Withdrawal": r"(withdraw|agent)",
        "Income": r"\bpayment from\b|salary|salarie|inward payment",
        "Loan Repayment": r"(od loan repayment|overdraw)",
        "Credit": r"(watu credit|kopo kopo|kcb m-pesa|momentum|lin cap|mogo)"
    }

    for category, pattern in patterns.items():
        if re.search(pattern, text):
            return category
    return "Other"

#  M-PESA PROCESSOR 
def process_mpesa(text):
    lines = text.split('\n')
    transactions = []

    for i, line in enumerate(lines):
        if "Completed" in line:
            match = re.search(r'Completed[\s-]*(-?\d{1,3}(?:,\d{3})*(?:\.\d{2}))', line)
            if not match and i + 1 < len(lines):
                match = re.search(r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{2}))', lines[i + 1])

            if match:
                try:
                    amount = float(match.group(1).replace(",", ""))
                    details_lines = [line]
                    for j in range(1, len(lines) - i):
                        if "Completed" in lines[i + j]:
                            break
                        details_lines.append(lines[i + j])
                    details = " ".join(details_lines).strip()
                    direction = "Inflow" if amount > 0 else "Outflow"
                    category = categorize_mpesa(details)
                    if category == "Other":
                        category = f"Other ({direction})"

                    transactions.append({
                        "Details": details,
                        "Amount": abs(amount),
                        "Inflow/Outflow": direction,
                        "Category": category
                    })
                except:
                    continue

    if not transactions:
        return None, None

    df = pd.DataFrame(transactions)
    summary = df.groupby("Category")["Amount"].sum().reset_index()
    summary["Count"] = df.groupby("Category")["Amount"].count().values
    return df, summary

#  BANK PROCESSOR 
def process_bank(text):
    lines = text.splitlines()
    transactions = []
    i = 0

    while i < len(lines) - 1:
        line = lines[i].strip()
        if re.match(r"\d{2}/\d{2}/\d{4}", line):
            date = line
            narration_lines = []
            j = i + 1
            while j < len(lines):
                amt_line = lines[j].strip()
                amt_match = re.match(r"\d{2}/\d{2}/\d{4}\s+(-?[\d,]+\.\d{2})\s+[\d,.]+[CD]R\s+[\d,.]+[CD]R", amt_line)
                if amt_match:
                    try:
                        amount = float(amt_match.group(1).replace(",", ""))
                        direction = "Inflow" if amount > 0 else "Outflow"
                        narration = " ".join(narration_lines).strip()
                        category = categorize_mpesa(narration)
                        if category == "Other":
                            category = f"Other ({direction})"
                        transactions.append({
                            "Date": date,
                            "Details": narration,
                            "Amount": abs(amount),
                            "Inflow/Outflow": direction,
                            "Category": category
                        })
                    except:
                        pass
                    i = j
                    break
                else:
                    narration_lines.append(amt_line)
                    j += 1
        i += 1

    if not transactions:
        return None, None

    df = pd.DataFrame(transactions)
    summary = df.groupby("Category")["Amount"].sum().reset_index()
    summary["Count"] = df.groupby("Category")["Amount"].count().values
    return df, summary

#  DOCUMENT CLASSIFIER 
def extract_and_classify(file, password=None):
    text = extract_text(file, password)
    if "mpesa" in file.name.lower():
        doc_type = "mpesa"
    elif "statement" in text.lower() or "ledger balance" in text.lower():
        doc_type = "bank"
    else:
        doc_type = "unknown"
    return {"filename": file.name, "text": text, "type": doc_type}

def process_document(doc):
    text = doc["text"]
    if doc["type"] == "mpesa":
        df, summary = process_mpesa(text)
        return {"type": "mpesa", "df": df, "summary": summary}
    elif doc["type"] == "bank":
        df, summary = process_bank(text)
        return {"type": "bank", "df": df, "summary": summary}
    else:
        return {"type": "unknown", "error": "Document type not recognized."}

#  STREAMLIT UI 
st.header("Upload Your M-PESA and Bank Statements")
uploaded_files = st.file_uploader("Choose files", type=["pdf", "txt", "docx"], accept_multiple_files=True)

pdf_password = st.text_input("Enter PDF password (if any):", type="password")

if uploaded_files:
    for file in uploaded_files:
        doc = extract_and_classify(file, password=pdf_password)
        result = process_document(doc)

        st.markdown(f"---\n### 📄 File: `{doc['filename']}`")

        if result["type"] in ["mpesa", "bank"]:
            st.write(f"**Detected Type**: {result['type'].upper()}")
            if result["summary"] is not None:
                st.dataframe(result["summary"])
                st.bar_chart(result["summary"].set_index("Category")["Count"])
            else:
                st.warning("No transactions found.")
        else:
            st.warning(result.get("error", "Unable to process this file."))
