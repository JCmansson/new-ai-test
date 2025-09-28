# TXO Business Architecture Decision Records v3.1

These ADRs define **TXO-specific business rules and organizational patterns** that reflect how TentXO operates,
regardless of the underlying technology.

---

## ADR-B001: Mandatory Organizational Context Parameters

**Status:** MANDATORY
**Date:** 2025-01-01

### Context

TXO operates across multiple organizations and environments. Data mixing and configuration errors must be prevented at
the parameter level.

### Decision

**All scripts require exactly two positional parameters:**

1. `org_id` (first position, never named)
2. `env_type` (second position, never named)
3. Additional parameters may use named arguments (3rd position onwards)

### Implementation

```bash
# ✅ CORRECT
python script.py txo prod
python script.py company1 test --input-file data.csv
python complex_script.py myorg dev arg3 --verbose --retries 5

# ❌ WRONG
python script.py --org-id=txo --env-type=prod
python script.py prod txo  # Wrong order
```

### Consequences

- Positive: Clear data separation, predictable file naming, consistent CLI
- Negative: No flexibility in parameter order
- Mitigation: Helpful error messages guide users to correct usage

---

## ADR-B002: Configuration Injection with Underscore Prefix

**Status:** MANDATORY
**Date:** 2025-01-01

### Context

TXO functions need access to runtime metadata (org, env, tokens) alongside configuration data.

### Decision

Pass single `config` dictionary with underscore-prefixed injected runtime fields.

### Standard Injected Fields

- `_org_id` - Organization identifier from command line
- `_env_type` - Environment type from command line
- `_token` - OAuth token (if acquired)
- Additional runtime data as needed

### Implementation

```python
# Framework injects these automatically
config["_org_id"] = args.org_id
config["_env_type"] = args.env_type
config["_token"] = acquired_token


# Functions receive complete context
def process_data(config: Dict[str, Any]) -> None:
    org_id = config["_org_id"]
    api_url = config["global"]["api-base-url"]
    token = config["_token"]
```

### Consequences

- Positive: Cleaner function signatures, easier testing, complete context
- Negative: Less explicit about dependencies
- Mitigation: Document injected fields clearly in function docstrings

---

## ADR-B003: Hard-Fail Configuration Philosophy

**Status:** MANDATORY
**Date:** 2025-01-01

### Context

TXO values predictable, consistent behavior. Configuration errors should fail immediately and clearly.

### Decision

- **Hard fail** (`dict['key']`) for ALL configuration data - let KeyError propagate
- **Soft fail** (`dict.get('key')`) ONLY for external API responses and optional data
- **No defaults** for configuration values in code

### Implementation

```python
# ✅ CORRECT - Configuration (hard fail)
api_url = config['global']['api-base-url']  # KeyError if missing
rate_config = config['script-behavior']['rate-limiting']
enabled = rate_config['enabled']  # KeyError if malformed

# ✅ CORRECT - External data (soft fail OK)
email = api_response.get('email')  # None OK for missing field
customer_name = external_data.get('name', 'Unknown')

# ❌ WRONG - Configuration with defaults
timeout = config.get('timeout', 30)  # Masks configuration errors
```

### Consequences

- Positive: Fail fast on misconfiguration, no silent errors
- Negative: Must have complete configuration files
- Mitigation: Provide complete templates and clear error messages

---

## ADR-B004: JSON Schema Validation Requirements

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO processes complex configuration and data files. Invalid structure causes runtime errors and data corruption.

### Decision

JSON Schema validation requirements by file type:

- **MUST** validate main configuration files (`{org}-{env}-config.json`)
- **SHOULD** validate large input files and API payloads (RFC 2119)
- **MAY** validate simple data files and outputs

### Implementation

```python
# Main config - always validate
config_loader.validate_schema(config, 'org-env-config-schema.json')

# Large input files - should validate
if file_size > 1MB or record_count > 1000:
    validate_schema(data, 'input-data-schema.json')

# Simple outputs - optional validation
if strict_mode:
    validate_schema(output, 'output-schema.json')
```

