# Business Central Data Fetch - In-Depth Documentation

> **Target Audience**: Experienced developers and maintainers
> **Purpose**: Complete understanding for customization, extension, and maintenance

---

## Architecture & Design Rationale

### Why This Script Exists

**Business Problem**: TXO operates across multiple Business Central environments with different companies, each having intercompany configurations that must be validated for consistency. Manual validation is error-prone and time-consuming.

**Solution Approach**: Automated API-based data extraction that:
- Fetches configuration data from all company/API combinations
- Presents data in analyzable Excel format
- Provides clear success/failure tracking
- Supports easy extension to new environments and APIs

### Why TXO Framework Patterns

**Hard-Fail Configuration (ADR-B003)**:
```python
# Why this matters for BC integration
bc_config = config['business-central']  # Hard-fail if missing
companies = bc_config['companies']  # Hard-fail if misconfigured
```

**Rationale**: Business Central API URLs require exact company names and tenant IDs. Silent defaults would cause authentication failures or wrong data retrieval. Better to fail immediately with clear error than to proceed with incorrect configuration.

**Hierarchical Logging Context (ADR-B006)**:
```python
context = f"[{environment}/{company}/{api_name}]"
logger.info(f"{context} Starting API call")
```

**Rationale**: When processing 3 environments × 10 companies × 5 APIs = 150 API calls, hierarchical context makes it immediately clear which specific call failed. This aligns with TXO's ERD structure (Tenant → BC_Environment → Company → API) and enables quick troubleshooting.

**ProcessingResults Pattern (ADR-B007)**:
```python
results = ProcessingResults()
results.add_success(context, record_count)
results.add_warning(context, "0 records")
results.add_failure(context, "404 - Not Found")
```

**Rationale**: Business stakeholders need executive summaries, not log files. The pattern provides immediate visibility into bulk operations: "5 successful, 1 warning, 2 failed" is actionable information.

**OAuth Token Management (ADR-B008)**:
```python
config = parse_args_and_load_config(
    "Fetch BC data", 
    require_token=True  # Explicit requirement
)
```

**Rationale**: BC API requires authentication, so token is mandatory. The framework handles OAuth flow, token caching, and automatic injection as `config['_token']`. Script just declares the requirement.

---

## Detailed Configuration Options

### Global Configuration Section

```json
{
  "global": {
    "tenant-id": "c1061658-0240-4cbc-8da5-165a9caa30a3",
    "client-id": "your-azure-ad-app-id",
    "oauth-scope": "https://api.businesscentral.dynamics.com/.default"
  }
}
```

**tenant-id**: Azure AD tenant UUID where Business Central is hosted
- **Required**: Yes (hard-fail if missing)
- **Format**: UUID string
- **How to find**: Azure Portal → Azure Active Directory → Overview → Tenant ID
- **Example**: `c1061658-0240-4cbc-8da5-165a9caa30a3`

**client-id**: Azure AD application (service principal) ID
- **Required**: Yes (hard-fail if missing)
- **Format**: UUID string
- **How to obtain**: Azure Portal → App Registrations → Create/Select App → Application ID
- **Permissions needed**: API permissions for Business Central (Dynamics 365 Business Central)

**oauth-scope**: OAuth 2.0 scope for BC API access
- **Required**: Yes (hard-fail if missing)
- **Standard value**: `https://api.businesscentral.dynamics.com/.default`
- **Do not change**: Unless using different BC API endpoint

### Business Central Configuration Section

```json
{
  "business-central": {
    "base-url": "https://api.businesscentral.dynamics.com/v2.0",
    "environments": ["TestSE", "Production"],
    "companies": ["AFHS", "TXO", "CRONUS SE", "Fabrikam"],
    "apis": ["IntercompanyPartner", "IntercompanySetup", "Customer", "Vendor"]
  }
}
```

**base-url**: BC API base endpoint
- **Default**: `https://api.businesscentral.dynamics.com/v2.0`
- **When to change**: Different BC cloud (Government, China, etc.) or on-premises
- **On-premises example**: `https://your-server:7048/BC200/ODataV4`

