# utils/logger.py
"""
Thread-safe singleton logger with MANDATORY token redaction.

This module provides centralized logging with:
- MANDATORY token/secret redaction patterns from config file
- MANDATORY logging configuration from config file
- Hard fail if either configuration is missing or invalid
- UTC timestamps by default
- Quiet on success, verbose on failure
- Thread-safe singleton pattern

SECURITY: This logger will FAIL to start if configurations are not properly set.
No defaults, no fallbacks - configuration is mandatory.
"""

import logging
import logging.config
import json
import os
import re
import sys
import time
import threading
from datetime import datetime
from typing import List, Tuple, Dict, Any

from utils.path_helpers import get_path


class TokenRedactionFilter(logging.Filter):
    """
    Filter that redacts tokens and secrets from log messages.

    STRICT MODE: Fails hard if patterns file is missing or invalid.
    No fallback patterns - configuration is mandatory.
    """

    def __init__(self):
        super().__init__()
        self.config_path = get_path('config', 'log-redaction-patterns.json')

        # Load and validate configuration - will exit(1) on any failure
        config = self._load_and_validate_config()

        # Load patterns - will exit(1) on any failure
        self.patterns = self._load_regex_patterns(config)
        self.simple_patterns = self._load_simple_patterns(config)

        # Final validation - must have at least some patterns
        total_patterns = len(self.patterns) + len(self.simple_patterns)
        if total_patterns == 0:
            self._fail("No redaction patterns loaded! At least one pattern is required.")

        # Success - stay quiet unless DEBUG mode
        if os.getenv('DEBUG_LOGGING'):
            print(f"[DEBUG] Loaded {total_patterns} redaction patterns "
                  f"({len(self.patterns)} regex, {len(self.simple_patterns)} simple)",
                  file=sys.stderr)

    def _fail(self, message: str) -> None:
        """Print error and exit with code 1."""
        error_msg = (
            f"\n{'=' * 60}\n"
            f"CRITICAL SECURITY ERROR\n"
            f"{message}\n"
            f"File: {self.config_path}\n"
            f"{'=' * 60}"
        )
        print(error_msg, file=sys.stderr)
        sys.exit(1)

    def _load_and_validate_config(self) -> Dict[str, Any]:
        """
        Load and validate the configuration file.
        Hard fails on any error.
        """
        # Check file exists
        if not self.config_path.exists():
            self._fail(
                f"Redaction patterns file not found!\n"
                f"Create this file to define security redaction patterns."
            )

        # Load JSON
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self._fail(f"Invalid JSON in redaction patterns!\nError: {e}")
        except Exception as e:
            self._fail(f"Failed to read redaction patterns!\nError: {e}")

        # Validate top-level structure
        if not isinstance(config, dict):
            self._fail("Configuration must be a JSON object (not array or scalar)")

        if 'redaction-patterns' not in config:
            self._fail(
                "Invalid configuration structure!\n"
                "Missing required top-level key: 'redaction-patterns'"
            )

        if not isinstance(config['redaction-patterns'], dict):
            self._fail("'redaction-patterns' must be an object")

        return config

    def _load_regex_patterns(self, config: Dict[str, Any]) -> List[Tuple[re.Pattern, str]]:
        """
        Load regex patterns with strict validation.
        Hard fails on any error. Quiet on success.
        """
        patterns = []

        # Check for patterns key
        if 'patterns' not in config['redaction-patterns']:
            self._fail(
                "Missing required key: 'redaction-patterns.patterns'\n"
                "This array must contain regex pattern definitions."
            )

        pattern_list = config['redaction-patterns']['patterns']

        # Validate it's an array
        if not isinstance(pattern_list, list):
            self._fail("'redaction-patterns.patterns' must be an array")

        # Process each pattern
        for idx, pattern_def in enumerate(pattern_list):
            # Validate pattern structure
            if not isinstance(pattern_def, dict):
                self._fail(f"Pattern at index {idx} must be an object")

            # Require 'name' field
            if 'name' not in pattern_def:
                self._fail(f"Pattern at index {idx} missing required 'name' field")

            name = pattern_def['name']

            # Require 'pattern' field
            if 'pattern' not in pattern_def:
                self._fail(f"Pattern '{name}' missing required 'pattern' field")

            # Require 'replacement' field
            if 'replacement' not in pattern_def:
                self._fail(f"Pattern '{name}' missing required 'replacement' field")

            pattern_str = pattern_def['pattern']
            replacement = pattern_def['replacement']

            # Validate types
            if not isinstance(pattern_str, str):
                self._fail(f"Pattern '{name}' field 'pattern' must be a string")

            if not isinstance(replacement, str):
                self._fail(f"Pattern '{name}' field 'replacement' must be a string")

            # Compile regex pattern
            try:
                compiled = re.compile(pattern_str, re.IGNORECASE)
                patterns.append((compiled, replacement))
                # Quiet on success - don't print each pattern
                if os.getenv('DEBUG_LOGGING'):
                    print(f"[DEBUG]   Loaded regex: {name}", file=sys.stderr)
            except re.error as e:
                self._fail(
                    f"Invalid regex in pattern '{name}'\n"
                    f"Regex: {pattern_str}\n"
                    f"Error: {e}"
                )
            except Exception as e:
                self._fail(f"Failed to compile pattern '{name}': {e}")

        return patterns

    def _load_simple_patterns(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Load simple patterns. These are optional but strictly validated if present.
        Quiet on success.
        """
        simple_patterns = []

        # Simple patterns are optional
        if 'simple-patterns' not in config['redaction-patterns']:
            return simple_patterns

        simple_list = config['redaction-patterns']['simple-patterns']

        # Validate it's an array
        if not isinstance(simple_list, list):
            self._fail("'redaction-patterns.simple-patterns' must be an array")

        # Process each simple pattern
        for idx, pattern_def in enumerate(simple_list):
            # Validate pattern structure
            if not isinstance(pattern_def, dict):
                self._fail(f"Simple pattern at index {idx} must be an object")

            # Require 'name' field
            if 'name' not in pattern_def:
                self._fail(f"Simple pattern at index {idx} missing required 'name' field")

            name = pattern_def['name']

            # Require 'contains' field
            if 'contains' not in pattern_def:
                self._fail(f"Simple pattern '{name}' missing required 'contains' field")

            # Require 'replacement' field
            if 'replacement' not in pattern_def:
                self._fail(f"Simple pattern '{name}' missing required 'replacement' field")

            contains = pattern_def['contains']
            replacement = pattern_def['replacement']

            # Validate types
            if not isinstance(contains, list):
                self._fail(f"Simple pattern '{name}' field 'contains' must be an array")

            if not isinstance(replacement, str):
                self._fail(f"Simple pattern '{name}' field 'replacement' must be a string")

            if len(contains) == 0:
                self._fail(f"Simple pattern '{name}' field 'contains' cannot be empty")

            # Validate each keyword
            for keyword in contains:
                if not isinstance(keyword, str):
                    self._fail(f"Simple pattern '{name}' contains non-string keyword: {keyword}")
                if not keyword:
                    self._fail(f"Simple pattern '{name}' contains empty keyword")

            simple_patterns.append({
                'name': name,
                'contains': contains,
                'replacement': replacement
            })

            # Quiet on success
            if os.getenv('DEBUG_LOGGING'):
                print(f"[DEBUG]   Loaded simple: {name}", file=sys.stderr)

        return simple_patterns

    def _apply_simple_patterns(self, text: str) -> str:
        """Apply simple string-based redaction patterns."""
        for pattern in self.simple_patterns:
            for keyword in pattern['contains']:
                # Case-insensitive search for keyword
                if keyword.lower() in text.lower():
                    # Build regex that captures keyword and value
                    escaped_keyword = re.escape(keyword)
                    # Match keyword and everything after until delimiter
                    # Delimiters: space, semicolon, quote, ampersand, comma, newline, or end
                    regex = f"({escaped_keyword})([^\\s;\"'&,}}\\n]*)"

                    # Replace with keyword + replacement
                    text = re.sub(regex,
                                  f"\\1{pattern['replacement']}",
                                  text,
                                  flags=re.IGNORECASE)

        return text

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive information from log record."""
        # Process main message
        if hasattr(record, 'msg'):
            msg = str(record.msg)

            # Apply regex patterns
            for pattern, replacement in self.patterns:
                msg = pattern.sub(replacement, msg)

            # Apply simple patterns
            msg = self._apply_simple_patterns(msg)

            record.msg = msg

        # Process arguments
        if hasattr(record, 'args') and record.args:
            cleaned_args = []
            for arg in record.args:
                arg_str = str(arg)

                # Apply regex patterns
                for pattern, replacement in self.patterns:
                    arg_str = pattern.sub(replacement, arg_str)

                # Apply simple patterns
                arg_str = self._apply_simple_patterns(arg_str)

                cleaned_args.append(arg_str)
            record.args = tuple(cleaned_args)

        return True


class UTCFormatter(logging.Formatter):
    """Formatter that uses UTC timestamps."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force UTC timestamps
        self.converter = time.gmtime

    def formatTime(self, record, datefmt=None):
        """Override to use UTC."""
        return super().formatTime(record, datefmt)


class TxoLogger:
    """
    Thread-safe singleton logger for the application.

    Features:
    - MANDATORY token redaction from JSON file (no defaults)
    - MANDATORY logging configuration from JSON file (no defaults)
    - UTC timestamps
    - Hard fail if configuration is missing
    - Quiet on success, verbose on failure
    - Thread-safe singleton pattern

    SECURITY: Will exit(1) if either configuration is not properly set.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure only one instance exists."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize logger if not already initialized."""
        with self._lock:
            if not self._initialized:
                # Debug mode check
                debug_mode = os.getenv('DEBUG_LOGGING')

                if debug_mode:
                    print("[DEBUG] Initializing TxoLogger...", file=sys.stderr)

                # Create base logger
                self.logger = logging.getLogger('TxoApp')

                # Create token filter - will exit(1) if config missing/invalid
                try:
                    self.token_filter = TokenRedactionFilter()
                except SystemExit:
                    # Re-raise to ensure exit
                    raise
                except Exception as e:
                    # Unexpected error - still fail hard
                    print(f"\n{'=' * 60}", file=sys.stderr)
                    print(f"UNEXPECTED ERROR initializing security: {e}", file=sys.stderr)
                    print(f"{'=' * 60}\n", file=sys.stderr)
                    sys.exit(1)

                # Setup logging configuration - will exit(1) if config missing/invalid
                self._setup_logger()
                self._initialized = True

                # Log initialization only at DEBUG level
                self.logger.debug("TxoLogger initialized successfully")
                self.logger.debug(f"Loaded {len(self.token_filter.patterns)} regex patterns, "
                                  f"{len(self.token_filter.simple_patterns)} simple patterns")

    def _setup_logger(self) -> None:
        """
        Set up logger from MANDATORY configuration file.

        HARD FAILS if logging-config.json is missing or invalid.
        No defaults, no fallbacks - configuration is mandatory.
        Quiet on success, verbose on failure.
        """
        config_path = get_path('config', 'logging-config.json')

        # Check file exists
        if not config_path.exists():
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"Logging configuration file not found!\n"
                f"Expected: {config_path}\n"
                f"Create this file to define logging configuration.\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Load and parse JSON
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"Invalid JSON in logging configuration!\n"
                f"File: {config_path}\n"
                f"Error: {e}\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"Failed to read logging configuration!\n"
                f"File: {config_path}\n"
                f"Error: {e}\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Validate required structure
        if not isinstance(config, dict):
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"Logging config must be a JSON object!\n"
                f"File: {config_path}\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Check for required sections
        required_sections = ['formatters', 'handlers', 'loggers']
        missing_sections = [s for s in required_sections if s not in config]

        if missing_sections:
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"Missing required sections in logging config!\n"
                f"Missing: {', '.join(missing_sections)}\n"
                f"File: {config_path}\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Check TxoApp logger is configured - hard-fail if loggers section missing
        if 'TxoApp' not in config['loggers']:
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"'TxoApp' logger not configured!\n"
                f"Add 'TxoApp' to the 'loggers' section.\n"
                f"File: {config_path}\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Apply runtime modifications
        try:
            # 1. Dynamic log file path (computed at runtime)
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_filename = f"app_{date_str}.log"
            log_path = str(get_path('logs', log_filename))

            # Update all file handlers with dynamic path
            if 'handlers' in config:
                for handler_name, handler_config in config['handlers'].items():
                    if handler_config['class'].endswith('FileHandler'):  # Hard-fail if missing
                        handler_config['filename'] = log_path
                        if os.getenv('DEBUG_LOGGING'):
                            print(f"[DEBUG] Set {handler_name} path to {log_path}", file=sys.stderr)

            # 2. Force UTC formatter
            if 'formatters' in config:
                for formatter_name in config['formatters']:
                    config['formatters'][formatter_name]['()'] = UTCFormatter
                    if os.getenv('DEBUG_LOGGING'):
                        print(f"[DEBUG] Set {formatter_name} to UTC", file=sys.stderr)

            # Apply configuration
            logging.config.dictConfig(config)

            # Get our logger
            self.logger = logging.getLogger('TxoApp')

            # Success - stay quiet unless debug mode
            if os.getenv('DEBUG_LOGGING'):
                print(f"[DEBUG] Logging configured from {config_path}", file=sys.stderr)

        except Exception as e:
            error_msg = (
                f"\n{'=' * 60}\n"
                f"CRITICAL CONFIGURATION ERROR\n"
                f"Failed to apply logging configuration!\n"
                f"Error: {e}\n"
                f"File: {config_path}\n"
                f"{'=' * 60}"
            )
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Add token redaction filter to everything
        self.logger.addFilter(self.token_filter)

        # Also add to root logger to catch ALL logs
        root_logger = logging.getLogger()
        root_logger.addFilter(self.token_filter)

        if os.getenv('DEBUG_LOGGING'):
            print("[DEBUG] Token redaction filter applied to all loggers", file=sys.stderr)

    def reload_redaction_patterns(self) -> None:
        """
        Reload redaction patterns from config file.

        Will exit(1) if patterns cannot be reloaded.
        """
        with self._lock:
            self.logger.info("Reloading redaction patterns...")

            # Remove old filter
            self.logger.removeFilter(self.token_filter)
            root_logger = logging.getLogger()
            root_logger.removeFilter(self.token_filter)

            # Create new filter with reloaded patterns
            # This will exit(1) if config is now invalid
            try:
                self.token_filter = TokenRedactionFilter()
            except SystemExit:
                print("\nFAILED TO RELOAD - APPLICATION WILL EXIT", file=sys.stderr)
                raise

            # Add new filter
            self.logger.addFilter(self.token_filter)
            root_logger.addFilter(self.token_filter)

            self.logger.info(f"Successfully reloaded redaction patterns: "
                             f"{len(self.token_filter.patterns)} regex, "
                             f"{len(self.token_filter.simple_patterns)} simple")

    # Logging methods
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message with redaction."""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message with redaction."""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message with redaction."""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message with redaction."""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message with redaction."""
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback and redaction."""
        self.logger.exception(msg, *args, **kwargs)


def setup_logger() -> TxoLogger:
    """
    Get configured logger instance.

    WILL EXIT(1) if:
    - log-redaction-patterns.json is missing or invalid
    - logging-config.json is missing or invalid

    Security and configuration are mandatory - no defaults, no fallbacks.

    Returns:
        Configured TxoLogger instance

    Raises:
        SystemExit: If any configuration is missing or invalid

    Example:
        >>> logger = setup_logger()  # Will exit(1) if not configured
        >>> ctx = "[prod:company123]"
        >>> logger.info(f"{ctx} Processing started")

    Debug Mode:
        Set DEBUG_LOGGING=1 environment variable to see initialization details:
        $ DEBUG_LOGGING=1 python your_script.py
    """
    try:
        return TxoLogger()
    except SystemExit:
        # Ensure we exit even if called in a try/except
        print("\nCONFIGURATION REQUIRED - CANNOT CONTINUE", file=sys.stderr)
        sys.exit(1)