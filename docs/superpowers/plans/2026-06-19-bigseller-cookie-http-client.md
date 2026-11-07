# BigSeller Cookie-based HTTP Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace in-browser `fetch()` (agent-browser eval_js / page.evaluate) with a cookie-based curl HTTP client for all BigSeller API calls, so the browser is only needed at login time.

**Architecture:** `bs login` (Playwright, one-shot) solves captcha then extracts httpOnly cookies via `context.cookies()` → saves `~/.bigseller_cookies.json`. A new `modules/bigseller/http_client.py` loads the cookie header and calls the BigSeller REST API via `curl` subprocess. `orders.py`, `sync.py`, `product.py` delegate their `_fetch_*` helpers to it. Mirrors the existing zhixia pattern. `sourcing.py` (1688 web scraping) is untouched.

**Tech Stack:** Python 3.13 (`/opt/homebrew/bin/python3.13`), stdlib `subprocess`/`json`/`base64`, `unittest` + `unittest.mock`, Playwright (login only).

## Global Constraints

- Python interpreter: `/opt/homebrew/bin/python3.13` (per CLAUDE.md / pyrightconfig).
- Run pytest via: `/opt/homebrew/bin/python3.13 -m pytest <path> -q`.
- Auth exception name MUST stay `SessionExpired` and its messages MUST contain the substring `session 過期` — `scripts/cron_auto_purchase.py:43` and `scripts/cron_fulfill.py:57` grep CLI output for `SessionExpired` / `session 過期` / `重新登入失敗` to trigger re-login. Do NOT rename to `BSAuthError`.
- No auto-relogin inside API calls (design decision B). Expired → raise `SessionExpired`, caller/user re-runs `bs login`.
- Cookies sent as the FULL header string (all ~23 cookies), not just `muc_token`+`JSESSIONID` (decision A).
- `sourcing.py`, `utils/browser.py`, `utils/agent_browser.py` are NOT modified.
- Docstrings/comments in Chinese (project style, per CLAUDE.md).
- Each module starts with `sys.path.insert(0, ...)` to import `config` (project style).

## Spec refinement (approved during planning)

The spec (§5.3, §7) named the exception `BSAuthError`. **Refined to `SessionExpired`** to preserve cron-script string matching (see Global Constraints). Behavior identical; only the name changes. `orders.py` keeps a `SessionExpired` symbol by importing it from `http_client`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `modules/bigseller/http_client.py` | **Create** | cookie load/save + curl-based `bs_get`/`bs_post_form`/`bs_post_json` + `SessionExpired` |
| `tests/test_bigseller_http_client.py` | **Create** | unit tests (mock `subprocess.run`) |
| `modules/bigseller/login.py` | Modify | on login success, call `save_cookies(ctx.cookies(...))` |
| `modules/bigseller/orders.py` | Modify | `_fetch_*` delegate to http_client; remove eval_js helpers |
| `modules/bigseller/sync.py` | Modify | `_fetch_*` delegate to http_client; remove eval_js helpers |
| `modules/bigseller/product.py` | Modify | `_fetch` uses http_client (4 call-sites); `_get_page` stays for scraping |
| `CLAUDE.md` | Modify | API 呼叫規範 + API Key Reference transport note |
| `AGENTS.md` | Modify | mirror CLAUDE.md |
| `docs/bigseller-api-notes.md` | Modify | transport note |

---

## Task 1: http_client cookie storage layer

**Files:**
- Create: `modules/bigseller/http_client.py`
- Test: `tests/test_bigseller_http_client.py`

**Interfaces:**
- Produces: `SessionExpired(Exception)`, `save_cookies(cookies: list[dict]) -> None`, `load_cookies() -> str`, `cookie_expiry() -> datetime | None`, module constant `COOKIE_PATH`.

- [ ] **Step 1: Write failing tests for cookie storage**

Create `tests/test_bigseller_http_client.py`:

