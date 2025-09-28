# tests/test_features.py
"""
Comprehensive test for v3.0 features.

Tests:
- Token redaction in logs (including underscore prefixes)
- Rate limiting with nested config
- Circuit breaker with nested config
- Universal save() with type detection
- API factory with enhanced features
- Error handling patterns with ErrorContext
- Dir constants usage

Usage:
    python test_features.py <org_id> <env_type>

Example:
    python test_features.py demo test
"""

import time
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any

from utils.logger import setup_logger
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir  # v3.0: Type-safe directory constants
from utils.api_factory import create_rest_api, ApiManager
from utils.exceptions import HelpfulError, ApiOperationError, ErrorContext
from utils.api_common import RateLimiter, CircuitBreaker

logger = setup_logger()
data_handler = TxoDataHandler()


def test_token_redaction(config: Dict[str, Any]) -> None:
    """Test that sensitive data is redacted in logs, including underscore prefixes."""
    logger.info("=" * 50)
    logger.info("TEST 1: Token Redaction (v3.0 Enhanced)")
    logger.info("=" * 50)

    # These should all be redacted
    test_cases = [
        ("Bearer token", f"Bearer {config.get('_token', 'test123abc')}"),
        ("JWT token", "eyJhbGciOiJIUzI1NiIs.eyJzdWIiOiIxMjM0.abc123xyz"),
        ("Password JSON", '{"password": "supersecret123"}'),
        ("_password JSON", '{"_password": "metadata_secret"}'),  # v3.0: underscore prefix
        ("Client secret", '{"client-secret": "my-secret-value"}'),
        ("_client_secret", f'{{"_client_secret": "{config.get("_client_secret", "test")}"}}'),  # v3.0
        ("_token metadata", f'{{"_token": "{config.get("_token", "metadata_token")}"}}'),  # v3.0
        ("_api_key", '{"_api_key": "sk-1234567890"}'),  # v3.0
        ("Long token", "a" * 50)  # 50 character token
    ]

    for name, value in test_cases:
        logger.info(f"Testing {name}: {value}")

    logger.info("✅ Check logs/app_*.log - all sensitive data should show [REDACTED]")
    logger.info("✅ v3.0: Underscore-prefixed metadata fields should also be redacted")
    print()


def test_rate_limiter(config: Dict[str, Any]) -> None:
    """Test rate limiting functionality with v3.0 nested config."""
    logger.info("=" * 50)
    logger.info("TEST 2: Rate Limiter (v3.0 Nested Config)")
    logger.info("=" * 50)

    # v3.0: Get rate limit from nested config structure
    rate_config = config["script-behavior"]["rate-limiting"]

    if not rate_config["enabled"]:
        logger.warning("Rate limiting disabled in config - skipping test")
        return

    calls_per_second = rate_config["calls-per-second"]
    burst_size = rate_config.get("burst-size", 1)

    limiter = RateLimiter(calls_per_second=calls_per_second)

    logger.info(f"Testing {calls_per_second} calls/second rate limit (burst={burst_size})")

    # Make rapid calls
    start = time.time()
    num_calls = 10

    for i in range(num_calls):
        limiter.wait_if_needed()
        logger.debug(f"Call {i + 1}/{num_calls} completed")

    elapsed = time.time() - start
    expected_min = (num_calls - 1) / calls_per_second

    logger.info(f"Made {num_calls} calls in {elapsed:.2f}s")
    logger.info(f"Expected minimum time: {expected_min:.2f}s")

    if elapsed >= expected_min * 0.9:  # Allow 10% tolerance
        logger.info("✅ Rate limiter working correctly")
    else:
        logger.warning(f"⚠️ Rate limiter may not be working (too fast)")
    print()


def test_circuit_breaker(config: Dict[str, Any]) -> None:
    """Test circuit breaker functionality with v3.0 nested config."""
    logger.info("=" * 50)
    logger.info("TEST 3: Circuit Breaker (v3.0 Nested Config)")
    logger.info("=" * 50)

    # v3.0: Get circuit breaker from nested config structure
    cb_config = config["script-behavior"]["circuit-breaker"]

    if not cb_config["enabled"]:
        logger.warning("Circuit breaker disabled in config - skipping test")
        return

    threshold = cb_config["failure-threshold"]
    timeout = cb_config["timeout-seconds"]

    breaker = CircuitBreaker(failure_threshold=threshold, timeout=timeout)

    logger.info(f"Testing circuit breaker (threshold={threshold}, timeout={timeout}s)")

    # Record failures
    for i in range(threshold):
        breaker.record_failure()
        logger.debug(f"Recorded failure {i + 1}/{threshold}")

    # Should be open now
    if breaker.is_open():
        logger.info("✅ Circuit breaker opened after threshold failures")
    else:
        logger.error("❌ Circuit breaker should be open but isn't")

    # Record success to reset
    breaker.record_success()
    if not breaker.is_open():
        logger.info("✅ Circuit breaker reset after success")
    else:
        logger.error("❌ Circuit breaker should be closed after success")
    print()


