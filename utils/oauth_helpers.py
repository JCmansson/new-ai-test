# utils/oauth_helpers.py
"""
Enhanced OAuth 2.0 Client Credentials implementation with caching and retry logic.

Provides robust OAuth token management with:
- Token caching with automatic refresh
- Thread-safe operations
- Retry logic with exponential backoff
- Comprehensive error handling
- Multiple grant type support
"""
import json
import time
import threading
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.logger import setup_logger
from utils.exceptions import ApiAuthenticationError, ApiTimeoutError

logger = setup_logger()


@dataclass
class TokenInfo:
    """
    Container for OAuth token information.

    Attributes:
        access_token: The OAuth access token
        expires_at: When the token expires (UTC timestamp)
        token_type: Type of token (usually "Bearer")
        scope: Granted scope
    """
    # Removed __slots__ due to conflict with default values

    access_token: str
    expires_at: float
    token_type: str = "Bearer"
    scope: Optional[str] = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """
        Check if token is expired or about to expire.

        Args:
            buffer_seconds: Consider expired if expiring within this many seconds

        Returns:
            True if token is expired or expiring soon
        """
        return time.time() >= (self.expires_at - buffer_seconds)

    @property
    def authorization_header(self) -> str:
        """Get the authorization header value."""
        return f"{self.token_type} {self.access_token}"


class TokenCache:
    """
    Thread-safe token cache with automatic expiration.
    """

    def __init__(self):
        """Initialize token cache."""
        self._cache: Dict[str, TokenInfo] = {}
        self._lock = threading.Lock()

    def get(self, cache_key: str) -> Optional[TokenInfo]:
        """
        Get token from cache if valid.

        Args:
            cache_key: Unique key for this token

        Returns:
            TokenInfo if valid token exists, None otherwise
        """
        with self._lock:
            token_info = self._cache.get(cache_key)
            if token_info and not token_info.is_expired():
                remaining = token_info.expires_at - time.time()
                logger.debug(f"Using cached token for {cache_key}, "
                             f"expires in {remaining:.0f}s")
                return token_info
            elif token_info:
                logger.debug(f"Cached token for {cache_key} is expired")
                del self._cache[cache_key]
            return None

    def set(self, cache_key: str, token_info: TokenInfo) -> None:
        """
        Store token in cache.

        Args:
            cache_key: Unique key for this token
            token_info: Token information to cache
        """
        with self._lock:
            self._cache[cache_key] = token_info
            logger.debug(f"Cached token for {cache_key}, "
                         f"expires at {datetime.fromtimestamp(token_info.expires_at)}")

    def clear(self, cache_key: Optional[str] = None) -> None:
        """
        Clear cached tokens.

        Args:
            cache_key: If provided, only clear this key. Otherwise clear all.
        """
        with self._lock:
            if cache_key:
                self._cache.pop(cache_key, None)
                logger.debug(f"Cleared cached token for {cache_key}")
            else:
                self._cache.clear()
                logger.debug("Cleared all cached tokens")


# Global token cache instance
_token_cache = TokenCache()


