# 選品到上架 第 1 期（上架即綁定）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 CLI 把一個 1688 商品變成「所有商家 SKU 已建立、已綁定、已用專案 1 的查法驗證」的 BigSeller 蝦皮草稿；補綁既有商品；每天健檢貨源；發佈指令與第 15 天開折扣排程做好但受閘門保護。

**Architecture:** 新模組 `modules/listing/`，沿用 order_processing 的模式：純函式（命名、定價、規格挑選、草稿改寫、健檢分類）與 I/O 分離，所有 BigSeller／1688／Firestore／Slack 邊界都經 `typing.Protocol` 定義的 deps 注入，測試注入假物件。CLI 新增 `python main.py listing <action>`，寫入預設 dry-run。

**Tech Stack:** Python 3.13（uv）、OpenCC（`opencc-python-reimplemented`）、`google-cloud-firestore`、curl（BigSeller 走 `http_client.py`，1688 頁面、LLM、Slack 都是 curl）、pytest。

**Spec:** `docs/superpowers/specs/2026-10-22-listing-flow-design.md`（第 6、8、10、11、12 節是本計畫範圍；第 7、9 節是第 2、3 期，另寫計畫）

## 前置條件

- **專案 1 的 PR（分支 `feat/order-cycle`）合併進 main 之後才開始 Task 2 以後的工作**，開工前先用 ccd_host `sync_with_base_branch` 同步。本計畫共用它新增的：`modules/notify/slack.py`（`send_slack`、`Notifier`）、`modules/order_processing/firestore_client.get_client()`、`modules/order_processing/firestore_stores.FirestoreNotificationLog`、`tests/order_processing/fake_firestore.FakeFirestore`、`config.FIREBASE_PROJECT_ID`、`config.SLACK_WEBHOOK_URL`、`pyproject.toml` 的 `google-cloud-firestore` 與 `opencc-python-reimplemented`。這些檔案只 import、不修改。
- **Task 1 需要業主在對話中明確同意後才能執行**（會在正式 BigSeller 帳號建測試草稿與測試商家 SKU）。Task 1 不依賴專案 1，可以先做。

## 重用既有程式（2026-10-22 James：專案 2 的 11 項周邊功能全部保留，由本專案挑用得到的）

| 既有程式 | 用在 | 怎麼用 |
|---|---|---|
| `bigseller/promotions.py` 店內折扣（`DISCOUNT_ADD`） | Task 10 第 15 天開折扣 | 直接呼叫；每規格折扣價格式以 Task 1 錄到的為準 |
| `sku_binding.scan_unbound_skus` / `zero_variations` / `offline_products`（`scripts/cleanup_unbound_skus.py` 的核心） | Task 11 補綁掃描、Task 12 健檢動作 | 包進 deps 正式實作；沿用「edit detail 回 0 筆 variations 要重試，避免誤判」 |
| `scripts/scan_unmapped_supplier_skus.py` 的 `skuSupplierRelation/pageList` 掃法 | Task 11 補綁 | 邏輯收進 deps，腳本保留給人工用 |
| `bigseller/product_optimizer.py` 的「只用來源證據、不捏造」規則與 80 字截斷 | Task 5 `generate_copy` | LLM 失敗時的規則式備援；prompt 沿用同一套禁止事項 |
| `scripts/scan_simplified_chinese_images.py`（OCR 簡繁判斷，零 token） | 第 3 期精修圖自動檢查 | 先用 OCR 擋簡體字，再交視覺模型比對外觀 |
| `image_optimizer`（`ratio.fix_safe_ratio`、`scoring.score_image`） | 第 3 期 | 生成後修蝦皮安全比例、挑分數高的圖 |
| `product_image.generate_with_codex` | 第 3 期 | 沿用 `codex exec` 呼叫方式（設計第 9.2 節） |
| `ecommerce/google_trends.py`、`community/monitor.py` + `llm_analyze.py` | 第 2 期候選商品 | 趨勢證據、AI 角色建議的輸入 |
| `scripts/price_audit.py` 的知蝦市價帶邏輯 | 第 2 期選品頁競品價 | 收進模組函式後共用 |

不用：`update-from-1688` / `update-from-codex`（命名規則與本流程衝突，設計第 11 節）、`zhixia login`（route token 走 `zhixia capture`）、評價、售後、財務、店鋪分類、廣告類促銷（營運用，非上架流程）。

## Global Constraints

- 不得修改：`modules/order_processing/*`、`modules/huohanhan/*`、`modules/fulfill/*`、`modules/bigseller/orders.py`、`purchase_draft.py`、`supplier_resolve.py`、`scripts/cron_*.py`、`main.py` 的 `orders` 區段、`config.py` 中訂單處理設定。需要時先停下來問業主。
- BigSeller I/O 一律走 `modules/bigseller/http_client.py` 的 `bs_get`/`bs_post_form`/`bs_post_json`；不跨模組 import 私有函式（`_xxx`）。
- 商家 SKU（= 蝦皮 `variationSku`）格式：`{offerId}-{台灣繁體規格名}`，例如 `958331892364-粉色-L`。不得使用 `MABA{pid}-…`。
- 規格名繁體轉換用 OpenCC `s2twp`。
- 目標毛利率 `TARGET_MARGIN_RATE = 0.30`，沒有硬門檻（低於只標示提醒）。
- 引流品：目標成交價 = 不虧錢的最低價（平日平台費情境 20% + 退貨率 5%），不設原價、不開折扣。
- 原價 = 目標成交價 ÷ `ORIGINAL_PRICE_FACTOR`（0.8），再取 9 結尾（`repricing.price_ending_9`）。
- 一般商品發佈後滿 `DISCOUNT_AFTER_DAYS`（14）天開店內折扣，回到目標成交價。
- 直購用 `estimate_profit(mode="dropshipping")`；同時算 `mode="bulk"` 的價格供專案 4。
- 重量拿不到時不得套預設值，必須由使用者用 `--weight-kg` 指定，否則中止。
- 1688 規格已售完（`canBookCount == 0`）不上架；起批量 > 1 拒絕直購；成本用買 1 件的價格。
- 貨源健檢：只有明確判定下架或規格不存在才動作；被擋、逾時、解析失敗一律是 `unknown`，不動作，連續 `HEALTH_UNKNOWN_ALERT_DAYS`（3）天才 Slack 提醒。
- 寫入指令預設 dry-run；`--commit` 才寫 BigSeller／Firestore；`--notify` 才發 Slack。dry-run 不寫 Firestore、不發 Slack。
- 發佈閘門：綁定驗證全部通過 **且** Firestore 紀錄 `images_approved == True`（第 3 期才會設為 True）。
- 測試不打真的 BigSeller、1688、LLM、Firebase、Slack。
- docstring 用中文；public 函式加 type hints；模組開頭 `sys.path.insert(0, …)`。

