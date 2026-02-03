import streamlit as st
import pandas as pd
import sqlite3
import os
import hashlib
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib.pyplot as plt
from io import BytesIO


# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="GST Reporter Pro",
    layout="wide",
    page_icon="📊"
)

os.makedirs("reports", exist_ok=True)


# =====================================================
# DARK STYLE
# =====================================================
plt.style.use("dark_background")

GREEN = "#2ecc71"
RED = "#e74c3c"
BLUE = "#3498db"


# =====================================================
# DATABASE
# =====================================================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# USERS TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

# REPORTS TABLE (per user)
cursor.execute("""
CREATE TABLE IF NOT EXISTS reports(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    date TEXT,
    total_amount REAL,
    total_gst REAL,
    grand_total REAL
)
""")

conn.commit()


# =====================================================
# PASSWORD HASH
# =====================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# =====================================================
# SESSION STATE
# =====================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


# =====================================================
# AUTH FUNCTIONS
# =====================================================

def register():

    st.subheader("🆕 Register")

    user = st.text_input("Username", key="reg_user")
    pwd = st.text_input("Password", type="password", key="reg_pass")

    if st.button("Register", key="reg_btn"):

        if not user or not pwd:
            st.warning("Fill all fields")
            return

        try:
            cursor.execute(
                "INSERT INTO users(username,password) VALUES(?,?)",
                (user, hash_password(pwd))
            )
            conn.commit()
            st.success("Account created! Now login.")
        except:
            st.error("Username already exists")


def login():

    st.subheader("🔐 Login")

    user = st.text_input("Username", key="login_user")
    pwd = st.text_input("Password", type="password", key="login_pass")

    if st.button("Login", key="login_btn"):

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (user, hash_password(pwd))
        )

        if cursor.fetchone():
            st.session_state.logged_in = True
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Wrong credentials")


# =====================================================
# AUTH PAGE
# =====================================================
if not st.session_state.logged_in:

    st.title("📊 GST Reporter Pro")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        login()

    with tab2:
        register()

    st.stop()


# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.success(f"Logged in as: {st.session_state.user}")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()


# =====================================================
# PDF GENERATOR
# =====================================================
def generate_pdf(df, ta, tg, gt, filename):

    path = f"reports/{filename}"
    doc = SimpleDocTemplate(
        path,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elements = []

    # ===== TITLE =====
    title = Paragraph("GST Compliance Report", styles["Heading1"])
    elements.append(title)
    elements.append(Spacer(1, 30))


    # ===== TABLE =====
    table_data = [list(df.columns)] + df.values.tolist()

    table = Table(table_data, hAlign="CENTER")   # ⭐ CENTERED

    table.setStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ])

    elements.append(table)
    elements.append(Spacer(1, 40))


    # ===== TOTALS (NO ₹ SYMBOL) =====
    totals = [
        f"Total Amount : Rs. {ta:,.2f}",
        f"Total GST    : Rs. {tg:,.2f}",
        f"Grand Total  : Rs. {gt:,.2f}",
    ]

    for t in totals:
        elements.append(Paragraph(t, styles["Heading3"]))


    doc.build(elements)

    return path

# =====================================================
# MAIN UI
# =====================================================
st.title("📊 GST Compliance Reporter PRO")

uploaded = st.file_uploader("Upload Excel / CSV / TXT", type=["xlsx", "csv", "txt"])


# =====================================================
# FILE PROCESSING
# =====================================================
if uploaded:

    if uploaded.name.endswith((".csv", ".txt")):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    if "Amount" not in df.columns:
        st.error("File must contain 'Amount' column")
        st.stop()

    df["Amount"] = df["Amount"].astype(str).str.replace(",", "").astype(float)

    st.subheader("📄 Data Preview")
    st.dataframe(df, use_container_width=True)


    # GST calculation
    gst_cols = [c for c in df.columns if c.lower() in ["gst", "tax"]]

    if gst_cols:
        df["GST"] = pd.to_numeric(df[gst_cols[0]], errors="coerce").fillna(0)
    else:
        rate = st.selectbox("GST Rate (%)", [5, 12, 18, 28])
        df["GST"] = df["Amount"] * rate / 100

    df["Total"] = df["Amount"] + df["GST"]


    ta = df["Amount"].sum()
    tg = df["GST"].sum()
    gt = df["Total"].sum()


    # =====================================================
    # SUMMARY
    # =====================================================
    c1, c2, c3 = st.columns(3)
    c1.metric("Amount", f"₹{ta:,.2f}")
    c2.metric("GST", f"₹{tg:,.2f}")
    c3.metric("Grand Total", f"₹{gt:,.2f}")


    # =====================================================
    # CHARTS
    # =====================================================
    st.subheader("📊 Analytics")

    colA, colB = st.columns(2)


    # ---------- BAR ----------
    with colA:
        fig1, ax1 = plt.subplots(figsize=(3.8, 3.5))

        ax1.bar(
            ["Amount", "GST", "Total"],
            [ta, tg, gt],
            color=[GREEN, RED, BLUE]
        )

        ax1.set_title("GST Breakdown")
        st.pyplot(fig1, width="content")


    # ---------- PIE ----------
    with colB:
        fig2, ax2 = plt.subplots(figsize=(3.8, 3.5))

        ax2.pie(
            [ta, tg],
            labels=["Amount", "GST"],
            colors=[GREEN, RED],
            autopct="%1.1f%%"
        )

        ax2.set_title("Amount vs GST Share")
        st.pyplot(fig2, width="content")



    # =====================================================
    # BUTTONS
    # =====================================================
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Save"):
            cursor.execute(
                "INSERT INTO reports(username,date,total_amount,total_gst,grand_total) VALUES(?,?,?,?,?)",
                (
                    st.session_state.user,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    ta, tg, gt
                )
            )
            conn.commit()
            st.success("Saved!")

    with col2:
        if st.button("📥 PDF"):
            name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            path = generate_pdf(df, ta, tg, gt, name)
            with open(path, "rb") as f:
                st.download_button("Download PDF", f, name)

    with col3:
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        st.download_button("📥 Excel", buffer.getvalue(), "report.xlsx")


# =====================================================
# HISTORY (PER USER)
# =====================================================
st.divider()
st.subheader("📁 History")

hist = pd.read_sql_query(
    "SELECT date,total_amount,total_gst,grand_total FROM reports WHERE username=? ORDER BY id DESC",
    conn,
    params=(st.session_state.user,)
)

if not hist.empty:

    hist.index = hist.index + 1
    hist.index.name = "Sr No"

    st.dataframe(hist, use_container_width=True)

    hist["date"] = pd.to_datetime(hist["date"])

    monthly = (
        hist.groupby(hist["date"].dt.to_period("M"))
        [["total_amount", "total_gst", "grand_total"]]
        .sum()
        .reset_index()
    )

    monthly["date"] = monthly["date"].astype(str)
    monthly.index = monthly.index + 1
    monthly.index.name = "Sr No"

    st.subheader("📅 Monthly Summary")
    st.dataframe(monthly, use_container_width=True)

    fig3, ax3 = plt.subplots(figsize=(5, 3))
    ax3.bar(monthly["date"], monthly["grand_total"], color=BLUE)
    ax3.set_title("Monthly Grand Total")
    st.pyplot(fig3, width="content")

    if st.button("🗑 Clear My History"):
        cursor.execute(
            "DELETE FROM reports WHERE username=?",
            (st.session_state.user,)
        )
        conn.commit()
        st.rerun()

else:
    st.info("No saved reports yet")
