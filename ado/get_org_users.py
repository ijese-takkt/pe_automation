import requests
import base64
import os
from datetime import datetime
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # folder where this script lives

# --- CONFIG ---
ADO_ORG = os.getenv("ADO_ORG")
ADO_PAT = os.getenv("ADO_PAT")

if not ADO_ORG or not ADO_PAT:
    print("❌ Error: Environment variables ADO_ORG_URL or ADO_PAT are missing.")
    exit(1)

# --- AUTH ---
encoded_pat = base64.b64encode(f":{ADO_PAT}".encode()).decode()
headers = {
    'Authorization': f'Basic {encoded_pat}',
    'Content-Type': 'application/json'
}

# --- HELPER: Date Math ---
def calculate_inactive_days(last_access_str):
    """
    Converts ADO timestamp (e.g., '2023-10-01T12:00:00Z') to days inactive.
    Returns 9999 if user never logged in.
    """
    if not last_access_str:
        return 9999
    
    # Parse the timestamp (replacing Z with +00:00 to make it timezone-aware)
    last_login_dt = datetime.fromisoformat(last_access_str.replace('Z', '+00:00'))
    
    # Calculate difference between NOW (aware) and LOGIN (aware)
    now = datetime.now(last_login_dt.tzinfo)
    delta = now - last_login_dt
    return delta.days

print("\n--- Scanning Users ---")

# API: User Entitlements (Contains License + Login Data)
# LICENSING DOMAIN: Change 'dev.azure.com' to 'vsaex.dev.azure.com'
LICENSING_ORG_URL = f"https://vsaex.dev.azure.com/{ADO_ORG}"

url_users = f"{LICENSING_ORG_URL}/_apis/userentitlements?top=30000&api-version=7.1-preview.2"
all_users = []

res = requests.get(url_users, headers=headers)
data = res.json()
print("totalCount:", data.get("totalCount"))
print("items on this page:", len(data.get("items", [])))
    
# Loop through the items in this page
for item in data.get('items', []):
    user = item.get('user', {})
    access = item.get('accessLevel', {})

    email = user.get('principalName')
    license_type = access.get('licenseDisplayName')
    license_source = access.get('licensingSource') # 'account' vs 'msdn'
    last_login_raw = item.get('lastAccessedDate')    
    
    all_users.append({
        'Email': email,
        'License': license_type,
        'Source': license_source,
        'Last Login': last_login_raw,
        'Last Login Date': last_login_raw.split('T')[0] if last_login_raw else '',
        'Days Inactive': calculate_inactive_days(last_login_raw)
    })

# --- RESULTS ---
print(f"\n✅ Scan Complete. Found {len(all_users)} total users.")

# --- WRITE CSV ---
output_path = BASE_DIR / "outputs" / ADO_ORG  # outputs/<ORG> next to the script
output_path.mkdir(parents=True, exist_ok=True)

csv_file = output_path / f"users_latest.csv"

fieldnames = [
    "Email",
    "License",
    "Source",
    "Last Login",
    "Last Login Date",
    "Days Inactive",
]

with csv_file.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_users)

print(f"✅ Written {len(all_users)} users to {csv_file}")
