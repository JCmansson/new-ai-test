#!/usr/bin/env python3
"""
fetch_bc_date.py
-----------------
Fetch configuration tables from Microsoft Dynamics 365 Business Central (OData)
for multiple companies and APIs, and export them into a single Excel workbook
with one sheet per (company × API) combination.

TXO patterns used:
- Logger singleton and hierarchical context logging
- Hard-fail configuration access
- ApiManager/create_rest_api for HTTP
- Dir.* for path management
- ProcessingResults pattern for final ✅/❌ summary
- TxoDataHandler.get_utc_timestamp() for timestamps

Run:
    python src/fetch_bc_date.py chris test
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, TYPE_CHECKING
from pathlib import Path

# TXO utils (do not replace with custom functions)
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir, get_path
from utils.api_factory import ApiManager
from utils.exceptions import (
    HelpfulError, ApiError, ApiAuthenticationError, ApiTimeoutError,
    FileOperationError, ConfigurationError
)

if TYPE_CHECKING:
    import pandas as pd  # type: ignore

logger = setup_logger()
data_handler = TxoDataHandler()


@dataclass
class ProcessingResults:
    """Track operation results for user-friendly summary."""
    created: List[str] = field(default_factory=list)   # created outputs (sheets/files)
    updated: List[str] = field(default_factory=list)   # reserved (not used here)
    failed: List[str] = field(default_factory=list)
    expected_errors: int = 0

    def summary(self) -> str:
        total_success = len(self.created) + len(self.updated)
        if self.failed:
            return (f"❌ Completed with {len(self.failed)} failures: "
                    f"{len(self.created)} created, {len(self.updated)} updated, "
                    f"{len(self.failed)} failed")
        expected_note = (f" ({self.expected_errors} handled expected duplicates)"
                         if self.expected_errors > 0 else "")
        return (f"✅ All {total_success} operations successful: "
                f"{len(self.created)} created, {len(self.updated)} updated{expected_note}")


def _safe_sheet_name(name: str) -> str:
    """Excel sheet name constraints: max 31 chars, disallow : \\ / ? * [ ]"""
    invalid = set(':\\/?*[]')
    cleaned = ''.join(ch for ch in name if ch not in invalid)
    return cleaned[:31] if len(cleaned) > 31 else cleaned


def _build_bc_url(config: Dict[str, Any], environment_name: str, company: str, api_name: str) -> str:
    base_url = config['global']['api-base-url'].rstrip('/')
    api_version = config['global']['api-version']
    tenant_id = config['global']['tenant-id']
    # Example:
    # https://api.businesscentral.dynamics.com/v2.0/{tenant}/{environment}/ODataV4/Company('TXO')/IntercompanyPartner
    return (f"{base_url}/{api_version}/{tenant_id}/{environment_name}/ODataV4/"
            f"Company('{company}')/{api_name}")


def _to_dataframe(records: List[Dict[str, Any]]):
    """Create a DataFrame only when needed (lazy import)."""
    import pandas as pd  # Lazy import to follow TXO performance guidance
    if not records:
        # Create an empty DF with a placeholder column so Excel has a table
        return pd.DataFrame([{"_no_rows": True}]).iloc[0:0]
    return pd.DataFrame.from_records(records)


def main() -> None:
    # 1) Initialize with TXO patterns
    config = parse_args_and_load_config(
        "Fetch Business Central configuration tables → Excel", require_token=True
    )

    try:
        bc = config['business-central']
        environment_name = bc['environment-name']
        companies: List[str] = bc['companies']
        apis: List[str] = bc['apis']
        excel_filename: str = config['script-behavior']['excel-output-filename']
    except KeyError as e:
        raise ConfigurationError(f"Missing configuration key: {e}") from e

    if not companies or not apis:
        raise HelpfulError(
            what_went_wrong="No companies or APIs defined.",
            how_to_fix="Fill 'business-central.companies' and 'business-central.apis' in your org-env config.",
            example='{"business-central": {"environment-name": "TestSE", "companies": ["TXO"], "apis": ["IntercompanyPartner"]}}'
        )

    # 2) Fetch and stage data
    results = ProcessingResults()
    sheets: Dict[str, 'pd.DataFrame'] = {}

    with ApiManager(config) as manager:
        api = manager.get_rest_api(require_auth=True)
        env_label = config['_env_type'].title()

        for company in companies:
            for api_name in apis:
                context = f"[{env_label}/{company}/{api_name}]"
                url = _build_bc_url(config, environment_name, company, api_name)
                logger.info(f"{context} GET {url}")
                try:
                    payload = api.get(url)  # TxoRestAPI handles retries, rate limits, auth
                    # OData returns {"value": [...]}
                    records = payload.get('value') if isinstance(payload, dict) else None
                    if records is None:
                        # Soft-fail OK for external data as per ADR-B003
                        logger.warning(f"{context} Unexpected response format; coercing to list")
                        records = payload if isinstance(payload, list) else []

                    df = _to_dataframe(records)  # Lazy pandas import
                    sheet_name = _safe_sheet_name(f"{company}__{api_name}")
                    sheets[sheet_name] = df
                    results.created.append(f"BusinessCentral/{company}/{api_name}")
                    logger.info(f"{context} Retrieved {len(df)} rows")
                except ApiAuthenticationError as e:
                    msg = f"{context} Authentication error: {e}"
                    logger.error(msg)
                    results.failed.append(f"BusinessCentral/{company}/{api_name}: auth failed")
                except ApiTimeoutError as e:
                    msg = f"{context} Timeout: {e}"
                    logger.error(msg)
                    results.failed.append(f"BusinessCentral/{company}/{api_name}: timeout")
                except ApiError as e:
                    msg = f"{context} API error: {e}"
                    logger.error(msg)
                    results.failed.append(f"BusinessCentral/{company}/{api_name}: api error")
                except Exception as e:  # Fallback; specific errors logged above when available
                    logger.error(f"{context} Unexpected error: {e}")
                    results.failed.append(f"BusinessCentral/{company}/{api_name}: unexpected error")

    # 3) Write Excel (one sheet per (company×api))
    output_path: Path = get_path(Dir.OUTPUT, excel_filename, ensure_parent=True)
    try:
        # Prefer using pandas.ExcelWriter to guarantee multi-sheet output
        import pandas as pd  # Lazy import here too
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        logger.info(f"[{config['_env_type'].title()}/Excel/Write] Wrote {output_path}")
    except Exception as e:
        raise FileOperationError(f"Failed to write Excel file: {output_path}") from e

    # 4) Save a machine-readable summary
    ts = data_handler.get_utc_timestamp()
    summary = {
        "timestamp": ts,
        "org": config["_org_id"],
        "env": config["_env_type"],
        "environment-name": environment_name,
        "companies": companies,
        "apis": apis,
        "excel-file": str(output_path.name),
        "created": results.created,
        "failed": results.failed,
    }
    data_handler.save(summary, Dir.OUTPUT, f"bc-fetch-summary_{ts}.json")

    # Final human-friendly summary
    logger.info(results.summary())


if __name__ == "__main__":
    main()