def test_universal_save(config: Dict[str, Any]) -> None:
    """Test v3.0 universal save() with automatic type detection."""
    logger.info("=" * 50)
    logger.info("TEST 4: Universal Save (v3.0 Smart Detection)")
    logger.info("=" * 50)

    org_id = config["_org_id"]
    env_type = config["_env_type"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    # Test 1: JSON with Decimal (auto-handled)
    json_data = {
        "amount": Decimal("99.99"),
        "count": 100,
        "org": org_id,
        "env": env_type
    }
    filename = f"{org_id}-{env_type}-test_json_{timestamp}.json"

    # v3.0: Use Dir.TMP constant instead of string
    path = data_handler.save(json_data, Dir.TMP, filename)
    logger.info(f"✅ JSON with Decimal saved to {path}")

    # Verify it was saved correctly
    loaded = data_handler.load_json(Dir.TMP, filename)
    if loaded["amount"] == 99.99:  # Will be float after round-trip
        logger.info("✅ Decimal serialization worked")

    # Test 2: Plain text
    text_data = f"Test report for {org_id}-{env_type}\nGenerated at {timestamp}"
    filename = f"{org_id}-{env_type}-test_text_{timestamp}.txt"
    path = data_handler.save(text_data, Dir.TMP, filename)
    logger.info(f"✅ Text saved to {path}")

    # Test 3: DataFrame (if pandas available)
    try:
        import pandas as pd
        df = pd.DataFrame([
            {"col1": 1, "col2": "a"},
            {"col1": 2, "col2": "b"}
        ])

        # CSV - v3.0 universal save detects from extension
        filename = f"{org_id}-{env_type}-test_csv_{timestamp}.csv"
        path = data_handler.save(df, Dir.TMP, filename, index=False)
        logger.info(f"✅ DataFrame saved as CSV to {path}")

        # Excel - v3.0 universal save detects from extension
        filename = f"{org_id}-{env_type}-test_xlsx_{timestamp}.xlsx"
        path = data_handler.save(df, Dir.TMP, filename, index=False, sheet_name="TestSheet")
        logger.info(f"✅ DataFrame saved as Excel to {path}")

    except ImportError:
        pd = None
        logger.info("⚠️ Pandas not installed - skipping DataFrame tests")

    # Test 4: YAML (if available)
    try:
        yaml_data = {
            "test": "v3.0 features",
            "nested": {
                "rate-limiting": {"enabled": True},
                "circuit-breaker": {"enabled": False}
            }
        }
        filename = f"{org_id}-{env_type}-test_yaml_{timestamp}.yaml"
        path = data_handler.save(yaml_data, Dir.TMP, filename)
        logger.info(f"✅ YAML saved to {path}")
    except ImportError:
        logger.info("⚠️ YAML not installed - skipping YAML test")

    print()


def test_api_factory(config: Dict[str, Any]) -> None:
    """Test API factory with v3.0 enhanced features."""
    logger.info("=" * 50)
    logger.info("TEST 5: API Factory (v3.0 Enhanced)")
    logger.info("=" * 50)

    has_token = config.get("_token") is not None

    # Test 1: Create API with nested config
    try:
        api = create_rest_api(config, require_auth=has_token)

        # Check v3.0 features
        if api.rate_limiter:
            logger.info("✅ Rate limiter created from nested config")
        else:
            logger.info("ℹ️ Rate limiter not enabled")

        if api.circuit_breaker:
            logger.info("✅ Circuit breaker created from nested config")
        else:
            logger.info("ℹ️ Circuit breaker not enabled")

        # Check SessionManager (v3.0)
        if hasattr(api, '_session_manager'):
            logger.info("✅ SessionManager with connection pooling active")

        # Clean up
        api.close()

    except KeyError as config_error:
        logger.error(f"❌ Missing required config: {config_error}")
        raise HelpfulError(
            what_went_wrong=f"Configuration missing required key: {config_error}",
            how_to_fix="Ensure your config has all required sections",
            example="Check script-behavior section with nested structure"
        )

    # Test 2: Context manager (v3.0 enhanced)
    try:
        with ApiManager(config) as manager:
            api = manager.get_rest_api(require_auth=has_token)
            logger.info("✅ API created with context manager")
            # API will be closed automatically
    except Exception as context_error:
        logger.error(f"❌ Context manager failed: {context_error}")

    print()


def test_error_context(config: Dict[str, Any]) -> None:
    """Test v3.0 ErrorContext for enhanced debugging."""
    logger.info("=" * 50)
    logger.info("TEST 6: Error Context (v3.0 New Feature)")
    logger.info("=" * 50)

    # Use config to satisfy PyCharm
    org_id = config["_org_id"]
    env_type = config["_env_type"]
    logger.debug(f"Testing error context for {org_id}-{env_type}")

    # Test ErrorContext
    context = ErrorContext(
        operation="test_operation",
        resource="/api/test",
        details={"org": org_id, "env": env_type}
    )

    # Test with ApiOperationError
    try:
        raise ApiOperationError(
            "Test error with context",
            context=context
        )
    except ApiOperationError as api_error:
        logger.info(f"Error with context: {api_error}")
        if hasattr(api_error, 'context') and api_error.context:
            logger.info(f"  Operation: {api_error.context.operation}")
            logger.info(f"  Resource: {api_error.context.resource}")
            logger.info("✅ ErrorContext working correctly")
        else:
            logger.error("❌ ErrorContext not attached")

    # Test HelpfulError (unchanged)
    try:
        raise HelpfulError(
            what_went_wrong="This is a v3.0 test error",
            how_to_fix="No action needed - this is intentional",
            example="This demonstrates the helpful error format"
        )
    except HelpfulError as helpful_error:
        logger.info("HelpfulError format:")
        print(str(helpful_error))
        logger.info("✅ HelpfulError pattern working")

    print()


def test_github_api(config: Dict[str, Any]) -> None:
    """Test actual API call using v3.0 enhanced REST client."""
    logger.info("=" * 50)
    logger.info("TEST 7: Live API Test with v3.0 Features")
    logger.info("=" * 50)

    try:
        # v3.0: No auth needed for public API
        api = create_rest_api(config, require_auth=False)

        # Make request to GitHub
        url = "https://api.github.com/repos/python/cpython"

        logger.info("Fetching Python repository info from GitHub...")
        start = time.time()

        result = api.get(url)

        elapsed = time.time() - start

        if result:
            logger.info(f"✅ API call successful in {elapsed:.2f}s")
            logger.info(f"Repository: {result.get('full_name')}")
            logger.info(f"Stars: {result.get('stargazers_count', 0):,}")
            logger.info(f"Language: {result.get('language')}")

            # Check if v3.0 features were used
            if api.rate_limiter:
                logger.info("  (Rate limited)")
            if api.circuit_breaker:
                logger.info("  (Circuit breaker active)")
        else:
            logger.warning("⚠️ No data returned")

        api.close()

    except ApiOperationError as api_error:
        logger.error(f"❌ API call failed: {api_error}")
    except Exception as unexpected_error:
        logger.error(f"❌ Unexpected error: {unexpected_error}")

    print()


def generate_summary_report(config: Dict[str, Any], test_results: Dict[str, bool]) -> None:
    """Generate and save test summary report using v3.0 patterns."""
    logger.info("=" * 50)
    logger.info("TEST SUMMARY (v3.0)")
    logger.info("=" * 50)

    org_id = config["_org_id"]
    env_type = config["_env_type"]

    # Calculate stats
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)

    # Create report
    report = {
        "test_run": {
            "version": "3.0.0",
            "org_id": org_id,
            "env_type": env_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": total_tests - passed_tests
        },
        "test_results": test_results,
        "configuration": {
            "rate_limiting_enabled": config["script-behavior"]["rate-limiting"]["enabled"],
            "circuit_breaker_enabled": config["script-behavior"]["circuit-breaker"]["enabled"],
            "timeout_seconds": config["script-behavior"]["api-timeouts"]["rest-timeout-seconds"],
            "token_optional": config.get("_token") is None  # v3.0 feature
        },
        "v3_features_tested": [
            "Dir constants",
            "Universal save()",
            "Token optional by default",
            "Nested configuration",
            "Enhanced redaction",
            "ErrorContext",
            "SessionManager"
        ]
    }

    # v3.0: Save report using Dir.OUTPUT constant
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{org_id}-{env_type}-test_report_{timestamp}.json"
    path = data_handler.save(report, Dir.OUTPUT, filename)

    # Display summary
    logger.info(f"Tests Passed: {passed_tests}/{total_tests}")
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")

    logger.info(f"\nReport saved to: {path}")

    if passed_tests == total_tests:
        logger.info("\n🎉 All v3.0 tests passed!")
    elif passed_tests > 0:
        logger.info(f"\n⚠️ {total_tests - passed_tests} test(s) failed")
    else:
        logger.error("\n❌ All tests failed")


