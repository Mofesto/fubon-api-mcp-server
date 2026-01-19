# Tasks: SDK v2.2.7 Upgrade — API-Key Authentication & Certificate Export

**Feature Branch**: `001-sdk-v2.2.7-upgrade`  
**Generated**: 2025-01-19  
**Status**: Ready for Execution  
**Total Tasks**: 31 | **Setup**: 3 | **Foundational**: 6 | **P1 Story (API-Key Auth)**: 7 | **P2 Story (Certificate Export)**: 8 | **P2 Story (Compatibility)**: 4 | **Polish**: 3

---

## Execution Strategy

### MVPs & Delivery Milestones

- **MVP v0.1** (Minimal Viable Upgrade): Phase 1 + Phase 2 Foundational
  - SDK v2.2.7 binary installed & validated
  - `pyproject.toml` updated
  - Backward compatibility confirmed (all existing tests pass)
  - **Estimated effort**: ~4-6 hours | **Risk**: Low

- **MVP v0.2** (API-Key Auth Feature): MVP v0.1 + Phase 3 (P1 Story)
  - API-Key authentication working
  - New auth tests passing
  - Bilingual error messages deployed
  - **Estimated effort**: +3-4 hours | **Risk**: Low-Medium

- **Final v1.0** (Full Feature): All phases
  - All three stories complete (API-Key + Certificate Export + Compatibility)
  - Full test coverage ≥80%
  - Documentation complete
  - **Estimated effort**: +2-3 hours | **Risk**: Low

### Parallel Execution Plan

**Phase 2 Foundational (6 tasks)**:
- [P] T002, T003, T004 can execute in parallel (config changes, SDK validation, dependency updates)
- [P] T005, T006 can execute after T004 completes (both depend on SDK installation)

**Phase 3, 4, 5 (18 tasks)**:
- **P1 Story (T008-T014)**: Can start immediately after Phase 2
- **P2 Story - Cert Export (T015-T021)**: Can start immediately after Phase 2 (independent of P1)
- **P2 Story - Compatibility (T022-T025)**: Can start immediately after Phase 2 (independent of others)

**Phase 6 Polish (T026-T028)**:
- Can execute in parallel with any Phase 3-5 tasks
- Final tasks (T026-T028) must complete after all Phase 3-5 stories

### Dependency Graph

```
Phase 1 (Setup)
  ↓
Phase 2 (Foundational: SDK download & config)
  ├→ Phase 3 (P1: API-Key Auth)
  ├→ Phase 4 (P2: Certificate Export)
  ├→ Phase 5 (P2: Compatibility)
  └→ Phase 6 (Polish: Docs & Release)
```

---

## Phase 1: Setup (3 tasks)

**Phase Goal**: Initialize feature branch and validation framework.

**Independent Test Criteria**: 
- Branch created and pushed to remote
- Prerequisites verified (Python 3.10+, pytest, pytest-cov)
- Pre-commit hooks validated (Black, isort, flake8)

---

- [ ] T001 Create feature branch `001-sdk-v2.2.7-upgrade` and update local workspace
- [ ] T002 [P] Validate Python version ≥3.10 and install pytest, pytest-cov if missing (integration with pyproject.toml)
- [ ] T003 [P] Verify pre-commit hooks configured (Black, isort, flake8) in `.pre-commit-config.yaml`

---

## Phase 2: Foundational — SDK Baseline & Configuration (6 tasks)

**Phase Goal**: Download SDK v2.2.7 binary, update dependencies, and prepare dual-auth infrastructure.

**Independent Test Criteria**:
- SDK v2.2.7 binary present in `wheels/` for all target platforms (Windows, macOS, Linux)
- `pyproject.toml` pinned to `fubon_neo>=2.2.7`
- `config.py` supports both traditional auth and API-Key environment variables
- `server.py` initialization detects auth method and configures SDK correctly
- Existing test suite passes unchanged (backward compatibility validated)

**Critical**: All Phase 2 tasks must complete before Phase 3-5 stories begin.

---

- [x] T004 [P] Download SDK v2.2.7 wheel binaries for all platforms (Windows, macOS ARM64/x86_64, Linux x86_64) and place in `wheels/` directory
  
- [x] T005 [P] Update `pyproject.toml` to require `fubon_neo>=2.2.7` as minimum version (replace current unspecified or <2.2.7 requirement)

- [x] T006 Extend `config.py` to support API-Key authentication environment variables: `FUBON_API_KEY`, `FUBON_API_SECRET` alongside existing `FUBON_USERNAME`, `FUBON_PASSWORD`, `FUBON_PFX_PATH`, `FUBON_PFX_PASSWORD`

- [x] T007 [P] Modify `server.py` SDK initialization to detect and support dual authentication methods: 
  - If `FUBON_API_KEY` + `FUBON_API_SECRET` present → Initialize with API-Key auth
  - If `FUBON_USERNAME` + `FUBON_PASSWORD` + `FUBON_PFX_PATH` present → Initialize with traditional PFX auth
  - Both paths must be tested independently