```python
import json
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.bigseller import http_client
from modules.bigseller.http_client import SessionExpired


def _fake_cookies(exp_offset: int = 0):
    """Fake playwright cookie list with a muc_token JWT-like value."""
    # JWT payload {"exp": <now+20d>} base64url-encoded (no signature needed)
    import base64
    exp = int(time.time()) + 20 * 86400 + exp_offset
    payload = json.dumps({"exp": exp}).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    return [
        {"name": "muc_token", "value": f"eyJ0eXAi.{b64}.sig"},
        {"name": "JSESSIONID", "value": "ABC123"},
        {"name": "fingerPrint", "value": "fp"},
    ]


class TestCookieStorage(unittest.TestCase):
    def setUp(self):
        # 每個測試用獨立 cookie 檔，不污染家目錄
        self._tmp = "/tmp/_bs_http_client_test_cookies.json"
        self._orig = http_client.COOKIE_PATH
        http_client.COOKIE_PATH = __import__("pathlib").Path(self._tmp)
        if http_client.COOKIE_PATH.exists():
            http_client.COOKIE_PATH.unlink()

    def tearDown(self):
        http_client.COOKIE_PATH = self._orig
        p = __import__("pathlib").Path(self._tmp)
        if p.exists():
            p.unlink()

    def test_save_load_roundtrip(self):
        http_client.save_cookies(_fake_cookies())
        header = http_client.load_cookies()
        self.assertIn("muc_token=eyJ0eXAi", header)
        self.assertIn("JSESSIONID=ABC123", header)
        self.assertIn("fingerPrint=fp", header)

    def test_load_missing_raises(self):
        with self.assertRaises(SessionExpired):
            http_client.load_cookies()

    def test_load_expired_raises(self):
        http_client.save_cookies(_fake_cookies(exp_offset=-21 * 86400))  # 已過期
        with self.assertRaises(SessionExpired):
            http_client.load_cookies()

    def test_cookie_expiry(self):
        http_client.save_cookies(_fake_cookies())
        exp = http_client.cookie_expiry()
        self.assertIsInstance(exp, datetime)
        # 未登入時回 None
        http_client.COOKIE_PATH.unlink()
        self.assertIsNone(http_client.cookie_expiry())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_http_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.bigseller.http_client'`

- [ ] **Step 3: Create http_client.py with storage layer only**

Create `modules/bigseller/http_client.py`:

```python
"""BigSeller cookie-based HTTP client。

login（Playwright）抽 httpOnly cookie 存檔後，本模組以 curl 帶 cookie 打 API，
不再需要常駐瀏覽器。cookie 過期請重跑 `python main.py bs login`。
"""
from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_BS_BASE = "https://www.bigseller.com"
COOKIE_PATH = Path.home() / ".bigseller_cookies.json"
_SESSION_EXPIRED_CODE = 2001


class SessionExpired(Exception):
    """BigSeller 未登入或 session 過期；請跑 `python main.py bs login`。"""


def _muc_token_exp(cookies: list[dict]) -> int | None:
    """從 muc_token JWT payload 抽 exp（unix 秒）；找不到回 None。"""
    for c in cookies:
        if c.get("name") == "muc_token":
            try:
                payload_b64 = c["value"].split(".")[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                return int(json.loads(base64.urlsafe_b64decode(payload_b64))["exp"])
            except Exception:
                return None
    return None


def save_cookies(cookies: list[dict]) -> None:
    """playwright cookie list → 存 {header, exp, saved_at} 至 COOKIE_PATH。"""
    header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    data = {
        "header": header,
        "exp": _muc_token_exp(cookies),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    COOKIE_PATH.write_text(json.dumps(data, ensure_ascii=False))


def load_cookies() -> str:
    """回 cookie header 字串。缺檔或 muc_token exp 已過 → raise SessionExpired。"""
    if not COOKIE_PATH.exists():
        raise SessionExpired(
            "未登入 BigSeller（無 cookie 檔）；請跑 `python main.py bs login`"
        )
    data = json.loads(COOKIE_PATH.read_text())
    exp = data.get("exp")
    if exp and exp < time.time():
        raise SessionExpired(
            f"BigSeller session 過期 (exp={datetime.fromtimestamp(exp)});"
            "請跑 `python main.py bs login`"
        )
    return data["header"]


def cookie_expiry() -> datetime | None:
    """muc_token exp；未登入回 None。"""
    if not COOKIE_PATH.exists():
        return None
    data = json.loads(COOKIE_PATH.read_text())
    exp = data.get("exp")
    return datetime.fromtimestamp(exp) if exp else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_http_client.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/bigseller/http_client.py tests/test_bigseller_http_client.py
git commit -m "feat(bigseller): add cookie-based http_client storage layer"
```

