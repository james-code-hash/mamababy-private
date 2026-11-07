# Slice 1: prepare-purchase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the order-driven `prepare-purchase` command — read BigSeller out-of-stock Shopee orders, group by (supplier, warehouse) into purchase batches, and create/overwrite 1688 purchase drafts only when demand changed (fingerprint-gated), with a thin local store.

**Architecture:** New `modules/order_processing/` package. Pure functions for batching, fingerprinting, and action decisions (no I/O, table-driven unit tests). A thin SQLite store persists only purchase-batch fingerprints (BigSeller owns inventory/allocation/state per ADR 0010/0012; order-processing state is a computed view per T1). Orchestrator glues BigSeller API + pure logic, dry-run by default.

**Tech Stack:** Python 3.13 (`/opt/homebrew/bin/python3.13`), stdlib only (`sqlite3`, `hashlib`, `json`, `dataclasses`, `unittest`). BigSeller calls reuse existing `modules/bigseller/orders.py` (agent-browser `eval_js` fetch). Tests are stdlib `unittest` files run directly (repo has no pytest).

**Spec:** [docs/superpowers/specs/2026-06-16-order-processing-slice1-prepare-purchase-design.md](../specs/2026-06-16-order-processing-slice1-prepare-purchase-design.md)
**API notes:** [docs/bigseller-api-notes.md](../../bigseller-api-notes.md)

---

## File Structure

| File | Responsibility |
|---|---|
| `modules/order_processing/__init__.py` | package marker |
| `modules/order_processing/fingerprint.py` | `compute_fingerprint()` — deterministic batch digest (pure) |
| `modules/order_processing/batching.py` | `extract_order_lines()`, `build_batches()` — parse + group (pure) |
| `modules/order_processing/state_view.py` | `BatchAction` + `decide_purchase_actions()` — action decision (pure) |
| `modules/order_processing/store.py` | `FingerprintStore` — thin SQLite over `purchase_batch_fingerprint` |
| `modules/order_processing/prepare_purchase.py` | orchestration: BigSeller I/O + pure logic, dry-run/commit |
| `modules/bigseller/orders.py` (modify) | add `get_out_of_stock_orders()` (packState=4) |
| `config.py` (modify) | add `ORDER_PROCESSING_DB` path |
| `main.py` (modify) | add `orders prepare-purchase` subcommand |
| `docs/adr/0001-local-sqlite-order-processing-store.md` (modify) | rewrite to thin store (T1) |
| `tests/order_processing/test_*.py` | unittest files, run directly |

