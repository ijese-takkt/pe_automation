# PE Automation

- Scripts and jobs for **Platform Engineering** automation

# Docs

- python 3.12
- ado jobs go to ado folder
- venv folder holds virtual env for python 
- start_venv.bat starts virtual environment and keeps cmd window open

## Fetch org users

- Microsoft recommends using rest /userentitlements api instead of graph api (entitlements vs identities)
    - https://developercommunity.visualstudio.com/t/what-is-the-different-between-get-user-entitlement/1080296
    - https://learn.microsoft.com/en-us/rest/api/azure/devops/memberentitlementmanagement/user-entitlements/search-user-entitlements?view=azure-devops-rest-7.1
- MSDN licenses should NOT be downgraded
- api bug: continuationToken often returns '' (null)
    - workaround: add &top=30000 as parameter for /userentitlements, no paging needed then
