# Implementation Plan: SDK v2.2.7 Upgrade — API-Key Authentication & Certificate Export

**Branch**: `001-sdk-v2.2.7-upgrade` | **Date**: 2025-01-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-sdk-v2.2.7-upgrade/spec.md`

**Note**: This plan is filled in following the `.specify/templates/plan-template.md` workflow. All phases follow the Constitution (Phase gating, Test-First, TDD, bilingual docs).

---

## Summary

Upgrade Fubon MCP Server from SDK v2.2.4 (or similar) to **v2.2.7**, introducing:
1. **API-Key authentication** (new security model: API key + secret instead of username + PFX)
2. **Certificate export** (programmatic credential lifecycle management)
3. **Backward compatibility** (existing PFX-based auth unchanged)

Primary user stories:
- **P1 MVP**: API-Key login method (new SDK feature, independent & deployable alone)
- **P2**: Certificate export functionality (new SDK feature, independent & deployable alone)
- **P2**: Validation that v2.2.7 has no breaking changes (ensures all existing tests pass)

---

## Technical Context

**Language/Version**: Python 3.10+ ✅ (SDK v2.2.7 supports 3.8-3.12)  
**Primary Dependencies**: 
  - `fubon_neo>=2.2.7` (currently likely 2.2.4; upgrade to exact 2.2.7)
  - `fastmcp>=0.1.0`, `mcp>=1.0.0`, `pydantic>=2.0.0` (unchanged)

**Storage**: N/A (no new data models; API-Key is in-memory credential)

**Testing**: `pytest>=7.0.0` with `--cov` (integration tests validate backward compatibility)

**Target Platform**: 
  - Windows 64-bit, macOS (ARM64 + x86_64), Linux x86_64 (multi-platform binary)
  - Tested on Windows primarily; macOS/Linux validation required

**Project Type**: Single server (monolith in `fubon_api_mcp_server/server.py`)

**Performance Goals**: 
  - API-Key auth latency = PFX auth latency (no degradation)
  - Certificate export <100ms for typical 2KB cert

**Constraints**: 
  - Backward compatibility required (no breaking changes to existing APIs)
  - SDK binary must be installed & validated (not built from source)
  - Bilingual error messages for API-Key auth (English + Traditional Chinese 繁體中文)

**Scale/Scope**: 
  - Upgrade scope: Low (new authentication method, SDK internals; existing MCP tools unchanged)
  - Integration scope: Medium (update pyproject.toml, config.py, server.py init, tests)
  - Testing scope: High (validate all existing features work with v2.2.7)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constraint | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality** | ✅ PASS | SDK upgrade only; no new logic; pre-commit gates apply automatically |
| **II. Testing Standards** | ✅ PASS | Integration tests will validate backward compatibility at ≥80% |
| **III. UX Consistency** | ✅ PASS | Both interfaces (lib + VS Code ext) use same SDK; auto-aligned |
| **IV. Performance** | ✅ PASS | No performance impact from auth method change |
| **V. Story Independence** | ✅ PASS | P1 & P2 stories independently testable & deployable |
| **Specification Clarity** | ✅ PASS | BDD acceptance criteria defined; edge cases documented |
| **Phase Gating** | ✅ PASS | Upgrade is Phase 2 Foundational (SDK baseline); unblocks features |
| **Bilingual Docs** | ✅ PASS | API-Key setup guide will be English + 繁體中文 |

**Gate Result**: ✅ **PASSED** — Proceed to Phase 0 (Research) & Phase 1 (Design).

---

## Project Structure

### Documentation (this feature)

```text
specs/001-sdk-v2.2.7-upgrade/
├── spec.md              # Feature specification (user scenarios, requirements)
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (resolve NEEDS CLARIFICATION items)
├── data-model.md        # Phase 1 output (entities, schemas)
├── quickstart.md        # Phase 1 output (quick integration guide)
├── contracts/           # Phase 1 output (API contracts / types)
└── tasks.md             # Phase 2 output (task list with dependencies)
```

### Source Code (repository root)

```text
fubon_api_mcp_server/
├── config.py            # Environment config (update to support API_KEY env vars)
├── server.py            # MCP server main (update SDK init to support API-Key auth)
├── utils.py             # Utilities (add API-Key credential validation)
├── account_service.py   # Account operations (no changes needed; SDK handles)
├── trading_service.py   # Trading operations (no changes needed; SDK handles)
├── market_data_service.py # Market data (no changes needed; SDK handles)
└── __init__.py          # Package init (no changes expected)

