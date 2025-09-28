# TXO Technical Standards v3.1

These standards define **Python-specific technical patterns** used in TXO's codebase. These are implementation choices
that could apply to any Python project but reflect TXO's specific needs and preferences.

---

## ADR-T001: Thread-Safe Singleton Pattern

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO runs scripts sequentially across multiple environments and needs shared resources (logger, caches, rate limiters) to
be thread-safe for future concurrent operations.

### Decision

Use double-checked locking pattern for all singleton implementations and shared caches.

### Implementation

```python
# Singleton pattern (from logger.py)
class TxoLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance


# Shared cache pattern (from config_loader.py)
_loader_cache: WeakValueDictionary = WeakValueDictionary()
_cache_lock = threading.Lock()


def get_config_loader(org_id: str, env_type: str, use_cache: bool = True) -> ConfigLoader:
    if not use_cache:
        return ConfigLoader(org_id, env_type)

    cache_key = f"{org_id}_{env_type}"
    with _cache_lock:
        if cache_key in _loader_cache:
            return _loader_cache[cache_key]

        loader = ConfigLoader(org_id, env_type)
        _loader_cache[cache_key] = loader
        return loader
```

### Consequences

- Positive: Prevents race conditions, supports future concurrency
- Positive: Consistent patterns across modules
- Positive: WeakValueDictionary provides automatic cleanup
- Negative: Additional complexity for single-threaded scripts
- Mitigation: Abstract pattern into reusable decorators/mixins

---

## ADR-T002: Thread-Safe Lazy Loading

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

Heavy Python modules (pandas, yaml, openpyxl) slow script startup significantly. Many scripts don't use all
dependencies.

### Decision

Implement thread-safe lazy loading with double-checked locking for heavy dependencies.

### Implementation

```python
class TxoDataHandler:
    # Class-level module cache with thread safety
    _modules: Dict[str, Any] = {}
    _import_lock = threading.Lock()

    @classmethod
    def _lazy_import(cls, module_name: str) -> Any:
        """Thread-safe lazy import of modules."""
        if module_name not in cls._modules:
            with cls._import_lock:
                # Double-check pattern for thread safety
                if module_name not in cls._modules:
                    logger.debug(f"Lazy loading {module_name} module")
                    try:
                        if module_name == 'pandas':
                            import pandas
                            cls._modules['pandas'] = pandas
                        elif module_name == 'yaml':
                            import yaml
                            cls._modules['yaml'] = yaml
                        # ... etc
                    except ImportError as e:
                        error_msg = f"{module_name} not installed. Install with: pip install {module_name}"
                        logger.error(error_msg)
                        raise ImportError(error_msg) from e

        return cls._modules[module_name]
```

### Usage

```python
# Only imports pandas when CSV operations are actually used
def load_csv(directory: CategoryType, filename: str) -> 'pd.DataFrame':
    pd = TxoDataHandler._lazy_import('pandas')  # Lazy import here
    # ... use pd.read_csv()
```

### Consequences

- Positive: Fast startup for scripts not using heavy modules (~2-3 second improvement)
- Positive: Thread-safe for concurrent operations
- Positive: Memory efficient
- Negative: First use has import delay
- Mitigation: Clear debug logging of lazy loads

---

## ADR-T003: Memory Optimization with __slots__

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

TXO creates many instances of data containers (paths, configs, API objects). Default Python objects use dictionaries for
attributes, wasting memory.

### Decision

Use `__slots__` for high-frequency data containers and performance-critical classes.

### When to Use __slots__

- **✅ Use**: Data containers, API objects, thousands of instances
- **✅ Use**: Performance-critical paths, immutable objects
- **❌ Avoid**: Complex inheritance, need for dynamic attributes
- **❌ Avoid**: Classes requiring dataclass default values

### Implementation

```python
# ✅ High-frequency data containers (from path_helpers.py)
@dataclass(frozen=True)
class ProjectPaths:
    __slots__ = [
        'root', 'config', 'data', 'files', 'generated_payloads',
        'logs', 'output', 'payloads', 'schemas', 'tmp', 'wsdl'
    ]
    # All fields required, no defaults
    root: Path
    config: Path
    # ... etc


# ✅ Performance-critical classes (from api_common.py)
class CircuitBreaker:
    __slots__ = ['failure_threshold', 'timeout', '_failures', '_last_failure', '_state']

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        # ... explicit initialization


# ✅ Memory optimization (from config_loader.py)
class ConfigLoader:
    __slots__ = ['org_id', 'env_type', '_config', '_secrets', '_lock']
```

### Consequences

