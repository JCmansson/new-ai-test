# tests/test_redaction.py
"""
Test script to verify v3.0 redaction patterns are working correctly.

This includes testing for underscore-prefixed metadata fields that are
common in TXO convention (_token, _password, _client_secret, etc.)

Run this to ensure sensitive data is being properly redacted.
"""

from utils.logger import setup_logger


def test_redaction_patterns():
    """Test various sensitive data patterns to ensure they're redacted."""
    logger = setup_logger()

    print("\n=== Testing v3.0 Redaction Patterns ===\n")
    print("Check the console output and log file to verify redaction:\n")

    # Test underscore-prefixed metadata (v3.0 enhancement)
    print("--- Testing TXO Metadata Convention (underscore prefix) ---")

    logger.info('Config with metadata: {"_token": "Bearer abc123xyz"}')
    # Should show: {"_token": "[REDACTED]"}

    logger.info('Secrets: {"_password": "metadata_password123"}')
    # Should show: {"_password": "[REDACTED]"}

    logger.info('OAuth: {"_client_secret": "oauth_secret_value"}')
    # Should show: {"_client_secret": "[REDACTED]"}

    logger.info('API: {"_api_key": "sk-1234567890abcdef"}')
    # Should show: {"_api_key": "[REDACTED]"}

    print("\n--- Testing Standard Patterns ---")

    # Test Azure Communication Services
    logger.info(
        "Azure Comm connection: endpoint=https://coms-txo-cybersec.europe.communication.azure.com/;accesskey=abcd1234efgh5678ijkl")
    # Should show: endpoint=https://coms-txo-cybersec.europe.communication.azure.com/;accesskey=[REDACTED]

    # Test Azure Storage
    logger.info("Storage: DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=abc123def456ghi789==")
    # Should show: DefaultEndpointsProtocol=https;AccountName=[REDACTED];AccountKey=[REDACTED]

    # Test Bearer tokens
    logger.info(
        "Auth header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
    # Should show: Auth header: Bearer [REDACTED]

    # Test JWT tokens
    logger.info(
        "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
    # Should show: Token: [REDACTED_JWT]

    # Test passwords in JSON (both with and without underscore)
    logger.info('Config: {"username": "admin", "password": "supersecret123"}')
    # Should show: Config: {"username": "admin", "password": "[REDACTED]"}

    # Test API keys with various separators
    logger.info("Request URL: https://api.example.com/data?api_key=1234567890abcdefghij&user=john")
    # Should show: Request URL: https://api.example.com/data?api_key=[REDACTED]&user=john

    logger.info("Request URL: https://api.example.com/data?api-key=1234567890abcdefghij&user=john")
    # Should show: Request URL: https://api.example.com/data?api-key=[REDACTED]&user=john

    # Test client secrets with various formats
    logger.info('OAuth: {"client_id": "my-app", "client_secret": "secret123456"}')
    # Should show: OAuth: {"client_id": "my-app", "client_secret": "[REDACTED]"}

    logger.info('OAuth: {"client_id": "my-app", "client-secret": "secret123456"}')
    # Should show: OAuth: {"client_id": "my-app", "client-secret": "[REDACTED]"}

    # Test long random tokens
    logger.info("Random token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6")
    # Should show: Random token: [REDACTED_TOKEN]

    # Test credit card
    logger.info("Payment with card: 4111-1111-1111-1111")
    # Should show: Payment with card: [REDACTED_CARD]

    # Test SSN
    logger.info("Customer SSN: 123-45-6789")
    # Should show: Customer SSN: [REDACTED_SSN]

    # Test connection strings
    logger.info("DB: Server=myserver;Database=mydb;User Id=sa;Password=MyP@ssw0rd;")
    # Should show: DB: Server=myserver;Database=mydb;User Id=sa;Password=[REDACTED];

    # Test multiple sensitive items in one message
    logger.info("Full config: api_key=abc123 api-key=xyz789 _token=meta123 Bearer token123456789012345678901234567890")
    # Should show: Full config: api_key=[REDACTED] api-key=[REDACTED] _token=[REDACTED] Bearer [REDACTED]

    print("\n=== v3.0 Test Complete ===")
    print("Check the log file for redacted output")
    print("If any sensitive data is NOT redacted, update log-redaction-patterns.json")
    print("\nNOTE: v3.0 should redact underscore-prefixed fields like _token, _password, etc.\n")


def test_reload_patterns():
    """Test that patterns can be reloaded at runtime."""
    logger = setup_logger()

    print("\n=== Testing Pattern Reload ===\n")

    logger.info("Before reload: accesskey=sensitive123")
    logger.info("Before reload: _token=metadata_token")

    # Simulate updating the config file
    print("Update log-redaction-patterns.json if needed, then press Enter...")
    input()

    # Note: Reload functionality would need to be implemented in logger.py
    # This is a placeholder for the test
    if hasattr(logger, 'reload_redaction_patterns'):
        logger.reload_redaction_patterns()
        print("Patterns reloaded")
    else:
        print("Pattern reload not implemented yet")

    logger.info("After reload: accesskey=sensitive456")
    logger.info("After reload: _token=metadata_token2")

    print("\n=== Reload Test Complete ===\n")


def test_edge_cases():
    """Test edge cases and complex patterns."""
    logger = setup_logger()

    print("\n=== Testing Edge Cases ===\n")

    # Mixed case
    logger.info("Mixed: Api_Key=test123 API-KEY=test456 ApiKey=test789")

    # Nested JSON
    logger.info('Nested: {"auth": {"_token": "secret", "user": {"_password": "pass123"}}}')

    # URL encoded
    logger.info("Encoded: password%3Dsecret123%26api_key%3Dabc")

    # Base64 encoded (should catch long strings)
    logger.info("Base64: YWNjZXNza2V5PWFiYzEyM2RlZjQ1Nmdoaas789==")

    print("\n=== Edge Case Test Complete ===\n")


if __name__ == "__main__":
    import sys

    # Follow TXO pattern: require org_id and env_type
    if len(sys.argv) < 3:
        print("Usage: python test_redaction.py <org_id> <env_type> [options]")
        print("Example: python test_redaction.py demo test")
        print("Example: python test_redaction.py demo test --reload")
        print("Example: python test_redaction.py demo test --edge")
        sys.exit(1)

    # Accept org_id and env_type for consistency, but we don't use them
    # This utility doesn't need configuration, but follows TXO patterns
    org_id = sys.argv[1]
    env_type = sys.argv[2]

    # Check for additional options
    if len(sys.argv) > 3:
        option = sys.argv[3]
        if option == "--reload":
            test_reload_patterns()
        elif option == "--edge":
            test_edge_cases()
        else:
            print(f"Unknown option: {option}")
            print("Available options: --reload, --edge")
    else:
        test_redaction_patterns()
        print("\nTip: Run with --reload to test pattern reloading")
        print("     Run with --edge to test edge cases")