### Consequences

- Positive: Catch errors early, consistent data structure, self-documenting
- Negative: Additional schema maintenance overhead
- Mitigation: Generate schemas from examples, version schemas with configs

---

## ADR-B005: Never Print - Always Log

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO needs consistent, structured, searchable output for debugging and audit trails.

### Decision

**Absolute prohibition on print() statements.** All output must use structured logging.

### Logging Levels

- **Debug**: File only (detailed troubleshooting info)
- **Info**: Console + file (normal operation status)
- **Warning/Error**: Console + file (issues requiring attention)

### Debugging Workflow

1. Delete existing log file
2. Run script with debug logging enabled
3. Upload log file to AI for analysis
4. Use structured log data for troubleshooting

### Implementation

```python
# ✅ CORRECT
logger.info("Processing started for %d records", len(data))
logger.debug("API request payload: %s", json.dumps(payload))
logger.error("Failed to process record %s: %s", record_id, error)

# ❌ WRONG
print(f"Processing {len(data)} records")  # Not captured in logs
print("Debug info:", payload)  # Not structured
```

### Consequences

- Positive: All output captured, structured for analysis, AI-friendly debugging
- Negative: Requires logger setup in every module
- Mitigation: Logger setup is mandatory framework requirement

---

## ADR-B006: Hierarchical Logging Context

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO operates across multiple environments, organizations, and API endpoints. Log entries need clear context hierarchy
for traceability.

### Decision

Use square bracket context format: `[Higher/Mid/Lower]` for all operations.

### Context Hierarchy

- **Higher**: Environment level (`Prod`, `Test`, `Dev`)
- **Mid**: Organization/Company level (`CompanyOne`, `TXO`, `ClientABC`)
- **Lower**: API/Operation level (`BusinessCentral`, `SalesOrders`, `CustomerSync`)

### Implementation

```python
# Context building
context = f"[{env_type.title()}/{company_name}/{api_name}]"
logger.info(f"{context} Starting data synchronization")
logger.debug(f"{context} Processing batch of {batch_size} records")
logger.error(f"{context} API call failed: {error_message}")

# Examples
logger.info("[Prod/CompanyOne/BusinessCentral] Retrieved 150 sales orders")
logger.error("[Test/TXO/CustomerAPI] Authentication failed: invalid token")
logger.debug("[Dev/ClientABC/InventorySync] Transforming product data")
```

### Consequences

- Positive: Clear traceability, easy log filtering, environment isolation
- Negative: Longer log messages, context management overhead
- Mitigation: Helper functions for context building, consistent formatting

---

## ADR-B007: Standardized Operation Result Tracking

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO scripts perform bulk operations across multiple entities. Users need clear summaries of what succeeded, failed, and
requires attention.

### Decision

All scripts must use standardized `ProcessingResults` pattern for operation tracking and user-friendly reporting.

### Implementation

```python
@dataclass
class ProcessingResults:
    """Track all operation results for summary reporting"""
    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    expected_errors: int = 0

    def add_result(self, api_name: str, company_id: str, result: OperationResult):
        """Add an operation result"""
        identifier = f"{api_name}/{company_id}/{result.entity_id}"

        if result.success:
            if result.operation == "created":
                self.created.append(identifier)
            elif result.operation == "updated":
                self.updated.append(identifier)
                if result.expected_error:
                    self.expected_errors += 1
        else:
            self.failed.append(f"{identifier}: {result.message}")

    def summary(self) -> str:
        """Generate user-friendly summary"""
        total_success = len(self.created) + len(self.updated)

        if self.failed:
            return (f"❌ Completed with {len(self.failed)} failures: "
                    f"{len(self.created)} created, {len(self.updated)} updated, "
                    f"{len(self.failed)} failed")
        else:
            expected_note = f" ({self.expected_errors} handled expected duplicates)" if self.expected_errors > 0 else ""
            return (f"✅ All {total_success} operations successful: "
                    f"{len(self.created)} created, {len(self.updated)} updated{expected_note}")
```