- Positive: ~40% memory reduction for instances
- Positive: 15-20% faster attribute access
- Positive: Prevents typos in attribute names
- Negative: No dynamic attributes possible
- Negative: Incompatible with dataclass default values
- Mitigation: Use selectively for appropriate classes

---

## ADR-T004: Structured Exception Hierarchy

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

Generic Python exceptions provide poor error handling granularity. TXO needs specific error types for different recovery
strategies and user-friendly messages.

### Decision

Implement comprehensive custom exception hierarchy with context and helpful error messages.

### Implementation

```python
# Base exception with context
@dataclass
class ErrorContext:
    operation: Optional[str] = None
    resource: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class TxoBaseError(Exception):
    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        self.context = context or ErrorContext()
        super().__init__(message)


# Specific API errors
class ApiAuthenticationError(ApiError):
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


# User-friendly errors with solutions
class HelpfulError(TxoBaseError):
    def __init__(self, what_went_wrong: str, how_to_fix: str, example: Optional[str] = None):
        message = f"\n❌ Problem: {what_went_wrong}\n\n✅ Solution: {how_to_fix}"
        if example:
            message += f"\n\n📝 Example:\n{example}"
        super().__init__(message)
        self.what_went_wrong = what_went_wrong
        self.how_to_fix = how_to_fix
        self.example = example
```

### Exception Categories

- **TxoBaseError**: Base for all TXO exceptions
- **ApiError**: API-related errors (timeout, auth, rate limit)
- **ConfigurationError**: Configuration problems
- **ValidationError**: Data validation failures
- **FileOperationError**: File I/O problems
- **HelpfulError**: User-friendly errors with solutions

### Consequences

- Positive: Precise error handling and recovery
- Positive: Better debugging with context
- Positive: User-friendly error messages for common problems
- Negative: More exception classes to maintain
- Mitigation: Clear hierarchy documentation, consistent patterns

---

## ADR-T005: Context Manager Resource Management

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

Resource cleanup (API connections, file handles, locks) is error-prone without structured patterns. Manual cleanup is
often forgotten in exception paths.

### Decision

Use context managers for all resource management. Provide context manager wrappers for external resources.

### Implementation

```python
# API lifecycle management (from api_factory.py)
class ApiManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._rest_api: Optional[TxoRestAPI] = None

    def get_rest_api(self, **kwargs) -> TxoRestAPI:
        if self._rest_api is None:
            self._rest_api = create_rest_api(self.config, **kwargs)
        return self._rest_api

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._rest_api and hasattr(self._rest_api, 'close'):
            self._rest_api.close()
            logger.debug(f"Closed REST API connection")


# Configuration loading (from config_loader.py)
class ConfigContext:
    def __init__(self, org_id: str, env_type: str, validate: bool = True):
        self.org_id = org_id
        self.env_type = env_type
        self.validate = validate

    def __enter__(self) -> Dict[str, Any]:
        self.loader = get_config_loader(self.org_id, self.env_type)
        self.config = self.loader.load_config(validate=self.validate)
        return self.config

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup if needed
        pass
```

### Usage Patterns

```python
# API management
with ApiManager(config) as manager:
    rest_api = manager.get_rest_api()
    # API automatically closed on exit

# Configuration loading
with ConfigContext("txo", "prod") as config:
    api_url = config['global']['api-base-url']
    # Resources cleaned up automatically
```

### Consequences

- Positive: Automatic resource cleanup
- Positive: Exception-safe resource handling
- Positive: Clear resource lifetimes
- Negative: Additional boilerplate for simple cases
- Mitigation: Provide simple context managers for common patterns

---

## ADR-T006: Factory Pattern for Complex Object Creation

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

API client creation involves complex configuration assembly (rate limiting, circuit breakers, timeouts, authentication).
Direct instantiation leads to scattered configuration logic.

### Decision

Use factory functions for complex object creation with configuration injection and optional caching.

### Implementation

```python
def create_rest_api(config: Dict[str, Any],
                    require_auth: bool = True,
                    use_cache: bool = False,
                    cache_key: Optional[str] = None) -> TxoRestAPI:
    """Create configured REST API client with enhanced features."""

    # Generate cache key if caching enabled
    if use_cache and not cache_key:
        org_id = config["_org_id"]
        env_type = config["_env_type"]
        auth_suffix = "auth" if require_auth else "noauth"
        cache_key = f"rest_{org_id}_{env_type}_{auth_suffix}"

    # Check cache
    if use_cache:
        with _cache_lock:
            if cache_key in _api_cache:
                return _api_cache[cache_key]

    # Extract and validate configuration (hard-fail)
    script_behavior = config["script-behavior"]
    timeout_config = script_behavior["api-timeouts"]
    retry_config = script_behavior["retry-strategy"]

    # Create components
    rate_limiter = _get_rate_limiter(config)
    circuit_breaker = _get_circuit_breaker(config)

    # Assemble API client
    api = TxoRestAPI(
        token=config["_token"] if require_auth else None,
        timeout_config=timeout_config,
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker
    )

    # Cache if requested
    if use_cache and cache_key:
        with _cache_lock:
            _api_cache[cache_key] = api

    return api
```

