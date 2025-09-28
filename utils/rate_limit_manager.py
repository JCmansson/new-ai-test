# utils/rate_limit_manager.py
from typing import Dict, Optional
from dataclasses import dataclass
import threading
from urllib.parse import urlparse

from utils.api_common import RateLimiter
from utils.logger import setup_logger

logger = setup_logger()


@dataclass
class EndpointLimits:
    """Rate limit configuration for an endpoint."""
    calls_per_second: float
    burst_size: float = 1.0
    shared_pool: Optional[str] = None  # Share limits with other endpoints


class RateLimitManager:
    """
    Manages rate limiters for multiple API endpoints.

    Supports:
    - Per-endpoint limits
    - Shared limit pools
    - Dynamic limit updates from response headers
    """

    def __init__(self, default_cps: float = 10, default_burst: float = 1.0):
        self.default_cps = default_cps
        self.default_burst = default_burst
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

        # Endpoint-specific configurations
        self._endpoint_configs: Dict[str, EndpointLimits] = {}

    def configure_endpoint(self, pattern: str,
                           calls_per_second: float,
                           burst_size: float = 1.0,
                           shared_pool: Optional[str] = None):
        """
        Configure limits for an endpoint pattern.

        Args:
            pattern: URL pattern (e.g., "api.github.com", "*/users/*")
            calls_per_second: Rate limit for this endpoint
            burst_size: Burst capacity
            shared_pool: Name of shared limit pool
        """
        self._endpoint_configs[pattern] = EndpointLimits(
            calls_per_second, burst_size, shared_pool
        )

    def get_limiter(self, url: str) -> RateLimiter:
        """Get or create rate limiter for URL."""
        # Extract domain as default key
        parsed = urlparse(url)
        domain = parsed.netloc

        # Find matching configuration
        config = self._find_config(url, domain)

        # Use shared pool name if configured, else use domain
        key = config.shared_pool if config.shared_pool else domain

        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(
                    config.calls_per_second,
                    config.burst_size
                )
                logger.debug(f"Created rate limiter for {key}: "
                             f"{config.calls_per_second} cps, "
                             f"burst={config.burst_size}")

            return self._limiters[key]

    def _find_config(self, url: str, domain: str) -> EndpointLimits:
        """Find best matching configuration for URL."""
        # Check exact domain match
        if domain in self._endpoint_configs:
            return self._endpoint_configs[domain]

        # Check patterns (simplified - could use fnmatch)
        for pattern, config in self._endpoint_configs.items():
            if pattern in url:
                return config

        # Return defaults
        return EndpointLimits(self.default_cps, self.default_burst)

    def update_from_headers(self, url: str, headers: Dict[str, str]):
        """
        Update rate limits from API response headers.

        Handles:
        - X-RateLimit-Limit: requests per window
        - X-RateLimit-Remaining: requests remaining
        - X-RateLimit-Reset: window reset time
        """
        limit = headers.get('X-RateLimit-Limit')
        remaining = headers.get('X-RateLimit-Remaining')

        if limit and remaining:
            # Adjust limiter based on remaining capacity
            limiter = self.get_limiter(url)
            # Implementation depends on your needs
            logger.debug(f"Rate limit for {url}: {remaining}/{limit} remaining")