---

## Task 2: http_client curl transport + GET/POST helpers

**Files:**
- Modify: `modules/bigseller/http_client.py` (append transport)
- Test: `tests/test_bigseller_http_client.py` (append transport tests)

**Interfaces:**
- Consumes: `load_cookies()` from Task 1.
- Produces: `bs_get(path, params=None) -> dict`, `bs_post_form(path, body: str) -> dict`, `bs_post_json(path, body: dict|list) -> dict`, internal `_curl(...)`.

- [ ] **Step 1: Write failing transport tests**

Append to `tests/test_bigseller_http_client.py` (inside the file, after the existing class):

```python
import subprocess


def _completed(stdout: str):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)


class TestTransport(unittest.TestCase):
    def setUp(self):
        self._tmp = "/tmp/_bs_http_client_test_cookies.json"
        self._orig = http_client.COOKIE_PATH
        http_client.COOKIE_PATH = __import__("pathlib").Path(self._tmp)
        http_client.save_cookies(_fake_cookies())  # 有效 cookie 檔
        # 記錄每次 curl 呼叫的 cmd
        self.calls = []
        self._patcher = patch(
            "modules.bigseller.http_client.subprocess.run",
            side_effect=self._fake_run,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        http_client.COOKIE_PATH = self._orig
        p = __import__("pathlib").Path(self._tmp)
        if p.exists():
            p.unlink()

    def _fake_run(self, cmd, **kwargs):
        self.calls.append(cmd)
        return self._next_response

    def _set_response(self, stdout: str):
        self._next_response = _completed(stdout)

    def test_bs_get_success(self):
        self._set_response('{"code":0,"data":{"x":1}}\n200')
        r = http_client.bs_get("/api/v1/purchase/manage/stateCount.json",
                               params={"purchaseType": 1})
        self.assertEqual(r["code"], 0)
        cmd = self.calls[0]
        self.assertIn("stateCount.json?purchaseType=1", " ".join(cmd))
        self.assertIn("-b", cmd)  # 帶 cookie

    def test_bs_post_json_body_and_header(self):
        self._set_response('{"code":0}\n200')
        http_client.bs_post_json("/api/v1/order/new/pageList.json",
                                 {"status": "new", "pageNo": 1})
        cmd = " ".join(self.calls[0])
        self.assertIn("Content-Type: application/json", cmd)
        self.assertIn('"status": "new"', cmd)

    def test_bs_post_form_body_and_header(self):
        self._set_response('{"code":-1,"msg":"missing params"}\n200')
        r = http_client.bs_post_form(
            "/api/v1/purchase/platform/manage/syncOrderByPurchaseIds.json",
            "purchaseIds=")
        self.assertEqual(r["code"], -1)  # business error 原樣回傳
        cmd = " ".join(self.calls[0])
        self.assertIn("Content-Type: application/x-www-form-urlencoded", cmd)

    def test_session_expired_code_2001(self):
        self._set_response('{"code":2001}\n200')
        with self.assertRaises(SessionExpired):
            http_client.bs_get("/any")

    def test_http_401(self):
        self._set_response('{}\n401')
        with self.assertRaises(SessionExpired):
            http_client.bs_get("/any")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_http_client.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'bs_get'`

- [ ] **Step 3: Append transport to http_client.py**

Append to `modules/bigseller/http_client.py`:

