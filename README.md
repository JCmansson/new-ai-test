# TXO Python Template v3.1

> **Problem Solved**: Consistent, secure, production-ready Python automation across multiple organizations and
> environments
> **Get Running**: 5 minutes from clone to first script execution in PyCharm

![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![Version](https://img.shields.io/badge/version-3.1-green)
![MIT License](https://img.shields.io/badge/license-MIT-green)
![PyCharm](https://img.shields.io/badge/IDE-PyCharm-green)

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

## Quick Start in PyCharm (5 Minutes)

### 1. Clone and Open in PyCharm (1 minute)

1. **Clone**: `git clone https://github.com/tentixo/txo-python-template.git`
2. **Open in PyCharm**: File → Open → Select the cloned directory
3. **Trust the project** when PyCharm asks
4. **Let PyCharm install dependencies** automatically (it will detect `pyproject.toml`)

### 2. Setup Configuration (2 minutes)

Right-click in PyCharm Project Explorer:

```
config/
├── org-env-config_example.json           → Copy → Rename to: demo-test-config.json
└── org-env-config-secrets_example.json   → Copy → Rename to: demo-test-config-secrets.json
```

**PyCharm Steps**:

1. Right-click `org-env-config_example.json` → **Copy**
2. Right-click in `config/` folder → **Paste**
3. Rename to `demo-test-config.json`
4. Repeat for all 4 example files

> 💡 **Example files work as-is** - No editing needed for demo!

### 3. Run Your First Script (2 minutes)

1. **Open** `src/try_me_script.py` in PyCharm
2. **Right-click** in the editor → **Run 'try_me_script'**
3. **It will fail** - this is expected! PyCharm will ask for run configuration
4. **Edit Run Configuration**:
   - **Parameters**: `demo test`
   - **Working directory**: (should be project root)
   - **Click OK**
5. **Run again** → Should see success output:

```
[Test/Demo/LocalProcessing] Processing started
✅ All 5 operations successful: 3 created, 2 updated
```

---

## PyCharm Project Structure

```
your-txo-project/
├── config/              # Configuration files (copy examples here)
│   ├── org-env-config_example.json          # → Copy to {org}-{env}-config.json
│   ├── org-env-config-secrets_example.json  # → Copy to {org}-{env}-config-secrets.json
│   ├── logging-config_example.json          # → Copy to logging-config.json
│   └── log-redaction-patterns_example.json  # → Copy to log-redaction-patterns.json
├── data/                # Put input files here (CSV, JSON, etc.)
├── output/              # Generated reports appear here
├── logs/                # Debug files for AI troubleshooting
├── src/                 # Your scripts go here
│   └── try_me_script.py # Working example script
├── tests/               # Test scripts
├── utils/               # 🚨 DO NOT MODIFY - TXO framework code
└── ai/decided/          # Documentation and ADRs
```

---

## Creating Your Own Scripts in PyCharm

### Method 1: Copy and Modify (Recommended)

1. **Copy** `src/try_me_script.py` in PyCharm
2. **Rename** to your script name
3. **Modify** the business logic inside `main()`
4. **Set run parameters**: `{your_org} {your_env}`

### Method 2: Start from Template

```python
# Your new script: src/my_script.py
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir

logger = setup_logger()
data_handler = TxoDataHandler()


def main():
    # Auto-loads config, no token needed for local processing
    config = parse_args_and_load_config("My awesome script")

    # Type-safe file operations
    input_data = data_handler.load(Dir.DATA, "input.csv")

    # Your business logic here
    processed_data = process_my_data(input_data)

    # Auto-detects file type from extension
    data_handler.save(processed_data, Dir.OUTPUT, "results.xlsx")

    logger.info("✅ Processing complete!")


def process_my_data(data):
    # Your logic here
    return data


if __name__ == "__main__":
    main()
```

### PyCharm Run Configuration

- **Parameters**: `myorg prod` (always org_id env_type)
- **Working directory**: Project root
- **Environment variables**: Add `DEBUG_LOGGING=1` for verbose output

---

## Common Usage Patterns

### Local Data Processing (Most Common)

```python
def main():
    # No authentication needed
    config = parse_args_and_load_config("Process customer data")

    # Load from data/ directory
    customers = data_handler.load(Dir.DATA, "customers.csv")
    processed = transform_customers(customers)

    # Save to output/ directory
    data_handler.save(processed, Dir.OUTPUT, "processed-customers.xlsx")
```

**PyCharm Setup**: Parameters = `myorg prod`

### API Integration Scripts

```python
from utils.api_factory import create_rest_api


def main():
    # Explicitly request authentication
    config = parse_args_and_load_config("Sync with API", require_token=True)

    # Get configured API client (rate limiting, retries built-in)
    api = create_rest_api(config)
    customers = api.get("/customers")
```

**PyCharm Setup**:

- Parameters = `myorg prod`
- Ensure OAuth configured in config file

---

## Configuration in PyCharm

### Required Files (Script exits if missing)

All config files live in `config/` directory:

```json lines
// demo-test-config.json (Main settings)
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

```json lines
// demo-test-config-secrets.json (Gitignored automatically)
{
  "client-secret": "your-actual-secret",
  "api-token": "your-actual-token"
}
```

### PyCharm JSON Editing

- **Syntax highlighting** - PyCharm validates JSON automatically
- **Schema validation** - Uses `schemas/org-env-config-schema.json`
- **Auto-completion** - PyCharm suggests valid keys
- **Error highlighting** - Red underlines for invalid JSON

---

## Debugging in PyCharm

### Using PyCharm Debugger

1. **Set breakpoints** in your script
2. **Right-click** → **Debug 'script_name'**
3. **Step through** TXO framework calls
4. **Inspect variables** - config, data_handler, logger

### Log File Analysis

- **Logs appear** in `logs/` directory
- **Open in PyCharm** for syntax highlighting
- **Search/filter** using PyCharm's find functionality
- **Upload to AI** for debugging assistance

### Common Debug Scenarios in PyCharm

```python
# Set breakpoint here to inspect config structure
config = parse_args_and_load_config("Debug script")
print(f"Loaded config keys: {list(config.keys())}")  # Breakpoint here

# Set breakpoint to see what data was loaded
data = data_handler.load(Dir.DATA, "input.csv")
print(f"Data shape: {data.shape}")  # Breakpoint here
```

---

## Troubleshooting in PyCharm

| Problem                             | PyCharm Solution                                 |
|-------------------------------------|--------------------------------------------------|
| `Config file not found`             | Copy examples from `config/` in Project Explorer |
| `Invalid category 'output'`         | Use `Dir.OUTPUT` - PyCharm autocompletes Dir.*   |
| `Token required but not configured` | Add `require_token=False` or edit config JSON    |
| `Import error: cannot import Dir`   | Check PyCharm Python interpreter settings        |
| Script won't run                    | Check Run Configuration → Parameters field       |

### PyCharm-Specific Tips

- **Red underlines** = Import or syntax errors
- **Yellow highlights** = Warnings or suggestions
- **Ctrl+Click** on TXO functions to see source code
- **File → Settings → Python Interpreter** to verify dependencies

---

## Project Templates and Patterns

### PyCharm File Templates

Create **File → Settings → Editor → File and Code Templates**:

```python
# TXO Script Template
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir

logger = setup_logger()
data_handler = TxoDataHandler()


def main():
    config = parse_args_and_load_config("${SCRIPT_NAME}")

    # TODO: Add your business logic here

    logger.info("✅ ${SCRIPT_NAME} completed")


if __name__ == "__main__":
    main()
```

### PyCharm Run Configuration Templates

Save run configurations for common patterns:

- **Local Processing**: Parameters = `demo test`
- **Production**: Parameters = `myorg prod`
- **Debug Mode**: Environment = `DEBUG_LOGGING=1`

---

## Advanced PyCharm Integration

### Code Inspections

PyCharm will highlight TXO pattern violations:

- **String literals** instead of `Dir.*` constants
- **Soft-fail** patterns like `config.get()`
- **Print statements** instead of logger calls

### PyCharm Plugins Recommended

- **JSON Schema** - Validates config files
- **Python Security** - Detects security issues
- **Requirements** - Manages dependencies

### Version Control in PyCharm

PyCharm Git integration respects `.gitignore`:

- ✅ **Config examples** are tracked
- ❌ **Secrets files** auto-ignored (`*-secrets.*`)
- ❌ **Generated files** ignored (`logs/`, `output/`)

---

## When You Need More

- **Architecture decisions**: `ai/decided/txo-business-adr_v3.1.md`
- **Python patterns**: `ai/decided/txo-technical-standards_v3.1.md`
- **All available functions**: `ai/decided/utils-quick-reference_v3.1.md`
- **Detailed setup**: `ai/decided/in-depth-readme_v3.1.md`
- **AI development**: `ai/decided/ai-prompt-template_v3.1.md`

---

## Migration from Previous Versions

### v3.0 → v3.1 (Minor Updates)

- Configuration structure unchanged
- New documentation format standards
- Enhanced PyCharm integration

### v2.x → v3.1 (Breaking Changes)

```python
# Update imports
from utils.path_helpers import Dir  # NEW requirement

# Update path usage
# OLD: data_handler.load_json('config', 'file.json')
# NEW: data_handler.load_json(Dir.CONFIG, 'file.json')

# Update token requirement
# OLD: config = parse_args_and_load_config("Script")  # Token required
# NEW: config = parse_args_and_load_config("Script")  # Token optional
```

**PyCharm Migration Help**:

1. **Find/Replace** string literals with Dir constants
2. **Code inspection** will highlight patterns to update
3. **Refactor** tools can help with bulk updates

---

## Version History

### v3.1 (Current)

- Enhanced PyCharm integration and workflow
- Streamlined configuration with examples in config/
- Moved scripts to src/ for better organization

### v3.0

- Type-safe path management with Dir constants
- Token optional by default, mandatory configuration files
- Enhanced security and structured logging patterns

---

**Version:** v3.1  
**Last Updated:** 2025-09-28
**Domain:** TXO Python Template  
**Purpose:** Production-ready Python automation framework with PyCharm integration