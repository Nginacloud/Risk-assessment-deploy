import streamlit as st
import pdfplumber
import pandas as pd
import matplotlib.pyplot as plt
import re
from io import StringIO
from typing import Optional

# ------------------------------
# 1️⃣ FSV MATRIX
# ------------------------------
FSV_MATRIX = {
    "POOL A": [
        {"models": ["toyota"], "year_ranges": [(2004, 2007, 0.45), (2008, 2011, 0.50), (2012, 9999, 0.55)]},
        {"models": ["mark x", "majesta", "crown"], "year_ranges": [(2007, 9999, 0.40)]},
        {"models": ["suv"], "year_ranges": [(2012, 9999, 0.50)]},
        {"models": ["lexus"], "year_ranges": [(2008, 9999, 0.50)]},
        {"models": ["probox"], "year_ranges": [(2005, 2009, 0.40), (2010, 2013, 0.50), (2014, 9999, 0.55)]},
        {"models": ["estima"], "year_ranges": [(2008, 9999, 0.40)]},
        {"models": ["townace"], "year_ranges": [(2010, 9999, 0.50)]},
        {"models": ["isis"], "year_ranges": [(2010, 9999, 0.50)]},
        {"models": ["fielder", "premio", "allion", "harrier"], "year_ranges": [(2014, 9999, 0.70)]},
        {"models": ["toyota other"], "year_ranges": [(2014, 9999, 0.60)]},
        {"models": ["hilux", "landcruiser"], "year_ranges": [(2005, 2008, 0.40), (2009, 2012, 0.55), (2013, 9999, 0.55)]}
    ],
    "POOL B": [
        {"models": ["nissan", "mazda", "subaru", "honda", "mitsubishi", "ford", "suzuki"], "year_ranges": [(2005, 2009, 0.40), (2010, 2013, 0.50), (2014, 9999, 0.55)]},
        {"models": ["xtrail", "dualis","tiida", "march", "juke","murano","note","bluebird","serena","sylphy"], "year_ranges": [(2005, 2009, 0.40), (2010, 2013, 0.50), (2014, 9999, 0.55)]},
        {"models": ["mazda cx5 diesel"], "year_ranges": [(2007, 2008, 0.35), (2009, 2011, 0.45), (2012, 9999, 0.50)]},
        {"models": ["mazda premacy"], "year_ranges": [(2007, 9999, 0.40)]},
        {"models": ["pathfinder", "civic", "colt", "mirage", "lancer", "navara", "teana", "patrol", "wingroad", "advan"], "year_ranges": [(2007, 9999, 0.40)]},
        {"models": ["dmax isuzu"], "year_ranges": [(2006, 2009, 0.40), (2010, 2012, 0.50), (2013, 9999, 0.55)]},
        {"models": ["ford ranger"], "year_ranges": [(2008, 2011, 0.40), (2012, 9999, 0.45)]}
    ],
    "POOL C": [
        {"models": ["volkswagen"], "year_ranges": [(2009, 9999, 0.40)]},
        {"models": ["audi", "bmw", "range rover", "land rover"], "year_ranges": [(2010, 9999, 0.40)]}
    ],
    "POOL D": [
        {"models": ["canters mitsubishi", "canters isuzu", "canters tata", "canters dyna"], "year_ranges": [(2010, 9999, 0.40)]},
        {"models": ["john deere", "masssey ferguson", "new holland"], "year_ranges": [(2010, 9999, 0.40)]}
    ]
}


# ------------------------------
# UTILITY FUNCTIONS
# ------------------------------
def categorize_mpesa(description):
    description_lower = description.lower()
    if "airtime" in description_lower:
        return "Airtime"
    if "bet" in description_lower or "game" in description_lower or "betika" in description_lower or "sportpesa" in description_lower:
        return "Betting"
    if "petroleum" in description_lower or "fuel" in description_lower or "gas" in description_lower or "diesel" in description_lower or "oil" in description_lower:
        return "Petroleum"
    if "loan" in description_lower or "overdraft" in description_lower or "fuliza" in description_lower:
        return "Loans"
    else:
        return "Other"

