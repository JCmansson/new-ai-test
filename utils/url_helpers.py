# utils/url_helpers.py
"""
Generic URL construction and manipulation utilities.

Provides reusable URL building functions that can be used
across different APIs and services.
"""

import re
from typing import Dict, Any, Optional, List, Union
from urllib.parse import quote, urlencode, urlparse, urlunparse, parse_qs
from dataclasses import dataclass, field

from utils.logger import setup_logger

logger = setup_logger()


@dataclass
class URLComponents:
    """
    Structured URL components for building and manipulation.

    Attributes:
        base_url: Base URL without path
        path_segments: List of path segments
        query_params: Query parameters
        fragment: URL fragment
    """
    # Removed __slots__ due to conflict with default values

    base_url: str
    path_segments: List[str] = field(default_factory=list)
    query_params: Dict[str, Any] = field(default_factory=dict)
    fragment: Optional[str] = None

    def build(self) -> str:
        """Build the complete URL from components."""
        url = self.base_url.rstrip('/')

        # Add path segments
        if self.path_segments:
            path = '/'.join(str(seg) for seg in self.path_segments if seg)
            url = f"{url}/{path}"

        # Add query parameters
        if self.query_params:
            query_string = build_query_string(self.query_params)
            url = f"{url}?{query_string}"

        # Add fragment
        if self.fragment:
            url = f"{url}#{self.fragment}"

        return url


def build_url(base_url: str,
              *path_segments: Union[str, int],
              query_params: Optional[Dict[str, Any]] = None,
              fragment: Optional[str] = None,
              encode_path: bool = True) -> str:
    """
    Build a URL from components with proper encoding.

    Args:
        base_url: Base URL
        *path_segments: Variable number of path segments
        query_params: Optional query parameters
        fragment: Optional URL fragment
        encode_path: Whether to URL-encode path segments

    Returns:
        Complete URL string

    Example:
         url = build_url("https://api.example.com", "v2", "users", 123,
         ..                query_params={"filter": "active", "limit": 10})
         # Returns: "https://api.example.com/v2/users/123?filter=active&limit=10"
    """
    # Remove trailing slash from base URL
    url = base_url.rstrip('/')

    # Add path segments
    if path_segments:
        if encode_path:
            encoded_segments = [quote(str(seg), safe='') for seg in path_segments]
        else:
            encoded_segments = [str(seg) for seg in path_segments]
        path = '/'.join(encoded_segments)
        url = f"{url}/{path}"

    # Add query parameters
    if query_params:
        query_string = build_query_string(query_params)
        url = f"{url}?{query_string}"

    # Add fragment
    if fragment:
        url = f"{url}#{quote(fragment)}"

    return url


def build_query_string(params: Dict[str, Any],
                       safe_chars: str = '',
                       array_format: str = 'repeat') -> str:
    """
    Build a query string from parameters with proper encoding.

    Args:
        params: Dictionary of query parameters
        safe_chars: Characters that shouldn't be encoded
        array_format: How to format array values:
                     'repeat' - key=val1&key=val2
                     'brackets' - key[]=val1&key[]=val2
                     'comma' - key=val1,val2

    Returns:
        Encoded query string

    Example:
         params = {"filter": "active", "tags": ["python", "api"]}
         build_query_string(params)
         # Returns: "filter=active&tags=python&tags=api"
    """
    if not params:
        return ""

    query_parts = []

    for key, value in params.items():
        if value is None:
            continue

        if isinstance(value, (list, tuple)):
            # Handle array values based on format
            if array_format == 'repeat':
                for item in value:
                    query_parts.append(f"{key}={quote(str(item), safe=safe_chars)}")
            elif array_format == 'brackets':
                for item in value:
                    query_parts.append(f"{key}[]={quote(str(item), safe=safe_chars)}")
            elif array_format == 'comma':
                items = ','.join(quote(str(item), safe=safe_chars) for item in value)
                query_parts.append(f"{key}={items}")
        elif isinstance(value, bool):
            # Convert boolean to lowercase string
            query_parts.append(f"{key}={str(value).lower()}")
        else:
            query_parts.append(f"{key}={quote(str(value), safe=safe_chars)}")

    return '&'.join(query_parts)