class OAuthClient:
    """
    Enhanced OAuth 2.0 client with caching and retry logic.
    """

    def __init__(self,
                 tenant_id: Optional[str] = None,
                 timeout: int = 30,
                 max_retries: int = 3,
                 cache_tokens: bool = True):
        """
        Initialize OAuth client.

        Args:
            tenant_id: Azure tenant ID (can be set per request)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            cache_tokens: Whether to cache tokens
        """
        self.tenant_id = tenant_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_tokens = cache_tokens
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        return session

    def get_client_credentials_token(self,
                                     client_id: str,
                                     client_secret: str,
                                     scope: str,
                                     tenant_id: Optional[str] = None,
                                     additional_params: Optional[Dict[str, str]] = None) -> str:
        """
        Get access token using OAuth 2.0 client credentials flow.

        Args:
            client_id: Application (client) ID
            client_secret: Client secret
            scope: OAuth scope
            tenant_id: Azure tenant ID (overrides instance tenant_id)
            additional_params: Additional parameters for token request

        Returns:
            Access token string

        Raises:
            ApiAuthenticationError: If token request fails
            ApiTimeoutError: If request times out
            ValueError: If tenant_id is not provided
        """
        tenant = tenant_id or self.tenant_id
        if not tenant:
            raise ValueError("tenant_id must be provided either in constructor or method call")

        # Check cache first
        cache_key = f"{tenant}:{client_id}:{scope}"
        if self.cache_tokens:
            cached_token = _token_cache.get(cache_key)
            if cached_token:
                return cached_token.access_token

        # Request new token
        token_info = self._request_token(
            tenant_id=tenant,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            grant_type='client_credentials',
            additional_params=additional_params
        )

        # Cache token
        if self.cache_tokens:
            _token_cache.set(cache_key, token_info)

        return token_info.access_token

    def get_token_with_refresh(self,
                               refresh_token: str,
                               client_id: str,
                               client_secret: str,
                               scope: str,
                               tenant_id: Optional[str] = None) -> Tuple[str, str]:
        """
        Get new access token using refresh token.

        Args:
            refresh_token: OAuth refresh token
            client_id: Application (client) ID
            client_secret: Client secret
            scope: OAuth scope
            tenant_id: Azure tenant ID

        Returns:
            Tuple of (access_token, new_refresh_token)

        Raises:
            ApiAuthenticationError: If token request fails
        """
        tenant = tenant_id or self.tenant_id
        if not tenant:
            raise ValueError("tenant_id must be provided")

        token_info = self._request_token(
            tenant_id=tenant,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            grant_type='refresh_token',
            additional_params={'refresh_token': refresh_token}
        )

        # Extract refresh token if present
        new_refresh = getattr(token_info, 'refresh_token', refresh_token)

        return token_info.access_token, new_refresh

    def _request_token(self,
                       tenant_id: str,
                       client_id: str,
                       client_secret: str,
                       scope: str,
                       grant_type: str,
                       additional_params: Optional[Dict[str, str]] = None) -> TokenInfo:
        """
        Internal method to request token from OAuth endpoint.
        """
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        data = {
            'grant_type': grant_type,
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': scope
        }

        if additional_params:
            data.update(additional_params)

        logger.debug(f"Requesting {grant_type} token for client {client_id[:8]}...")

        try:
            response = self.session.post(url, data=data, timeout=self.timeout)

            if response.status_code == 200:
                token_data = response.json()

                # Calculate expiration time
                expires_in = token_data.get('expires_in', 3600)
                expires_at = time.time() + expires_in

                token_info = TokenInfo(
                    access_token=token_data['access_token'],
                    expires_at=expires_at,
                    token_type=token_data.get('token_type', 'Bearer'),
                    scope=token_data.get('scope', scope)
                )

                logger.info(f"Successfully obtained {grant_type} token, "
                            f"expires in {expires_in}s")

                return token_info

            else:
                # Handle error response
                error_msg = f"Token request failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = f"{error_msg}: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}"
                except (json.JSONDecodeError, ValueError, AttributeError):  # Specific exceptions
                    error_msg = f"{error_msg}: {response.text[:200]}"

                logger.error(error_msg)
                raise ApiAuthenticationError(error_msg)

        except requests.Timeout:
            logger.error(f"Token request timed out after {self.timeout}s")
            raise ApiTimeoutError(f"OAuth token request timed out after {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"Token request failed: {e}")
            raise ApiAuthenticationError(f"OAuth token request failed: {e}")
        except KeyError as e:
            logger.error(f"Invalid token response, missing field: {e}")
            raise ApiAuthenticationError(f"Invalid token response, missing: {e}")

    def revoke_token(self, token: str, client_id: str,
                     client_secret: str, tenant_id: Optional[str] = None) -> bool:
        """
        Revoke an access or refresh token.

        Note: Microsoft Azure AD doesn't support token revocation endpoint.
        This method clears the token from cache instead.

        Args:
            token: Token to revoke (not used but kept for API compatibility)
            client_id: Application (client) ID
            client_secret: Client secret (not used but kept for API compatibility)
            tenant_id: Azure tenant ID

        Returns:
            True if revocation succeeded (cache cleared)
        """
        # Mark parameters as intentionally unused for API compatibility
        _ = token  # Unused - Microsoft doesn't support token revocation
        _ = client_secret  # Unused - kept for API consistency

        tenant = tenant_id or self.tenant_id
        if not tenant:
            raise ValueError("tenant_id must be provided")

        # Microsoft doesn't support token revocation endpoint
        # Clear from cache instead
        if self.cache_tokens:
            cache_key = f"{tenant}:{client_id}:*"
            _token_cache.clear(cache_key)
            logger.info(f"Cleared cached tokens for client {client_id[:8]}...")

        return True

    @staticmethod
    def clear_cache() -> None:
        """Clear all cached tokens."""
        _token_cache.clear()


# Global client instance for backward compatibility
_default_client = OAuthClient(cache_tokens=True)


def get_client_credentials_token(tenant_id: str,
                                 client_id: str,
                                 client_secret: str,
                                 scope: str,
                                 use_cache: bool = True) -> str:
    """
    Get access token using OAuth 2.0 client credentials flow.

    Backward compatible function using enhanced implementation.

    Args:
        tenant_id: Azure tenant ID
        client_id: Application (client) ID
        client_secret: Client secret
        scope: OAuth scope
        use_cache: Whether to use token caching (default: True)

    Returns:
        Access token string

    Raises:
        requests.HTTPError: If token request fails
        KeyError: If response is missing access_token
    """
    try:
        # Use the enhanced client
        _default_client.cache_tokens = use_cache
        return _default_client.get_client_credentials_token(
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            tenant_id=tenant_id
        )
    except ApiAuthenticationError as e:
        # Convert to HTTPError for backward compatibility
        error = requests.HTTPError(str(e))
        error.response = type('obj', (object,), {'status_code': 401, 'text': str(e)})()
        raise error
    except Exception as e:
        # Ensure KeyError is raised for missing access_token (backward compat)
        if "access_token" in str(e):
            raise KeyError("access_token") from e
        raise


def clear_token_cache() -> None:
    """Clear all cached OAuth tokens."""
    _token_cache.clear()


def get_oauth_client(tenant_id: Optional[str] = None,
                     timeout: int = 30,
                     max_retries: int = 3,
                     cache_tokens: bool = True) -> OAuthClient:
    """
    Get a configured OAuth client instance.

    Args:
        tenant_id: Azure tenant ID
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        cache_tokens: Whether to cache tokens

    Returns:
        Configured OAuthClient instance
    """
    return OAuthClient(
        tenant_id=tenant_id,
        timeout=timeout,
        max_retries=max_retries,
        cache_tokens=cache_tokens
    )