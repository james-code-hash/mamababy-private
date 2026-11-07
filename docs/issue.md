# MamaBaby Tools — Issue 記錄

> `uv run python main.py test` 的 FAIL / ISSUE 記在這裡；修好後刪除該條目。

- 2026-11-04 `main.py test` FAIL：`estimate_profit / _match_score`。頭程運費已改 ¥9/kg（`docs/forwarder-fees.md`），`apps/ops-cli/tests/run_all.py` 這項檢查仍以 ¥7.3/kg 斷言。main 上既有問題（PR #105 已記錄），與《帕帕家》PR 無關。
