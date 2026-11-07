# Order Processing Slice 3: Blocked 與阻塞處置模組

## Scope

Slice 3 implements the human-in-the-loop **阻塞處置** (blocked order handling) mechanism and **採購鎖定後取消** detection. It blocks cancelled source orders after purchase locking from being automatically shipped, provides SQLite storage for tracking blocked and resolved states, offers explicit CLI commands for operator decisions, and integrates with BigSeller's native confirm-receiving workflow for inventory sync.

### In Scope
- Automatic detection of "canceled post lock" orders during `fulfill-shipping` and marking them as `blocked`.
- A new `blocked_order_record` SQLite table to store blocked/resolved states, resolution action, reasons, operator, and notes.
- A new CLI command `mamababy orders list-blocked` to display all currently blocked orders.
- A new CLI command `mamababy orders resolve-block <order_id>` to apply manual resolutions:
  - `resume_shipping`: Unblocks and allows the order to be re-run in `fulfill-shipping`.
  - `keep_in_stock`: Triggers BigSeller's Confirm Receiving API to move the purchase state to 3 (Completed) to update BigSeller native WMS stock, then unblocks.
  - `reassign_order`: Re-routes the 1688 tracking number to a new active Shopee order and registers it in `forwarder_submission`.
  - `return_to_supplier` & `mark_done`: Resolves the block with descriptive record for manual/off-line tracking.

### Out of Scope
- Automatic automated chat-bot notifications (keeps CLI-driven).
- Complicated auto-matching for reassignment (requires explicit target order parameter).

## Domain Decisions

- **Canceled Post Lock Safety**: Any source order whose BigSeller purchase order is already paid/on-the-way (`state=1`) but is now canceled in Shopee/BigSeller must be blocked. Automatically submitting such orders to the forwarder is forbidden.
- **Thin Store Compliance**: For `keep_in_stock` (留庫存), the local system does not maintain a physical stock ledger. Instead, it calls the BigSeller API to confirm receipt of the purchase order, which triggers BigSeller's native WMS to increase inventory and push stock, keeping local state devoid of duplicates.
- **Reassignment Routing**: Reassigning a package (`reassign_order`) maps the existing 1688 `tracking_no` to the new `to_platform_order_id` in `forwarder_submission`, immediately executing a 1-key packing request to Huohanhan under the new order Sn.

## Flows

### 1. Cancellation & Block Detection Flow (during `fulfill-shipping`)
```
[Candidate Source Orders]
          │
          ▼
[Check BS Cancel List (recently_canceled_set)] ───► If canceled ──► [Write to blocked_order_record]
          │                                                                      │
          ▼ (If not in recent list)                                              ▼
[Verify details via get_shopee_order_detail()] ◄───────────────────► [Skip in fulfill-shipping]
```

### 2. Resolution Flow (`orders resolve-block`)
```
                       [resolve-block]
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
     [resume_shipping]  [keep_in_stock]  [reassign_order]
             │                │                │
      (Mark resolved)         │          (Place order with)
             │                ▼          (new orderSn & key)
             │        [BS Confirm Recv]        │
             │                │                ▼
             │                ▼         (Write to forwarder)
             └───────────────►┴◄───────────────┘
                              │
                              ▼
                     (Mark resolved in DB)
```

## Files

- `modules/order_processing/blocked_store.py`: SQLite operations for `blocked_order_record`.
- `modules/order_processing/blocked_handling.py`: Core logic for block detection, listing, and resolution.
- `main.py`: Registers `orders list-blocked` and `orders resolve-block` CLI commands.