tests/
├── test_account_info.py              # Existing tests (must pass with v2.2.7)
├── test_auth_apikey.py               # NEW: API-Key authentication tests
├── test_certificate_export.py        # NEW: Certificate export tests
└── test_sdk_compatibility.py         # NEW: SDK v2.2.7 compatibility validation

wheels/
└── fubon_neo-2.2.7-cp37-abi3-win_amd64.whl  # SDK v2.2.7 binary (to be downloaded)

pyproject.toml           # Update: fubon_neo>=2.2.7 (currently unspecified or <2.2.7)
```

**Structure Decision**: 
- **Single project** — Monolith structure unchanged
- **Config changes**: Add `API_KEY` & `API_SECRET` environment variables (alongside existing `FUBON_USERNAME`, `FUBON_PASSWORD`, `FUBON_PFX_PATH`)
- **SDK init changes**: Detect auth method (API-Key vs PFX) and initialize accordingly
- **Test additions**: New test files for API-Key flow & certificate export; existing tests re-run to validate backward compatibility

---

## Complexity Tracking

*Justification for any Constitution Check violations (if applicable)*

| Constraint | Violation? | Why Needed | Simpler Alternative Rejected Because |
|-----------|-----------|-----------|--------------------------------------|
| Code Quality | ❌ No | Pre-commit gates apply automatically | N/A |
| Testing Standards | ❌ No | Integration tests validate ≥80% coverage | N/A |
| Bilingual Docs | ❌ No | API-Key guides will be bilingual from start | N/A |
| Backward Compat | ❌ No | SDK v2.2.7 is backward compatible (no breaking changes) | N/A |

**No violations** — This is a straightforward SDK upgrade with backward compatibility.

---

## Phase Timeline & Dependencies

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately ✅
- **Phase 2 (Foundational)**: Depends on Phase 1 completion
  - Task: Download & validate SDK v2.2.7 binary (all platforms)
  - Task: Update pyproject.toml to require `fubon_neo>=2.2.7`
  - Task: Update config.py for API-Key environment variables
  - Task: Update server.py SDK initialization to support both auth methods
  - **CRITICAL**: Phase 2 BLOCKS all Phase 3+ stories until complete
- **Phase 3 (P1 Story - API-Key Auth)**: Depends on Phase 2 completion
  - Subtasks: Test API-Key login, validate trading operations
- **Phase 4 (P2 Story - Certificate Export)**: Depends on Phase 2 completion
  - Subtasks: Test cert export, test cert import, test password handling
- **Phase 5 (P2 Story - Compatibility Validation)**: Depends on Phase 2 completion
  - Subtasks: Run full test suite, validate coverage ≥80%
- **Phase 6 (Polish)**: Depends on all Phase 3-5 completion
  - Documentation updates, changelog entry, version bump

### Parallel Opportunities

- Phase 1 tasks can parallelize (environment setup independent)
- Phase 2 tasks can mostly parallelize (config changes are independent)
- Phase 3, 4, 5 stories CAN run in parallel (different test files, different SDK features)

---

## Key Decisions

1. **Authentication Method Selection**
   - **Decision**: Support BOTH API-Key and PFX auth simultaneously (no forced migration)
   - **Rationale**: Backward compatibility; users can adopt at their own pace
   - **Implementation**: Detect auth method based on provided credentials (if `api_key` in env → API-Key; else → PFX)

2. **Configuration Management**
   - **Decision**: Use environment variables for both auth methods
   - **Rationale**: Aligns with 12-factor app principles; supports CI/CD & cloud deployments
   - **Environment variables**:
     - Existing: `FUBON_USERNAME`, `FUBON_PASSWORD`, `FUBON_PFX_PATH`, `FUBON_PFX_PASSWORD`
     - NEW: `FUBON_API_KEY`, `FUBON_API_SECRET`

3. **Certificate Export API Design**
   - **Decision**: Add helper function in `config.py` or new `credentials.py` module
   - **Rationale**: Separate credential management from SDK initialization
   - **Function signature**: `export_certificate(password: str, output_path: str) -> bool`

4. **Testing Strategy**
   - **Decision**: Integration tests (not unit tests) for auth methods
   - **Rationale**: Auth flows require live SDK interaction; mocking provides false confidence
   - **Test scope**: Authenticate → Execute simple trade query → Verify success
   - **Backward compat test**: Run entire existing test suite unchanged

5. **Documentation Approach**
   - **Decision**: Bilingual (English + Traditional Chinese 繁體中文) README section + docstrings
   - **Rationale**: Fubon API audience is Taiwanese; honor bilingual standard from Constitution
   - **Content**: API-Key setup workflow from Fubon portal, parameter descriptions, error handling

---

## Research Phase (Phase 0) — PENDING

Before proceeding to Phase 1 design, the following items require clarification:

- [ ] **SDK Binary Availability**: Confirm SDK v2.2.7 wheel files are available on official Fubon site (not just as ZIP)
- [ ] **API-Key Signature Format**: Does API-Key use HMAC-SHA256 or other signature scheme? (affects error handling)
- [ ] **Session Timeout on Key Change**: How long until session is force-logged-out after API-Key list change? (affects production monitoring)
- [ ] **Certificate Format**: Does export produce PFX, PEM, or other format? (affects compatibility with existing cert paths)
- [ ] **Existing pyproject.toml fubon_neo pinning**: Is current version pinned or floating? (affects upgrade complexity)

**Research Phase Output**: `research.md` (to be generated) will resolve all above items.

---

## Design Phase (Phase 1) — PENDING

Once research is complete, Phase 1 will generate:

- [ ] **data-model.md**: Define `APIKeyCredentials`, `CertificatePayload`, `AuthMethod` enum
- [ ] **contracts/**: API interface documentation (auth methods, error codes)
- [ ] **quickstart.md**: "How to use API-Key with Fubon MCP Server in 5 minutes"
- [ ] **Agent context update**: Run `.specify/scripts/powershell/update-agent-context.ps1 -AgentType copilot`
  - Add `fubon_neo v2.2.7`, `API-Key authentication`, `certificate export` to context

---

## Acceptance Criteria

Implementation is complete when:

1. ✅ **Backward Compatibility**: All existing tests pass unchanged with v2.2.7 (no code changes to MCP tools)
2. ✅ **API-Key Auth Works**: New tests authenticate using API-Key + Secret and execute trades successfully
3. ✅ **Certificate Export Works**: Export function succeeds for valid credentials
4. ✅ **Dual Interface**: Both Python library & VS Code extension work with new SDK (auto-aligned via shared SDK)
5. ✅ **Bilingual Docs**: Setup guides for API-Key auth in English + Traditional Chinese
6. ✅ **Coverage Maintained**: Test coverage ≥80% (no degradation)
7. ✅ **pyproject.toml Updated**: `fubon_neo>=2.2.7` specified as minimum version
8. ✅ **Pre-commit Passes**: All code quality gates (Black, isort, flake8, mypy) pass

---

## Next Steps

1. **Execute Phase 0 (Research)**: 
   - Fetch SDK v2.2.7 documentation from Fubon API site
   - Resolve all NEEDS CLARIFICATION items in this plan
   - Generate `research.md` with findings
   
2. **Execute Phase 1 (Design)**:
   - Generate `data-model.md` with entity schemas
   - Generate `contracts/` with API interface definitions
   - Generate `quickstart.md` with integration guide
   - Update agent context
   
3. **Execute Phase 2 (Foundational)**:
   - Download SDK v2.2.7 wheels for all platforms
   - Update pyproject.toml, config.py, server.py
   - Validate SDK binary installation
   
4. **Execute Phase 3-5 (Stories)**:
   - Implement API-Key auth (P1)
   - Implement certificate export (P2)
   - Validate backward compatibility (P2)
   
5. **Execute Phase 6 (Polish)**:
   - Update README with bilingual API-Key setup
   - Update CHANGELOG with v2.2.7 changes
   - Bump version to reflect SDK upgrade

---

**Version**: 1.0.0 | **Created**: 2025-01-19 | **Status**: Draft → Ready for Phase 0 Research

