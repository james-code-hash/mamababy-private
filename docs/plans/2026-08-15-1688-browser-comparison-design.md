# 1688 三路瀏覽器資料取得 MVP 設計

## 目標

針對商品 `988805223565`，比較三種入口是否能取得同一份完整資料：

1. Chrome → BigSeller 內嵌 1688
2. Camoufox → BigSeller 內嵌 1688
3. Camoufox → 1688 原生商品頁

每條路徑都要讀取商品資訊、完整 SKU、規格 ID、SKU 價格（逐 SKU 價格或數量階梯價）與庫存，並清楚記錄登入要求、驗證頁、缺欄位與解析失敗。MVP 只讀取，不寫入 BigSeller 採購池。

## 驗證前提

- Chrome／BigSeller：使用者先手動登入 BigSeller，測試程式不接觸或輸出密碼、Cookie、Token。
- Camoufox／BigSeller：使用獨立持久 Profile；首次執行由使用者手動完成 BigSeller 登入。
- Camoufox／1688：使用另一個獨立持久 Profile；若 1688 要求登入或驗證，由使用者手動處理。
- CAPTCHA、安全驗證與反爬頁只分類與記錄，不自動繞過、不輪換代理。

## 架構

新增獨立的比較模組，不直接改變現有 `sku-preview` 的正式行為。三個 Adapter 共用同一個輸出格式與解析器：

- `ChromeBigSellerAdapter`：連接已登入的 Chrome，進入 BigSeller 尋源頁與其 1688 內嵌內容。
- `CamoufoxBigSellerAdapter`：啟動 Camoufox 持久 Profile，進入 BigSeller 內嵌 1688。
- `CamoufoxDirect1688Adapter`：啟動 Camoufox 持久 Profile，直接開啟 1688 商品頁。
- `sku_binding` 的 HTML 結構化資料解析與 SKU 對照邏輯：以 `platformSkuId` 優先，其次 `specId`，最後才使用正規化規格文字。

BigSeller API 的 `addAli1688Product` 回應作為 SKU 身分基準；瀏覽器頁面只負責補商品頁實際價格、階梯價與庫存。無法安全對照的列標記為失敗，不猜測價格。

## 輸出與資料流

預計提供 `bs purchase sku-compare 988805223565`，輸出 JSON 與人類可讀摘要。每條路徑各自保存暫存 HTML／結構化快照，並回傳：

- `route`, `offer_id`, `page_url`, `auth_status`
- `sku_count`, `rows[]`
- `platformSkuId`, `specId`, `sku`, `price`, `priceMode`, `priceTiers`, `canBookCount`
- `elapsed_ms`, `status`, `blocked_reason`

報告會比較三條路徑的 SKU 數量、ID 覆蓋率、價格覆蓋率、價格值與庫存差異；同一商品的逐 SKU 價格與階梯價不混為同一種價格。

## 驗收條件

1. 三條路徑都能獨立完成或明確回報失敗原因。
2. 至少一條路徑取得完整 SKU 與價格資料，且與現有 `988805223565.html` 快照可對照。
3. 若遇驗證頁，報告能區分「被攔截」與「頁面沒有價格」而不是產生空白成功結果。
4. 不呼叫 `saveAli1688Sku`，不修改採購池與商品資料。
5. 通過本地解析器單元測試，再進行一次真實商品整合測試；10 商品批次留到 MVP 通過後。

## 不在 MVP 範圍

- 自動解 CAPTCHA 或繞過安全驗證
- 代理輪換、指紋對抗策略調優
- 自動批量抓取 10 個以上商品
- 將比較結果直接寫回 BigSeller
