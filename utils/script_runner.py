# utils/script_runner.py
"""
Enhanced script runner utilities with v2.1 best practices.

Provides robust script initialization with:
- MANDATORY configuration files (can use example templates)
- OPTIONAL OAuth token acquisition (off by default)
- Configuration validation
- Hard-fail philosophy
- Clear, actionable error messages

Philosophy:
- Every script requires config files (enforces consistency)
- Config can be minimal (copy from templates)
- Token is optional for most scripts
"""

import argparse
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from utils.oauth_helpers import OAuthClient
from utils.exceptions import HelpfulError, ConfigurationError, ValidationError

# Module logger - no org_id injection
logger = setup_logger()


@dataclass
class ArgumentDefinition:
    """Definition for a command-line argument."""
    name: str
    type: type = str
    help: str = ""
    default: Any = None
    choices: Optional[List[Any]] = None
    required: bool = True
    action: Optional[str] = None


class ScriptRunner:
    """Enhanced script runner with configuration management."""

    def __init__(self, description: str, require_token: bool = False):
        """
        Initialize script runner.

        Args:
            description: Script description for help text
            require_token: Whether to acquire OAuth token (default: False)
        """
        self.description = description
        self.require_token = require_token
        self.oauth_client: Optional[OAuthClient] = None

    def parse_arguments(self, extra_args: Optional[List[ArgumentDefinition]] = None) -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        # Required arguments - always needed
        parser.add_argument("org_id", help="Organization ID (e.g., 'txo')")
        parser.add_argument("env_type", help="Environment type (e.g., 'test', 'prod')")

        # Add extra arguments if provided
        if extra_args:
            for arg_def in extra_args:
                kwargs: Dict[str, Any] = {"help": arg_def.help}

                # Handle optional vs required
                if arg_def.default is not None or not arg_def.required:
                    arg_name = f"--{arg_def.name.replace('_', '-')}"
                    kwargs["default"] = arg_def.default
                    kwargs["required"] = arg_def.required
                else:
                    arg_name = arg_def.name

                if not arg_def.action:
                    kwargs["type"] = arg_def.type
                else:
                    kwargs["action"] = arg_def.action

                if arg_def.choices:
                    kwargs["choices"] = arg_def.choices

                parser.add_argument(arg_name, **kwargs)

        return parser.parse_args()

    def load_configuration(self, org_id: str, env_type: str) -> Dict[str, Any]:
        """
        Load and validate configuration.

        ALWAYS requires config files - no escape hatch!
        Files can be minimal (copied from templates).

        Args:
            org_id: Organization identifier
            env_type: Environment type

        Returns:
            Configuration dictionary with injected fields

        Raises:
            HelpfulError: If configuration loading fails
        """
        logger.info(f"Starting {self.description}")
        logger.info(f"Configuration: {org_id}-{env_type}")

        try:
            # Load configuration - ALWAYS validate structure
            config_loader = ConfigLoader(org_id, env_type)
            config = config_loader.load_config(
                validate=True,  # Always validate structure
                include_secrets=True
            )

            # Check if using minimal/example config - hard-fail if global section missing
            global_section = config["global"]  # Hard-fail if missing
            if not global_section.get("tenant-id") and not global_section.get("client-id"):
                logger.debug("Using configuration without OAuth settings (suitable for local scripts)")

        except HelpfulError:
            raise  # Already formatted nicely
        except (ConfigurationError, ValidationError) as e:
            # Convert config/validation errors to user-friendly format
            raise HelpfulError(
                what_went_wrong=f"Configuration validation failed: {e}",
                how_to_fix=(
                    f"Check your configuration files:\n"
                    f"  1. Verify config/{org_id}-{env_type}-config.json exists and is valid JSON\n"
                    f"  2. Check schema compliance (copy from examples if needed)\n"
                    f"  3. Verify all required fields are present"
                ),
                example=f"cp config/org-env-config_example.json config/{org_id}-{env_type}-config.json"
            ) from e
        except FileNotFoundError:
            raise HelpfulError(
                what_went_wrong=f"Configuration file not found for {org_id}-{env_type}",
                how_to_fix=(
                    f"Create config files:\n"
                    f"  1. cp config/org-env-config_example.json config/{org_id}-{env_type}-config.json\n"
                    f"  2. cp config/org-env-config-secrets_example.json config/{org_id}-{env_type}-config-secrets.json\n"
                    f"  3. Edit the files as needed (can leave as-is for simple scripts)"
                ),
                example="For a simple script, the example config works as-is"
            )
        except Exception as e:
            raise HelpfulError(
                what_went_wrong=f"Configuration error: {e}",
                how_to_fix="Check your config file is valid JSON and matches the schema",
                example=f"Validate against schemas/org-env-config-schema.json"
            )

        # Inject standard fields (always present)
        config["_org_id"] = org_id
        config["_env_type"] = env_type

        return config

    def acquire_token(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Acquire OAuth token if required.

        Args:
            config: Configuration dictionary

        Returns:
            Token string or None

        Raises:
            HelpfulError: If token acquisition fails
        """
        if not self.require_token:
            logger.debug("Token acquisition not required for this script")
            return None

        logger.info("Acquiring OAuth token...")

        try:
            # Check for fallback token first
            fallback_token = config.get("_az_token")
            if fallback_token:
                logger.info("Using fallback token from secrets")
                return fallback_token

            # Extract OAuth config (hard-fail if missing when required)
            global_config = config["global"]  # Hard-fail if missing

            tenant_id = global_config.get("tenant-id")
            client_id = global_config.get("client-id")
            oauth_scope = global_config.get("oauth-scope")
            client_secret = config.get("_client_secret")  # From secrets

            # Check if OAuth is configured
            if not all([tenant_id, client_id, oauth_scope, client_secret]):
                missing = []
                if not tenant_id:
                    missing.append("tenant-id")
                if not client_id:
                    missing.append("client-id")
                if not oauth_scope:
                    missing.append("oauth-scope")
                if not client_secret:
                    missing.append("client-secret (in secrets file)")

                raise HelpfulError(
                    what_went_wrong=f"Token required but OAuth config incomplete. Missing: {', '.join(missing)}",
                    how_to_fix=(
                        "Either:\n"
                        "  1. Add OAuth settings to your config file (global section)\n"
                        "  2. Add 'az-token' to your secrets file as fallback\n"
                        "  3. If token not needed, use require_token=False"
                    ),
                    example=(
                        "In config: \"global\": {\"tenant-id\": \"...\", \"client-id\": \"...\", \"oauth-scope\": \"...\"}\n"
                        "In secrets: {\"client-secret\": \"...\", \"az-token\": \"fallback-token-here\"}"
                    )
                )

            if not self.oauth_client:
                self.oauth_client = OAuthClient(tenant_id=tenant_id, cache_tokens=True)

            token = self.oauth_client.get_client_credentials_token(
                client_id=client_id,
                client_secret=client_secret,
                scope=oauth_scope,
                tenant_id=tenant_id
            )

            logger.info("✅ Token acquired successfully")
            return token

        except HelpfulError:
            raise  # Re-raise with helpful context
        except Exception as e:
            raise HelpfulError(
                what_went_wrong=f"Token acquisition failed: {e}",
                how_to_fix="Check OAuth configuration or add fallback token",
                example="Verify client-id, client-secret, and tenant-id are correct"
            )

    def run(self, extra_args: Optional[List[ArgumentDefinition]] = None) -> Dict[str, Any]:
        """
        Main entry point - parse args, load config, optionally get token.

        Args:
            extra_args: Optional additional arguments

        Returns:
            Complete configuration dictionary
        """
        # Parse arguments
        args = self.parse_arguments(extra_args)

        # Load configuration (always required)
        config = self.load_configuration(args.org_id, args.env_type)

        # Inject extra arguments if provided
        if extra_args:
            for arg_def in extra_args:
                attr_name = arg_def.name.replace('-', '_')
                if hasattr(args, attr_name):
                    config[f"_{attr_name}"] = getattr(args, attr_name)

        # Acquire token only if required
        if self.require_token:
            token = self.acquire_token(config)
            config["_token"] = token
        else:
            config["_token"] = None

        return config


def parse_args_and_load_config(description: str,
                               require_token: bool = False) -> Dict[str, Any]:
    """
    Parse arguments and load configuration - standard entry point.

    ALWAYS requires configuration files (can use example templates).
    Token is OPTIONAL by default (most scripts don't need it).

    Args:
        description: Script description
        require_token: Whether to acquire OAuth token (default: False)

    Returns:
        Configuration dictionary with injected fields:
        - _org_id: Organization ID from command line
        - _env_type: Environment type from command line
        - _token: OAuth token (if require_token=True) or None
        - All config fields from JSON files

    Example:
        # Simple script (no token needed):
        config = parse_args_and_load_config("My local script")

        # API script (token required):
        config = parse_args_and_load_config("BC sync script", require_token=True)
    """
    try:
        runner = ScriptRunner(description, require_token)
        return runner.run()

    except HelpfulError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def parse_custom_args_and_load_config(description: str,
                                      custom_args: Optional[List[ArgumentDefinition]] = None,
                                      require_token: bool = False) -> Dict[str, Any]:
    """
    Parse arguments with custom additions and load configuration.

    ALWAYS requires configuration files.
    Token is OPTIONAL by default.

    Args:
        description: Script description
        custom_args: Additional argument definitions
        require_token: Whether to acquire OAuth token (default: False)

    Returns:
        Configuration dictionary with all injected fields

    Example:
        custom_args = [
            ArgumentDefinition("input_file", type=str, help="Input file path"),
            ArgumentDefinition("--verbose", action="store_true", help="Verbose output")
        ]
        config = parse_custom_args_and_load_config("My script", custom_args)
    """
    try:
        runner = ScriptRunner(description, require_token)
        return runner.run(extra_args=custom_args)

    except HelpfulError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)