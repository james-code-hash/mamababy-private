# CLAUDE.md

> `AGENTS.md` mirrors this file.

Private add-on for MoneyERP (main repo `shopee-bank/money-erp-v2`). Everything generic belongs in v2;
only owner-specific code, assets and deploy scripts go here.

- Code lives in `mamababy_private/`; it imports `moneyerp.*` and is wired in through entry points
  (`pyproject.toml`), never by patching v2.
- Tests: from a v2 checkout with this package installed editable,
  `uv run python -m pytest <this repo>/tests -q` and `uv run python <this repo>/tests/papa_golden.py`.
- No secrets in the repo. Docstrings in Chinese; code, commits and PRs in English.
- Series workflow: `.claude/skills/papa-home-episode/SKILL.md`; plan: `docs/papa-home-series.md`.
