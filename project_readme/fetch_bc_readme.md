# Business Central Data Fetch Script

> **Problem Solved**: Validate and export Business Central settings from multiple companies and API endpoints
> **Get Running**: 5 minutes from setup to first data export

## What This Solves

**Business Need**: Extract intercompany configuration data from Business Central across multiple companies to validate settings consistency.

**Before This Script**:
- Manual API testing for each company/endpoint combination
- No systematic way to compare settings across companies
- Time-consuming validation of intercompany configurations

**After This Script**:
- Automated data extraction from all configured companies
- Single Excel file with organized data sheets
- Clear success/failure reporting for each API call

---

## Quick Start (5 Minutes)

### 1. Setup Configuration (2 minutes)

```bash
# Copy configuration templates to config directory
cp chris-test-config.json config/
cp chris-test-config-secrets.json config/

# Edit chris-test-config.json - add your Azure AD app client ID
{
  "global": {
    "client-id": "YOUR_CLIENT_ID_HERE"
  }
}

# Edit chris-test-config-secrets.json - add your client secret
{
  "client-secret": "YOUR_CLIENT_SECRET_HERE"
}
```

### 2. Run the Script (1 minute)

```bash
python src/fetch_bc_data.py chris test

# Expected output:
# [TestSE/AFHS/IntercompanyPartner] Starting API call
# [TestSE/AFHS/IntercompanyPartner] ✅ Retrieved 5 records
# ...
# ✅ All 6 API calls successful
```

### 3. Find Your Results

**Excel File Location**: `output/chris-test-bc-data_2025-09-30T123456Z.xlsx`

**Excel Structure**:
- One sheet per company/API combination
- Sheet names: `TestSE_AFHS_IntercompanyPartner`, `TestSE_TXO_IntercompanySetup`, etc.
- All fields from API response included

---

## Prerequisites

### Required
- Python 3.8 or higher
- Azure AD application with Business Central API permissions
- Client ID and Client Secret from Azure AD app registration

### Dependencies
All dependencies are in `pyproject.toml`:
```bash
pip install -r requirements.txt
```

Key packages: requests, pandas, openpyxl

---

## Configuration Overview

### Main Configuration: chris-test-config.json

```json
{
  "global": {
    "tenant-id": "c1061658-0240-4cbc-8da5-165a9caa30a3",
    "client-id": "YOUR_CLIENT_ID_HERE",
    "oauth-scope": "https://api.businesscentral.dynamics.com/.default"
  },
  "business-central": {
    "base-url": "https://api.businesscentral.dynamics.com/v2.0",
    "environments": ["TestSE"],
    "companies": ["AFHS", "TXO", "CRONUS SE"],
    "apis": ["IntercompanyPartner", "IntercompanySetup"]
  }
}
```

**Easy Extension**: Add more environments, companies, or APIs to the arrays.

### Secrets Configuration: chris-test-config-secrets.json

```json
{
  "client-secret": "YOUR_SECRET_HERE"
}
```

**Security Note**: This file is automatically gitignored by `*-secrets.*` pattern.

**JSON Schema**: See `schemas/chris-test-config-schema.json` for validation rules.

---

## Usage

### Basic Usage
```bash
python src/fetch_bc_data.py chris test
```

### Command Line Format
```bash
python src/fetch_bc_data.py <org_id> <env_type>
```

**Parameters**:
- `org_id`: Organization identifier (e.g., chris, txo)
- `env_type`: Environment type (e.g., test, prod)

### PyCharm Run Configuration
1. Right-click `fetch_bc_data.py`
2. Select "Run 'fetch_bc_data'"
3. Edit configuration to add parameters: `chris test`

---

## Output Contract

### Excel File
**Filename Format**: `{org_id}-{env_type}-bc-data_{timestamp}.xlsx`

**Example**: `chris-test-bc-data_2025-09-30T143045Z.xlsx`

**Sheet Naming**: `{Environment}_{Company}_{API}`
- `TestSE_AFHS_IntercompanyPartner`
- `TestSE_TXO_IntercompanySetup`
- etc.

**Location**: `output/` directory

**Content**: All fields from the OData API response, one row per record.

---

## Logging Contract

### Log Locations
- **Console**: INFO level and above (normal operation status)
- **File**: `logs/app.log` (includes DEBUG level for troubleshooting)

### Key Log Messages

**Success**:
```
[TestSE/AFHS/IntercompanyPartner] ✅ Retrieved 5 records
✅ All 6 API calls successful
```

