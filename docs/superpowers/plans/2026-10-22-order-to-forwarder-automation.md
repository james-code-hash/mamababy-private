# 收單到出貨自動化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一個 `orders cycle` 指令每 2 小時在 claw-arm-1 跑：推進採購、偵測取消、通知貨憨憨出貨、合併下 1688 待付款單（未付款可取消重建），狀態存 Firestore，通知走 Slack；業主只需付款。

**Architecture:** 沿用 `modules/order_processing/` 的依賴注入 + Protocol 模式。新增 Firestore store 取代 SQLite、Slack 通知器（含去重）、`cycle.py` 編排器呼叫既有/改造後的 `prepare_purchase`、`fulfill_shipping`、取消偵測，回傳結構化結果；cron 腳本只是薄殼。

**Tech Stack:** Python 3.13（uv）、`google-cloud-firestore`、curl（Slack webhook，沿用專案 curl 慣例）、pytest/unittest、systemd timer 或 cron。

**Spec:** `docs/superpowers/specs/2026-10-22-order-to-forwarder-automation-design.md`（已核准）。執行者兩份都要讀。

## Global Constraints

- 業主唯一固定人工步驟是 1688 付款；其餘自動。
- 採購循環每 2 小時一次；批次鍵 (supplier_id, warehouse_id)；收貨倉預設＝設定 `PURCHASE_WAREHOUSE_ID`。
- 鎖定條件 = **已付款**（不是「已在 1688 下單」）。付款狀態查不到（unknown）一律當已付款處理（不取消、不覆蓋）。
- 只取消/刪除/覆蓋**自動化自己建立**（Firestore `op_purchases` 有紀錄）的採購單；人工建立的不動，但其內含的蝦皮訂單不得再採購。
- 取消舊 1688 待付款單**成功後**才可下新單；取消失敗 → 不下新單、告警。
- 不拆單（ADR 0011）：訂單任一項配不到供應商或多重綁定挑不出 → 整張不採購、通知。
- 一張蝦皮訂單所有相關採購的運單號到齊才送貨憨憨；每個商品項帶自己的運單號；對不出商品↔包裹 → 不送、通知。
- 任何 API 錯誤不得當成空結果；中止受影響步驟、非零結束、Slack 告警。
- dry-run（不帶 `--commit`）不得寫 BigSeller、1688、貨憨憨、Firestore，也不發 Slack。
- 儲存：Firebase 專案 `mamababy-1bf68`，Firestore `(default)`；憑證以 `GOOGLE_APPLICATION_CREDENTIALS` 指向 service account 檔，不進版控。
- 通知只用 Slack Incoming Webhook（`SLACK_WEBHOOK_URL`），排程路徑上不得再呼叫 Telegram。
- 通知去重：同一 dedupe key 只在首次或內容改變時發；未付款單每 24 小時提醒一次。
- 測試不得打真 Firebase/BigSeller/貨憨憨/Slack（注入假物件）。
- 對正式帳號的寫入型探測（真的取消、真的下單）需業主在對話中明確同意。
- 新 ADR 編號從 `0013` 開始。
- 驗證指令：`uv run python -m pytest -q`、`uv run python main.py test`。

## Review Focus

1. 業主在系統取消舊單的同一刻付款 → 取消回 False → 不得下新單、要回報錯誤（Task 6 測試 `test_rebuild_cancel_failure_never_places`）。
2. BigSeller session 中途過期 → 讀取函式 raise，循環中止且不把「讀不到」當「沒有訂單」（Task 4 `test_out_of_stock_api_error_raises`、Task 9 `test_cycle_read_failure_aborts_before_purchase`）。
3. 同一張蝦皮訂單已在人工建立的採購單裡、又出現在缺貨清單 → 不得再買（Task 6 `test_orders_in_unowned_purchase_not_rebought`）。
4. Slack webhook 失敗 → BigSeller 動作照常完成、該通知不標記為已發（下輪重試）、循環非零結束（Task 3 `test_failed_send_not_recorded`、Task 9 `test_cycle_slack_failure_exit_nonzero`）。
5. Firestore 不可用 → 在任何 BigSeller 寫入前中止（Task 9 `test_cycle_store_unavailable_no_writes`）。

---

## File Structure

