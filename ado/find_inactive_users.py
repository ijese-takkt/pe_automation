import requests
import base64
import os
from datetime import datetime

# --- CONFIG ---
ORG_URL = os.getenv("ADO_ORG_URL")
PAT = os.getenv("ADO_PAT")

if not ORG_URL or not PAT:
    print("❌ Error: Environment variables ADO_ORG_URL or ADO_PAT are missing.")
    exit(1)

# --- AUTH ---
encoded_pat = base64.b64encode(f":{PAT}".encode()).decode()
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
licensing_org_url = ORG_URL.replace("dev.azure.com", "vsaex.dev.azure.com")
url_users = f"{licensing_org_url}/_apis/userentitlements?top=30000&api-version=7.1-preview.2"
print(url_users)
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
        'Days Inactive': calculate_inactive_days(last_login_raw)
    })

from collections import Counter

source_counts = Counter(u.get("Source") for u in all_users)
print(source_counts)


# --- RESULTS ---
print(f"\n✅ Scan Complete. Found {len(all_users)} total users.")

# Print top 1 for preview
for u in all_users[:20]:
    print(u)