def parse_mpesa_statement(text):
    lines = text.splitlines()
    inflows = 0
    categories = {}
    for line in lines:
        match = re.search(r"(Completed).*?([-]?[\d,]+\.\d{2})", line)
        if match:
            amount = float(match.group(2).replace(",", "").replace("-", ""))
            description = line
            category = categorize_mpesa(description)
            categories[category] = categories.get(category, 0) + amount
            inflows += amount if "received" in description.lower() or "promotion payment" in description.lower() else 0
    return categories, inflows

def get_fsv(model: str, year: int) -> Optional[float]:
    model = model.lower()
    for pool in FSV_MATRIX.values():
        for entry in pool:
            if any(m in model for m in entry['models']):
                for start, end, percent in entry['year_ranges']:
                    if start <= year <= end:
                        return percent
    return None

def get_interest_rate(period_in_months: int) -> float:
    if period_in_months == 1:
        return 8.0
    elif 0 <= period_in_months <= 3:
        return 6.0
    elif 0 <= period_in_months <= 6:
        return 5.0
    elif 7 <= period_in_months <= 12:
        return 4.0
    elif 13 <= period_in_months <= 36:
        return 3.5
    else:
        return 3.5

# ------------------------------
# STREAMLIT APP
# ------------------------------
st.title("M-PESA & CRB Risk Assessment Tool")

mpesa_text = st.text_area("Paste M-PESA Statement Text")

if mpesa_text:
    st.subheader("M-PESA Summary")
    categories, total_inflows = parse_mpesa_statement(mpesa_text)
    total = sum(categories.values())
    for k, v in categories.items():
        pct = (v / total) * 100 if total else 0
        st.write(f"**{k}**: KSh {v:,.2f} ({pct:.2f}%)")
    st.success(f"Total Inflows: KSh {total_inflows:,.2f}")
    inflow_eligibility = total_inflows / 3
    st.info(f"Loan Eligibility Based on M-PESA: KSh {inflow_eligibility:,.2f}")

    st.subheader("Vehicle & Risk Inputs")
    crb_score = st.number_input("CRB Score:", 1, 850, value=650)
    ppi_score = st.number_input("PPI (M1–M9):", 1, 9, value=1)
    prob_of_default = st.slider("Probability of Default (%):", 0, 100, value=2)
    model_name = st.text_input("Car Model (e.g. Toyota Fielder):")
    year = st.number_input("Year of Manufacture:", 1990, 2025, value=2015)
    fsv_value = st.number_input("Forced Sale Value:", 100000, 10000000, value=500000)
    period_in_months = st.slider("Loan Period (Months):", 1, 36, value=12)

    if st.button("Assess Full Eligibility"):
        fsv_percentage = get_fsv(model_name, year)
        if fsv_percentage is None:
            st.error("Vehicle model/year not in FSV matrix. Check spelling or year.")
        else:
            fsv_based_eligibility = fsv_value * fsv_percentage
            interest_rate = get_interest_rate(period_in_months)
            min_eligible = min(inflow_eligibility, fsv_based_eligibility)

            st.subheader("Final Assessment")
            st.write(f"**Vehicle Eligibility:** KSh {fsv_based_eligibility:,.2f} ({fsv_percentage*100:.0f}% of KSh {fsv_value:,.0f})")
            st.write(f"**Loan Eligibility (M-PESA):** KSh {inflow_eligibility:,.2f}")
            st.success(f"**Approved Amount:** KSh {min_eligible:,.2f}")
            st.info(f"**Interest Rate:** {interest_rate:.2f}%")

            if crb_score < 500:
                st.warning("Poor CRB Score")
            if ppi_score > 5:
                st.warning("High PPI: Risky Payment Behavior")
            if prob_of_default > 20:
                st.warning("High Probability of Default")
            else:
                st.success("Good credit profile")