| 檔案 | 責任 |
|---|---|
| `docs/bigseller-api-notes.md`（改） | Task 1 查證結果 |
| `modules/order_processing/store_types.py`（新） | 各 store 的 Protocol 與 TypedDict |
| `modules/order_processing/firestore_stores.py`（新） | Firestore 實作：指紋、採購帳本、貨代提交、阻塞、通知紀錄 |
| `modules/order_processing/firestore_client.py`（新） | 建立 Firestore client（讀 config） |
| `tests/order_processing/fake_firestore.py`（新） | 測試用 dict-backed 假 client |
| `modules/order_processing/store.py`、`forwarder_store.py`、`blocked_store.py`（改） | 刪 SQLite 版 `FingerprintStore`/`ForwarderSubmissionStore`/`BlockedOrderStore`；`ProductScanStore` 與 `JsonValue` 型別保留（`ProductScanStore` 屬上架側，不動） |
| `modules/notify/slack.py`（新）、`modules/notify/__init__.py` | Slack 傳送 + 去重通知器 |
| `modules/bigseller/orders.py`（改） | 讀取 fail-loud、一單多採購映射、付款狀態/取消 1688 單 API |
| `modules/order_processing/state_view.py`（改） | 新鎖定規則（付款、自有） |
| `modules/order_processing/prepare_purchase.py`（改） | 不拆單、dry-run 計數、重建流程、寫帳本 |
| `modules/order_processing/fulfill_shipping.py`、`fulfillment_types.py`（改） | 多採購/多運單號 |
| `modules/huohanhan/client.py`、`modules/fulfill/*`（改） | place-order 每項帶各自運單號 |
| `modules/order_processing/cancellation.py`（新，取代 `blocked_handling.detect_and_block_canceled_orders`） | 四種取消時間點的判定與處置 |
| `modules/order_processing/cycle.py`（新） | 一次循環編排 + 通知組裝 |
| `main.py`（改） | `orders cycle`；既有 orders 子命令改用 Firestore store |
| `scripts/cron_order_cycle.py`（新）、`scripts/cron_utils.py`（改） | 排程入口；移除 Telegram 與 Hermes 路徑 |
| `scripts/cron_new_order_alert.py`、`scripts/cron_fulfill_pipeline.py` 與其測試（刪） | 被 `cron_order_cycle.py` 取代 |
| `deploy/mamababy-order-cycle.service`、`.timer`（新）、`docs/deploy-linux.md`（改） | 部署 |
| `docs/adr/0013-firestore-order-processing-store.md`、`0014-purchase-lock-on-payment.md`（新）、`0001`/`0004`（標註被取代/修訂） | 決策紀錄 |
| `CLAUDE.md`、`AGENTS.md`（改） | 同步規範（兩檔一起改） |

---

### Task 1: 查證外部能力（閘門）

**Files:**
- Modify: `docs/bigseller-api-notes.md`（新增「1688 付款、取消、分包」章節）
- Create: `tests/fixtures/order_processing/purchase_row_placed.json`、`huohanhan_pending_order.json`（真實回應去識別化：電話、地址、姓名改假值）
- Commit: 連同 spec 與本計畫

只用唯讀方式：讀既有採購單列表/詳情、BigSeller 前端 JS（搜尋 purchase 相關 `cancel`/`close`/`pay` 端點）、1688 開放平台文件與 `ALI_1688_AK` 唯讀查詢、貨憨憨待打包清單。

- [ ] **Step 1:** 抓 state 0/5/1 各一筆有 `aliOrderNo` 的採購單（`get_purchase_list`、`get_purchase_detail`），列出所有欄位；找出能區分「待付款 / 已付款」的欄位與值（候選 `platformOrderStatus`、`payStatus`）。必要時以 `ALI_1688_AK` 呼叫 1688 買家訂單詳情（例如 `alibaba.trade.get.buyerView`）確認權限與付款狀態欄位。
- [ ] **Step 2:** 找「取消 1688 未付款訂單」的方法：BigSeller 前端 chunk 搜尋 purchase 平台訂單取消端點；或 1688 `alibaba.trade.cancel`。記下 endpoint、參數、成功判定。查 1688 未付款單自動關閉時限。
- [ ] **Step 3:** 查已付款 1688 單申請取消/退款是否有 API（BigSeller 或 1688）；查貨憨憨退貨申請 API（只記錄）。
- [ ] **Step 4:** 分包：看 BigSeller 採購單 `trackingNo` 欄位多運單號時的格式（是否逗號分隔、是否有逐項對應欄位），以及貨憨憨 `shopOrderGoods[]` 哪個欄位是蝦皮規格 SKU（用來把商品項對到採購單的 `varSku`）。
- [ ] **Step 5:** 查 BigSeller 蝦皮訂單「已取消」的 `status` 正確拼字（`cancelled` vs `canceled`），以實際 API 回應為準。
- [ ] **Step 6:** 寫進 `docs/bigseller-api-notes.md`，存兩個 fixture。
- [ ] **Step 7（閘門）:** 若 Step 1 找不到付款狀態、或 Step 2 找不到任何取消未付款單的方法：**停止，回報業主**（依 spec「待查證」段），不要往下做 Task 6。其他 Task（2–5、7–8）可繼續。若 Step 2 需要實際取消一張單來驗證，先取得業主同意。
- [ ] **Step 8: Commit**
```bash
git add docs/superpowers/specs/2026-10-22-order-to-forwarder-automation-design.md docs/superpowers/plans/2026-10-22-order-to-forwarder-automation.md docs/bigseller-api-notes.md tests/fixtures/order_processing/
git commit -m "docs: record 1688 payment/cancel capabilities for order cycle"
```

---

### Task 2: Firestore store 層（取代 SQLite）

**Files:**
- Create: `modules/order_processing/store_types.py`、`modules/order_processing/firestore_client.py`、`modules/order_processing/firestore_stores.py`、`tests/order_processing/fake_firestore.py`、`tests/order_processing/test_firestore_stores.py`、`docs/adr/0013-firestore-order-processing-store.md`
- Modify: `pyproject.toml`（加 `google-cloud-firestore`、`opencc-python-reimplemented`）、`config.py`（`FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "mamababy-1bf68")`）、`modules/order_processing/store.py`（刪 `FingerprintStore`）、`forwarder_store.py`（刪 `ForwarderSubmissionStore`，保留 `JsonValue`/`JsonDict`）、`blocked_store.py`（刪 `BlockedOrderStore`，`BlockedOrderRecord` 移到 `store_types.py`）、`main.py` 的 `cmd_orders_*`（改用 `firestore_stores`）、`docs/adr/0001-*.md`（標註 Superseded by 0013）
- Delete tests: `tests/order_processing/test_store.py`、`test_forwarder_store.py`、`test_blocked_store.py`（行為搬到 `test_firestore_stores.py`）；其他用到 SQLite store 的測試改用 Firestore store + `FakeFirestore`