def build_odata_filter(conditions: Dict[str, Any],
                       operator: str = 'and') -> str:
    """
    Build an OData filter string from conditions.

    Args:
        conditions: Dictionary of field conditions
        operator: Logical operator ('and' or 'or')

    Returns:
        OData filter string

    Example:
          conditions = {
        ...     "status": "eq 'active'",
        ...     "amount": "gt 1000",
        ...     "category": "Electronics"
        ... }
         build_odata_filter(conditions)
         # Returns: "status eq 'active' and amount gt 1000 and category eq 'Electronics'"
    """
    if not conditions:
        return ""

    filter_parts = []

    for _field, condition in conditions.items():
        if isinstance(condition, str):
            # Check if condition already has an operator
            if any(op in condition for op in ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains']):
                filter_parts.append(f"{_field} {condition}")
            else:
                # Assume equality and quote string values
                if condition.replace('.', '').replace('-', '').isdigit():
                    # Numeric value
                    filter_parts.append(f"{_field} eq {condition}")
                else:
                    # String value - add quotes
                    filter_parts.append(f"{_field} eq '{condition}'")
        elif isinstance(condition, (int, float)):
            filter_parts.append(f"{_field} eq {condition}")
        elif isinstance(condition, bool):
            filter_parts.append(f"{_field} eq {str(condition).lower()}")
        elif condition is None:
            filter_parts.append(f"{_field} eq null")

    return f" {operator} ".join(filter_parts)


def parse_url(url: str) -> Dict[str, Any]:
    """
    Parse a URL into its components.

    Args:
        url: URL string to parse

    Returns:
        Dictionary with URL components

    Example:
          components = parse_url("https://api.example.com/v2/users?limit=10#section")
         Returns: {
           'scheme': 'https',
           'netloc': 'api.example.com',
           'path': '/v2/users',
           'params': '',
           'query': {'limit': ['10']},
           'fragment': 'section'
         }
    """
    parsed = urlparse(url)
    return {
        'scheme': parsed.scheme,
        'netloc': parsed.netloc,
        'path': parsed.path,
        'params': parsed.params,
        'query': parse_qs(parsed.query),
        'fragment': parsed.fragment
    }


def add_query_params(url: str, params: Dict[str, Any]) -> str:
    """
    Add or update query parameters in a URL.

    Args:
        url: Original URL
        params: Parameters to add or update

    Returns:
        Updated URL

    Example:
        #  url = add_query_params("https://api.example.com/users?page=1",
        ...                       {"limit": 20, "page": 2})
         # Returns: "https://api.example.com/users?page=2&limit=20"
    """
    parsed = urlparse(url)
    query_dict = parse_qs(parsed.query)

    # Update with new params
    for key, value in params.items():
        if value is not None:
            query_dict[key] = [str(value)] if not isinstance(value, list) else value

    # Rebuild query string
    query_string = urlencode(query_dict, doseq=True)

    # Rebuild URL
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        query_string,
        parsed.fragment
    ))


def extract_path_params(url_template: str, url: str) -> Dict[str, str]:
    """
    Extract path parameters from a URL based on a template.

    Args:
        url_template: Template with {param} placeholders
        url: Actual URL to extract from

    Returns:
        Dictionary of extracted parameters

    Example:
        template = "https://api.example.com/v2/users/{user_id}/posts/{post_id}"
        url = "https://api.example.com/v2/users/123/posts/456"
        extract_path_params(template, url)
        # Returns: {'user_id': '123', 'post_id': '456'}
    """
    # Convert template to regex
    pattern = re.escape(url_template)
    pattern = re.sub(r'\\{([^}]+)\\}', r'(?P<\1>[^/]+)', pattern)

    match = re.match(pattern, url)
    if match:
        return match.groupdict()
    return {}


def build_context_string(*components: Any, separator: str = ':') -> str:
    """
    Build a context string for logging from components.

    Args:
        *components: Variable number of components
        separator: Separator between components

    Returns:
        Formatted context string

    Example:
         ctx = build_context_string("prod", "company-123", "user-456")
         # Returns: "[prod:company-123:user-456]"
    """
    # Filter out None values and convert to strings
    parts = [str(c) for c in components if c is not None]

    # Truncate long IDs (like GUIDs)
    truncated_parts = []
    for part in parts:
        if len(part) > 36 and '-' in part:  # Likely a GUID
            truncated_parts.append(part[:8])
        else:
            truncated_parts.append(part)

    return f"[{separator.join(truncated_parts)}]"


def normalize_path(path: str) -> str:
    """
    Normalize a URL path by removing redundant slashes and dots.

    Args:
        path: Path to normalize

    Returns:
        Normalized path

    Example:
         normalize_path("/api//v2/./users/../companies/")
         # Returns: "/api/v2/companies/"
    """
    # Remove multiple slashes
    path = re.sub(r'/+', '/', path)

    # Handle . and .. segments
    segments = []
    for segment in path.split('/'):
        if segment == '..':
            if segments and segments[-1] != '':
                segments.pop()
        elif segment != '.' and segment != '':
            segments.append(segment)

    # Reconstruct path
    normalized = '/'.join(segments)

    # Preserve leading slash
    if path.startswith('/'):
        normalized = '/' + normalized

    # Preserve trailing slash
    if path.endswith('/') and not normalized.endswith('/'):
        normalized += '/'

    return normalized


def join_url_paths(*paths: str) -> str:
    """
    Join URL path segments properly.

    Args:
        *paths: Variable number of path segments

    Returns:
        Joined path with proper slashes

    Example:
         join_url_paths("/api/v2/", "/users/", "123")
         # Returns: "/api/v2/users/123"
    """
    if not paths:
        return ""

    # Start with first path
    result = paths[0]

    # Join remaining paths
    for path in paths[1:]:
        if not path:
            continue

        # Ensure single slash between segments
        if result.endswith('/') and path.startswith('/'):
            result = result + path[1:]
        elif not result.endswith('/') and not path.startswith('/'):
            result = result + '/' + path
        else:
            result = result + path

    return normalize_path(result)