# utils/api_factory.py
"""
API client factory with enhanced configuration support.

Handles creation of REST API clients with:
- Rate limiting and circuit breaker support
- Automatic configuration from config dict
- Optional API instance caching
- Context manager support

All configuration is REQUIRED - no soft fails or defaults.
"""

import threading
from typing import Dict, Any, Optional
from weakref import WeakValueDictionary

from utils.logger import setup_logger
from utils.rest_api_helpers import TxoRestAPI
from utils.api_common import RateLimiter, CircuitBreaker

logger = setup_logger()

# Thread-safe cache for API instances (optional)
_api_cache: WeakValueDictionary = WeakValueDictionary()
_cache_lock = threading.Lock()


def _get_rate_limiter(config: Dict[str, Any]) -> Optional[RateLimiter]:
    """
    Create rate limiter from REQUIRED configuration.

    Args:
        config: Configuration dictionary - must contain script-behavior.rate-limiting

    Returns:
        RateLimiter instance or None if not enabled

    Raises:
        KeyError: If required configuration is missing
    """
    script_behavior = config["script-behavior"]
    rate_config = script_behavior["rate-limiting"]

    if not rate_config["enabled"]:
        return None

    # Hard fail - all required when enabled
    calls_per_second = rate_config["calls-per-second"]
    burst_size = rate_config["burst-size"]  # Hard fail - required field

    logger.debug(f"Creating rate limiter: {calls_per_second} calls/second, burst={burst_size}")
    return RateLimiter(calls_per_second=calls_per_second, burst_size=burst_size)


def _get_circuit_breaker(config: Dict[str, Any]) -> Optional[CircuitBreaker]:
    """
    Create circuit breaker from REQUIRED configuration.

    Args:
        config: Configuration dictionary - must contain script-behavior.circuit-breaker

    Returns:
        CircuitBreaker instance or None if not enabled

    Raises:
        KeyError: If required configuration is missing
    """
    # Hard fail - script-behavior must exist
    script_behavior = config["script-behavior"]

    # Hard fail - circuit-breaker section must exist
    cb_config = script_behavior["circuit-breaker"]

    # Hard fail - enabled flag must exist
    if not cb_config["enabled"]:
        return None

    # Hard fail - required parameters must exist when enabled
    failure_threshold = cb_config["failure-threshold"]
    timeout = cb_config["timeout-seconds"]

    logger.debug(f"Creating circuit breaker: threshold={failure_threshold}, timeout={timeout}s")
    return CircuitBreaker(failure_threshold=failure_threshold, timeout=timeout)


def create_rest_api(config: Dict[str, Any],
                    require_auth: bool = True,
                    use_cache: bool = False,
                    cache_key: Optional[str] = None,
                    rate_limiter: Optional[RateLimiter] = None,
                    circuit_breaker: Optional[CircuitBreaker] = None) -> TxoRestAPI:
    """
    Create configured REST API client with enhanced features.

    Args:
        config: Configuration dictionary
        require_auth: Whether authentication is required (default: True)
        use_cache: Whether to cache and reuse API instances
        cache_key: Optional custom cache key
        rate_limiter: Optional rate limiter
        circuit_breaker: Optional circuit breaker

    Returns:
        Configured TxoRestAPI instance

    Example:
        # Business Central (requires auth)
        api = create_rest_api(config)

        # Public API (no auth)
        api = create_rest_api(config, require_auth=False)
    """
    # Generate cache key if caching is enabled
    if use_cache:
        if not cache_key:
            org_id = config["_org_id"]
            env_type = config["_env_type"]
            auth_suffix = "auth" if require_auth else "noauth"
            cache_key = f"rest_{org_id}_{env_type}_{auth_suffix}"

        with _cache_lock:
            if cache_key in _api_cache:
                logger.debug(f"Returning cached REST API for {cache_key}")
                return _api_cache[cache_key]

    # Extract token only if authentication required
    token = None
    if require_auth:
        token = config["_token"]  # Hard fail if auth required
    else:
        token = config.get("_token")  # Optional if no auth needed

    # Extract other configuration (always required)
    org_id = config["_org_id"]
    env_type = config["_env_type"]
    script_behavior = config["script-behavior"]

    # All subsections are required
    timeout_config = script_behavior["api-timeouts"]
    retry_config = script_behavior["retry-strategy"]
    jitter_config = script_behavior["jitter"]

    # Merge timeout and retry configs
    combined_timeouts = {**timeout_config, **retry_config}

    # Create rate limiter and circuit breaker if not provided
    if rate_limiter is None:
        rate_limiter = _get_rate_limiter(config)

    if circuit_breaker is None:
        circuit_breaker = _get_circuit_breaker(config)

    # Create API instance
    api = TxoRestAPI(
        token=token,
        require_auth=require_auth,
        timeout_config=combined_timeouts,
        jitter_config=jitter_config,
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker
    )

    # Cache if requested
    if use_cache and cache_key:
        with _cache_lock:
            _api_cache[cache_key] = api
            logger.debug(f"Cached REST API instance for {cache_key}")

    logger.debug(
        f"Created REST API client for {org_id}-{env_type} "
        f"(auth={require_auth}, "
        f"rate_limit={rate_limiter is not None}, "
        f"circuit_breaker={circuit_breaker is not None})"
    )

    return api


def clear_api_cache() -> None:
    """
    Clear all cached API instances.

    Useful for testing or when you need to force recreation of API clients.
    """
    with _cache_lock:
        count = len(_api_cache)
        _api_cache.clear()
        if count > 0:
            logger.debug(f"Cleared {count} cached API instances")


class ApiManager:
    """
    Context manager for API lifecycle management.

    Ensures proper cleanup of API resources when used with 'with' statement.
    Configuration is REQUIRED - no defaults.

    Example:
         with ApiManager(config) as manager:
        ...     rest_api = manager.get_rest_api()
        ...     # API is automatically cleaned up on exit
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize API manager.

        Args:
            config: Configuration dictionary for API creation (required)

        Raises:
            KeyError: If required configuration is missing
        """
        self.config = config
        self._rest_api: Optional[TxoRestAPI] = None

        # Validate config has required fields upfront
        self.org_id = config["_org_id"]
        self.env_type = config["_env_type"]

    def get_rest_api(self, **kwargs) -> TxoRestAPI:
        """
        Get or create REST API instance.

        Args:
            **kwargs: Additional arguments for create_rest_api

        Returns:
            Configured REST API instance

        Raises:
            KeyError: If required configuration is missing
        """
        if self._rest_api is None:
            self._rest_api = create_rest_api(self.config, **kwargs)
        return self._rest_api

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        if self._rest_api and hasattr(self._rest_api, 'close'):
            self._rest_api.close()
            logger.debug(f"Closed REST API connection for {self.org_id}-{self.env_type}")


# Utility function for batch configuration
def get_batch_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract batch handling configuration.

    Args:
        config: Main configuration dictionary

    Returns:
        Batch handling configuration

    Raises:
        KeyError: If batch-handling section is missing
    """
    # Hard fail - must have script-behavior and batch-handling
    return config["script-behavior"]["batch-handling"]
