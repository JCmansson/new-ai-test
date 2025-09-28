# TXO Python Template v3.0 Refactoring Roadmap

## Executive Summary

This document outlines critical improvements needed to bring the TXO Python Template from v2.1 to v3.0. The focus is on eliminating technical debt, enforcing the hard-fail philosophy consistently, and improving architecture for better maintainability and testing.

**Estimated Effort**: 40-60 hours  
**Risk Level**: Medium (breaking changes in some areas)  
**Priority**: High (addresses fundamental architectural issues)

## Critical Issues Requiring Immediate Fix

### 1. Soft-Fail Patterns Still Present (Priority: CRITICAL)

**Problem**: Despite v2.1's hard-fail philosophy, soft-fail patterns using `.get()` still exist in critical paths.

**Affected Files**:
- `api_factory.py` (lines 56, 75)
- `rest_api_helpers.py` (line 341)
- `script_runner.py` (multiple locations)

**Impact**: Silent failures, configuration errors going unnoticed, violates core v2.1 philosophy.

**Solution**:
```python
# BEFORE (Wrong)
script_behavior = config.get("script-behavior", {})
delay = config.get("script-behavior", {}).get("api-delay-seconds", 1)

# AFTER (Correct)
script_behavior = config["script-behavior"]  # Hard fail if missing
delay = script_behavior["api-delay-seconds"]  # Required when script-behavior exists
```

**Implementation Steps**:
1. Search all files for `.get(` pattern
2. Evaluate each usage - is it configuration or API response?
3. Configuration → Replace with hard-fail
4. API response → Keep `.get()` only if truly optional
5. Add try/except with HelpfulError where needed

### 2. Library Code Using sys.exit() (Priority: CRITICAL)

**Problem**: `config_loader.py` calls `sys.exit()` directly, preventing proper error handling by calling code.

**Affected Files**:
- `config_loader.py` (lines 117, 136, 143)

**Impact**: Scripts can't handle configuration errors gracefully, testing becomes difficult.

**Solution**:
```python
# BEFORE (Wrong)
if not schema_file.exists():
    logger.error("Schema file not found")
    sys.exit(1)

# AFTER (Correct)
if not schema_file.exists():
    raise HelpfulError(
        what_went_wrong="Schema file not found",
        how_to_fix="Ensure schemas/org-env-config-schema.json exists",
        example="This file validates your configuration structure"
    )
```

### 3. Global State Anti-Patterns (Priority: HIGH)

**Problem**: Multiple modules use global state, making testing difficult and creating potential race conditions.

**Affected Files**:
- `logger.py` - Global singleton
- `oauth_helpers.py` - Global token cache and client
- `api_factory.py` - Global API cache

**Impact**: Difficult to test, potential race conditions, memory leaks.

**Solution**: Dependency injection pattern
```python
# BEFORE (Global state)
_token_cache = TokenCache()  # Global
_default_client = OAuthClient()  # Global

# AFTER (Dependency injection)
class OAuthManager:
    def __init__(self, cache: Optional[TokenCache] = None):
        self.cache = cache or TokenCache()
        self.client = OAuthClient(cache_tokens=bool(cache))
```

## Design Improvements

### 4. Overly Complex Methods (Priority: MEDIUM)

**Problem**: Several methods exceed 100 lines with deep nesting.

**Most Complex Methods**:
1. `rest_api_helpers.py::_execute_request()` - 150+ lines
2. `rest_api_helpers.py::_handle_async_operation()` - 80+ lines
3. `load_n_save.py::save()` - Complex type detection

**Solution**: Method extraction
```python
class TxoRestAPI:
    def _execute_request(self, method: str, url: str, **kwargs):
        """Simplified orchestration method."""
        self._validate_request(method, url)
        self._apply_resilience_patterns()
        
        response = self._perform_request(method, url, **kwargs)
        
        if response.status_code == 202:
            return self._handle_async_response(response)
        
        return self._handle_sync_response(response)
    
    def _validate_request(self, method: str, url: str):
        """Validate request parameters."""
        if not url:
            raise ValueError("URL cannot be empty")
        if method not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
            raise ValueError(f"Invalid HTTP method: {method}")
    
    def _apply_resilience_patterns(self):
        """Apply rate limiting and circuit breaker."""
        if self.circuit_breaker:
            self._check_circuit_breaker()
        if self.rate_limiter:
            self._apply_rate_limit()
    
    def _perform_request(self, method: str, url: str, **kwargs):
        """Execute the actual HTTP request."""
        # Just the request logic
        pass
```

