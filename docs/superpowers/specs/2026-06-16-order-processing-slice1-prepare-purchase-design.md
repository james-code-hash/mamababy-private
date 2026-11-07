# Slice 1 設計：基礎 + prepare-purchase（訂單驅動採購）

日期：2026-06-16
範圍：第一輪訂單處理的第一個垂直切片。

## 背景

本切片建立在本 session 兩個架構轉向之上：

- **BigSeller 為庫存／分配真相來源**（ADR 0010）：庫存數量、訂單分配、保留全由 BigSeller 原生 WMS 處理，本地只唯讀。庫存優先「免費」——BigSeller 同步即自動分配，只有缺貨訂單需採購。ADR 0008、0009 已作廢。
- **訂單驅動採購，非補貨**（ADR 0012）：買正好缺貨來源訂單需要的量、採購單 `note` 綁定蝦皮訂單號；不採用 BigSeller 的補貨建議與 Purchase Plan。採購批次（ADR 0003）與採購覆蓋（ADR 0004）為核心邏輯保留。
- **薄 store（T1）**：凡能從 BigSeller 即時推導的狀態都不本地鏡像。訂單處理狀態是「計算視圖」，不是儲存表。雙寫必漂移。

詞彙以 [CONTEXT.md](../../../CONTEXT.md) 為準。

## 範圍

**包含**：薄 store（採購批次指紋表）＋訂單處理狀態計算視圖（純函式）＋ `prepare-purchase` 命令——讀缺貨來源訂單 → 按供應商組採購批次 → 算指紋 → 建立／覆蓋 1688 草稿 → 更新本地指紋。

**不包含**（後續 slice）：`fulfill-shipping`（貨運履約→貨代，Slice 2）；`blocked` 與阻塞處置（Slice 3）；採購送出後的鎖定流轉細節（本切片止於建草稿與覆蓋，付款送出沿用既有 submit）。

## API 依據

完整探索見 [bigseller-api-notes.md](../../bigseller-api-notes.md)。Slice 1 linchpin：

- **缺貨來源訂單** = `POST /api/v1/order/new/pageList.json`，body `status:"new"` + `packState:"4"`。回應 `data.page.rows[]`，缺貨數在 `data.stateMap.pack4`。
- 每筆 row 帶 `platformOrderId`（蝦皮訂單號）、`error=html.order.inventory.no.enough.stock`、`errorMsg`（缺貨 SKU）、`warehouseId`/`shipmentWarehouse`（多倉）、`orderItemList[]`（`itemSku`/`varSku`/`varAttr`/`quantity`）。
- 沿用既有呼叫模式：agent-browser `eval_js()` 在已登入頁 fetch，共用 session cookie。

## 架構與元件

新模組 `modules/order_processing/`，各檔單一職責、介面清晰、可獨立測試：

- `store.py` — 薄 SQLite，可替換 Store 介面。Slice 1 只一張表，鍵為（供應商, 倉庫）：
  ```
  purchase_batch_fingerprint(
    supplier_id   INTEGER,
    warehouse_id  INTEGER,
    fingerprint   TEXT,       -- 來源訂單集合 + 銷售SKU + 數量 的摘要
    purchase_id   INTEGER,    -- 對應 BigSeller 草稿 id，可空
    computed_at   TEXT,
    PRIMARY KEY (supplier_id, warehouse_id)
  )
  ```
  阻塞處置決定、重試 metadata 表留到 Slice 3（YAGNI）。

- `state_view.py` — 純函式，無 I/O：
  ```
  decide_purchase_actions(
    out_of_stock_orders,   # BigSeller packState=4 rows
    purchase_mapping,      # build_purchase_order_mapping()
    saved_fingerprints,    # 本地 store
  ) -> list[BatchAction]
  ```
  `BatchAction` 動作 ∈ {`建立草稿`, `覆蓋草稿`（指紋變了）, `跳過`（指紋未變）, `略過-已鎖定`（採購已付款）}，每（供應商, 倉庫）批次一個。

- `fingerprint.py` — 由（來源訂單集合、供應商、倉庫、銷售 SKU、數量）算採購批次指紋；同需求同指紋、需求變則指紋變。一張 1688 採購寄到單一貨代倉地址，故批次以（供應商, 倉庫）為鍵，不可只按供應商混倉。

- `prepare_purchase.py` — 編排：抓缺貨單 → 解析（供應商/倉庫/銷售SKU/數量/蝦皮訂單號）→ 按（供應商, 倉庫）組批次算指紋 → `decide_purchase_actions` → dry-run 預覽或 `--commit` 執行 → 更新指紋。

- `modules/bigseller/orders.py` — 新增 `get_out_of_stock_orders()`（packState=4 翻頁）。
- 既有 `auto_purchase.py` 的供應商分組（擴為供應商＋倉庫）+ 草稿建立/覆蓋邏輯抽進 `prepare_purchase.py`，與 1200 行的 `main.py` 解耦。

## 資料流

```
缺貨來源訂單(BigSeller) ─┐
現有採購映射(BigSeller)  ─┼─> decide_purchase_actions(純函式) ─> [BatchAction]
本地指紋(store)          ─┘                                          │
                                                  dry-run 預覽 / --commit
                                                          │
                                       create_purchase_draft / 覆蓋 (BigSeller→1688)
                                                          │
                                                  更新本地指紋(store)
```

## 錯誤處理

- BigSeller API `code != 0` → 該批次標記失敗、記錄原因、不中斷其他批次（沿用既有 logging）。
- 供應商解析不到（skuId 與 varSku 都對不到貨源）→ 該訂單列為「無法採購」，dry-run/輸出明確標示，不靜默吞掉。
- `--commit` 為對外寫入（建 1688 草稿）：預設 dry-run，必須顯式 `--commit` 才執行。

## 測試（TDD）

- `state_view.decide_purchase_actions`：表格驅動單元測試。邊界：已鎖定（已付款）略過、指紋未變跳過、多訂單共用同供應商合併一批、部分缺貨整單走採購（ADR 0011）。
- `fingerprint`：同需求→同指紋；改數量/改訂單集合→不同指紋。
- `store`：指紋 round-trip、覆寫。
- BigSeller client：mock `eval_js` 邊界做單元測試；live 整合測試手動選跑（需登入 session）。

## 連帶文件更新

- **ADR 0001**（本地 SQLite store）需改寫為薄 store（T1）：store 只存 BigSeller 不模型化的東西（指紋、之後的阻塞處置決定與重試 metadata），訂單處理狀態為計算視圖。此改寫納入本切片實作計畫。

## 先決條件與待辦

- Playwright/agent-browser 需登入 BigSeller（同既有 session 概念）才能跑 live。
- Slice 2 再探：訂單列表區分「已分配待打包」的 packState；fulfill-shipping 與貨代多倉對應。
- Slice 3 再探：確認收貨（Purchase Receiving）端點，供 keep_in_stock。

## 非目標

不重做 BigSeller 已有的庫存／分配／補貨建議；不引入補貨模型；不在本切片處理拆批寄（整單走採購，ADR 0011）。
