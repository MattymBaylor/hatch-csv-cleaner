import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Hatch CSV Cleaner", page_icon="🧹", layout="centered")
st.title("Hatch CSV Cleaner 🧹")

# Add a sub‑heading underneath the main title to show branding. This line uses
# Streamlit's subheader API to display a smaller heading below the page
# title. Adjust the text here to customize your branding.
st.subheader("Created for HGE Recruiting by M. Martelli")

# Provide a short caption describing what the app does. The caption sits
# under the sub‑heading and explains to your colleagues that nothing is
# stored when they upload files.
st.caption("Upload vendor CSV → get a cleaned file for Hatch. Nothing is stored.")

EXPECTED = ["First Name", "Last Name", "Email", "Phone", "Status"]

def smart_cap_piece(piece: str) -> str:
    """Capitalize segments of a name separated by hyphens or apostrophes."""
    if not piece:
        return ""
    def cap_seg(s: str) -> str:
        return s[:1].upper() + s[1:].lower() if s else ""
    parts = re.split(r"([\-’'])", piece)
    return "".join([p if p in ["-", "’", "'"] else cap_seg(p) for p in parts])

def extract_first_name(name: str) -> str:
    """Extract and capitalize the first token from a full name."""
    if not name:
        return ""
    token = str(name).strip().split()[0] if str(name).strip() else ""
    return smart_cap_piece(token)

def normalize_phone(raw: str) -> str:
    """Strip non‑digits and a leading '1' for long numbers."""
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", str(raw))
    if digits.startswith("1") and len(digits) >= 11:
        digits = digits[1:]
    return digits

def load_csv_any(file) -> pd.DataFrame:
    """Attempt to load a CSV with several encodings."""
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            return pd.read_csv(file, dtype=str, keep_default_na=False, na_values=[], encoding=enc)
        except Exception:
            file.seek(0)
            continue
    file.seek(0)
    return pd.read_csv(file, dtype=str, keep_default_na=False, na_values=[])

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the input DataFrame according to Hatch CSV spec."""
    cols = {c.lower(): c for c in df.columns}
    first = df[cols["name"]].apply(extract_first_name) if "name" in cols else ""
    last  = df[cols["address"]] if "address" in cols else ""
    email_src = cols.get("email_address") or cols.get("email")
    email = df[email_src].str.strip().str.lower() if email_src else ""
    phone_src = cols.get("phone_number") or cols.get("phone")
    phone = df[phone_src].apply(normalize_phone) if phone_src else ""

    out = pd.DataFrame({
        "First Name": first if isinstance(first, pd.Series) else pd.Series([""] * len(df)),
        "Last Name":  last  if isinstance(last, pd.Series)  else pd.Series([""] * len(df)),
        "Email":      email if isinstance(email, pd.Series) else pd.Series([""] * len(df)),
        "Phone":      phone if isinstance(phone, pd.Series) else pd.Series([""] * len(df)),
        "Status":     pd.Series([""] * len(df))
    })

    # Drop the first row if all five columns are empty.
    if len(out) and out.iloc[0].replace("", pd.NA).isna().all():
        out = out.iloc[1:].reset_index(drop=True)
    return out

def to_csv_bytes(df: pd.DataFrame, name: str) -> bytes:
    """Convert a DataFrame to bytes for download."""
    b = io.BytesIO()
    df.to_csv(b, index=False, encoding="utf-8")
    return b.getvalue()

uploaded = st.file_uploader("Upload one or more CSV files", type=["csv"], accept_multiple_files=True)

if uploaded:
    cleaned_list = []
    for f in uploaded:
        df_in = load_csv_any(f)
        cleaned = clean(df_in)
        st.write(f"File: {f.name} — Rows read: {len(df_in)}, Rows output: {len(cleaned)}")
        st.dataframe(cleaned.head(20), use_container_width=True)
        csv_bytes = to_csv_bytes(cleaned, f.name)
        st.download_button(
            label=f"⬇️ Download cleaned: hatch_cleaned_{f.name}",
            data=csv_bytes,
            file_name=f"hatch_cleaned_{f.name}",
            mime="text/csv"
        )
        cleaned_list.append(cleaned)
    if len(cleaned_list) > 1:
        merged = pd.concat(cleaned_list, ignore_index=True)
        csv_bytes = to_csv_bytes(merged, "merged.csv")
        st.download_button(
            label="⬇️ Download merged: hatch_cleaned_merged.csv",
            data=csv_bytes,
            file_name="hatch_cleaned_merged.csv",
            mime="text/csv"
        )
else:
    st.markdown("""
    - Keeps exactly these columns: **First Name**, **Last Name**, **Email**, **Phone**, **Status**
    - Name rules: hyphens/apostrophes capitalized (e.g., Mary-Anne, O’Brien). Uses the first token only.
    - Email is lowercased and trimmed; Phone retains only digits (trimming a leading '1' if length ≥11).
    - Drops `match_score`, `score`, `salary`, `desired_salary` and all other columns.
    - Removes a completely empty first row.
    - Outputs UTF‑8 CSV files named `hatch_cleaned_{original}.csv`.
    """)