### Usage Pattern

```python
results = ProcessingResults()

for record in data:
    try:
        if process_record(record):
            results.add_legacy_result("SalesAPI", company_id, record.id, True, "created")
        else:
            results.add_legacy_result("SalesAPI", company_id, record.id, False)
    except Exception as e:
        results.failed.append(f"SalesAPI/{company_id}/{record.id}: {str(e)}")

# Always show summary
logger.info(results.summary())
```

### Consequences

- Positive: Consistent user feedback, clear success/failure tracking, audit trail
- Negative: Additional boilerplate for simple scripts
- Mitigation: Helper methods for common patterns, framework integration

---

## ADR-B008: Token Optional by Default

**Status:** MANDATORY
**Date:** 2025-01-16

### Context

Most TXO scripts process local data and don't require external API authentication. Requiring OAuth setup for simple
scripts creates unnecessary friction.

### Decision

Scripts default to **no authentication required**. API scripts must explicitly request tokens.

### Implementation

```python
# ✅ Local scripts (most common)
config = parse_args_and_load_config("Local data processing")  # No token

# ✅ API scripts (explicit)
config = parse_args_and_load_config("BC sync script", require_token=True)
```

### Consequences

- Positive: Easier onboarding, simpler config for local scripts
- Positive: Clear distinction between local and API scripts
- Negative: Breaking change from previous versions
- Mitigation: Clear documentation and migration examples

---

## ADR-B009: Mandatory Configuration Files

**Status:** MANDATORY
**Date:** 2025-01-16

### Context

TXO values consistency and security. Optional configurations with defaults hide misconfigurations and security
vulnerabilities.

### Decision

Three configuration files are **mandatory** - script exits if any are missing:

1. `{org}-{env}-config.json` - Main business configuration
2. `logging-config.json` - Logging setup and levels
3. `log-redaction-patterns.json` - Security token redaction

### Implementation

```bash
# Required files for txo-prod
config/txo-prod-config.json
config/logging-config.json
config/log-redaction-patterns.json

# Templates provided
config/org-env-config_example.json
config/logging-config.json
config/log-redaction-patterns.json
```

### Consequences

- Positive: Consistent behavior, security always active, fail fast
- Negative: Cannot run without setup
- Mitigation: Provide complete templates, clear setup instructions

---

## ADR-B010: Standardized Project Directory Structure

**Status:** MANDATORY
**Date:** 2025-01-16

### Context

TXO scripts work across multiple projects and environments. Consistent directory structure enables predictable
automation, backup strategies, and team collaboration.

### Decision

Mandatory directory structure for all TXO Python projects:

#### Used by code
```
txo-project-root/
├── config/              # Configuration files (mandatory)
│   ├── templates/       # Example config files (checked in)
│   ├── {org}-{env}-config.json           # Main config (gitignored if contains secrets)
│   ├── {org}-{env}-config-secrets.json   # Secrets (always gitignored)
│   ├── logging-config.json               # Logging setup (checked in)
│   └── log-redaction-patterns.json       # Security patterns (checked in)
├── data/                # Input data files
├── output/              # Generated files and reports
├── files/               # External files used as is
├── logs/                # Log files (gitignored)
├── tmp/                 # Temporary files (gitignored)
├── schemas/             # JSON schema files for validation
├── utils/               # Helper files TXO framework code (do not modify)
├── generated_payloads/            # To be manually validated before moving to payloads/ (gitignored)
├── payloads/            # Files ready to send via API
├── tests/               # Test scripts
├── src/                 # Main scripts
└── wsdl/                # SOAP service definitions (if needed)
```

#### Human, AI, and documentation
```
txo-project-root/
├── ai/                 # AI and human files
│   ├── diecided/       # Patterns defined human and AI together 
│   ├── prompts/        # Prompts to edit and upload to AI
│   └── reports/        # AI generated reports
├── docs/               # Input data files
├── code_inspection/      # For saving PyCharm's Code/Inspect Code.. reports
├── in-depth-readme.md
├── module-dependency-diagram.md
└── README.md
```