## Review Focus

1. 1688 頁面被反爬擋下或回傳空白頁 → 健檢必須判為 `unknown`，絕不下架（Task 6、Task 12 測試）。
2. 草稿規格名和 1688 規格名對不上（簡繁、順序、單位不同）→ 建草稿中止並列出對不上的規格，不得建出部分綁定的草稿就回報成功（Task 5 測試）。
3. `saveOrUpdateRelation` 假成功、或專案 1 的查法查到別的 platformSkuId → 綁定驗證判失敗、草稿狀態 `incomplete`、指令非零結束（Task 8 測試）。
4. 同一個 1688 商品重跑 `listing create` → 拒絕，不建第二個草稿（Task 9 測試）。
5. 一個蝦皮商品裡只有部分規格的貨源消失 → 只把那些規格庫存設 0，不下架整個商品；已經是 0 的不重複寫（Task 12 測試）。

---

### Task 1: 錄 BigSeller API 並做唯讀勘查（需業主同意）

**Files:**
- Modify: `CLAUDE.md`、`AGENTS.md`（BigSeller API Key Reference 加「上架 API」小節，兩檔同步）
- Create: `tests/fixtures/listing/`（下列 JSON／HTML 樣本，去除 cookie、token、個資）
- 探針腳本放 `/tmp`，用完即刪，不進版控

**Interfaces:**
- Produces: 文件化的端點與 body 格式，供 Task 7 實作；fixture 檔名如下，Task 5/6/7 的測試會讀：
  - `crawl_detail.json`（`GET crawl/edit.json` 回應）
  - `claim_request.json`、`claim_response.json`
  - `draft_after_claim.json`（認領後 `GET listing/shopee/edit/{id}.json` 回應）
  - `create_merchant_sku_request.json`、`create_merchant_sku_response.json`
  - `discount_add_request.json`、`discount_add_response.json`（每個規格不同折扣價）
  - `pool_bound_rows.json`（`get_pool_skus(mapping_status=1)` 的兩筆列）
  - `offer_active.html`、`offer_offline.html`、`offer_blocked.html`
- Produces（寫進 `config.py` 的實測值，Task 2 建立常數時填入）：`VARIATION_SKU_MAX_LEN`、`SHOPEE_MAX_TIERS`、`SHOPEE_MAX_OPTIONS_PER_TIER`、`SHOPEE_MAX_VARIATIONS`、`LISTING_DS_STOCK`、`DISCOUNT_MAX_DAYS`、crawl `weight` 的單位

- [ ] **Step 1: 在對話中向業主說明要建立的測試資料並取得明確同意**

說明：會在店鋪（設定 `SHOP_ID`）建 1 個測試草稿（不發佈）、為它建立商家 SKU、建 1 個測試折扣活動後立即結束；完成後刪除。沒有得到「同意」不得繼續。

- [ ] **Step 2: 錄「採集箱 → 認領成蝦皮草稿」**

用 Playwright 開 `https://www.bigseller.com/web/crawl/index.htm`（profile `/tmp/bigseller_chromium_profile`、`CHROME_DEBUG_PORT=9333`），對一個已 `linkCrawl` 的測試 offer 按認領到 shopee 店鋪（設定 `SHOP_ID`），記錄 XHR 的 method、path、body、回應（含新草稿 id）。同時確認 `linkCrawl` 後如何拿到 crawl 列 id（`list_crawl_products(search_content=…)` 用什麼搜尋值）。

- [ ] **Step 3: 錄「建立商家 SKU」**

對測試草稿的規格，在 BigSeller 介面建立商家 SKU（或找到「依草稿規格自動產生商家 SKU」的功能），記錄 XHR。確認建立後 `skuSupplierRelation/pageList.json` 查得到，並記下回應如何帶出新 skuId。

- [ ] **Step 4: 錄「每個規格不同折扣價的店內折扣活動」**

在介面建立折扣活動、對測試商品的兩個規格設不同折扣價，記錄 `add.json`（或 `edit/details.json`）的 body；記下活動最長天數。建立後立即結束活動（`deleteOrEnd.json`）。

- [ ] **Step 5: 唯讀勘查**

記錄：既有直購商品規格的 `stock` 慣例值（`LISTING_DS_STOCK`）；BigSeller 庫存推送設定是否開啟、新商家 SKU 倉庫庫存 0 是否會推到蝦皮；`variationSku` 長度上限；蝦皮規格層數、每層選項數、組合數上限；crawl detail `weight` 單位；pool 已綁定列的欄位名（商家 SKU、platformSkuId、offerId 各是哪個 key）；草稿缺必填屬性時 save 或 publish 回什麼錯誤；發佈後蝦皮商品在 BigSeller 的 id 是否仍等於草稿 id（不是的話發佈回應從哪裡帶出新 id）；蝦皮對預購（較長備貨）商品比例是否有上限。**若新商家 SKU 的倉庫庫存 0 會被推到蝦皮，或預購比例有上限會擋住直購商品，停下來回報業主，等決定後再繼續。**從 62 個上架商品挑一個 1688 已下架的 offer（或 `reports/` 裡記錄過下架的 offer）存 `offer_offline.html`，一個正常的存 `offer_active.html`，一個反爬頁存 `offer_blocked.html`。

- [ ] **Step 6: 清理測試資料**

刪除測試草稿（`/api/v1/product/listing/shopee/...` 刪除端點，Step 2 一併錄）、測試商家 SKU、測試 crawl 列。用 API 回查確認已不存在。

- [ ] **Step 7: 寫文件與 fixture，commit**

```bash
git add CLAUDE.md AGENTS.md tests/fixtures/listing/
git commit -m "docs: record BigSeller listing APIs (claim, merchant SKU, per-variation discount)"
```

---

### Task 2: 設定常數與定價策略

**Files:**
- Modify: `config.py`（只改定價段與新增上架段，不碰訂單處理設定）
- Create: `modules/listing/__init__.py`、`modules/listing/pricing.py`
- Test: `tests/listing/__init__.py`、`tests/listing/test_pricing.py`

