# TXO Python Template In-Depth Guide v3.1

> **Audience**: Developers who want to understand the architecture and customize the framework
> **Time Investment**: 30 minutes to full understanding

## Table of Contents

1. [Architecture Philosophy](#architecture-philosophy)
2. [Complete Setup Guide](#complete-setup-guide)
3. [Advanced Configuration](#advanced-configuration)
4. [API Integration Patterns](#api-integration-patterns)
5. [Performance & Reliability](#performance--reliability)
6. [Security Implementation](#security-implementation)
7. [Testing and Validation](#testing-and-validation)
8. [Customization Guide](#customization-guide)
9. [Migration from Previous Versions](#migration-from-previous-versions)
10. [Troubleshooting Deep Dive](#troubleshooting-deep-dive)

---

## Architecture Philosophy

### The TXO Way: Fail Fast, Consistent, Secure

**Hard-Fail Philosophy**:

```python
# ✅ TXO Way - Fail immediately on misconfiguration
api_url = config['global']['api-base-url']  # KeyError if missing

# ❌ Traditional - Silent failure with defaults
api_url = config.get('global', {}).get('api-base-url', 'https://default.com')
```

**Why Hard-Fail?**

- Production errors surface during development
- No hidden configuration dependencies
- Clear, actionable error messages

### Layered Architecture (Dependencies Flow Downward)

```
User Scripts (src/, tests/)
    ↓
Orchestration (script_runner, api_factory, config_loader)
    ↓
API Layer (rest_api_helpers, oauth_helpers)
    ↓
Core Services (logger, api_common)
    ↓
Foundation (path_helpers, exceptions)
```

**Dependency Rules**:

- Higher layers can import lower layers
- Lower layers NEVER import higher layers
- Foundation layer has zero dependencies

---

## Complete Setup Guide

### Project Initialization Checklist

#### 1. Environment Setup

```bash
# Install dependencies
pip install uv
uv pip install -r pyproject.toml

# Verify Python version
python --version  # Requires 3.8+
```

#### 2. Configuration Files (Mandatory)

```bash
# Copy all required templates
cp config/org-env-config_example.json config/myorg-prod-config.json
cp config/org-env-config-secrets_example.json config/myorg-prod-config-secrets.json
cp config/logging-config.json config/logging-config.json  # Already in place
cp config/log-redaction-patterns.json config/log-redaction-patterns.json  # Already in place
```

#### 3. Directory Structure Validation

```python
from utils.path_helpers import ProjectPaths

# Validate and create missing directories
paths = ProjectPaths.init()
created = paths.ensure_dirs()
print(f"Created directories: {created}")

# Check structure
existing, missing = paths.validate_structure()
print(f"Missing: {missing}")  # Should be empty
```

#### 4. Configuration Validation

```python
from utils.config_loader import ConfigLoader

# Test configuration loading
loader = ConfigLoader("myorg", "prod")
config = loader.load_config(validate=True)
print("✅ Configuration valid")
```

---

## Advanced Configuration

### Nested Configuration Structure (v3.0+)

```json
{
  "global": {
    "api-base-url": "https://api.businesscentral.dynamics.com",
    "tenant-id": "your-tenant-id",
    "timeout-seconds": 30
  },
  "script-behavior": {
    "rate-limiting": {
      "enabled": true,
      "calls-per-second": 10,
      "burst-size": 1
    },
    "circuit-breaker": {
      "enabled": true,
      "failure-threshold": 5,
      "timeout-seconds": 60
    },
    "retry-strategy": {
      "max-retries": 3,
      "backoff-factor": 2.0,
      "max-backoff": 30
    },
    "jitter": {
      "enabled": true,
      "min-factor": 0.8,
      "max-factor": 1.2
    }
  }
}
```

### Secrets Management Deep Dive

```xml

<secrets-structure>
    <location>config/{org}-{env}-config-secrets.json</location>
    <git-status>ALWAYS GITIGNORED</git-status>
    <format>flat-json-only</format>
    <naming-convention>kebab-case</naming-convention>
</secrets-structure>
```

```json lines
// config/myorg-prod-config-secrets.json (GITIGNORED)
{
  "client-secret": "actual-secret-here",
  "database-password": "actual-password",
  "api-key": "actual-key"
}
```

**Secret Injection Pattern**:

```python
# Secrets automatically injected with underscore prefix
client_secret = config['_client-secret']  # kebab-case preserved
db_password = config['_database-password']

# Visual distinction: kebab-case = JSON origin, snake_case = Python variable
api_token = config['_api-key']  # From JSON
retry_count = 3  # Python variable
```

---

## API Integration Patterns

### REST API with Full Resilience

```xml

<api-pattern>
    <resilience-features>rate-limiting,circuit-breaker,retries,async-handling</resilience-features>
    <authentication>oauth-client-credentials</authentication>
    <error-handling>structured-exceptions</error-handling>
</api-pattern>
```

```python
from utils.api_factory import create_rest_api
from utils.exceptions import ApiRateLimitError, ApiTimeoutError


def sync_customers():
    config = parse_args_and_load_config("Customer sync", require_token=True)

    # API client with rate limiting, circuit breaker, retries
    api = create_rest_api(config)

    # All resilience patterns applied automatically
    customers = api.get("/customers")  # Rate limited

    results = ProcessingResults()
    for customer in customers:
        try:
            result = api.post("/customers", json=customer)  # Circuit breaker protection
            results.created.append(f"CustomerAPI/{config['_org_id']}/{customer.id}")
        except ApiRateLimitError as e:
            logger.warning(f"Rate limited: retry after {e.retry_after}s")
            time.sleep(e.retry_after)
            continue
        except ApiTimeoutError as e:
            results.failed.append(f"CustomerAPI/{config['_org_id']}/{customer.id}: timeout")

    logger.info(results.summary())  # ✅/❌ user-friendly output
```

### Async Operation Handling (202 Accepted)

```python
# TxoRestAPI automatically handles async operations
result = api.post("/bulk-import", json=large_dataset)
# Automatically polls until completion or timeout
# Returns final result, not 202 response
```

---

## Performance & Reliability

### Thread-Safe Lazy Loading

```xml

<performance-pattern>
    <technique>double-checked-locking</technique>
    <modules>pandas,yaml,openpyxl</modules>
    <benefit>fast-startup</benefit>
</performance-pattern>
```

```python
# Heavy modules loaded only when needed
class TxoDataHandler:
    _modules: Dict[str, Any] = {}
    _import_lock = threading.Lock()

    @classmethod
    def _lazy_import(cls, module_name: str) -> Any:
        if module_name not in cls._modules:
            with cls._import_lock:
                # Double-check pattern for thread safety
                if module_name not in cls._modules:
                    logger.debug(f"Lazy loading {module_name}")
                    import pandas  # Only when actually needed
                    cls._modules['pandas'] = pandas
        return cls._modules[module_name]
```

### Memory Optimization with __slots__

```python
# 40% memory reduction for frequent objects
@dataclass
class ProcessingResults:
    __slots__ = ['created', 'updated', 'failed', 'expected_errors']


class CircuitBreaker:
    __slots__ = ['failure_threshold', 'timeout', '_failures', '_last_failure', '_state']
```

### Connection Pooling Strategy

```python
# Session management with LRU cache
class SessionManager:
    _max_cache_size = 50  # Prevents memory leaks
    _session_cache: WeakValueDictionary = WeakValueDictionary()
    # Thread-local + shared cache strategy
```

---

## Security Implementation

### Mandatory Token Redaction

```xml

<security-config>
    <file>config/log-redaction-patterns.json</file>
    <status>MANDATORY</status>
    <exit-behavior>sys.exit(1) if missing</exit-behavior>
</security-config>
```

```json
{
  "redaction-patterns": {
    "patterns": [
      {
        "name": "bearer-token",
        "pattern": "Bearer\\s+[A-Za-z0-9\\-._~+/]+=*",
        "replacement": "Bearer [REDACTED]"
      },
      {
        "name": "client-secret",
        "pattern": "client[_-]?secret[\"']?\\s*[:=]\\s*[\"']?([^\"'\\s,}]+)",
        "replacement": "client-secret\": \"[REDACTED]\""
      }
    ]
  }
}
```

### Context-Aware Logging Pattern

```python
# Hierarchical context for traceability
# Format: [Environment/Organization/Operation]
context = f"[{config['_env_type'].title()}/{company_name}/{api_name}]"

logger.info(f"{context} Processing {len(customers)} customers")
logger.debug(f"{context} API request: {payload}")  # Tokens auto-redacted
logger.error(f"{context} Failed to sync customer {customer_id}: {error}")

# Example outputs:
# [Prod/CompanyOne/BusinessCentral] Processing 150 customers
# [Test/TXO/CustomerAPI] API request: {"client-secret": "[REDACTED]"}
```

---

## Testing and Validation

### Unit Testing Individual Layers

```xml

<testing-strategy>
    <approach>layer-by-layer</approach>
    <foundation>no-dependencies</foundation>
    <integration>full-stack</integration>
</testing-strategy>
```

```python
# Test foundation layer (no dependencies required)
def test_path_helpers():
    from utils.path_helpers import Dir, get_path
    path = get_path(Dir.CONFIG, 'test.json')
    assert path.name == 'test.json'
    assert Dir.validate('config') == True
    assert Dir.validate('invalid') == False


# Test core services layer
def test_logger_setup():
    from utils.logger import setup_logger
    logger = setup_logger()  # Will exit if config missing
    logger.info("Test message with _secret_token")  # Should be redacted


# Test with dependencies
def test_data_handler_lazy_loading():
    from utils.load_n_save import TxoDataHandler
    handler = TxoDataHandler()

    # Verify lazy loading
    assert 'pandas' not in handler._modules
    df = handler.load_csv(Dir.DATA, 'test.csv')
    assert 'pandas' in handler._modules  # Now loaded
```

### Integration Testing

```bash
# Full script test with demo configuration
python src/try_me_script.py demo test

# Validate configuration structure
python -c "
from utils.config_loader import ConfigLoader
loader = ConfigLoader('demo', 'test')
config = loader.load_config(validate=True)
print('✅ Configuration schema valid')
print(f'Injected fields: {[k for k in config.keys() if k.startswith(\"_\")]}')
"

# Test all utilities
python tests/test_features.py demo test
```

---

## Customization Guide

### Adding New Directory Types

```python
# 1. Update CategoryType literal in path_helpers.py
CategoryType = Literal[
    'config', 'data', 'output', 'logs', 'reports',  # Add 'reports'
]


# 2. Add to Dir class
class Dir:
    CONFIG: CategoryType = 'config'
    REPORTS: CategoryType = 'reports'  # Add this


# 3. Update ProjectPaths dataclass
@dataclass(frozen=True)
class ProjectPaths:
    __slots__ = ['root', 'config', 'data', 'reports']  # Add reports
    root: Path
    config: Path
    data: Path
    reports: Path  # Add this field

    @classmethod
    def init(cls, root_path: Optional[Path] = None) -> 'ProjectPaths':
        # Add reports directory initialization
        return cls(
            root=root_path,
            config=root_path / "config",
            data=root_path / "data",
            reports=root_path / "reports",  # Add this
        )
```

### Custom Exception Types

```python
# Add to exceptions.py
class BusinessLogicError(TxoBaseError):
    """Raised when business rules are violated."""

    def __init__(self, rule: str, value: Any, context: Optional[ErrorContext] = None):
        message = f"Business rule violated: {rule} (value: {value})"
        super().__init__(message, context)
        self.rule = rule
        self.value = value


# Usage in your scripts
if customer.age < 18:
    context = ErrorContext(operation="customer_validation", resource=customer.id)
    raise BusinessLogicError("minimum_age", customer.age, context)
```

### Custom API Clients

```python
# Extend the factory pattern
def create_custom_api(config: Dict[str, Any]) -> CustomAPI:
    """Create API client for custom service."""
    # Use TXO patterns: rate limiting, circuit breaker, logging
    rate_limiter = _get_rate_limiter(config)
    circuit_breaker = _get_circuit_breaker(config)

    return CustomAPI(
        base_url=config['global']['custom-api-url'],
        token=config['_api-token'],
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker
    )
```

---

## Migration from Previous Versions

### v2.x → v3.1 Migration Checklist

```xml

<migration-guide>
    <breaking-changes>Dir-constants,token-optional,nested-config</breaking-changes>
    <compatibility>limited-v2-support</compatibility>
</migration-guide>
```

```python
# ✅ Update imports
from utils.path_helpers import Dir  # NEW requirement

# ✅ Update all path usage
# OLD: data_handler.load_json('config', 'file.json')
# NEW: data_handler.load_json(Dir.CONFIG, 'file.json')

# ✅ Update token requirement (BREAKING CHANGE)
# OLD: config = parse_args_and_load_config("Script")  # Token was required
# NEW: config = parse_args_and_load_config("Script")  # Token optional by default
# NEW: config = parse_args_and_load_config("Script", require_token=True)  # Explicit

# ✅ Update save methods
# OLD: data_handler.save_json(data, 'output', 'file.json')
# NEW: data_handler.save(data, Dir.OUTPUT, 'file.json')  # Auto-detects JSON

# ✅ Update configuration structure
# OLD: Flat config: {"api-url": "...", "rate-limit": 10}
# NEW: Nested config: {"global": {"api-url": "..."}, "script-behavior": {"rate-limiting": {"calls-per-second": 10}}}
```

### Configuration Migration Script

```python
# scripts/migrate_config_v2_to_v3.py
def migrate_config(old_config_path: str, new_config_path: str):
    """Migrate v2.x flat config to v3.1 nested structure."""

    with open(old_config_path) as f:
        old_config = json.load(f)

    # Convert to nested structure
    new_config = {
        "global": {
            "api-base-url": old_config.get("api-url"),
            "timeout-seconds": old_config.get("timeout", 30)
        },
        "script-behavior": {
            "rate-limiting": {
                "enabled": old_config.get("rate-limit", 0) > 0,
                "calls-per-second": old_config.get("rate-limit", 10)
            }
        }
    }

    with open(new_config_path, 'w') as f:
        json.dump(new_config, f, indent=2)
```

---

## Troubleshooting Deep Dive

### Configuration Issues

**Problem**: `KeyError: 'api-base-url'` in existing scripts

```xml

<troubleshooting-pattern>
    <diagnosis>configuration-structure</diagnosis>
    <steps>validate-structure,check-nesting,verify-keys</steps>
</troubleshooting-pattern>
```

```python
# Diagnosis: Check configuration structure
from utils.config_loader import ConfigLoader

loader = ConfigLoader("myorg", "prod")
config = loader.load_config(validate=False)  # Skip validation temporarily

print("Top-level keys:", list(config.keys()))
if 'global' in config:
    print("Global keys:", list(config['global'].keys()))
else:
    print("❌ Missing 'global' section - need v3.1 nested structure")

# Solution: Access nested structure correctly
api_url = config['global']['api-base-url']  # Not config['api-base-url']
```

**Problem**: `sys.exit(1)` from logger during startup

```python
# Diagnosis: Check all required files exist
from pathlib import Path

required_files = [
    'config/logging-config.json',
    'config/log-redaction-patterns.json',
    f'config/{org_id}-{env_type}-config.json'
]

missing_files = []
for file_path in required_files:
    if not Path(file_path).exists():
        missing_files.append(file_path)

if missing_files:
    print(f"❌ Missing required files: {missing_files}")
    print("Copy example files from config/ directory")
```

### Performance Issues

**Problem**: Script startup takes >2 seconds

```python
# Diagnosis: Check lazy loading is working
import time

start = time.time()
from utils.load_n_save import TxoDataHandler

handler = TxoDataHandler()
import_time = time.time() - start

print(f"Import time: {import_time:.3f}s")  # Should be < 0.1s
print(f"Modules loaded: {list(handler._modules.keys())}")  # Should be empty

# Heavy modules should load only when needed
start = time.time()
df = handler.load_csv(Dir.DATA, "test.csv")  # First pandas usage
pandas_load_time = time.time() - start
print(f"First pandas usage: {pandas_load_time:.3f}s")  # 1-2s is normal
```

### API Integration Issues

**Problem**: Rate limiting not working, getting 429 errors

```python
# Diagnosis: Check rate limiting configuration
rate_config = config['script-behavior']['rate-limiting']
print(f"Rate limiting enabled: {rate_config['enabled']}")
print(f"Calls per second: {rate_config['calls-per-second']}")

# Verify API factory creates rate limiter
from utils.api_factory import create_rest_api

api = create_rest_api(config)
print(f"API has rate limiter: {api.rate_limiter is not None}")

# Test rate limiter manually
if api.rate_limiter:
    api.rate_limiter.wait_if_needed()  # Should pause if needed
```

**Problem**: Circuit breaker opening too frequently

```python
# Diagnosis: Check circuit breaker settings
cb_config = config['script-behavior']['circuit-breaker']
print(f"Failure threshold: {cb_config['failure-threshold']}")
print(f"Timeout seconds: {cb_config['timeout-seconds']}")

# Check circuit breaker state
if api.circuit_breaker:
    print(f"Circuit open: {api.circuit_breaker.is_open()}")
    print(f"Failure count: {api.circuit_breaker._failures}")

# Solution: Increase failure threshold or improve error handling
```

### Type Safety Issues

**Problem**: `ValueError: Invalid category 'output'`

```python
# Diagnosis: Using string literals instead of Dir constants
from utils.path_helpers import Dir

# ❌ Wrong way (string literal)
try:
    path = get_path('output', 'file.json')
except ValueError as e:
    print(f"Error: {e}")

# ✅ Correct way (Dir constant)
path = get_path(Dir.OUTPUT, 'file.json')
print(f"✅ Correct path: {path}")

# Check all available Dir constants
print("Available Dir constants:", [attr for attr in dir(Dir) if not attr.startswith('_')])
```

---

## Architecture References

For complete understanding of architectural decisions:

### Business Architecture

- **File**: `ai/decided/txo-business-adr_v3.1.md`
- **Covers**: Hard-fail philosophy rationale, security requirements, organizational patterns
- **Key ADRs**: Configuration injection, mandatory files, naming conventions

### Technical Implementation

- **File**: `ai/decided/txo-technical-standards_v3.1.md`
- **Covers**: Thread safety patterns, memory optimization, Python-specific decisions
- **Key ADRs**: Lazy loading, exception hierarchy, context managers

### Function Reference

- **File**: `ai/decided/utils-quick-reference_v3.1.md`
- **Covers**: Complete API documentation, anti-patterns to avoid
- **Purpose**: Prevent AI hallucination by showing existing functions

### Dependency Architecture

- **File**: `module-dependency-diagram.md`
- **Covers**: Layer relationships, refactoring order, testing strategy
- **Visual**: Mermaid diagrams of component relationships

---

## Version History

### v3.1 (Current)

- Added comprehensive architecture explanation and customization guide
- Enhanced security and performance deep dive sections

### v3.0

- Initial in-depth guide with layered architecture documentation
- Complete setup and troubleshooting procedures

---

**Version:** v3.1  
**Last Updated:** 2025-01-25
**Domain:** TXO Framework Documentation  
**Purpose:** Complete architectural understanding and customization guide