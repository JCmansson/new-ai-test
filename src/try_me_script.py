# examples/try_me_script.py
"""
Try Me First! - Simple script to test TXO Python Template v3.0 setup

This script demonstrates core TXO v3.0 patterns using GitHub's public API.
No authentication or complex setup required - it just works!

Usage:
    python try_me_script.py <org_id> <env_type>

Example:
    python try_me_script.py demo test

What it does:
    1. Fetches top Python repositories from GitHub
    2. Saves results to output/demo-test-github_repos_2025-01-25T143045Z.json
    3. Demonstrates v3.1 patterns: Dir constants, UTC timestamps, no token needed

Perfect for:
    - Testing your development environment
    - Learning TXO v3.1 patterns
    - Validating the template setup
"""

from typing import Dict, Any, List

from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir  # v3.0: Type-safe directory constants
from utils.api_factory import create_rest_api
from utils.exceptions import ApiOperationError, HelpfulError

logger = setup_logger()
data_handler = TxoDataHandler()


def fetch_github_repos(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetch top Python repositories from GitHub's public API.

    Args:
        config: Configuration dictionary with injected fields

    Returns:
        List of repository dictionaries

    Raises:
        ApiOperationError: If GitHub API request fails
    """
    # Create REST API client using TXO framework (no auth needed for GitHub public API)
    api = create_rest_api(config, require_auth=False)

    # GitHub search API endpoint
    url = "https://api.github.com/search/repositories"

    logger.info("Fetching top Python repositories from GitHub...")

    try:
        # Use TXO REST API framework (handles timeouts, rate limiting, retries automatically)
        data = api.get(url, params={
            "q": "language:python stars:>1000",
            "sort": "stars",
            "order": "desc",
            "per_page": 10
        })

        repos = data["items"]  # Hard fail if 'items' key missing

        logger.info(f"Successfully fetched {len(repos)} repositories")

        # Extract and structure the data
        results = []
        for repo in repos:
            # Required fields (hard fail if missing)
            results.append({
                "name": repo["name"],
                "full_name": repo["full_name"],
                "stars": repo["stargazers_count"],
                "language": repo["language"],
                "url": repo["html_url"],
                "created_at": repo["created_at"],
                "updated_at": repo["updated_at"],
                # Optional fields (using get for these)
                "description": repo.get("description", "No description"),
                "topics": repo.get("topics", []),
                "license": repo.get("license", {}).get("name") if repo.get("license") else "No license"
            })

        return results

    except KeyError as e:
        logger.error(f"GitHub API response missing expected field: {e}")
        raise ApiOperationError(f"Invalid GitHub API response structure: missing {e}")
    except Exception as e:
        logger.error(f"API request failed: {e}")
        raise ApiOperationError(f"GitHub API request failed: {e}")


def save_results(config: Dict[str, Any], repos: List[Dict[str, Any]]) -> None:
    """
    Save repository data to output file using v3.0 patterns.

    Args:
        config: Configuration dictionary
        repos: List of repository data

    Raises:
        HelpfulError: If save operation fails
    """
    if not repos:
        logger.warning("No repositories to save")
        return

    # Build output filename with TXO pattern
    org_id = config["_org_id"]  # Hard fail if missing
    env_type = config["_env_type"]  # Hard fail if missing

    filename = f"{org_id}-{env_type}-github_repos.json"

    try:
        # v3.1: Use save_with_timestamp for UTC timestamp in TXO standard format
        output_path = data_handler.save_with_timestamp(
            repos, Dir.OUTPUT, filename,
            add_timestamp=True
        )
        logger.info(f"✅ Saved {len(repos)} repositories to: {output_path}")

    except Exception as e:
        logger.error(f"Save operation failed: {e}")
        raise HelpfulError(
            what_went_wrong=f"Could not save results to {Dir.OUTPUT}/{filename}",
            how_to_fix=f"Check that {Dir.OUTPUT}/ directory exists and is writable",
            example=f"Create the directory: mkdir {Dir.OUTPUT}"
        )


def display_summary(repos: List[Dict[str, Any]]) -> None:
    """
    Display a summary of fetched repositories.

    Args:
        repos: List of repository data
    """
    logger.info("=" * 60)
    logger.info("GitHub API Test - Summary")
    logger.info("=" * 60)
    logger.info(f"Total repositories fetched: {len(repos)}")
    logger.info("")
    logger.info("Top 3 Python repositories by stars:")

    for i, repo in enumerate(repos[:3], 1):
        logger.info(f"  {i}. {repo['full_name']}")
        logger.info(f"     ⭐ Stars: {repo['stars']:,}")
        logger.info(f"     📝 {repo['description'][:70]}...")
        logger.info("")

    logger.info("=" * 60)


def main():
    """Main entry point demonstrating TXO v3.0 patterns."""
    # v3.0: Load configuration WITHOUT token (public API doesn't need auth)
    config = parse_args_and_load_config(
        "Try Me Script - Test TXO Template v3.0 with GitHub API",
        require_token=False  # v3.0: Token optional by default
    )

    # Extract org and env (hard fail if missing - v3.0 philosophy)
    org_id = config["_org_id"]
    env_type = config["_env_type"]

    logger.info(f"🚀 Starting Try-Me script (v3.0) for {org_id}-{env_type}")

    # Check for configuration
    if "script-behavior" in config:
        logger.debug("Using script-behavior configuration")
    else:
        logger.info("Using default settings (no script-behavior config found)")

    try:
        repos = fetch_github_repos(config)

        # Save the results using v3.1 patterns
        save_results(config, repos)

        # Display summary
        display_summary(repos)

        logger.info(f"✅ Try-Me script completed successfully for {org_id}-{env_type}")
        logger.info("✅ TXO Template v3.0 is working correctly!")

    except ApiOperationError as e:
        logger.error(f"❌ API Error: {e}")
        logger.error("\nPossible causes:")
        logger.error("  1. No internet connection")
        logger.error("  2. GitHub API is temporarily down")
        logger.error("  3. Hit rate limit (wait a few minutes)")
        raise

    except HelpfulError:
        # Re-raise to let script_runner handle the display
        raise

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HelpfulError(
            what_went_wrong=f"Script failed unexpectedly: {e}",
            how_to_fix="Check the logs for details or run with --debug",
            example="python try_me_script.py demo test --debug"
        )


if __name__ == "__main__":
    import sys

    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Script interrupted by user")
        sys.exit(130)
    except HelpfulError:
        # HelpfulError message already logged
        sys.exit(1)
    except Exception as unexpected_error:
        # Broad exception acceptable for main script catch-all
        logger.error(f"❌ Unexpected error: {unexpected_error}")
        sys.exit(1)