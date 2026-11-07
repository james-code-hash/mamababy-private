# Order Processing Slice 2: 貨運履約與貨憨憨 WMS 同步

## Scope

Slice 2 implements `orders fulfill-shipping`: the second half of 訂單處理 after 1688 採購已有貨運編號. It reconciles BigSeller 採購單映射 with 貨憨憨 WMS 待打包訂單, groups source orders by shared 1688 tracking number, submits each ready group to the forwarder, and records per-source-order submission results for idempotent reruns.

Out of scope: blocked order resolution, keep-in-stock receiving, BigSeller inventory mirroring, and replacing the older `fulfill run` command.

## Domain Decisions

- BigSeller remains the source of truth for purchase state, tracking number, order allocation, and inventory.
- 貨憨憨 WMS sync means reading forwarder pending orders and submitting ready source orders, not mirroring warehouse inventory into local state.
- Submission state is stored per 來源訂單, not per tracking number. This preserves rerun safety when one shared tracking number contains several source orders and only some are currently present in the forwarder WMS.
- Missing forwarder pending orders are reported as `missing_in_forwarder`, not treated as submission errors. A later rerun can pick them up once the WMS has synced them.

## Flow

1. Read BigSeller purchase-order mapping from existing `build_purchase_order_mapping()`.
2. Keep only purchase mappings with `state == 1` and a non-empty `tracking_no`.
3. Skip source orders already marked `submitted` in `forwarder_submission`.
4. Read 貨憨憨 pending orders and keep only source orders currently present there.
5. Group ready source orders by 1688 `tracking_no`.
6. Select a forwarder transport by keyword, defaulting to `海快`, with first-channel fallback.
7. In dry-run mode, report planned groups only.
8. In commit mode, call provider `place_order()` and record each source order as `submitted` or `failed`.

## Files

- `modules/order_processing/fulfill_shipping.py` owns the Slice 2 orchestration.
- `modules/order_processing/fulfillment_types.py` owns DTOs and boundary protocols.
- `modules/order_processing/forwarder_store.py` owns the local forwarder submission table.
- `main.py` wires `orders fulfill-shipping`.
- `CONTEXT.md` adds the resolved glossary terms `貨代待打包訂單` and `貨代提交紀錄`.
