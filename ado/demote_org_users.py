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
output_dir = BASE_DIR / "outputs" / ADO_ORG

input_csv = output_dir / "users_latest.csv"
output_csv = output_dir / "users_with_status.csv"

if not input_csv.exists():
    print(f"::error:: Input CSV not found: {input_csv}")
    exit(1)

# --- CHECK WHETHER NEW INPUT CSV ---
need_analysis = True

if output_csv.exists():
    t_input = input_csv.stat().st_mtime
    t_output = output_csv.stat().st_mtime
    if t_input < t_output:
        need_analysis = False
        print(f"::notice:: users_latest csv is older than status csv. No flagging needed.")

# --- ANALYZE AND FLAG USERS FOR DEMOTION (If needed) ---
if need_analysis:
    print(f"::notice::Marking demote candidates for org {ADO_ORG} with threshold {THRESHOLD_DAYS} days.")
    print(f"::notice::Input CSV: {input_csv}")

    print(f"Loading data from {input_csv}...")
    df = pd.read_csv(input_csv)

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
            and "stakeholder" not in license_type.lower()
            and days_inactive >= THRESHOLD_DAYS
        )

        if should_demote:
            df.at[index, 'Demotion_Status'] = 'Demote'
            demote_count += 1

    # Sort: Highest inactivity at top
    df = df.sort_values(by='Days Inactive', ascending=False)
    
    # save new CSV
    df.to_csv(output_csv, index=False)

    print(f"::notice::Total users in CSV: {total}")
    print(f"::notice::Users flagged as demote candidates: {demote_count}")
    print(f"::notice:: Output saved to: {output_csv}")

#--- DEMOTE USERS ---
print(f"::notice:: Execution mode for demotion: {EXECUTION_MODE}")