**Interfaces:**
- Consumes: `modules.profit.estimate_profit`、`modules.bigseller.repricing.price_ending_9`
- Produces:
  - `config`：`TARGET_MARGIN_RATE = 0.30`（註解改為「目標毛利率，無硬門檻」）、`ORIGINAL_PRICE_FACTOR = 0.8`、`DISCOUNT_AFTER_DAYS = 14`、`LISTING_DS_DAYS_TO_SHIP = 10`、`HEALTH_UNKNOWN_ALERT_DAYS = 3`、`WEIGHT_DEVIATION_ALERT_RATE = 0.20`，以及 Task 1 的實測常數
  - `Role = Literal["lead", "normal"]`
  - `class WeightUnknown(ValueError)`
  - `@dataclass(frozen=True) class SpecPrice: target_price: int; original_price: int | None; margin_at_target: float; below_target_margin: bool; bulk_target_price: int`
  - `def price_spec(cost_cny: float, weight_kg: float | None, role: Role) -> SpecPrice`

- [ ] **Step 1: Write the failing tests**

```python
def test_normal_role_hits_30_percent_and_original_is_target_over_08():
    p = price_spec(cost_cny=10.0, weight_kg=0.2, role="normal")
    base = estimate_profit(10.0, 0, weight_kg=0.2, mode="dropshipping", target_margin=0.30)
    assert p.target_price == price_ending_9(base["suggested_price_normal"])
    assert p.original_price == price_ending_9(p.target_price / 0.8)
    assert p.margin_at_target >= 0.30
    assert p.below_target_margin is False

def test_lead_role_is_break_even_without_original_price():
    p = price_spec(cost_cny=10.0, weight_kg=0.2, role="lead")
    base = estimate_profit(10.0, 0, weight_kg=0.2, mode="dropshipping", target_margin=0.0)
    assert p.target_price == price_ending_9(base["suggested_price_normal"])
    assert p.original_price is None
    assert estimate_profit(10.0, p.target_price, weight_kg=0.2, mode="dropshipping")["profit_ntd_normal"] >= 0

def test_bulk_price_is_lower_than_dropshipping():
    p = price_spec(cost_cny=10.0, weight_kg=0.5, role="normal")
    assert p.bulk_target_price < p.target_price

def test_missing_weight_raises():
    with pytest.raises(WeightUnknown):
        price_spec(cost_cny=10.0, weight_kg=None, role="normal")

def test_target_margin_config_is_30_percent():
    assert config.TARGET_MARGIN_RATE == 0.30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/listing/test_pricing.py -q`
Expected: FAIL（`ModuleNotFoundError: modules.listing`）

- [ ] **Step 3: 改 `config.py` 並實作 `price_spec`**

`margin_at_target` 用 `estimate_profit(cost, target_price, …)["margin_normal"]`；`below_target_margin = margin_at_target < TARGET_MARGIN_RATE`（lead 一律 False）。

- [ ] **Step 4: Run tests — 新測試與既有 `tests/test_profit.py` 都要 PASS**

Run: `uv run python -m pytest tests/listing/test_pricing.py tests/test_profit.py tests/test_pricing_batch_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py modules/listing/ tests/listing/
git commit -m "feat(listing): add pricing strategy with 30% target and lead break-even"
```

---

### Task 3: 商家 SKU 命名

**Files:**
- Create: `modules/listing/naming.py`
- Test: `tests/listing/test_naming.py`

**Interfaces:**
- Produces:
  - `def to_tw(text: str) -> str`（OpenCC `s2twp`，模組層級建一次 converter）
  - `class SkuTooLong(ValueError)`、`class SkuCollision(ValueError)`
  - `def merchant_sku(offer_id: str, spec_sku: str) -> str`
  - `def merchant_skus(offer_id: str, spec_skus: list[str]) -> dict[str, str]`（spec_sku → 商家 SKU；截斷後撞名 raise `SkuCollision`）
  - `def offer_id_of(sku: str) -> str | None`（前綴是 6 位以上數字才回傳）

- [ ] **Step 1: Write the failing tests**

```python
def test_simplified_spec_becomes_taiwan_traditional():
    assert merchant_sku("958331892364", "粉色-L") == "958331892364-粉色-L"
    assert merchant_sku("958331892364", "黑色-均码") == "958331892364-黑色-均碼"
    assert merchant_sku("1045723696589", "库洛米-大号") == "1045723696589-庫洛米-大號"

def test_long_spec_is_truncated_keeping_offer_prefix():
    sku = merchant_sku("958331892364", "超" * 300)
    assert len(sku) == config.VARIATION_SKU_MAX_LEN
    assert sku.startswith("958331892364-")

def test_truncation_collision_raises():
    a, b = "超" * 300 + "A", "超" * 300 + "B"
    with pytest.raises(SkuCollision):
        merchant_skus("958331892364", [a, b])

def test_offer_id_of():
    assert offer_id_of("958331892364-粉色-L") == "958331892364"
    assert offer_id_of("MABA123-粉色") is None
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_naming.py -q` → FAIL
- [ ] **Step 3: Implement**（截斷只截規格段，保留 `{offerId}-`）
- [ ] **Step 4: Run to verify pass** — 同上指令 → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): merchant SKU naming {offerId}-{traditional spec}"`

---

### Task 4: 1688 商品資料型別與規格挑選

**Files:**
- Create: `modules/listing/types.py`、`modules/listing/spec_select.py`
- Test: `tests/listing/test_spec_select.py`

**Interfaces:**
- Produces（`types.py`）：
  - `@dataclass(frozen=True) class OfferSpec: platform_sku_id: str; spec_id: str; spec_sku: str; price_cny: float | None; price_tiers: tuple[tuple[int, float], ...]; can_book_count: int | None`（`spec_sku` 是 1688 規格名以 `-` 串接，如 `黑色-M`；`price_tiers` 是 `(beginAmount, price)`）
  - `@dataclass(frozen=True) class OfferDetail: offer_id: str; title: str; begin_amount: int; weight_kg: float | None; main_images: tuple[str, ...]; attributes: tuple[dict, ...]; specs: tuple[OfferSpec, ...]; tier_count: int`
  - `@dataclass(frozen=True) class SelectedSpec: spec: OfferSpec; cost_cny: float`
  - `@dataclass(frozen=True) class SpecSelection: included: tuple[SelectedSpec, ...]; dropped: tuple[tuple[OfferSpec, str], ...]`
- Produces（`spec_select.py`）：
  - `class OfferRejected(ValueError)`（訊息要能直接印給業主看）
  - `def unit_cost(spec: OfferSpec, begin_amount: int) -> float`（`price_cny` 有值就用；否則取 `beginAmount <= 1` 的階梯價；起批量 > 1 raise `OfferRejected`）
  - `def select_specs(offer: OfferDetail, keep: set[str] | None = None) -> SpecSelection`

