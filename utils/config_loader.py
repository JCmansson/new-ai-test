# utils/config_loader.py
"""
Enhanced ConfigLoader with validation, caching, and thread safety.

Handles configuration and secrets with:
- JSON Schema validation
- Automatic secrets injection with underscore prefix
- Thread-safe singleton pattern
- Memory-efficient caching
"""
import jsonschema
import threading
from typing import Dict, Any, Optional
from weakref import WeakValueDictionary

from utils.exceptions import ConfigurationError, ValidationError, ErrorContext

from utils.logger import setup_logger
from utils.load_n_save import TxoDataHandler
from utils.exceptions import HelpfulError

logger = setup_logger()
data_handler = TxoDataHandler()

# Thread-safe cache for ConfigLoader instances
_loader_cache: WeakValueDictionary = WeakValueDictionary()
_cache_lock = threading.Lock()


class ConfigLoader:
    """
    Configuration loader with validation and caching.

    Features:
    - JSON Schema validation
    - Automatic secrets injection
    - Lazy loading and caching
    - Thread-safe operations
    - Memory-efficient design
    """

    # Memory optimization with __slots__
    __slots__ = ['org_id', 'env_type', '_config', '_secrets', '_lock']

    def __init__(self, org_id: str, env_type: str) -> None:
        """
        Initialize the ConfigLoader with organization and environment details.

        Args:
            org_id: The organization identifier (e.g., "txo")
            env_type: The environment type (e.g., "test", "prod")
        """
        self.org_id = org_id
        self.env_type = env_type
        self._config: Optional[Dict[str, Any]] = None  # Cache for config
        self._secrets: Optional[Dict[str, Any]] = None  # Cache for secrets
        self._lock = threading.Lock()  # Instance-level lock for thread safety

    @property
    def config_filename(self) -> str:
        """Get the configuration filename for this org and environment."""
        return f"{self.org_id}-{self.env_type}-config.json"

    @property
    def secrets_filename(self) -> str:
        """Get the secrets filename for this org and environment."""
        return f"{self.org_id}-{self.env_type}-config-secrets.json"

    def _load_secrets(self) -> Dict[str, Any]:
        """
        Load flat key-value secrets file.

        Secrets must be a flat dictionary (no nested structures).

        Returns:
            Dictionary of secrets, or empty dict if file not found

        Raises:
            ValueError: If secrets contain nested structures
        """
        try:
            secrets = data_handler.load_json('config', self.secrets_filename)

            # Validate flat structure
            for key, value in secrets.items():
                if isinstance(value, (dict, list)):
                    raise ValueError(
                        f"Secrets must be flat key-value pairs. "
                        f"Found complex value at key '{key}'"
                    )

            logger.info(f"Loaded secrets: {self.secrets_filename}")
            return secrets

        except FileNotFoundError:
            logger.debug(f"No secrets file found: {self.secrets_filename}")
            return {}
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error loading secrets: {e}")
            raise

    @staticmethod
    def _inject_secrets(config: Dict[str, Any], secrets: Dict[str, Any]) -> None:
        """
        Inject flat secrets into config with underscore prefix.

        Converts kebab-case to snake_case:
        "client-secret" → "_client_secret"

        Args:
            config: Configuration dictionary to inject into
            secrets: Flat secrets dictionary
        """
        for key, value in secrets.items():
            # Convert kebab-case to snake_case with underscore prefix
            new_key = "_" + key.replace("-", "_")
            config[new_key] = value
            logger.debug(f"Injected secret key: {new_key}")

    def validate_schema(self, data: Dict[str, Any], schema_filename: str) -> None:
        """
        Validate data against the specified JSON schema.

        Args:
            data: Data to validate
            schema_filename: Name of schema file in schemas/ directory

        Raises:
            SystemExit: If schema file not found or validation fails
        """
        logger.debug(f"Starting schema validation: {schema_filename} for "
                     f"{self.org_id}-{self.env_type}")

        try:
            schema = data_handler.load_json('schemas', schema_filename)
        except FileNotFoundError as e:
            logger.error(f"❌ CRITICAL: Schema file not found: {schema_filename}")
            logger.error(f"Script cannot continue without schema validation: {e}")
            raise ConfigurationError(
                f"Schema file not found: {schema_filename}",
                context=ErrorContext(
                    operation="schema_validation",
                    resource=schema_filename,
                    details={"org_id": self.org_id, "env_type": self.env_type}
                )
            ) from e

        # Perform validation
        try:
            jsonschema.validate(instance=data, schema=schema)
            logger.info(f"✅ Schema validation successful: {schema_filename} for "
                        f"{self.org_id}-{self.env_type}")

        except jsonschema.ValidationError as e:
            # Handle validation errors
            error_path = " > ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            logger.error(
                f"❌ CRITICAL: Schema validation failed for {self.org_id}-{self.env_type}: "
                f"Error at '{error_path}' - {e.message}"
            )
            logger.error(f"Schema file: {schema_filename}")
            logger.error("Script cannot continue with invalid configuration.")
            raise ValidationError(
                f"Schema validation failed at '{error_path}': {e.message}",
                context=ErrorContext(
                    operation="schema_validation",
                    resource=f"{self.org_id}-{self.env_type}-config.json",
                    details={
                        "schema_file": schema_filename,
                        "error_path": error_path,
                        "validation_message": e.message
                    }
                )
            ) from e

        except Exception as e:
            logger.error(f"❌ CRITICAL: Unexpected error during schema validation: {e}")
            raise ConfigurationError(
                f"Unexpected error during schema validation: {e}",
                context=ErrorContext(
                    operation="schema_validation",
                    resource=f"{self.org_id}-{self.env_type}-config.json",
                    details={"schema_file": schema_filename}
                )
            ) from e

    def load_config(self, validate: bool = True,
                    include_secrets: bool = True,
                    force_reload: bool = False) -> Dict[str, Any]:
        """
        Load the main configuration with optional secrets injection.

        Thread-safe loading with caching support.

        Args:
            validate: Whether to validate against schema (default: True)
            include_secrets: Whether to load and inject secrets (default: True)
            force_reload: Force reload even if cached (default: False)

        Returns:
            The configuration dictionary with injected secrets

        Raises:
            HelpfulError: If the config file is missing
            ValueError: If secrets are not flat
            SystemExit: If validation fails
        """
        with self._lock:
            # Return cached config if available and not forcing reload
            if self._config is not None and not force_reload:
                logger.debug(f"Returning cached config for {self.org_id}-{self.env_type}")
                return self._config

            try:
                # Load main configuration
                self._config = data_handler.load_json('config', self.config_filename)
                logger.info(f"Loaded config: {self.config_filename}")

                # Validate against schema if requested
                if validate:
                    self.validate_schema(self._config, 'org-env-config-schema.json')

                # Load and inject secrets if requested
                if include_secrets:
                    self._secrets = self._load_secrets()
                    if self._secrets:
                        self._inject_secrets(self._config, self._secrets)
                        logger.debug(f"Injected {len(self._secrets)} secrets into config")

                return self._config

            except FileNotFoundError:
                raise HelpfulError(
                    what_went_wrong=f"Configuration file '{self.config_filename}' not found in config/ directory",
                    how_to_fix=f"Create the file 'config/{self.config_filename}' with your configuration",
                    example="""Example minimal config:
{
  "global": {
    "api-base-url": "https://api.example.com",
    "api-version": "v2",
    "timeout-seconds": 30
  },
  "script-behavior": {
    "api-delay-seconds": 1
  }
}"""
                )
            except HelpfulError:
                # Re-raise HelpfulError as-is
                raise
            except Exception as e:
                # Log unexpected errors and re-raise
                logger.error(f"Unexpected error loading config: {e}")
                raise

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a specific value from the configuration.

        Loads config if not already loaded.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if self._config is None:
            self.load_config()

        return self._config.get(key, default)

    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get a specific secret value.

        Loads secrets if not already loaded.

        Args:
            key: Secret key to retrieve (without underscore prefix)
            default: Default value if key not found

        Returns:
            Secret value or default
        """
        if self._secrets is None:
            self._secrets = self._load_secrets()

        return self._secrets.get(key, default)

    def clear_cache(self) -> None:
        """Clear cached configuration and secrets data."""
        with self._lock:
            self._config = None
            self._secrets = None
            logger.debug(f"Cleared cache for {self.org_id}-{self.env_type}")

    def reload(self, validate: bool = True, include_secrets: bool = True) -> Dict[str, Any]:
        """
        Force reload configuration and secrets.

        Args:
            validate: Whether to validate against schema
            include_secrets: Whether to load and inject secrets

        Returns:
            The reloaded configuration dictionary
        """
        self.clear_cache()
        return self.load_config(validate=validate, include_secrets=include_secrets)

    def __repr__(self) -> str:
        """String representation of ConfigLoader."""
        return f"ConfigLoader(org_id='{self.org_id}', env_type='{self.env_type}')"


def get_config_loader(org_id: str, env_type: str,
                      use_cache: bool = True) -> ConfigLoader:
    """
    Get or create a ConfigLoader instance.

    Uses caching to avoid creating multiple loaders for the same org/env.

    Args:
        org_id: Organization identifier
        env_type: Environment type
        use_cache: Whether to use cached instance if available

    Returns:
        ConfigLoader instance

    Example:
         loader = get_config_loader("txo", "prod")
         config = loader.load_config()
    """
    if not use_cache:
        return ConfigLoader(org_id, env_type)

    cache_key = f"{org_id}_{env_type}"

    with _cache_lock:
        if cache_key in _loader_cache:
            logger.debug(f"Returning cached ConfigLoader for {cache_key}")
            return _loader_cache[cache_key]

        loader = ConfigLoader(org_id, env_type)
        _loader_cache[cache_key] = loader
        logger.debug(f"Created and cached ConfigLoader for {cache_key}")
        return loader


class ConfigContext:
    """
    Context manager for configuration loading.

    Ensures configuration is loaded and optionally validated.

    Example:
         with ConfigContext("txo", "prod") as config:
        ...     api_url = config['global']['api-base-url']
        ...     token = config['_client_secret']  # From injected secrets
    """

    def __init__(self, org_id: str, env_type: str,
                 validate: bool = True,
                 include_secrets: bool = True,
                 use_cache: bool = True):
        """
        Initialize configuration context.

        Args:
            org_id: Organization identifier
            env_type: Environment type
            validate: Whether to validate configuration
            include_secrets: Whether to load and inject secrets
            use_cache: Whether to use cached loader
        """
        self.org_id = org_id
        self.env_type = env_type
        self.validate = validate
        self.include_secrets = include_secrets
        self.use_cache = use_cache
        self.loader: Optional[ConfigLoader] = None
        self.config: Optional[Dict[str, Any]] = None

    def __enter__(self) -> Dict[str, Any]:
        """Load configuration on context entry."""
        self.loader = get_config_loader(self.org_id, self.env_type, self.use_cache)
        self.config = self.loader.load_config(
            validate=self.validate,
            include_secrets=self.include_secrets
        )
        return self.config

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on context exit."""
        # Could add cleanup logic here if needed
        pass