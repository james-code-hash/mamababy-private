# BigSeller Cookie-based HTTP Client 重構設計

- 日期：2026-06-19
- 狀態：Approved
- 作者：James（與 Claude 協作）

## 1. 背景與動機

BigSeller 模組目前的 API 呼叫**全部**透過 `utils/agent_browser.eval_js`，在「持續運行的瀏覽器頁面」內執行 `fetch()` 來共用 session cookie。這衍生三個問題：

1. **瀏覽器必須常駐**：`utils/browser.py` 的 `ensure_browser()` 用 `launch_persistent_context` + `atexit._cleanup`，process 結束就關瀏覽器。每個獨立 CLI 指令（各自一個 process）連不上已死的瀏覽器，API 全掛。需額外跑「常駐 host process」繞過。
2. **CloakBrowser 不開 CDP port**：`ensure_browser` 的 CloakBrowser 分支不帶 `--remote-debugging-port`，`is_chrome_running()`（查 9333）恆 False，agent-browser 永遠連不上。
3. **三套重複 transport**：`orders.py`、`sync.py`（重複的 `_fetch_*`）、`product.py`（`_fetch(page,...)` 用 `page.evaluate()`）各自實作 fetch，難以統一測試與維護。

### 關鍵發現

BigSeller 認證 = **httpOnly cookie**（`muc_token` JWT + `JSESSIONID`，共 23 個），**可用 curl `-b <header>` 直接打 API**。實測三種 transport 全驗證通過：

| transport | 端點 | 結果 |
|---|---|---|
| GET | `purchase/manage/stateCount.json?purchaseType=1` | code:0（aliDraft:4） |
| POST json | `order/new/pageList.json` `{"status":"new",...}` | code:0（rows:0） |
| POST form | `purchase/platform/manage/syncOrderByPurchaseIds.json` `purchaseIds=` | code:-1「missing params」（auth 過，-1 為空參數） |

cookie 透過 Playwright `context.cookies()`（CDP）抽取，可拿到 httpOnly cookie（`document.cookie` 拿不到）。`muc_token` 為 JWT，**效期 20 天**（exp 欄位）。

### 對照 zhixia 模式

zhixia 已是「login（Playwright）→ 抽 token 存檔 → curl（無瀏覽器）」模式。本重構讓 BigSeller 對齊此模式。

## 2. 目標與非目標

### 目標
- BigSeller API 呼叫改為 cookie-based curl subprocess，**不再需要常駐瀏覽器**。
- 瀏覽器僅在 `bs login` 時一次性使用（解驗證碼 + 抽 cookie）。
- 統一三套 fetch 實作為單一 `http_client` 模組。
- 與 zhixia 架構一致（login → cookie 檔 → curl）。

### 非目標
- 不動 `sourcing.py`（1688.com 網頁搜尋爬蟲，需瀏覽器渲染，維持 agent-browser）。
- 不動 `utils/browser.py` / `utils/agent_browser.py`（sourcing + login 仍用）。
- 不改 1688 下單確認流程（`bs purchase confirm`）業務邏輯。
-不自動重登入（見 §4 決策）。

## 3. 設計決策

| 議題 | 決策 | 理由 |
|---|---|---|
| Token 過期處理 | **不自動重登入**；cookie 檔缺/過期/API code 2001/http 401,403 → raise `BSAuthError`，提示手動跑 `bs login` | 與 zhixia 一致、可預測；避免 curl 呼叫突然卡 30s 過驗證碼；20 天效期手動重登頻率低 |
| Cookie 顆粒度 | **帶全部 23 cookie**（存整段 header 字串） | 完全等同瀏覽器行為，最穩；伺服器可能檢查 `fingerPrint` 等 |
| http_client API 形狀 | **模組函式**（`bs_get/bs_post_form/bs_post_json` + `load_cookies/save_cookies`） | 對齊現有 `_fetch_*` 命名，call-site 改動最小 |
| eval_js 去留 | **完全移除**（orders/sync/product） | cookie 模式不需瀏覽器；留 fallback 只增複雜度 |

