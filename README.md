# PE Automation

Scripts and jobs for **Platform Engineering** automation.


## General

* Python **3.12**
* Azure DevOps–related code lives under `ado/`
  * Any generated data goes under `ado/outputs/<ORG>/`


## Local Development

* these are not in repo but you need them or equivalents to develop/test locally
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
* If `ado/outputs/KKEU/users_latest.csv` changed, commits and pushes it back to the repo
* GitHub’s UI can display the CSV directly (no download needed)


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

    * `Email`, `License`, `Source`, `Last Login`, `Last Login Date`, `Days Inactive`
  * Path: `ado/outputs/<ORG>/users_latest.csv`

    * For `KKEU`: `ado/outputs/KKEU/users_latest.csv`
