# SDD ledger — plan: docs/superpowers/plans/2026-10-22-order-to-forwarder-automation.md

Spec: docs/superpowers/specs/2026-10-22-order-to-forwarder-automation-design.md (approved 2026-10-22)
Branch: feat/order-cycle (created from main 1555afc in the main checkout; no other session uses this checkout — listing-flow runs in its own worktree)
Ruling: work on branch feat/order-cycle in main checkout instead of a new worktree — spec/plan were uncommitted here and the .venv lives here; listing-flow session is isolated in its own worktree — cost if wrong: a stray edit lands on this branch, easy to revert.

## Preflight scan

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T2 ↔ T7 (forwarder store) | T2 changes `record_submitted/record_failed` to `tracking_nos: list[str]`; T7 rewrites fulfill_shipping | T2 must adapt existing callers minimally (`[tracking_no]`) so suite stays green; T7 then uses lists natively |
| T2 ↔ T8 (blocked store) | T2 test calls `record_blocked("O1", 7, ["T1"], "canceled", stage=...)`; Interfaces text says "同現有方法 + stage" | Inconsistent tracking param type → ruling below |
| T2 ↔ T6 (main.py wiring) | T2 wires Firestore stores into `cmd_orders_*`; T6 adds `ledger` param to `prepare_purchase` | T6 must update `cmd_orders_prepare_purchase` to pass ledger |
| T4 ↔ T6 | T4 strict reads; T6 rewrites `list_existing_drafts_by_key` | T6 keeps strict `get_purchase_list` |
| T5 ↔ T6 (prepare_purchase) | both edit prepare_purchase result dict | sequential; T6 keeps T5 keys (`excluded_orders`, `planned_*`) |
| T7 ↔ T8 (fulfill_shipping) | T7 multi-purchase mapping; T8 removes embedded detection, adds `blocked_ids` | sequential, no conflict |
| T7 ↔ blocked_handling | T7 changes `place_forwarder_order(pending_order, goods_tracking)`; `BlockedHandlingDeps.place_forwarder_order` + `reassign_order` | T7 brief already covers reassign; must also update BlockedHandlingDeps protocol signature |
| T6 ↔ T8 ↔ T9 | payment status from T6 (`get_purchase_payment_status`) used by T8 `get_purchase` and T9 `refresh_payments` | consistent |
| T1 gate ↔ T6/T8/T9 | gate failure blocks T6; T8/T9 need payment status too | ruling below |
| T1 self | research only, fixtures + notes | ok |
| T2 self | adds opencc dependency (not in spec) | ruling below |
| T3 self | test `_log` private access | acceptable in test |
| T4 self | ok |
| T5 self | ok |
| T6 self | iteration keys must include keys with owned unpaid purchases even when absent from batches (noted in plan) | ok |
| T7 self | goods sku field name from T1 | carry T1 result |
| T8 self | ok |
| T9 self | `test_cycle_slack_failure_exit_nonzero` needs CLI-level test | ok |
| T10 self | deletes test_cron_routes.py only if it tests old cron only | implementer checks |

Ruling: `record_blocked(platform_order_id: str, purchase_id: int, tracking_nos: list[str], block_reason: str, *, stage: str)` — the test in T2 is the concrete spec and per-item multi-tracking (spec) needs lists — cost if wrong: small signature churn in T8.
Ruling: if T1 gate trips (no payment status or no cancel-unpaid method), finish T2–T5 and T7, then stop and ask the user before T6/T8/T9 — spec says "停下來回報業主" and T8/T9 depend on payment status — cost if wrong: idle time.
Ruling: keep `opencc-python-reimplemented` in pyproject (T2) — deploy on fresh claw-arm-1 env would otherwise silently fall back to a ~50-char table and block more orders as ambiguous, which breaks the spec's goal — cost if wrong: one extra dependency.

