# TXO Utils Quick Reference v3.1

> **🚨 DO NOT INVENT THESE FUNCTIONS - THEY ALREADY EXIST**
>
> Use this reference to see what's available in `utils/` before writing new code.
> All functions follow TXO Business ADRs and Technical Standards.

---

## 🏗️ Script Setup & Configuration

### Script Initialization (`utils.script_runner`)

```python
from utils.script_runner import parse_args_and_load_config

# Most common pattern (no authentication needed)
config = parse_args_and_load_config("Process local data")

# API scripts (explicit token requirement)
config = parse_args_and_load_config("BC sync script", require_token=True)

# Returns config with injected fields:
# config["_org_id"] = "txo"
# config["_env_type"] = "prod"
# config["_token"] = "abc123..." (if require_token=True)
```

### Configuration Loading (`utils.config_loader`)

```python
from utils.config_loader import ConfigLoader, ConfigContext

# Direct usage
loader = ConfigLoader("txo", "prod")
config = loader.load_config(validate=True, include_secrets=True)

# Context manager pattern
with ConfigContext("txo", "prod") as config:
    api_url = config['global']['api-base-url']  # Hard-fail access
    token = config['_client-secret']  # Injected secret (kebab-case preserved)
```

### Logging (`utils.logger`)

```python
from utils.logger import setup_logger

# Singleton logger with mandatory security redaction
logger = setup_logger()  # Will sys.exit(1) if config files missing

# Hierarchical context logging
context = f"[{env_type.title()}/{company_name}/{api_name}]"
logger.info(f"{context} Processing started")
logger.debug(f"{context} Request payload: {payload}")  # Tokens auto-redacted
```

---

## 💾 Data Operations

### Universal Data Handler (`utils.load_n_save`)

```python
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir

data_handler = TxoDataHandler()

# Universal save - auto-detects format from data type + extension
data_handler.save(dict_data, Dir.OUTPUT, "report.json") -> Path  # JSON
data_handler.save(dataframe, Dir.OUTPUT, "data.xlsx") -> Path  # Excel
data_handler.save(dataframe, Dir.OUTPUT, "data.csv") -> Path  # CSV
data_handler.save("text", Dir.OUTPUT, "log.txt") -> Path  # Text

# UTC Timestamp saving (v3.1) - TXO standard format: 2025-01-25T143045Z
timestamp = data_handler.get_utc_timestamp() -> str  # "2025-01-25T143045Z"
data_handler.save_with_timestamp(data, Dir.OUTPUT, "report.json") -> Path  # report.json
data_handler.save_with_timestamp(data, Dir.OUTPUT, "report.json", add_timestamp=True) -> Path  # report_2025-01-25T143045Z.json

# Universal load - auto-detects format from extension
data = data_handler.load(Dir.DATA, "input.csv") -> DataFrame  # Returns pandas DataFrame
data = data_handler.load(Dir.CONFIG, "settings.json") -> dict  # Returns dict
data = data_handler.load(Dir.DATA, "document.txt") -> str  # Returns string

# Utility methods
exists = data_handler.exists(Dir.DATA, "file.csv", check_empty=True) -> bool
size = data_handler.get_size(Dir.OUTPUT, "report.xlsx") -> int  # bytes
data_handler.delete(Dir.TMP, "temp.json", safe=True) -> bool
```

### Path Management (`utils.path_helpers`)

```python
from utils.path_helpers import Dir, get_path, ProjectPaths

# Type-safe directory constants (ALWAYS use these)
Dir.CONFIG  # 'config'
Dir.DATA  # 'data'
Dir.OUTPUT  # 'output'
Dir.LOGS  # 'logs'
Dir.TMP  # 'tmp'
Dir.SCHEMAS  # 'schemas'
Dir.WSDL  # 'wsdl'

# Path construction with automatic parent creation
path = get_path(Dir.CONFIG, "settings.json") -> Path
path = get_path(Dir.OUTPUT, "report.xlsx", ensure_parent=True) -> Path

# Project paths access
paths = ProjectPaths.init()
print(f"Root: {paths.root}")
print(f"Config dir: {paths.config}")

# Cleanup utilities
deleted_count = cleanup_tmp(max_age_hours=24) -> int
size_str = get_dir_size(Dir.LOGS, human_readable=True) -> str  # "1.2 MB"
```

---

## 🌐 API Integration

### API Factory (`utils.api_factory`)

