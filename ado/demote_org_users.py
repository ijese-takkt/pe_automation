import requests
import base64
import os
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import json 


# --- CONFIG ---
ADO_ORG = os.getenv("ADO_ORG")
ADO_PAT = os.getenv("ADO_PAT")
GITHUB_RUN_ID = os.getenv("GITHUB_RUN_ID","local")
GITHUB_SHA = os.getenv("GITHUB_SHA","local")

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
LICENSING_ORG_URL = f"https://vsaex.dev.azure.com/{ADO_ORG}"


# --- LOAD CSV ---
BASE_DIR = Path(__file__).resolve().parent
output_dir = BASE_DIR / "outputs" / ADO_ORG

input_csv = output_dir / "users_latest.csv"
output_csv = output_dir / "users_with_status.csv"

# --- LOGS ---
demotions_log = output_dir / "demotions_APPEND_ONLY.log"
demotions_csv = output_dir / "demotions.csv"


if not input_csv.exists():
    print(f"::error:: Input CSV not found: {input_csv}")
    exit(1)


def append_demotion_event(*, org, entitlement_id, email, old_license, new_license,
                          days_inactive, threshold_days, source, mode,
                          gh_run_id, gh_sha):
    """
    Append a single demotion event as line-delimited JSON to demotions.log.
    """
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    event = {
        "ts": ts,
        "org": org,
        "userEntitlementId": str(entitlement_id),
        "email": email,
        "oldLicense": old_license,
        "newLicense": new_license,
        "daysInactive": int(days_inactive) if pd.notna(days_inactive) else None,
        "thresholdDays": int(threshold_days),
        "source": source,
        "mode": mode,
        "ghRunId": gh_run_id,
        "ghSha": gh_sha,
    }

    demotions_log.parent.mkdir(parents=True, exist_ok=True)
    with demotions_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def rebuild_demotions_csv():
    """
    Rebuild demotions.csv from demotions.log, sorted by newest first.
    """
    if not demotions_log.exists():
        return

    rows = []
    with demotions_log.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # ignore bad lines
                continue

    if not rows:
        return

    df_log = pd.DataFrame(rows)
    # Map to human-facing columns
    df_log["TimestampUtc"] = df_log["ts"]
    df_log["Org"] = df_log.get("org", "")
    df_log["Email"] = df_log.get("email", "")
    df_log["UserEntitlementId"] = df_log.get("userEntitlementId", "")
    df_log["OldLicense"] = df_log.get("oldLicense", "")
    df_log["NewLicense"] = df_log.get("newLicense", "")
    df_log["DaysInactive"] = df_log.get("daysInactive", "")
    df_log["ThresholdDays"] = df_log.get("thresholdDays", "")
    df_log["Source"] = df_log.get("source", "")
    df_log["Mode"] = df_log.get("mode", "")
    df_log["GitHubRunId"] = df_log.get("ghRunId", "")
    df_log["CommitSha"] = df_log.get("ghSha", "")

    cols = [
        "TimestampUtc",
        "Org",
        "Email",
        "UserEntitlementId",
        "OldLicense",
        "NewLicense",
        "DaysInactive",
        "ThresholdDays",
        "Source",
        "Mode",
        "GitHubRunId",
        "CommitSha",
    ]

    df_log = df_log.sort_values(by="TimestampUtc", ascending=False)
    df_log[cols].to_csv(demotions_csv, index=False)


# --- ANALYZE AND FLAG USERS FOR DEMOTION ---
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
    source = candidate.get('Source', '')

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

    # 1) Append to append-only demotions.log
    append_demotion_event(
        org=ADO_ORG,
        entitlement_id=entitlement_id,
        email=email,
        old_license=current_license,
        new_license=new_license,
        days_inactive=days_inactive,
        threshold_days=THRESHOLD_DAYS,
        source=source,
        mode=EXECUTION_MODE,
        gh_run_id=GITHUB_RUN_ID,
        gh_sha=GITHUB_SHA,
    )

    # 2) Rebuild demotions.csv for humans
    rebuild_demotions_csv()

    # 3) Mark this user as demoted in the status CSV (so we don't try again)
    df_status.loc[df_status['UserEntitlementId'] == entitlement_id, 'Demotion_Status'] = 'Demote DONE'
    df_status.to_csv(output_csv, index=False)
    print(f"::notice::Status CSV updated ({output_csv}).")


# --- MODE 2: DEMOTE ALL ---
elif EXECUTION_MODE == "DEMOTE_ALL":
    print(f"::notice::[DEMOTE ALL] Found {candidate_count} candidates.")
    print("::notice::NOT IMPLEMENTED YET (Safety Lock). No changes were made.")