### Type-Safe Path Access

Use `Dir.*` constants instead of string literals:

```python
from utils.path_helpers import Dir

# ✅ CORRECT - Type-safe directory access
config_path = get_path(Dir.CONFIG, 'settings.json')
data_file = data_handler.load(Dir.DATA, 'input.csv')
data_handler.save(results, Dir.OUTPUT, 'report.xlsx')

# ❌ WRONG - String literals (typo-prone)
config_path = get_path('config', 'settings.json')
data_file = load('data', 'input.csv')
```

### Directory Constants

- `Dir.CONFIG` - Configuration and secrets files
- `Dir.DATA` - Input data files
- `Dir.OUTPUT` - Generated reports and files
- `Dir.LOGS` - Application log files
- `Dir.TMP` - Temporary processing files
- `Dir.SCHEMAS` - JSON schema validation files
- `Dir.WSDL` - SOAP service definitions
- `Dir.FILES` - General file storage
- `Dir.PAYLOADS` - API request/response samples
- `Dir.GENERATED_PAYLOADS` - Auto-generated API payloads

### Git Configuration

```gitignore
# Generated files
/logs/
/tmp/
/output/

# Secrets and sensitive data
*-secrets.*
*-secrets/
*.secret

# IDE and system files
.idea/
.vscode/
__pycache__/
*.pyc
```

### Consequences

- Positive: Consistent structure across projects, predictable automation
- Positive: IDE autocomplete, no typos, refactoring support
- Positive: Clear separation of concerns (config vs data vs output)
- Negative: Must import Dir constants, rigid structure
- Mitigation: Framework handles directory creation automatically

---

## ADR-B011: Secrets Management and Git Security

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO handles sensitive data (tokens, API keys, passwords) that must never be committed to version control. Secrets
management must be consistent and secure across all environments.

### Decision

Standardized secrets management with git exclusion and flat JSON structure:

1. **Secrets stored** in `{org}-{env}-config-secrets.json`
2. **Git ignore pattern**: `*-secrets.*` in `.gitignore`
3. **Template provided**: `{org}-{env}-config-secrets_example.json` (checked in, empty/example values)
4. **Flat structure only**: No nested objects in secrets files

### Implementation

```json lines
// ✅ CORRECT - txo-prod-config-secrets.json (gitignored)
{
  "client-secret": "actual-secret-value-here",
  "api-token": "real-token-value",
  "database-password": "actual-password"
}

// ✅ CORRECT - txo-prod-config-secrets_example.json (checked in)
{
  "client-secret": "",
  "api-token": "your-api-token-here",
  "database-password": "your-db-password"
}

// ❌ WRONG - Nested structure
{
  "oauth": {
    "client-secret": "value"
    // No nesting allowed
  }
}
```

### Git Configuration

```gitignore
# In .gitignore
*-secrets.*
*-secrets/
*.secret
```

### Consequences

- Positive: No secrets in version control, consistent structure
- Positive: Easy setup with templates, flat structure simplifies access
- Negative: Must maintain separate secrets files per environment
- Mitigation: Clear templates and setup documentation

---

## ADR-B012: Naming Convention Standards

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

Consistent naming conventions improve readability, reduce cognitive load, and support tooling integration across TXO's
multi-format codebase. Different naming conventions also provide visual cues about data origins.

### Decision

Format-specific naming conventions based on community standards:

### Naming Rules by Format

- **Markdown files**: `kebab-case_v1.0.md` (e.g., `user-guide_v1.0.md`, `api-reference_v2.1.md`)
- **JSON keys**: `kebab-case` (e.g., `"api-base-url"`, `"retry-count"`)
- **Python files**: `snake_case.py` (e.g., `data_handler.py`, `api_client.py`)
- **YAML keys**: `snake_case` (e.g., `api_base_url:`, `retry_count:`)

### Visual Data Origin Distinction

The mixed conventions create helpful visual cues in Python code:

