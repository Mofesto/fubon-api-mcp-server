## Fubon API MCP Server — Copilot Rules (Concise)

This repo wraps the Fubon Securities Python SDK (`fubon_neo`) into an MCP server. These rules make AI agents productive quickly in this codebase.

### Architecture & Key Files
- **Monolith server**: `fubon_api_mcp_server/server.py` (all MCP tools, resources, global state)
- **Service classes**: `trading_service.py`, `market_data_service.py`, `account_service.py`, `reports_service.py`, `indicators_service.py` - each registers MCP tools with the main FastMCP instance
- **Service responsibilities**: Services follow a pattern — `MarketDataService` handles REST/futopt data parsing and normalization; `TradingService` encapsulates all order operations including condition and time-slice orders; `AccountService` provides accounting endpoints and PnL queries; `ReportsService` surfaces SDK callbacks into MCP tools.
- **Config & Utils**: `config.py` (env vars, data dirs), `utils.py` (account validation, error handling), `enums.py` (safe enum conversions)
- **Globals in server.py**: `sdk`, `accounts`, `reststock` (stock REST), `restfutopt` (futures/options REST), report lists (`latest_order_reports`, etc.)
- **VS Code extension**: `vscode-extension/` (spawns `python -m fubon_api_mcp_server.server`)
- **Examples**: `examples/` (demos), **Tests**: `tests/` (pytest with fixtures mocking SDK)

### MCP Tool Patterns (must follow)
- Decorate with `@mcp.tool()`. Validate inputs via Pydantic args classes defined near usage.
- Always call `validate_and_get_account(account)` (from `utils.py`) before trading APIs - reinitializes SDK per call.
- Unified response shape: `{"status": "success|error", "data": ..., "message": ...}`; add counts when useful.
- Error guard for services: if `reststock`/`restfutopt` is None, return `"期貨/選擇權行情服務未初始化"` (for futopt) or stock equivalent.
- API result handling:
  - Stock intraday/snapshot/historical: returns plain dict/list from REST client.
  - Fut/Opt intraday: returns object with `is_success` + `.data` (e.g., `ticker/quote/candles/volumes/trades`).
  - Fut/Opt `tickers`/`products`: dict with top-level keys (type, exchange, data[]). Parse `result["data"]` and normalize keys.
- Pass SDK parameters as keyword args (not dict param). Tests assert `assert_called_once_with(symbol="TX00", session="afterhours")` style.

### Important Gotchas & Conventions ⚠️
- MCP tools always validate and reinitialize accounts per-call — call `validate_and_get_account(account)` early in a tool function. This both fetches an account object and re-configures `sdk` for the active call.
- SDK results are not uniform — prefer `if result and hasattr(result, "is_success") and result.is_success:` then use `result.data`. If not `is_success`, check `result.message`.
- `@mcp.resource` endpoints are read-only and often return local `data/` cache only (eg: `twstock://{symbol}/historical`). This pattern avoids unnecessary remote API calls.
- Do not mutate globals in `server.py` such as `sdk`, `reststock`, `restfutopt`, `accounts`; tests rely on these being patched and reinitialized via `validate_and_get_account`.

### Concurrency & Long-running Ops 🔁
- `batch_place_order` and other batch operations use `ThreadPoolExecutor` for concurrency — follow its pattern for parallelizable tasks.
- Time-slice orders (`place_time_slice_order`) and other split strategies accept `split_count` and `single_quantity`. Ensure quantity units are *shares* (1000 shares = 1張).

### Tests & Mocking Patterns 🧪
- Unit tests in `tests/` mock global `sdk` and `accounts` via fixtures (`tests/conftest.py`). Patch and assert call styles: `sdk.stock.place_order.assert_called_once_with(**kwargs)` (keyword args).
- For fut/opt clients, tests assert normalization of `result["data"]` and top-level keys in `products/tickers` calls.

### Quick Examples (copy-paste) ✂️
- Place a stock order (follow `trading_service.py::place_order`):
```py
account_obj, err = validate_and_get_account(account)  # required
params = {"account": account_obj, "symbol": "2330", "price": "100", "quantity": 1000, "buy_sell": "Buy"}
result = sdk.stock.place_order(**params)
if result and hasattr(result, "is_success") and result.is_success:
  return result.data
```
- Parse a fut/opt ticker (follow `market_data_service.py`): call `restfutopt.tickers(product=...)` and check `data` + `is_success`.

### Testing Workflow (pytest)
- Fixtures: see `tests/conftest.py` (mocks `sdk`, `accounts`, and server globals via patching).
- Typical commands (PowerShell on Windows):
  ```pwsh
  python -m pytest -q
  python -m pytest --cov=fubon_api_mcp_server --cov-report=html
  python -m pytest tests/test_market_data_service.py::TestGetIntradayFutOptTickers -v
  ```
- Common fut/opt expectations used by tests:
  - `tickers/products`: input filters echoed in `filters_applied`; aggregate `total_count`, `type_counts`.
  - Service not initialized => specific error message above.
  - Normalize option fields: `contract_type`, `expiration_date`, `strike_price`, `option_type`, `underlying_symbol`.

### Dev Routines & Debugging
- Start MCP server: `python -m fubon_api_mcp_server.server` (logs under `log/`).
- Required env: `FUBON_USERNAME`, `FUBON_PASSWORD`, `FUBON_PFX_PATH`, optional `FUBON_PFX_PASSWORD`, `FUBON_DATA_DIR`.
- Local cache: historical data under `data/` (CSV). Prefer reading cache before hitting API.