### 5. Memory Management Issues (Priority: MEDIUM)

**Problem**: Thread-local storage and weak references used incorrectly.

**Issues**:
- Thread-local storage in `SessionManager` can leak memory
- WeakValueDictionary used unnecessarily in caches
- Dataclass `__slots__` conflicts preventing optimization

**Solution**:
```python
# Better session management
class SessionManager:
    def __init__(self, max_size: int = 50):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
    
    def get_session(self, key: str) -> requests.Session:
        with self._lock:
            if key in self._cache:
                # Move to end (LRU)
                self._cache.move_to_end(key)
                return self._cache[key]
            
            session = self._create_session()
            self._add_to_cache(key, session)
            return session
    
    def _add_to_cache(self, key: str, session: requests.Session):
        """Add with LRU eviction."""
        if len(self._cache) >= self._max_size:
            # Evict oldest
            _, old_session = self._cache.popitem(last=False)
            old_session.close()
        
        self._cache[key] = session
    
    def clear(self):
        """Properly close all sessions."""
        with self._lock:
            for session in self._cache.values():
                session.close()
            self._cache.clear()
```

## Architecture Improvements

### 6. Configuration Access Pattern (Priority: LOW)

**Problem**: Direct dictionary access throughout codebase is error-prone.

**Solution**: Configuration proxy with better error messages
```python
class ConfigProxy:
    """Safer configuration access with helpful errors."""
    
    def __init__(self, config: Dict[str, Any], source: str = "unknown"):
        self._config = config
        self._source = source  # e.g., "demo-test-config.json"
    
    def require(self, *path: str) -> Any:
        """Get required config value with helpful error."""
        current = self._config
        for i, key in enumerate(path):
            if not isinstance(current, dict):
                raise HelpfulError(
                    what_went_wrong=f"Config path {'.'.join(path[:i])} is not a dictionary",
                    how_to_fix=f"Check structure in {self._source}",
                    example="Ensure nested objects are properly formatted"
                )
            
            if key not in current:
                raise HelpfulError(
                    what_went_wrong=f"Missing required config: {'.'.join(path[:i+1])}",
                    how_to_fix=f"Add '{key}' to {'.'.join(path[:i])} section",
                    example=f"Check config/example.json for structure"
                )
            
            current = current[key]
        
        return current
    
    def optional(self, *path: str, default: Any = None) -> Any:
        """Get optional config value."""
        try:
            return self.require(*path)
        except HelpfulError:
            return default

# Usage
config = ConfigProxy(raw_config, "demo-test-config.json")
api_url = config.require("global", "api-base-url")
timeout = config.optional("script-behavior", "timeout", default=30)
```

### 7. Dependency Injection Framework (Priority: LOW)

**Problem**: Hard-coded dependencies make testing difficult.

**Solution**: Simple DI container
```python
class DIContainer:
    """Simple dependency injection container."""
    
    def __init__(self):
        self._services = {}
        self._singletons = {}
    
    def register(self, name: str, factory: Callable, singleton: bool = False):
        """Register a service factory."""
        self._services[name] = (factory, singleton)
    
    def get(self, name: str) -> Any:
        """Get a service instance."""
        if name not in self._services:
            raise KeyError(f"Service '{name}' not registered")
        
        factory, is_singleton = self._services[name]
        
        if is_singleton:
            if name not in self._singletons:
                self._singletons[name] = factory()
            return self._singletons[name]
        
        return factory()

# Setup
container = DIContainer()
container.register("logger", lambda: setup_logger(), singleton=True)
container.register("data_handler", lambda: TxoDataHandler(), singleton=True)
container.register("api", lambda: create_rest_api(config), singleton=False)

# Usage
logger = container.get("logger")
api = container.get("api")
```

## Implementation Plan

### Phase 1: Critical Fixes (Week 1)
1. **Day 1-2**: Fix all soft-fail patterns
   - Search and replace in api_factory.py
   - Search and replace in rest_api_helpers.py
   - Update script_runner.py
   - Test with existing scripts

2. **Day 3**: Remove sys.exit() from library code
   - Update config_loader.py
   - Add proper exception handling
   - Update calling code to handle exceptions

3. **Day 4-5**: Initial testing and bug fixes
   - Run all example scripts
   - Fix any breaking changes
   - Update documentation

