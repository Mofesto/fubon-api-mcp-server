# Repository Guidelines


## AGENTS.md

- Do not preserve backward compatibility. Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
- Make architectural decisions for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.

## Project Structure & Module Organization

- `fubon_api_mcp_server/` contains the Python MCP server. `server.py` is the entry point; service modules cover trading, market data, accounts, reports, analysis, and indicators. Shared helpers live in `config.py`, `enums.py`, and `utils.py`.
- `tests/` contains pytest tests and SDK-mocking fixtures in `tests/conftest.py`. `examples/` contains manual API examples, and `vscode-extension/` contains the VS Code extension.
- `scripts/` holds PowerShell release/version tooling; `specs/` holds implementation plans. `data/`, `assets/`, and `wheels/` are runtime or distribution assets.

## Build, Test, and Development Commands

Use Python 3.10–3.13 and install the editable development package:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

- `python -m fubon_api_mcp_server.server` starts the MCP server; configure `FUBON_*` variables from `.env.example` first.
- `python -m pytest` runs the test suite; target a test with `python -m pytest tests/test_account_service.py -v`.
- `python -m pytest --cov=fubon_api_mcp_server --cov-report=html` creates coverage output in `htmlcov/`.
- `./scripts/quick_check.ps1` runs the fast formatting, lint, and smoke-test checks on Windows.
- `python -m build` followed by `python -m twine check dist/*` validates a package build.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, Black formatting with a 127-character line length, and isort’s Black profile. Use `snake_case` for modules/functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. New MCP tools should validate inputs with Pydantic, use the existing `{"status": ..., "data": ..., "message": ...}` response shape, and keep SDK parsing inside the relevant service.

## Testing Guidelines

Name files `test_*.py`, classes `Test*`, and functions `test_*`. Keep default tests offline by mocking SDK clients and server globals; use `integration` or `trading` markers for external services or credentials, and never place real orders from automated tests. Add regression coverage for behavior changes and aim for 80% overall coverage.

## Commit & Pull Request Guidelines

Use concise Conventional Commits, matching history such as `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, and `ci:`. PRs should explain the change, link an issue or spec, list validation commands, and update docs/examples when interfaces change. Include screenshots for VS Code extension UI changes.

## Security & Agent-Specific Notes

Never commit `.env`, API keys, passwords, certificates, or account data; update `.env.example` with placeholders only. Before changing MCP behavior, read `CLAUDE.md` and `.github/copilot-instructions.md`. Trading calls must validate the account through the existing helper, and changes should preserve the established SDK mocking and response conventions.