### Benefits

- Centralized configuration logic
- Consistent object creation
- Optional caching and dependency injection
- Easy testing with mock configs

### Consequences

- Positive: Centralized configuration logic, consistent setup
- Positive: Easy testing and mocking
- Negative: Additional abstraction layer
- Mitigation: Clear factory function documentation

---

## ADR-T007: Type Import Organization

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

Runtime imports of heavy modules (pandas, yaml) slow startup. Type checking imports should not affect runtime
performance but are needed for proper type hints.

### Decision

Use `TYPE_CHECKING` block for type-only imports. Organize imports in standard order.

### Import Order

1. Standard library imports
2. Third-party imports
3. Local/internal imports
4. Type checking imports (in TYPE_CHECKING block)

### Implementation

```python
# Standard library
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Third-party (if any)
import requests

# Local imports
from utils.logger import setup_logger
from utils.path_helpers import CategoryType, get_path
from utils.exceptions import FileOperationError

# Type checking only (not loaded at runtime)
if TYPE_CHECKING:
    import pandas as pd
    import yaml
    from openpyxl import Workbook
```

### Type Annotation Usage

```python
# Use string literals for forward references
def load_csv(directory: CategoryType, filename: str) -> 'pd.DataFrame':
    pd = TxoDataHandler._lazy_import('pandas')  # Runtime import
    return pd.read_csv(get_path(directory, filename))


# Use TYPE_CHECKING imports in type hints
def save_workbook(workbook: 'Workbook', directory: CategoryType, filename: str) -> Path:
# Implementation uses actual runtime objects
```

### Consequences

- Positive: Faster startup times (avoid heavy imports)
- Positive: Clear separation of runtime vs type dependencies
- Positive: Consistent import organization
- Negative: Requires understanding of TYPE_CHECKING pattern
- Mitigation: Clear documentation and examples

---

## ADR-T008: Literal Types for Constants

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

String constants for categories, file formats, and API states lack type safety and IDE support. Typos in constants cause
runtime errors.

### Decision

Use `Literal` types for constrained string values combined with runtime validation classes.

### Implementation

```python
from typing import Literal

# Define literal types for type checking
CategoryType = Literal[
    'config', 'data', 'files', 'generated_payloads',
    'logs', 'output', 'payloads', 'schemas', 'tmp', 'wsdl'
]

FileFormat = Literal['json', 'text', 'csv', 'excel', 'yaml', 'binary', 'gzip']


# Runtime constants class for validation
class Dir:
    CONFIG: CategoryType = 'config'
    DATA: CategoryType = 'data'
    OUTPUT: CategoryType = 'output'

    # ... etc

    @classmethod
    def validate(cls, category: str) -> bool:
        """Runtime validation of category strings."""
        return category in {cls.CONFIG, cls.DATA, cls.OUTPUT, ...}


# Type-safe function signatures
def get_path(category: CategoryType, filename: str) -> Path:
    """Type-safe path construction with runtime validation."""
    if not Dir.validate(category):
        raise ValueError(f"Invalid category: {category}. Use Dir.* constants")
    # ... implementation
```

### IDE Benefits

```python
# IDE autocompletes valid values
data_handler.save(data, Dir.OUTPUT, 'file.json')  # ✅ Autocomplete works
data_handler.save(data, Dir.OUTPU, 'file.json')  # ❌ Type error caught
```

### Consequences

- Positive: Type-safe string constants with IDE support
- Positive: Compile-time validation with mypy
- Positive: Runtime validation prevents errors
- Negative: Requires Python 3.8+ or typing_extensions
- Mitigation: Provide runtime validation fallbacks

---

## ADR-T009: Docstring Standards

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

Inconsistent docstring formats harm code readability and IDE support. Auto-generated documentation requires structured
formats.

### Decision

Use Google-style docstrings with mandatory sections for public APIs.

### Required Sections

- **Description**: What the function does
- **Args**: All parameters with types and descriptions
- **Returns**: Return value type and description
- **Raises**: Exceptions that may be raised
- **Example**: Usage example for complex functions

