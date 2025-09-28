# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running Scripts

**Primary Method (PyCharm/IDE)**:
- Use PyCharm's Run Configuration (recommended)
- IDE automatically handles import paths
- Set working directory to project root

**Command Line Method**:
```bash
# From project root with PYTHONPATH
PYTHONPATH=. python src/try_me_script.py demo test

# Or use python -m (preferred for command line)
python -m src.try_me_script demo test

# With custom org/env
PYTHONPATH=. python src/your_script.py mycompany prod

# Debug mode
DEBUG_LOGGING=1 PYTHONPATH=. python src/script.py demo test
```

**For AI/Automation**:
```bash
# Claude Code: Always use PYTHONPATH when running scripts via Bash tool
PYTHONPATH=. python src/script_name.py org env
```

### Setup Commands
```bash
# Install dependencies using uv (preferred)
pip install uv
uv pip install -r pyproject.toml

# Copy required config files before first run
cp config/org-env-config_example.json config/myorg-test-config.json
cp config/org-env-config-secrets_example.json config/myorg-test-config-secrets.json
```

### Project Management
```bash
# Clean temporary files
python -c "from utils.path_helpers import cleanup_tmp; print(f'Deleted {cleanup_tmp()} files')"

# Check directory sizes
python -c "from utils.path_helpers import Dir, get_dir_size; print(get_dir_size(Dir.LOGS))"
```

### Code Quality
```bash
# TXO Compliance validation (recommended for AI-generated scripts)
PYTHONPATH=. python utils/validate_tko_compliance.py src/your_script.py

# PyCharm generates inspection reports in code-reports/ directory
# Known issues (as of current version):
# - Type mismatches with CaseInsensitiveDict in rest_api_helpers.py
# - Several variable shadowing warnings (non-critical)

# Basic syntax check
python -m py_compile src/your_script.py
```

## Architecture Overview

This is the **TXO Python Template v3.0** - a production-ready framework for Python automation with enterprise-grade security features, mandatory configuration, and type-safe operations.

### Core Architecture Principles
- **Security First**: All scripts require mandatory configuration files (no defaults)
- **Type-Safe Paths**: Uses `Dir.*` constants instead of string literals
- **Hard-Fail Philosophy**: Configuration errors exit immediately with clear messages
- **Token Optional**: Most scripts don't need authentication (explicit `require_token=True` for API scripts)

### Key Components

#### 1. Path Management (`utils/path_helpers.py`)
- **ALWAYS use** `Dir.*` constants: `Dir.CONFIG`, `Dir.OUTPUT`, `Dir.LOGS`, etc.
- **NEVER use** string literals like `'config'` or `'output'`
- Type-safe directory access with IDE autocomplete
- Automatic parent directory creation

#### 2. Configuration System (`utils/config_loader.py` + `utils/script_runner.py`)
- **Mandatory Files** (script exits if missing):
  - `{org}-{env}-config.json` - Main configuration
  - `logging-config.json` - Logging setup
  - `log-redaction-patterns.json` - Token redaction patterns
- **Optional**: `{org}-{env}-config-secrets.json` (gitignored, injected as `_token`, `_client_secret`)
- Nested configuration structure (v3.0)

#### 3. Smart I/O System (`utils/load_n_save.py`)
- Single `save()` method auto-detects file types from extensions
- Supports JSON, Excel, CSV, YAML, text files
- Single `load()` method with type detection
- Thread-safe operations with proper locking

#### 4. API Framework (`utils/api_factory.py`, `utils/api_common.py`)
- Rate limiting with configurable burst sizes
- Circuit breaker pattern for resilience
- OAuth token management
- Automatic retry with exponential backoff

### Standard Script Pattern

#### Local Processing Script (No Auth)
```python
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.load_n_save import TxoDataHandler
from utils.path_helpers import Dir

logger = setup_logger()
data_handler = TxoDataHandler()

def main():
    # Token optional by default
    config = parse_args_and_load_config("Process local data")

    # Load data using Dir constants
    data = data_handler.load(Dir.DATA, "input.csv")

    # Process data...

    # Save with smart detection
    data_handler.save(results, Dir.OUTPUT, "results.xlsx")
```

#### API Integration Script (Needs Auth)
```python
from utils.logger import setup_logger
from utils.script_runner import parse_args_and_load_config
from utils.api_factory import create_rest_api

def main():
    # Explicitly require token
    config = parse_args_and_load_config(
        "API sync script",
        require_token=True
    )

    # Create API client (uses config['_token'])
    api = create_rest_api(config)
```

## Critical Patterns

### 1. Type-Safe Directory Usage
```python
# ✅ CORRECT
from utils.path_helpers import Dir
config = data_handler.load_json(Dir.CONFIG, 'settings.json')

# ❌ WRONG - Will cause ValueError
config = data_handler.load_json('config', 'settings.json')
```