**Interfaces:**
- Produces（`store_types.py`）:
  - `class FingerprintStoreLike(Protocol)`: `get_all() -> dict[tuple[int,int], FingerprintRecord]`、`upsert(supplier_id: int, warehouse_id: int, fingerprint: str, purchase_id: int | None) -> None`
  - `class PurchaseRecord(TypedDict)`: `purchase_id: int`、`supplier_id: int`、`supplier_name: str`、`warehouse_id: int`、`ali_order_no: str | None`、`order_nos: list[str]`、`items: list[dict]`（`var_sku`、`qty`、`unit_price`）、`amount: float | None`、`freight: float | None`、`status: str`（`"placed" | "paid" | "canceled" | "superseded"`）、`superseded_by: int | None`、`placed_at: str`、`paid_at: str | None`
  - `class PurchaseLedgerLike(Protocol)`: `record_placed(rec: PurchaseRecord) -> None`、`get(purchase_id: int) -> PurchaseRecord | None`、`list_open() -> list[PurchaseRecord]`（status ∈ placed/paid）、`mark(purchase_id: int, status: str, *, superseded_by: int | None = None, paid_at: str | None = None) -> None`、`owned_ids() -> set[int]`
  - `class ForwarderStoreLike(Protocol)`: 同現有 `ForwarderSubmissionStore` 的 `get_submitted_order_ids`、`record_submitted`、`record_failed`，但 `tracking_no: str` 改為 `tracking_nos: list[str]`
  - `class BlockedStoreLike(Protocol)`: 同現有 `BlockedOrderStore` 方法（`get_blocked_order_ids`、`get_all_records`、`get_record`、`record_blocked`、`record_resolved`），`record_blocked` 加參數 `stage: str`（`"paid_unshipped" | "shipped_by_1688" | "after_forwarder"`）
  - `class NotificationLogLike(Protocol)`: `last(key: str) -> dict | None`（`{"digest": str, "sent_at": str}`）、`record(key: str, digest: str) -> None`
  - `firestore_client.get_client() -> google.cloud.firestore.Client`（`project=FIREBASE_PROJECT_ID`）
  - `firestore_stores`: `FirestoreFingerprintStore(client)`、`FirestorePurchaseLedger(client)`、`FirestoreForwarderStore(client)`、`FirestoreBlockedStore(client)`、`FirestoreNotificationLog(client)`
- Collections / doc id：`op_batch_fingerprints/{supplier_id}_{warehouse_id}`、`op_purchases/{purchase_id}`、`op_forwarder_submissions/{provider}_{source_order_id}`、`op_blocked_orders/{platform_order_id}`、`op_notifications/{key}`（key 先把 `/` 換成 `_`）。時間一律 UTC ISO-8601 字串。
- `FakeFirestore`：只實作用到的 `collection(name).document(id).get()/.set(data, merge=False)`、`collection(name).stream()`，回傳物件有 `.exists`、`.id`、`.to_dict()`。

- [ ] **Step 1: Write failing tests**（`tests/order_processing/test_firestore_stores.py`，皆用 `FakeFirestore()`）
```python
def test_fingerprint_roundtrip():
    s = FirestoreFingerprintStore(FakeFirestore())
    s.upsert(101, 2001, "fp1", 9001)
    assert s.get_all() == {(101, 2001): {"fingerprint": "fp1", "purchase_id": 9001}}

def test_ledger_owned_and_open():
    led = FirestorePurchaseLedger(FakeFirestore())
    led.record_placed(_rec(purchase_id=1, status="placed"))
    led.record_placed(_rec(purchase_id=2, status="placed"))
    led.mark(2, "superseded", superseded_by=3)
    assert led.owned_ids() == {1, 2}
    assert [r["purchase_id"] for r in led.list_open()] == [1]

def test_forwarder_store_multi_tracking():
    f = FirestoreForwarderStore(FakeFirestore())
    f.record_submitted("huohanhan", ["O1"], ["T1", "T2"], "", {"success": True})
    assert f.get_submitted_order_ids("huohanhan") == {"O1"}

def test_blocked_store_stage_and_resolve():
    b = FirestoreBlockedStore(FakeFirestore())
    b.record_blocked("O1", 7, ["T1"], "canceled", stage="shipped_by_1688")
    assert b.get_blocked_order_ids() == {"O1"}
    b.record_resolved("O1", "mark_done", None, "james")
    assert b.get_blocked_order_ids() == set()

def test_notification_log_last():
    n = FirestoreNotificationLog(FakeFirestore())
    assert n.last("pay/1") is None
    n.record("pay/1", "d1")
    assert n.last("pay/1")["digest"] == "d1"
```
- [ ] **Step 2:** `uv run python -m pytest tests/order_processing/test_firestore_stores.py -q` → FAIL（import error）。
- [ ] **Step 3:** 實作 `store_types.py`、`firestore_client.py`、`firestore_stores.py`、`fake_firestore.py`；加依賴（`uv add google-cloud-firestore opencc-python-reimplemented`）；`config.FIREBASE_PROJECT_ID`。
- [ ] **Step 4:** 刪三個 SQLite store 類與其測試；`prepare_purchase.py`/`fulfill_shipping.py`/`blocked_handling.py` 的型別改用 `store_types` Protocol；`main.py` 的 `cmd_orders_*` 改用 `firestore_stores.*(get_client())`。`config.ORDER_PROCESSING_DB` 保留（`ProductScanStore` 仍用）。
- [ ] **Step 5:** 寫 ADR 0013（Firestore 為訂單處理工作流狀態與收益事實的儲存；BigSeller 仍是庫存真相；取代 0001），0001 標 Superseded。
- [ ] **Step 6:** `uv run python -m pytest -q` → 全 PASS。
- [ ] **Step 7: Commit** `feat(order-processing): store workflow state in Firestore`