**environments**: Array of BC environment names
- **Required**: Yes (hard-fail if empty)
- **Format**: Array of strings matching BC environment technical names
- **Case-sensitive**: Yes - must match exactly
- **How to find**: BC Admin Center → Environments → Environment name
- **Common values**: `Production`, `Sandbox`, `TestSE`, `QA`

**companies**: Array of company technical names
- **Required**: Yes (hard-fail if empty)
- **Format**: Array of strings matching BC company technical names
- **Case-sensitive**: Yes - must match exactly
- **How to find**: BC → Companies → Company Information → Name field
- **Note**: Display name may differ from technical name

**apis**: Array of OData API endpoint names
- **Required**: Yes (hard-fail if empty)
- **Format**: Array of strings matching BC OData entity names
- **Case-sensitive**: Yes - must match exactly
- **Common entities**: `IntercompanyPartner`, `IntercompanySetup`, `Customer`, `Vendor`, `Item`, `SalesOrder`, `PurchaseOrder`, `GeneralLedgerEntry`
- **How to find**: BC API documentation or `{base-url}/{tenant}/{env}/ODataV4/Company('{company}')/$metadata`

### Script Behavior Configuration

```json
{
  "script-behavior": {
    "api-timeouts": {
      "rest-timeout-seconds": 60
    },
    "retry-strategy": {
      "max-retries": 3,
      "backoff-factor": 2.0
    },
    "jitter": {
      "min-factor": 0.8,
      "max-factor": 1.2
    }
  }
}
```

**api-timeouts.rest-timeout-seconds**:
- **Default**: 60
- **Purpose**: HTTP request timeout before giving up
- **When to increase**: Large datasets (>10,000 records per API)
- **When to decrease**: Fast APIs with small datasets
- **Range**: 10-300 seconds

**retry-strategy.max-retries**:
- **Default**: 3
- **Purpose**: Number of retry attempts on transient failures (500, 503, network errors)
- **When to increase**: Unreliable network or BC environment under load
- **When to decrease**: Fast-fail scenarios for testing
- **Range**: 0-10 retries

**retry-strategy.backoff-factor**:
- **Default**: 2.0
- **Purpose**: Exponential backoff multiplier between retries
- **Formula**: `delay = backoff_factor ^ retry_attempt` seconds
- **Example**: With 2.0 → delays are 2s, 4s, 8s
- **Range**: 1.0-5.0

**jitter.min-factor / max-factor**:
- **Default**: 0.8 / 1.2
- **Purpose**: Randomize retry delays to avoid thundering herd
- **Formula**: `actual_delay = base_delay * random(min_factor, max_factor)`
- **Example**: 5s delay becomes random(4s, 6s)
- **Why**: Multiple scripts retrying simultaneously can overwhelm BC

---

## API URL Construction

### URL Pattern
```
https://api.businesscentral.dynamics.com/v2.0/{tenant-id}/{environment}/ODataV4/Company('{company}')/{api}
```

### Real Examples
```
https://api.businesscentral.dynamics.com/v2.0/c1061658-0240-4cbc-8da5-165a9caa30a3/TestSE/ODataV4/Company('TXO')/IntercompanyPartner

https://api.businesscentral.dynamics.com/v2.0/c1061658-0240-4cbc-8da5-165a9caa30a3/Production/ODataV4/Company('AFHS')/Customer
```

### URL Component Details

**Company name encoding**: Single quotes are required
- Correct: `Company('TXO')`
- Wrong: `Company(TXO)`, `Company("TXO")`

**Space handling in company names**:
- Companies with spaces: `Company('CRONUS SE')`
- Framework handles URL encoding automatically

**API name exact match**:
- OData is case-sensitive
- `IntercompanyPartner` ≠ `intercompanypartner`
- Check BC metadata for exact names

---

## Error Handling Patterns

### Three-Tier Error Strategy

**1. Fatal Errors - Stop Immediately**
```python
# Configuration errors
raise HelpfulError(
    what_went_wrong="Missing business-central config",
    how_to_fix="Add business-central section",
    example='{ "business-central": { ... } }'
)
```
**When**: Missing configuration, authentication failure
**Behavior**: Script exits immediately
**Rationale**: Cannot proceed without valid config or auth

