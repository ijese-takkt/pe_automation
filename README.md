# PE Automation

Scripts and jobs for **Platform Engineering** automation.

### Implemented so far
1. Get all users for org KKEU
    - output is a csv, both viewable here and downloadable
2. Demote org users to stakeholder, based on inactivity
    - modes: DRY_RUN, DEMOTE_ONE (to be implemented: DEMOTE_ALL)
3. Get all fields for org KKEU
    - output is a csv viewable here, plus xlsx (downloadable) with additional aggregate reports


### Backlog / TODO

1. Now:
    - project stats collector
2. Next:
    - keep last 5 invocations (logs, csvs) just timestamp them
    - full logs for user extractor and demoting
3. Later:
    - demote all (manually, later scheduled)

## General Docs

* Python **3.12**
* Azure DevOps–related code lives under `ado/`
  * Any generated data goes under `ado/outputs/<ADO_ORG>/`
* Each script and github action is documented below


### Local Development

* these are not in repo but you need them or equivalents to develop/test locally
* you probably want to create venv then activate it to work from there
    * venv needs to be OUTSIDE the repo, e.g. in its parent folder
* `venv/` holds the local Python virtual environment
* `start_venv.bat` activates the venv and keeps the cmd window open
* For local development, set `ADO_ORG` and `ADO_PAT` via a **.bat / shell script outside the repo**
  (to avoid committing PATs in plaintext)


### Secrets (GitHub)

* **`ADO_PAT`** (repository secret)

  * PAT that currently has sufficient permissions for all target orgs
  * Used by GitHub Actions; locally you still set `ADO_PAT` via env

> In the workflow we hardcode `ADO_ORG` to `KKEU` and read `ADO_PAT` from this secret.


## GitHub Actions

### `Get ADO users for KKEU`

* Workflow file: `.github/workflows/get-ado-users-KKEU.yml`
* Sets `ADO_ORG=KKEU`
* Runs `ado/get_org_users.py`
* Commits and pushes `ado/outputs/KKEU/users_latest.csv` back to the repo
* GitHub’s UI can display the CSV directly (no download needed)

### `Catalogue KKEU fields`

* Workflow file: `.github/workflows/get-ado-fields-KKEU.yml`
* Sets `ADO_ORG=KKEU`
* Runs `ado/get_org_fields.py`
* Commits and pushes back to the repo:
  - `ado/outputs/KKEU/ado_project_fields.csv` 
  - `ado/outputs/KKEU/ado_project_fields.xlsx` 
* GitHub’s UI can display the CSV directly (no download needed)
* Excel needs to be downloaded, then user can:
  - filter the first sheet with original data
  - review other sheets containing aggregate reports

### `Demote ADO users for KKEU (DRY RUN)`

* Workflow file: `.github/workflows/demote-ado-users-KKEU_dry_run.yml`
* Sets:

  * `ADO_ORG=KKEU`
  * `EXECUTION_MODE=DRY_RUN`
  * `DEMOTE_THRESHOLD_DAYS=90`
* Requires `ado/outputs/KKEU/users_latest.csv`
  (normally produced by `Get ADO users for KKEU`)
* Runs `ado/demote_org_users.py` to:

  * load `users_latest.csv`
  * mark candidates with `Demotion_Status="Demote"` based on inactivity and license rules
  * write `ado/outputs/KKEU/users_with_status.csv`
* Commits and pushes `ado/outputs/` back to the repo
  (so `users_with_status.csv` is visible and reviewable in GitHub)
* Does **not** change anything in Azure DevOps – purely reporting / planning step.


### `Demote ADO users for KKEU (DEMOTE ONE)`

* Workflow file: `.github/workflows/demote-ado-users-KKEU_demote_one.yml`
* Basically does the same as DRY_RUN version, but:
  * Sets `EXECUTION_MODE=DEMOTE_ONE`
  * Runs `ado/demote_org_users.py`
  * Commits and pushes `ado/outputs/` back to the repo so the status file reflects the changes.
