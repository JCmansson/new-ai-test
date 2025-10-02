# src/fetch_bc_data.py

from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir, get_path
from utils.api_factory import create_rest_api
from utils.exceptions import ApiAuthenticationError, ApiTimeoutError, HelpfulError

import pandas as pd
from dataclasses import dataclass, field
from typing import List
from datetime import datetime, timezone


# 🔹 UTC timestamp helper (ADR-B006)
def get_utc_timestamp() -> str:
    """Return current UTC timestamp in TXO format YYYYMMDD_HHMMSSZ"""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


# 🔹 Standardized Results Tracking (ADR-B007, extended for 'empty')
@dataclass
class ProcessingResults:
    """Track all operation results for summary reporting"""
    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    empty: List[str] = field(default_factory=list)
    expected_errors: int = 0

    def summary(self) -> str:
        total_success = len(self.created) + len(self.updated)
        if self.failed:
            return (f"❌ Completed with {len(self.failed)} failures "
                    f"({len(self.empty)} empty): "
                    f"{len(self.created)} created, {len(self.updated)} updated, "
                    f"{len(self.failed)} failed")
        elif self.empty:
            return (f"⚠️ Completed with empty results: "
                    f"{len(self.created)} created, {len(self.updated)} updated, "
                    f"{len(self.empty)} empty")
        else:
            return (f"✅ All {total_success} operations successful: "
                    f"{len(self.created)} created, {len(self.updated)} updated")


# 🔹 Initialize mandatory TXO utilities
logger = setup_logger()
data_handler = TxoDataHandler()


def main():
    # 1. Initialize with TXO script_runner
    config = parse_args_and_load_config("Fetch Business Central data", require_token=True)
    env_type = config["_env_type"]
    org_id = config["_org_id"]
    base_ctx = f"[{env_type.title()}/{org_id}/BCData]"

    # 2. Load BC configuration (hard-fail access)
    try:
        bc_env = config["business-central"]["environment-name"]
        companies = config["business-central"]["companies"]
        apis = config["business-central"]["apis"]
    except KeyError as e:
        raise HelpfulError(
            what_went_wrong=f"Missing config key: {e}",
            how_to_fix="Check config/{org_id}-{env_type}-config.json against schema",
            example="Ensure 'business-central' contains 'environment-name', 'companies', 'apis'"
        )

    # 3. Resolve global connection details
    try:
        base_url = config["global"]["api-base-url"]
        api_version = config["global"]["api-version"]
        tenant_id = config["global"]["tenant-id"]
    except KeyError as e:
        raise HelpfulError(
            what_went_wrong=f"Missing global config key: {e}",
            how_to_fix="Check 'global' section in config file",
            example="Ensure 'api-base-url', 'api-version', 'tenant-id' exist"
        )

    # 4. Create API client
    try:
        api = create_rest_api(config, require_auth=True)
    except Exception as e:
        raise ApiAuthenticationError(f"{base_ctx} Failed to create API client: {e}")

    results = ProcessingResults()
    excel_sheets = {}

    # 5. Fetch data from BC APIs
    for company in companies:
        for api_name in apis:
            call_ctx = f"[{bc_env}/{company}/{api_name}]"
            try:
                # ✅ Correct URL construction
                url = (
                    f"{base_url}/{api_version}/{tenant_id}/{bc_env}"
                    f"/ODataV4/Company('{company}')/{api_name}"
                )
                response = api.get(url)
                df = pd.DataFrame(response.get("value", []))

                # ✅ Drop system column
                if "@odata.etag" in df.columns:
                    df = df.drop(columns=["@odata.etag"])

                sheet_name = f"{company}_{api_name}"
                excel_sheets[sheet_name] = df

                if df.empty:
                    results.empty.append(f"{company}/{api_name}")
                    logger.warning(f"{call_ctx} ⚠️ Returned 0 rows")
                else:
                    results.created.append(f"BCAPI/{company}/{api_name}")
                    logger.info(f"{call_ctx} ✅ Retrieved {len(df)} rows")

            except ApiTimeoutError as e:
                results.failed.append(f"{company}/{api_name}: {e}")
                logger.error(f"{call_ctx} ❌ Timeout: {e}")
            except Exception as e:
                results.failed.append(f"{company}/{api_name}: {e}")
                logger.error(f"{call_ctx} ❌ Failed: {e}")

    # 6. Save Excel file via explicit ExcelWriter with UTC suffix
    try:
        timestamp = get_utc_timestamp()
        output_path = get_path(Dir.OUTPUT, f"{org_id}-{env_type}-bc-data-{timestamp}.xlsx")

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, df in excel_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        logger.info(f"{base_ctx} Saved Excel workbook with {len(excel_sheets)} sheets to {output_path}")
    except Exception as e:
        raise HelpfulError(
            what_went_wrong=f"Failed to save Excel workbook: {e}",
            how_to_fix="Check output/ directory and ensure openpyxl is installed",
            example="pip install openpyxl"
        )

    # 7. Final summary
    logger.info(f"{base_ctx} {results.summary()}")
    if results.failed:
        for f in results.failed:
            logger.error(f"{base_ctx} Failure detail: {f}")
    if results.empty:
        for e in results.empty:
            logger.warning(f"{base_ctx} Empty detail: {e}")


if __name__ == "__main__":
    main()