規則：`can_book_count == 0` → dropped（原因「1688 已售完」）；`keep` 有給時只留 `spec_sku` 或 `to_tw(spec_sku)` 在 keep 裡的；`offer.begin_amount > 1` → `OfferRejected("起批量 N > 1，不能直購，建議改走備貨")`；全部被 drop → `OfferRejected`；沒給 keep 且 `tier_count > SHOPEE_MAX_TIERS`、任一層選項數 > `SHOPEE_MAX_OPTIONS_PER_TIER` 或 included 數 > `SHOPEE_MAX_VARIATIONS` → `OfferRejected`，訊息列出全部 `spec_sku` 並提示用 `--specs` 指定。

- [ ] **Step 1: Write the failing tests**

```python
def test_sold_out_specs_are_dropped(): ...      # can_book_count=0 的在 dropped，原因 "1688 已售完"
def test_moq_above_one_is_rejected(): ...       # begin_amount=2 → OfferRejected，訊息含 "不能直購"
def test_tier_price_for_single_unit(): ...      # price_cny=None, tiers ((1, 9.5), (10, 8.0)) → cost 9.5
def test_tier_starting_above_one_rejected(): ...# tiers ((3, 9.0),) → OfferRejected
def test_over_shopee_limit_without_keep_lists_specs(): ...  # 規格數 > SHOPEE_MAX_VARIATIONS → OfferRejected，訊息含每個 spec_sku 與 "--specs"
def test_keep_accepts_traditional_names(): ...  # keep={"黑色-均碼"} 留下 spec_sku "黑色-均码"
def test_all_dropped_rejected(): ...
```

每個測試用 `OfferSpec`／`OfferDetail` 直接建構，斷言如註解所述。

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_spec_select.py -q` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): select listable 1688 specs (sold-out, MOQ, Shopee limits)"`

---

### Task 5: 文案與草稿改寫（純函式）

**Files:**
- Create: `modules/listing/copywriting.py`、`modules/listing/draft_rewrite.py`
- Test: `tests/listing/test_copywriting.py`、`tests/listing/test_draft_rewrite.py`

**Interfaces:**
- Consumes: Task 2 `SpecPrice`、Task 3 `to_tw`/`merchant_skus`、Task 4 型別、`modules.bigseller.sku_binding.norm_spec`
- Produces:
  - `@dataclass(frozen=True) class ListingCopy: name: str; description: str`
  - `def generate_copy(offer: OfferDetail, llm: Callable[[str, str], str]) -> ListingCopy`（`llm(prompt, system_msg)`；正式呼叫端傳 `modules.community.llm_analyze.call_llm`）
  - `@dataclass(frozen=True) class PlannedVariation: spec: SelectedSpec; merchant_sku: str; price: SpecPrice | None`（補綁既有商品時為 None；`rewrite_draft` 遇到 None raise `ValueError`）
  - `@dataclass(frozen=True) class DraftPlan: offer_id: str; role: Role; weight_kg: float; variations: tuple[PlannedVariation, ...]`
  - `class DraftMismatch(ValueError)`（帶 `unmatched_draft: list[str]`、`unmatched_specs: list[str]`）
  - `def rewrite_draft(product: dict, plan: DraftPlan, copy: ListingCopy) -> dict`（回傳新 dict，不改輸入）

`generate_copy`：prompt 要求只依 1688 標題與屬性改寫，台灣用語、繁體、不捏造特性，輸出 JSON `{"name","description"}`；回應不是 JSON 時 raise `ValueError`；結果再過一次 `to_tw`；`name` 超過蝦皮標題上限（Task 1 未查到時用 120 字）時截斷。

`rewrite_draft`：草稿每個 variation 用 `norm_spec` 比對（option 值以 `-` 串接，或 `variationName`）到 plan 的 `spec.spec_sku`；在 plan 裡的規格寫入 `variationSku = merchant_sku`、option 值與 `variationName` 轉 `to_tw`、`originalPrice`（normal 用 `original_price`，lead 用 `target_price`）、`price = None`、`stock = LISTING_DS_STOCK`；不在 plan 的（已售完被 drop 的）從 `variations` 移除，並同步移除 `option1`/`option2` 中不再使用的選項；有 plan 規格對不到草稿、或草稿規格對不到任何 1688 規格 → raise `DraftMismatch`。商品層級寫入 `name`、`productText.description`（欄位位置照 `fixtures/listing/draft_after_claim.json`）、`daysToShip = LISTING_DS_DAYS_TO_SHIP`、`weight`（依 Task 1 單位）。

- [ ] **Step 1: Write the failing tests**

```python
def test_rewrite_sets_sku_prices_and_traditional_names():
    product = load_fixture("draft_after_claim.json")["data"]["product"]
    out = rewrite_draft(product, plan_from(product), ListingCopy("標題", "描述"))
    skus = {v["variationSku"] for v in out["variations"]}
    assert skus == {pv.merchant_sku for pv in plan.variations}
    assert all(v["price"] is None for v in out["variations"])
    assert out["daysToShip"] == config.LISTING_DS_DAYS_TO_SHIP
    assert product["variations"][0].get("variationSku") != out["variations"][0]["variationSku"]  # 輸入未被改動

def test_lead_role_uses_target_price_as_list_price(): ...
def test_dropped_spec_is_removed_from_variations_and_options(): ...
def test_unmatched_variation_raises_draft_mismatch():
    # 草稿多一個 1688 沒有的規格 → DraftMismatch.unmatched_draft == ["紫色-XL"]
    ...
def test_generate_copy_parses_json_and_converts_to_traditional():
    copy = generate_copy(offer, llm=lambda p, s: '{"name": "宝宝湿巾", "description": "柔软"}')
    assert copy == ListingCopy("寶寶溼巾", "柔軟")
def test_generate_copy_rejects_non_json(): ...
```

（`plan_from` 是測試內 helper：依 fixture 規格建 `DraftPlan`。`to_tw("宝宝湿巾")` 的實際輸出以 OpenCC 結果為準，寫測試時先跑一次確認字面值。）

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_copywriting.py tests/listing/test_draft_rewrite.py -q` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): rewrite claimed draft with traditional copy, SKUs and prices"`

---

### Task 6: 1688 商品頁讀取與健檢分類