- [x] T008 [P] Update `utils.py` to add API-Key credential validation helper function `validate_api_key_credentials(api_key: str, secret_key: str) -> tuple[bool, str]` that checks format and non-empty values

- [x] T009 Run full existing integration test suite against v2.2.7 and verify all tests pass unchanged (validate backward compatibility ≥99.9% success rate)

---

## Phase 3: P1 Story — API-Key Authentication Login (7 tasks)

**Story Goal**: Users can authenticate using API-Key + Secret instead of traditional username/password/PFX, enabling modern security workflows and IP whitelisting.

**Independent Test Criteria**:
- API-Key authentication succeeds for valid credentials
- API-Key auth allows trading operations (same as traditional auth)
- API-Key auth fails gracefully for invalid/expired keys with bilingual error message
- Session timeout on API-Key revocation is handled (user must re-authenticate)
- P1 story can be deployed independently without Certificate Export (P2) feature

---

- [ ] T010 [US1] Create test file `tests/test_auth_apikey.py` with fixtures for mock API-Key credentials and test cases covering: valid auth, invalid key, invalid secret, missing credentials, expired key handling

- [ ] T011 [P] [US1] Implement API-Key authentication test in `tests/test_auth_apikey.py::test_authenticate_with_api_key`: authenticate with API-Key, verify session is established, verify user account info is retrieved

- [ ] T012 [P] [US1] Implement test `tests/test_auth_apikey.py::test_api_key_auth_invalid_secret`: attempt auth with invalid secret, verify authentication fails with appropriate error message

- [ ] T013 [P] [US1] Implement test `tests/test_auth_apikey.py::test_api_key_auth_missing_credentials`: attempt auth without API-Key or Secret, verify clear error directing user to Fubon portal for API-Key setup

- [ ] T014 [US1] Add bilingual error messages for API-Key auth failures in `config.py` (English + Traditional Chinese 繁體中文):
  - "Invalid API Key format" / "無效的 API 金鑰格式"
  - "API Key or Secret not found in environment" / "環境中找不到 API 金鑰或祕密"
  - "API Key expired or revoked" / "API 金鑰已過期或已撤銷"
  - "Please apply for API Key at https://www.fbs.com.tw/TradeAPI/docs/key/" / "請在 https://www.fbs.com.tw/TradeAPI/docs/key/ 申請 API 金鑰"

- [ ] T015 [US1] Update `README.md` with API-Key authentication setup section (bilingual: English + Traditional Chinese):
  - Step-by-step: Apply for API-Key at Fubon portal
  - Set environment variables: `FUBON_API_KEY`, `FUBON_API_SECRET`
  - Example connection string
  - Difference from traditional PFX auth
  - Security best practices (IP whitelisting)

- [ ] T016 [US1] Run P1 tests and validate all API-Key auth tests pass; run full existing test suite to ensure no regressions

---

## Phase 4: P2 Story — Certificate Export Feature (7 tasks)

**Story Goal**: Users can export and import web certificates programmatically, enabling credential rotation and CI/CD integration.

**Independent Test Criteria**:
- Certificate export succeeds for valid authenticated user
- Exported certificate can be re-imported and used for authentication
- Export password validation works correctly
- Certificate export errors are handled gracefully with bilingual messages
- P2 Cert Export story can be deployed independently of P1 (API-Key) feature

---

- [ ] T017 [US2] Create test file `tests/test_certificate_export.py` with fixtures for certificate credentials and test cases covering: successful export, export with password, re-import test, password validation, format verification

- [ ] T018 [P] [US2] Implement certificate export test in `tests/test_certificate_export.py::test_export_certificate_success`: authenticate, export certificate to temp file, verify file exists and is valid PFX/PEM format

- [ ] T019 [P] [US2] Implement test `tests/test_certificate_export.py::test_export_certificate_with_password`: export certificate with specified password, verify exported file can be opened with password

- [ ] T020 [P] [US2] Implement test `tests/test_certificate_export.py::test_import_exported_certificate`: export certificate, import from exported file to new location, verify imported cert is usable for authentication

- [ ] T021 [P] [US2] Implement test `tests/test_certificate_export.py::test_export_certificate_invalid_password`: attempt export with invalid password format, verify clear error message

- [ ] T022 [US2] Add helper function in `utils.py`: `export_certificate(password: str, output_path: str) -> tuple[bool, str]` that wraps SDK certificate export with error handling

- [ ] T023 [US2] Add bilingual error messages for certificate export failures in `utils.py` (English + Traditional Chinese 繁體中文):
  - "Certificate export failed: invalid password" / "憑證匯出失敗: 密碼無效"
  - "Export path is not writable" / "匯出路徑不可寫入"
  - "Certificate format not supported" / "不支援憑證格式"

- [ ] T024 [US2] Run P2 Cert Export tests and validate all certificate export tests pass; run full existing test suite to ensure no regressions

---

## Phase 5: P2 Story — SDK Upgrade & Dependency Validation (4 tasks)

**Story Goal**: Ensure SDK v2.2.7 is fully backward compatible with existing codebase; no breaking changes detected.

