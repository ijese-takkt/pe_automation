import requests
import base64
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import json  # optional but handy if you want to pretty-print responses
import base64


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

# --- AUTH / LICENSING ORG URL ---
encoded_pat = base64.b64encode(f":{ADO_PAT}".encode()).decode()
headers = {
    'Authorization': f'Basic {encoded_pat}',
    'Content-Type': 'application/json'
}
LICENSING_ORG_URL = f"https://vsaex.dev.azure.com/{ADO_ORG}"


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
    print(f"::notice::Output saved to: {output_csv}")

#--- DEMOTE USERS ---
print(f"::notice:: Execution mode for demotion: {EXECUTION_MODE}")

# Reload CSV to get the latest sorted flags
df_status = pd.read_csv(output_csv)
candidates = df_status[df_status['Demotion_Status'] == 'Demote']
candidate_count = len(candidates)

if candidate_count == 0:
    print("::notice::No candidates found marked for demotion.")
    exit(0)

# --- MODE 1: DRY RUN ---
if EXECUTION_MODE == "DRY_RUN":
    print(f"::notice::[DRY RUN] Found {candidate_count} candidates flaggd for demotion.")
    print("::notice::No changes made. Below is the full list of impacted users:\n")
    
    # Configure Pandas to print the full list without truncation
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    
    # Print clean table
    cols_to_show = ['Email', 'Days Inactive', 'License', 'Last Login']
    print(candidates[cols_to_show].to_string(index=False))


# --- MODE 2: DEMOTE ONE ---
elif EXECUTION_MODE == "DEMOTE_ONE":
    print(f"::notice::[DEMOTE ONE] Processing the first candidate out of {candidate_count}...")

    # Take the most inactive candidate (df was already sorted when creating users_with_status.csv)
    candidate = candidates.iloc[0]

    entitlement_id = candidate.get('UserEntitlementId')
    email = candidate.get('Email')
    days_inactive = candidate.get('Days Inactive')
    current_license = candidate.get('License')

    if pd.isna(entitlement_id) or not str(entitlement_id).strip():
        print(f"::error:: Candidate {email} has no UserEntitlementId in CSV. Aborting.")
        exit(1)

    print(f"::notice::Will demote user:")
    print(f"  Email          : {email}")
    print(f"  Entitlement ID : {entitlement_id}")
    print(f"  Current license: {current_license}")
    print(f"  Days inactive  : {days_inactive}")

    url = f"{LICENSING_ORG_URL}/_apis/userentitlements/{entitlement_id}?api-version=7.1-preview.3"
    headers = {
        'Authorization': f'Basic {encoded_pat}',
        'Content-Type': 'application/json-patch+json'
    }
    payload = [
        {
            "op": "replace",
            "path": "/accessLevel",
            "value": {
                "accountLicenseType": "stakeholder"
            }
        }
    ]

    try:
        resp = requests.patch(url, headers=headers, json=payload)
    except Exception as e:
        print(f"::error::HTTP error while calling ADO: {e}")
        exit(1)

    if resp.status_code not in (200, 201):
        print(f"::error::Failed to demote user. Status: {resp.status_code}")
        print(f"::error::Response: {resp.text}")
        exit(1)

    updated = resp.json()
    new_license = (updated.get("accessLevel") or {}).get("licenseDisplayName", "Unknown")

    print("::notice::User successfully demoted in ADO.")
    print(f"  New license: {new_license}")

    # Mark this user as demoted in the status CSV (so we don't try again)
    df_status.loc[df_status['UserEntitlementId'] == entitlement_id, 'Demotion_Status'] = 'Demote DONE'
    df_status.to_csv(output_csv, index=False)
    print(f"::notice::Status CSV updated ({output_csv}).")


# --- MODE 2: DEMOTE ALL ---
elif EXECUTION_MODE == "DEMOTE_ALL":
    print(f"::notice::[DEMOTE ALL] Found {candidate_count} candidates.")
    print("::notice::NOT IMPLEMENTED YET (Safety Lock). No changes were made.")