**2. Failures - Track and Continue**
```python
# HTTP errors
except ApiError as e:
    results.add_failure(context, f"{e.status_code} - {str(e)}")
    logger.error(f"{context} ❌ {error_msg}")
    continue  # Process remaining APIs
```
**When**: Individual API call fails (404, 500, timeout)
**Behavior**: Log error, track in results, continue with next API
**Rationale**: One bad company/API shouldn't block others

**3. Warnings - Log and Continue**
```python
# Empty responses
if len(records) == 0:
    results.add_warning(context, "0 records (empty response)")
    logger.warning(f"{context} No records returned")
    continue
```
**When**: API succeeds but returns no data
**Behavior**: Log warning, don't create sheet, continue
**Rationale**: Empty data might be valid (no intercompany partners configured)

### Common HTTP Error Codes

**401 Unauthorized**:
- **Cause**: Invalid/expired token, wrong client-id/secret
- **Solution**: Verify Azure AD app credentials
- **Script behavior**: Fails immediately (cannot continue without auth)

**404 Not Found**:
- **Cause**: Company name wrong, API endpoint wrong, environment wrong
- **Solution**: Check company/API names in BC, verify they're in the environment
- **Script behavior**: Logs failure, continues with other combinations

**429 Too Many Requests**:
- **Cause**: Rate limit exceeded
- **Solution**: Framework handles automatic retry with backoff
- **Script behavior**: Waits and retries automatically

**500/503 Internal Server Error**:
- **Cause**: BC service issue, temporary overload
- **Solution**: Framework retries automatically
- **Script behavior**: Retries up to max-retries, then fails

**504 Gateway Timeout**:
- **Cause**: Query too complex, large dataset, BC under load
- **Solution**: Increase rest-timeout-seconds, reduce batch size
- **Script behavior**: Retries with longer timeout

---

## Data Structure & OData Response Format

### Standard OData Response
```json
{
  "value": [
    {
      "SystemId": "guid-here",
      "Code": "PARTNER001",
      "Name": "Partner Company",
      "InboxType": "Database",
      "InboxDetails": "IC_INBOX"
    }
  ],
  "@odata.context": "https://api.../metadata#Company('TXO')/IntercompanyPartner"
}
```

### How the Script Handles Responses

**1. Extract 'value' array**:
```python
if isinstance(response, dict) and 'value' in response:
    records = response['value']
```
**Why**: BC OData always wraps results in 'value' array

**2. Convert to DataFrame**:
```python
import pandas as pd
sheets = {name: pd.DataFrame(data) for name, data in all_data.items()}
```
**Why**: pandas preserves all fields and data types automatically

**3. Save as Excel**:
```python
data_handler.save_with_timestamp(sheets, Dir.OUTPUT, filename, add_timestamp=True)
```
**Why**: Multi-sheet Excel with UTC timestamp follows TXO standards

### Excel Sheet Structure

**Sheet Name Format**: `{Environment}_{Company}_{API}`
- Example: `TestSE_AFHS_IntercompanyPartner`
- Underscores prevent Excel sheet name issues
- Max 31 characters (Excel limitation)

**Column Names**: Direct from OData response
- Preserves original field names (camelCase from BC)
- All fields included (no filtering)

**Data Types**: Auto-detected by pandas
- Dates → Excel date format
- Numbers → Excel numeric format
- Text → Excel text format

---

## Developer Extension Notes

### Adding New API Endpoints

**Step 1**: Update configuration
```json
{
  "business-central": {
    "apis": [
      "IntercompanyPartner",
      "IntercompanySetup",
      "Customer",        // Add new endpoint
      "Vendor",          // Add new endpoint
      "Item"             // Add new endpoint
    ]
  }
}
```

**Step 2**: Run script - no code changes needed
```bash
python src/fetch_bc_data.py chris test
```

**That's it!** The script automatically processes all configured APIs.

### Adding New Environments

