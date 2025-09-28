# Module Dependency Diagram v3.1

## Architecture Overview

The TXO Python Template v3.1 follows a layered architecture with clear dependency rules. The v3.1 release adds direct hard-fail imports, UTC timestamp utilities, and complete ADR compliance with enhanced code quality.

## Dependency Layers

### Layer 1: Foundation (No Dependencies)
- `exceptions.py` - Custom exception hierarchy with `ErrorContext`
- `path_helpers.py` - Path management with `Dir` constants

### Layer 2: Core Services
- `logger.py` - Depends on: path_helpers
  - Contains: `TxoLogger`, `TokenRedactionFilter`, `ContextFilter`
- `api_common.py` - Depends on: logger
  - Contains: `RateLimiter`, `CircuitBreaker`, retry utilities

### Layer 3: Data & I/O
- `load_n_save.py` - Depends on: exceptions, logger, path_helpers
  - Direct hard-fail imports (pandas, yaml, openpyxl)
  - Universal save() method with UTC timestamp support

### Layer 4: API Implementation
- `oauth_helpers.py` - Depends on: logger, exceptions
- `rest_api_helpers.py` - Depends on: logger, exceptions, api_common
  - Contains: `MinimalRestAPI`, `SessionManager`, `RestOperationResult`
- `soap_api_helpers.py` - Depends on: logger, exceptions, api_common
- `url_helpers.py` - Depends on: logger

### Layer 5: Orchestration
- `config_loader.py` - Depends on: logger, path_helpers, load_n_save, exceptions
- `api_factory.py` - Depends on: logger, rest_api_helpers, soap_api_helpers, api_common
  - Creates: `RateLimiter`, `CircuitBreaker` instances
- `script_runner.py` - Depends on: config_loader, oauth_helpers, logger, exceptions
  - Token optional by default, hard-fail configuration access

### Layer 6: User Scripts
- `src/*.py` - Depends on: script_runner, api_factory, load_n_save, exceptions, logger, path_helpers

## Visual Dependency Graph

```mermaid
graph TD
    %% Color scheme for different layers
    classDef foundation fill:#0D5ED7,stroke:#444,stroke-width:4px,color:#fff
    classDef core fill:#237046,stroke:#444,stroke-width:4px,color:#fff
    classDef data fill:#870000,stroke:#444,stroke-width:4px,color:#fff
    classDef api fill:#A34700,stroke:#444,stroke-width:4px,color:#fff
    classDef orchestration fill:#4B0082,stroke:#444,stroke-width:4px,color:#fff
    classDef user fill:#2F4F4F,stroke:#444,stroke-width:2px,color:#fff

    %% Foundation Layer (Blue)
    exceptions[exceptions.py<br/>ErrorContext]:::foundation
    path_helpers[path_helpers.py<br/>Dir constants]:::foundation

    %% Core Services (Green)
    logger[logger.py<br/>TokenRedactionFilter<br/>ContextFilter]:::core
    api_common[api_common.py<br/>RateLimiter<br/>CircuitBreaker]:::core

    %% Data Layer (Red)
    load_n_save[load_n_save.py<br/>Universal save]:::data

    %% API Implementation (Orange)
    rest_api_helpers[rest_api_helpers.py<br/>SessionManager]:::api
    soap_api_helpers[soap_api_helpers.py]:::api
    oauth_helpers[oauth_helpers.py]:::api
    url_helpers[url_helpers.py]:::api

    %% Orchestration (Purple)
    config_loader[config_loader.py]:::orchestration
    api_factory[api_factory.py<br/>ApiManager]:::orchestration
    script_runner[script_runner.py<br/>Token optional]:::orchestration
    concurrency[concurrency.py]:::orchestration

    %% User Scripts (Gray)
    user_script[src/*.py]:::user

    %% Dependencies
    logger --> path_helpers

    api_common --> logger

    load_n_save --> exceptions
    load_n_save --> logger
    load_n_save --> path_helpers

    oauth_helpers --> logger
    oauth_helpers --> exceptions

    rest_api_helpers --> logger
    rest_api_helpers --> exceptions
    rest_api_helpers --> api_common

    soap_api_helpers --> logger
    soap_api_helpers --> exceptions
    soap_api_helpers --> api_common

    url_helpers --> logger

    config_loader --> logger
    config_loader --> path_helpers
    config_loader --> load_n_save
    config_loader --> exceptions

    api_factory --> logger
    api_factory --> rest_api_helpers
    api_factory --> soap_api_helpers
    api_factory --> api_common

    concurrency --> logger
    concurrency --> exceptions

    script_runner --> config_loader
    script_runner --> oauth_helpers
    script_runner --> logger
    script_runner --> exceptions

    user_script --> script_runner
    user_script --> api_factory
    user_script --> load_n_save
    user_script --> exceptions
    user_script --> logger
    user_script --> path_helpers
    user_script --> concurrency

    %% Legend
    subgraph Legend
        L1[Foundation - No deps]:::foundation
        L2[Core - Basic deps]:::core
        L3[Data - I/O ops]:::data
        L4[API - External]:::api
        L5[Orchestration]:::orchestration
        L6[User Scripts]:::user
    end
```

## Key Sequence Flows

### Script Initialization (v3.1)

