# TXO Python Template v3.0 - In-Depth Guide

## Overview

The TXO Python Template v3.0 is a production-ready framework that enforces consistent patterns across all Python scripts. It includes enterprise-grade features like automatic token redaction, rate limiting, circuit breakers, mandatory configuration, and type-safe path management.

**Version**: 3.0.0  
**Python**: 3.10+ required, 3.13+ recommended  
**Philosophy**: Hard-fail on configuration, fail-fast on errors, type-safe operations, clear guidance for users

## Table of Contents
1. [Core v3.0 Patterns](#core-v30-patterns)
2. [Security Enhancements](#security-enhancements)
3. [API Resilience Features](#api-resilience-features)
4. [Error Handling System](#error-handling-system)
5. [Performance Optimizations](#performance-optimizations)
6. [Configuration Management](#configuration-management)
7. [Helper Modules Reference](#helper-modules-reference)
8. [Script Development Guide](#script-development-guide)
9. [Best Practices](#best-practices)
10. [Common Pitfalls](#common-pitfalls)
11. [Troubleshooting](#troubleshooting)
12. [Migration from v2.x](#migration-from-v2x)

## Core v3.0 Patterns

### 1. Type-Safe Directory Constants (NEW)

**v3.0 Revolution**: Never use string literals for directories!

```python
from utils.path_helpers import Dir

# ✅ CORRECT - Type-safe, IDE autocomplete, no typos
config = data_handler.load_json(Dir.CONFIG, 'settings.json')
data_handler.save(results, Dir.OUTPUT, 'report.xlsx')
path = get_path(Dir.LOGS, 'app.log')

# ❌ WRONG - String literals are error-prone
config = data_handler.load_json('config', 'settings.json')  # NO!
```

Available Dir constants:
- `Dir.CONFIG` - Configuration files
- `Dir.DATA` - Input data files
- `Dir.OUTPUT` - Generated output
- `Dir.LOGS` - Log files
- `Dir.FILES` - External files used as-is
- `Dir.GENERATED_PAYLOADS` - Payloads for validation
- `Dir.PAYLOADS` - Ready-to-send payloads
- `Dir.SCHEMAS` - JSON schemas
- `Dir.TMP` - Temporary files
- `Dir.WSDL` - WSDL files
- `Dir.AI` - AI-related files

### 2. Token Optional by Default (CHANGED)

**v3.0 Change**: Most scripts don't need authentication!

```python
# DEFAULT - No token needed for local processing
config = parse_args_and_load_config("Process local data")
# require_token=False is the default

# EXPLICIT - Only for API scripts
config = parse_args_and_load_config(
    "Sync with Business Central",
    require_token=True  # Must be explicit for API access
)
```

### 3. Universal Smart Save (ENHANCED)

One method for all file types with automatic detection:

```python
from utils.load_n_save import TxoDataHandler
data_handler = TxoDataHandler()

# Auto-detects from data type + extension
data_handler.save(dict_data, Dir.OUTPUT, "data.json")    # JSON with DecimalEncoder
data_handler.save(dataframe, Dir.OUTPUT, "report.xlsx")  # Excel
data_handler.save(dataframe, Dir.OUTPUT, "report.csv")   # CSV
data_handler.save("text", Dir.OUTPUT, "readme.txt")      # Plain text
data_handler.save(config, Dir.CONFIG, "settings.yaml")   # YAML

# Load also auto-detects
df = data_handler.load(Dir.DATA, "input.csv")  # Returns DataFrame
config = data_handler.load(Dir.CONFIG, "settings.yaml")  # Returns dict
```

### 4. Mandatory Configuration Pattern

**No defaults allowed** - Configuration must exist:

```python
# Script WILL exit(1) if ANY required file is missing:
# 1. {org}-{env}-config.json
# 2. logging-config.json
# 3. log-redaction-patterns.json

logger = setup_logger()  # Exits if logging configs missing
config = parse_args_and_load_config("Script")  # Exits if main config missing

# Hard-fail on missing keys (v3.0 philosophy)
api_url = config['global']['api-base-url']  # KeyError = good!
tenant = config['global']['tenant-id']      # Immediate failure if missing

# Soft-fail ONLY for API response data
email = api_response.get('email')  # None if missing is OK for external data
```

### 5. Nested Configuration Structure

Configuration now uses logical nesting:

```json
{
  "script-behavior": {
    "rate-limiting": {
      "enabled": true,
      "calls-per-second": 10,
      "burst-size": 1
    },
    "circuit-breaker": {
      "enabled": false,
      "failure-threshold": 5,
      "timeout-seconds": 60
    }
  }
}
```

### 6. Enhanced Logging with Token Redaction

Logger automatically redacts sensitive patterns including underscore prefixes:

```python
# Automatically redacted patterns:
logger.info(f"Token: {config['_token']}")  
# Logs: "Token: Bearer [REDACTED]"

logger.debug(f"Config: {json.dumps({'_password': 'secret'})}")  
# Logs: "Config: {"_password": "[REDACTED]"}"

# Supports TXO metadata convention
logger.info(f"Secret: {config['_client_secret']}")
# Logs: "Secret: [REDACTED]"
```

Redaction includes:
- Bearer tokens
- JWT tokens (eyJ...)
- Passwords (including `_password`)
- API keys (including `_api_key`)
- Client secrets (including `_client_secret`)
- Tokens (including `_token`)
- Long random strings (40+ chars)

### 7. Standard Script Pattern

Every script follows this structure:

```python
# examples/my_script.py  ← Path comment ALWAYS first
"""
Script description and purpose.

Usage:
    python my_script.py <org_id> <env_type>
"""

from typing import Dict, Any
from datetime import datetime, timezone

from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir  # ← ALWAYS import Dir
from utils.exceptions import HelpfulError

logger = setup_logger()
data_handler = TxoDataHandler()

def main():
    config = parse_args_and_load_config(
        "Script description",
        require_token=False  # Default for most scripts
    )
    
    org_id = config['_org_id']
    env_type = config['_env_type']
    logger.info(f"Starting for {org_id}-{env_type}")
    
    # Your logic here
    
if __name__ == "__main__":
    main()
```

## Security Enhancements

### Enhanced Token Redaction

The `TokenRedactionFilter` now handles underscore-prefixed metadata:

```python
# Patterns that are automatically redacted:
- "Bearer [token]" → "Bearer [REDACTED]"
- "_token": "value" → "_token": "[REDACTED]"
- "_password": "value" → "_password": "[REDACTED]"  
- "_api_key": "value" → "_api_key": "[REDACTED]"
- "_client_secret": "value" → "_client_secret": "[REDACTED]"
```

### Structured Error Context

New `ErrorContext` dataclass provides debugging information without exposing sensitive data:

```python
from utils.exceptions import ErrorContext, ApiError

context = ErrorContext(
    operation="fetch_customers",
    resource="/api/v2/customers",
    details={"page": 1, "size": 100}
)

raise ApiError("Failed to fetch data", context=context)
# Error message includes context without sensitive data
```

### Session Management with Limits

Connection pooling now has strict limits to prevent resource exhaustion:

```python
# SessionManager in rest_api_helpers.py
- Maximum 50 sessions cached (LRU eviction)
- Thread-safe with proper locking
- Automatic cleanup on eviction
- Per-thread session storage for performance
```

## API Resilience Features

### Integrated Rate Limiting

Rate limiting is now built into the API client:

```python
# Configuration
{
  "script-behavior": {
    "rate-limiting": {
      "enabled": true,
      "calls-per-second": 10,
      "burst-size": 1
    }
  }
}

# Automatic usage
api = create_rest_api(config)  # Rate limiter created if enabled
response = api.get(url)  # Automatically throttled
```

The `RateLimiter` class uses token bucket algorithm:
- Smooth rate limiting (not bursty)
- Configurable calls per second
- Thread-safe implementation

### Circuit Breaker Pattern

Prevent cascade failures with automatic circuit breaking:

```python
# Configuration
{
  "script-behavior": {
    "circuit-breaker": {
      "enabled": true,
      "failure-threshold": 5,
      "timeout-seconds": 60
    }
  }
}

# Behavior
1. After 5 consecutive failures → circuit opens
2. All requests fail fast for 60 seconds
3. After timeout → circuit attempts reset
4. One success → circuit closes fully
```

### Async Operations (202 Accepted)

Handle long-running operations transparently:

```python
# Automatic handling of 202 responses
result = api.post("/long-operation", data)

# Behind the scenes:
# 1. Receives 202 Accepted with Location header
# 2. Polls Location URL respecting Retry-After
# 3. Applies jitter to polling interval
# 4. Returns final result when ready
# 5. Times out after configurable max-wait
```

Configuration:
```json
"api-timeouts": {
  "async-max-wait": 300,      # Max 5 minutes
  "async-poll-interval": 5    # Default poll every 5s
}
```

### Enhanced Connection Pooling

The `SessionManager` class provides:
- Thread-local session storage for performance
- Shared cache with LRU eviction
- Maximum 50 sessions to prevent memory issues
- Automatic cleanup on exit
- Move-to-end for true LRU behavior

## Error Handling System

### Exception Hierarchy

```
TxoBaseError
├── ErrorContext (dataclass for context)
├── ApiError
│   ├── ApiTimeoutError
│   ├── ApiRateLimitError (includes retry_after)
│   ├── ApiAuthenticationError
│   ├── ApiNotFoundError
│   └── ApiValidationError
├── ConfigurationError (includes config_key)
├── ValidationError (includes field, value)
├── FileOperationError (includes file_path, operation)
└── HelpfulError (user-friendly with solutions)
```

### HelpfulError Pattern

Provide actionable solutions to users:

```python
from utils.exceptions import HelpfulError

raise HelpfulError(
    what_went_wrong="Configuration file not found",
    how_to_fix="Copy the template from config/templates/",
    example="cp config/templates/example.json config/myorg-prod-config.json"
)
```

Output:
```
❌ Problem: Configuration file not found

✅ Solution: Copy the template from config/templates/

📝 Example:
cp config/templates/example.json config/myorg-prod-config.json
```

### Context-Aware Errors

All exceptions can include structured context:

```python
from utils.exceptions import ErrorContext, ApiOperationError

context = ErrorContext(
    operation="update_customer",
    resource="Customer-12345",
    details={"field": "email", "value": "invalid"}
)

raise ApiValidationError(
    "Email validation failed",
    field="email",
    value="invalid",
    context=context
)
```

## Performance Optimizations

### Thread-Safe Lazy Loading

Heavy dependencies are loaded only when needed:

```python
# In load_n_save.py
def _ensure_pandas(self):
    """Lazy load pandas only when needed."""
    if self._pd is None:
        with self._import_lock:
            if self._pd is None:  # Double-check pattern
                import pandas as pd
                self._pd = pd
    return self._pd

# Similar for yaml, openpyxl, etc.
```

### Efficient Session Reuse

Sessions are reused across requests:

```python
# Thread-local storage for performance
_thread_local = threading.local()

def get_session(self, key: str) -> requests.Session:
    # Check thread-local first (fast)
    if not hasattr(_thread_local, 'sessions'):
        _thread_local.sessions = {}
    
    if key in _thread_local.sessions:
        return _thread_local.sessions[key]
    
    # Fall back to shared cache (with lock)
    with self._lock:
        # LRU cache with eviction
        ...
```

### Jitter for Thundering Herd Prevention

All retries include jitter to prevent synchronized retries:

```python
def apply_jitter(delay: float, config: Dict[str, Any]) -> float:
    """Apply jitter to prevent thundering herd."""
    min_factor = config.get("min-factor", 0.8)
    max_factor = config.get("max-factor", 1.2)
    return delay * random.uniform(min_factor, max_factor)
```

## Configuration Management

### Required Configuration Files

#### 1. Main Config: `config/{org}-{env}-config.json`

Must include nested structure:

```json
{
  "global": {
    "api-base-url": "https://api.example.com",
    "api-version": "v2",
    "tenant-id": "",     # Can be empty for non-API scripts
    "client-id": "",     # Can be empty for non-API scripts
    "oauth-scope": ""    # Can be empty for non-API scripts
  },
  "script-behavior": {
    "api-delay-seconds": 1,
    "api-timeouts": {
      "rest-timeout-seconds": 60,
      "async-max-wait": 300,
      "async-poll-interval": 5
    },
    "retry-strategy": {
      "max-retries": 5,
      "backoff-factor": 3.0
    },
    "jitter": {
      "min-factor": 0.8,
      "max-factor": 1.2
    },
    "rate-limiting": {
      "enabled": false,
      "calls-per-second": 10,
      "burst-size": 1
    },
    "circuit-breaker": {
      "enabled": false,
      "failure-threshold": 5,
      "timeout-seconds": 60
    },
    "batch-handling": {
      "read-batch-size": 20,
      "update-batch-size": 10
    }
  }
}
```

#### 2. Logging Config: `config/logging-config.json`

MANDATORY - Script exits if missing:

```json
{
  "version": 1,
  "formatters": {
    "standard": {
      "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "level": "INFO",
      "formatter": "standard"
    },
    "file": {
      "class": "logging.FileHandler",
      "level": "DEBUG",
      "formatter": "standard",
      "filename": "logs/app.log"
    }
  },
  "loggers": {
    "TxoApp": {
      "level": "DEBUG",
      "handlers": ["console", "file"]
    }
  }
}
```

#### 3. Redaction Patterns: `config/log-redaction-patterns.json`

MANDATORY for security:

```json
{
  "_comment": "Keys prefixed with _ are documentation for humans",
  "redaction-patterns": {
    "patterns": [
      {
        "name": "bearer-token",
        "pattern": "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*",
        "replacement": "Bearer [REDACTED]"
      },
      {
        "name": "token-json",
        "pattern": "\"_?token\":\\s*\"[^\"]*\"",
        "replacement": "\"token\": \"[REDACTED]\""
      }
    ]
  },
  "_usage-notes": {
    "metadata-prefix": "Leading underscores are TXO convention for metadata",
    "pattern-flexibility": "Patterns handle both - and _ separators"
  }
}
```

### Schema Validation

All configurations are validated against JSON schema:

```json
// schemas/org-env-config-schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["global", "script-behavior"],
  "properties": {
    "global": {
      "type": "object",
      "required": ["api-base-url"],
      ...
    }
  }
}
```

## Helper Modules Reference

### Core Modules

#### utils.path_helpers
```python
from utils.path_helpers import Dir, get_path

# Type-safe directory constants
Dir.CONFIG, Dir.OUTPUT, Dir.LOGS, etc.

# Get full path
path = get_path(Dir.CONFIG, "settings.json")
# Returns: Path object to config/settings.json
```

#### utils.script_runner
```python
# Standard initialization (token optional)
config = parse_args_and_load_config(
    "Script description",
    require_token=False    # Default - most scripts don't need auth
)

# For API scripts
config = parse_args_and_load_config(
    "API sync script",
    require_token=True     # Explicit for API access
)

# With custom arguments
from utils.script_runner import ArgumentDefinition

extra_args = [
    ArgumentDefinition("batch_size", int, "Batch size", default=100),
    ArgumentDefinition("dry_run", bool, "Dry run mode", action="store_true")
]
config = parse_custom_args_and_load_config("Script", extra_args)
```

#### utils.logger
```python
from utils.logger import setup_logger

logger = setup_logger()  # Will exit if configs missing

# Thread-safe singleton with automatic redaction
logger.debug("Details")      # File only
logger.info("Progress")      # Console + file
logger.warning("Warning")    # Console + file
logger.error("Error", exc_info=True)  # With traceback
```

#### utils.load_n_save
```python
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir

data_handler = TxoDataHandler()

# Universal save (auto-detects type)
data_handler.save(data, Dir.OUTPUT, "file.json")   # Any data type
data_handler.save(df, Dir.OUTPUT, "file.xlsx")     # DataFrame
data_handler.save("text", Dir.OUTPUT, "file.txt")  # String

# Universal load (auto-detects format)
data = data_handler.load(Dir.DATA, "file.csv")     # Returns DataFrame
config = data_handler.load(Dir.CONFIG, "file.json") # Returns dict

# File operations
exists = data_handler.exists(Dir.CONFIG, "file.json")
data_handler.delete(Dir.TMP, "temp.json")
size = data_handler.get_size(Dir.OUTPUT, "report.xlsx")
```

#### utils.api_factory
```python
from utils.api_factory import create_rest_api, ApiManager

# Create API with all features
api = create_rest_api(config)  # Rate limiting, circuit breaker included

# With context manager for automatic cleanup
with ApiManager(config) as manager:
    api = manager.get_rest_api()
    # Sessions closed automatically on exit
```

#### utils.exceptions
```python
from utils.exceptions import (
    HelpfulError, 
    ErrorContext,
    ApiRateLimitError,
    ApiTimeoutError
)

# User-friendly errors
raise HelpfulError(
    what_went_wrong="Database connection failed",
    how_to_fix="Check your connection string",
    example="postgres://user:pass@localhost/db"
)

# Context-aware API errors
context = ErrorContext(
    operation="fetch_data",
    resource="/api/customers"
)
raise ApiTimeoutError("Request timed out", context=context)
```

### API Modules

#### utils.rest_api_helpers
```python
from utils.rest_api_helpers import MinimalRestAPI

# Enhanced REST client with all features
api = MinimalRestAPI(
    token=token,
    rate_limiter=rate_limiter,      # Optional
    circuit_breaker=circuit_breaker  # Optional
)

# Automatic pagination
entities = api.get_odata_entities(
    base_url=url,
    entity_name="Customers",
    odata_filter="Country eq 'USA'",
    select_fields=["Name", "Email"],
    page_size=100
)

# Handle async operations
result = api.post("/long-operation", data)  # Handles 202 automatically
```

#### utils.api_common
```python
from utils.api_common import RateLimiter, CircuitBreaker

# Rate limiting
limiter = RateLimiter(calls_per_second=10)
limiter.wait_if_needed()  # Blocks if rate exceeded

# Circuit breaker
breaker = CircuitBreaker(failure_threshold=5, timeout=60)
if breaker.is_open():
    raise ApiOperationError("Circuit breaker open")
```

## Script Development Guide

### Template for Local Processing Script

```python
# examples/process_data.py
"""Process local data files - no authentication needed."""

from typing import Dict, Any
from datetime import datetime, timezone

from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir
from utils.exceptions import HelpfulError

logger = setup_logger()
data_handler = TxoDataHandler()

def process_data(config: Dict[str, Any]) -> None:
    """Main processing logic."""
    # Load input
    df = data_handler.load(Dir.DATA, "input.csv")
    
    # Process
    df['processed'] = True
    
    # Save with TXO naming
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    filename = f"{config['_org_id']}-{config['_env_type']}-results_{utc}.xlsx"
    
    output_path = data_handler.save(df, Dir.OUTPUT, filename)
    logger.info(f"✅ Saved to: {output_path}")

def main():
    # No token needed (default)
    config = parse_args_and_load_config("Process local data")
    
    try:
        process_data(config)
    except Exception as e:
        raise HelpfulError(
            what_went_wrong=f"Processing failed: {e}",
            how_to_fix="Check input file format",
            example="Ensure CSV has required columns"
        )

if __name__ == "__main__":
    main()
```

### Template for API Integration Script

```python
# examples/api_sync.py
"""Sync with external API - requires authentication."""

from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.api_factory import create_rest_api
from utils.path_helpers import Dir
from utils.exceptions import HelpfulError, ApiOperationError

logger = setup_logger()

def sync_data(config: Dict[str, Any]) -> None:
    """Sync data with API."""
    api = create_rest_api(config)
    
    try:
        # Fetch from API
        endpoint = f"{config['global']['api-base-url']}/data"
        data = api.get(endpoint)
        
        # Save locally
        data_handler.save(data, Dir.OUTPUT, "api-data.json")
        
    except ApiOperationError as e:
        raise HelpfulError(
            what_went_wrong=f"API sync failed: {e}",
            how_to_fix="Check API endpoint and authentication",
            example="Verify token is valid and endpoint exists"
        )

def main():
    # Explicitly require token for API
    config = parse_args_and_load_config(
        "API sync script",
        require_token=True  # Required for API access
    )
    
    sync_data(config)

if __name__ == "__main__":
    main()
```

## Best Practices

### ✅ DO
1. **Always use Dir constants** - Never use string literals for directories
2. **Use save() for everything** - It auto-detects the type
3. **Let config fail hard** - No .get() for required configuration
4. **Include UTC timestamps** - In all output filenames
5. **Use HelpfulError** - For user-facing error messages
6. **Set require_token=True** - ONLY for scripts that need API access
7. **Use context managers** - For resource cleanup
8. **Log at appropriate levels** - DEBUG for details, INFO for progress

### ❌ DON'T
1. **Use string paths** - Like 'config' or 'output'
2. **Require tokens unnecessarily** - Most scripts don't need auth
3. **Use soft defaults** - For required configuration
4. **Use print()** - Always use logger
5. **Build paths manually** - Use get_path() with Dir constants
6. **Ignore exceptions** - Handle them with HelpfulError
7. **Mix save methods** - Just use save() for everything
8. **Skip UTC timestamps** - Always include them in output files

## Common Pitfalls

### Using String Literals Instead of Dir Constants
```python
# ❌ WRONG
data = data_handler.load_json('config', 'settings.json')

# ✅ CORRECT
data = data_handler.load_json(Dir.CONFIG, 'settings.json')
```

### Requiring Token When Not Needed
```python
# ❌ WRONG - Local processing doesn't need token
config = parse_args_and_load_config("Process CSV", require_token=True)

# ✅ CORRECT - Token optional by default
config = parse_args_and_load_config("Process CSV")
```

### Using Soft-Fail on Required Config
```python
# ❌ WRONG - Hides configuration errors
url = config.get('global', {}).get('api-url', 'default')

# ✅ CORRECT - Fails immediately if missing
url = config['global']['api-url']
```

### Using Multiple Save Methods
```python
# ❌ WRONG - Old pattern, verbose
data_handler.save_json(data, Dir.OUTPUT, "data.json")
data_handler.save_excel(df, Dir.OUTPUT, "report.xlsx")

# ✅ CORRECT - Universal save
data_handler.save(data, Dir.OUTPUT, "data.json")
data_handler.save(df, Dir.OUTPUT, "report.xlsx")
```

## Troubleshooting

### Invalid Directory Error
```
ValueError: Invalid directory 'config'. Use Dir.* constants
```
**Fix**: Import and use `Dir.CONFIG` instead of string 'config'

### Config File Not Found
```
CRITICAL CONFIGURATION ERROR
Configuration file not found!
```
**Fix**: Copy templates from `config/templates/`

### Token Required But Not Configured
```
❌ Problem: Token required but OAuth config incomplete
✅ Solution: Either configure OAuth or use require_token=False
```
**Fix**: Only set `require_token=True` for API scripts

### Circuit Breaker Open
```
ApiOperationError: Circuit breaker open for operation
```
**Fix**: Wait for timeout period or fix underlying API issue

### Rate Limit Exceeded
```
ApiRateLimitError: Rate limit exceeded
```
**Fix**: Enable rate limiting in configuration

## Migration from v2.x

### Breaking Changes

1. **Dir Constants Required**
   ```python
   # v2.x
   data_handler.load_json('config', 'file.json')
   
   # v3.0
   from utils.path_helpers import Dir
   data_handler.load_json(Dir.CONFIG, 'file.json')
   ```

2. **Token Optional by Default**
   ```python
   # v2.x - Token required by default
   config = parse_args_and_load_config("Script")
   
   # v3.0 - Token optional by default
   config = parse_args_and_load_config("Script")  # No token
   config = parse_args_and_load_config("Script", require_token=True)  # With token
   ```

3. **Nested Configuration**
   ```json
   // v2.x - Flat
   "enable-rate-limiting": true,
   "rate-limit-per-second": 10
   
   // v3.0 - Nested
   "rate-limiting": {
     "enabled": true,
     "calls-per-second": 10,
     "burst-size": 1
   }
   ```

4. **Universal Save Method**
   ```python
   # v2.x - Different methods
   data_handler.save_json(data, 'output', 'file.json')
   data_handler.save_excel(df, 'output', 'file.xlsx')
   
   # v3.0 - One method
   data_handler.save(data, Dir.OUTPUT, 'file.json')
   data_handler.save(df, Dir.OUTPUT, 'file.xlsx')
   ```

5. **Mandatory Config Files**
   - Must have `logging-config.json`
   - Must have `log-redaction-patterns.json`
   - No defaults - script exits if missing

### Migration Checklist
- [ ] Replace all string directory literals with Dir constants
- [ ] Update config to nested structure
- [ ] Remove `require_token=True` unless script needs API
- [ ] Replace all save_* methods with save()
- [ ] Ensure all 3 config files exist
- [ ] Move scripts to examples/ or tests/
- [ ] Update imports to include Dir

## Version History

### v3.0.0 (Current)
- Type-safe Dir constants replace string literals
- Token optional by default (was required)
- Universal save() method with auto-detection
- Mandatory configuration files (no defaults)
- Enhanced redaction for underscore-prefixed metadata
- SessionManager with connection pool limits
- Integrated RateLimiter and CircuitBreaker
- Thread-safe lazy loading

### v2.1.0
- Nested configuration structure
- Hard-fail philosophy
- TxoRestAPI class naming
- Basic smart save

### v2.0.0
- Token redaction
- Rate limiting support
- Circuit breaker pattern
- Async operation support

## Additional Resources

- **Architecture Decisions**: See [ADR Records](ai/decided/adr_v3.md)
- **Module Dependencies**: See [Module Dependency Diagram](module-dependency-diagram.md)
- **AI Assistance**: Upload `ai/prompts/txo-xml-prompt-v3.0.xml` to Claude/GPT-4
- **GitHub Issues**: Report bugs and request features

## Support

- Template Version: v3.0.0
- Python Required: 3.10+ (3.13+ recommended)
- License: MIT