```python
from urllib.parse import urlencode

_DEFAULT_REFERER = "https://www.bigseller.com/web/order/index.htm"


def _check(resp: dict | None, http_code: int) -> dict:
    """判斷 session 過期：http 401/403、無回應、或 API code 2001 → raise SessionExpired。
    business error（code != 0）原樣回傳，不吞。"""
    if http_code in (401, 403):
        raise SessionExpired(
            f"BigSeller HTTP {http_code}；session 過期，請跑 `python main.py bs login`"
        )
    if resp is None:
        raise SessionExpired(
            "BigSeller API 無回應（session 過期？）；請跑 `python main.py bs login`"
        )
    if resp.get("code") == _SESSION_EXPIRED_CODE:
        raise SessionExpired(
            "BigSeller API session 過期 (code 2001)；請跑 `python main.py bs login`"
        )
    return resp


def _curl(method: str, path: str, *, content_type: str | None = None,
          body: str | None = None, params: dict | None = None) -> dict:
    """curl 帶 cookie 打 BigSeller API → 解析 JSON dict。"""
    url = path if path.startswith("http") else _BS_BASE + path
    if params:
        url = f"{url}?{urlencode(params)}"
    header = load_cookies()
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, url,
           "-H", "accept: application/json, text/plain, */*",
           "-H", "clienttype: 1",
           "-H", f"referer: {_DEFAULT_REFERER}",
           "-b", header]
    if content_type:
        cmd += ["-H", f"Content-Type: {content_type}"]
    if body is not None:
        cmd += ["-d", body]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"BigSeller API timeout: {url}") from e
    text = r.stdout
    if "\n" in text:
        body_text, code_str = text.rsplit("\n", 1)
        http_code = int(code_str) if code_str.strip().isdigit() else 0
    else:
        body_text, http_code = text, 0
    try:
        resp = json.loads(body_text) if body_text.strip() else None
    except json.JSONDecodeError:
        raise RuntimeError(
            f"BigSeller API 非 JSON 回應 (http {http_code}): {body_text[:200]}"
        )
    return _check(resp, http_code)


def bs_get(path: str, params: dict | None = None) -> dict:
    """GET → BigSeller response dict（含 code, data）。"""
    return _curl("GET", path, params=params)


def bs_post_form(path: str, body: str) -> dict:
    """POST form-urlencoded → response dict。"""
    return _curl("POST", path, content_type="application/x-www-form-urlencoded",
                 body=body)


def bs_post_json(path: str, body: dict | list) -> dict:
    """POST JSON → response dict。"""
    return _curl("POST", path, content_type="application/json",
                 body=json.dumps(body, ensure_ascii=False))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_http_client.py -q`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/bigseller/http_client.py tests/test_bigseller_http_client.py
git commit -m "feat(bigseller): add curl transport (bs_get/bs_post_form/bs_post_json)"
```

---

## Task 3: login.py saves cookies on success

**Files:**
- Modify: `modules/bigseller/login.py`
- Test: `tests/test_bigseller_http_client.py` (append `_save_cookies` test)

**Interfaces:**
- Consumes: `save_cookies` from Task 1.
- Produces: login success writes `~/.bigseller_cookies.json`.

- [ ] **Step 1: Write failing test for `_save_cookies`**

Append to `tests/test_bigseller_http_client.py`:

```python
class TestSaveCookiesOnLogin(unittest.TestCase):
    def setUp(self):
        self._tmp = "/tmp/_bs_login_test_cookies.json"
        self._orig = http_client.COOKIE_PATH
        http_client.COOKIE_PATH = __import__("pathlib").Path(self._tmp)
        if http_client.COOKIE_PATH.exists():
            http_client.COOKIE_PATH.unlink()

    def tearDown(self):
        http_client.COOKIE_PATH = self._orig
        p = __import__("pathlib").Path(self._tmp)
        if p.exists():
            p.unlink()

    def test_save_cookies_writes_file(self):
        from modules.bigseller.login import _save_cookies
        ctx = MagicMock()
        ctx.cookies.return_value = _fake_cookies()
        _save_cookies(ctx)
        self.assertTrue(http_client.COOKIE_PATH.exists())
        # cookie 檔可被 load_cookies 讀回
        self.assertIn("muc_token", http_client.load_cookies())

    def test_save_cookies_swallows_error(self):
        # cookie 抽取失敗不應讓 login 整個失敗
        from modules.bigseller.login import _save_cookies
        ctx = MagicMock()
        ctx.cookies.side_effect = RuntimeError("boom")
        _save_cookies(ctx)  # 不 raise
