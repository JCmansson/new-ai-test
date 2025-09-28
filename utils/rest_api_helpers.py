# utils/rest_api_helpers.py
"""
REST API helpers for Business Central operations with enhanced features.

Provides robust REST client with:
- Automatic retry with exponential backoff
- Connection pooling with limits
- Async operation support (202 Accepted)
- Rate limiting and circuit breaker integration
- OData pagination support
"""

import json
import time
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.logger import setup_logger
from utils.exceptions import (
    ApiOperationError, ApiTimeoutError, ApiValidationError,
    EntityNotFoundError
)
from utils.api_common import (
    apply_jitter as apply_jitter_func,
    manual_retry,
    RateLimiter,
    CircuitBreaker
)
from utils.rate_limit_manager import RateLimitManager

logger = setup_logger()


@dataclass
class RestOperationResult:
    """
    Result tracking for REST operations.

    Attributes:
        success: Whether operation succeeded
        operation: Type of operation performed
        entity_id: ID of affected entity
        message: Human-readable message
        status_code: HTTP status code
        raw_result: Raw response data
    """
    # Removed __slots__ due to conflict with default values

    success: bool
    operation: str  # "created", "updated", "deleted", "failed"
    entity_id: str
    message: str
    status_code: int = 0
    raw_result: Any = None


class SessionManager:
    """
    Thread-safe session manager with connection pool limits.

    Prevents unbounded growth of session cache and ensures proper cleanup.
    """

    def __init__(self, max_cache_size: int = 50):
        """
        Initialize session manager.

        Args:
            max_cache_size: Maximum number of sessions to cache
        """
        self._session_cache: OrderedDict = OrderedDict()
        self._max_cache_size = max_cache_size
        self._lock = threading.Lock()
        self._thread_local = threading.local()

    def get_session(self, key: str, headers: Dict[str, str],
                    retry_config: Dict[str, Any]) -> requests.Session:
        """
        Get or create a session for the given key.

        Args:
            key: Unique key for this session type
            headers: Headers to apply to session
            retry_config: Retry configuration

        Returns:
            Configured requests.Session
        """
        # Check thread-local first for performance
        if not hasattr(self._thread_local, 'sessions'):
            self._thread_local.sessions = {}

        if key in self._thread_local.sessions:
            return self._thread_local.sessions[key]

        # Check shared cache with lock
        with self._lock:
            if key in self._session_cache:
                session = self._session_cache[key]
                # Move to end (LRU)
                self._session_cache.move_to_end(key)
            else:
                # Create new session
                session = self._create_session(headers, retry_config)

                # Evict oldest if at capacity
                if len(self._session_cache) >= self._max_cache_size:
                    oldest_key = next(iter(self._session_cache))
                    old_session = self._session_cache.pop(oldest_key)
                    old_session.close()
                    logger.debug(f"Evicted oldest session: {oldest_key}")

                self._session_cache[key] = session

        # Store in thread-local
        self._thread_local.sessions[key] = session
        return session

    @staticmethod
    def _create_session(headers: Dict[str, str],
                        retry_config: Dict[str, Any]) -> requests.Session:
        """Create a new configured session."""
        session = requests.Session()
        session.headers.update(headers)

        retry_strategy = Retry(
            total=retry_config["max-retries"],  # Hard-fail if missing
            backoff_factor=retry_config["backoff-factor"],  # Hard-fail if missing
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
            allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_maxsize=10,
            pool_connections=10
        )
        session.mount("https://", adapter)

        return session

    def close_all(self):
        """Close all cached sessions."""
        with self._lock:
            for session in self._session_cache.values():
                session.close()
            self._session_cache.clear()


