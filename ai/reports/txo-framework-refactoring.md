# TXO Framework Refactoring Guide

> **Purpose**: Technical details for framework development and maintenance
> **Audience**: Framework developers and advanced users
> **Source**: Extracted from module-dependency-diagram.md for better organization

---

## Refactoring Order

When updating the template, follow this dependency order:

### Phase 1: Foundation (no dependencies)
1. `exceptions.py` - Add ErrorContext, new exception types
2. `path_helpers.py` - Add Dir constants

### Phase 2: Core Services (minimal dependencies)
3. `logger.py` - Add TokenRedactionFilter, ContextFilter
4. `api_common.py` - Add RateLimiter, CircuitBreaker

### Phase 3: Data Layer (foundation + core)
5. `load_n_save.py` - Add universal save(), thread-safe loading

### Phase 4: API Implementation (all previous)
6. `oauth_helpers.py` - Update for v3.1
7. `rest_api_helpers.py` - Add SessionManager, async handling
8. `soap_api_helpers.py` - Update for v3.1
9. `url_helpers.py` - Update for v3.1

### Phase 5: Orchestration (all previous)
10. `config_loader.py` - Mandatory validation
11. `api_factory.py` - Create rate limiters, circuit breakers
12. `concurrency.py` - Update for v3.1
13. `script_runner.py` - Token optional by default

### Phase 6: User Scripts (everything)
14. Update scripts to use Dir constants
15. Remove unnecessary require_token=True

## Key Design Principles

### 1. Unidirectional Dependencies
- Lower layers never depend on higher layers
- Foundation modules have zero dependencies
- User scripts can use everything

### 2. Single Responsibility
Each module has one clear purpose:
- `logger.py` - Only logging and redaction
- `path_helpers.py` - Only path management and Dir constants
- `api_factory.py` - Only API creation and configuration

### 3. Dependency Injection
Configuration and dependencies are injected:
```python
# Good - injected
def process(config: Dict[str, Any]):
    api = create_rest_api(config)  # Config injected

# Bad - hardcoded
def process():
    config = load_my_config()  # Hidden dependency
    api = create_rest_api(config)
```

### 4. Fail Fast Philosophy
Required configuration uses hard-fail:
```python
# Good - fails immediately if missing
url = config['global']['api-url']  # KeyError if missing

# Bad - silent failure
url = config.get('global', {}).get('api-url', 'default')
```

### 5. Type Safety (v3.1)
Use type-safe constants instead of strings:
```python
# Good - type-safe
from utils.path_helpers import Dir
data = load(Dir.CONFIG, 'file.json')

# Bad - error-prone strings
data = load('config', 'file.json')
```

## Testing Dependencies

### Unit Testing Individual Modules

```bash
# Test exceptions.py - no dependencies
python -c "
from utils.exceptions import HelpfulError, ErrorContext
context = ErrorContext(operation='test')
raise HelpfulError('test', 'fix', 'example')
"

# Test path_helpers.py - no dependencies
python -c "
from utils.path_helpers import Dir, get_path
print(f'Dir.CONFIG = {Dir.CONFIG}')
print(f'Path = {get_path(Dir.CONFIG, \"test.json\")}'')
"

# Test logger.py - needs path_helpers
python -c "
from utils.logger import setup_logger
logger = setup_logger()
logger.info('Test with _token: [should be redacted]')
"

# Test api_common.py - needs logger
python -c "
from utils.api_common import RateLimiter, CircuitBreaker
limiter = RateLimiter(calls_per_second=10)
breaker = CircuitBreaker(failure_threshold=5)
print(f'Circuit open: {breaker.is_open()}')
"
```

### Integration Testing
```bash
# Test v3.1 features
python tests/test_features.py demo test

# Test example script
python src/try_me_script.py demo test
```

## Common Circular Dependency Issues

### Problem Areas to Avoid

1. **Config in Logger**
   - Don't make logger depend on config_loader
   - Logger uses its own JSON loading

2. **API in Exceptions**
   - Exceptions shouldn't import API modules
   - Keep exceptions generic with ErrorContext

3. **Script Runner in Helpers**
   - Helper modules shouldn't import script_runner
   - Use dependency injection instead

### Signs of Circular Dependencies
- `ImportError` at module level
- Functions that import inside themselves
- Modules that import each other
- `cannot import name 'X' from partially initialized module`