```mermaid
sequenceDiagram
    participant User
    participant Script as src/script.py
    participant Runner as script_runner
    participant Config as config_loader
    participant OAuth as oauth_helpers
    participant Logger as logger

    User->>Script: python script.py org env
    Script->>Runner: parse_args_and_load_config()

    Note over Runner: require_token=False by default

    Runner->>Logger: setup_logger(org_id)

    Note over Logger: Exit if configs missing:<br/>- logging-config.json<br/>- log-redaction-patterns.json

    Runner->>Config: load_config(org, env)
    Config->>Config: load JSON files
    Config->>Config: validate schema (mandatory)
    Config->>Config: inject secrets
    Config-->>Runner: config dict

    alt Token Required (explicit)
        Runner->>OAuth: get_client_credentials_token()
        OAuth->>OAuth: check cache
        alt Token Cached
            OAuth-->>Runner: cached token
        else Token Expired
            OAuth->>OAuth: request new token
            OAuth-->>Runner: new token
        end
        Runner->>Config: inject _token
    end

    Runner-->>Script: config with _org_id, _env_type, [_token]
    Script->>Script: main() executes
```

### API Call with v3.1 Resilience

```mermaid
sequenceDiagram
    participant Script as src/api_script.py
    participant Factory as api_factory
    participant API as MinimalRestAPI
    participant RateLimiter
    participant CircuitBreaker
    participant SessionMgr as SessionManager
    participant External as External API

    Script->>Factory: create_rest_api(config)
    Factory->>Factory: parse nested config

    alt Rate Limiting Enabled
        Factory->>RateLimiter: new RateLimiter(calls_per_second)
    end

    alt Circuit Breaker Enabled
        Factory->>CircuitBreaker: new CircuitBreaker(threshold, timeout)
    end

    Factory->>API: MinimalRestAPI(token, limiter, breaker)
    Factory-->>Script: api instance

    Script->>API: api.get(url)

    API->>CircuitBreaker: is_open()?
    alt Circuit Open
        CircuitBreaker-->>API: true
        API-->>Script: ApiOperationError("Circuit open")
    else Circuit Closed
        CircuitBreaker-->>API: false

        API->>RateLimiter: wait_if_needed()
        Note over RateLimiter: Token bucket algorithm

        API->>SessionMgr: get_session(key)
        Note over SessionMgr: Thread-local + LRU cache<br/>Max 50 sessions
        SessionMgr-->>API: session (reused or new)

        API->>External: HTTP GET

        alt Success (200)
            External-->>API: response
            API->>CircuitBreaker: record_success()
            API-->>Script: data

        else Rate Limited (429)
            External-->>API: 429 + Retry-After
            API->>API: exponential backoff + jitter
            API->>External: retry

        else Async Operation (202)
            External-->>API: 202 + Location header
            API->>API: _handle_async_operation()

            loop Poll until complete or timeout
                API->>API: wait(Retry-After + jitter)
                API->>External: GET Location
                alt Complete (200)
                    External-->>API: final result
                    API-->>Script: result
                else Still Processing (202)
                    External-->>API: 202
                    Note over API: Continue polling
                else Timeout
                    API-->>Script: ApiTimeoutError
                end
            end

        else Server Error (5xx)
            External-->>API: 500
            API->>CircuitBreaker: record_failure()
            API->>API: retry with backoff
        end
    end
```

### Universal Save with Type Detection

```mermaid
sequenceDiagram
    participant Script as src/script.py
    participant DataHandler as TxoDataHandler
    participant PathHelper as path_helpers
    participant FileSystem as File System

    Script->>DataHandler: save(data, Dir.OUTPUT, "file.json")

    Note over DataHandler: Direct hard-fail imports<br/>pandas/yaml/openpyxl at module top

    DataHandler->>DataHandler: detect type from data + extension

    alt DataFrame detected
        Note over DataHandler: pandas already imported<br/>at module top
        alt .csv extension
            DataHandler->>DataFrame: to_csv()
        else .xlsx extension
            Note over DataHandler: openpyxl already imported
            DataHandler->>DataFrame: to_excel()
        else .json extension
            DataHandler->>DataFrame: to_json()
        end
    else Dict/List detected
        alt .json extension
            DataHandler->>DataHandler: DecimalEncoder
            DataHandler->>DataHandler: json.dumps()
        else .yaml extension
            Note over DataHandler: yaml already imported
            DataHandler->>DataHandler: yaml.dump()
        end
    else String detected
        DataHandler->>DataHandler: write as text
    end

    DataHandler->>PathHelper: get_path(Dir.OUTPUT, "file.json")

    Note over PathHelper: Type-safe Dir constant<br/>No string literals

    PathHelper->>PathHelper: resolve path
    PathHelper-->>DataHandler: Path object

    DataHandler->>FileSystem: write file
    FileSystem-->>DataHandler: success
    DataHandler-->>Script: Path to saved file
```

---

**For technical refactoring guidance, see:**
- **Framework Development**: `ai/reports/refactoring.md`
- **Function Reference**: `ai/decided/utils-quick-reference_v3.1.md`
- **Architecture Decisions**: `ai/decided/txo-business-adr_v3.1.md`
- **Technical Standards**: `ai/decided/txo-technical-standards_v3.1.md`

---

**Version:** v3.1  
**Last Updated:** 2025-09-28  
**Domain:** Module Dependencies  
**Purpose:** Visual architecture overview and flow understanding  