> **2026-10-23 已改道**：試跑時本機直連 1688 被反爬擋，業主同意改由 BigSeller 代抓（`listing_api.fetch_offer_via_crawl` + `modules/listing/crawl_source.py`）。下面直連頁面的 `classify_offer_page` 等函式已移除，`offer_source.py` 只留 `OfferSnapshot` 型別。

**Files:**
- Modify: `modules/bigseller/sku_binding.py`（新增 public `download_1688_offer_page`、`fetch_offer_page_data`；`_fetch_1688_html` 改成呼叫前者再檢查，行為不變）
- Create: `modules/listing/offer_source.py`
- Test: `tests/listing/test_offer_source.py`

**Interfaces:**
- Produces（`sku_binding.py`）：
  - `def download_1688_offer_page(offer_id: str) -> str`（curl 下載，不檢查內容；curl 失敗 raise `RuntimeError`）
  - `def fetch_offer_page_data(offer_id: str) -> dict`（= `parse_1688_page_data(_fetch_1688_html(offer_id))`）
- Produces（`offer_source.py`）：
  - `OfferStatus = Literal["active", "offline", "unknown"]`
  - `@dataclass(frozen=True) class OfferSnapshot: offer_id: str; status: OfferStatus; can_book: dict[str, int | None]; prices_cny: dict[str, float | None]; reason: str`（key 是 platformSkuId）
  - `OFFLINE_MARKERS: tuple[str, ...]`（沿用 `product.check_1688_product_status` 的下架字樣）
  - `def classify_offer_page(offer_id: str, html: str) -> OfferSnapshot`
  - `def fetch_offer_snapshot(offer_id: str, download: Callable[[str], str] = download_1688_offer_page) -> OfferSnapshot`（下載例外 → `unknown`，reason 帶錯誤訊息）
  - `def build_offer_detail(offer_id: str, page_data: dict, pool_skus: list[dict], weight_kg: float | None) -> OfferDetail`（把 `fetch_offer_page_data` 結果與 `sku_binding.get_offer_skus` 的 `platformSkuId` 對起來；`tier_count = len(page_data["offer"]["skuProps"])`）

`download_1688_offer_page` 改為回傳 `tuple[str, str]`（最終 URL、HTML），`classify_offer_page(offer_id, html, final_url="")` 同步加參數。`classify_offer_page`：最終 URL 含 `wrongpage`（Task 1 實測：不存在的 offer 會被導到 `page.1688.com/shtml/static/wrongpage.html`）或含任一 `OFFLINE_MARKERS` → `offline`；`parse_1688_page_data` 成功且 `offer.status` 不是下架值（Task 1 確認值）→ `active`；其餘（反爬頁、解析失敗）→ `unknown`。

- [ ] **Step 1: Write the failing tests**

```python
def test_active_page_has_per_sku_stock():
    snap = classify_offer_page("x", read_fixture("offer_active.html"))
    assert snap.status == "active" and snap.can_book
def test_offline_page_is_offline():
    assert classify_offer_page("x", read_fixture("offer_offline.html")).status == "offline"
def test_blocked_page_is_unknown_not_offline():
    assert classify_offer_page("x", read_fixture("offer_blocked.html")).status == "unknown"
def test_download_error_is_unknown():
    def boom(_): raise RuntimeError("timeout")
    snap = fetch_offer_snapshot("x", download=boom)
    assert snap.status == "unknown" and "timeout" in snap.reason
def test_existing_fetch_behaviour_unchanged(): ...  # 以 patch 驗證 _fetch_1688_html 對反爬頁仍 raise RuntimeError
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_offer_source.py tests/bigseller/test_sku_binding.py -q` → 新測試 FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → 全部 PASS（含既有 sku_binding 測試）
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): classify 1688 offer pages as active/offline/unknown"`

---

### Task 7: deps Protocol 與 BigSeller 正式實作

**Files:**
- Create: `modules/listing/deps.py`（Protocol）、`modules/listing/bigseller_deps.py`（正式實作）
- Test: `tests/listing/test_bigseller_deps.py`、`tests/listing/fakes.py`（測試共用假 deps）

**Interfaces:**
- Consumes: Task 1 錄到的端點；`crawl_prices.link_crawl`、`crawl_prices.list_crawl_products`、`crawl_prices.get_crawl_product`、`crawl_prices.extract_listing_offer_id`；`sku_binding.add_offer_to_pool`、`get_offer_skus`、`get_merchant_sku_map`、`bind_sku`、`get_pool_skus`、`get_active_listings`、`zero_variations`、`offline_products`、`DEFAULT_SHOP_ID`；`supplier_resolve.resolve_supplier_by_var_sku`；`sync.link_supplier`；Task 6 `fetch_offer_snapshot`、`build_offer_detail`
- Produces（`deps.py`，`class ListingDeps(Protocol)`）：
  - `offer_detail(self, offer_id: str) -> OfferDetail`
  - `claim_draft(self, offer_id: str) -> int`（linkCrawl → 找 crawl 列 → 認領；回傳草稿 id）
  - `get_draft(self, draft_id: int) -> dict` / `save_draft(self, product: dict) -> None`
  - `publish_draft(self, product: dict) -> int`（回傳發佈後的 BigSeller 蝦皮商品 id，依 Task 1 結果）
  - `add_offer_to_pool(self, offer_id: str) -> None`
  - `create_merchant_skus(self, draft_id: int, skus: list[str]) -> dict[str, int]`
  - `merchant_sku_ids(self) -> dict[str, int]`
  - `bind(self, merchant_sku_id: int, platform_sku_id: str, offer_id: str, sku: str) -> tuple[bool, str | None]`
  - `purchase_mapping(self, sku: str) -> dict | None`（= `resolve_supplier_by_var_sku(sku)`）
  - `link_supplier(self, merchant_sku_id: int, supplier_id: int, price_cny: float, offer_id: str) -> None`
  - `create_variation_discount(self, listing_id: int, prices: dict[str, int], start: datetime, end: datetime) -> int`（回傳活動 id）
  - `active_listings(self) -> list[dict]`（每列含 `id`、`name`、`weight`、完整 `variations`）
  - `bound_relations(self) -> dict[str, tuple[str, str]]`（商家 SKU → (offerId, platformSkuId)，來自 pool 已綁定列）
  - `offer_snapshot(self, offer_id: str) -> OfferSnapshot`
  - `zero_variations(self, listing_id: int, skus: set[str]) -> None` / `offline_listings(self, listing_ids: list[int]) -> None`
  - `set_live_variation_skus(self, listing_id: int, sku_by_variation_id: dict[int, str]) -> None`（補綁缺 SKU 用，`listing/shopee/edit.json`）
  - `listing_offer_id(self, listing: dict) -> str | None`