* Intended as a **safe, incremental** way to exercise real demotion logic on one user at a time before enabling bulk demotion.

## Scripts

### `ado/get_org_users.py`

* Uses **REST `userentitlements`** instead of Graph:
  * Entitlements (licensed users) vs raw identities
  * Docs:
    * [https://developercommunity.visualstudio.com/t/what-is-the-different-between-get-user-entitlement/1080296](https://developercommunity.visualstudio.com/t/what-is-the-different-between-get-user-entitlement/1080296)
    * [https://learn.microsoft.com/en-us/rest/api/azure/devops/memberentitlementmanagement/user-entitlements/search-user-entitlements](https://learn.microsoft.com/en-us/rest/api/azure/devops/memberentitlementmanagement/user-entitlements/search-user-entitlements)
* Important rules:
  * `licensingSource = "msdn"` **should NOT be downgraded** by automation
  * We only consider `licensingSource = "account"` (and later possibly `auto` / `trial`) for demotions
* API quirk:
  * `continuationToken` is often `''` even when `totalCount` > page size
  * Workaround: use `?top=30000` to get all entitlements in one call
* Output:
  * Creates CSV with:
    * `Email`, `License`, `Source`, `Last Login`, `Created`, `Last Login Date`, `Created Date`, `Days Inactive`
  * Path: `ado/outputs/<ORG>/users_latest.csv`
    * For `KKEU`: `ado/outputs/KKEU/users_latest.csv`
  * Days Inactive: is calculated from Last Login OR Created (whichever is newer) to today
    * This is because if user never logged in then Last Login is 01-01-0001

### `ado/get_org_fields.py`

* **Purpose:**
  Catalogue all fields used across Azure DevOps projects in the organization, then generate both raw data and governance-friendly summary tables.

* **Key steps:**

  * Fetch **all org-level field definitions** (type, identity, name, referenceName, etc.).
  * Fetch **all projects** in the organization.
  * For each project:

    * Fetch **process name** via `includeCapabilities=true`.
    * Fetch **all Work Item Types (WITs)** in that project.
    * For each WIT: fetch **fields attached to that WIT**.
  * Collect **unique fields per project** (deduped across WITs).
  * Combine with org-level metadata to produce a flat dataset.

* **Output (CSV):**
  * Creates a normalized table with one row per `(Project, Field)`:
    * `Project`
    * `ProcessName`
    * `FieldName`
    * `FieldRefName`
    * `FieldType`
    * `IsIdentity`
    * `IsCustom` (derived from `FieldRefName.startswith("Custom.")`)
  * Path:
    ```
    output/<ORG>/ado_project_fields.csv
    ```
    Example:
    ```
    output/KKEU/ado_project_fields.csv
    ```
* **Output (Excel workbook):**
  After CSV is generated (or using existing CSV if `SKIP_CSV=1` is set), the script builds:
  `ado_project_fields.xlsx` with **four sheets**:
  1. **`data`**
     Raw rows copied from the CSV.
  2. **`projects_custom_fields`**
     * For each project: number of **distinct custom fields** used.
     * Helps identify over-customized projects.
  3. **`process_projects`**
     * For each process template: number of projects using it.
     * Highlights unused or rarely used processes.
  4. **`fields_project_counts`**
     * For each custom field: number of projects referencing it.
     * Identifies highly reused fields vs. one-off “snowflake” fields.

  * Path:
    ```
    outputs/<ADO_ORG>/ado_project_fields.xlsx
    ```

* **Developer conveniences:**
  * Script supports skipping CSV generation (useful during development) 
    - via BUILD_CSV flag (hardcoded for now, just change it directly when testing)
    - in this mode, only the Excel workbook is rebuilt.
  * CSV writing and Excel writing are separated into functions for clarity.

* **Notes:**
  * No external references or pagination complexities — ADO’s WIT/fields endpoints return everything in one call.
  * ADO process information is fetched per-project; there is no bulk endpoint.
  * All aggregations use simple pandas groupings (`groupby`, `nunique`).


### `ado/demote_org_users.py`

*(consumes `users_latest.csv` and updates licenses in ADO)*

**Purpose:**
Evaluate all users from the latest entitlement snapshot, flag those eligible for license demotion (e.g., Basic → Stakeholder), and optionally execute the demotion in Azure DevOps via JSON Patch.
Supports three execution modes: **DRY_RUN**, **DEMOTE_ONE**, and **DEMOTE_ALL**.


**Key steps:**

1. **Load input dataset**
   * Reads:
     ```
     outputs/<ADO_ORG>/users_latest.csv
     ```
   * This file is produced by the separate nightly scan script (`scan_org_users.py`).

2. **Determine if re-analysis is needed**
   * Compares timestamps of:
     * `users_latest.csv` (input)
     * `users_with_status.csv` (output)
   * If input is newer → analysis must be re-run.
   * (Note: timestamp quirks in CI environments may make this conservative.)

3. **Analyze and flag users**
   * Adds or updates a `Demotion_Status` column with:
     * `""` (default)
     * `"Demote"` (candidate)
     * `"Demote DONE"` (after actual PATCH)
   * A user is marked `"Demote"` if:
     * License source is **account** (not MSDN)
     * Current license is **not** already Stakeholder
     * Inactivity ≥ configured threshold (`DEMOTE_THRESHOLD_DAYS`)
   * Sorting is applied so the most inactive appear at the top.

4. **Persist status dataset**
   * Writes:
     ```
     outputs/<ORG>/users_with_status.csv
     ```
   * This serves as the definitive snapshot for the demotion step.


**Execution Modes**

Controlled via environment variable:
```
EXECUTION_MODE = { DRY_RUN | DEMOTE_ONE | DEMOTE_ALL }
```

* **DRY_RUN**
  * No changes sent to Azure DevOps.
  * Prints clean, full table of all candidates.
  * Safest mode and default.

* **DEMOTE_ONE**
  * Applies one license demotion only (the top candidate by inactivity).
  * Sends a JSON Patch request to:
    ```
    PATCH https://vsaex.dev.azure.com/<ORG>/_apis/userentitlements/<UserEntitlementId>?api-version=7.1-preview.3
    ```
  * Payload (JSON Patch syntax):
    ```json
    [
      {
        "op": "replace",
        "path": "/accessLevel",
        "value": {
          "accountLicenseType": "stakeholder",
          "licensingSource": "account"
        }
      }
    ]
    ```
  * After success, marks the row as `"Demote DONE"` in the status CSV.

* **DEMOTE_ALL**
  * Intended to loop through all `"Demote"` rows and PATCH each user.
  * Currently locked as a safety mechanism until the flow is battle-tested.


**Input/Output Files**
- Input (read): ```outputs/<ADO_ORG>/users_latest.csv```
- Output (written): ```outputs/<ADO_ORG>/users_with_status.csv```

Includes columns:
* `UserEntitlementId` ← used in PATCH URL
* `Email`
* `License`
* `Source`
* `Days Inactive`
* `Demotion_Status` ( "", "Demote", "Demote DONE" )

**Developer Notes & Behavior**
  * Uses the **ADO Licensing API** (`vsaex.dev.azure.com`) — different domain than standard ADO REST.
  * All REST updates use **JSON Patch** (`application/json-patch+json`).
  * Safety-first design: nothing destructive happens unless explicitly switched to `DEMOTE_ONE` or `DEMOTE_ALL`.
  * CSV-driven architecture makes behavior transparent and traceable for audit or rollback.
  * Script is intended to be run after the nightly scan workflow (but can be run manually too).

**Typical usage in CI/CD**

A standard flow is:

1. **Nightly GitHub Action** runs `get_org_users.py` → generates fresh `users_latest.csv`.
2. **Manual or scheduled** job runs `demote_org_users.py` in:

   * **DRY_RUN** first (report only)
   * **DEMOTE_ONE** demote most inactive users one by one and check logs until happy all works fine
   * **DEMOTE_ALL** later (once fully validated)