**Update configuration**:
```json
{
  "business-central": {
    "environments": ["TestSE", "Production", "Sandbox"]
  }
}
```

**No code changes needed** - framework loops through all environments.

### Adding New Companies

**Update configuration**:
```json
{
  "business-central": {
    "companies": ["AFHS", "TXO", "CRONUS SE", "NewCompany"]
  }
}
```

**No code changes needed** - framework loops through all companies.

### Custom Data Filtering

**Current behavior**: Fetches all records from API

**To add filtering**, modify `fetch_api_data()`:
```python
def fetch_api_data(api, url: str, context: str, filters: Optional[Dict] = None) -> Optional[List[Dict]]:
    # Add OData query parameters
    if filters:
        query_params = []
        if 'top' in filters:
            query_params.append(f"$top={filters['top']}")
        if 'filter' in filters:
            query_params.append(f"$filter={filters['filter']}")
        
        if query_params:
            url = f"{url}?{'&'.join(query_params)}"
    
    response = api.get(url)
    # ... rest of function
```

**Usage example**:
```python
# Only fetch first 100 records
filters = {'top': 100}

# Filter by specific criteria
filters = {'filter': "Code eq 'PARTNER001'"}
```

### Custom Output Formats

**Current**: Multi-sheet Excel

**To add CSV output**:
```python
# After collecting all_data
for sheet_name, records in all_data.items():
    df = pd.DataFrame(records)
    csv_filename = f"{sheet_name}.csv"
    data_handler.save(df, Dir.OUTPUT, csv_filename)
```

**To add JSON output**:
```python
import json
json_filename = f"{org_id}-{env_type}-bc-data.json"
data_handler.save(all_data, Dir.OUTPUT, json_filename)
```

### Custom Validation Rules

**Add validation after data fetch**:
```python
def validate_intercompany_setup(records: List[Dict]) -> List[str]:
    """Validate intercompany setup rules."""
    issues = []
    
    for record in records:
        # Example: Check IC partner has inbox configured
        if not record.get('InboxDetails'):
            issues.append(f"Partner {record['Code']} missing inbox details")
        
        # Example: Check inbox type is valid
        if record.get('InboxType') not in ['Database', 'File Location']:
            issues.append(f"Partner {record['Code']} invalid inbox type")
    
    return issues

# Call after fetch
validation_issues = validate_intercompany_setup(records)
if validation_issues:
    for issue in validation_issues:
        logger.warning(f"{context} Validation: {issue}")
```

### Integration with Other TXO Scripts

**Pass config to another script**:
```python
from other_script import process_bc_data

# After fetching data
processed = process_bc_data(all_data, config)
```

**Chain operations**:
```bash
# Fetch data
python src/fetch_bc_data.py chris test

# Process the output
python src/analyze_bc_data.py chris test --input output/chris-test-bc-data_*.xlsx
```

---

## Performance Considerations

### Current Performance Profile

**Sequential Processing**:
- One API call at a time
- Respects rate limiting
- Predictable execution time

**Typical execution time**:
- 3 environments × 3 companies × 2 APIs = 18 calls
- ~2 seconds per API call (including delays)
- Total: ~36 seconds

### Optimization Options

**1. Parallel API Calls** (Advanced):
```python
import concurrent.futures

def fetch_all_parallel(environments, companies, apis):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for env in environments:
            for company in companies:
                for api_name in apis:
                    future = executor.submit(fetch_one_api, env, company, api_name)
                    futures.append(future)
        
        results = [f.result() for f in futures]
    return results
```
**Trade-off**: Faster but harder to debug, may hit rate limits

**2. Batch API Calls** (If BC supports):
```python
# Some OData endpoints support $batch
# Check BC documentation for availability
```

**3. Caching** (For development):
```python
# Cache API responses during testing
if use_cache and cache_key in cache:
    return cache[cache_key]
```

---

## Comprehensive Configuration Example