**Warnings** (non-fatal):
```
[TestSE/TXO/IntercompanySetup] ⚠️  No records returned (empty response)
```

**Errors**:
```
[TestSE/CRONUS SE/IntercompanyPartner] ❌ 404 - Not Found
❌ Completed with 1 failures: 5 successful, 1 failed
```

### Debug Mode
Enable detailed logging by setting in config:
```json
{
  "script-behavior": {
    "debug-mode": true,
    "verbose-logging": true
  }
}
```

---

## Processing Results Summary

### Success Message Examples
```
✅ SUCCESSFUL API CALLS:
  [TestSE/AFHS/IntercompanyPartner]: 5 records
  [TestSE/AFHS/IntercompanySetup]: 1 record
  [TestSE/TXO/IntercompanyPartner]: 3 records
```

### Warning Message Examples
```
⚠️  WARNINGS:
  [TestSE/CRONUS SE/IntercompanySetup]: 0 records (empty response)
```

### Failure Message Examples
```
❌ FAILED API CALLS:
  [TestSE/CRONUS SE/IntercompanyPartner]: 404 - Not Found
  [TestSE/TXO/IntercompanySetup]: 401 - Unauthorized
```

### Overall Status
```
================================================================================
✅ All 6 API calls successful (1 warnings)
================================================================================

OR

================================================================================
❌ Completed with 2 failures: 4 successful, 0 warnings, 2 failed (Total: 6 calls)
================================================================================
```

**Script Behavior**:
- Continues processing all combinations even if some fail
- Empty responses logged as warnings (not failures)
- HTTP errors logged as failures but don't stop execution

---

## Troubleshooting

### Config file not found
**Error**: `Config file not found: config/chris-test-config.json`

**Solution**: 
```bash
cp chris-test-config.json config/
# Edit the file to add your client-id
```

### Authentication failed (401)
**Error**: `[TestSE/AFHS/IntercompanyPartner] ❌ 401 - Unauthorized`

**Causes**:
1. Invalid client-secret in `chris-test-config-secrets.json`
2. Expired or incorrect client-id in `chris-test-config.json`
3. Insufficient API permissions on Azure AD app

**Solution**:
1. Verify client-id and client-secret are correct
2. Check Azure AD app has Business Central API permissions
3. Ensure OAuth scope is correct: `https://api.businesscentral.dynamics.com/.default`

### Missing business-central configuration
**Error**: `Missing 'business-central' configuration section`

**Solution**: Add the `business-central` section to config file:
```json
{
  "business-central": {
    "base-url": "https://api.businesscentral.dynamics.com/v2.0",
    "environments": ["TestSE"],
    "companies": ["AFHS", "TXO"],
    "apis": ["IntercompanyPartner", "IntercompanySetup"]
  }
}
```

### No data retrieved
**Error**: `⚠️  No data retrieved - Excel file not created`

**Cause**: All API calls failed or returned empty responses

**Solution**:
1. Check log file for specific errors: `logs/app.log`
2. Verify company names match Business Central exactly (case-sensitive)
3. Verify API names are correct OData entity names
4. Test API access manually in browser or Postman

### Company not found (404)
**Error**: `[TestSE/INVALID/IntercompanyPartner] ❌ 404 - Not Found`

**Cause**: Company name doesn't exist in the environment

**Solution**: 
1. Verify company technical names in Business Central
2. Update `companies` array in config with correct names
3. Company names are case-sensitive

### API endpoint not found
**Error**: `[TestSE/TXO/InvalidAPI] ❌ 404 - Not Found`

**Cause**: API endpoint name is incorrect

**Solution**: 
1. Verify OData API names in Business Central API documentation
2. Update `apis` array in config with correct endpoint names
3. Common valid names: IntercompanyPartner, IntercompanySetup, Customer, Vendor

---

## Next Steps

**For detailed documentation**: See `in-depth-readme.md` for:
- Architecture and design decisions
- Complete configuration options
- Error handling strategies
- Extension and customization guide

**For TXO framework details**: See `ai/decided/` directory:
- `txo-business-adr_v3.1.md` - Business rules and patterns
- `txo-technical-standards_v3.1.md` - Python implementation standards
- `utils-quick-reference_v3.1.md` - Available utility functions

---

**Version:** 1.0  
**Last Updated:** 2025-09-30  
**Script**: fetch_bc_data.py  
**Purpose**: Quick start guide for Business Central data extraction