### Resolution Strategy
1. Move shared code to a lower layer
2. Use dependency injection instead of imports
3. Create a new intermediate module
4. Use type hints with string literals: `'ClassName'`

## Performance Considerations

### Import Strategy (v3.1)
All dependencies imported directly at module top:

```python
# Hard-fail imports - TXO requires properly configured environment
import pandas as pd
import yaml
import openpyxl  # Used by pandas for Excel operations

class TxoDataHandler:
    # Direct usage - no lazy loading complexity
    def load_csv(self, ...):
        return pd.read_csv(...)  # pd available immediately
```

### Singleton Patterns
Several modules use singleton patterns:
- `logger.py` - Single TxoLogger instance
- `config_loader.py` - Cached configuration
- `api_factory.py` - Optional API instance caching

### Connection Pooling
API modules reuse connections efficiently:
- `SessionManager` - Thread-local + shared cache
- Maximum 50 sessions (LRU eviction)
- Automatic cleanup on exit

### Rate Limiting Performance
- Token bucket algorithm (smooth, not bursty)
- Minimal overhead when disabled
- Thread-safe implementation

## Version Compatibility

### v3.1 Improvements
- **Hard-fail imports** - No more lazy loading complexity
- **UTC timestamp utilities** - Standardized timestamp formatting
- **Complete ADR compliance** - All soft-fail patterns eliminated
- **Enhanced code quality** - Professional standards throughout

### v3.0 → v3.1 Migration
```python
# Import changes - now direct
# OLD: Complex lazy loading system
# NEW: Direct imports at module top

# UTC timestamps - now built-in
# OLD: Manual datetime formatting
utc_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
# NEW: TXO standard format
timestamp = TxoDataHandler.get_utc_timestamp()  # "2025-01-25T143045Z"

# Configuration access - now consistently hard-fail
# OLD: Mixed .get() and [] access
timeout = config.get("timeout", 30)
# NEW: Hard-fail throughout
timeout = config["timeout"]  # KeyError if missing
```

## Troubleshooting

### Module Not Found
```python
ImportError: cannot import name 'Dir' from 'utils.path_helpers'
```
- Ensure using v3.1 of template
- Check path_helpers.py has Dir class

### Circular Import
```python
ImportError: cannot import name 'X' from partially initialized module
```
- Check dependency graph above
- Move shared code to lower layer
- Use hard-fail imports at module top

### Type Errors
```python
TypeError: expected Dir, got str
```
- Update to use Dir constants
- Import Dir from path_helpers

### Config Structure Errors
```python
KeyError: 'rate-limiting'
```
- Update config to nested structure
- Check against schema

### Import Errors (v3.1)
```python
ImportError: No module named 'pandas'
```
- Install dependencies: `pip install -r pyproject.toml`
- Check pyproject.toml has all required packages

## Future Architecture Considerations

### Potential Improvements
1. **Async/Await Support** - Full asyncio implementation
2. **Plugin System** - Dynamic helper loading
3. **Distributed Tracing** - OpenTelemetry integration
4. **Message Queue** - Celery/RabbitMQ for long operations
5. **Metrics Collection** - Prometheus integration
6. **GraphQL Support** - In addition to REST/SOAP

### Maintaining the Architecture
1. Keep dependencies unidirectional
2. Document new modules in dependency diagram
3. Add tests for new dependencies
4. Update refactoring order for new modules
5. Consider performance impact
6. Maintain type safety with Dir constants
7. Follow fail-fast philosophy

## Module Interface Contracts

### Foundation Layer
- **No external dependencies**
- **No I/O operations**
- **Pure Python only**

### Core Services Layer
- **Minimal dependencies (foundation only)**
- **No business logic**
- **Reusable utilities**

### Data Layer
- **Handle all I/O operations**
- **Type detection and conversion**
- **Thread-safe operations**

### API Layer
- **Protocol-specific implementations**
- **Resilience patterns built-in**
- **Connection management**

### Orchestration Layer
- **Compose lower layers**
- **Configuration management**
- **High-level workflows**

### User Scripts Layer
- **Use all available layers**
- **Business logic here**
- **No framework modifications**

---

**Version:** v3.1
**Last Updated:** 2025-09-28
**Domain:** Framework Development
**Purpose:** Technical refactoring guidance and architecture maintenance