- 所有寫入方法遇到 API `code != 0` raise `RuntimeError`（含 API msg），不回 False。
- Task 1 實測修正（見 CLAUDE.md「上架 API」）：`claim_draft` 用 `offer/{id}.html` 網址 linkCrawl、`multiPlatformCollect.json` 的欄位是 `ids`、草稿 id 以 `sourceUrl` 從草稿列表找回；`create_merchant_skus` 用 `inventory/merchant/add/v1.json`（重量放最上層 `commodityWeight` 公克）；`stock` 沿用 1688 `canBookCount`（既有上架慣例），`LISTING_DS_STOCK` 不使用；商家 SKU 倉庫關聯與折扣 API 實送驗證是待業主決定的未決事項（見 PR #11）。
- `tests/listing/fakes.py`：`FakeListingDeps`，每個方法記錄呼叫到 `self.calls: list[tuple[str, tuple]]`，回傳值由建構參數決定。

- [ ] **Step 1: Write the failing tests**（patch `modules.listing.bigseller_deps.bs_post_json` 等，用 Task 1 fixture）

```python
def test_claim_draft_posts_recorded_body_and_returns_draft_id(): ...   # body == fixture claim_request；回傳 fixture 中的草稿 id
def test_create_merchant_skus_returns_ids_from_relation_table(): ...
def test_create_variation_discount_sends_per_variation_prices(): ...  # body 與 fixture discount_add_request 同形狀，兩個規格價格不同
def test_write_failure_raises_with_api_message(): ...                # code=-1, msg="操作失败" → RuntimeError 含 "操作失败"
def test_bound_relations_maps_sku_to_offer_and_platform_sku(): ...    # 讀 pool_bound_rows.json
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_bigseller_deps.py -q` → FAIL
- [ ] **Step 3: Implement Protocol、正式實作與 `FakeListingDeps`**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): ListingDeps protocol and BigSeller implementation"`

---

### Task 8: 綁定與驗證（發佈閘門的核心）

**Files:**
- Create: `modules/listing/binding.py`
- Test: `tests/listing/test_binding.py`

**Interfaces:**
- Consumes: Task 5 `PlannedVariation`、Task 7 `ListingDeps`
- Produces:
  - `@dataclass(frozen=True) class BindingCheck: sku: str; ok: bool; reason: str | None`
  - `def bind_variations(draft_id: int, offer_id: str, variations: Sequence[PlannedVariation], deps: ListingDeps) -> list[BindingCheck]`（入池 → 建缺少的商家 SKU → 逐筆 bind → verify → link_supplier）
  - `def verify_bindings(variations: Sequence[PlannedVariation], deps: ListingDeps) -> list[BindingCheck]`（唯讀）

驗證規則（每個規格）：`deps.purchase_mapping(sku)` 回 None → `"專案 1 查不到 1688 對應"`；`merchant_sku_id` 是 None → `"查得到但缺商家 skuId，下單會被拒"`；`platform_sku_id != pv.spec.platform_sku_id` → `"綁到別的 1688 規格 {x}"`；`purchase_mapping` raise（含 `AmbiguousPlatformSku`）→ `ok=False`，reason 為例外訊息。驗證通過才 `link_supplier(merchant_sku_id, supplier_id, cost_cny, offer_id)`。

- [ ] **Step 1: Write the failing tests**

```python
def test_all_bound_and_verified(): ...                 # 每個 check.ok；calls 順序 add_offer_to_pool → create_merchant_skus → bind… → purchase_mapping… → link_supplier…
def test_only_missing_merchant_skus_are_created(): ...  # merchant_sku_ids 已有 A，create_merchant_skus 只收到 [B]
def test_bind_reports_false_success(): ...             # bind 回 (True, None) 但 purchase_mapping 回別的 platform_sku_id → ok False，reason 含 "綁到別的 1688 規格"
def test_mapping_without_merchant_sku_id_fails(): ...
def test_ambiguous_mapping_fails_without_crashing(): ...
def test_supplier_not_linked_when_verification_fails(): ...
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_binding.py -q` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): bind variations and verify with order-processing lookup"`

---

### Task 9: Firestore 紀錄與 `listing create` / `listing bind-check`

**Files:**
- Create: `modules/listing/store.py`、`modules/listing/create.py`
- Modify: `main.py`（新增 `_build_listing_parser` 與 `cmd_listing_*`，在 `main()` 註冊；不動 `orders` 區段）、`tests/run_all.py`（CLI help 清單加 `listing --help`、`listing create --help`、`listing bind-check --help`）
- Test: `tests/listing/test_store.py`、`tests/listing/test_create.py`

**Interfaces:**
- Consumes: `tests.order_processing.fake_firestore.FakeFirestore`（測試）、`modules.order_processing.firestore_client.get_client`（正式）；Task 2–8
- Produces（`store.py`）：
  - 集合常數：`LISTING_PRODUCTS = "listing_products"`（doc id = 草稿 id）、`LISTING_HEALTH = "listing_health"`（doc id = 商家 SKU）、`SKU_MEASURED_WEIGHTS = "sku_measured_weights"`（doc id = 商家 SKU，欄位 `samples_g: list[int]`，由專案 1 寫入）
  - `class ListingStore`：`get(draft_id: int) -> dict | None`、`find_by_offer(offer_id: str) -> dict | None`、`upsert(draft_id: int, data: dict) -> None`（merge）、`all() -> list[dict]`
  - `class HealthStore`：`get(sku: str) -> dict | None`、`upsert(sku: str, data: dict) -> None`
  - `class MeasuredWeights`：`average_g(sku: str) -> float | None`
  - `listing_products` 文件欄位：`offer_id, listing_id: int|None, role, mode("dropshipping"), weight_kg, status("bound"|"incomplete"|"published"), issues: list[str], images_approved: bool(預設 False), variations: [{merchant_sku, platform_sku_id, cost_cny, target_price, original_price, bulk_target_price}], published_at: str|None, discount: {activity_id, start, end}|None, created_at`
- Produces（`create.py`）：
  - `@dataclass class CreateResult: draft_id: int | None; status: str; checks: list[BindingCheck]; selection: SpecSelection; warnings: list[str]`
  - `def create_listing(offer_id: str, role: Role, deps: ListingDeps, store: ListingStore, *, keep: set[str] | None, weight_kg: float | None, commit: bool, llm: Callable[[str, str], str]) -> CreateResult`
  - `def recheck_listing(draft_id: int, deps: ListingDeps, store: ListingStore, *, commit: bool) -> CreateResult`