### Full Production Configuration
```json
{
  "global": {
    "tenant-id": "c1061658-0240-4cbc-8da5-165a9caa30a3",
    "client-id": "12345678-1234-1234-1234-123456789abc",
    "oauth-scope": "https://api.businesscentral.dynamics.com/.default"
  },
  "business-central": {
    "base-url": "https://api.businesscentral.dynamics.com/v2.0",
    "environments": ["Production", "Sandbox", "UAT"],
    "companies": [
      "AFHS",
      "TXO", 
      "CRONUS SE",
      "Fabrikam Inc.",
      "Contoso Corporation"
    ],
    "apis": [
      "IntercompanyPartner",
      "IntercompanySetup",
      "Customer",
      "Vendor",
      "Item",
      "GeneralLedgerSetup"
    ]
  },
  "script-behavior": {
    "api-timeouts": {
      "rest-timeout-seconds": 120
    },
    "retry-strategy": {
      "max-retries": 5,
      "backoff-factor": 2.0
    },
    "jitter": {
      "min-factor": 0.8,
      "max-factor": 1.2
    },
    "rate-limiting": {
      "enabled": true,
      "calls-per-second": 5,
      "burst-size": 1
    },
    "circuit-breaker": {
      "enabled": true,
      "failure-threshold": 10,
      "timeout-seconds": 300
    },
    "debug-mode": false,
    "verbose-logging": false
  }
}
```

### Development Configuration
```json
{
  "global": {
    "tenant-id": "c1061658-0240-4cbc-8da5-165a9caa30a3",
    "client-id": "test-app-id",
    "oauth-scope": "https://api.businesscentral.dynamics.com/.default"
  },
  "business-central": {
    "base-url": "https://api.businesscentral.dynamics.com/v2.0",
    "environments": ["Sandbox"],
    "companies": ["CRONUS SE"],
    "apis": ["IntercompanyPartner"]
  },
  "script-behavior": {
    "api-timeouts": {
      "rest-timeout-seconds": 30
    },
    "retry-strategy": {
      "max-retries": 1,
      "backoff-factor": 1.0
    },
    "debug-mode": true,
    "verbose-logging": true
  }
}
```

---

## References & Related Documentation

### TXO Architecture Decision Records

**Business ADRs** (`ai/decided/txo-business-adr_v3.1.md`):
- **ADR-B003**: Hard-Fail Configuration Philosophy
- **ADR-B006**: Smart Logging Context Strategy (Environment/Company/API)
- **ADR-B007**: Standardized Operation Result Tracking
- **ADR-B008**: Token Optional by Default (this script requires token)
- **ADR-B010**: Standardized Project Directory Structure

**Technical Standards** (`ai/decided/txo-technical-standards_v3.1.md`):
- **ADR-T004**: Structured Exception Hierarchy
- **ADR-T006**: Factory Pattern for Complex Object Creation (API factory)
- **ADR-T009**: Docstring Standards

### TXO Framework Components

**Utils Reference** (`ai/decided/utils-quick-reference_v3.1.md`):
- `script_runner.parse_args_and_load_config()` - Script initialization
- `api_factory.create_rest_api()` - API client creation
- `load_n_save.TxoDataHandler` - File operations
- `path_helpers.Dir.*` - Type-safe directory constants
- `exceptions.*` - Custom exception hierarchy

### Business Central API Documentation

**Official Microsoft Docs**:
- [BC API Overview](https://docs.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/)
- [OData API Reference](https://docs.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/)
- [Authentication Guide](https://docs.microsoft.com/en-us/dynamics365/business-central/dev-itpro/administration/automation-apis-authentication)

**Metadata Endpoint**:
```
https://api.businesscentral.dynamics.com/v2.0/{tenant}/{env}/ODataV4/$metadata
```
Use this to discover available entities and their properties.

---

## Version History

**Version:** 1.0  
**Last Updated:** 2025-09-30

### v1.0 (Current)
- Initial release with multi-environment/company/API support
- Configurable endpoints and companies
- Multi-sheet Excel output with UTC timestamps
- Three-tier error handling (fatal/failure/warning)
- Hierarchical logging context aligned with TXO ERD
- ProcessingResults pattern for executive summaries

---

**Version:** 1.0  
**Domain:** Business Central Integration  
**Purpose:** Maintainer guide for BC data extraction script