---

### Task 3: Slack 通知器

**Files:**
- Create: `modules/notify/__init__.py`、`modules/notify/slack.py`、`tests/test_notify_slack.py`
- Modify: `config.py`（`SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")`）

**Interfaces:**
- Consumes: `NotificationLogLike`（Task 2）
- Produces:
  - `send_slack(text: str, webhook_url: str | None = None) -> bool`：curl POST JSON `{"text": text}`；回應 body 為 `ok` 才算成功；沒設 URL → 印警告回 False。
  - `class Notifier`: `__init__(self, log: NotificationLogLike, sender: Callable[[str], bool] = send_slack, now: Callable[[], datetime] = utcnow)`；`notify(key: str, text: str, *, remind_after: timedelta | None = None) -> bool`：digest = sha256(text)；`last(key)` 不存在或 digest 不同 → 發；相同且設了 `remind_after` 且距上次 ≥ 該值 → 發；否則不發回 True。只有 sender 回 True 才 `record`。回傳「該發的都發成功」。

- [ ] **Step 1: Write failing tests**
```python
def test_dedupes_same_text(): ...          # 同 key 同文字第二次 sender 不被呼叫
def test_resends_when_text_changes(): ...  # 文字變 → 再發
def test_reminder_after_interval(): ...    # remind_after=24h，now 前進 25h → 再發；前進 1h → 不發
def test_failed_send_not_recorded():
    n = Notifier(FirestoreNotificationLog(FakeFirestore()), sender=lambda t: False)
    assert n.notify("k", "hi") is False
    assert n._log.last("k") is None
```
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作。
- [ ] **Step 4:** 跑 → PASS。
- [ ] **Step 5: Commit** `feat(notify): add Slack notifier with dedupe`

---

### Task 4: BigSeller 讀取 fail-loud 與取消拼字

**Files:**
- Modify: `modules/bigseller/orders.py`（`get_out_of_stock_orders`、`get_shopee_orders`、`get_purchase_list` 呼叫端）、`modules/order_processing/prepare_purchase.py`（`BigSellerDeps` 讀取改 strict）
- Test: `tests/order_processing/test_get_out_of_stock_orders.py`、`tests/bigseller/test_orders_strict.py`（新）

**Interfaces:**
- Produces: `class BigSellerReadError(RuntimeError)`（`modules/bigseller/orders.py`）。`get_out_of_stock_orders(page, page_size, strict: bool = True)`、`get_shopee_orders(status, page, page_size, strict: bool = False)`：strict 時 `resp` 空或 `code != 0` → raise `BigSellerReadError`。`BigSellerDeps._drafts` 改用 `get_purchase_list(..., strict=True)`。常數 `SHOPEE_STATUS_CANCELLED = "<Task 1 Step 5 結果>"`，`blocked_handling.py:56` 與 `get_shopee_order_detail` 預設清單都改用它。

- [ ] **Step 1: Write failing tests**：`test_out_of_stock_api_error_raises`（patch `bs_post_json` 回 `{"code": -1}` → `pytest.raises(BigSellerReadError)`）；`test_shopee_orders_strict_raises`；`test_cancelled_status_constant_used`（`get_shopee_order_detail` 預設 statuses 含 `SHOPEE_STATUS_CANCELLED`）。
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作。
- [ ] **Step 4:** `uv run python -m pytest -q` → PASS。
- [ ] **Step 5: Commit** `fix(bigseller): fail loudly on order/purchase read errors`

---

### Task 5: 不拆單 + dry-run 計數

**Files:**
- Modify: `modules/order_processing/prepare_purchase.py`
- Test: `tests/order_processing/test_prepare_purchase.py`

**Interfaces:**
- Produces: `prepare_purchase` 回傳 dict 新增/改義：`planned_create: int`、`planned_overwrite: int`、`planned_rebuild: int`（dry-run 也填）、`excluded_orders: list[dict]`（`{"platform_order_id", "reason": "unresolved_supplier" | "ambiguous_spec", "var_skus": list[str], "message": str}`，取代 `unresolved` 與 `ambiguous` 兩鍵）。`created/overwritten` 維持只算實際執行。

- [ ] **Step 1: Write failing tests**
```python
def test_unresolved_line_excludes_whole_order():
    # O1 兩項：A 可解析、B 解析不到 → O1 完全不進批次
    r = pp.prepare_purchase(TwoLineOneUnresolvedDeps(), store, commit=True, place=True)
    assert deps.created == []
    assert r["excluded_orders"][0]["platform_order_id"] == "O1"
    assert r["excluded_orders"][0]["reason"] == "unresolved_supplier"

def test_dry_run_reports_planned_counts():
    r = pp.prepare_purchase(FakeDeps(), store, commit=False)
    assert r["planned_create"] == 1 and r["created"] == 0
```
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作：解析迴圈收集被排除訂單，組批次前過濾掉；計數依 action 累計。`main.py cmd_orders_prepare_purchase` 輸出改讀新鍵。
- [ ] **Step 4:** 跑全部 → PASS。
- [ ] **Step 5: Commit** `fix(order-processing): exclude whole order when any line is unpurchasable`