**Test convention** (matches repo's `sys.path.insert` pattern; no pytest):
Each test file starts with:
```python
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```
and ends with `if __name__ == "__main__": unittest.main()`.
Run a file: `/opt/homebrew/bin/python3.13 tests/order_processing/test_X.py -v`

---

## Task 1: Package scaffold + config DB path

**Files:**
- Create: `modules/order_processing/__init__.py`
- Modify: `config.py` (append after `PROJECT_ROOT`)
- Test: `tests/order_processing/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_scaffold.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestScaffold(unittest.TestCase):
    def test_package_imports(self):
        import modules.order_processing  # noqa: F401

    def test_config_db_path_defined(self):
        from config import ORDER_PROCESSING_DB
        self.assertTrue(ORDER_PROCESSING_DB.endswith("order_processing.db"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_scaffold.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.order_processing'`

- [ ] **Step 3: Create the package and config constant**

Create `modules/order_processing/__init__.py`:
```python
"""訂單處理（第一輪）：薄 store + 計算視圖 + prepare-purchase。"""
```

In `config.py`, add after the `PROJECT_ROOT = Path(__file__).parent` line:
```python
# ── 訂單處理本地 store（薄 store，僅存 BigSeller 不模型化的東西）──
ORDER_PROCESSING_DB = str(PROJECT_ROOT / "data" / "order_processing.db")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_scaffold.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/__init__.py config.py tests/order_processing/test_scaffold.py
git commit -m "feat(order-processing): scaffold package + thin-store db path"
```

---

## Task 2: fingerprint.compute_fingerprint

A batch's fingerprint is a stable SHA-256 over (supplier, warehouse, sorted order numbers, sorted (sku, qty) pairs). Same demand → same fingerprint; any change → different.

**Files:**
- Create: `modules/order_processing/fingerprint.py`
- Test: `tests/order_processing/test_fingerprint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_fingerprint.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing.fingerprint import compute_fingerprint


class TestFingerprint(unittest.TestCase):
    def _batch(self):
        return dict(
            supplier_id=101, warehouse_id=54396,
            order_nos=["A2", "A1"],
            items=[{"sku": "X-红", "qty": 2}, {"sku": "Y-蓝", "qty": 1}],
        )

    def test_deterministic_and_order_insensitive(self):
        b1 = self._batch()
        b2 = dict(
            supplier_id=101, warehouse_id=54396,
            order_nos=["A1", "A2"],                       # reordered
            items=[{"sku": "Y-蓝", "qty": 1}, {"sku": "X-红", "qty": 2}],  # reordered
        )
        self.assertEqual(compute_fingerprint(**b1), compute_fingerprint(**b2))

    def test_qty_change_changes_fingerprint(self):
        base = compute_fingerprint(**self._batch())
        changed = self._batch()
        changed["items"][0]["qty"] = 3
        self.assertNotEqual(base, compute_fingerprint(**changed))

    def test_order_set_change_changes_fingerprint(self):
        base = compute_fingerprint(**self._batch())
        changed = self._batch()
        changed["order_nos"].append("A3")
        self.assertNotEqual(base, compute_fingerprint(**changed))

    def test_warehouse_change_changes_fingerprint(self):
        base = compute_fingerprint(**self._batch())
        changed = self._batch()
        changed["warehouse_id"] = 2001
        self.assertNotEqual(base, compute_fingerprint(**changed))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_fingerprint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.order_processing.fingerprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/order_processing/fingerprint.py
"""採購批次指紋：偵測採購覆蓋（ADR 0004）。"""
import hashlib
import json


def compute_fingerprint(supplier_id: int, warehouse_id: int,
                        order_nos: list[str], items: list[dict]) -> str:
    """由（供應商, 倉庫, 來源訂單集合, 商品數量）算穩定指紋。

    items: [{"sku": str, "qty": int}, ...]。對 order_nos 與 items 排序後雜湊，
    確保同需求同指紋、需求變則指紋變。
    """
    payload = {
        "supplier_id": int(supplier_id),
        "warehouse_id": int(warehouse_id),
        "order_nos": sorted(str(n) for n in order_nos),
        "items": sorted((str(it["sku"]), int(it["qty"])) for it in items),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_fingerprint.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/fingerprint.py tests/order_processing/test_fingerprint.py
git commit -m "feat(order-processing): purchase-batch fingerprint"
```

---

## Task 3: store.FingerprintStore

Thin SQLite over `purchase_batch_fingerprint`, keyed by (supplier_id, warehouse_id). Only persists fingerprints + the draft purchase_id we created.

**Files:**
- Create: `modules/order_processing/store.py`
- Test: `tests/order_processing/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_store.py
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing.store import FingerprintStore


class TestFingerprintStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")

    def test_empty_get_all(self):
        store = FingerprintStore(self.db)
        self.assertEqual(store.get_all(), {})

    def test_upsert_then_get_all(self):
        store = FingerprintStore(self.db)
        store.upsert(101, 54396, "fp-abc", 9001)
        got = store.get_all()
        self.assertEqual(got[(101, 54396)], {"fingerprint": "fp-abc", "purchase_id": 9001})

    def test_upsert_overwrites_same_key(self):
        store = FingerprintStore(self.db)
        store.upsert(101, 54396, "fp-old", 9001)
        store.upsert(101, 54396, "fp-new", 9002)
        got = store.get_all()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[(101, 54396)], {"fingerprint": "fp-new", "purchase_id": 9002})

    def test_persists_across_instances(self):
        FingerprintStore(self.db).upsert(7, 8, "fp", 1)
        self.assertIn((7, 8), FingerprintStore(self.db).get_all())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.order_processing.store'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/order_processing/store.py
"""薄本地 store：只存 BigSeller 不模型化的東西（ADR 0010, T1）。

Slice 1 只一張表：採購批次指紋。Store 介面可替換。
"""
import os
import sqlite3


class FingerprintStore:
    """採購批次指紋的 SQLite 存取，鍵為 (supplier_id, warehouse_id)。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_batch_fingerprint (
                    supplier_id   INTEGER NOT NULL,
                    warehouse_id  INTEGER NOT NULL,
                    fingerprint   TEXT    NOT NULL,
                    purchase_id   INTEGER,
                    computed_at   TEXT    DEFAULT (datetime('now')),
                    PRIMARY KEY (supplier_id, warehouse_id)
                )
                """
            )

    def get_all(self) -> dict[tuple[int, int], dict]:
        """回傳 {(supplier_id, warehouse_id): {"fingerprint", "purchase_id"}}。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT supplier_id, warehouse_id, fingerprint, purchase_id "
                "FROM purchase_batch_fingerprint"
            ).fetchall()
        return {
            (r[0], r[1]): {"fingerprint": r[2], "purchase_id": r[3]}
            for r in rows
        }

    def upsert(self, supplier_id: int, warehouse_id: int,
               fingerprint: str, purchase_id: int | None) -> None:
        """寫入或覆蓋一個 (supplier, warehouse) 批次的指紋。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO purchase_batch_fingerprint
                    (supplier_id, warehouse_id, fingerprint, purchase_id, computed_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(supplier_id, warehouse_id) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    purchase_id = excluded.purchase_id,
                    computed_at = excluded.computed_at
                """,
                (int(supplier_id), int(warehouse_id), fingerprint,
                 None if purchase_id is None else int(purchase_id)),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_store.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/store.py tests/order_processing/test_store.py
git commit -m "feat(order-processing): thin fingerprint store"
```

---

## Task 4: batching.extract_order_lines

Pure: turn one BigSeller out-of-stock order row into flat line dicts. Tested against the real captured row.

**Files:**
- Create: `modules/order_processing/batching.py`
- Test: `tests/order_processing/test_batching_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_batching_extract.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing.batching import extract_order_lines

# 真實缺貨 row（截自 order/new/pageList.json packState=4，見 bigseller-api-notes.md）
REAL_ROW = {
    "platformOrderId": "260616734X5J0J",
    "warehouseId": 54396,
    "shipmentWarehouse": "眾達國際",
    "packState": 4,
    "orderItemList": [
        {"itemSku": "564403880886",
         "varSku": "564403880886-猫咪男款（深藍）-44-45碼",
         "varAttr": "猫咪男款（深藍）,44-45碼", "quantity": 1, "skuId": None},
    ],
}


class TestExtractOrderLines(unittest.TestCase):
    def test_extracts_one_line(self):
        lines = extract_order_lines(REAL_ROW)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], {
            "platform_order_id": "260616734X5J0J",
            "warehouse_id": 54396,
            "sku_id": None,
            "item_sku": "564403880886",
            "var_sku": "564403880886-猫咪男款（深藍）-44-45碼",
            "quantity": 1,
        })

    def test_multiple_items(self):
        row = {
            "platformOrderId": "O9", "warehouseId": 7,
            "orderItemList": [
                {"itemSku": "A", "varSku": "A-1", "quantity": 2, "skuId": 11},
                {"itemSku": "B", "varSku": "B-1", "quantity": 1, "skuId": None},
            ],
        }
        lines = extract_order_lines(row)
        self.assertEqual([l["item_sku"] for l in lines], ["A", "B"])
        self.assertEqual(lines[0]["sku_id"], 11)
        self.assertEqual(lines[0]["quantity"], 2)

    def test_missing_quantity_defaults_to_one(self):
        row = {"platformOrderId": "O", "warehouseId": 1,
               "orderItemList": [{"itemSku": "A", "varSku": "A-1"}]}
        self.assertEqual(extract_order_lines(row)[0]["quantity"], 1)

    def test_empty_item_list(self):
        self.assertEqual(extract_order_lines({"platformOrderId": "O", "warehouseId": 1}), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_batching_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.order_processing.batching'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/order_processing/batching.py
"""缺貨來源訂單 → 採購批次（純函式，無 I/O）。"""


def extract_order_lines(order_row: dict) -> list[dict]:
    """把一筆 BigSeller 缺貨訂單 row 攤平成行項目清單。

    每行：{platform_order_id, warehouse_id, sku_id, item_sku, var_sku, quantity}。
    """
    platform_order_id = order_row.get("platformOrderId") or ""
    warehouse_id = order_row.get("warehouseId")
    lines = []
    for item in order_row.get("orderItemList") or []:
        lines.append({
            "platform_order_id": platform_order_id,
            "warehouse_id": warehouse_id,
            "sku_id": item.get("skuId"),
            "item_sku": item.get("itemSku") or "",
            "var_sku": item.get("varSku") or "",
            "quantity": item.get("quantity") or 1,
        })
    return lines
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_batching_extract.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/batching.py tests/order_processing/test_batching_extract.py
git commit -m "feat(order-processing): extract order lines from out-of-stock rows"
```

---

## Task 5: batching.build_batches

Pure: group already-resolved lines (each carrying supplier_id, warehouse_id, sku, qty, order_no, purchase_price) into batches keyed by (supplier_id, warehouse_id), summing qty per sku and de-duping order numbers.

**Files:**
- Modify: `modules/order_processing/batching.py`
- Test: `tests/order_processing/test_batching_build.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_batching_build.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing.batching import build_batches


def line(order_no, supplier_id, warehouse_id, sku, qty, sku_id=None, price=0):
    return {"platform_order_id": order_no, "supplier_id": supplier_id,
            "warehouse_id": warehouse_id, "var_sku": sku, "sku_id": sku_id,
            "quantity": qty, "purchase_price": price}


class TestBuildBatches(unittest.TestCase):
    def test_groups_by_supplier_and_warehouse(self):
        lines = [
            line("O1", 101, 7, "X-1", 1),
            line("O2", 101, 7, "X-1", 2),     # same key+sku → qty sums to 3
            line("O3", 101, 9, "X-1", 1),     # same supplier, diff warehouse → separate
            line("O4", 202, 7, "Y-1", 1),     # diff supplier
        ]
        batches = build_batches(lines)
        self.assertEqual(set(batches.keys()), {(101, 7), (101, 9), (202, 7)})
        b = batches[(101, 7)]
        self.assertEqual(sorted(b["order_nos"]), ["O1", "O2"])
        self.assertEqual(b["items"]["X-1"]["qty"], 3)

    def test_dedupes_order_numbers(self):
        lines = [line("O1", 1, 1, "A", 1), line("O1", 1, 1, "B", 1)]
        self.assertEqual(build_batches(lines)[(1, 1)]["order_nos"], ["O1"])

    def test_carries_sku_id_and_price(self):
        batches = build_batches([line("O1", 1, 1, "A-1", 2, sku_id=55, price=12)])
        item = batches[(1, 1)]["items"]["A-1"]
        self.assertEqual(item["sku_id"], 55)
        self.assertEqual(item["purchase_price"], 12)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_batching_build.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_batches'`

- [ ] **Step 3: Write minimal implementation**

Append to `modules/order_processing/batching.py`:
```python
def build_batches(resolved_lines: list[dict]) -> dict[tuple[int, int], dict]:
    """把已解析供應商的行項目組成採購批次，鍵為 (supplier_id, warehouse_id)。

    每行需含 supplier_id, warehouse_id, var_sku, quantity，可選 sku_id, purchase_price。
    同 (供應商, 倉庫) 下，相同 var_sku 數量加總；order_nos 去重。
    回傳 {(supplier_id, warehouse_id): {"order_nos": [...], "items": {var_sku: {...}}}}。
    """
    batches: dict[tuple[int, int], dict] = {}
    for ln in resolved_lines:
        key = (int(ln["supplier_id"]), int(ln["warehouse_id"]))
        batch = batches.setdefault(key, {"order_nos": [], "items": {}})

        order_no = ln["platform_order_id"]
        if order_no and order_no not in batch["order_nos"]:
            batch["order_nos"].append(order_no)

        sku = ln["var_sku"]
        qty = int(ln["quantity"])
        if sku in batch["items"]:
            batch["items"][sku]["qty"] += qty
        else:
            batch["items"][sku] = {
                "qty": qty,
                "sku_id": ln.get("sku_id"),
                "purchase_price": ln.get("purchase_price", 0),
            }
    return batches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_batching_build.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/batching.py tests/order_processing/test_batching_build.py
git commit -m "feat(order-processing): group resolved lines into supplier+warehouse batches"
```

---

## Task 6: state_view.decide_purchase_actions

Pure decision: for each batch, compare its fingerprint against the saved one and the existing draft's state. Decides create / overwrite / skip / skip_locked.

**Files:**
- Create: `modules/order_processing/state_view.py`
- Test: `tests/order_processing/test_state_view.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_state_view.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing.state_view import decide_purchase_actions, BatchAction


def batch(order_nos, items):
    # items: {var_sku: {"qty", "sku_id", "purchase_price"}}
    return {"order_nos": order_nos, "items": items}


ITEMS = {"X-1": {"qty": 2, "sku_id": None, "purchase_price": 0}}


class TestDecide(unittest.TestCase):
    def test_no_existing_draft_creates(self):
        batches = {(101, 7): batch(["O1"], ITEMS)}
        actions = decide_purchase_actions(batches, existing_draft_by_key={}, saved_fingerprints={})
        self.assertEqual(len(actions), 1)
        a = actions[0]
        self.assertIsInstance(a, BatchAction)
        self.assertEqual(a.action, "create")
        self.assertEqual((a.supplier_id, a.warehouse_id), (101, 7))
        self.assertIsNone(a.existing_purchase_id)

    def test_unchanged_fingerprint_skips(self):
        batches = {(101, 7): batch(["O1"], ITEMS)}
        # pre-compute the fingerprint the same way the code will
        from modules.order_processing.fingerprint import compute_fingerprint
        fp = compute_fingerprint(101, 7, ["O1"], [{"sku": "X-1", "qty": 2}])
        actions = decide_purchase_actions(
            batches,
            existing_draft_by_key={(101, 7): {"purchase_id": 900, "state": 0}},
            saved_fingerprints={(101, 7): fp},
        )
        self.assertEqual(actions[0].action, "skip")

    def test_changed_fingerprint_overwrites(self):
        batches = {(101, 7): batch(["O1", "O2"], ITEMS)}   # extra order vs saved
        from modules.order_processing.fingerprint import compute_fingerprint
        stale = compute_fingerprint(101, 7, ["O1"], [{"sku": "X-1", "qty": 2}])
        actions = decide_purchase_actions(
            batches,
            existing_draft_by_key={(101, 7): {"purchase_id": 900, "state": 0}},
            saved_fingerprints={(101, 7): stale},
        )
        self.assertEqual(actions[0].action, "overwrite")
        self.assertEqual(actions[0].existing_purchase_id, 900)

    def test_locked_draft_skips_locked(self):
        # state != 0 means already submitted/paid (採購鎖定, ADR 0004 no overwrite)
        batches = {(101, 7): batch(["O1", "O2"], ITEMS)}
        actions = decide_purchase_actions(
            batches,
            existing_draft_by_key={(101, 7): {"purchase_id": 900, "state": 1}},
            saved_fingerprints={(101, 7): "anything"},
        )
        self.assertEqual(actions[0].action, "skip_locked")

    def test_actions_sorted_by_key_for_determinism(self):
        batches = {(202, 7): batch(["O2"], ITEMS), (101, 9): batch(["O1"], ITEMS)}
        actions = decide_purchase_actions(batches, {}, {})
        self.assertEqual([(a.supplier_id, a.warehouse_id) for a in actions],
                         [(101, 9), (202, 7)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_state_view.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.order_processing.state_view'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/order_processing/state_view.py
"""訂單處理狀態的計算視圖（純函式，無 I/O）。

Slice 1 只需採購準備階段的決策：對每個 (供應商, 倉庫) 批次，依指紋與既有草稿
狀態決定 建立 / 覆蓋 / 跳過 / 略過-已鎖定。BigSeller 為庫存/分配/狀態真相來源
（ADR 0010）；本函式不碰 I/O，輸入皆由編排層備好。
"""
from dataclasses import dataclass

from modules.order_processing.fingerprint import compute_fingerprint


@dataclass
class BatchAction:
    supplier_id: int
    warehouse_id: int
    action: str                 # "create" | "overwrite" | "skip" | "skip_locked"
    fingerprint: str
    order_nos: list[str]
    items: dict                 # {var_sku: {"qty", "sku_id", "purchase_price"}}
    existing_purchase_id: int | None


def decide_purchase_actions(
    batches: dict[tuple[int, int], dict],
    existing_draft_by_key: dict[tuple[int, int], dict],
    saved_fingerprints: dict[tuple[int, int], str],
) -> list[BatchAction]:
    """為每個批次決定動作。

    batches: {(supplier, warehouse): {"order_nos", "items"}}
    existing_draft_by_key: {(supplier, warehouse): {"purchase_id", "state"}}
        state==0 為草稿（可覆蓋）；非 0 表示已送出/付款（採購鎖定）。
    saved_fingerprints: {(supplier, warehouse): fingerprint}
    回傳依鍵排序的 BatchAction 清單（決定性輸出）。
    """
    actions: list[BatchAction] = []
    for key in sorted(batches.keys()):
        supplier_id, warehouse_id = key
        batch = batches[key]
        fp_items = [{"sku": sku, "qty": v["qty"]}
                    for sku, v in batch["items"].items()]
        fingerprint = compute_fingerprint(
            supplier_id, warehouse_id, batch["order_nos"], fp_items)

        existing = existing_draft_by_key.get(key)
        if existing is None:
            action, existing_id = "create", None
        elif existing.get("state") != 0:
            action, existing_id = "skip_locked", existing.get("purchase_id")
        elif saved_fingerprints.get(key) == fingerprint:
            action, existing_id = "skip", existing.get("purchase_id")
        else:
            action, existing_id = "overwrite", existing.get("purchase_id")

        actions.append(BatchAction(
            supplier_id=supplier_id, warehouse_id=warehouse_id,
            action=action, fingerprint=fingerprint,
            order_nos=batch["order_nos"], items=batch["items"],
            existing_purchase_id=existing_id,
        ))
    return actions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_state_view.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/state_view.py tests/order_processing/test_state_view.py
git commit -m "feat(order-processing): decide purchase actions (fingerprint-gated)"
```

---

## Task 7: orders.get_out_of_stock_orders

Add the linchpin BigSeller call: out-of-stock orders via `order/new/pageList.json` with `packState:"4"`. Tested by monkeypatching the module's `_fetch_post_json`.

**Files:**
- Modify: `modules/bigseller/orders.py` (add function near `get_shopee_orders`, ~line 262)
- Test: `tests/order_processing/test_get_out_of_stock_orders.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_get_out_of_stock_orders.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.bigseller import orders


class TestGetOutOfStockOrders(unittest.TestCase):
    def tearDown(self):
        # restore patched function if any
        import importlib
        importlib.reload(orders)

    def test_sends_packstate_4_and_parses_rows(self):
        captured = {}

        def fake_post(path, body):
            captured["path"] = path
            captured["body"] = body
            return {"code": 0, "data": {"page": {"rows": [{"platformOrderId": "O1"}]}}}

        orders._fetch_post_json = fake_post
        rows = orders.get_out_of_stock_orders(page=1, page_size=50)

        self.assertEqual(captured["path"], "/api/v1/order/new/pageList.json")
        self.assertEqual(captured["body"]["status"], "new")
        self.assertEqual(captured["body"]["packState"], "4")
        self.assertEqual(captured["body"]["pageNo"], 1)
        self.assertEqual(rows, [{"platformOrderId": "O1"}])

    def test_returns_empty_on_error_code(self):
        orders._fetch_post_json = lambda path, body: {"code": 1, "data": None}
        self.assertEqual(orders.get_out_of_stock_orders(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_get_out_of_stock_orders.py -v`
Expected: FAIL — `AttributeError: module 'modules.bigseller.orders' has no attribute 'get_out_of_stock_orders'`

- [ ] **Step 3: Write minimal implementation**

In `modules/bigseller/orders.py`, add directly after `get_shopee_orders` (after line 276):
```python
def get_out_of_stock_orders(page: int = 1, page_size: int = 50) -> list[dict]:
    """取得缺貨來源訂單（packState=4）。

    對應後台「訂單 → 缺貨」（order/index.htm?status=new&fromSource=outStock）。
    API filter 為 body packState="4"。回傳 data.page.rows。
    """
    resp = _fetch_post_json(
        "/api/v1/order/new/pageList.json",
        {"status": "new", "packState": "4", "pageNo": page, "pageSize": page_size},
    )
    if not resp or resp.get("code") != 0:
        return []
    data = resp.get("data") or {}
    page_data = data.get("page") or {}
    return page_data.get("rows") or data.get("rows") or data.get("list") or []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_get_out_of_stock_orders.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/bigseller/orders.py tests/order_processing/test_get_out_of_stock_orders.py
git commit -m "feat(bigseller): get_out_of_stock_orders via packState=4"
```

---

## Task 8: prepare_purchase orchestrator (dry-run + commit)

Glue: fetch out-of-stock orders → resolve supplier per line (reuse existing helpers) → build batches → decide actions → print dry-run plan or, with commit=True, create/overwrite drafts and persist fingerprints. Tested by injecting fakes for all BigSeller calls (no network).

**Files:**
- Create: `modules/order_processing/prepare_purchase.py`
- Test: `tests/order_processing/test_prepare_purchase.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_prepare_purchase.py
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing import prepare_purchase as pp
from modules.order_processing.store import FingerprintStore


class FakeDeps:
    """注入 prepare_purchase 的 BigSeller 邊界，避免網路。"""
    def __init__(self):
        self.created = []
        self.deleted = []

    def get_out_of_stock_orders(self):
        return [{
            "platformOrderId": "O1", "warehouseId": 7,
            "orderItemList": [
                {"itemSku": "A", "varSku": "A-红", "quantity": 2, "skuId": 55},
            ],
        }]

    def resolve_supplier(self, line):
        # A-红 → supplier 101, price 12
        return {"supplier_id": 101, "purchase_price": 12}

    def list_existing_drafts_by_key(self):
        return {}                     # no existing drafts

    def create_draft(self, supplier_id, warehouse_id, note, items):
        self.created.append((supplier_id, warehouse_id, note, items))
        return {"id": 9001}

    def delete_draft(self, purchase_id):
        self.deleted.append(purchase_id)
        return True


class TestPreparePurchase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = FingerprintStore(os.path.join(self.tmp, "t.db"))
        self.deps = FakeDeps()

    def test_dry_run_creates_nothing(self):
        result = pp.prepare_purchase(deps=self.deps, store=self.store, commit=False)
        self.assertEqual(self.deps.created, [])
        self.assertEqual(result["planned"], 1)
        self.assertEqual(result["actions"][0]["action"], "create")
        self.assertEqual(self.store.get_all(), {})

    def test_commit_creates_draft_and_persists_fingerprint(self):
        result = pp.prepare_purchase(deps=self.deps, store=self.store, commit=True)
        self.assertEqual(len(self.deps.created), 1)
        supplier_id, warehouse_id, note, items = self.deps.created[0]
        self.assertEqual((supplier_id, warehouse_id), (101, 7))
        self.assertEqual(note, "O1")
        self.assertIn((101, 7), self.store.get_all())
        self.assertEqual(self.store.get_all()[(101, 7)]["purchase_id"], 9001)
        self.assertEqual(result["created"], 1)

    def test_commit_twice_second_run_skips_unchanged(self):
        pp.prepare_purchase(deps=self.deps, store=self.store, commit=True)
        # second run: same demand, but now an existing draft is reported
        self.deps.list_existing_drafts_by_key = lambda: {(101, 7): {"purchase_id": 9001, "state": 0}}
        result = pp.prepare_purchase(deps=self.deps, store=self.store, commit=True)
        self.assertEqual(len(self.deps.created), 1)            # no new create
        self.assertEqual(result["actions"][0]["action"], "skip")

    def test_unresolved_supplier_is_reported_not_swallowed(self):
        self.deps.resolve_supplier = lambda line: None
        result = pp.prepare_purchase(deps=self.deps, store=self.store, commit=True)
        self.assertEqual(self.deps.created, [])
        self.assertEqual(result["unresolved"], ["O1"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_prepare_purchase.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.order_processing.prepare_purchase'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/order_processing/prepare_purchase.py
"""prepare-purchase 編排：缺貨來源訂單 → 採購批次 → 建立/覆蓋 1688 草稿。

訂單驅動採購（ADR 0012），批次以 (供應商, 倉庫) 為鍵（ADR 0011/多倉）。
所有 BigSeller 邊界透過 deps 注入，方便測試；正式執行用 BigSellerDeps。
"""
from modules.order_processing.batching import build_batches, extract_order_lines
from modules.order_processing.state_view import decide_purchase_actions


def prepare_purchase(deps, store, commit: bool = False) -> dict:
    """執行採購準備。commit=False 為 dry-run（預設），只回報計畫不動 BigSeller。

    deps 需提供：get_out_of_stock_orders(), resolve_supplier(line),
    list_existing_drafts_by_key(), create_draft(...), delete_draft(id)。
    store 為 FingerprintStore。
    """
    # 1. 抓缺貨來源訂單並攤平行項目
    orders = deps.get_out_of_stock_orders()
    raw_lines: list[dict] = []
    for order in orders:
        raw_lines.extend(extract_order_lines(order))

    # 2. 逐行解析供應商（I/O，注入）；解析不到的訂單記下、不靜默吞掉
    resolved: list[dict] = []
    unresolved_orders: list[str] = []
    for ln in raw_lines:
        info = deps.resolve_supplier(ln)
        if not info or not info.get("supplier_id"):
            if ln["platform_order_id"] not in unresolved_orders:
                unresolved_orders.append(ln["platform_order_id"])
            continue
        resolved.append({
            **ln,
            "supplier_id": int(info["supplier_id"]),
            "purchase_price": info.get("purchase_price", 0),
        })

    # 3. 組批次 → 決定動作
    batches = build_batches(resolved)
    existing = deps.list_existing_drafts_by_key()
    saved = {k: v["fingerprint"] for k, v in store.get_all().items()}
    actions = decide_purchase_actions(batches, existing, saved)

    # 4. dry-run 預覽 / commit 執行
    created = overwritten = skipped = 0
    action_log: list[dict] = []
    for a in actions:
        note = ",".join(a.order_nos)
        items = [
            {"skuId": v.get("sku_id"), "purchaseQty": v["qty"],
             "purchasePrice": v.get("purchase_price", 0), "varSku": sku}
            for sku, v in a.items.items()
        ]
        action_log.append({
            "supplier_id": a.supplier_id, "warehouse_id": a.warehouse_id,
            "action": a.action, "note": note, "items": len(items),
        })

        if not commit or a.action in ("skip", "skip_locked"):
            if a.action in ("skip", "skip_locked"):
                skipped += 1
            continue

        if a.action == "overwrite" and a.existing_purchase_id is not None:
            deps.delete_draft(a.existing_purchase_id)
            overwritten += 1
        draft = deps.create_draft(a.supplier_id, a.warehouse_id, note, items)
        if not draft:
            continue
        if a.action == "create":
            created += 1
        store.upsert(a.supplier_id, a.warehouse_id, a.fingerprint, draft.get("id"))

    return {
        "planned": len(actions),
        "created": created,
        "overwritten": overwritten,
        "skipped": skipped,
        "unresolved": unresolved_orders,
        "actions": action_log,
        "dry_run": not commit,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_prepare_purchase.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/order_processing/prepare_purchase.py tests/order_processing/test_prepare_purchase.py
git commit -m "feat(order-processing): prepare-purchase orchestrator (dry-run/commit)"
```

---

## Task 9: BigSellerDeps + CLI wiring

Provide the real `deps` (wiring existing BigSeller functions) and the `orders prepare-purchase` CLI command. Supplier resolution reuses `get_sku_supplier_mapping` + `_search_supplier_by_var_sku` from `auto_purchase`.

**Files:**
- Modify: `modules/order_processing/prepare_purchase.py` (add `BigSellerDeps`)
- Modify: `main.py` (add `orders` subparser group + `cmd_orders_prepare_purchase`)
- Test: `tests/order_processing/test_bigseller_deps.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/order_processing/test_bigseller_deps.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.order_processing.prepare_purchase import BigSellerDeps


class TestBigSellerDeps(unittest.TestCase):
    def test_resolve_supplier_uses_sku_map_then_fallback(self):
        deps = BigSellerDeps(
            sku_supplier_map={55: {"supplier_id": 101, "purchase_price": 12}},
            var_sku_resolver=lambda var_sku: {"supplier_id": 202, "purchase_price": 5},
        )
        # sku_id hit
        self.assertEqual(
            deps.resolve_supplier({"sku_id": 55, "var_sku": "A-1"})["supplier_id"], 101)
        # sku_id miss → var_sku fallback
        self.assertEqual(
            deps.resolve_supplier({"sku_id": None, "var_sku": "B-1"})["supplier_id"], 202)

    def test_list_existing_drafts_groups_by_supplier_warehouse(self):
        deps = BigSellerDeps(
            sku_supplier_map={},
            var_sku_resolver=lambda v: None,
            draft_list=[{"id": 9, "supplierId": 101, "warehouseId": 7, "state": 0}],
        )
        got = deps.list_existing_drafts_by_key()
        self.assertEqual(got[(101, 7)], {"purchase_id": 9, "state": 0})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_bigseller_deps.py -v`
Expected: FAIL — `ImportError: cannot import name 'BigSellerDeps'`

- [ ] **Step 3: Write minimal implementation**

Append to `modules/order_processing/prepare_purchase.py`:
```python
class BigSellerDeps:
    """正式執行用的 BigSeller 邊界。可注入既有資料以利測試。"""

    def __init__(self, sku_supplier_map=None, var_sku_resolver=None,
                 draft_list=None):
        self._sku_map = sku_supplier_map
        self._var_resolver = var_sku_resolver
        self._draft_list = draft_list

    # ── lazy 載入既有 BigSeller 函式（測試時用注入值，不觸發網路）──
    def _sku_supplier_mapping(self):
        if self._sku_map is None:
            from modules.bigseller.orders import get_sku_supplier_mapping
            self._sku_map = get_sku_supplier_mapping()
        return self._sku_map

    def _resolve_by_var_sku(self, var_sku):
        if self._var_resolver is not None:
            return self._var_resolver(var_sku)
        from modules.bigseller.auto_purchase import _search_supplier_by_var_sku
        return _search_supplier_by_var_sku(var_sku)

    def get_out_of_stock_orders(self):
        from modules.bigseller.orders import get_out_of_stock_orders
        all_rows, page = [], 1
        while True:
            rows = get_out_of_stock_orders(page=page, page_size=50)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 50:
                break
            page += 1
        return all_rows

    def resolve_supplier(self, line):
        sku_id = line.get("sku_id")
        if sku_id is not None:
            info = self._sku_supplier_mapping().get(int(sku_id))
            if info and info.get("supplier_id"):
                return info
        return self._resolve_by_var_sku(line.get("var_sku") or "")

    def _drafts(self):
        if self._draft_list is None:
            from modules.bigseller.orders import get_purchase_list
            self._draft_list = get_purchase_list(state=0, page_size=500)
        return self._draft_list

    def list_existing_drafts_by_key(self):
        result = {}
        for d in self._drafts():
            sid, wid = d.get("supplierId"), d.get("warehouseId")
            if sid is None or wid is None:
                continue
            result[(int(sid), int(wid))] = {
                "purchase_id": d.get("id"),
                "state": d.get("state", 0),
            }
        return result

    def create_draft(self, supplier_id, warehouse_id, note, items):
        from modules.bigseller.orders import create_purchase_draft
        return create_purchase_draft(
            supplier_id=supplier_id, warehouse_id=warehouse_id,
            note=note, items=items)

    def delete_draft(self, purchase_id):
        from modules.bigseller.orders import delete_purchase
        return delete_purchase(purchase_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/opt/homebrew/bin/python3.13 tests/order_processing/test_bigseller_deps.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Wire the CLI command in `main.py`**

Add the command function next to `cmd_bs_auto_purchase` (after line 263):
```python
@_safe
def cmd_orders_prepare_purchase(args):
    """採購準備：缺貨來源訂單 → (供應商,倉庫) 採購批次 → 建立/覆蓋 1688 草稿。"""
    from config import ORDER_PROCESSING_DB
    from modules.order_processing.prepare_purchase import prepare_purchase, BigSellerDeps
    from modules.order_processing.store import FingerprintStore

    result = prepare_purchase(
        deps=BigSellerDeps(),
        store=FingerprintStore(ORDER_PROCESSING_DB),
        commit=args.commit,
    )
    mode = "LIVE" if args.commit else "DRY-RUN"
    print(f"[{mode}] 計畫 {result['planned']} 批 / "
          f"建立 {result['created']} / 覆蓋 {result['overwritten']} / "
          f"跳過 {result['skipped']}")
    for a in result["actions"]:
        print(f"  • 供應商 {a['supplier_id']} 倉 {a['warehouse_id']}: "
              f"{a['action']} note={a['note']} items={a['items']}")
    if result["unresolved"]:
        print(f"  ⚠️ 無法解析供應商: {', '.join(result['unresolved'])}")
    if not args.commit:
        print("（dry-run；加 --commit 才實際建立草稿）")
```

Add the subparser. Find where `bs_sub` is created (search `add_subparsers`) and add a sibling `orders` group near the `auto-purchase` parser (~line 916). Use the SAME top-level subparsers object that `bs` is registered on (it is the variable returned by the top-level `add_subparsers(...)`; in this file that object is used to build `bs`). Add:
```python
    # ── orders（新架構訂單處理命令）──
    orders_parser = subparsers.add_parser("orders", help="訂單處理（採購準備/貨運履約）")
    orders_sub = orders_parser.add_subparsers(dest="orders_cmd")

    pp_parser = orders_sub.add_parser(
        "prepare-purchase",
        help="採購準備：缺貨訂單 → 採購批次 → 1688 草稿（預設 dry-run）")
    pp_parser.add_argument("--commit", action="store_true",
                           help="實際建立/覆蓋草稿（預設只預覽）")
    pp_parser.set_defaults(func=cmd_orders_prepare_purchase)
```
NOTE: replace `subparsers` with the actual variable name used for the top-level `add_subparsers()` in `main.py`. Confirm by reading `main.py` around the `add_subparsers(` call before editing.

- [ ] **Step 6: Verify CLI is wired (dry-run smoke)**

Run: `/opt/homebrew/bin/python3.13 main.py orders prepare-purchase --help`
Expected: help text shows `--commit`. (A full dry-run needs a logged-in BigSeller session; run manually when available.)

- [ ] **Step 7: Commit**

```bash
git add modules/order_processing/prepare_purchase.py main.py tests/order_processing/test_bigseller_deps.py
git commit -m "feat(order-processing): BigSeller deps + 'orders prepare-purchase' CLI"
```

---

## Task 10: Rewrite ADR 0001 to the thin store (T1)

Doc-only: ADR 0001 currently describes a full order-processing SQLite store. Narrow it to the thin store decided this session.

**Files:**
- Modify: `docs/adr/0001-local-sqlite-order-processing-store.md`

- [ ] **Step 1: Read the current ADR 0001 and rewrite its body**

Read `docs/adr/0001-local-sqlite-order-processing-store.md`. Prepend a status note and update the body so it states: the local SQLite store is a **thin store** (T1) that persists ONLY what BigSeller does not model — Slice 1: purchase-batch fingerprints; later slices add block-resolution decisions and retry metadata. Order-processing state is a **computed view** derived from BigSeller signals + local decisions, NOT a mirrored table (cross-reference ADR 0010). Keep the original "replaceable Store interface" decision; remove any claim that the store mirrors per-order inventory or full state-machine rows.

Add at the top of the file:
```markdown
> **更新（2026-06-16）：薄 store（T1）。** 本地 SQLite 只存 BigSeller 不模型化的東西——Slice 1 為採購批次指紋，後續 slice 加阻塞處置決定與重試 metadata。訂單處理狀態是計算視圖（BigSeller 訊號 + 本地決定），不鏡像 BigSeller 的庫存/分配/狀態（見 ADR 0010）。可替換 Store 介面的決定維持不變。
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/0001-local-sqlite-order-processing-store.md
git commit -m "docs(adr-0001): narrow local store to thin store (T1)"
```

---

## Final verification

- [ ] **Run the whole order_processing test suite**

```bash
for f in tests/order_processing/test_*.py; do
  echo "== $f =="; /opt/homebrew/bin/python3.13 "$f" || exit 1
done
echo "ALL ORDER_PROCESSING TESTS PASSED"
```
Expected: every file reports OK; final line prints.

- [ ] **Confirm no regression in existing imports**

```bash
/opt/homebrew/bin/python3.13 -c "import main; import modules.bigseller.orders; import modules.bigseller.auto_purchase; print('imports OK')"
```
Expected: `imports OK`

---

## Self-review notes (spec coverage)

- 薄 store（指紋表）→ Task 1, 3 ✓
- 狀態視圖純函式 → Task 6 ✓
- 缺貨來源訂單（packState=4）→ Task 7 ✓
- (供應商, 倉庫) 批次 → Task 5 ✓
- 採購批次指紋 / 採購覆蓋偵測 → Task 2, 6 ✓
- dry-run 預設 + `--commit` → Task 8, 9 ✓
- 供應商解析沿用既有 fallback → Task 9 ✓
- 無法採購明確標示、不靜默吞 → Task 8 (`unresolved`) ✓
- `orders prepare-purchase` 命令（ADR 0005）→ Task 9 ✓
- ADR 0001 改寫 → Task 10 ✓

**Out of scope (later slices):** fulfill-shipping (Slice 2); blocked + 阻塞處置 (Slice 3); purchase submit/payment lock flow beyond draft create/overwrite; confirm-receiving for keep_in_stock.