```

Add `from unittest.mock import MagicMock, patch` to the test file imports (replace the existing `from unittest.mock import patch` line).

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_http_client.py::TestSaveCookiesOnLogin -q`
Expected: FAIL — `ImportError: cannot import name '_save_cookies'`

- [ ] **Step 3: Add `_save_cookies` + call it on both login success paths**

In `modules/bigseller/login.py`, add this helper (place it just above `def login(`):

```python
def _save_cookies(ctx) -> None:
    """登入成功後抽 BigSeller httpOnly cookie 存檔，供 http_client curl 使用。

    失敗只記 warning，不影響登入結果。
    """
    try:
        from modules.bigseller.http_client import save_cookies, COOKIE_PATH
        cookies = ctx.cookies(["https://www.bigseller.com"])
        save_cookies(cookies)
        logger.info("✅ Cookies 已儲存至 %s", COOKIE_PATH)
    except Exception as exc:
        logger.warning("儲存 cookie 失敗（不影響登入）: %s", exc)
```

Then edit the two success paths in `login()`. Replace:

```python
    # ── Try restoring existing session in persistent context ────────
    if _try_restore_session(page):
        logger.info("✅ Session restored")
        return True

    # ── Fresh login on the same page ────────────────────────────────
    try:
        success = _do_login(page)
        if success:
            logger.info("✅ Login successful")
        else:
            logger.warning("OTP/2FA required — browser stays open for manual handling")
        return success
    except Exception:
        raise
```

with:

