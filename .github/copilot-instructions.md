## Fubon API MCP Server — Copilot Rules (Concise)

This repo wraps the Fubon Securities Python SDK (`fubon_neo`) into an MCP server. These rules make AI agents productive quickly in this codebase.

### Architecture & Key Files
- Monolith server: `fubon_api_mcp_server/server.py` (all MCP tools, resources)
- Config: `fubon_api_mcp_server/config.py`; Utils: `fubon_api_mcp_server/utils.py`
- Globals in `server.py`: `sdk`, `accounts`, `reststock` (stock REST), `restfutopt` (futures/options REST)
- VS Code extension launcher: `vscode-extension/` (spawns `python -m fubon_api_mcp_server.server`)
- Examples: `examples/` (e.g., `demo_futopt_tickers.py`), Tests: `tests/`

### MCP Tool Patterns (must follow)
- Decorate with `@mcp.tool()`. Validate inputs via Pydantic args classes defined near usage.
- Always call `validate_and_get_account(account)` (from `utils.py`) before trading APIs.
- Unified response shape for tools: `{"status": "success|error", "data": ..., "message": ...}`; add counts when useful.
- Error guard for services: if `reststock`/`restfutopt` is None, return `"期貨/選擇權行情服務未初始化"` (for futopt) or the corresponding stock message.
- API result handling conventions:
  - Stock intraday/snapshot/historical: returns plain dict/list from REST client.
  - Fut/Opt intraday: most endpoints return object with `is_success` + `.data` (e.g., `ticker/quote/candles/volumes/trades`).
  - Fut/Opt `tickers`/`products` return a dict with top-level keys (type, exchange, data[]). Parse `result["data"]` and normalize keys.
- Pass SDK parameters as keyword args (not a dict param). Tests assert `assert_called_once_with(symbol="TX00", session="afterhours")` style.

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
- Start MCP server directly: `python -m fubon_api_mcp_server.server` (logs under `log/`).
- Required env (.env): `FUBON_USERNAME`, `FUBON_PASSWORD`, `FUBON_PFX_PATH`, optional `FUBON_PFX_PASSWORD`, `FUBON_DATA_DIR`.
- Local cache: historical data under `data/` (CSV). Prefer reading cache before hitting API.
- UTF-8 I/O enforced at `server.py` start to avoid mojibake in Chinese output.

### Style & Quality Gates
- Black line-length 127, isort profile "black"; flake8 checks (E9, F63, F7, F82) only.
- Type checking: gradual; ignore external SDKs like `fubon_neo`, `mcp`, `fastmcp`.
- Keep changes minimal and aligned with existing patterns; avoid refactors across unrelated tools.

### Integration Notes
- `fubon_neo` is required (install from PyPI or `wheels/`).
- VS Code extension registers an MCP server and prompts credentials at start; passwords are not stored.

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
- Base path: `BASE_DATA_DIR` from env `FUBON_DATA_DIR` or default user data dir; created on startup.
- Reader: `read_local_stock_data(symbol)` loads `data/<symbol>.csv`, parses `date`, sorts descending.
- Writer: `save_to_local_csv(symbol, new_data)` performs atomic write: merge existing + new, drop duplicates on `date`, sort descending, write to temp file then move.
- Resource endpoint: `@mcp.resource("twstock://{symbol}/historical")` returns local cached records only (does not fetch remote).
- Fetch flow (historical candles): segments via `fetch_historical_data_segment` then enrich with `process_historical_data` (adds `vol_value`, `price_change`, `change_ratio`) before potential save.
- Agent additions MUST: prefer reading cache before remote call; never overwrite file without merge; maintain date column format; avoid adding heavy derived columns beyond existing pattern.

