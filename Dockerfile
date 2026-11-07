# James 的映像檔：MoneyERP 主程式映像檔＋私人附加套件（帕帕貝貝家）。
# BASE 用 money-erp-v2 的同一個 commit 映像檔（image.yml 帶進來），不要用 :main，才知道跑的是哪一版。
ARG BASE=ghcr.io/shopee-bank/money-erp-v2-ops:main
FROM ${BASE}

USER root
COPY --chown=app:app pyproject.toml README.md /opt/mamababy-private/
COPY --chown=app:app mamababy_private /opt/mamababy-private/mamababy_private
RUN uv pip install --python /app/.venv/bin/python --no-deps /opt/mamababy-private \
 && /app/.venv/bin/python -c "from moneyerp.core import plugins; s = plugins.series(); assert s and s.key == 'papa_home', s"
USER app