---

### Task 6: 付款才鎖定、只動自有單、取消重建（依 Task 1 閘門）

**Files:**
- Modify: `modules/order_processing/state_view.py`、`modules/order_processing/prepare_purchase.py`、`modules/bigseller/orders.py`（新 API 函式）
- Create: `docs/adr/0014-purchase-lock-on-payment.md`；`docs/adr/0004-*.md` 加「修訂：見 0014」
- Test: `tests/order_processing/test_state_view.py`、`test_prepare_purchase.py`、`test_bigseller_deps.py`

**Interfaces:**
- Consumes: `PurchaseLedgerLike`（Task 2）、Task 1 的付款欄位與取消端點
- Produces:
  - `modules/bigseller/orders.py`: `get_purchase_payment_status(purchase: dict) -> Literal["unpaid", "paid", "unknown"]`（純函式，依 Task 1 欄位判斷；沒有 `aliOrderNo` → `"unpaid"`）、`cancel_unpaid_ali_order(purchase_id: int) -> bool`（Task 1 端點）
  - `PurchaseDeps` 新方法：`cancel_unpaid_order(purchase_id: int) -> bool`
  - `list_existing_drafts_by_key()` 每個 entry 改為 `{"purchases": [{"purchase_id": int, "state": int, "ali_order_no": str | None, "payment": str, "order_nos": list[str]}]}`（同鍵所有採購單，不再只取最新）
  - `decide_purchase_actions(batches, existing_by_key, saved_fingerprints, owned_ids: set[int]) -> list[BatchAction]`，`BatchAction.action` ∈ `"create" | "overwrite" | "rebuild" | "cancel" | "skip" | "skip_locked"`，新增欄位 `replace_purchase_ids: list[int]`
  - `prepare_purchase(deps, store, ledger: PurchaseLedgerLike, commit=False, warehouse_id=<PURCHASE_WAREHOUSE_ID>, place=False)`；回傳新增 `placed: list[dict]`（`{"purchase_id", "supplier_id", "supplier_name", "ali_order_no", "amount", "order_nos", "replaced": list[int]}`）、`canceled: list[int]`
- 決策規則（`state_view.decide_purchase_actions`，同鍵）：
  1. 「已占用訂單」= 該鍵所有**非自有**採購單的 order_nos ∪ 所有**已付款或 unknown**採購單的 order_nos。批次先剔除已占用訂單；剔除後為空且無自有未付款單 → `skip_locked`。
  2. 自有、未付款、有 `ali_order_no` 的單 = 可重建單。
  3. 剩餘訂單集合指紋 == 已存指紋且有可重建單或草稿 → `skip`。
  4. 有可重建單 → 剩餘訂單非空 `rebuild`（`replace_purchase_ids` = 可重建單），為空 `cancel`。
  5. 只有自有、無 `ali_order_no` 的草稿 → `overwrite`（沿用刪草稿重建）。
  6. 否則 `create`。
- 執行（commit）：`rebuild`/`cancel` 先對每個 `replace_purchase_ids` 呼叫 `cancel_unpaid_order`，任何一個 False → 記錯誤、**不 place**、不改帳本；全部成功 → `ledger.mark(old, "superseded" 或 "canceled", superseded_by=new)`，再 `delete_draft`，`rebuild` 再 place。place 成功後 `ledger.record_placed(...)`（status `"placed"`，`amount` 由 Task 1 的採購單欄位取得，取不到為 None）。

- [ ] **Step 1: Write failing tests**（state_view）
```python
def test_unpaid_owned_rebuilds_with_new_order(): ...      # 自有未付款含 O1；批次 O1+O2 → rebuild，replace=[old]
def test_paid_purchase_locks_its_orders_new_order_created(): ...  # 已付款含 O1；批次 O1+O2 → create 只含 O2
def test_unknown_payment_treated_as_paid(): ...
def test_orders_in_unowned_purchase_not_rebought(): ...   # 非自有未付款含 O1；批次 O1 → skip_locked
def test_all_orders_canceled_cancels_unpaid(): ...        # 自有未付款含 O1；批次空鍵仍出現 → cancel
```
（`decide_purchase_actions` 需要對「有自有未付款單但本輪批次沒有該鍵」也產生 `cancel`：迭代鍵 = batches 鍵 ∪ 含自有未付款單的鍵。）
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作 `state_view`。
- [ ] **Step 4: Write failing tests**（prepare_purchase）
```python
def test_rebuild_cancel_failure_never_places():
    deps = RebuildDeps(cancel_ok=False)
    r = pp.prepare_purchase(deps, store, ledger, commit=True, place=True)
    assert deps.placed_calls == [] and r["errors"]

def test_rebuild_success_marks_superseded_and_records_new():
    ...
    assert ledger.get(OLD)["status"] == "superseded" and ledger.get(NEW)["status"] == "placed"
```
- [ ] **Step 5:** 跑 → FAIL；實作 `prepare_purchase` + `BigSellerDeps`（`cancel_unpaid_order`、新 `list_existing_drafts_by_key`；`place_draft` 內原本的「已下單就 skip」防護改用新結構，仍保留以防重複下單）。
- [ ] **Step 6:** 寫 ADR 0014（鎖定改為付款；只動自有單；取消成功才重建），0004 註記修訂；`CONTEXT.md` 的「採購鎖定」定義同步更新。
- [ ] **Step 7:** `uv run python -m pytest -q` → PASS。
- [ ] **Step 8: Commit** `feat(order-processing): lock purchases on payment and rebuild unpaid owned orders`