## 4. 架構與資料流

```
bs login (Playwright 一次性, Gemini OCR 驗證碼)
  └─ context.cookies(['https://www.bigseller.com'])
     └─ save_cookies() → ~/.bigseller_cookies.json
        └─ 瀏覽器可關閉

API 呼叫（任何 CLI 指令）:
  http_client.load_cookies() → header 字串
  └─ _curl(url, -b header, ...) → BigSeller API → JSON dict
     └─ code 2001 / http 401,403 → BSAuthError
```

## 5. 元件

### 5.1 NEW `modules/bigseller/http_client.py`

```python
COOKIE_PATH = ~/.bigseller_cookies.json
_BS_BASE = "https://www.bigseller.com"
_SESSION_EXPIRED_CODE = 2001

class BSAuthError(Exception):
    """未登入或 session 過期；請跑 `python main.py bs login`。"""

def save_cookies(cookies: list[dict]) -> None:
    """playwright cookie list → 存 {header, exp, saved_at}。exp 取自 muc_token JWT。"""

def load_cookies() -> str:
    """回 header 字串。缺檔或 muc_token exp 已過 → raise BSAuthError。"""

def cookie_expiry() -> datetime | None:
    """muc_token exp；未登入回 None。"""

def bs_get(path: str, params: dict | None = None) -> dict
def bs_post_form(path: str, body: str) -> dict
def bs_post_json(path: str, body: dict | list) -> dict

def _curl(url, method, content_type, data) -> dict:
    """subprocess curl -s -w '\\n%{http_code}'；解析 stdout+http_code。
       code 2001 / http 401,403 → BSAuthError；timeout/網路錯 → RuntimeError。
       business error (code != 0) 原樣回傳，不吞。"""
```

**共帶 header**：`accept`、`clienttype: 1`、`referer: https://www.bigseller.com/...`、`-b <header>`（全 cookie）。content-type 由 method 決定。

### 5.2 MODIFY `modules/bigseller/login.py`

login 成功路徑（`login()` 成功 + `_try_restore_session` 成功）呼叫新增的 `_save_cookies(ctx)`：
```python
def _save_cookies(ctx) -> None:
    from modules.bigseller.http_client import save_cookies
    cookies = ctx.cookies(['https://www.bigseller.com'])
    save_cookies(cookies)
```
在 `login()` 回傳 True 前、`_try_restore_session` 回傳 True 前各呼叫一次。

### 5.3 MODIFY `modules/bigseller/orders.py`
- `_fetch_get/_fetch_post_form/_fetch_post_json` → delegate `http_client.bs_get/bs_post_form/bs_post_json`。**保留函式名作薄 wrapper**（內容只剩一行轉呼），降 call-site 改動量；call-site 不動。
- 移除：`from utils.agent_browser import eval_js`、`_ensure_bigseller_origin`、`_parse_eval_response`、`_relogin`。
- `SessionExpired`：改為 `BSAuthError` 的 alias（`SessionExpired = BSAuthError`），保留 caller 的 `except SessionExpired`。更新 docstring。

### 5.4 MODIFY `modules/bigseller/sync.py`
- 3 個重複 `_fetch_get/_fetch_post_json/_fetch_post_form` → delegate http_client。
- 移除 `from utils.agent_browser import eval_js`、自有 `_parse_eval_response`。

### 5.5 MODIFY `modules/bigseller/product.py`
- `_fetch(page, url, method, body)` → 內部改呼叫 http_client（`bs_get/bs_post_form/bs_post_json`）。
- 拿掉 `_fetch` 的 `page` 參數與 call-site 的 page 傳遞。
- 移除不再使用的 `from utils.browser import ensure_browser`（若 product.py 僅用於 API；若有其他瀏覽器用途則保留——實作時確認）。

### 5.6 UNCHANGED
- `modules/bigseller/sourcing.py`：1688 爬蟲（run_ab/snapshot/fill），維持 agent-browser + 瀏覽器。
- `utils/browser.py`（含 9333 patch）、`utils/agent_browser.py`：sourcing + login 仍用。