```python
# ✅ CORRECT - Clear data source distinction
api_base_url = config['global']['api-base-url']  # kebab-case = JSON origin
timeout_seconds = config['global']['timeout-seconds']  # kebab-case = JSON origin
retry_count = 3  # snake_case = Python variable

# Injected secrets preserve JSON format for consistency
client_token = config['_client-secret']  # kebab-case shows JSON origin
database_password = config['_database-password']  # kebab-case shows JSON origin
```

### Implementation

```bash
# ✅ CORRECT - File names
docs/installation-guide.md
utils/config_loader.py
schemas/api-request-schema.json
deployment/staging-config.yaml

# ✅ CORRECT - JSON keys
{
  "global": {
    "api-base-url": "https://api.example.com",
    "timeout-seconds": 30,
    "rate-limiting": {
      "calls-per-second": 10,
      "burst-size": 1
    }
  }
}

# ✅ CORRECT - YAML keys
database:
  connection_string: "postgresql://..."
  pool_size: 10
  timeout_seconds: 30

# ✅ CORRECT - Python with visual distinction
class ConfigLoader:
    def load_api_config(self):
        base_url = self.config['global']['api-base-url']  # JSON → Python
        return base_url

# ✅ CORRECT - Secrets injection preserves format
def inject_secrets(config: Dict[str, Any], secrets: Dict[str, Any]) -> None:
    for key, value in secrets.items():
        # Preserve kebab-case to show JSON origin
        config[f'_{key}'] = value  # "client-secret" → "_client-secret"
```

### Rationale

- **kebab-case**: Standard for URLs, markdown files, JSON APIs
- **snake_case**: Python PEP 8 standard, YAML community preference
- **Visual distinction**: Different cases immediately show data origin
- **Consistency**: Each format follows its ecosystem conventions
- **No transformation**: JSON keys stay as-is throughout the system

### Consequences

- Positive: Follows community standards, consistent within format
- Positive: Visual cues help developers understand data flow
- Positive: No hidden transformations, what you see is what you get
- Negative: Mixed conventions across formats
- Negative: Slightly awkward kebab-case in Python dict keys
- Mitigation: Clear rules per format, benefits outweigh minor awkwardness

---

## ADR-B013: Documentation Format Standards

**Status:** MANDATORY
**Date:** 2025-01-25

### Context

TXO creates extensive documentation (ADRs, guides, specifications) that must be versioned, organized, and consistently
formatted across teams and projects.

### Decision

Standardized documentation format with mandatory versioning, kebab-case naming, and Markdown-first approach with
structured XML when needed.

### Format Standards

#### **Primary Format: Markdown with Inline XML**

- **Base format**: Markdown (`.md`) for readability and universal support
- **Structured data**: Inline XML elements when precision is needed
- **AI prompts**: Markdown + XML hybrid instead of pure XML files

#### **Naming Convention**

**Format**: `document-name_v1.0.md`

- **Document name**: kebab-case (lowercase, hyphen-separated)
- **Version**: underscore + semantic version (`_v1.0`, `_v2.1`, `_v3.0.1`)
- **Extension**: `.md` (Markdown)

### Versioning Rules

- **Major version** (`v1.0` → `v2.0`): Breaking changes, incompatible updates
- **Minor version** (`v1.0` → `v1.1`): New content, backward-compatible additions
- **Patch version** (`v1.1.0` → `v1.1.1`): Corrections, clarifications, typo fixes

### Version Synchronization

**All documentation in a project should use the same version number as the git tag/release version.**

- **Project at v3.1**: All docs should be `*_v3.1.md`
- **Project at v2.0**: All docs should be `*_v2.0.md`
- **Individual documents**: Do NOT have independent versioning

```bash
# ✅ CORRECT - All docs sync with project version
git tag: v3.1
├── txo-business-adr_v3.1.md
├── txo-technical-standards_v3.1.md
├── utils-quick-reference_v3.1.md
└── module-dependency-diagram_v3.1.md

# ❌ WRONG - Mixed versions create confusion
git tag: v3.1
├── txo-business-adr_v3.1.md
├── utils-quick-reference_v1.0.md    # Out of sync!
└── api-guide_v2.5.md                # Out of sync!
```

