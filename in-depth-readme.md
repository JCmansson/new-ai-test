# In-Depth README --- Fetch Business Central Data

## 1. Introduction

This document supplements the root `README.md` by providing **design
rationale, advanced configuration, and maintenance guidance**.\
It is intended for maintainers, advanced developers, and auditors who
need to understand the **why** behind the implementation decisions.

This aligns with ADR-B009 (Script Documentation) and references ADRs
B002--B012.

------------------------------------------------------------------------

## 2. Architecture & Design Rationale

-   **Schema validation (ADR-B004):** ensures predictable,
    contract-based inputs.\
-   **UTC filenames (ADR-B006):** lexicographically sortable,
    timezone-safe.\
-   **ProcessingResults (ADR-B007):** standardized
    machine/human-readable summaries.\
-   **Flat secrets (ADR-B011):** simpler validation, avoids ambiguity.

------------------------------------------------------------------------

## 3. Configuration --- Full Details

This section expands the overview in `README.md` with **deep
explanations**.

### Script Behavior

-   `api-delay-seconds` → throttle between requests.\
-   `api-timeouts` → rest, soap, wsdl, async.\
-   `retry-strategy` → max retries, backoff-factor.\
-   `jitter` → randomized delays to avoid thundering herd.\
-   `rate-limiting` → calls-per-second and burst-size.\
-   `circuit-breaker` → failure thresholds and reset timers.\
-   `batch-handling` → read/update/vat batch sizes.\
-   `debug-mode`, `verbose-logging`, `enable-progress-bars`.

### Advanced Examples

Include extended examples showing overrides and their impact.

------------------------------------------------------------------------

## 4. Error Handling & Recovery

-   **HelpfulError taxonomy:** schema validation, OAuth failure,
    timeouts, save failures.\
-   **Expected vs unexpected:** when retries are applied vs fail-fast.\
-   **Empty results:** treated as warnings by default, configurable
    policy.\
-   **Circuit breaker behavior:** when and how API calls are suspended.

------------------------------------------------------------------------

## 5. Developer Notes

Guidelines for extending or maintaining the script:

-   **Add new API endpoints:** extend `business-central.apis` in
    config.\
-   **Support new output formats:** update `utils/load_n_save.py`,
    ensure ADR-B006 compliance.\
-   **Extend logging:** when to add new contexts, integration with TXO
    log aggregator.

------------------------------------------------------------------------

## 6. Integration with TXO Utilities

This script integrates with standard TXO utilities:

-   `TxoDataHandler` --- file and data management.\
-   `script_runner` --- argument parsing, config loading.\
-   `HelpfulError` --- standardized error messaging.

See also: `utils-quick-reference_v3.1.md`.

------------------------------------------------------------------------

## 7. References

-   ADRs: B002--B012\
-   `utils-quick-reference_v3.1.md`\
-   `schemas/org-env-config-schema.json`\
-   `txo-technical-standards_v3.1.md`

------------------------------------------------------------------------