```python
    # ── Try restoring existing session in persistent context ────────
    if _try_restore_session(page):
        _save_cookies(ctx)
        logger.info("✅ Session restored")
        return True

    # ── Fresh login on the same page ────────────────────────────────
    try:
        success = _do_login(page)
        if success:
            _save_cookies(ctx)
            logger.info("✅ Login successful")
        else:
            logger.warning("OTP/2FA required — browser stays open for manual handling")
        return success
    except Exception:
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_http_client.py -q`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/bigseller/login.py tests/test_bigseller_http_client.py
git commit -m "feat(bigseller): save cookies to ~/.bigseller_cookies.json on login"
```

---

## Task 4: orders.py delegates _fetch_* to http_client

**Files:**
- Modify: `modules/bigseller/orders.py:1-150`

**Interfaces:**
- Consumes: `bs_get/bs_post_form/bs_post_json`, `SessionExpired` from http_client.
- Produces: same `_fetch_get/_fetch_post_form/_fetch_post_json` signatures (now thin wrappers), `SessionExpired` re-exported for any `except SessionExpired` callers.

- [ ] **Step 1: Replace header + helpers in orders.py**

Replace lines 1-150 of `modules/bigseller/orders.py` (the module docstring, imports, `SessionExpired`, `_relogin`, `_parse_eval_response`, `_check_session`, `_ensure_bigseller_origin`, and the three `_fetch_*` functions) with:

```python
"""BigSeller 採購單 + 蝦皮訂單管理

所有 API 透過 http_client（cookie-based curl）呼叫，不再需要常駐瀏覽器。
cookie 過期請重跑 `python main.py bs login`。

API 規格參考 CLAUDE.md（BigSeller API Key Reference）：
  - GET pageList / stateCount / detail
  - POST form submit / delete
  - POST json order/new/pageList
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.bigseller.http_client import (
    bs_get, bs_post_form, bs_post_json, SessionExpired,
)

_BS_BASE = "https://www.bigseller.com"


# ─── 薄 wrapper（保留原名以不動 call-site）────────────────────────

def _fetch_get(path: str) -> dict | None:
    """GET → BigSeller response dict（含 code, data）。"""
    return bs_get(path)


def _fetch_post_form(path: str, body: str) -> dict | None:
    """POST form-urlencoded → response dict。"""
    return bs_post_form(path, body)


def _fetch_post_json(path: str, body: dict) -> dict | None:
    """POST json → response dict。"""
    return bs_post_json(path, body)
```

- [ ] **Step 2: Verify import + existing order_processing tests still pass**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "from modules.bigseller import orders; print('orders import OK')"
/opt/homebrew/bin/python3.13 -m pytest tests/order_processing/ -q
```
Expected: import OK; all order_processing tests PASS (they inject fake deps, no network).

- [ ] **Step 3: Verify no remaining eval_js/_relogin/_check_session references in orders.py**

Run: `grep -nE "eval_js|_relogin|_check_session|_ensure_bigseller_origin|_parse_eval_response|from utils.agent_browser" modules/bigseller/orders.py`
Expected: no output (all removed).

- [ ] **Step 4: Live check against running browser's cookies (if cookie file absent, expect clear SessionExpired)**

Run: `/opt/homebrew/bin/python3.13 -c "from modules.bigseller.orders import get_state_count; print(get_state_count())"`
Expected: either a real `{'code':0,...}` dict (if `~/.bigseller_cookies.json` exists from a prior login) or `SessionExpired: 未登入...`. Either proves wiring (no crash, no agent-browser dependency).

- [ ] **Step 5: Commit**

```bash
git add modules/bigseller/orders.py
git commit -m "refactor(bigseller): orders.py fetch helpers delegate to http_client"
```

---

## Task 5: sync.py delegates _fetch_* to http_client

**Files:**
- Modify: `modules/bigseller/sync.py:1-63`

**Interfaces:**
- Consumes: `bs_get/bs_post_form/bs_post_json` from http_client.

- [ ] **Step 1: Replace header + helpers in sync.py**

Replace lines 1-63 of `modules/bigseller/sync.py` (docstring, imports, `_parse_eval_response`, `_fetch_get`, `_fetch_post_json`, `_fetch_post_form`) with:

```python
"""BigSeller 商品同步 API

封裝 SKU 匹配和供應商貨源 API，透過 http_client（cookie-based curl）呼叫。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.bigseller.http_client import bs_get, bs_post_form, bs_post_json


def _fetch_get(path: str) -> dict | None:
    """GET → response dict。"""
    return bs_get(path)


def _fetch_post_json(path: str, body: dict | list) -> dict | None:
    """POST json → response dict。body 可為 dict 或 list。"""
    return bs_post_json(path, body)


def _fetch_post_form(path: str, body: str) -> dict | None:
    """POST form → response dict。"""
    return bs_post_form(path, body)
```

- [ ] **Step 2: Verify import + no eval_js residue**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "from modules.bigseller import sync; print('sync import OK')"
grep -nE "eval_js|_parse_eval_response|from utils.agent_browser" modules/bigseller/sync.py
```
Expected: import OK; grep outputs nothing.

- [ ] **Step 3: Commit**

```bash
git add modules/bigseller/sync.py
git commit -m "refactor(bigseller): sync.py fetch helpers delegate to http_client"
```

---

## Task 6: product.py _fetch uses http_client (keep _get_page for scraping)

**Files:**
- Modify: `modules/bigseller/product.py:48-62` (the `_fetch` helper) and the 4 call-sites at lines ~70, ~175, ~215, ~219.

> Scope note: `product.py` uses `_get_page()` + `page.evaluate(...)` for **1688 scraping** (lines 104, 123, 139, 180, 240-253, 337, 392, 577, 675-701). Those stay browser-based. Only the 4 `_fetch(...)` API call-sites move to http_client.