---

### Task 7: 一單多採購、逐項運單號、分包

**Files:**
- Modify: `modules/bigseller/orders.py`（`build_purchase_order_mapping`）、`modules/order_processing/fulfillment_types.py`、`fulfill_shipping.py`、`modules/huohanhan/client.py`、`modules/fulfill/base.py`、`modules/fulfill/huohanhan_provider.py`
- Test: `tests/order_processing/test_fulfill_shipping.py`、`test_huohanhan_payload.py`

**Interfaces:**
- Produces:
  - `build_purchase_order_mapping() -> dict[str, list[dict]]`：值為該蝦皮訂單相關的**所有**採購單 `{purchase_id, tracking_nos: list[str], state, items: list[{"var_sku", "qty"}]}`（`tracking_nos` 依 Task 1 格式拆分；`items` 由採購單明細取得）
  - `FulfillmentDeps.list_purchase_order_mapping() -> dict[str, list[PurchaseMapping]]`；`PurchaseMapping` 加 `tracking_nos: list[str]`、`items: list[dict]`，移除 `tracking_no`
  - `FulfillmentDeps.place_forwarder_order(pending_order, goods_tracking: dict[str, str]) -> JsonDict`（key = `shopOrderGoods[].id`，value = 運單號）
  - 純函式 `assign_goods_tracking(pending_order: Mapping, purchases: list[PurchaseMapping], goods_sku_field: str) -> dict[str, str] | None`（`fulfill_shipping.py`）：只有一張採購單且只有一個運單號 → 所有 goods 用它；否則依 `goods_sku_field`（Task 1 Step 4 的欄位名）對 `var_sku` 找所屬採購單，該採購單只有一個運單號則用它；任何 goods 對不到或所屬採購單有多個運單號 → 回 None。
  - `_build_place_order_payload(pending_order, goods_tracking: dict[str, str], warehouse_id)`：每筆 `orderShip.shipNo = goods_tracking[goods.id]`
  - `FulfillmentResult` 新增 `needs_manual: list[dict]`（`{"platform_order_id", "reason": "unmapped_parcels"}`）、`waiting_tracking: list[str]`
  - candidate 條件：該訂單所有採購單 `state == 1` 且 `tracking_nos` 非空，否則列入 `waiting_tracking`

- [ ] **Step 1: Write failing tests**
```python
def test_two_suppliers_each_goods_gets_own_tracking():
    tr = assign_goods_tracking(pending(goods=[("g1","A-红"),("g2","B-蓝")]),
        [pm(tracking_nos=["T1"], items=[{"var_sku":"A-红","qty":1}]),
         pm(tracking_nos=["T2"], items=[{"var_sku":"B-蓝","qty":1}])], "modelSku")
    assert tr == {"g1": "T1", "g2": "T2"}

def test_waits_until_all_purchases_have_tracking(): ...   # 一張有 T1、一張沒有 → 不送，waiting_tracking 含該單
def test_split_parcel_unmappable_needs_manual(): ...      # 單一採購 tracking_nos=["T1","T2"] → None → needs_manual
def test_payload_uses_per_goods_tracking(): ...           # orderShip[0].shipNo=="T1", [1]=="T2"
```
（`"modelSku"` 換成 Task 1 Step 4 查到的實際欄位名。）
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作上述介面；`resolve_blocked_order` 的 `reassign_order` 改傳 `goods_tracking`（所有 goods 用原紀錄的第一個運單號，原行為）。
- [ ] **Step 4:** `uv run python -m pytest -q` → PASS。
- [ ] **Step 5: Commit** `fix(fulfillment): send each item's own 1688 tracking to huohanhan`

---

### Task 8: 取消偵測（四個時間點）

**Files:**
- Create: `modules/order_processing/cancellation.py`、`tests/order_processing/test_cancellation.py`
- Modify: `modules/order_processing/blocked_handling.py`（刪 `detect_and_block_canceled_orders`；`BlockedHandlingDeps` 保留給 `resolve_blocked_order`）、`fulfill_shipping.py`（移除內嵌偵測與 `blocked_store`/`blocked_deps` 參數，改收 `blocked_ids: set[str]` 參數以排除）

**Interfaces:**
- Consumes: `PurchaseLedgerLike`、`ForwarderStoreLike`、`BlockedStoreLike`
- Produces:
  - `class CancellationDeps(Protocol)`: `list_canceled_order_ids(since: datetime) -> set[str]`（分頁讀取取消狀態蝦皮訂單直到早於 since；讀取錯誤 raise）、`get_purchase(purchase_id: int) -> dict`（含 `state`、`tracking_nos`、`payment`）、`cancel_or_refund_paid_order(purchase_id: int) -> bool | None`（None = 無此能力，依 Task 1 Step 3）
  - `@dataclass CancellationOutcome`: `platform_order_id: str`、`stage: Literal["before_payment", "paid_unshipped", "shipped_by_1688", "after_forwarder"]`、`purchase_id: int | None`、`action: Literal["none", "auto_canceled", "blocked"]`、`detail: str`
  - `detect_cancellations(deps: CancellationDeps, ledger, forwarder_store, blocked_store, *, provider: str, since: datetime, commit: bool) -> list[CancellationOutcome]`
