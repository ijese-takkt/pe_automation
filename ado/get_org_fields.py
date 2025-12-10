import requests
import base64
import os
from datetime import datetime
import csv
from pathlib import Path
import pandas as pd


# --- QUERY PROJECTS AND  BUILD CSV ---
def build_csv():
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


# --- CREATE EXCEL ---
def build_excel():
        
    csv_path = BASE_DIR / "outputs" / ADO_ORG / "ado_project_fields.csv"
    xlsx_path = BASE_DIR / "outputs" / ADO_ORG / "ado_project_fields.xlsx"

    df = pd.read_csv(csv_path, sep=",")

    print(f"[build_excel] Reading CSV from: {csv_path}")
    print(f"[build_excel] Rows: {len(df)}")
    print(f"[build_excel] Columns: {list(df.columns)}")

    # sanity: show first few rows (truncate)
    print("[build_excel] Sample rows:")
    print(df.head(5).to_string(index=False))

    # check expected columns
    expected = ["Project", "ProcessName", "FieldRefName", "FieldName"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        print(f"[build_excel] ❌ Missing expected columns: {missing}")
        return

    # 1) Raw data
    df_data = df.copy()

    # 2) Project | # custom fields (distinct)
    df_custom = df[df["IsCustom"] == "Yes"]
    proj_custom_counts = (
        df_custom.groupby("Project")["FieldRefName"]
        .nunique()
        .reset_index(name="CustomFieldCount")
        .sort_values("CustomFieldCount", ascending=False)
    )

    # 3) Process | # projects
    proc_proj_counts = (
        df.groupby("ProcessName")["Project"]
        .nunique()
        .reset_index(name="ProjectCount")
        .sort_values("ProjectCount", ascending=False)
    )

    # 4) Custom field | # projects using it
    field_proj_counts = (
        df_custom.groupby(["FieldRefName", "FieldName"])["Project"]
        .nunique()
        .reset_index(name="ProjectCount")
        .sort_values("ProjectCount", ascending=False)
    )

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_data.to_excel(writer, sheet_name="data", index=False)
        proj_custom_counts.to_excel(writer, sheet_name="projects_custom_fields", index=False)
        proc_proj_counts.to_excel(writer, sheet_name="process_projects", index=False)
        field_proj_counts.to_excel(writer, sheet_name="fields_project_counts", index=False)

    print(f"✅ Written Excel workbook: {xlsx_path}")


# --- MAIN ---
BASE_DIR = Path(__file__).resolve().parent  # folder where this script lives

# Config
ADO_ORG = os.getenv("ADO_ORG")
ADO_PAT = os.getenv("ADO_PAT")

if not ADO_ORG or not ADO_PAT:
    print("❌ Error: Environment variables ADO_ORG or ADO_PAT are missing.")
    exit(1)

# Get data from projects and dumpt it to csv as kind of db
BUILD_CSV = True # takes several minutes, set to FALSE when testing other parts
if BUILD_CSV:
    build_csv()

# Create excel with original data on the first sheet, 
#   and aggregate reports as additional sheets
build_excel()