## 6. Cookie 存檔格式

`~/.bigseller_cookies.json`：
```json
{
  "header": "muc_token=eyJ...; JSESSIONID=...; <全部 23 個 name=value>",
  "exp": 1783585815,
  "saved_at": "2026-06-19T15:38:39"
}
```
- `header`：現成 `-b` 字串（CDP 抽取，含 httpOnly）。
- `exp`：muc_token JWT payload `exp`（unix 秒），主動過期檢查用。
- `saved_at`：debug/可讀性。

## 7. 錯誤處理

| 情境 | 行為 |
|---|---|
| 無 cookie 檔 | `BSAuthError("未登入；請先跑 python main.py bs login")` |
| muc_token exp 已過 | `BSAuthError("session 過期 (exp=...)；請跑 python main.py bs login")` |
| API 回 code 2001 | `BSAuthError("API session 過期；請跑 python main.py bs login")` |
| http 401 / 403 | `BSAuthError(...)` |
| curl timeout / 網路錯 | `RuntimeError` 帶 stderr |
| API code != 0（business error） | **原樣回傳** resp dict，caller 自決（不吞） |

http_client **不自動重登入**、**不吞 business error**。

## 8. 測試

### NEW `tests/test_bigseller_http_client.py`（單元，mock `subprocess.run`）
- `load_cookies` 缺檔 → `BSAuthError`
- `load_cookies` exp 已過 → `BSAuthError`
- `bs_get` 成功（mock 回 code:0 JSON）→ 正確解析
- `bs_post_json` / `bs_post_form` 成功
- API code 2001 → `BSAuthError`
- http 401 → `BSAuthError`
- `save_cookies` → `load_cookies` roundtrip 一致

### 既有測試不受影響
- `tests/order_processing/test_bigseller_deps.py`：注入假 deps，不打網路 → 不受影響。
- `tests/order_processing/test_prepare_purchase.py` 等：同上。

### 驗收測試（手動，impl 後跑）
1. `bs login` → 確認 `~/.bigseller_cookies.json` 產生。
2. **殺掉 host 瀏覽器**（`kill` 9333 上的 Chromium + `/tmp/bs_host.py`）。
3. fresh shell 跑：
   - `python main.py bs order list --status new` → 正常（非 SessionExpired）
   - `python main.py bs purchase states` → code:0 真實資料
   - `python main.py orders prepare-purchase` → dry-run 正常
4. 全部不需瀏覽器 = 重構成功。

## 9. 文檔修正

- **CLAUDE.md**：`## API 呼叫規範` 的 BigSeller 行（現寫「透過 agent-browser eval_js()…共用 session cookie」）→ 改為 cookie-curl 說明。`## BigSeller API Key Reference` 的 GET/postForm/postJ 機制註記同步更新。
- **AGENTS.md**（CLAUDE.md 鏡像）：同步改。
- **docs/bigseller-api-notes.md**：更新 transport 說明。
- **模組 docstring**：`orders.py`、`sync.py`、`product.py` 開頭註解（現提 agent-browser eval_js）。

歷史 design/plan 文檔（`docs/superpowers/specs|plans/2026-06-16-order-processing-*`）為歷史紀錄，不追溯改。

## 10. 風險與緩解

| 風險 | 緩解 |
|---|---|
| 伺服器檢查非 cookie header（如 `x-csrf-token`） | 實作時若某 endpoint 失敗，比對瀏覽器 DevTools 完整 request header 補上；GET/order/purchase 已驗證不需 |
| muc_token 過期但 JSESSIONID 仍在 → 誤判 | 以 muc_token exp 為準（JWT 有明確 exp）；API code 2001 為第二道防線 |
| cookie 檔含敏感憑證 | 與 `~/.zhixia_tokens.json` 同等級（家目錄 600）；不入 git |
| product.py 對 page 有非 API 用途 | §5.5 實作時逐一確認 call-site |