**Independent Test Criteria**:
- All existing tests pass unchanged with SDK v2.2.7 (no code modifications to tests or MCP tools)
- Code coverage remains ≥80%
- No new enum values or API changes break existing trading/market data operations
- Compatibility validation document generated with detailed findings

---

- [ ] T025 [US3] Create test file `tests/test_sdk_compatibility.py` that runs critical existing tests: stock trading, fut/opt quotes, account info, to document SDK compatibility (no breaking changes expected)

- [ ] T026 [P] [US3] Verify all trading parameters (enums) used in existing code are still valid in v2.2.7: `buy_sell`, `price_type`, `market_type`, `order_type`, `time_in_force` (document in test comments)

- [ ] T027 [P] [US3] Run entire test suite with coverage: `pytest --cov=fubon_api_mcp_server --cov-report=html` and verify coverage ≥80%; document baseline from v2.2.4

- [ ] T028 [US3] Generate compatibility report in `specs/001-sdk-v2.2.7-upgrade/COMPATIBILITY_REPORT.md` documenting:
  - SDK versions tested (v2.2.4 baseline vs v2.2.7 current)
  - Test coverage before/after upgrade
  - Enum/API changes discovered (if any)
  - Breaking changes (expected: none)
  - Platforms validated (Windows, macOS, Linux)

---

## Phase 6: Polish & Release (1 task)

**Phase Goal**: Documentation finalization, changelog entry, and version bump for release.

**Independent Test Criteria**:
- README reflects API-Key feature in both English and Traditional Chinese
- CHANGELOG entry describes v2.2.7 upgrade with new features
- All pre-commit gates pass (Black, isort, flake8, mypy)
- Version bumped (setuptools-scm from git tag)

---

- [ ] T029 Update `README.md` with v2.2.7 features summary, update `CHANGELOG.md` with entry for SDK upgrade, API-Key auth feature, and certificate export capability; ensure both sections are bilingual (English + Traditional Chinese)

- [ ] T030 [P] Run pre-commit checks: `black fubon_api_mcp_server/`, `isort fubon_api_mcp_server/`, `flake8 fubon_api_mcp_server/` and ensure all pass without changes required

- [ ] T031 [P] Tag release with version bump (e.g., `v0.4.0`) corresponding to SDK v2.2.7 milestone; verify setuptools-scm generates version in `_version.py`

---

## Testing Strategy

### Test Execution Order

```
Phase 2: T009 (backward compatibility baseline)
Phase 3: T010-T016 (API-Key auth tests)
Phase 4: T017-T024 (Certificate export tests)
Phase 5: T025-T028 (Compatibility validation)
```

### Coverage Goals

- **Phase 2**: Backward compatibility ≥99.9% (existing tests pass)
- **Phase 3**: API-Key auth coverage 100% (new feature)
- **Phase 4**: Certificate export coverage 100% (new feature)
- **Phase 5**: Overall codebase coverage ≥80% maintained

### Running Tests Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run specific story tests
pytest tests/test_auth_apikey.py -v
pytest tests/test_certificate_export.py -v
pytest tests/test_sdk_compatibility.py -v

# Run full suite with coverage
pytest --cov=fubon_api_mcp_server --cov-report=html

# Open coverage report
# Windows: start htmlcov/index.html
# macOS: open htmlcov/index.html
# Linux: xdg-open htmlcov/index.html
```

---

## Task Dependencies Summary

| Phase | Tasks | Depends On | Parallel | Estimated Time |
|-------|-------|-----------|----------|-----------------|
| 1 Setup | T001-T003 | None | Yes (T002, T003) | 0.5-1 hour |
| 2 Foundational | T004-T009 | Phase 1 | Mostly (T004-T006 parallel, T007-T008 parallel) | 2-3 hours |
| 3 P1 API-Key | T010-T016 | Phase 2 | Yes (test tasks parallel) | 2-3 hours |
| 4 P2 Cert Export | T017-T024 | Phase 2 | Yes (test tasks parallel) | 2-3 hours |
| 5 P2 Compat | T025-T028 | Phase 2 | Mostly (T026, T027 parallel) | 1-2 hours |
| 6 Polish | T029-T031 | Phases 3-5 | Mostly | 0.5-1 hour |

**Total Estimated Effort**: 8-13 hours (spread over multiple contributors or days)

---

## Checklist Validation

✅ **All tasks follow required format**:
- [x] Checkbox present on all tasks
- [x] Sequential Task IDs (T001-T031)
- [x] [P] parallelization markers present where applicable
- [x] [Story] labels present in Phase 3-5 only
- [x] Clear descriptions with file paths
- [x] Organized by Phase (Setup → Foundational → Stories → Polish)

✅ **Story Independence**:
- [x] P1 (API-Key Auth) can be deployed without P2
- [x] P2a (Certificate Export) can be deployed without P1
- [x] P2b (Compatibility) validates all three work together

✅ **Test Coverage**:
- [x] Tests included in Phase 3-5 (new feature tests)
- [x] Backward compatibility validation in Phase 2 & Phase 5
- [x] Coverage maintained ≥80%

---

**Status**: Ready for execution | **Last Updated**: 2025-01-19