- CLI：
  - `listing create <offer_id> [--role lead|normal] [--specs "黑色-M,白色-L"] [--weight-kg 0.3] [--commit]`
  - `listing bind-check <draft_id> [--commit]`（重跑入池／建 SKU／綁定／驗證並更新 status）
  - 任何規格驗證失敗或 `OfferRejected`／`DraftMismatch`／`WeightUnknown` → 印原因、`sys.exit(2)`

`create_listing` 流程：`store.find_by_offer` 有紀錄 → raise `ValueError("已建立過草稿 {id}，請用 listing bind-check")`；`deps.offer_detail` → `select_specs` → 重量（`weight_kg` 參數優先，否則 `offer.weight_kg`，都沒有 → `WeightUnknown`）→ `price_spec` 每個規格 → `merchant_skus`；`commit=False` 到此為止，回傳計畫（status `"planned"`），不呼叫任何寫入 deps、不寫 store；`commit=True` 才 `claim_draft` → `get_draft` → `generate_copy` → `rewrite_draft` → `save_draft` → `bind_variations` → `store.upsert`（全部 ok → `"bound"`，否則 `"incomplete"` 並寫 `issues`）。

類目必填屬性：第 1 期不自動填（設計文件 6.1 的這一項延到第 2 期與審核頁一起做）。認領後草稿缺必填屬性時，`save_draft`／`publish_draft` 的 API 錯誤訊息原樣印出並寫進 `issues`；業主在 BigSeller 介面補屬性。

- [ ] **Step 1: Write the failing tests**

```python
def test_dry_run_makes_no_writes(): ...           # FakeListingDeps.calls 只含 offer_detail；FakeFirestore 無文件；status "planned"
def test_commit_happy_path_records_bound(): ...   # store 文件 status "bound"、images_approved False、variations 價格與 price_spec 相同
def test_failed_binding_records_incomplete(): ... # 一個規格驗證失敗 → status "incomplete"、issues 含該 SKU
def test_duplicate_offer_refused(): ...           # find_by_offer 有紀錄 → ValueError，claim_draft 未被呼叫
def test_missing_weight_requires_flag(): ...      # offer.weight_kg None 且未給 weight_kg → WeightUnknown
def test_cli_exit_code_2_on_incomplete(): ...     # 透過 main 的 cmd 函式 + patch deps 工廠
def test_measured_weights_average(): ...          # samples_g [300, 320] → 310.0；沒文件 → None
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_store.py tests/listing/test_create.py -q` → FAIL
- [ ] **Step 3: Implement store、create、CLI**
- [ ] **Step 4: Run to verify pass**，並跑 `uv run python main.py listing create --help` → 印出說明
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): listing create/bind-check CLI with Firestore record"`

---

### Task 10: 發佈閘門與第 15 天開折扣

**Files:**
- Create: `modules/listing/publish.py`
- Modify: `main.py`（`listing publish`、`listing discount-due`）、`tests/run_all.py`（help 清單）
- Test: `tests/listing/test_publish.py`

**Interfaces:**
- Consumes: Task 8 `verify_bindings`、Task 9 `ListingStore`、`modules.notify.slack.Notifier`
- Produces:
  - `class PublishBlocked(RuntimeError)`
  - `def publish_listing(draft_id: int, deps: ListingDeps, store: ListingStore, *, commit: bool, now: datetime) -> None`
  - `@dataclass class DiscountRun: created: list[int]; renewed: list[int]; skipped: list[tuple[int, str]]`
  - `def run_discount_due(deps: ListingDeps, store: ListingStore, *, commit: bool, now: datetime) -> DiscountRun`
- CLI：`listing publish <draft_id> [--commit]`；`listing discount-due [--commit] [--notify]`

閘門順序：store 沒紀錄 → `PublishBlocked("不是本流程建立的草稿")`；`images_approved` 不是 True → `PublishBlocked("圖片尚未審核")`；`verify_bindings` 任一失敗 → `PublishBlocked` 並列出 SKU 與原因；通過且 `commit` → `publish_draft` → `store.upsert(status="published", listing_id=<回傳值>, published_at=now.isoformat())`。

折扣：`role == "normal"`、`status == "published"`、`published_at <= now - DISCOUNT_AFTER_DAYS`、`discount is None` → 建活動，`prices = {merchant_sku: target_price}`，`start = now`，`end = now + DISCOUNT_MAX_DAYS`；`discount.end - now <= 2 天` → 從舊活動 end 起建新活動（renewed）；`role == "lead"` 一律 skipped。`--notify` 時把 created/renewed 發 Slack（`Notifier` key `listing:discount:{date}`）。

- [ ] **Step 1: Write the failing tests**

```python
def test_publish_blocked_until_images_approved(): ...   # images_approved False → PublishBlocked，publish_draft 未呼叫
def test_publish_blocked_on_binding_failure(): ...
def test_publish_records_published_at(): ...
def test_dry_run_publish_does_not_call_publish(): ...
def test_discount_not_before_day_14(): ...              # published_at = now - 13d → skipped
def test_discount_created_on_day_14_with_target_prices(): ...
def test_lead_never_discounted(): ...
def test_discount_renewed_two_days_before_end(): ...
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_publish.py -q` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): publish gate and day-14 discount job"`

---

### Task 11: 既有商品補綁 `listing backfill`

**Files:**
- Create: `modules/listing/backfill.py`
- Modify: `main.py`（`listing backfill`）、`tests/run_all.py`
- Test: `tests/listing/test_backfill.py`

**Interfaces:**
- Consumes: Task 3 `merchant_sku`/`offer_id_of`/`to_tw`、Task 7 deps（`active_listings`、`bound_relations`、`listing_offer_id`、`set_live_variation_skus`、`offer_detail`）、Task 8 `bind_variations`
- Produces:
  - `@dataclass class BackfillReport: bound: list[str]; renamed: dict[str, str]; needs_owner: list[tuple[str, str]]; pool_unused: int`
  - `def backfill_bindings(deps: ListingDeps, *, commit: bool) -> BackfillReport`
- CLI：`listing backfill [--commit] [--notify]`

