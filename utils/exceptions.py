# utils/exceptions.py
"""
Custom exception hierarchy for TXO Python Template.

Provides specific exception types for different error scenarios,
making error handling more precise and meaningful.
"""

from typing import Optional, Any, Dict
from dataclasses import dataclass


@dataclass
class ErrorContext:
    """
    Structured error context for debugging.

    Attributes:
        operation: What operation was being performed
        resource: What resource was being accessed
        details: Additional error details
    """
    # NOTE: Removed __slots__ because it conflicts with default values
    # If memory optimization is critical, use __init__ instead of dataclass defaults

    operation: Optional[str] = None
    resource: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            k: v for k, v in {
                'operation': self.operation,
                'resource': self.resource,
                'details': self.details
            }.items() if v is not None
        }


class TxoBaseError(Exception):
    """
    Base exception for all TXO template errors.

    Provides common functionality for all custom exceptions.
    """

    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        """
        Initialize base exception.

        Args:
            message: Error message
            context: Optional error context for debugging
        """
        self.context = context or ErrorContext()
        super().__init__(message)

    def __str__(self) -> str:
        """Format exception with context."""
        base_msg = super().__str__()
        if self.context.operation:
            return f"{base_msg} (during {self.context.operation})"
        return base_msg


# API-related exceptions

class ApiError(TxoBaseError):
    """
    Base exception for API-related errors.

    Attributes:
        status_code: HTTP status code if applicable
        response: Raw response object if available
    """

    def __init__(self, message: str,
                 status_code: Optional[int] = None,
                 response: Optional[Any] = None,
                 context: Optional[ErrorContext] = None):
        """
        Initialize API error.

        Args:
            message: Error message
            status_code: HTTP status code
            response: Raw response object
            context: Error context
        """
        super().__init__(message, context)
        self.status_code = status_code
        self.response = response


class ApiOperationError(ApiError):
    """Raised when an API operation fails."""
    pass


class ApiTimeoutError(ApiError):
    """Raised when an API request times out."""

    def __init__(self, message: str = "API request timed out",
                 timeout_seconds: Optional[int] = None, **kwargs):
        """
        Initialize timeout error.

        Args:
            message: Error message
            timeout_seconds: Timeout duration that was exceeded
        """
        if timeout_seconds:
            message = f"{message} after {timeout_seconds} seconds"
        super().__init__(message, status_code=408, **kwargs)


class ApiRateLimitError(ApiError):
    """
    Raised when API rate limit is exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying (if provided by API)
    """

    def __init__(self, message: str = "Rate limit exceeded",
                 retry_after: Optional[int] = None, **kwargs):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retry
        """
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.message = f"{message}. Retry after {retry_after} seconds"


class ApiAuthenticationError(ApiError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        """Initialize authentication error."""
        super().__init__(message, status_code=401, **kwargs)


class ApiNotFoundError(ApiError):
    """Raised when requested resource is not found."""

    def __init__(self, resource: str = "Resource", message: Optional[str] = None, **kwargs):
        """
        Initialize not found error.

        Args:
            resource: Type/name of resource not found
            message: Optional custom message
        """
        if message is None:
            message = f"{resource} not found"
        super().__init__(message, status_code=404, **kwargs)


class ApiValidationError(ApiError):
    """
    Raised when API validation fails.

    Used for 400/422 responses indicating client-side validation errors.
    """

    def __init__(self, message: str = "Validation failed",
                 field: Optional[str] = None,
                 value: Optional[Any] = None, **kwargs):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation
            value: Invalid value
        """
        if field:
            message = f"{message} for field '{field}'"
            if value is not None:
                message = f"{message}: {value}"
        super().__init__(message, status_code=400, **kwargs)
        self.field = field
        self.value = value


class EntityNotFoundError(ApiNotFoundError):
    """
    Raised when a specific entity is not found.

    Specialized version of ApiNotFoundError for entity operations.
    """

    def __init__(self, entity_type: str = "Entity",
                 entity_id: Optional[str] = None, **kwargs):
        """
        Initialize entity not found error.

        Args:
            entity_type: Type of entity
            entity_id: ID of the missing entity
        """
        if entity_id:
            resource = f"{entity_type} with ID '{entity_id}'"
        else:
            resource = entity_type
        super().__init__(resource=resource, **kwargs)
        self.entity_type = entity_type
        self.entity_id = entity_id


# Configuration and validation exceptions

class ConfigurationError(TxoBaseError):
    """
    Raised when configuration is invalid or missing.

    Attributes:
        config_key: Specific configuration key that caused the error
    """

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        """
        Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused error
        """
        super().__init__(message, **kwargs)
        self.config_key = config_key
        if config_key:
            self.message = f"{message} (key: {config_key})"


class ValidationError(TxoBaseError):
    """
    Raised when data validation fails.

    Attributes:
        field: Field that failed validation
        value: Value that was invalid
    """

    def __init__(self, message: str,
                 field: Optional[str] = None,
                 value: Optional[Any] = None, **kwargs):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation
            value: Invalid value
        """
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


# File operation exceptions

class FileOperationError(TxoBaseError):
    """
    Raised when file operations fail.

    Attributes:
        file_path: Path to the file that caused the error
        operation: Type of operation (read, write, delete)
    """

    def __init__(self, message: str,
                 file_path: Optional[str] = None,
                 operation: Optional[str] = None, **kwargs):
        """
        Initialize file operation error.

        Args:
            message: Error message
            file_path: Path to problematic file
            operation: Operation that failed
        """
        super().__init__(message, **kwargs)
        self.file_path = file_path
        self.operation = operation


# Helpful error with instructions

class HelpfulError(TxoBaseError):
    """
    Exception that provides helpful instructions to fix the problem.

    Used for user-friendly error messages with solutions.
    """

    def __init__(self, what_went_wrong: str,
                 how_to_fix: str,
                 example: Optional[str] = None):
        """
        Initialize helpful error.

        Args:
            what_went_wrong: Description of the problem
            how_to_fix: Instructions to fix it
            example: Optional example of correct usage
        """
        message = f"\n❌ Problem: {what_went_wrong}\n\n✅ Solution: {how_to_fix}"
        if example:
            message += f"\n\n📝 Example:\n{example}"
        super().__init__(message)
        self.what_went_wrong = what_went_wrong
        self.how_to_fix = how_to_fix
        self.example = example