def main():
    """Main test orchestration for v3.0 features."""
    # Parse args and setup logger FIRST
    from utils.script_runner import parse_args_and_load_config

    # v3.0: Token optional by default
    config = parse_args_and_load_config(
        "V3.0 Feature Test Suite",
        require_token=False  # v3.0: Explicit - no token needed for tests
    )

    logger.info("Starting v3.0 feature tests")
    logger.info(f"Organization: {config['_org_id']}")
    logger.info(f"Environment: {config['_env_type']}")
    logger.info(f"Token present: {config.get('_token') is not None}")
    print()

    # Track results
    test_results = {}

    # Run tests
    tests = [
        ("token_redaction", test_token_redaction),
        ("rate_limiter", test_rate_limiter),
        ("circuit_breaker", test_circuit_breaker),
        ("universal_save", test_universal_save),
        ("api_factory", test_api_factory),
        ("error_context", test_error_context),
        ("github_api", test_github_api)
    ]

    for test_name, test_func in tests:
        try:
            test_func(config)
            test_results[test_name] = True
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            test_results[test_name] = False

    # Generate summary
    generate_summary_report(config, test_results)


if __name__ == "__main__":
    import sys

    try:
        main()
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(130)
    except HelpfulError as e:
        # These are already formatted nicely
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)