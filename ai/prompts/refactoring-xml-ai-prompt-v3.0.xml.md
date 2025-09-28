# Refactoring prompt for TXO v3.0

```xml

<?xml version="1.0" encoding="UTF-8"?>
<txo_v3_refactoring_assistant version="3.0">
    <metadata>
        <purpose>Guide AI assistants through TXO v2.1 to v3.0 refactoring</purpose>
        <last_updated>2025-01-15</last_updated>
        <estimated_effort>40-60 hours</estimated_effort>
        <breaking_changes>true</breaking_changes>
    </metadata>

    <ai_instructions>
        <instruction priority="critical">
            When user asks about v3.0 refactoring, FIRST assess current state:
            1. Request all utils/*.py files
            2. Check for soft-fail patterns (config.get)
            3. Look for sys.exit() calls
            4. Identify global state variables
            5. Find methods over 100 lines
            6. Generate assessment report
        </instruction>

        <instruction priority="critical">
            ENFORCE these principles strictly:
            - NO soft-fail on configuration (config.get → config[])
            - NO sys.exit() in library code (raise exceptions)
            - NO global mutable state (except logging)
            - NO methods over 50 lines (split them)
            - ALWAYS use HelpfulError for user-facing errors
        </instruction>

        <instruction priority="high">
            Track all changes in a table:
            | File | Issue | Fix | Status | Breaking |
            Update after each file modification
        </instruction>
    </ai_instructions>

    <phase_1_critical_fixes>
        <title>Phase 1: Eliminate Soft-Fail Patterns (Day 1-2)</title>

        <file name="api_factory.py">
            <search_patterns>
                config.get("script-behavior", {})
                script_behavior.get("rate-limiting", {})
                script_behavior.get("circuit-breaker", {})
            </search_patterns>

            <fix_pattern>
                <before>
                    script_behavior = config.get("script-behavior", {})
                    if not script_behavior.get("enable-rate-limiting", False):
                    return None
                </before>
                <after>
                    # Hard fail - script-behavior is REQUIRED
                    script_behavior = config["script-behavior"]
                    rate_config = script_behavior["rate-limiting"]

                    if not rate_config["enabled"]:
                    return None
                </after>
            </fix_pattern>

            <validation>
                # Test that KeyError is raised
                config = {"global": {}}
                try:
                api = create_rest_api(config)
                print("ERROR: Should have raised KeyError")
                except KeyError as e:
                print(f"✓ Correctly raised KeyError: {e}")
            </validation>
        </file>

        <file name="rest_api_helpers.py">
            <search_patterns>
                config.get("script-behavior", {}).get(
                self.timeouts.get(
                batch_config.get(
            </search_patterns>

            <fix_pattern>
                <before>
                    delay = config.get("script-behavior", {}).get("api-delay-seconds", 1)
                </before>
                <after>
                    # If script-behavior exists, delay is required
                    try:
                    delay = config["script-behavior"]["api-delay-seconds"]
                    except KeyError:
                    delay = 1 # Default only if entire section missing
                </after>
            </fix_pattern>
        </file>

        <file name="script_runner.py">
            <issues>
                - validate_config parameter allows skipping validation
                - getattr() used for optional flags
                - Global logger modification
            </issues>

            <complete_rewrite>
                Remove ALL validation escape hatches:
                - Delete validate_config parameter
                - Delete --no-validation flag
                - Always call validate_schema
                - Replace getattr() with direct access
                - Create new logger instance, don't modify global
            </complete_rewrite>
        </file>
    </phase_1_critical_fixes>

    <phase_2_remove_sys_exit>
        <title>Phase 2: Remove sys.exit() from Libraries (Day 3)</title>

        <file name="config_loader.py">
            <search_lines>
                Line 117: sys.exit(1)
                Line 136: sys.exit(1)
                Line 143: sys.exit(1)
            </search_lines>

            <fix_pattern>
                <before>
                    except FileNotFoundError as e:
                    logger.error(f"Schema file not found: {schema_filename}")
                    sys.exit(1)
                </before>
                <after>
                    except FileNotFoundError as e:
                    raise HelpfulError(
                    what_went_wrong=f"Schema file '{schema_filename}' not found",
                    how_to_fix="Ensure schema exists in schemas/ directory",
                    example="Run: ls schemas/ to check available schemas"
                    )
                </after>
            </fix_pattern>

            <remove_import>
                import sys # Remove if no longer needed
            </remove_import>
        </file>
    </phase_2_remove_sys_exit>

    <phase_3_global_state>
        <title>Phase 3: Eliminate Global State (Week 2)</title>

        <file name="oauth_helpers.py">
            <global_variables>
                _token_cache = TokenCache()
                _default_client = OAuthClient(cache_tokens=True)
            </global_variables>

            <refactor_to>
                class OAuthManager:
                """Manager for OAuth operations without global state."""

                def __init__(self, cache_enabled: bool = True):
                self.cache = TokenCache() if cache_enabled else None
                self._clients: Dict[str, OAuthClient] = {}

                def get_client(self, tenant_id: str) -> OAuthClient:
                if tenant_id not in self._clients:
                self._clients[tenant_id] = OAuthClient(
                tenant_id=tenant_id,
                cache_tokens=self.cache is not None
                )
                return self._clients[tenant_id]

                def get_token(self, config: Dict[str, Any]) -> str:
                tenant_id = config["global"]["tenant-id"]
                client = self.get_client(tenant_id)
                return client.get_client_credentials_token(
                client_id=config["global"]["client-id"],
                client_secret=config["_client_secret"],
                scope=config["global"]["oauth-scope"]
                )

                # Backward compatibility function
                def get_client_credentials_token(*args, **kwargs):
                """DEPRECATED: Use OAuthManager instead."""
                import warnings
                warnings.warn(
                "get_client_credentials_token is deprecated. Use OAuthManager.",
                DeprecationWarning,
                stacklevel=2
                )
                manager = OAuthManager()
                return manager.get_token(*args, **kwargs)
            </refactor_to>
        </file>

        <file name="api_factory.py">
            <global_variables>
                _api_cache: WeakValueDictionary = WeakValueDictionary()
                _cache_lock = threading.Lock()
            </global_variables>

            <refactor_to>
                class ApiFactory:
                """Factory for creating API clients without global state."""

                def __init__(self, enable_cache: bool = False):
                self.cache_enabled = enable_cache
                self._cache: Dict[str, Any] = {} if enable_cache else None
                self._lock = threading.Lock() if enable_cache else None

                def create_rest_api(self, config: Dict[str, Any],
                use_cache: bool = None) -> TxoRestAPI:
                # Implementation without global state
                pass

                # Default instance for backward compatibility
                _default_factory = ApiFactory(enable_cache=False)

                def create_rest_api(config: Dict[str, Any], **kwargs) -> TxoRestAPI:
                """Backward compatible function."""
                return _default_factory.create_rest_api(config, **kwargs)
            </refactor_to>
        </file>

        <file name="logger.py">
            <note>
                Logger singleton is acceptable as logging is inherently global.
                However, improve thread safety and cleanup.
            </note>

            <minor_improvements>
                - Add __del__ method for cleanup
                - Use threading.RLock instead of Lock
                - Add reset() method for testing
            </minor_improvements>
        </file>
    </phase_3_global_state>

    <phase_4_split_complex_methods>
        <title>Phase 4: Split Complex Methods (Week 3)</title>

        <file name="rest_api_helpers.py">
            <method name="_execute_request" lines="150+">
                <split_into>
                    _validate_request(method, url)
                    _apply_pre_request_checks()
                    _perform_http_request(method, url, **kwargs)
                    _handle_response(response)
                    _handle_retry_logic(attempt, error)
                </split_into>

                <new_structure>
                    def _execute_request(self, method: str, url: str, **kwargs):
                    """Simplified orchestration method."""
                    self._validate_request(method, url)
                    self._apply_pre_request_checks()

                    for attempt in range(self.max_retries):
                    try:
                    response = self._perform_http_request(method, url, **kwargs)
                    return self._handle_response(response)
                    except RetryableError as e:
                    if not self._should_retry(attempt, e):
                    raise
                    self._wait_before_retry(attempt, e)

                    raise ApiOperationError(f"Failed after {self.max_retries} attempts")
                </new_structure>
            </method>

            <method name="_handle_async_operation" lines="80+">
                <split_into>
                    _extract_async_headers(response)
                    _poll_async_status(location, retry_after)
                    _wait_for_async_completion(location, max_wait)
                </split_into>
            </method>
        </file>

        <file name="load_n_save.py">
            <method name="save" lines="100+">
                <split_into>
                    _detect_data_type(data, filename)
                    _save_dataframe(data, path, **kwargs)
                    _save_json(data, path, **kwargs)
                    _save_text(data, path, **kwargs)
                    _save_workbook(data, path, **kwargs)
                </split_into>

                <new_structure>
                    def save(self, data: Any, directory: str, filename: str, **kwargs) -> Path:
                    """Save data with automatic type detection."""
                    path = get_path(directory, filename)
                    data_type = self._detect_data_type(data, filename)

                    save_methods = {
                    'dataframe': self._save_dataframe,
                    'json': self._save_json,
                    'text': self._save_text,
                    'workbook': self._save_workbook
                    }

                    save_method = save_methods.get(data_type)
                    if not save_method:
                    raise TypeError(f"Unsupported data type: {type(data)}")

                    return save_method(data, path, **kwargs)
                </new_structure>
            </method>
        </file>
    </phase_4_split_complex_methods>

    <phase_5_memory_optimization>
        <title>Phase 5: Fix Memory Issues (Week 3)</title>

        <issue name="thread_local_leak">
            <problem>
                Thread-local storage in SessionManager can leak memory when threads die
            </problem>

            <solution>
                Use WeakKeyDictionary for thread tracking:

                import weakref
                from threading import current_thread

                class SessionManager:
                def __init__(self):
                self._thread_sessions = weakref.WeakKeyDictionary()

                def get_session(self, key: str) -> requests.Session:
                thread = current_thread()
                if thread not in self._thread_sessions:
                self._thread_sessions[thread] = {}

                thread_cache = self._thread_sessions[thread]
                if key not in thread_cache:
                thread_cache[key] = self._create_session()

                return thread_cache[key]
            </solution>
        </issue>

        <issue name="dataclass_slots_conflict">
            <problem>
                Can't use __slots__ with dataclass field defaults
            </problem>

            <solution>
                Use __init__ method instead of field defaults:

                @dataclass
                class ProcessingResult:
                __slots__ = ['successful', 'failed', 'total_time']

                def __init__(self):
                self.successful = []
                self.failed = []
                self.total_time = 0.0
            </solution>
        </issue>
    </phase_5_memory_optimization>

    <phase_6_new_patterns>
        <title>Phase 6: Introduce New Patterns (Week 4)</title>

        <pattern name="ConfigProxy">
            <purpose>Safer configuration access with better errors</purpose>

            <implementation>
                # utils/config_proxy.py
                class ConfigProxy:
                def __init__(self, config: Dict[str, Any], source: str = "config"):
                self._config = config
                self._source = source

                def require(self, *path: str) -> Any:
                """Get required value - hard fail with helpful error."""
                current = self._config
                for i, key in enumerate(path):
                if key not in current:
                path_str = '.'.join(path[:i+1])
                raise HelpfulError(
                what_went_wrong=f"Missing config: {path_str}",
                how_to_fix=f"Add to {self._source}",
                example=self._generate_example(path)
                )
                current = current[key]
                return current
            </implementation>

            <usage>
                config = ConfigProxy(raw_config, "demo-test-config.json")
                url = config.require("global", "api-base-url")
                timeout = config.optional("timeouts", "rest", default=60)
            </usage>
        </pattern>

        <pattern name="MethodMetrics">
            <purpose>Track method performance and complexity</purpose>

            <implementation>
                def measure_complexity(func):
                """Decorator to warn about complex methods."""
                import inspect

                @wraps(func)
                def wrapper(*args, **kwargs):
                source = inspect.getsource(func)
                lines = source.count('\n')

                if lines > 50:
                logger.warning(
                f"Method {func.__name__} has {lines} lines. "
                f"Consider refactoring."
                )

                return func(*args, **kwargs)

                return wrapper
            </implementation>
        </pattern>
    </phase_6_new_patterns>

    <validation_suite>
        <test name="no_soft_fail">
            <description>Ensure no soft-fail patterns remain</description>

            <script>
                import os
                import re

                soft_fail_pattern = re.compile(r'config\.get\(["\']')

                for root, dirs, files in os.walk('utils'):
                for file in files:
                if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                content = f.read()
                matches = soft_fail_pattern.findall(content)
                if matches:
                print(f"FAIL: {path} has {len(matches)} soft-fail patterns")
                else:
                print(f"PASS: {path}")
            </script>
        </test>

        <test name="no_sys_exit">
            <description>Ensure no sys.exit() in library code</description>

            <script>
                for file in utils/*.py:
                if grep -q "sys.exit" "$file"; then
                echo "FAIL: $file contains sys.exit()"
                else
                echo "PASS: $file"
                fi
            </script>
        </test>

        <test name="method_length">
            <description>Check for methods over 50 lines</description>

            <script>
                import ast
                import os

                def check_method_length(filepath):
                with open(filepath, 'r') as f:
                tree = ast.parse(f.read())

                for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                lines = node.end_lineno - node.lineno
                if lines > 50:
                print(f"WARN: {filepath}::{node.name} has {lines} lines")

                for root, dirs, files in os.walk('utils'):
                for file in files:
                if file.endswith('.py'):
                check_method_length(os.path.join(root, file))
            </script>
        </test>
    </validation_suite>

    <migration_guide>
        <breaking_change severity="high">
            <what>Configuration access now hard-fails</what>

            <before>
                delay = config.get("script-behavior", {}).get("delay", 1)
            </before>

            <after>
                # Option 1: Required
                delay = config["script-behavior"]["delay"]

                # Option 2: With default
                try:
                delay = config["script-behavior"]["delay"]
                except KeyError:
                delay = 1
            </after>

            <migration_steps>
                1. Audit all config files - ensure complete
                2. Add missing sections with defaults
                3. Update schema with new requirements
                4. Test with incomplete config to find issues
            </migration_steps>
        </breaking_change>

        <breaking_change severity="medium">
            <what>No sys.exit() in libraries</what>

            <impact>
                config_loader now raises HelpfulError instead of exiting
            </impact>

            <migration_steps>
                1. Wrap config loading in try/except
                2. Handle HelpfulError appropriately
                3. Let script_runner handle exits
            </migration_steps>
        </breaking_change>

        <breaking_change severity="low">
            <what>Global state removed from oauth_helpers</what>

            <before>
                token = get_client_credentials_token(...)
            </before>

            <after>
                manager = OAuthManager()
                token = manager.get_token(config)
            </after>

            <migration_steps>
                1. Replace function calls with OAuthManager
                2. Or keep using deprecated function (warns)
            </migration_steps>
        </breaking_change>
    </migration_guide>

    <success_criteria>
        <criterion>Zero .get() calls on config dictionaries</criterion>
        <criterion>Zero sys.exit() in utils/ directory</criterion>
        <criterion>All methods under 50 lines (goal)</criterion>
        <criterion>No global mutable state except logger</criterion>
        <criterion>All existing scripts still functional</criterion>
        <criterion>Performance equal or better than v2.1</criterion>
        <criterion>Memory usage stable under load</criterion>
    </success_criteria>

    <rollback_plan>
        <step>Git tag v2.1.0 before starting</step>
        <step>Create utils_v2_backup/ directory</step>
        <step>Test each phase independently</step>
        <step>Keep deprecated functions for compatibility</step>
        <step>Document all breaking changes</step>
        <step>If issues: git checkout v2.1.0</step>
    </rollback_plan>
</txo_v3_refactoring_assistant>
```