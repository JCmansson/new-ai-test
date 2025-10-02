# Fetch Business Central Data

## Purpose / Scope

This script retrieves data from Microsoft Dynamics 365 Business Central
(BC) using the TXO framework. It authenticates via OAuth client
credentials, fetches data from configured companies and APIs, and
exports results into a multi-sheet Excel workbook. This standardization
ensures consistent data extraction across orgs/environments, fulfilling
ADR-B009 requirements for clarity and reproducibility.

## Prerequisites

-   Python 3.13+ installed

-   Virtual environment (standardized as `.venv` per ADR-B008)

-   Dependencies installed:

    ``` bash
    pip install -r requirements.txt
    ```

-   Configuration and secrets files created in `config/`

## Setup Instructions

1.  **Clone the repo**

    ``` bash
    git clone <repo-url>
    cd <repo-dir>
    ```

2.  **Create and activate a virtual environment**

    ``` bash
    python -m venv .venv
    source .venv/bin/activate   # Linux / macOS
    .venv\Scripts\activate    # Windows
    ```

3.  **Install dependencies**

    ``` bash
    pip install -r requirements.txt
    ```

4.  **Prepare config files**

    -   Place `config/{org}-{env}-config.json` and
        `config/{org}-{env}-config-secrets.json` in `config/`

    -   Validate against `schemas/org-env-config-schema.json` (optional
        pre-check):

        ``` bash
        jsonschema -i config/chris-test-config.json schemas/org-env-config-schema.json
        ```

5.  **Run script**

    -   CLI:

        ``` bash
        python src/fetch_bc_data.py <org_id> <env_type>
        ```

        Example:

        ``` bash
        python src/fetch_bc_data.py chris test
        ```

    -   IDE (PyCharm):\
        Use **Run Configurations**, set
        `Script path = src/fetch_bc_data.py`\
        and `Parameters = chris test`

## Configuration

Input config files must validate against JSON Schema
(`schemas/org-env-config-schema.json`).

### Main Config (`config/{org}-{env}-config.json`)

-   **global** → API connection details\
-   **script-behavior** → retry, timeouts, circuit breaker, etc.\
-   **business-central** → environment-name, companies, apis

### Secrets Config (`config/{org}-{env}-config-secrets.json`)

-   Flat-only key-value structure per ADR-B011

Validation is performed automatically at runtime; schema failures cause
hard-stop (ADR-B004).

## Output Contract

Outputs an Excel workbook with one sheet per company/api combination.

-   **Filename pattern (ADR-B006):**\
    `{org}-{env}-bc-data-{UTC_TIMESTAMP}.xlsx`\
    Example: `chris-test-bc-data-20250928_194507Z.xlsx`

-   System columns like `@odata.etag` are removed.\

-   Multi-sheet export uses `pandas.ExcelWriter` with `openpyxl`.

## Logging Contract

Logs follow ADR-B005 context rules:

-   Per-call:
    `[bc_env/company/api] ✅ Retrieved X rows | ⚠️ Returned 0 rows | ❌ Error`\
-   Save confirmation: `[Env/Org/BCData] Saved Excel workbook...`\
-   Summary: All operations successful / Completed with empty results /
    Completed with failures

## ProcessingResults Summary

At the end of execution, ProcessingResults outputs a standardized
summary (ADR-B007):

-   **Success:**\
    `✅ All 6 operations successful: 6 created, 0 updated`

-   **Warning:**\
    `⚠️ Completed with empty results: 5 created, 0 updated, 1 empty`

-   **Failure:**\
    `❌ Completed with 1 failures (2 empty): 4 created, 0 updated, 1 failed`

## Troubleshooting

Common HelpfulError cases:

-   **Schema validation failed** → check config keys vs schema\
-   **OAuth error** → verify client-id, tenant-id, client-secret in
    Azure AD\
-   **Excel save error** → ensure `openpyxl` is installed and `output/`
    directory is writable\
-   **Empty results** → shown as warnings, not errors (unless configured
    otherwise)