### Phase 2: Global State Cleanup (Week 2)
1. **Day 1-2**: Refactor logger.py
   - Remove singleton pattern
   - Add factory method
   - Update all imports

2. **Day 3-4**: Refactor oauth_helpers.py
   - Remove global cache
   - Add OAuthManager class
   - Update api_factory.py

3. **Day 5**: Testing and integration
   - Ensure backward compatibility
   - Performance testing

### Phase 3: Code Quality (Week 3)
1. **Day 1-2**: Split complex methods
   - Refactor _execute_request()
   - Refactor save() method
   - Add unit tests

2. **Day 3-4**: Memory management
   - Fix thread-local issues
   - Optimize caching
   - Add cache monitoring

3. **Day 5**: Documentation and cleanup
   - Update all docstrings
   - Remove deprecated code
   - Update examples

### Phase 4: Architecture (Week 4)
1. **Day 1-2**: Implement ConfigProxy
   - Create new class
   - Optional migration path
   - Update documentation

2. **Day 3-4**: Basic DI container (optional)
   - Implement if time permits
   - Add to new scripts only
   - Document pattern

3. **Day 5**: Final testing and release
   - Full regression testing
   - Performance benchmarks
   - Release notes

## Breaking Changes

### High Impact
1. **Configuration hard-fails** - Scripts will crash if config is incomplete
   - **Migration**: Ensure all config files are complete
   - **Benefit**: No silent failures

2. **No sys.exit() in libraries** - Different exception types
   - **Migration**: Update error handling in scripts
   - **Benefit**: Better testing and error recovery

### Medium Impact
1. **Global state removal** - Some imports may change
   - **Migration**: Update import statements
   - **Benefit**: Better testing, no race conditions

### Low Impact
1. **Method signatures** - Some internal methods split/renamed
   - **Migration**: Only affects custom extensions
   - **Benefit**: More maintainable code

## Testing Strategy

### Unit Tests (New)
```python
# test_config_loader.py
def test_hard_fail_on_missing_config():
    """Ensure KeyError on missing required config."""
    config = {"global": {}}
    with pytest.raises(KeyError):
        _ = config["script-behavior"]  # Should fail

def test_helpful_error_on_schema_missing():
    """Ensure HelpfulError when schema file missing."""
    with pytest.raises(HelpfulError) as exc:
        loader = ConfigLoader("test", "test")
        loader.validate_schema({}, "nonexistent.json")
    
    assert "Schema file not found" in str(exc.value)
```

### Integration Tests
```python
# test_api_integration.py
def test_circuit_breaker_opens_after_failures():
    """Ensure circuit breaker opens after threshold."""
    config = {
        "script-behavior": {
            "circuit-breaker": {
                "enabled": True,
                "failure-threshold": 3,
                "timeout-seconds": 1
            }
        }
    }
    
    api = create_rest_api(config)
    # Simulate 3 failures
    # Assert circuit is open
    # Wait for timeout
    # Assert circuit closes
```

### Performance Tests
```python
# test_performance.py
def test_session_cache_performance():
    """Ensure session caching improves performance."""
    # Measure time with caching
    # Measure time without caching
    # Assert caching is faster
```

## Success Metrics

1. **Zero soft-fail patterns** in configuration access
2. **No sys.exit()** calls in utils/ directory
3. **All methods under 50 lines** (except unavoidable cases)
4. **100% hard-fail compliance** for configuration
5. **No global mutable state** (except logging)
6. **Memory usage stable** under load
7. **All existing scripts still work**

## Risk Mitigation

1. **Backward Compatibility**
   - Keep deprecated functions with warnings
   - Provide migration guide
   - Phase rollout over 2 versions

2. **Testing Coverage**
   - Add unit tests before refactoring
   - Integration tests for critical paths
   - Performance benchmarks

3. **Documentation**
   - Update inline comments
   - Migration guide for v2.1 → v3.0
   - Example scripts showing new patterns

## Post-Implementation

1. **Monitor** for issues in production
2. **Gather feedback** from users
3. **Document** lessons learned
4. **Plan v3.1** for remaining improvements

## Conclusion

This refactoring addresses fundamental architectural issues while maintaining the core TXO philosophy. The hard-fail principle will be consistently applied, global state will be eliminated, and code quality will be significantly improved. The phased approach minimizes risk while delivering value incrementally.