- 規則：只看 ledger 開放中採購單（`list_open`）的 order_nos 與已送貨代的訂單。
  - 採購單未付款 → `before_payment`、`action="none"`（交給 Task 6 下輪重建處理）。
  - 已付款、`state` ≠ 1 且無運單號 → `paid_unshipped`：若該採購單所有 order_nos 都已取消且 `cancel_or_refund_paid_order` 回 True → `auto_canceled`、`ledger.mark(pid, "canceled")`；其餘 → `blocked`。
  - 已有運單號、未送貨代 → `shipped_by_1688`、`blocked`。
  - 已送貨代 → `after_forwarder`、`action="none"`，detail 註記「貨轉為台灣倉庫存」，`blocked_store.record_blocked(..., stage="after_forwarder")` 後立即 `record_resolved(..., "mark_done", "returned to Taiwan stock", "system")` 以留紀錄。
  - 已在 blocked/resolved 的訂單不重複處理。
  - `commit=False` → 只回傳 outcomes，不寫任何 store、不呼叫取消。

- [ ] **Step 1: Write failing tests**：`test_before_payment_no_action`、`test_paid_unshipped_all_canceled_auto_cancels`、`test_paid_unshipped_partial_cancel_blocks`、`test_paid_unshipped_no_capability_blocks`（回 None）、`test_shipped_by_1688_blocks`、`test_after_forwarder_records_resolved_stock`、`test_dry_run_writes_nothing`、`test_list_canceled_error_propagates`。
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作 `cancellation.py` 與正式 `BigSellerCancellationDeps`（同檔）。
- [ ] **Step 4:** `uv run python -m pytest -q` → PASS。
- [ ] **Step 5: Commit** `feat(order-processing): detect cancellations at every purchase stage`

---

### Task 9: `orders cycle` 編排與通知

**Files:**
- Create: `modules/order_processing/cycle.py`、`tests/order_processing/test_cycle.py`
- Modify: `main.py`（`orders cycle [--commit]`）、`config.py`（`PAID_NO_TRACKING_ALERT_HOURS = 72`、`TRACKING_NOT_IN_FORWARDER_ALERT_HOURS = 48`、`UNPAID_REMINDER_HOURS = 24`）

**Interfaces:**
- Consumes: Task 2–8 全部
- Produces:
  - `@dataclass CycleDeps`: `purchase: PurchaseDeps`、`fulfillment: FulfillmentDeps`、`cancellation: CancellationDeps`、`advance: Callable[[bool], dict]`（正式 = `advance_purchase_pipeline(dry_run=...)`）、`refresh_payments: Callable[[], dict[int, str]]`（purchase_id → payment，正式由 `get_purchase_list` + `get_purchase_payment_status`）
  - `@dataclass CycleStores`: `fingerprints`、`ledger`、`forwarder`、`blocked`、`notifications`
  - `@dataclass CycleReport`: `advanced: dict`、`cancellations: list[CancellationOutcome]`、`fulfillment: FulfillmentResult`、`purchase: dict`、`stale: list[dict]`、`errors: list[str]`、`messages: list[tuple[str, str]]`（(dedupe_key, text)）
  - `run_cycle(deps: CycleDeps, stores: CycleStores, notifier: Notifier | None, *, commit: bool, now: datetime) -> CycleReport`
  - `build_messages(report: CycleReport, ledger: PurchaseLedgerLike, now: datetime) -> list[tuple[str, str]]`（純函式）
- 步驟順序：(0) `stores.ledger.list_open()` 先讀一次（Firestore 不可用 → raise，結束前不碰 BigSeller）→ (1) `advance` → (2) `refresh_payments`，ledger 中 placed→paid 的寫 `paid_at` → (3) `detect_cancellations` → (4) `fulfill_shipping`（排除 blocked）→ (5) `prepare_purchase(place=commit)` → (6) 逾時檢查（已付款超過 `PAID_NO_TRACKING_ALERT_HOURS` 無運單、有運單超過 `TRACKING_NOT_IN_FORWARDER_ALERT_HOURS` 不在貨代清單）→ (7) 組訊息、`commit` 時經 notifier 發送。任一步驟 raise → 記入 `errors`，**之後的寫入步驟（4、5）不執行**，仍發錯誤通知。
- 訊息與 dedupe key：
  - `pay/{purchase_id}`：每張新下或重建的待付款單（供應商名、1688 訂單號、金額、蝦皮訂單號；重建時列「取代 #舊id（已取消）」），`remind_after=UNPAID_REMINDER_HOURS`，ledger 中仍 placed 的每輪都送進 notifier（由去重決定是否發）。
  - `excluded/{platform_order_id}`：配不到/多重綁定的訂單。
  - `place-failed/{supplier_id}`：下單失敗原因與受影響訂單。
  - `cancel/{platform_order_id}`：每個 action ≠ none 或 stage=after_forwarder 的取消。
  - `manual-parcel/{platform_order_id}`：分包對不上。
  - `stale/{kind}/{id}`：逾時提醒。
  - `cutover/unowned`：第一次 commit（ledger 為空）時列出所有非自有、未付款且有 aliOrderNo 的採購單。
  - `error/{step}`：步驟錯誤（文字含錯誤訊息前 300 字）。
