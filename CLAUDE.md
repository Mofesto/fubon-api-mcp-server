# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

An MCP (Model Context Protocol) server wrapping the Fubon Securities Python SDK (`fubon_neo`) to expose Taiwan stock trading, market data, account management, and quantitative analysis as AI-callable tools.

## Commands

### Run tests
```bash
# All tests
python -m pytest -q

# Single test class
python -m pytest tests/test_market_data_service.py::TestGetIntradayFutOptTickers -v

# With coverage
python -m pytest --cov=fubon_api_mcp_server --cov-report=html --cov-report=term-missing
```

### Lint and format
```bash
# Lint (errors only)
flake8 fubon_api_mcp_server tests --count --select=E9,F63,F7,F82 --show-source --statistics

# Format check
black --check --diff fubon_api_mcp_server tests --exclude fubon_api_mcp_server/_version.py

# Apply formatting
black .
isort fubon_api_mcp_server tests
```

### Type check and security
```bash
mypy fubon_api_mcp_server
bandit -r fubon_api_mcp_server -f json -o bandit-report.json
```

### Start server
```bash
python -m fubon_api_mcp_server.server
```

### Build and validate
```bash
python validate_server.py   # quick sanity check
python -m build             # produce dist/
twine check dist/*
```

### Release (PowerShell)
```bash
.\scripts\release.ps1               # patch bump
.\scripts\release.ps1 -BumpType minor
```

## Architecture

**Entry point:** `fubon_api_mcp_server/server.py` creates a `FastMCP` instance and instantiates all service classes. Each service calls `_register_tools()` in its `__init__`, decorating its methods with `@self.mcp.tool()` against the shared FastMCP instance. After registration, `mcp.run()` starts the server over stdio.

**Service classes:**
- `trading_service.py` — place/modify/cancel orders, condition orders, TPSL, trailing profit, time-slice splits
- `market_data_service.py` — REST stock and futures/options: intraday quotes, snapshots, candles, movers, actives, historical CSV cache, SQLite local DB
- `account_service.py` — balance, inventory, unrealized/realized PnL, margin, settlement
- `reports_service.py` — surfaces SDK callbacks (order fill/change/event) buffered in global lists in `server.py`
- `analysis_service.py` — Phase 3 quant: portfolio VaR, stress tests, performance attribution, arbitrage detection, sentiment index

**Supporting modules:**
- `config.py` — env-var config singleton, data dir setup, logging
- `utils.py` — `validate_and_get_account()`, `_safe_api_call()`, `export_certificate()`, `handle_exceptions()`
- `enums.py` — safe converters from string to `fubon_neo.constant` enums
- `indicators.py` / `indicators_advanced.py` — TA-Lib wrappers (RSI, MACD, Bollinger Bands, KD)

## Critical Patterns

### Every trading tool must start with
```python
account_obj, err = validate_and_get_account(account)
if err:
    return {"status": "error", "data": None, "message": err}
```
This reinitializes the `FubonSDK` singleton per call (`config_module.sdk`). Never bypass it.

### SDK calls use keyword args, always check `is_success`
```python
result = sdk.stock.place_order(account=account_obj, symbol="2330", price="100",
                               quantity=1000, buy_sell="Buy")
if result and hasattr(result, "is_success") and result.is_success:
    return {"status": "success", "data": result.data, "message": ""}
return {"status": "error", "data": None, "message": result.message}
```

### Unified response shape
All tools return `{"status": "success|error", "data": ..., "message": ...}`. Add `count`/`total_count` when returning lists.

### Dual auth (auto-detected, API-Key takes precedence)
- API-Key: `FUBON_API_KEY` + `FUBON_API_SECRET` → `sdk.login(api_key=..., secret_key=...)`
- PFX: `FUBON_USERNAME` + `FUBON_PASSWORD` + `FUBON_PFX_PATH` + optional `FUBON_PFX_PASSWORD`

### REST client null guard
Before any `reststock`/`restfutopt` call, check for `None` and return `"期貨/選擇權行情服務未初始化"` (futopt) or stock equivalent.

### Fut/Opt vs Stock REST responses differ
- Stock intraday/snapshot: returns plain dict/list
- Fut/Opt intraday: returns object with `.is_success` + `.data` (has sub-fields like `ticker`, `quote`, `candles`)
- Fut/Opt `tickers`/`products`: dict with top-level keys (`type`, `exchange`, `data[]`) — parse `result["data"]` and normalize option fields (`contract_type`, `expiration_date`, `strike_price`, `option_type`, `underlying_symbol`)

### `@mcp.resource` endpoints are cache-only
`twstock://{symbol}/historical` reads from `data/<symbol>.csv` only; never fetches remote. Historical fetch + save uses `fetch_historical_data_segment` → `process_historical_data` → `save_to_local_csv` (atomic merge, no overwrite).

### Active reports
Four global lists in `server.py` (`latest_order_reports`, `latest_filled_reports`, `latest_order_changed_reports`, `latest_event_reports`) are populated by SDK callbacks registered in `main()`. `ReportsService` provides read-only MCP tools over them.

## Testing

Tests mock `config_module.sdk` and `config_module.accounts` via `pytest-mock`. Fixtures are in `tests/conftest.py` (`sample_accounts`, `sample_account_objs`). Assert SDK calls using keyword-arg style: `sdk.stock.place_order.assert_called_once_with(**kwargs)`.

When adding new tools, add corresponding tests covering:
1. The `validate_and_get_account` / SDK reinitialization path
2. The `is_success` success branch and the failure branch
3. Service-not-initialized guard (for REST-dependent tools)

## Style Gates

- Black line-length **127**, isort profile **black**
- Flake8: only hard-error checks (`E9,F63,F7,F82`); `max-complexity=20`; ignore `E203,E501,W503`
- mypy: gradual — external SDKs (`fubon_neo`, `mcp`, `fastmcp`, `pandas`) are ignored
- UTF-8 I/O is enforced at server startup to avoid mojibake in Chinese output

## Adding New MCP Tools

1. Define a Pydantic args class adjacent to the tool function
2. Call `validate_and_get_account(account)` before any SDK call
3. Use keyword args for all SDK calls; check `is_success`
4. Return the unified `{status, data, message}` shape
5. Register via `@self.mcp.tool()` inside the service's `_register_tools()`; do not add directly to `server.py`

## Trading Parameter Reference

| Parameter | Values |
|---|---|
| `buy_sell` | `Buy` \| `Sell` |
| `market_type` | `Common` \| `Emg` \| `Odd` |
| `price_type` | `Limit` \| `Market` \| `LimitUp` \| `LimitDown` |
| `time_in_force` | `ROD` \| `IOC` \| `FOK` |
| `order_type` | `Stock` \| `Margin` \| `Short` \| `DayTrade` |
| Condition trigger | `MatchedPrice` \| `BuyPrice` \| `SellPrice` \| `TotalQuantity` |
| Comparison ops | `LessThan` \| `LessOrEqual` \| `Equal` \| `Greater` \| `GreaterOrEqual` |
| `stop_sign` | `Full` \| `Partial` \| `UntilEnd` |

Quantity units are **shares** (1,000 shares = 1張). TPSL market-price orders must pass `price=""`.
