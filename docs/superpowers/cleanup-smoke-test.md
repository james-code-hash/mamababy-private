# Cleanup PR #12 — read-only smoke test

Every command below is read-only against the live BigSeller account: no `--commit`,
no `--apply`, no offline/reprice/image writes. Local report files are the only output.

Run from the repo root with `.env` present and a valid `~/.bigseller_cookies.json`
(`uv run python main.py bs login` if expired).

Pick a live product whose `itemSku` is a 1688 offer ID:

```bash
uv run python main.py bs product list --limit 5 --json
```

| # | Tool | Command | Pass criteria |
|---|------|---------|---------------|
| 1 | update-from-1688 | `uv run python main.py bs product update-from-1688 <id> https://detail.1688.com/offer/<itemSku>.html` | Prints dry-run preview, exit 0, nothing saved. Every `variations[].variationSku` equals the current BS value (no `{itemSku}-{name}` rename). `images` are real 1688 URLs, at most 9, none invented (no made-up size chart). If the LLM fails, `llm_error` is set, description/attributes are empty, and the title is not replaced by simplified 1688 text. |
| 2 | update-from-codex | `uv run python main.py bs product update-from-codex <id> <1688 url>` | Same as #1; Codex output goes to `data/localized_images/` only. |
| 3 | reprice-all | `uv run python main.py bs product reprice-all --limit 5 --output /tmp/reprice_smoke.json` | Runs without `--market-report` (no stale `price_audit_20260822.json` lookup), writes the preview report, exit 0, no write (no `--apply`). |
| 4 | optimize-one | `uv run python main.py bs product optimize-one 1` (bad ID) and `... optimize-one <id>` | Bad ID exits non-zero with `讀取商品失敗`; good ID prints analysis, no write (no `--apply`). |
| 5 | price_audit.py | `uv run python scripts/price_audit.py --output /tmp/price_audit_smoke.json` | Writes the given path (default `reports/price_audit_<today>.json`), failed lookups appear in the report with a `❓` verdict, no crash on missing band. |
| 6 | scan_simplified_chinese_images.py | `uv run python scripts/scan_simplified_chinese_images.py` | Without tesseract or `chi_sim`/`chi_tra`: exits immediately with an install hint. With them: scans and writes `/tmp/bs_img_scan/simplified_report.*`. |
| 7 | cleanup_unbound_skus.py | `uv run python scripts/cleanup_unbound_skus.py` | Default is preview: prints `預覽模式`, report file ends in `_dryrun.json`, no offline/zero calls. |

## Results (owner's machine, 2026-10-23)

Local `.env` has no `LLM_API_KEY`, so every LLM step ran its failure path.

| # | Result |
|---|--------|
| 1 | **Failed, then fixed.** The DOM scraper no longer matched current 1688 pages: on a delisted offer it built a preview anyway (title `...亲子装潮-阿里巴巴`, no images, weight 0.5 kg default); on a live offer it took the shop name as title, 22 identical spec names and no prices. BigSeller variations have no `name` field (specs are `option1`/`option2`, price is `originalPrice`), so nothing matched. Fixed in `8b760a1`: reads 1688's structured page data via `sku_binding.fetch_1688_page_data` (curl, no browser), rejects unpublished offers. Re-run on product 876250768 / offer 827519898526: 48 of 54 specs matched and repriced, 6 unmatched kept their price, all `variationSku` unchanged, BS title kept (LLM failed), 5 real 1688 images, weight untouched. Delisted offers 988805223565 / 1045723696589 / 973312739111 now fail with an error. |
| 2 | **Failed, then fixed.** Imported `config.BS_1688_URL`, which does not exist (ImportError on every run). After `8b760a1`: exit 0, Codex wrote `data/localized_images/product_876250768_codex_optimized.jpg`, nothing saved. |
| 3 | Pass. `--crawl-db` must point at the main checkout's `data/bigseller_crawl_prices.db` when run from a worktree. 5 products / 356 variants previewed, market reference `market_unavailable`, `apply.status = dry_run`. Costs come from the crawl DB, so a delisted offer (1045723696589) is still priced. |
| 4 | Pass for exit codes (bad ID exits 1 with `讀取商品失敗`). Preview on 1014027667 put the raw Shopee extended-description JSON into `【原始商品資訊】`; fixed in `da41151` (text fields only). |
| 5 | Ran: all 22 keyword lookups failed (`路由 keyword 無有效 token`); all 62 products are in the report with `❓知蝦關鍵詞查詢失敗`, written to the `--output` path, no crash. `zhixia capture` could not fix it: the saved zhixia admin token is ~67 days old and the 9222 Chrome is not logged in to zhixia, so captured route tokens carry no auth (401). Needs `zhixia login` by the owner; real market data not verified. |
| 6 | Without tesseract: exits 1 with the install hint. After `brew install tesseract tesseract-lang`: three bugs found and fixed. (a) Non-UTF-8 tesseract stderr crashed the run (`3a988ed`). (b) On macOS Leptonica rewrites `/tmp/...` paths, so every cached image was "not found" and all 517 images came out text-free (`12529ac`). (c) With only `chi_sim`, traditional text is read as simplified (`發聲耐咬` → `发声耐咬`), flagging 224/517 images in all 62 products; now one `chi_tra+chi_sim` pass and simplified characters only count inside 3+ character runs (`6010b23`). Re-checked offline on the 517 cached live images: 32 images in 25 products flagged, mostly real simplified copy (`智慧测温`, `儿童尺码`, `多图可选`). The end-to-end rerun stopped at the product list because the BigSeller cookie expired (code 2001). |
| 7 | Pass. Preview only: would offline 1 product and zero specs on 16, report `_dryrun.json`, nothing written. |

`host_image`: 62 live listings scanned, none has an `api.telegram.org` image URL. Owner chose the minimal fix (`c36cf50`): token redacted from errors, and `apply_images` fails without echoing the URL if BigSeller did not rehost a Telegram image. Rotate the bot token, since earlier `image-optimize --apply` runs already sent it to BigSeller.
