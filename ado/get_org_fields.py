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
    print("❌ Error: Environment variables ADO_ORG or ADO_PAT are missing.")
    exit(1)

# --- AUTH ---
encoded_pat = base64.b64encode(f":{ADO_PAT}".encode()).decode()
headers = {
    "Authorization": f"Basic {encoded_pat}",
    "Content-Type": "application/json"
}

API_VERSION = "7.0"
BASE_URL = f"https://dev.azure.com/{ADO_ORG}"

def ado_get(url, params=None):
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"GET {url} failed: {resp.status_code} {resp.text}")
    return resp.json()

# --- FETCH ALL FIELDS (ORG LEVEL) ---
fields_url = f"{BASE_URL}/_apis/wit/fields"
data = ado_get(fields_url, params={"api-version": API_VERSION})
fields = data.get("value", [])

print(f"Found {len(fields)} fields in org\n")

# print first 5 with most relevant properties
for f in fields[:5]:
    print(
        f"Name: {f.get('name')}\n"
        f"  Ref: {f.get('referenceName')}\n"
        f"  Type: {f.get('type')}\n"
        f"  Usage: {f.get('usage')}\n"
        f"  IsIdentity: {f.get('isIdentity')}\n"
        f"  Description: {f.get('description')}\n"
        "----"
    )

# --- FETCH ALL PROJECTS ---
projects_url = f"{BASE_URL}/_apis/projects"
projects_data = ado_get(projects_url, params={"api-version": API_VERSION})
projects = projects_data.get("value", [])

print(f"\nFound {len(projects)} projects in org\n")

for p in projects[:5]:
    print(
        f"Name: {p.get('name')}\n"
        f"  Id: {p.get('id')}\n"
        f"  State: {p.get('state')}\n"
        f"  Description: {p.get('description')}\n"
        "----"
    )