class TxoRestAPI:
    """
    Enhanced REST API client.

    Features:
    - Optional authentication (for public APIs)
    - Automatic retry with exponential backoff and jitter
    - Connection pooling with limits
    - Rate limiting and circuit breaker support
    - Async operation handling (202 Accepted)
    - OData pagination support
    """

    def __init__(self,
                 token: Optional[str] = None,
                 require_auth: bool = True,
                 rate_limit_manager: Optional[RateLimitManager] = None,
                 timeout_config: Optional[Dict[str, Any]] = None,
                 jitter_config: Optional[Dict[str, Any]] = None,
                 rate_limiter: Optional[RateLimiter] = None,
                 circuit_breaker: Optional[CircuitBreaker] = None):
        """
        Initialize REST API client with enhanced features.

        Args:
            token: Bearer token for authentication (optional if require_auth=False)
            require_auth: Whether authentication is required (default: True)
            timeout_config: Timeout and retry settings
            jitter_config: Jitter configuration
            rate_limiter: Optional rate limiter instance
            circuit_breaker: Optional circuit breaker instance

        Raises:
            ValueError: If require_auth=True but no token provided
        """
        # Validate auth requirements
        if require_auth and not token:
            raise ValueError(
                "Token is required when require_auth=True. "
                "Either provide a token or set require_auth=False for public APIs."
            )

        self.token = token
        self.require_auth = require_auth

        self.rate_limit_manager = rate_limit_manager

        # Default timeout and retry settings
        defaults = {
            "rest-timeout-seconds": 60,
            "max-retries": 5,
            "backoff-factor": 3.0,
            "async-max-wait": 300,
            "async-poll-interval": 5
        }
        self.timeouts = {**defaults, **(timeout_config or {})}

        # Jitter configuration
        self.jitter_config = jitter_config or {"min-factor": 1.0, "max-factor": 1.0}

        # Rate limiting and circuit breaker
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker

        # Initialize headers - auth is optional
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation"
        }

        # Only add Authorization header if token provided
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
            logger.debug("REST API client initialized with authentication")
        else:
            logger.debug("REST API client initialized without authentication (public API mode)")

        # Session management with connection pool limits
        self._session_manager = SessionManager(max_cache_size=50)
        self._session_key = f"rest_{id(self)}"

        # Log configuration
        logger.debug(
            f"Initialized TxoRestAPI "
            f"(auth={'yes' if token else 'no'}, "
            f"rate_limit={'yes' if rate_limiter else 'no'}, "
            f"circuit_breaker={'yes' if circuit_breaker else 'no'})"
        )

    @property
    def session(self) -> requests.Session:
        """Get the current session with lazy initialization."""
        return self._session_manager.get_session(
            self._session_key,
            self.headers,
            self.timeouts
        )

    def apply_jitter(self, delay: float) -> float:
        """Apply jitter to delay based on configuration."""
        return apply_jitter_func(delay, self.jitter_config)

    @staticmethod
    def extract_context_from_url(url: str) -> str:
        """Extract env/company from BC URL for logging."""
        try:
            parts = url.split('/')
            env = None
            company = None

            # Find environment ID
            if len(parts) > 5:
                env = parts[5]

            # Find company
            for part in parts:
                if 'companies(' in part:
                    company = part.split('(')[1].rstrip(')')
                    if len(company) > 8 and '-' in company:
                        company = company[:8] + "..."
                    break

            if env and company:
                return f"[{env}:{company}]"
            elif env:
                return f"[{env}]"

        except (IndexError, AttributeError):
            pass
        return "[REST]"

    def _check_circuit_breaker(self, operation: str) -> None:
        """Check if circuit breaker allows operation."""
        if self.circuit_breaker and self.circuit_breaker.is_open():
            raise ApiOperationError(
                f"Circuit breaker open for {operation}. "
                f"Too many failures detected."
            )

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting if configured."""
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()

    def _handle_response_error(self, response: requests.Response,
                               operation_name: str) -> None:
        """Convert REST errors to appropriate exceptions."""
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message',
                                                            f"HTTP {response.status_code}")
        except (ValueError, AttributeError):
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"

        # Record failure in circuit breaker
        if self.circuit_breaker:
            self.circuit_breaker.record_failure()

        # Enhanced error classification
        if response.status_code == 408:
            raise ApiTimeoutError(f"{operation_name} timed out: {error_message}")
        elif response.status_code in [400, 422]:
            raise ApiValidationError(f"{operation_name} validation failed: {error_message}")
        elif response.status_code == 404:
            raise EntityNotFoundError("Resource", error_message)
        elif response.status_code == 409:
            raise ApiValidationError(f"{operation_name} conflict: {error_message}")
        elif response.status_code == 429:
            raise ApiOperationError(f"{operation_name} rate limited: {error_message}")
        else:
            raise ApiOperationError(f"{operation_name} failed: {error_message}")

    def _handle_async_operation(self, response: requests.Response,
                                context: str) -> Dict[str, Any]:
        """
        Handle 202 Accepted responses with polling.

        Args:
            response: Initial 202 response
            context: Logging context

        Returns:
            Final result after async operation completes
        """
        if response.status_code != 202:
            return response.json() if response.content else {}

        location = response.headers.get('Location')
        if not location:
            # No location header, return what we have
            logger.warning(f"{context} 202 response missing Location header")
            return response.json() if response.content else {}

        # Get polling interval from Retry-After or use config (hard-fail)
        retry_after = int(response.headers.get('Retry-After',
                                               self.timeouts['async-poll-interval']))
        max_wait = self.timeouts['async-max-wait']

        logger.info(f"{context} Async operation started, polling {location}")

        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < max_wait:
            poll_count += 1

            # Wait with jitter
            jittered_delay = self.apply_jitter(retry_after)
            logger.debug(f"{context} Polling attempt {poll_count}, waiting {jittered_delay:.1f}s")
            time.sleep(jittered_delay)

            # Check status
            try:
                status_response = self._execute_request("GET", location,
                                                        skip_async_check=True)

                if status_response.status_code == 200:
                    logger.info(f"{context} Async operation completed after {poll_count} polls")
                    return status_response.json() if status_response.content else {}
                elif status_response.status_code == 202:
                    # Still processing
                    retry_after = int(status_response.headers.get('Retry-After', retry_after))
                    continue
                else:
                    # Operation failed
                    self._handle_response_error(status_response, "Async operation")

            except Exception as e:
                logger.error(f"{context} Error polling async operation: {e}")
                raise

        # Timeout
        elapsed = time.time() - start_time
        raise ApiTimeoutError(
            f"Async operation timeout after {elapsed:.1f}s ({poll_count} polls)"
        )

    def _execute_request(self, method: str, url: str,
                         skip_async_check: bool = False,
                         **kwargs) -> requests.Response:
        """
        Execute HTTP request with retry logic, rate limiting, and circuit breaker.

        Args:
            method: HTTP method
            url: Request URL
            skip_async_check: Skip async operation handling
            **kwargs: Additional request arguments

        Returns:
            Response object
        """

        # Check circuit breaker
        self._check_circuit_breaker(f"{method} {url}")

        # Apply rate limiting
        self._apply_rate_limit()

        max_retries = self.timeouts["max-retries"]  # Hard-fail if missing
        backoff_factor = self.timeouts["backoff-factor"]  # Hard-fail if missing
        timeout = self.timeouts["rest-timeout-seconds"]  # Hard-fail if missing

        if 'timeout' not in kwargs:
            kwargs['timeout'] = timeout

        last_error = None
        context = self.extract_context_from_url(url)

        for attempt in range(max_retries):
            try:
                logger.debug(f"{context} {method} request (attempt {attempt + 1}/{max_retries})")

                response = self.session.request(method, url, **kwargs)

                # UPDATE RATE LIMITS FROM HEADERS (ADD HERE)
                if self.rate_limit_manager and response.headers:
                    self.rate_limit_manager.update_from_headers(url, dict(response.headers))

                if response.ok or response.status_code == 202:
                    # Record success in circuit breaker
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success()

                    # Handle async operations
                    if response.status_code == 202 and not skip_async_check:
                        result = self._handle_async_operation(response, context)
                        # Return the actual response with async result content
                        response._content = json.dumps(result).encode('utf-8') if result else b''
                        response.status_code = 200  # Update status to indicate completion
                        return response

                    return response

                # Check if we should retry
                if response.status_code in [429, 500, 502, 503, 504]:
                    if response.status_code == 429 and self.rate_limit_manager:
                        self.rate_limit_manager.update_from_headers(url, dict(response.headers))
                    last_error = f"HTTP {response.status_code}"
                    if attempt < max_retries - 1:
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            delay = float(retry_after)
                            logger.warning(f"{context} Rate limited, waiting {delay}s")
                        else:
                            delay = backoff_factor ** attempt

                        jittered_delay = self.apply_jitter(delay)
                        logger.warning(f"{context} HTTP {response.status_code}, "
                                       f"retrying in {jittered_delay:.1f}s")
                        time.sleep(jittered_delay)
                        continue

                # Non-retryable error
                self._handle_response_error(response, method)

            except requests.Timeout as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    delay = backoff_factor ** attempt
                    jittered_delay = self.apply_jitter(delay)
                    logger.warning(f"{context} Timeout on attempt {attempt + 1}/{max_retries}, "
                                   f"retrying in {jittered_delay:.1f}s")
                    time.sleep(jittered_delay)
                    continue
                raise ApiTimeoutError(f"{method} request timed out: {url}")

            except requests.RequestException as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    delay = backoff_factor ** attempt
                    jittered_delay = self.apply_jitter(delay)
                    logger.warning(f"{context} Request error on attempt {attempt + 1}/{max_retries}, "
                                   f"retrying in {jittered_delay:.1f}s: {e}")
                    time.sleep(jittered_delay)
                    continue
                raise ApiOperationError(f"{method} request failed: {e}")

        # Record failure in circuit breaker after all retries exhausted
        if self.circuit_breaker:
            self.circuit_breaker.record_failure()

        raise ApiOperationError(
            f"{method} failed after {max_retries} attempts. Last error: {last_error}"
        )

    def get(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute GET request with authentication and retry logic."""
        response = self._execute_request("GET", url, params=params)
        return response.json() if response.content else {}

    def get_odata_entities(self, base_url: str, entity_name: str,
                           odata_filter: str = None,
                           select_fields: List[str] = None,
                           page_size: int = None,
                           max_pages: int = None,
                           log_context: str = None,
                           batch_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Get all entities from OData endpoint with automatic pagination.

        Args:
            base_url: Base OData URL
            entity_name: OData entity name
            odata_filter: OData $filter clause
            select_fields: List of fields to select
            page_size: Number of records per page
            max_pages: Maximum pages to fetch
            log_context: Context for logging
            batch_config: Batch handling configuration

        Returns:
            List of all entities with OData metadata removed
        """
        if page_size is None:
            batch_config = batch_config or {}
            page_size = batch_config["read-batch-size"]  # Hard-fail if missing

        page_size = min(page_size, 1000)

        if not log_context:
            log_context = self.extract_context_from_url(base_url)

        all_entities = []
        skip = 0
        page_num = 1

        # Build query parameters
        query_params = []
        if odata_filter:
            query_params.append(f"$filter={quote(odata_filter)}")
        if select_fields:
            query_params.append(f"$select={','.join(select_fields)}")

        query_string = "&".join(query_params)

        logger.info(f"{log_context} Starting paginated fetch of {entity_name}")
        if odata_filter:
            logger.debug(f"{log_context} Filter: {odata_filter}")

        while True:
            if max_pages and page_num > max_pages:
                logger.info(f"{log_context} Reached max pages limit ({max_pages})")
                break

            # Build URL with pagination
            pagination_params = f"$top={page_size}&$skip={skip}"
            if query_string:
                url = f"{base_url}/{entity_name}?{query_string}&{pagination_params}"
            else:
                url = f"{base_url}/{entity_name}?{pagination_params}"

            try:
                logger.debug(f"{log_context} Fetching page {page_num} "
                             f"(skip={skip}, top={page_size})")
                response = self.get(url)

                entities = response.get('value', [])
                if not entities:
                    logger.info(f"{log_context} No more entities found, pagination complete")
                    break

                # Clean OData metadata
                cleaned_entities = []
                for entity in entities:
                    cleaned_entity = {k: v for k, v in entity.items()
                                      if not k.startswith('@odata.')}
                    cleaned_entities.append(cleaned_entity)

                all_entities.extend(cleaned_entities)
                logger.debug(f"{log_context} Page {page_num}: Retrieved {len(cleaned_entities)} "
                             f"entities (total: {len(all_entities)})")

                # Check for more pages
                next_link = response.get('@odata.nextLink')
                if not next_link and len(entities) < page_size:
                    logger.debug(f"{log_context} Last page reached "
                                 f"(got {len(entities)} < {page_size})")
                    break

                skip += page_size
                page_num += 1

                # Delay between pages
                if len(entities) == page_size:
                    delay = self.apply_jitter(0.5)
                    logger.debug(f"{log_context} Sleeping {delay:.2f}s between pages")
                    time.sleep(delay)

            except (ApiOperationError, ApiTimeoutError) as e:
                logger.error(f"{log_context} Failed to fetch page {page_num}: {e}")
                if page_num == 1:
                    raise
                else:
                    logger.warning(f"{log_context} Continuing with {len(all_entities)} "
                                   f"entities from successful pages")
                    break

        logger.info(f"{log_context} Retrieved total of {len(all_entities)} "
                    f"entities across {page_num} pages")
        return all_entities

    def get_odata_entities_filtered(self, base_url: str, entity_name: str,
                                    filter_conditions: Dict[str, Any],
                                    select_fields: List[str] = None,
                                    page_size: int = None,
                                    log_context: str = None,
                                    batch_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Get OData entities with multiple filter conditions.

        Args:
            base_url: Base OData URL
            entity_name: OData entity name
            filter_conditions: Dict of field->value conditions
            select_fields: List of fields to select
            page_size: Records per page
            log_context: Context for logging
            batch_config: Batch handling configuration

        Returns:
            List of filtered entities
        """
        filter_parts = []
        for field_name, condition in filter_conditions.items():
            if isinstance(condition, str) and any(op in condition for op in
                                                  ['eq', 'ne', 'gt', 'ge', 'lt', 'le']):
                filter_parts.append(f"{field_name} {condition}")
            else:
                if isinstance(condition, str):
                    filter_parts.append(f"{field_name} eq '{condition}'")
                else:
                    filter_parts.append(f"{field_name} eq {condition}")

        odata_filter = " and ".join(filter_parts) if filter_parts else None

        return self.get_odata_entities(
            base_url, entity_name, odata_filter, select_fields,
            page_size, log_context=log_context, batch_config=batch_config
        )

    def post(self, url: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute POST request with authentication and retry logic."""
        response = self._execute_request("POST", url, json=json_data)
        return response.json() if response.content else {}

    def patch(self, url: str, json_data: Dict[str, Any] = None,
              etag: str = None) -> Dict[str, Any]:
        """
        Execute PATCH request with authentication and retry logic.

        Args:
            url: Request URL
            json_data: JSON payload
            etag: Optional etag for optimistic concurrency
        """
        headers = None
        if etag:
            headers = {"If-Match": etag}

        response = self._execute_request("PATCH", url, json=json_data, headers=headers)
        return response.json() if response.content else {}

    def delete(self, url: str, etag: str = None) -> None:
        """
        Execute DELETE request with authentication and retry logic.

        Args:
            url: Request URL
            etag: Optional etag for optimistic concurrency
        """
        headers = None
        if etag:
            headers = {"If-Match": etag}

        self._execute_request("DELETE", url, headers=headers)

    def create_or_update(self, url: str, entity_name: str,
                         key_field: str, key_value: str,
                         payload: Dict[str, Any]) -> RestOperationResult:
        """
        Enhanced create or update operation for REST/OData endpoints.

        Args:
            url: Base URL for the entity collection
            entity_name: Name of the entity for logging
            key_field: Field name to use for identification
            key_value: Value of the key field
            payload: Data to create/update

        Returns:
            RestOperationResult with operation details
        """
        context = self.extract_context_from_url(url)

        try:
            # Check for existing entity
            filter_url = f"{url}?$filter={key_field} eq '{key_value}'"
            logger.debug(f"{context} Checking for existing {entity_name} "
                         f"with {key_field}='{key_value}'")

            response = self.get(filter_url)
            entities = response.get('value', [])

            if entities:
                # Update existing entity
                existing = entities[0]
                entity_id = existing.get('@odata.id') or existing.get('id', key_value)
                etag = existing.get('@odata.etag')

                if '@odata.id' in existing:
                    update_url = existing['@odata.id']
                else:
                    update_url = f"{url}({entity_id})"

                logger.debug(f"{context} Updating existing {entity_name} {key_value}")
                self.patch(update_url, payload, etag=etag)

                return RestOperationResult(
                    success=True,
                    operation="updated",
                    entity_id=key_value,
                    message=f"Updated existing {entity_name}",
                    status_code=200
                )
            else:
                # Create new entity
                logger.debug(f"{context} Creating new {entity_name} {key_value}")
                result = self.post(url, payload)

                return RestOperationResult(
                    success=True,
                    operation="created",
                    entity_id=key_value,
                    message=f"Created new {entity_name}",
                    status_code=201,
                    raw_result=result
                )

        except Exception as e:
            logger.error(f"{context} Failed to create/update {entity_name} {key_value}: {e}")
            return RestOperationResult(
                success=False,
                operation="failed",
                entity_id=key_value,
                message=str(e),
                status_code=0
            )

    def close(self):
        """Clean up resources."""
        self._session_manager.close_all()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()


def retry_rest_call(api_func, *args, max_retries: int = None,
                    backoff: float = None, **kwargs) -> Any:
    """
    Retry REST API calls with exponential backoff and jitter.

    Note: Mostly redundant now as retry logic is built into TxoRestAPI
    but kept for backward compatibility.

    Args:
        api_func: Function to retry
        max_retries: Maximum retry attempts
        backoff: Backoff factor for exponential delay
        **kwargs: Additional arguments for the function

    Returns:
        Result from successful API call
    """
    # If retry is already handled by the function, just call it
    if hasattr(api_func, '__self__') and isinstance(api_func.__self__, TxoRestAPI):
        kwargs.pop('timeout', None)
        return api_func(*args, **kwargs)

    # Use shared retry logic
    max_retries = max_retries or 3
    backoff = backoff or 2.0
    return manual_retry(api_func, *args, max_retries=max_retries,
                        backoff=backoff, **kwargs)
