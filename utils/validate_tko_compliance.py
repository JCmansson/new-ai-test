#!/usr/bin/env python3
"""
TXO Compliance Validator

Validates Python scripts against TXO patterns and standards.
Use this after AI generates scripts to ensure compliance.

Usage:
    python utils/validate_tko_compliance.py path/to/your_script.py
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

from utils.logger import setup_logger

logger = setup_logger()


class TkoComplianceValidator:
    """Validates Python scripts against TXO patterns."""

    def __init__(self):
        self.violations: List[Dict[str, str]] = []
        self.warnings: List[Dict[str, str]] = []

    def validate_file(self, script_path: Path) -> Tuple[bool, List[Dict], List[Dict]]:
        """
        Validate a Python script against TXO compliance rules.

        Returns:
            Tuple of (is_compliant, violations, warnings)
        """
        if not script_path.exists():
            self.violations.append({
                "type": "FILE_NOT_FOUND",
                "message": f"Script file not found: {script_path}",
                "line": 0,
                "fix": "Check the file path"
            })
            return False, self.violations, self.warnings

        content = script_path.read_text()
        lines = content.split('\n')

        # Run all validation checks
        self._check_api_patterns(lines)
        self._check_timestamp_patterns(lines)
        self._check_directory_patterns(lines)
        self._check_configuration_patterns(lines)
        self._check_complexity_patterns(lines)
        self._check_framework_patterns(content)

        is_compliant = len(self.violations) == 0
        return is_compliant, self.violations, self.warnings

    def _check_api_patterns(self, lines: List[str]) -> None:
        """Check for manual requests usage instead of create_rest_api."""
        for i, line in enumerate(lines, 1):
            if re.search(r'import requests|from requests', line):
                self.violations.append({
                    "type": "MANUAL_REQUESTS",
                    "message": "Using manual requests instead of TXO API framework",
                    "line": i,
                    "fix": "Replace with: from utils.api_factory import create_rest_api"
                })

            if re.search(r'requests\.Session\(\)|session = requests', line):
                self.violations.append({
                    "type": "MANUAL_SESSION",
                    "message": "Manual session management detected",
                    "line": i,
                    "fix": "Use: api = create_rest_api(config, require_auth=False)"
                })

    def _check_timestamp_patterns(self, lines: List[str]) -> None:
        """Check for manual timestamp formatting."""
        for i, line in enumerate(lines, 1):
            if re.search(r'datetime\.now\(\)\.strftime|\.strftime\(["\'].*T.*Z', line):
                self.violations.append({
                    "type": "MANUAL_TIMESTAMP",
                    "message": "Manual UTC timestamp formatting detected",
                    "line": i,
                    "fix": "Use: TxoDataHandler.get_utc_timestamp() or save_with_timestamp()"
                })

    def _check_directory_patterns(self, lines: List[str]) -> None:
        """Check for string directory literals."""
        for i, line in enumerate(lines, 1):
            if re.search(r'["\'](?:config|data|output|logs|tmp)["\']', line):
                self.violations.append({
                    "type": "STRING_DIRECTORY",
                    "message": "String directory literal detected",
                    "line": i,
                    "fix": "Use: Dir.CONFIG, Dir.DATA, Dir.OUTPUT, etc."
                })

    def _check_configuration_patterns(self, lines: List[str]) -> None:
        """Check for soft-fail configuration access."""
        for i, line in enumerate(lines, 1):
            if re.search(r'config\.get\(["\'][^"\']+["\'],', line):
                self.warnings.append({
                    "type": "SOFT_FAIL_CONFIG",
                    "message": "Potential soft-fail configuration access",
                    "line": i,
                    "fix": "Consider: config['key'] for hard-fail (if config setting)"
                })

    def _check_complexity_patterns(self, lines: List[str]) -> None:
        """Check for unnecessary complexity."""
        for i, line in enumerate(lines, 1):
            if re.search(r'time\.time\(\)|start_time|elapsed', line):
                self.warnings.append({
                    "type": "TIMING_CODE",
                    "message": "Performance timing code detected",
                    "line": i,
                    "fix": "Remove unless specifically requested"
                })

            if re.search(r'\.stat\(\)\.st_size|file_size', line):
                self.warnings.append({
                    "type": "FILE_SIZE_LOGGING",
                    "message": "File size logging detected",
                    "line": i,
                    "fix": "Remove unless specifically requested"
                })

    def _check_framework_patterns(self, content: str) -> None:
        """Check for standard TXO script patterns."""
        required_imports = [
            'from utils.script_runner import parse_args_and_load_config',
            'from utils.load_n_save import TxoDataHandler',
            'from utils.logger import setup_logger'
        ]

        for import_stmt in required_imports:
            if import_stmt not in content:
                self.violations.append({
                    "type": "MISSING_TXO_IMPORT",
                    "message": f"Missing standard TXO import: {import_stmt}",
                    "line": 0,
                    "fix": f"Add: {import_stmt}"
                })


def main():
    """Main validation function."""
    if len(sys.argv) != 2:
        logger.error("Usage: python utils/validate_tko_compliance.py path/to/script.py")
        sys.exit(1)

    script_path = Path(sys.argv[1])
    validator = TkoComplianceValidator()

    logger.info(f"🔍 Validating TXO compliance for: {script_path}")

    is_compliant, violations, warnings = validator.validate_file(script_path)

    # Report results
    if violations:
        logger.error(f"❌ {len(violations)} TXO compliance violations found:")
        for v in violations:
            logger.error(f"  Line {v['line']}: {v['message']}")
            logger.error(f"    Fix: {v['fix']}")

    if warnings:
        logger.warning(f"⚠️  {len(warnings)} potential issues found:")
        for w in warnings:
            logger.warning(f"  Line {w['line']}: {w['message']}")
            logger.warning(f"    Consider: {w['fix']}")

    if is_compliant and not warnings:
        logger.info("✅ Script is fully TXO compliant!")
    elif is_compliant:
        logger.info("✅ Script passes TXO compliance (with minor warnings)")
    else:
        logger.error("❌ Script has TXO compliance violations that must be fixed")
        sys.exit(1)


if __name__ == "__main__":
    main()