```python
from utils.api_factory import create_rest_api, ApiManager

# Create configured REST API client
api = create_rest_api(config, require_auth=True) -> TxoRestAPI
api_no_auth = create_rest_api(config, require_auth=False) -> TxoRestAPI

# With caching (optional)
api = create_rest_api(config, use_cache=True, cache_key="custom_key")

# Context manager for automatic cleanup
with ApiManager(config) as manager:
    rest_api = manager.get_rest_api(require_auth=True)
    # API automatically cleaned up on exit
```

### REST API Operations (`utils.rest_api_helpers`)

```python
# Created via api_factory - don't instantiate directly!
# api = create_rest_api(config)  # Use this instead

# Standard operations
response = api.get(url, **kwargs) -> Any
response = api.post(url, json=data, **kwargs) -> Any
response = api.put(url, json=data, **kwargs) -> Any
response = api.delete(url, **kwargs) -> Any

# Handles automatically:
# - Rate limiting (if configured)
# - Circuit breaker (if configured)
# - Retries with exponential backoff
# - Token redaction in logs
# - Async operations (202 polling)
```

### OAuth Authentication (`utils.oauth_helpers`)

```python
from utils.oauth_helpers import OAuthClient

# Usually handled by script_runner - use only for custom auth flows
oauth_client = OAuthClient(tenant_id="your-tenant", cache_tokens=True)

token = oauth_client.get_client_credentials_token(
    client_id="your-client-id",
    client_secret="your-secret",
    scope="https://api.businesscentral.dynamics.com/.default",
    tenant_id="your-tenant"
) -> str
```

---

## ⚡ Performance & Reliability

### Rate Limiting & Circuit Breaker (`utils.api_common`)

```python
from utils.api_common import RateLimiter, CircuitBreaker

# Usually created by api_factory - manual usage for custom scenarios
limiter = RateLimiter(calls_per_second=10, burst_size=1.0)
limiter.wait_if_needed()  # Call before each API request

breaker = CircuitBreaker(failure_threshold=5, timeout=60)
if breaker.is_open():
    logger.warning("Circuit breaker is open, skipping request")
    return None

# After successful API call
breaker.record_success()

# After failed API call
breaker.record_failure()
```

### Retry Logic (`utils.api_common`)

```python
from utils.api_common import manual_retry, apply_jitter

# Manual retry for any function
result = manual_retry(
    my_function, arg1, arg2,
    max_retries=3,
    backoff=2.0,
    jitter_config={"min-factor": 0.8, "max-factor": 1.2},
    kwarg1="value"
) -> Any

# Jitter calculation
jittered_delay = apply_jitter(delay=5.0, jitter_config=config) -> float
```

---

## 🛠️ Error Handling

### Custom Exceptions (`utils.exceptions`)

```python
from utils.exceptions import (
    TxoBaseError, HelpfulError, ErrorContext,
    ApiError, ApiAuthenticationError, ApiTimeoutError,
    ConfigurationError, ValidationError, FileOperationError
)

# User-friendly errors with solutions
raise HelpfulError(
    what_went_wrong="Config file missing",
    how_to_fix="Copy from templates/ directory",
    example="cp config/templates/example.json config/txo-prod-config.json"
)

# API-specific errors
raise ApiAuthenticationError("Token expired")
raise ApiTimeoutError("Request timed out", timeout_seconds=30)

# With error context
context = ErrorContext(operation="data_processing", resource="customers.csv")
raise ValidationError("Invalid CSV format", context=context)
```

---

## 📊 Operation Results Tracking

### ProcessingResults Pattern (Business Requirement)

```python
from dataclasses import dataclass, field
from typing import List


@dataclass
class ProcessingResults:
    """Standard pattern for tracking bulk operations - USE THIS!"""
    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    expected_errors: int = 0

    def add_result(self, api_name: str, company_id: str, result: OperationResult):

    # Implementation in your code

    def summary(self) -> str:
        """Generate ✅/❌ user-friendly summary"""
        # Returns: "✅ All 150 operations successful: 75 created, 75 updated"
        # Or: "❌ Completed with 5 failures: 70 created, 75 updated, 5 failed"


# Usage pattern
results = ProcessingResults()
for record in data:
    try:
        if create_customer(record):
            results.created.append(f"CustomerAPI/{company_id}/{record.id}")
        else:
            results.failed.append(f"CustomerAPI/{company_id}/{record.id}: creation failed")
    except Exception as e:
        results.failed.append(f"CustomerAPI/{company_id}/{record.id}: {str(e)}")

logger.info(results.summary())  # Always show final summary
```

---

## 🔄 Import Patterns

### Standard Import Block