### 2. Configuration Access
```python
# ✅ CORRECT - Hard fail on missing keys
api_url = config['global']['api-base-url']

# ❌ WRONG - Soft defaults discouraged
api_url = config.get('global', {}).get('api-base-url', 'default')
```

### 3. File Operations
```python
# ✅ CORRECT - Auto-detects file type
data_handler.save(dataframe, Dir.OUTPUT, "report.xlsx")  # Excel
data_handler.save(dict_data, Dir.OUTPUT, "data.json")    # JSON

# ✅ CORRECT - Universal load
data = data_handler.load(Dir.DATA, "input.csv")  # Returns DataFrame
```

## Directory Structure

#### Used by code
```
├── config/          # Configuration files
│   ├── {org}-{env}-config.json           # MANDATORY
│   ├── {org}-{env}-config-secrets.json   # MANDATORY (gitignored)
│   ├── logging-config.json               # MANDATORY
│   ├── log-redaction-patterns.json       # MANDATORY
│   ├── org-env-config_example.json       # Template to copy
│   └── org-env-config-secrets_example.json # Template to copy
├── data/            # Input data files
├── logs/            # Log files (gitignored)
├── output/          # Generated files
├── src/             # Your main scripts and examples
├── tests/           # Test scripts
├── tmp/             # Temporary files
└── utils/           # Core framework (DON'T MODIFY)
    ├── api_factory.py     # API client creation
    ├── config_loader.py   # Configuration validation
    ├── load_n_save.py     # Smart I/O operations
    ├── logger.py          # Security logging with redaction
    ├── path_helpers.py    # Dir constants, type-safe paths
    └── script_runner.py   # Script initialization
```

#### Human, AI, and documentation
```
├── ai/              # AI decisions and prompts
│   ├── decided/         # Instructions
│   ├── prompts/         # Main config (gitignored if contains secrets)
│   └── reports/         # Security patterns (checked in)
├── code_inspection/     # PyCharm Code/Inspect Code reports
├── docs/            # Project documentation
├── files/           # File storage
├── generated_payloads/ # Generated payload files
├── payloads/        # Payload templates
├── schemas/         # Schema definitions
└── wsdl/            # WSDL files
```

## Configuration Requirements

### Mandatory Config Structure
Scripts will exit(1) if these files are missing:

1. **Main Config**: `config/{org}-{env}-config.json`
```json
{
  "global": {
    "api-base-url": "https://api.example.com",
    "tenant-id": "",
    "client-id": ""
  },
  "script-behavior": {
    "rate-limiting": {
      "enabled": false,
      "calls-per-second": 10
    },
    "circuit-breaker": {
      "enabled": false,
      "failure-threshold": 5
    }
  }
}
```

2. **Logging Config**: `config/logging-config.json`
3. **Redaction Patterns**: `config/log-redaction-patterns.json`

### Development Tips

- **PyCharm**: Use Run Configuration (recommended) - handles paths automatically
- **Command Line**: Use `PYTHONPATH=. python src/script.py` or `python -m src.script`
- **Testing**: Use `src/try_me_script.py` to test setup - requires no authentication
- Copy config templates from `config/` before first run
- Scripts require exactly 2 args: `<org_id>` `<env_type>`
- All sensitive data automatically redacted from logs
- Use `DEBUG_LOGGING=1` for verbose output if configured

### Error Patterns

- **Config Missing**: Copy example files from `config/`
- **Invalid Directory**: Use `Dir.CONFIG` not `'config'`
- **Token Issues**: Set `require_token=False` for local processing scripts
- **Import Errors**: Use `PYTHONPATH=.` when running from command line

## Refactoring 3.1 - Code Quality Improvements

This section outlines critical improvements needed to align the codebase with TXO v3.0 principles. Each change requires discussion to determine implementation approach and documentation updates.

### **Process for Each Change**
1. **Discuss the Issue**: Why is this a problem? What's the impact?
2. **Evaluate Solutions**: What are the options? Trade-offs?
3. **Decide Approach**: Which solution fits TXO philosophy best?
4. **Update Documentation**: What ADRs/prompts need updates?
5. **Implement Change**: Make the code changes
6. **Validate**: Test that change works correctly

### **Critical Issues (Must Fix)**

#### 1. Missing Logger Import (Runtime Error)
**File**: `utils/rate_limit_manager.py` (lines 72, 108)
**Issue**: References undefined `logger` variable
**Impact**: Runtime NameError crashes
**Discussion Needed**:
- Should rate_limit_manager use module-level logger?
- Or pass logger as parameter to methods?
- How does this fit with logger setup patterns?