## Progress
Task 1: implementer done a97e457 — GATE TRIPPED (no BS payment field; cancel.json exists but 1688 effect unverified; ALI_1688_AK unset locally). cancelled spelling: frontend 'canceled' (unverified live). huohanhan goods SKU field unverified (0 pending rows; fixture synthetic, assumed modelSku). trackingNo = comma-joined + trackingNoList/trackingVos, no per-item mapping.
Task 1: review — spec ❌ (Important: gate outcome missing from docs/bigseller-api-notes.md). Fix round 1 deferred until Task 2 implementer finishes (same checkout; avoid concurrent git index use).
Task 1: minor (deferred): soften "賣家已發貨 = 必已付款" to 推定 + note proxy cannot detect unpaid
Task 1: minor (deferred): notes don't say whether state 0/5 rows were checked
Task 1: minor (deferred): fixtures keep real creatorUid/purchaserUid 1220326 and commonNo PO157P...; replace with fake
Task 1: minor (deferred): purchase_row_placed.json is state 1 with tracking (not an unpaid sample) — rename/comment
Task 1: minor (deferred): note `bs login` was run in method line
Task 2: implementer done 285b415 (DONE_WITH_CONCERNS: pre-existing pyright errors; no SQLite migration per ADR 0013)
Task 1: fix round 1/5 commit 13bfc67 (gate statement added; AK trade APIs APIUnsupported → gate still tripped)
Task 2: review clean (Approved). ⚠️ dry-run blocked detection writes Firestore (pre-existing; fixed by Task 8 per plan — carry to T8 dispatch).
Task 2: minor (deferred): FirestorePurchaseLedger.mark on missing doc creates partial doc (owned_ids includes it; list_open KeyError) — check exists/use update
Task 2: minor (deferred): blocked_handling reassign `record["tracking_nos"][0]` IndexError if empty
Task 2: complete (commits a97e457..285b415, review clean)
Task 1: re-review round 1 — finding ADDRESSED. minor (deferred): doc overclaims at bigseller-api-notes.md lines 67/101/107 (AK "不可用" vs only tested trade names unsupported; gateway "only skill APIs" is hypothesis)
Task 1: complete (commits 1555afc..13bfc67, review clean; gate TRIPPED — Task 6/8/9 wait for owner)
Task 3: implementer done 094d4c1 (298 passed)
Ruling: SHOPEE_STATUS_CANCELLED = "canceled" — BigSeller frontend sends "canceled" (Task 1 §5); server echoes any value so live data cannot settle it — cost if wrong: cancellation detection keeps missing (status quo), caught when first real cancel is not detected.
Task 3: minor (deferred, relevant to Review Focus #4): send_slack lets subprocess TimeoutExpired/OSError propagate — catch, warn without URL, return False
Task 3: minor (deferred): reminder tests anchored to real clock (monkeypatch firestore_stores._now)
Task 3: minor (deferred): send_slack success path untested; redundant `and last is not None`
Task 3: complete (commits 13bfc67..094d4c1, review clean)
Owner approved (chat, 2026-10-22) read-only test of skills-gateway fx_query_order. Result: POST https://skills-gateway.1688.com/api/fx_query_order/1.0.0 signed with ALI_1688_AK (same x-csk scheme as modules/sourcing/ali1688_api.build_auth_headers) works for BigSeller-placed orders: body {"orderId": aliOrderNo} → data.model.orderList[0] has orderStatus ("success" for a delivered one), payStatus (int, 6), payTime, logisticsStatus. Status map from 1688-distribution skill: waitbuyerpay=等待买家付款, waitsellersend, waitbuyerreceive, success, finish, cancel/cancelled, waitingsellerconfirm. Range query (createStart/End, max 7 days) returned 0 orders (no recent business) — no live unpaid sample.
Ruling: GATE RESOLVED — payment status = fx_query_order orderStatus: "waitbuyerpay" → unpaid; "cancel"/"cancelled" → canceled; any other value → paid; call failure/missing order → unknown (treated as paid) — cost if wrong: an unpaid order is treated as paid and not rebuilt (safe direction) or a paid one with an unexpected status is... treated as paid (safe).
Ruling: cancel-unpaid = BigSeller POST form /api/v1/purchase/manage/cancel.json id=<purchase_id>, then confirm via fx_query_order that the 1688 order status is cancel/cancelled before placing the replacement; not confirmed → treat as cancel failure (no new order, alert) — cost if wrong: rebuild never succeeds and owner gets an alert each cycle until the owner tests cancel once with consent.
Task 4: implementer done 1524cf6 (307 passed)
Task 4: review — Needs fixes: (I1) build_purchase_order_mapping non-strict → fulfill-shipping silently empty; (I2) get_shopee_order_detail non-strict on blocked path (fail-open)
Ruling: Task 4 Important #3 (no Slack alert added) — Slack alerting is Task 9's job (cycle builds error/{step} messages); Task 4 only needs to raise — cost if wrong: none, T9 brief covers it.
Task 4: minor (deferred): unify get_purchase_list(strict) RuntimeError into BigSellerReadError; no later-page failure test; stale "cancelled" fixture in test_blocked_handling
Task 4: fix round 1/5 (commit a0854f8; re-review dispatched)
Task 4: re-review round 1 — both ADDRESSED.
Task 4: minor (deferred, carry to T9): advance_purchase_pipeline get_purchase_list non-strict (orders.py:245,289,301) — cycle step 1 could silently skip; batch_delete_purchases non-strict
Task 4: complete (commits 094d4c1..a0854f8, review clean after 1 fix round)
Task 5: implementer done 1ef52d3 (314 passed)
Task 5: minor (deferred): empty var_sku adds "" to var_skus; dry-run test doesn't assert store untouched; planned_rebuild=0 uncommented (T6 fills it); PLACE-1688 label shown without --commit (pre-existing)
Task 5: complete (commits a0854f8..1ef52d3, review clean)
Ruling: Task 6 puts the 1688 trade query in new file `modules/sourcing/ali1688_trade.py` (reuses ali1688_api signing; base https://skills-gateway.1688.com, path /api/fx_query_order/1.0.0) and keeps `orders.get_purchase_payment_status` as the pure status mapper taking the fx_query_order orderStatus — plan said "純函式 依 Task 1 欄位判斷" but the field lives in 1688, not the BigSeller row — cost if wrong: one module move.
Task 6: implementer dispatched (opus) then STOPPED before any file change for handoff (2026-10-22). Restart Task 6 from scratch with the task-6 brief (plan Task 6) plus the "Ruling:" lines above (gate resolved via skills-gateway fx_query_order; cancel.json + confirmation; ali1688_trade.py placement).
Task 6: resumed in cloud session (2026-10-22), implemented inline (no subagent).
Ruling: `cancel_unpaid_order(purchase_id, ali_order_no)` takes the 1688 order no explicitly (plan: purchase_id only) — confirmation needs it and deps should not depend on a cached list — cost if wrong: one signature change.
Ruling: payment is queried by a separate `PurchaseDeps.get_payment_status(ali_order_no)` called only for owned purchases with aliOrderNo, no tracking, state != 1 (plan put `payment` inside list_existing_drafts_by_key) — avoids one 1688 call per non-owned/in-transit purchase — cost if wrong: none functionally.
Ruling: `find_draft_id_by_note` replaced by `find_purchase_by_note(note, ignore_purchase_ids)` returning {purchase_id, ali_order_no, amount}; requires aliOrderNo and excludes replaced ids (old canceled purchase may share the note) — cost if wrong: placed order not recorded → reported as error, its orders stay locked (no rebuy).
Ruling: cancel confirmation failure marks ledger `cancel_pending` (kept in list_open so its orders stay locked); ledger-open purchases missing from the BigSeller 0/1/5 list are merged back as occupied — prevents rebuy when BigSeller cancel succeeds but 1688 is then paid — cost if wrong: orders stuck locked until owner checks (reported as ledger_missing).
Ruling: unowned purchase without order numbers in note (opaque) → whole key skip_locked (fail-closed, as old place_draft guard) — cost if wrong: supplier blocked until that manual purchase completes.
Ruling: rebuild/cancel of 1688 orders only runs with --place; draft-only commit reports a warning.
Ruling: delete of replaced purchases after cancel is non-fatal (warning); place_draft guard ignores replaced ids.
Task 6: deferred Task 2 minor fixed — FirestorePurchaseLedger.mark on missing doc now raises KeyError.
Task 6: live check of skills-gateway impossible from cloud container (proxy 403 for skills-gateway.1688.com); unit-tested with fake HTTP only.
Task 6: review — Needs fixes: (I1) superseded/canceled purchase still listed in BigSeller treated as rebuildable → rebuild churn cancels newest unpaid each cycle; (I2) order excluded by transient resolve error inside owned unpaid purchase → wrongly rebuilt/canceled; (I3) purchase whose supplier name not in (non-strict) sku map dropped from occupancy → manual purchase orders rebought; (I4) per-key lock/failure lets other supplier keys buy part of the same order (ADR 0011); (I5) cancel_pending + "do not pay" set even when no cancel was sent (paid/unknown pre-check). Minors: fx_query_order orderId not checked; get_purchase_list single page 500; ledger records never leave placed (Task 9 refresh_payments); exact-note match.
Task 7: implemented inline. Ruling: purchase items for goods↔parcel mapping come from the Firestore ledger (PurchaseRecord.items), not BigSeller detail (sku field names in detail unverified, one call per purchase) — non-owned multi-purchase orders go to needs_manual — cost if wrong: more manual parcels.
Ruling: candidate = all non-canceled purchases of the order are state 1 with tracking; orders whose purchases are all finished (3) are not listed as waiting (pre-Firestore history) — cost if wrong: a 3+1 mix waits forever (Task 9 stale alert should catch).
Ruling: fulfill_shipping takes `blocked_ids` now (Task 8 part) and no longer runs embedded cancellation detection; build_purchase_order_mapping paginates all states, skips state 4.
Task 6: fix round 1/5 — I1 ledger-retired purchases ignored (payment "retired"); I2 excluded order inside owned purchase holds key; I3 strict sku map + unmapped non-owned purchases lock their orders globally; I4 fixed-point hold propagation across keys; I5 cancel_unpaid_order returns canceled|paid|unknown|bs_failed|unconfirmed, only unconfirmed → cancel_pending. Minors fixed: fx_query_order other-order guard, _drafts paginated. Deferred: ledger placed→paid refresh (Task 9), exact-note match, runtime failure on one key while another key places part of same order (retried next cycle, temporal only).
Task 6: re-review round 1 — I1–I5 ADDRESSED. New Important (retired draft later placed on 1688 hidden) fixed in round 2 → payment retired_live = occupied + reported. Minors fixed: duplicate-page detection raises; unmapped opaque purchases reported. Deferred: hold propagation is conservative (holds whole key's orders).
Task 8: implemented inline — modules/order_processing/cancellation.py (detect_cancellations + BigSellerCancellationDeps); blocked_handling.detect_and_block_canceled_orders and BlockedHandlingDeps.get_canceled_orders/get_order_detail removed; fulfill-shipping CLI runs detection first (dry-run excludes would-be-blocked orders without writing). Deferred T2 issue (dry-run detection writes Firestore) resolved.
Ruling: detect_cancellations also takes `other_purchases` (non-ledger purchases from the BigSeller mapping) so pre-cutover/manual in-transit orders canceled by the buyer are still blocked (never auto-canceled) — cost if wrong: one extra purchase-list read per cycle.
Ruling: cancel_or_refund_paid_order always returns None (no API per bigseller-api-notes §3) → paid_unshipped always blocks for manual handling.
Task 9: implemented inline — modules/order_processing/cycle.py (run_cycle, build_messages, build_production), `orders cycle [--commit]`, config thresholds (+CANCELLATION_LOOKBACK_DAYS=30). advance_purchase_pipeline reads now strict (carry from T4). send_slack catches TimeoutExpired/OSError without printing the URL (carry from T3).
Ruling: refresh_payments takes the ledger records (needs aliOrderNo) instead of no-arg; also clears cancel_pending → paid/canceled from 1688 status.
Ruling: PurchaseRecord gains optional `replaces` so the pay/{id} text is stable across cycles (dedupe) and still names the canceled old order.
Ruling: "tracking but not in forwarder" stale alert approximated as paid_at + PAID_NO_TRACKING + TRACKING_NOT_IN_FORWARDER hours (no tracking-appeared timestamp available).
Ruling: mapping/cancellation failures also stop the write steps (4, 5): a canceled order must not be sent to the forwarder.

## Local finish (owner's machine, 2026-10-23)

Live read-only checks: fx_query_order works locally; Firestore dry-runs of `orders cycle`/`fulfill-shipping`/`prepare-purchase` pass and write nothing (service account `order-cycle@mamababy-1bf68`, roles/datastore.user, created with owner consent). cancel.json and huohanhan goods SKU field remain unverified (no unpaid 1688 order, 0 pending forwarder orders). Details: docs/bigseller-api-notes.md §7–8.
Fix: huohanhan pending reads swallowed errors as 0 rows → place_order verify reported success for unsubmitted orders; now strict + all pages.
Fix: reassign of a multi-parcel blocked order refused (sent only the first tracking).
Whole-branch review (opus) — Critical: C1 partial tracking forwarded when a needed supplier's purchase is missing; C2 orders bought into another warehouse rebought. Important: I1 partial purchase when one key fails, I2 forwarder failures silent, I3 recurring errors never re-alerted, I4 orders dropping off the out-of-stock list silently removed, I5 placement failure reason/leftover draft, I6 Firestore full scans.
Ruling: C1 — ledger records carry `order_suppliers` (all suppliers each order needs, from resolved lines); forwarding waits until every needed supplier has an in-transit purchase; pre-cutover orders without ledger records keep old behavior — cost if wrong: an order waits (reported as missing-supplier) instead of shipping.
Ruling: C2 — occupancy and opaque locks merge per supplier across warehouses, not globally per order (a manual purchase from supplier A must not block buying supplier B's lines of the same order) — cost if wrong: an opaque old purchase in another warehouse locks that supplier until cleaned up (alerted).
Ruling: I1 — no persisted "incomplete order" state; pay notices warn about orders lacking another supplier's purchase and C1 stops partial forwarding — cost if wrong: owner may pay for half an order, but it is never shipped half and is alerted.
Ruling: I4 — orders removed from an owned unpaid purchase are still removed, with a warning when Shopee status is not canceled (hold-the-key would freeze the supplier indefinitely) — cost if wrong: owner must re-add manually after reading the warning.
Ruling: I6 — per-instance caches (one scan per collection per run) instead of query filters; archiving closed records is a follow-up — cost if wrong: reads grow linearly with history (~12 × docs/day).
Minors fixed: AK misconfig → step failure; run lock; webhook off argv; paid_at on paid cancel outcome; out-of-stock paging dedupe; canceled list page limit raises. Deferred: M7 verify-failure recorded as failed, M8 cutover cancellation noise, M9 unexpected 1688 statuses mapped to paid.
