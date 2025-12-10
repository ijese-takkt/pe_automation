# PE Automation

Scripts and jobs for **Platform Engineering** automation.


## General

* Python **3.12**
* Azure DevOps–related code lives under `ado/`
  * Any generated data goes under `ado/outputs/<ADO_ORG>/`


## Local Development

* these are not in repo but you need them or equivalents to develop/test locally
* you probably want to create venv then activate it to work from there
    * venv needs to be OUTSIDE the repo, e.g. in its parent folder
* `venv/` holds the local Python virtual environment
* `start_venv.bat` activates the venv and keeps the cmd window open
* For local development, set `ADO_ORG` and `ADO_PAT` via a **.bat / shell script outside the repo**
  (to avoid committing PATs in plaintext)


## Secrets (GitHub)

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

Here’s the matching documentation section for your new script, in the same style and level of detail—clean, practical, and focusing on what matters.


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


## TODO

Funtionality:
* single log of who has been actually demoted, when and why
* project stats collector

Other:
* document all
* keep last 5 invocations (logs, csvs) just timestamp them
* proper logs for user extractor and demoting

### Not yet

* demote all (manually, later scheduled)