### Implementation

```bash
# ✅ CORRECT - TXO documentation naming
txo-business-adr_v3.1.md
utils-quick-reference_v1.0.md
api-integration-guide_v2.0.md
troubleshooting-guide_v1.2.1.md

# ✅ CORRECT - Project-specific docs
customer-sync-specification_v1.0.md
business-central-setup_v2.1.md
data-mapping-rules_v1.0.md

# ❌ WRONG - No versioning
user-guide.md
api-reference.md

# ❌ WRONG - Wrong format
UserGuide_v1.0.md          # PascalCase
user_guide_v1.0.md         # snake_case
api-reference-v1.0.md      # hyphen instead of underscore before version
```

### Document Categories by Purpose

#### **ADRs (Architecture Decision Records)**

- Format: `{scope}-adr_v{version}.md`
- Examples: `txo-business-adr_v3.1.md`, `project-technical-adr_v1.0.md`

#### **Reference Documents**

- Format: `{topic}-reference_v{version}.md`
- Examples: `utils-quick-reference_v1.0.md`, `api-reference_v2.0.md`

#### **Guides and Tutorials**

- Format: `{topic}-guide_v{version}.md`
- Examples: `installation-guide_v1.0.md`, `troubleshooting-guide_v2.1.md`

#### **Specifications**

- Format: `{feature}-specification_v{version}.md`
- Examples: `data-sync-specification_v1.0.md`, `oauth-flow-specification_v1.1.md`

### Version Management Strategy

#### **When to Create New Version**

```bash
# Minor updates - increment minor version
api-reference_v1.0.md → api-reference_v1.1.md

# Major restructure - increment major version
user-guide_v1.2.md → user-guide_v2.0.md

# Typo fixes - increment patch version
installation-guide_v1.0.md → installation-guide_v1.0.1.md
```

#### **Version Archive Strategy**

- **Keep current version** in main directory
- **Archive old versions** in `archive/` subdirectory when superseded
- **Maintain compatibility** for at least one major version

```bash
# Current structure
ai/decided/
├── txo-business-adr_v3.1.md          # Current
├── txo-technical-standards_v3.1.md   # Current
├── utils-quick-reference_v1.0.md     # Current
└── archive/
    ├── txo-business-adr_v3.0.md       # Previous
    └── adr_v3.md                      # Legacy format
```

### Content Structure Standards

#### **Required Header Block**

```markdown
# Document Title v3.1

> **Purpose**: Brief description of what this document covers
> **Audience**: Who should read this (developers, business stakeholders, etc.)
> **Last Updated**: 2025-01-25

## Version History

- **v3.1** (2025-01-25): Added documentation standards
- **v3.0** (2025-01-16): Major restructure with new ADRs
- **v2.1** (2024-12-01): Initial version

---
```

#### **Markdown + XML Hybrid Examples**

**✅ PREFERRED - Readable Markdown with XML precision:**

```markdown
# Utils Quick Reference v1.0

## 🏗️ Script Setup Functions

### Script Initialization (`utils.script_runner`)

```python
# Most common pattern (no authentication)
config = parse_args_and_load_config("Process local data")
```

```xml


<function-signature>
    <name>parse_args_and_load_config</name>
    <params>description: str, require_token: bool = False</params>
    <returns>Dict[str, Any]</returns>
    <injected-fields>_org_id, _env_type, _token</injected-fields>
</function-signature>
```

**❌ AVOID - Pure XML (hard to read):**

```xml

<documentation>
    <module name="script_runner">
        <function name="parse_args_and_load_config">
            <signature>description: str, require_token: bool = False</signature>
            <returns>Dict[str, Any]</returns>
            <description>Parse arguments and load configuration</description>
        </function>
    </module>
</documentation>
```

**❌ AVOID - Pure Markdown (imprecise):**

```markdown
## script_runner module

