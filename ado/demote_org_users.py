import requests
import base64
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# --- CONFIG ---
ADO_ORG = os.getenv("ADO_ORG")
ADO_PAT = os.getenv("ADO_PAT")

if not ADO_ORG or not ADO_PAT:
    print("::error:: Environment variables ADO_ORG_URL or ADO_PAT are missing.")
    exit(1)

EXECUTION_MODE = os.getenv("EXECUTION_MODE", "DRY_RUN") # Options: DRY_RUN, DEMOTE_ONE, DEMOTE_ALL
threshold_str = os.getenv("DEMOTE_THRESHOLD_DAYS", "90")
try:
    THRESHOLD_DAYS = int(threshold_str)
except ValueError:
    print(f"::error::Invalid DEMOTE_THRESHOLD_DAYS: {threshold_str}")
    exit(1)

# --- LOAD CSV ---
BASE_DIR = Path(__file__).resolve().parent
csv_path = BASE_DIR / "outputs" / ADO_ORG / "users_latest.csv"

if not csv_path.exists():
    print(f"::error::CSV not found: {csv_path}")
    exit(1)

print(f"::notice::Marking demote candidates for org {ADO_ORG} with threshold {THRESHOLD_DAYS} days.")
print(f"::notice::Input CSV: {csv_path}")

print(f"Loading data from {csv_path}...")
df = pd.read_csv(csv_path)

# --- 3. APPLY RULES (MARKING ONLY) ---
print(f"::notice:: Marking candidates (Threshold: {THRESHOLD_DAYS} days)...")

# Initialize Status Column
if 'Demotion_Status' not in df.columns:
    df['Demotion_Status'] = ''

total = len(df)
demote_count = 0

for index, row in df.iterrows():
    # Safe data retrieval
    email = str(row.get('Email', '')).lower()
    days_inactive = row.get('Days Inactive', 0)
    license_type = row.get('License', '')
    source = row.get('Source', '')

    # Must be inactive long enough, NOT already free, NOT paid MSDN
    should_demote = (
        source == "account"
        and not "stakeholder" in license_type
        and days_inactive >= THRESHOLD_DAYS
    )

    if should_demote:
        df.at[index, 'Demotion_Status'] = 'Demote'
        demote_count += 1

# --- 4. SAVE NEW CSV ---
output_csv = BASE_DIR / "outputs" / ADO_ORG / "users_with_status.csv"
df.to_csv(output_csv, index=False)

print(f"::notice::Total users in CSV: {total}")
print(f"::notice::Users flagged as demote candidates: {demote_count}")
print(f"::notice:: Output saved to: {output_csv}")