#### 2. Soft-Fail Configuration Access (Violates ADR-027)
**Files Affected**: 7 files with 15+ violations
**Issue**: Using `config.get()` instead of hard-fail `config[]`
**Key Locations**:
- `script_runner.py`: Lines 124, 175, 181-186 (OAuth config)
- `rest_api_helpers.py`: Lines 134-135 (retry config)
- `api_common.py`: Lines 140-141 (jitter config)
- `api_factory.py`: Line 132 (token access)

**Discussion Needed**:
- Which configs should be truly optional vs required?
- How to handle optional vs missing sections?
- Should we differentiate between config structure vs external API responses?

#### 3. Library Code Using sys.exit() (Architectural Issue)
**Files**: `logger.py` (10 calls), `script_runner.py` (6 calls), `config_loader.py` (3 calls)
**Issue**: Libraries control program termination
**Impact**: Cannot handle errors gracefully, testing difficult

**Discussion Needed**:
- Which sys.exit() calls should become exceptions?
- Should `setup_logger()` ever exit or always raise?
- How to maintain "fail fast" philosophy while allowing error handling?

### **Code Quality Issues (Should Fix)**

#### 4. Type Checker Warnings
**File**: `utils/rest_api_helpers.py` (lines 436, 456)
**Issue**: `CaseInsensitiveDict[str]` vs `dict[str, str]` type mismatch
**Discussion Needed**:
- Fix type annotations or cast the response.headers?
- Are we using requests' CaseInsensitiveDict correctly?

#### 5. Variable Shadowing (Code Quality)
**Files**: Multiple files shadow `e`, `yaml`, `pd` variables
**Discussion Needed**:
- Are these false positives or real issues?
- Should we rename variables in except blocks?

#### 6. Unused Imports
**File**: `rate_limit_manager.py` imports unused `Tuple`
**Discussion Needed**:
- Simple cleanup or indicates design issue?

### **Architectural Improvements (Consider)**

#### 7. Global State Anti-Patterns (From Refactoring Roadmap)
**Issue**: Several modules use global state
**Files**: `oauth_helpers.py`, `api_factory.py`, `logger.py`
**Discussion Needed**:
- Is the singleton logger pattern acceptable?
- Should API caching be global or per-instance?
- How to balance convenience vs testability?

#### 8. Complex Methods (Maintainability)
**Issue**: Methods over 100 lines with deep nesting
**Files**:
- `rest_api_helpers.py::_execute_request()` (150+ lines)
- `load_n_save.py::save()` method complexity

**Discussion Needed**:
- What's the target method length limit?
- How to split complex methods while maintaining readability?

#### 9. Memory Management
**Issue**: Thread-local storage and cache management
**Discussion Needed**:
- Are current memory patterns causing issues?
- Should we optimize or leave as-is?

### **Documentation Alignment Issues**

#### 10. Refactoring Prompt Out of Date
**Issue**: ai/prompts/refactoring-xml-ai-prompt-v3.xml.txt references "v2.1 to v3.0" transition
**Discussion Needed**:
- Update to "v3.0 Code Quality" focus?
- What should the new refactoring priorities be?

#### 11. ADR vs Implementation Gaps
**Issue**: Code doesn't follow several ADRs (especially ADR-027)
**Discussion Needed**:
- Should we update ADRs to match reality?
- Or fix code to match ADRs?
- Which ADRs are still valid vs outdated?

### **Validation Scripts Needed**

#### 12. Automated Code Quality Checks
**Need**: Scripts to validate TXO compliance
**Discussion Needed**:
- What should be automatically checked?
- Integration with development workflow?

**Proposed Scripts**:
```bash
# Check for soft-fail patterns
python scripts/validate_hard_fail.py

# Check for sys.exit() in libraries
python scripts/validate_no_exit.py

# Check method complexity
python scripts/validate_method_length.py

# Validate imports and references
python scripts/validate_imports.py
```

### **Priority Recommendations**

**Phase 1 (Critical - Fix Immediately)**:
1. Missing logger import (runtime error)
2. Most critical soft-fail patterns (OAuth, retry config)

**Phase 2 (High - Plan and Discuss)**:
3. sys.exit() strategy in logger.py
4. Configuration access patterns documentation

**Phase 3 (Medium - Iterative Improvement)**:
5. Type checker warnings
6. Method complexity reduction

**Phase 4 (Low - Optional)**:
7. Global state refactoring
8. Memory optimization

### **Discussion Questions for Each Phase**

**For All Changes**:
- Does this change improve code safety/reliability?
- Does it align with TXO hard-fail philosophy?
- What's the migration impact on existing scripts?
- Should this be documented in an ADR?

**For Architecture Changes**:
- Is this solving a real problem or theoretical issue?
- Does the solution fit TXO's simplicity principle?
- What's the testing strategy for the change?

**For Documentation Updates**:
- Which prompts need updating?
- Should this become a new ADR?
- How do we communicate changes to users?