### Implementation

```python
def load_csv(directory: CategoryType, filename: str,
             delimiter: Optional[str] = None,
             encoding: Optional[str] = None,
             usecols: Optional[List[str]] = None) -> 'pd.DataFrame':
    """
    Load CSV file with memory-efficient options.

    Supports large files through selective column loading and custom delimiters.
    Uses lazy loading for pandas dependency.

    Args:
        directory: Source directory (use Dir.* constants)
        filename: CSV filename with extension
        delimiter: Column delimiter (default: comma)
        encoding: File encoding (default: UTF-8)
        usecols: Columns to load for memory efficiency (optional)

    Returns:
        DataFrame containing CSV data

    Raises:
        FileOperationError: If file cannot be read or parsed
        ImportError: If pandas is not installed
        ValidationError: If directory category is invalid

    Example:
        > # Load all data
        > df = TxoDataHandler.load_csv(Dir.DATA, "sales.csv")
        >
        > # Memory-efficient loading
        > df = TxoDataHandler.load_csv(
        ...     Dir.DATA, "large_file.csv",
        ...     usecols=['id', 'name', 'amount']
        ... )
    """
    # Implementation...
```

### PyCharm Compatibility

**IMPORTANT**: Use `>` instead of `>>>` for example code blocks to avoid PyCharm warnings.

```python
# ✅ CORRECT - PyCharm friendly
Example:
    > result = my_function("test")
    > print(result)

# ❌ WRONG - Triggers PyCharm docstring warnings
Example:
    >>> result = my_function("test")
    >>> print(result)
```

### Consequences

- Positive: Consistent documentation format
- Positive: Better IDE support and auto-completion
- Positive: Self-documenting code for complex functions
- Negative: More verbose function definitions
- Mitigation: Use templates and IDE snippets for common patterns

---

## ADR-T010: Method Complexity Management

**Status:** RECOMMENDED
**Date:** 2025-01-25

### Context

Some methods in the codebase exceed 100+ lines with deep nesting (e.g., `_execute_request()` in rest_api_helpers.py),
making them difficult to test, debug, and maintain.

### Decision

Establish method complexity guidelines and refactoring patterns.

### Complexity Limits

- **Target method length**: 50 lines
- **Maximum method length**: 100 lines (review required)
- **Maximum nesting depth**: 4 levels
- **Maximum parameters**: 7 parameters

### Refactoring Patterns

```python
# Instead of one 150-line method
def _execute_request(self, method: str, url: str, **kwargs) -> Any:
    """Main request execution - orchestrates the process."""
    request_data = self._prepare_request(method, url, **kwargs)
    response = self._send_with_retries(request_data)
    return self._process_response(response)


def _prepare_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Prepare request headers, auth, and parameters."""
    # 20-30 lines of preparation logic
    return prepared_request


def _send_with_retries(self, request_data: Dict[str, Any]) -> requests.Response:
    """Send request with retry logic and circuit breaker."""
    # 30-40 lines of retry logic
    return response


def _process_response(self, response: requests.Response) -> Any:
    """Process and validate response, handle errors."""
    # 25-30 lines of response handling
    return processed_data
```

### Benefits of Refactoring

- Each method has single responsibility
- Easier unit testing of individual pieces
- Better code readability and maintenance
- Reusable helper methods

### Consequences

- Positive: Easier testing, debugging, and maintenance
- Positive: Better code readability and reusability
- Negative: More methods to navigate in large classes
- Mitigation: Clear naming conventions and logical method grouping

---

## Summary

These Technical Standards define **how we implement Python code at TXO** - our preferences for threading, memory
optimization, error handling, and code organization. These patterns support TXO's business requirements while following
Python best practices.

Key themes:

1. **Thread Safety**: Prepare for concurrent operations with proper locking
2. **Performance**: Lazy loading, memory optimization, efficient patterns
3. **Reliability**: Structured exceptions, context managers, proper cleanup
4. **Maintainability**: Clear patterns, documentation standards, complexity limits
5. **Type Safety**: Literal types, proper imports, structured validation

These standards should evolve as Python evolves and as TXO's technical needs change.

---

## Version History

### v3.1 (Current)

- Added thread safety patterns and custom exception hierarchy
- Enhanced memory optimization and lazy loading standards

### v3.0

- Initial separation from business ADRs
- Established Python-specific technical patterns

---

**Version:** v3.1  
**Last Updated:** 2025-01-25  
**Domain:** TXO Technical Standards
**Purpose:** Python implementation patterns and best practices