Function that parses arguments and loads config. Returns a dictionary.
```

#### **ADR-Specific Structure**

```markdown
## ADR-XXX: Title

**Status:** MANDATORY | RECOMMENDED | OPTIONAL | DEPRECATED
**Date:** YYYY-MM-DD

### Context

Why is this decision needed?

### Decision

What is the decision?

### Implementation

How is it implemented? (if applicable)

### Consequences

- Positive: Benefits
- Negative: Drawbacks
- Mitigation: How to address drawbacks

### Example

Code or usage example
```

#### **Standard Footer Template**

All TXO documentation must end with this standardized footer:

```markdown
---

## Version History

**Version:** v3.1 | **Last Updated:** 2025-01-25

### v3.1 (Current)
- Added documentation format standards and version synchronization
- Enhanced security requirements and naming conventions

### v3.0
- Major restructure: separated business and technical ADRs
- Implemented type-safe path management and mandatory config files

---

**Version:** v3.1 | **Domain:** [Document Domain] | **Purpose:** [Brief document purpose]
```

**Footer Guidelines:**

- **Dense history**: Maximum 2-3 version entries, focus on major changes only
- **Current indicator**: Mark active version with "(Current)"
- **Meaningful descriptions**: Explain business impact, not technical details
- **Metadata line**: Version | Domain | Purpose for quick reference
- **Synchronized versioning**: Must match project git tag version

### File Organization

```text
# Project documentation structure
docs/
├── adr/                 # Architecture decisions
│   ├── business-adr_v3.1.md
│   ├── technical-adr_v3.1.md
│   └── archive/
├── guides/              # User guides
│   ├── installation-guide_v1.0.md
│   ├── user-manual_v2.0.md
│   └── archive/
├── reference/           # Reference materials
│   ├── api-reference_v1.0.md
│   ├── utils-reference_v1.0.md
│   └── archive/
└── specifications/      # Technical specifications
    ├── data-sync-spec_v1.0.md
    └── archive/
```

### Git Integration

```gitignore
# Don't ignore documentation
!/docs/**/*.md

# Archive old versions but keep accessible
!/docs/**/archive/*.md
```

### Rationale

- **Markdown-first**: Universal readability, git-friendly, works with all tools
- **XML when needed**: Structured precision for AI consumption, function signatures, metadata
- **Hybrid approach**: Best of both worlds - readable by humans, parseable by AI
- **Semantic versioning**: Clear compatibility and change tracking
- **kebab-case consistency**: Matches TXO naming conventions

### Consequences

- Positive: Clear versioning, organized documentation, easy to find current version
- Positive: Consistent format across teams and projects, readable + structured
- Positive: Historical context preserved in archives
- Positive: Markdown + XML hybrid optimizes for both human and AI consumption
- Negative: More complex naming than simple `.md` files
- Negative: Must remember to update versions and maintain XML structure
- Mitigation: Clear guidelines and examples, version control helps track changes

---

## Summary

These Business ADRs define **how TXO operates** - our organizational patterns, security requirements, and user
experience expectations. They should apply regardless of whether we implement in Python, Node.js, or any other
technology.

The key themes are:

1. **Predictability**: Hard-fail configs, mandatory parameters, consistent structure
2. **Security**: Secrets management, mandatory redaction, no defaults in version control
3. **Usability**: Clear error messages, result summaries, type safety
4. **Traceability**: Hierarchical context, operation tracking, audit trails
5. **Consistency**: Naming conventions, file structure, format standards

These rules reflect TXO's values and operational requirements, separate from technical implementation choices.

---

## Version History

### v3.1 (Current)

- Added documentation format standards and version synchronization
- Enhanced security requirements and naming conventions

### v3.0

- Major restructure: separated business and technical ADRs
- Implemented type-safe path management and mandatory config files

---

**Version:** v3.1   
**Last Updated:** 2025-01-25  
**Domain:** TXO Business Architecture  
**Purpose:** Organizational patterns and operational requirements  