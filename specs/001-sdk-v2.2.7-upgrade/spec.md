# Feature Specification: SDK v2.2.7 Upgrade — API-Key Authentication & Certificate Export

**Feature Branch**: `001-sdk-v2.2.7-upgrade`  
**Created**: 2025-01-19  
**Status**: Draft  
**Input**: User description: "Implement newest Fubon SDK v2.2.7, read documentation and make plan"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - API-Key Authentication Login (Priority: P1) 🎯 MVP

**Scenario**: Developer integrates Fubon MCP Server into workflow using API-Key instead of traditional username/password with PFX certificate.

**Why this priority**: P1 is MVP-critical:
- SDK v2.2.7 NEW FEATURE: API-Key authentication support
- Security enhancement: Users can now use granular API keys with IP whitelisting instead of storing PFX files
- Market requirement: Aligns with Fubon's security recommendations for API access
- Backward compatibility: Existing username/password method STILL WORKS, no breaking changes

**Independent Test**: Can authenticate using API-Key credentials and execute same trading operations as traditional auth. Can independently deploy this without other v2.2.7 features.

**Acceptance Scenarios**:

1. **Given** user has obtained API-Key & Secret from Fubon portal (https://www.fbs.com.tw/TradeAPI/docs/key/), 
   **When** user passes `api_key` + `secret_key` parameters instead of `username` + `password` + `pfx_path`, 
   **Then** SDK authenticates successfully and user can execute trades without PFX file

2. **Given** user has multiple API-Keys with IP restrictions configured, 
   **When** request originates from allowed IP, 
   **Then** authentication succeeds; when from blocked IP, authentication fails with clear error message

3. **Given** API-Key auth is active, 
   **When** user modifies API-Key list in Fubon portal (add/revoke keys), 
   **Then** all existing sessions are force-logged-out (as per Fubon spec)

4. **Given** both traditional auth (PFX) and API-Key auth are available, 
   **When** either method is used, 
   **Then** both work identically for downstream trading operations (no behavioral differences)

---

### User Story 2 - Certificate Export Feature (Priority: P2)

**Scenario**: Developer can export and import Fubon web certificates programmatically, enabling credential rotation and CI/CD integration.

**Why this priority**: P2 feature parity:
- SDK v2.2.7 NEW FEATURE: Credential export functionality
- Enables automated certificate lifecycle management
- Reduces manual credential handling in production
- Supports CI/CD certificate rotation workflows

**Independent Test**: Can export certificate to file and verify exported format. Can independently deploy without API-Key feature (though both shipped in v2.2.7).

**Acceptance Scenarios**:

1. **Given** user is authenticated, 
   **When** user calls certificate export method with password, 
   **Then** certificate is exported in standard format (PFX or equivalent) and saved to specified path

2. **Given** certificate is exported, 
   **When** file is moved to different location and re-imported, 
   **Then** import succeeds and certificate is usable for subsequent authentications

3. **Given** certificate export is performed, 
   **When** export password differs from certificate password, 
   **Then** appropriate error message guides user on password requirements

---

### User Story 3 - SDK Upgrade & Dependency Validation (Priority: P2)

**Scenario**: Entire codebase is validated against SDK v2.2.7 APIs; no breaking changes from v2.2.4 (current version).

**Why this priority**: P2 technical foundation:
- Ensures all existing features continue working
- Documents API change surface
- Validates new enum values for trading parameters
- Confirms backward compatibility

**Independent Test**: Existing test suite passes at ≥80% coverage with v2.2.7; no code changes needed (backward compatible upgrade).

**Acceptance Scenarios**:

1. **Given** current SDK version (implied v2.2.4 or similar), 
   **When** upgraded to v2.2.7, 
   **Then** all existing trading, account, and market data operations behave identically (no breaking changes)

2. **Given** v2.2.7 introduces new enum values (if any), 
   **When** existing code specifies old enum values, 
   **Then** enum values still work (backward compatible)

3. **Given** test suite runs against v2.2.7, 
   **When** all tests execute, 
   **Then** coverage remains ≥80% with no new test code required

---

### Edge Cases

- What happens when API-Key auth is used but session times out? (expect: session re-auth required)
- What if user exports certificate with unsupported password encoding? (expect: clear error + guidance)
- What if v2.2.7 is partially installed (binary missing)? (expect: clear error message + installation instructions)
- What if user attempts API-Key auth but hasn't applied for API-Key yet? (expect: helpful error directing to portal)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support API-Key authentication method (alternative to username/password/PFX)
- **FR-002**: System MUST support certificate export with password protection
- **FR-003**: System MUST maintain 100% backward compatibility with existing PFX-based auth
- **FR-004**: System MUST validate SDK v2.2.7 binary compatibility across Windows/macOS/Linux platforms
- **FR-005**: System MUST update pyproject.toml to pin SDK v2.2.7 as minimum version
- **FR-006**: System MUST document API-Key setup workflow in README (English + Traditional Chinese 繁體中文)
- **FR-007**: System MUST provide bilingual error messages for API-Key auth failures

### Key Entities *(include if feature involves data)*

- **APIKeyCredentials**: Tuple of (api_key: str, secret_key: str, optional_ip_whitelist: list[str])
- **CertificateExportPayload**: (certificate_data: bytes, export_password: str, format: str="PFX")
- **AuthenticationMethod**: Enum {TRADITIONAL_PFX, API_KEY} (newly supported in v2.2.7)

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: API-Key authentication achieves same success rate as traditional PFX auth in integration tests
- **SC-002**: Certificate export succeeds for 100% of tested credential combinations
- **SC-003**: All existing integration tests pass unchanged against v2.2.7 (backward compatibility ≥99.9%)
- **SC-004**: Documentation is bilingual (English + Traditional Chinese) for API-Key setup with 100% coverage of parameters
- **SC-005**: Code coverage remains ≥80% after upgrade (no degradation)
- **SC-006**: V2.2.7 upgrade can be deployed independently without other feature changes

---

## Version Upgrade Notes (v2.2.4 → v2.2.7)

### 2.2.7 (NEW - This Release)
- ✅ **NEW**: API-Key login support + credential export (MAIN FEATURE)
- Reference: [API-Key Documentation](https://www.fbs.com.tw/TradeAPI/docs/trading/api-key-apply/)

### 2.2.6
- Golang SDK version added (not relevant for Python)
- Technical indicators added to REST API

### 2.2.5
- Product price change report query (stocks)
- Short selling quota query enhancements
- Connection management upgrades

### 2.2.4
- Day-trade conditional orders support
- FIFO accounting query support
- `user_def` field validation (ASCII 33-126, max 10 chars)
- Python Web API exception handling (now uses Exception vs callback)

### Platform Support Notes (≥ v2.2.4)
- **Windows 64-bit**: `fubon_neo-2.2.7-cp37-abi3-win_amd64.zip`
- **macOS ARM64**: `fubon_neo-2.2.7-cp37-abi3-macosx_11_0_arm64.zip`
- **macOS x86_64**: `fubon_neo-2.2.7-cp37-abi3-macosx_10_12_x86_64.zip`
- **Linux x86_64**: `fubon_neo-2.2.7-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.zip`

### Python Support
- **Supported**: Python 3.8, 3.9, 3.10, 3.11, 3.12
- **NOT Supported**: Python 3.7 (dropped in v2.0.1)
- **Current project**: Targets Python 3.10+ ✅ (compatible)

---

## Constitution Check (Pre-Design Gate)

| Principle | Assessment | Notes |
|-----------|------------|-------|
| **I. Code Quality** | ✅ PASS | SDK upgrade only; no new code complexity; pre-commit gates apply |
| **II. Testing Standards** | ✅ PASS | Integration tests validate backward compatibility; 80% coverage maintained |
| **III. UX Consistency** | ✅ PASS | Both Python library & VS Code extension use same SDK; dual interface auto-aligned |
| **IV. Performance Requirements** | ✅ PASS | No performance impact; API-Key auth has same latency as PFX auth |
| **V. Story Independence** | ✅ PASS | P1 (API-Key) is independently testable & deployable; P2 stories follow |
| **Specification Clarity** | ✅ PASS | All acceptance criteria defined in BDD format; edge cases listed; no ambiguities |
| **Phase Gating** | ✅ PASS | Upgrade is Phase 2 Foundational work (SDK baseline); unblocks all downstream features |
| **Bilingual Standard** | ✅ PASS | API-Key docs & error messages will be English + Traditional Chinese |

**Gate Result**: ✅ **CONSTITUTION CHECK PASSES** — Proceed to Phase 0 (Research) & Phase 1 (Design).