- CLI：`orders cycle` 印出各步驟摘要；`--commit` 才寫入與發 Slack；`errors` 非空或任何通知發送失敗 → `sys.exit(1)`。

- [ ] **Step 1: Write failing tests**（全部用假 deps + FakeFirestore + 假 sender）
```python
def test_cycle_dry_run_no_writes_no_slack(): ...
def test_cycle_read_failure_aborts_before_purchase():   # purchase.get_out_of_stock_orders raise → place 未被呼叫，errors 有值
def test_cycle_store_unavailable_no_writes():           # ledger.list_open raise → advance 也未被呼叫
def test_cycle_slack_failure_exit_nonzero():            # sender 回 False → report 標記 notify_failed，CLI exit 1（用 main 函式測）
def test_payment_message_lists_supplier_amount_orders()
def test_rebuild_message_mentions_replaced_purchase()
def test_cutover_message_only_first_commit()
def test_paid_transition_sets_paid_at()
```
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作 `cycle.py`、CLI。
- [ ] **Step 4:** `uv run python -m pytest -q` 與 `uv run python main.py orders cycle --help` → PASS / 顯示說明。
- [ ] **Step 5: Commit** `feat(order-processing): add orders cycle orchestrator with Slack notices`

---

### Task 10: 排程入口、移除 Telegram/Hermes、部署文件

**Files:**
- Create: `scripts/cron_order_cycle.py`、`tests/test_cron_order_cycle.py`、`deploy/mamababy-order-cycle.service`、`deploy/mamababy-order-cycle.timer`
- Modify: `scripts/cron_utils.py`（刪 `send_telegram`；`_CRON_HOME` 預設 `~/.mamababy`，`_CRON_ENV` 預設 `~/.mamababy/.env`；刪 Hermes 路徑）、`docs/deploy-linux.md`（改寫：安裝 uv/依賴、`.env` 鍵清單 `SLACK_WEBHOOK_URL`/`GOOGLE_APPLICATION_CREDENTIALS`/`FIREBASE_PROJECT_ID`/`ALI_1688_AK`/貨憨憨帳密/BigSeller 帳密/Gmail OTP、systemd timer 每 2 小時、`bs login` 首次登入）、`CLAUDE.md` + `AGENTS.md`（order_processing 段：Firestore、`orders cycle`、Slack、鎖定=付款）、`tests/run_all.py`（如有引用舊 cron 腳本則移除）
- Delete: `scripts/cron_new_order_alert.py`、`scripts/cron_fulfill_pipeline.py`、`tests/test_cron_new_order_alert.py`、`tests/test_cron_routes.py`（若只測舊 cron）

**Interfaces:**
- Consumes: `run_cycle`、`Notifier`、`firestore_stores`、`cron_utils.setup_env`、`cron_utils.is_session_expired`、BigSeller 自動重登（沿用 `run_with_auto_login` 的重登邏輯，改成 in-process：捕捉 session 過期 → `bs login` → 重跑一次 `run_cycle`）、`huohan_login()`
- Produces: `scripts/cron_order_cycle.py main(argv: list[str] | None = None) -> int`；退出碼 0 = 無錯誤。

- [ ] **Step 1: Write failing tests**：`test_relogin_once_on_session_expired`（第一次 run_cycle raise session 過期 → 呼叫 login → 第二次成功 → 回 0）、`test_second_failure_returns_nonzero_and_notifies`、`test_no_telegram_in_cron_path`（`grep` 不到 `send_telegram`：用 `inspect.getsource(cron_utils)` 斷言）。
- [ ] **Step 2:** 跑 → FAIL。
- [ ] **Step 3:** 實作；刪舊 cron 與其測試；寫 systemd 檔（`OnCalendar=*-*-* 00/2:05:00`、`Persistent=true`、`ExecStart=<repo>/.venv/bin/python scripts/cron_order_cycle.py`）。
- [ ] **Step 4:** `uv run python -m pytest -q` 與 `uv run python main.py test` → 全 PASS；新 ISSUE/FAIL 記到 `issue.md`。
- [ ] **Step 5: Commit** `feat(deploy): run order cycle every 2h via systemd timer, Slack only`
- [ ] **Step 6（需業主同意）:** 向業主索取 Slack webhook 與頻道、確認 ssh 部署；`ssh claw-arm-1` 部署、跑一次 `orders cycle`（dry-run）核對輸出，再跑一次 `--commit` 並請業主確認 Slack 訊息；啟用 timer。
- [ ] **Step 7:** 開 PR（英文），完成後依全域規則轉 ready。

---

## Self-review 紀錄

- Spec 覆蓋：排程/循環（T9、T10）、批次規則與自有單（T6）、付款通知（T9）、通知貨代與分包（T7）、通知去重（T3、T9）、例外表各列（T5 配不到、T6 下單失敗/重建、T8 四種取消、T9 錯誤與逾時）、必修缺陷 1–9（T5、T7、T5、T4、T4+T8、T8、T9、T3+T10、T10）、待查證（T1）、Firebase（T2，含收益事實欄位）、部署與業主提供項（T10 Step 6）。
- 留給實作者：Slack 文字細節、systemd vs cron（已選 systemd，可改）、Firestore 欄位命名細節（collection 名已定）。