流程：未綁定（不在 `bound_relations`）的規格依 `offer_id_of(variationSku)` 分組；缺 `variationSku` 的規格用 `deps.listing_offer_id(listing)` 推 offerId，推得到就以 option 值組 `merchant_sku`、`commit` 時 `set_live_variation_skus` 寫回（記到 `renamed`），推不到 → `needs_owner`（原因「無法判斷 1688 商品」）；每組用 `offer_detail` 找對應規格（`norm_spec` 比對，比不到 → `needs_owner`「1688 找不到對應規格」），組成 `PlannedVariation`（`price=None`）後呼叫 `bind_variations`，失敗的 → `needs_owner`。`pool_unused` 只計數（`get_pool_skus(mapping_status=0)` 筆數）。`commit=False` 不呼叫任何寫入 deps。

- [ ] **Step 1: Write the failing tests**

```python
def test_dry_run_reports_plan_without_writes(): ...
def test_unbound_skus_grouped_by_offer_and_bound(): ...
def test_missing_variation_sku_renamed_then_bound(): ...   # renamed == {"<variationId>": "958331892364-粉色-L"}
def test_unknown_offer_goes_to_owner(): ...
def test_spec_not_on_1688_goes_to_owner(): ...
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_backfill.py -q` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): backfill bindings for existing listings"`

---

### Task 12: 每日貨源健檢 `listing health-check`

**Files:**
- Create: `modules/listing/health.py`
- Modify: `main.py`（`listing health-check`）、`tests/run_all.py`
- Test: `tests/listing/test_health.py`

**Interfaces:**
- Consumes: Task 6 `OfferSnapshot`、Task 7 deps、Task 9 `HealthStore`/`ListingStore`/`MeasuredWeights`、Task 2 `price_spec`/`estimate_profit`、`Notifier`
- Produces:
  - `@dataclass(frozen=True) class HealthAction: kind: Literal["zero", "offline", "unknown_alert", "price_alert", "weight_alert", "unbound"]; listing_id: int; skus: tuple[str, ...]; reason: str`
  - `def plan_health_actions(listings: list[dict], relations: dict[str, tuple[str, str]], snapshots: dict[str, OfferSnapshot], unknown_days: dict[str, int], roles: dict[str, Role], measured_g: dict[str, float]) -> list[HealthAction]`（純函式）
  - `def run_health_check(deps: ListingDeps, health: HealthStore, listings_store: ListingStore, weights: MeasuredWeights, *, commit: bool, notify: Notifier | None, now: datetime) -> list[HealthAction]`
- CLI：`listing health-check [--commit] [--notify]`。試跑週排程用 `--notify`（Slack 標題前綴「【試跑，未執行】」）；正式用 `--commit --notify`。

規則（每個 listing、每個規格）：
- 規格沒有綁定 → `unbound`（只報告）。
- 該 offer snapshot `unknown` → 不動作；`unknown_days[sku] + 1 >= HEALTH_UNKNOWN_ALERT_DAYS` → `unknown_alert`。
- snapshot `offline`，或 platformSkuId 不在 `can_book`，或 `can_book == 0` → 規格「貨源消失」。目前 `stock == 0` 的規格略過。
- 一個 listing 所有規格都「貨源消失」或已是 0 → 一個 `offline`；否則消失的規格合成一個 `zero`。
- 1688 價格（`prices_cny`）在目前售價下的毛利率低於目標（role 為 lead 時改看利潤 < 0；沒有 role 的既有商品視為 normal）→ `price_alert`，reason 含新的建議目標成交價。
- `measured_g` 有值且與 listing 重量差 > `WEIGHT_DEVIATION_ALERT_RATE` → `weight_alert`，reason 含重算後的建議價。

`run_health_check`：每個 offer 只抓一次 snapshot；`commit` 時執行 `zero`/`offline` 並在 `HealthStore` 記 `{action, prev_stock, reason, acted_at}`；`commit` 或 `notify` 時更新 `unknown_since`／清除已恢復的 unknown 紀錄；`notify` 時組一則摘要用 `Notifier.notify("listing:health:{date}", text)` 發送，沒有任何 action 不發。`commit=False` 不呼叫 `zero_variations`／`offline_listings`。

- [ ] **Step 1: Write the failing tests**

```python
def test_unknown_snapshot_never_acts(): ...
def test_unknown_three_days_alerts(): ...                 # unknown_days 2 → 本次第 3 天 → unknown_alert
def test_partial_loss_zeroes_only_lost_skus(): ...        # 3 規格中 1 個 can_book 0 → zero(skus=(那1個,))，無 offline
def test_offer_offline_delists_whole_listing(): ...
def test_already_zero_not_written_again(): ...
def test_price_rise_alerts_with_new_target(): ...
def test_weight_deviation_alerts(): ...                   # 宣稱 0.25kg、實測平均 320g → weight_alert
def test_dry_run_and_notify_modes(): ...                  # notify-only：發 Slack、不呼叫 zero_variations；dry-run：都不呼叫
```

- [ ] **Step 2: Run to verify fail** — `uv run python -m pytest tests/listing/test_health.py -q` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run to verify pass** → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(listing): daily 1688 source health check with trial mode"`

---

### Task 13: 文件、排程與整體驗證

**Files:**
- Modify: `CLAUDE.md`、`AGENTS.md`（模組職責加 `listing/`；說明商家 SKU 命名、發佈閘門）、`docs/cli.md`（`listing` 各 action）
- Create: `docs/ops/listing-cron.md`（claw-arm-1 crontab 範例：每天 09:00 `health-check --notify`、每天 10:00 `discount-due --notify`；試跑一週後改 `--commit --notify`；環境變數 `GOOGLE_APPLICATION_CREDENTIALS`、`SLACK_WEBHOOK_URL`）
- 共用筆記：共用筆記檔 `project3-listing-flow-interfaces.md` 更新 `sku_measured_weights` 欄位契約

- [ ] **Step 1: 寫文件與 crontab 範例**
- [ ] **Step 2: 全部驗證**

Run: `uv run python -m pytest -q` → 全部 PASS
Run: `uv run python main.py test` → 結尾無 FAIL；有 ISSUE 記到 `issue.md`
Run: `uvx pyright modules/listing` → 0 errors

- [ ] **Step 3: 對正式帳號唯讀試跑（不帶 `--commit`、不帶 `--notify`）**

Run: `uv run python main.py listing backfill` → 印出可自動綁定數與需人工清單（預期約 182 個 SKU 的處理計畫）
Run: `uv run python main.py listing health-check` → 印出計畫動作，unknown 比例寫進 PR 說明

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md docs/cli.md docs/ops/listing-cron.md
git commit -m "docs: listing CLI, binding gate and cron setup"
```

- [ ] **Step 5: 開 PR**，說明裡列出：Task 1 錄到的 API、唯讀試跑結果、仍待業主決定的事（`listing backfill --commit` 與排程正式寫入的時間點）。
