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
def calculate_inactive_days(last_access_str, created_str):
    # Parse ignoring the bogus 0001-01-01 date
    def parse_dt(s):
        if not s or s.startswith("0001-01-01"):
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    last_dt = parse_dt(last_access_str)
    created_dt = parse_dt(created_str)

    # Use whichever is newer
    if last_dt and created_dt:
        ref_dt = max(last_dt, created_dt)
    else:
        ref_dt = last_dt or created_dt

    # With your data, this should never happen anymore
    if not ref_dt:
        # fallback just in case Microsoft invents another surprise
        return 0

    now = datetime.now(ref_dt.tzinfo)
    return (now - ref_dt).days


print("\n--- Scanning Users ---")

# API: User Entitlements (Contains License + Login Data)
# LICENSING DOMAIN: Change 'dev.azure.com' to 'vsaex.dev.azure.com'
LICENSING_ORG_URL = f"https://vsaex.dev.azure.com/{ADO_ORG}"

url_users = f"{LICENSING_ORG_URL}/_apis/userentitlements?top=30000&api-version=7.1-preview.2"
all_users = []

res = requests.get(url_users, headers=headers)
data = res.json()

total = data.get("totalCount") or 0
items_count = len(data.get("items", []))

print(f"totalCount from API: {total}")
print(f"items on this page: {items_count}")

if total != items_count:
    print(f"::error::Mismatch between totalCount ({total}) and items on this page ({items_count}) – expected them to match with top=30000")
else:
    print("::notice::User entitlement counts match totalCount and items")
    
# Loop through the items in this page
for item in data.get('items', []):
    user = item.get('user', {})
    access = item.get('accessLevel', {})

    email = user.get('principalName')
    license_type = access.get('licenseDisplayName')
    license_source = access.get('licensingSource') # 'account' vs 'msdn'
    last_login_raw = item.get('lastAccessedDate')    
    created_raw    = item.get("dateCreated")        # entitlement creation

    all_users.append({
        'Email': email,
        'License': license_type,
        'Source': license_source,
        'Last Login': last_login_raw,
        'Created': created_raw,
        'Last Login Date': last_login_raw.split('T')[0] if last_login_raw else '',
        'Created Date': created_raw.split('T')[0] if created_raw else '',
        'Days Inactive': calculate_inactive_days(last_login_raw, created_raw)
    })

# --- RESULTS ---
print(f"::notice::Scan Complete. Found {len(all_users)} total users.")

# --- WRITE CSV ---
output_path = BASE_DIR / "outputs" / ADO_ORG  # outputs/<ORG> next to the script
output_path.mkdir(parents=True, exist_ok=True)

csv_file = output_path / f"users_latest.csv"

fieldnames = [
    "Email",
    "License",
    "Source",
    "Last Login",
    "Created",
    "Last Login Date",
    "Created Date",
    "Days Inactive",
]

with csv_file.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_users)

print(f"::notice::Written {len(all_users)} users to {csv_file}")