```python
# Standard TXO script imports (copy this pattern)
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir
from utils.api_factory import create_rest_api
from utils.exceptions import HelpfulError

# Initialize
logger = setup_logger()
data_handler = TxoDataHandler()
```

---

## ⚠️ What NOT to Do

### ❌ Don't Invent These (They Already Exist!)

```python
# ❌ DON'T CREATE - Use TxoDataHandler.save() instead
def save_json(data, filename): ...
def save_excel(df, filename): ...

# ❌ DON'T CREATE - Use create_rest_api() instead
import requests
session = requests.Session()  # Use create_rest_api(config, require_auth=False)
class CustomAPIClient: ...
class RateLimitedClient: ...

# ❌ DON'T CREATE - Use get_utc_timestamp() instead
utc_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")  # Use TxoDataHandler.get_utc_timestamp()

# ❌ DON'T CREATE - Use Dir constants instead
DIRECTORIES = {"config": "config", "output": "output"}

# ❌ DON'T CREATE - Use setup_logger() instead
def create_logger(): ...
def configure_logging(): ...

# ❌ DON'T ADD - Avoid unnecessary complexity
file_size = output_path.stat().st_size  # Focus on core functionality
start_time = time.time(); elapsed = time.time() - start_time  # Not needed
```

### ❌ Anti-Patterns

```python
# ❌ String literals for directories
data_handler.save(df, "output", "file.xlsx")

# ❌ Direct instantiation of complex objects
api = TxoRestAPI(token, timeout=30)  # Use api_factory instead

# ❌ Print statements
print("Processing complete")  # Use logger.info() instead

# ❌ Soft-fail for configuration
timeout = config.get("timeout", 30)  # Use config["timeout"] instead
```

---

## 🔍 **AI Code Review Checklist**

**Before writing ANY code, check:**

1. **API Calls**: Am I using `create_rest_api()` instead of manual `requests`?
2. **Timestamps**: Am I using `get_utc_timestamp()` instead of manual datetime formatting?
3. **File Operations**: Am I using `TxoDataHandler.save()` instead of manual file I/O?
4. **Directories**: Am I using `Dir.*` constants instead of string literals?
5. **Logging**: Am I using `setup_logger()` instead of print statements?
6. **Complexity**: Am I adding unnecessary timing, file size, or performance metrics?

**Red Flags** (immediately refactor):
- `import requests` → Use `create_rest_api()`
- `datetime.now()` for timestamps → Use `get_utc_timestamp()`
- `'output'` or `'config'` strings → Use `Dir.OUTPUT`, `Dir.CONFIG`
- Performance timing code → Remove unless specifically requested
- Manual session management → Use TXO framework

---

## 🎯 Usage Examples

### Complete Script Pattern

```python
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir
from utils.api_factory import create_rest_api

logger = setup_logger()
data_handler = TxoDataHandler()


def main():
    # 1. Initialize
    config = parse_args_and_load_config("Customer sync script", require_token=True)

    # 2. Load data
    customers = data_handler.load(Dir.DATA, "customers.csv")

    # 3. Create API client
    api = create_rest_api(config)

    # 4. Process with results tracking
    results = ProcessingResults()
    for customer in customers:
        try:
            response = api.post("/customers", json=customer.to_dict())
            results.created.append(f"CustomerAPI/{config['_org_id']}/{customer.id}")
        except Exception as e:
            results.failed.append(f"CustomerAPI/{config['_org_id']}/{customer.id}: {e}")

    # 5. Save results and summary
    data_handler.save_with_timestamp(results, Dir.OUTPUT, f"sync-results-{config['_org_id']}.json", add_timestamp=True)
    logger.info(results.summary())


if __name__ == "__main__":
    main()
```

---

## 🔗 Integration with ADRs

This reference implements:

- **Business ADRs**: Hard-fail config, logging context, ProcessingResults, directory structure
- **Technical Standards**: Thread safety, lazy loading, exception hierarchy, type safety

**Token Usage Strategy:**

```
Your Prompt + Business ADRs + Technical Standards + This Quick Reference
→ AI generates code using EXISTING functions
→ Consistent patterns, fewer tokens, working code
```

---

## Version History

### v3.1 (Current)

- Organized by use case to prevent AI hallucination
- Added anti-patterns and complete script examples
- Added UTC timestamp utilities (get_utc_timestamp, save_with_timestamp)

### v1.0

- Initial comprehensive function reference
- Established DO NOT INVENT approach

---

**Version:** v3.1  
**Last Updated:** 2025-01-25  
**Domain:** TXO Utils Reference  
**Purpose:** Prevent AI hallucination by showing existing functions