**Interfaces:**
- Consumes: `bs_get/bs_post_json` from http_client.

- [ ] **Step 1: Replace `_fetch` helper**

Replace the `_fetch(page, url, method='GET', body=None)` function (lines 48-62) with:

```python
def _fetch(url, method='GET', body=None):
    """打 BigSeller API（cookie-based curl）。GET 或 POST json。"""
    if method == 'GET':
        return bs_get(url)
    return bs_post_json(url, body or {})
```

Add to the imports section of `product.py` (after the existing `from utils.browser import ensure_browser` line):

```python
from modules.bigseller.http_client import bs_get, bs_post_json
```

- [ ] **Step 2: Update the 4 call-sites to drop the `page` argument**

Find and edit each call (the first positional `page` arg is removed):

- Line ~70 (`sync_product`):
  `return _fetch(page, f'/api/v1/product/listing/shopee/syncProductById.json?id={product_id}')`
  → `return _fetch(f'/api/v1/product/listing/shopee/syncProductById.json?id={product_id}')`
  Also remove the now-unused `page = _get_page()` line at ~69 IF `sync_product` has no other `page` use. (Check: `sync_product` body — if it only does the `_fetch`, remove `page = _get_page()` too. If it uses `page` elsewhere, keep it.)

- Line ~175 (inside `update_product` flow):
  `sync_r = _fetch(page, f'/api/v1/product/listing/shopee/syncProductById.json?id={product_id}')`
  → `sync_r = _fetch(f'/api/v1/product/listing/shopee/syncProductById.json?id={product_id}')`
  (Keep `page = _get_page()` at ~171 — `update_product` uses `page.evaluate` at ~180.)

- Line ~215 (`checkProductRepeat`):
  `check_r = _fetch(page, '/api/v1/product/listing/shopee/checkProductRepeat.json', method='POST', body=check_body)`
  → `check_r = _fetch('/api/v1/product/listing/shopee/checkProductRepeat.json', method='POST', body=check_body)`

- Line ~219 (`edit`):
  `save_r = _fetch(page, '/api/v1/product/listing/shopee/edit.json', method='POST', body=form_data)`
  → `save_r = _fetch('/api/v1/product/listing/shopee/edit.json', method='POST', body=form_data)`