### Big picture / Why these decisions
- Single monolith with service classes — this keeps the runtime artifact simple and the `FastMCP` registration centralized in `server.py` so new tools can be added by registering methods in service classes.
- Reinitialize `sdk` per call via `validate_and_get_account` — tests and tooling expect stateless tool invocations and this avoids stale session/auth issues.
- Local historical caching reduces API calls and simplifies offline testing — `@mcp.resource` endpoints intentionally return the cache only for deterministic testing.

### When writing new MCP tools
- Define a Pydantic args class next to the tool; use `validated_args = MyArgs(**args)` before `validate_and_get_account`.
- Put data parsing/normalization in a service method, not directly in `server.py`.
- Ensure `sdk` calls use keyword args and check `is_success` pattern; prefer `self._to_dict(result.data)` when returning SDK objects.

### Additions to check in PRs
- Verify `tests/` coverage for new tool behavior, especially for reinitialization and `is_success` handling.
- Add mocks to `tests/conftest.py` only if needed and never modify global `sdk` without `validate_and_get_account`.
- UTF-8 I/O enforced at `server.py` start to avoid mojibake in Chinese output.
- Validate server: `python validate_server.py` for quick checks.

### Build & Release
- **Versioning**: setuptools-scm from Git tags, writes to `_version.py`
- **Build**: `pyproject.toml` with platform-specific wheels for `fubon_neo`
- **Scripts**: `scripts/` for automated releases (PowerShell), version bumping, release notes
- **Extension**: VS Code extension in `vscode-extension/` with auto-publish

### Style & Quality Gates
- Black line-length 127, isort profile "black"; flake8 checks (E9, F63, F7, F82) only.
- Type checking: gradual; ignore external SDKs like `fubon_neo`, `mcp`, `fastmcp`.
- Keep changes minimal and aligned with existing patterns; avoid refactors across unrelated tools.

### Integration Notes
- `fubon_neo` required (install from PyPI or `wheels/`).
- VS Code extension registers MCP server and prompts credentials at start; passwords not stored.
- MCP tools run in separate contexts, so each call reinitializes SDK via `validate_and_get_account`.

### Practical Examples in Repo
- Fut/Opt: see `get_intraday_futopt_tickers/quote/candles/volumes/trades` in `server.py` and tests in `tests/test_market_data_service.py`.
- Trading: `batch_place_order` uses `ThreadPoolExecutor`; follow its pattern for concurrency.

If anything here seems off or incomplete (e.g., a new tool type or changed SDK response), leave a brief note in your PR and I’ll refine these rules.
### Trading Parameter Quick Reference
- `buy_sell`: `Buy` | `Sell` (maps to `BSAction`)
- `market_type`: `Common` | `Emg` | `Odd` (condition orders may use `Reference` etc. via conversion helpers)
- `price_type`: `Limit` | `Market` | `LimitUp` | `LimitDown` (condition variants also accept these; TPSL `price` must be empty string when Market)
- `time_in_force`: `ROD` | `IOC` | `FOK`
- `order_type`: `Stock` | `Margin` | `Short` | `DayTrade`
- Condition triggers: `MatchedPrice` | `BuyPrice` | `SellPrice` | `TotalQuantity` | (DayTrade adds timing fields)
- Comparison ops: `LessThan` | `LessOrEqual` | `Equal` | `Greater` | `GreaterOrEqual`
- StopSign: `Full` | `Partial` | `UntilEnd` (TPSL wrapper also uses `Full` / `Flat`)
- Trail order: `direction`=`Up`|`Down`, `percentage` int, `diff` offset, `price` ≤ 2 decimal places.

### Active / Filled / Changed / Event Reports
Global lists in `server.py` maintain last ~10 items for each category:
- `latest_order_reports`: raw objects from SDK callbacks (placed orders)
- `latest_order_changed_reports`: modifications (price/quantity/cancel)
- `latest_filled_reports`: fills (成交) with quantities/prices
- `latest_event_reports`: system / connection events
Access patterns:
```python
@mcp.tool()
def get_all_reports(args):
  # returns {order_reports:[...], order_changed_reports:[...], filled_reports:[...], event_reports:[...]}
```
Returned shape always: `{"status": "success", "data": <list|dict>, "message": ...}` plus `count` or `total_count` where meaningful. Tests assume simple passthrough of stored objects (no mutation).

### Local Historical Data Cache (data/)
- Base path: `BASE_DATA_DIR` from env `FUBON_DATA_DIR` or platform-specific default.
- Reader: `read_local_stock_data(symbol)` loads `data/<symbol>.csv`, parses `date`, sorts descending.
- Writer: `save_to_local_csv(symbol, new_data)` performs atomic write: merge existing + new, drop duplicates on `date`, sort descending, write to temp file then move.
- Resource endpoint: `@mcp.resource("twstock://{symbol}/historical")` returns local cached records only (does not fetch remote).
- Fetch flow: segments via `fetch_historical_data_segment` then enrich with `process_historical_data` (adds `vol_value`, `price_change`, `change_ratio`) before potential save.
- Always prefer reading cache before remote call; never overwrite file without merge; maintain date column format; avoid adding heavy derived columns beyond existing pattern.

---
If anything here is unclear or you'd like me to add tooling-specific snippets (e.g., how to test condition orders or simulate account re-login in CI), tell me which part to expand and I'll update this file.

