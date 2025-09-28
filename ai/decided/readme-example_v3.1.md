# TXO Python Template v3.1

> **Problem Solved**: Consistent, secure, production-ready Python automation across multiple organizations and
> environments
> **Get Running**: 5 minutes from clone to first script execution

## What This Solves

**Before TXO Template**:

- ❌ Scripts break across environments (dev vs prod)
- ❌ Secrets accidentally committed to git
- ❌ Inconsistent logging makes debugging impossible
- ❌ Manual configuration for every new project

**After TXO Template**:

- ✅ Consistent behavior across all environments
- ✅ Mandatory security patterns (never leak tokens)
- ✅ Structured logging with AI-friendly debug files
- ✅ Type-safe paths and configuration management

---

## Quick Start (5 Minutes)

### 1. Setup Configuration (30 seconds)

```bash
# Copy configuration templates
cp config/org-env-config_example.json config/demo-test-config.json
cp config/org-env-config-secrets_example.json config/demo-test-config-secrets.json

# Templates work as-is for demo scripts!
```

### 2. Run Your First Script (30 seconds)

```bash
# No authentication needed for local processing
python src/try_me_script.py demo test

# Expected output:
# [Test/Demo/LocalProcessing] Processing started
# ✅ All 5 operations successful: 3 created, 2 updated
```

### 3. Directory Structure (Know Where Things Go)

```
your-project/
├── config/          # Put your org-env-config.json here
├── data/            # Put input files here
├── src/             # Start with these working scripts
├── output/          # Generated reports appear here
├── logs/            # Debug files for AI troubleshooting
└── utils/           # DO NOT MODIFY - TXO framework
```

---

## Common Usage Patterns

### Local Data Processing (Most Common)

```python
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir

logger = setup_logger()
data_handler = TxoDataHandler()


def main():
    # Auto-loads config, no token needed
    config = parse_args_and_load_config("Process customer data")

    # Type-safe file operations
    customers = data_handler.load(Dir.DATA, "customers.csv")
    processed = process_customers(customers)
    data_handler.save(processed, Dir.OUTPUT, "results.xlsx")

# Usage: python your_script.py mycompany prod  # Always: org_id env_type
```

### API Integration Scripts

```python
from utils.api_factory import create_rest_api


def main():
    # Explicitly request authentication
    config = parse_args_and_load_config("Sync with BC", require_token=True)

    # Get configured API client (rate limiting, retries built-in)
    api = create_rest_api(config)
    response = api.get("/customers")
```

---

## Configuration Quick Reference

### Required Files (Script exits if missing)

```bash
config/
├── {org}-{env}-config.json           # Main settings
├── logging-config.json               # How to log (copy from templates/)
└── log-redaction-patterns.json       # Security (copy from templates/)
```

### Secrets (Optional, always gitignored)

```bash
config/
└── {org}-{env}-config-secrets.json   # API keys, passwords
```

### JSON Configuration Format

```json
{
  "global": {
    "api-base-url": "https://api.example.com",
    "timeout-seconds": 30
  },
  "script-behavior": {
    "rate-limiting": {
      "enabled": false,
      "calls-per-second": 10
    }
  }
}
```

---

## Troubleshooting (Common Issues)

| Problem                             | Solution                                      |
|-------------------------------------|-----------------------------------------------|
| `Config file not found`             | Copy example files from `config/` directory   |
| `Invalid category 'output'`         | Use `Dir.OUTPUT` instead of `'output'` string |
| `Token required but not configured` | Add `require_token=False` or configure OAuth  |
| `Import error: cannot import Dir`   | You have the wrong version - use v3.1+        |

---

## When You Need More

- **Architecture decisions**: See `ai/decided/txo-business-adr_v3.1.md`
- **Python patterns**: See `ai/decided/txo-technical-standards_v3.1.md`
- **All available functions**: See `ai/decided/utils-quick-reference_v3.1.md`
- **Detailed setup**: See `ai/decided/in-depth-readme_v3.1.md`

---

## Version History

### v3.1 (Current)

- Type-safe path management with Dir constants
- Token optional by default for local scripts

### v3.0

- Mandatory configuration files with templates
- Enhanced security and structured logging

---

**Version:** v3.1  
**Last Updated:** 2025-01-25
**Domain:** TXO Framework  
**Purpose:** Quick start guide for Python automation template