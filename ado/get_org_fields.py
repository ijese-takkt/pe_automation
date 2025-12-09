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

# --- FETCH ORG FIELDS (for type/isIdentity, etc.) ---
fields_url = f"{BASE_URL}/_apis/wit/fields"
fields_data = ado_get(fields_url, params={"api-version": API_VERSION})
fields = fields_data.get("value", [])
field_defs = {f["referenceName"]: f for f in fields}

print(f"Found {len(fields)} org fields\n")

# --- FETCH ALL PROJECTS ---
projects_url = f"{BASE_URL}/_apis/projects"
projects_data = ado_get(projects_url, params={"api-version": API_VERSION})
projects = projects_data.get("value", [])

print(f"Found {len(projects)} projects in org\n")

# --- WRITE CSV ---
output_path = BASE_DIR / "outputs" / ADO_ORG  # outputs/<ORG> next to the script
output_path.mkdir(parents=True, exist_ok=True)

csv_file = output_path / f"ado_project_fields.csv"

with csv_file.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=",")
    writer.writerow([
        "Project",
        "ProcessName",
        "FieldName",
        "FieldRefName",
        "FieldType",
        "IsIdentity",
        "IsCustom",
    ])

    total_rows = 0

    for p in projects:
#    for p in projects[:3]: # speeds up testing to process only 3 projects

        project_name = p.get("name")
        project_id = p.get("id")

        # get process name for this project (one extra call)
        proj_detail_url = f"{BASE_URL}/_apis/projects/{project_id}"
        proj_detail = ado_get(
            proj_detail_url,
            params={"api-version": API_VERSION, "includeCapabilities": "true"}
        )
        capabilities = proj_detail.get("capabilities", {})
        proc_tmpl = capabilities.get("processTemplate", {})
        process_name = proc_tmpl.get("templateName", "")

        print(f"→ Project: {project_name} (process: {process_name})")

        # collect all field referenceNames used in this project (across all WITs)
        project_field_refs = set()

        # list WITs for this project
        wits_url = f"{BASE_URL}/{project_name}/_apis/wit/workitemtypes"
        wits_data = ado_get(wits_url, params={"api-version": API_VERSION})
        wits = wits_data.get("value", [])

        for wit in wits:
            wit_name = wit.get("name")

            wit_fields_url = f"{BASE_URL}/{project_name}/_apis/wit/workitemtypes/{wit_name}/fields"
            wit_fields_data = ado_get(wit_fields_url, params={"api-version": API_VERSION})
            wit_fields = wit_fields_data.get("value", [])

            for wf in wit_fields:
                ref_name = wf.get("referenceName")
                if ref_name:
                    project_field_refs.add(ref_name)

        # now dump one row per (project, field)
        for ref_name in sorted(project_field_refs):
            meta = field_defs.get(ref_name, {})
            field_name = meta.get("name", ref_name)
            field_type = meta.get("type", "")
            is_identity = meta.get("isIdentity", False)
            is_custom = ref_name.startswith("Custom.")

            writer.writerow([
                project_name,
                process_name,
                field_name,
                ref_name,
                field_type,
                "Yes" if is_identity else "No",
                "Yes" if is_custom else "No",
            ])
            total_rows += 1

print(f"\n✅ Written {total_rows} rows to: {output_path}")