- [ ] **Step 3: Verify import + existing product tests pass**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "from modules.bigseller import product; print('product import OK')"
/opt/homebrew/bin/python3.13 -m pytest tests/test_bigseller_product.py -q
```
Expected: import OK; product tests PASS (they mock `page`, unaffected by `_fetch` change).

- [ ] **Step 4: Confirm no `_fetch(page` residue**

Run: `grep -n "_fetch(page" modules/bigseller/product.py`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add modules/bigseller/product.py
git commit -m "refactor(bigseller): product.py _fetch uses http_client (keep _get_page for scraping)"
```

---

## Task 7: Update documentation

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md`, `docs/bigseller-api-notes.md`

- [ ] **Step 1: Update CLAUDE.md `## API 呼叫規範`**

In `CLAUDE.md`, find the line under `## API 呼叫規範`:

```
- BigSeller API：透過 agent-browser `eval_js()` 在 BigSeller 頁面 fetch() — 共用 session cookie
```

Replace with:

```
- BigSeller API：`modules/bigseller/http_client.py` 用 curl 帶 httpOnly cookie（`muc_token` JWT + 全 cookie，存 `~/.bigseller_cookies.json`）直接打 — 不需常駐瀏覽器；cookie 過期重跑 `python main.py bs login`
```

- [ ] **Step 2: Update CLAUDE.md `## BigSeller API Key Reference` intro**

Find:

```
所有 BigSeller API 呼叫都透過 agent-browser eval_js 在已登入頁面上 fetch：
```

Replace with:

```
所有 BigSeller API 呼叫都透過 `modules/bigseller/http_client.py`（curl + cookie）：
```

- [ ] **Step 3: Mirror the same two edits in AGENTS.md**

`AGENTS.md` is the mirror of CLAUDE.md. Apply the identical two replacements.

- [ ] **Step 4: Update docs/bigseller-api-notes.md**

Open `docs/bigseller-api-notes.md`. If it describes the agent-browser/eval_js transport, update the transport paragraph to describe cookie-based curl via `http_client.py` (cookie file `~/.bigseller_cookies.json`, refresh via `bs login`). If the file only documents endpoint URLs (not transport), add a one-line note at the top: `> Transport: modules/bigseller/http_client.py (curl + httpOnly cookie, saved by bs login).`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md AGENTS.md docs/bigseller-api-notes.md
git commit -m "docs(bigseller): document cookie-based http_client transport"
```

---

## Task 8: Acceptance test — API works without a browser

**Files:** none (verification only)

> This proves the refactor's core claim: BigSeller API calls no longer need a running browser.

- [ ] **Step 1: Ensure a fresh cookie file exists**

Run login (writes `~/.bigseller_cookies.json`):
`/opt/homebrew/bin/python3.13 main.py bs login`
Expected: `✅ 登入成功` and `~/.bigseller_cookies.json` exists:
`ls -la ~/.bigseller_cookies.json`

- [ ] **Step 2: Kill the persistent browser + host**

Stop the browser host started earlier this session and any Chromium on 9333:
```bash
pkill -f bs_host.py
/opt/homebrew/bin/python3.13 -c "from utils.browser import kill_chrome; kill_chrome()"
```
Confirm 9333 is down: `lsof -nP -iTCP:9333 -sTCP:LISTEN` → no output.

- [ ] **Step 3: Run CLI API commands from a fresh shell (no browser)**

Run each; expect real data, NOT `SessionExpired` and NOT "瀏覽器未連線":
```bash
/opt/homebrew/bin/python3.13 main.py bs order list --status new --limit 10
/opt/homebrew/bin/python3.13 main.py bs purchase states
/opt/homebrew/bin/python3.13 main.py orders prepare-purchase
```
Expected: order list count, `stateCount` JSON (aliDraft etc.), prepare-purchase dry-run plan.

- [ ] **Step 4: Run the full module validation**

Run: `/opt/homebrew/bin/python3.13 tests/run_all.py`
Expected: PASS/ISSUE/FAIL summary with no new FAILs attributable to the refactor.

- [ ] **Step 5: Run pyright**

Run: `pyright modules/bigseller/http_client.py modules/bigseller/orders.py modules/bigseller/sync.py modules/bigseller/product.py modules/bigseller/login.py`
Expected: no new errors.

- [ ] **Step 6: Final commit (if any cleanup)**

If Steps 1-5 needed no code changes, no commit. Otherwise commit the fix.

---

## Self-Review (completed during planning)

**Spec coverage:** spec §5.1 → Tasks 1-2; §5.2 → Task 3; §5.3 → Task 4; §5.4 → Task 5; §5.5 → Task 6 (corrected: `_get_page`/`ensure_browser` stay for scraping); §6 format → Task 1 `save_cookies`; §7 error handling → Task 2 `_check`; §8 testing → Tasks 1-3 tests + Task 8 acceptance; §9 docs → Task 7. All sections covered.

**Placeholder scan:** every code step contains full code. Task 6 Step 2 has a conditional ("IF sync_product has no other page use") — this is a real branch the implementer resolves by inspection, with explicit guidance for both cases. No TBD/TODO.

**Type consistency:** `SessionExpired` used consistently (renamed from spec's `BSAuthError` — documented in refinement section + Global Constraints). `bs_get(path, params=None)`, `bs_post_form(path, body:str)`, `bs_post_json(path, body:dict|list)` signatures identical across Tasks 2,4,5,6. `save_cookies(cookies:list[dict])`, `load_cookies()->str`, `cookie_expiry()->datetime|None` consistent across Tasks 1,3.

**Cron compatibility:** `SessionExpired` name + `session 過期` substring preserved (Global Constraints) — `scripts/cron_*.py` string matching unaffected.
