# mamababy-private

Private add-on for the MoneyERP image (`shopee-bank/money-erp-v2`): the weekly
series plugin, its assets, and deploy notes that must not live in the public repo.

- Plugin entry points: `moneyerp.cli` (`papa …` commands) and `moneyerp.series`
  (weekly series that replaces the knowledge Reels slots once live).
- `Dockerfile` builds on top of `ghcr.io/shopee-bank/money-erp-v2-ops` and installs this package.
- Local dev: in a v2 checkout run `uv sync --all-packages --extra test`, then
  `uv pip install -e ../mamababy-private` and `uv run python -m pytest ../mamababy-private/tests -q`.
- `deploy-web.yml` / `deploy-rules.yml` are manual only; do not run them before the cutover
  (see the merge plan doc).
