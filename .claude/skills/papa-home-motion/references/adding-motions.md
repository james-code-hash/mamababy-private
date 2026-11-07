# 加新動作、新套路、新姿勢

寫分鏡不用讀這份。給要擴充動作庫的人（工程師、業主、或製作工作階段缺動作時）。

## 加一個零件動作（只改 JSON，不改程式）

在 `papa_home/assets/papa_home/motion/motions.json` 的 `gestures` 加一筆：

```json
"wave": {
  "label": "揮手", "desc": "靠方向那隻手舉高左右揮三下", "status": "draft",
  "species": ["human", "quadruped", "baby"], "head_shot": false, "needs": ["head", "arm_lead"], "length": 1.3,
  "steps": [
    {"part": "arm_lead", "at": 0, "to": {"rotation": "-110*dir", "duration": 0.22, "ease": "back.out(1.6)"}},
    {"repeat": 3, "every": 0.24, "at": 0.24, "steps": [
      {"part": "arm_lead", "at": 0, "to": {"rotation": "-132*dir", "duration": 0.12, "yoyo": true, "repeat": 1, "ease": "sine.inOut"}}
    ]},
    {"part": "arm_lead", "at": 1.0, "back": 0.3}
  ]
}
```

| 欄位 | 意思 |
|---|---|
| `status` | `draft`＝試用（業主還沒看片），`approved`＝業主看過成片確認。新動作一律先 `draft` |
| `species` | 哪些物種能用（`human`／`quadruped`／`baby`）；測試會檢查這些物種的每個角色至少有一個姿勢做得出來 |
| `head_shot` | 頭像鏡（只有頭）能不能用；只動 `head`／`lids` 的動作才設 true（其他零件在頭像鏡會被略過） |
| `needs` | 一定要有的零件角色；姿勢缺這個零件就不能做（例：`wag_fast` 要 `tail`） |
| `length` | 動作做完要多久（秒），給寫分鏡的人排時間；`holds: true`＝停在最後的樣子直到鏡尾 |
| `steps` | 時間軸，見下 |

step 的寫法（時間都相對於分鏡的 `gesture_at`）：

- `{"part": 角色, "at": 秒, "to": {GSAP 參數}}`：補間到那個值。可用的屬性：`rotation`（度）、`xPercent`／`yPercent`（零件畫布的百分比，1 ≈ 10px）、`x`／`y`（px，只建議用在 `body`）、`scaleX`／`scaleY`、`duration`、`ease`、`yoyo`、`repeat`。
- 加 `"from": {...}` 就變成 fromTo（例：眼皮從 0 開到 1，記得 `"immediateRender": false`）。
- `{"part": 角色, "at": 秒, "back": 秒}`：回到原位（rotation／xPercent／yPercent 歸零，power2.inOut）。
- `{"repeat": n, "every": 秒, "at": 秒, "steps": [...]}`：重複 n 次。
- 值：數字；`"7*dir"`＝乘方向（向右 1、向左 −1，跟 `look_at` 或 `flip`）；`"1.3*alt"`＝重複時正負交替（第 0 次負）；`"+=0.5"`＝相對值。
- 零件角色：`head`、`body`（整隻）、`arm_a`、`arm_b`、`arm_lead`（朝方向那隻）、`tail`、`lids`。旋轉軸心是 rig 的 `pivot`（肩膀、脖子、尾根）。
- 手的旋轉方向：`arm_a` 正值往畫面左外側甩、`arm_b` 負值往右外側甩（聳肩 ±38、歡呼 ±120）；`arm_lead` 指向目標用 `-75*dir`。
- 避免：`body` 的 `scaleY`（會跟自動呼吸打架）、超過 ±130 度的手（零件接縫會露出來）、跟 `idle` 同時長時間改頭的 rotation。
- 大人（`human`）是背影、手是長袖：手轉超過約 ±60 度，肩膀接縫就很明顯，近景時手還會伸出畫框，看起來像一截斷手（2026-11-05 第 2 集實測：爸爸 `cheer` ±120、媽媽 `point` −75），所以 `cheer`／`celebrate`／`point`／`explain` 不給大人用。大人的大動作改用 `shrug`、`reach`，要給觀眾看東西就用 INSERT 手部特寫。

寫完：

```bash
uv run python main.py papa motion-docs          # 重產 skill 參考文件（motions.md、characters.md）
uv run python -m pytest -q libs/content/tests/test_papa_motion.py
uv run python main.py papa build <有用到新動作的分鏡>.json -o /tmp/papa_try --only full
cd /tmp/papa_try/full && npx -y hyperframes@0.9.8 snapshot --at <動作中間的秒數> --output /tmp/papa_try/snap   # 看靜幀
```

業主看過成片確認後把 `status` 改成 `approved`，重產文件。

## 加一個表演套路

`papa_home/assets/papa_home/motion/beats.json` 的 `beats` 加一筆：`label`、`desc`、`status`、`species`、`set`（展開成哪些 cast 欄位）、`example`。
`set` 可以有 `gesture`、`mood`、`mood_to`（依角色給：`{"papa": "smug", "beibei": "happy"}`）、`eyes`、`look_at`、`mouth`。
`gesture` 與 `mood_to` 的時間＝分鏡的 `beat_at`。套路裡的 gesture 物種要涵蓋套路的物種（測試會擋）；用到試用動作的套路也標 `draft`。

## 加一個新姿勢或新角色

生圖不用先問業主（2026-11-05 業主定），順序 Codex → agy → Vertex，每張最多 3 次，自己打開圖看過才用；**新角色的造型（定裝圖）例外，要業主先挑**。
新角色從定裝圖開始：寫 spec（姿勢、身高、表情描述，例 `reports/papa-home/characters/sister.json`）跑
`python -m mamababy_private.scripts.papa_character <spec>` 生出各姿勢全身圖與正面表情頭像（去背、對齊到下面的規格、寫 rig.json 骨架），
再照下表拆件。2026-11-05 姊姊、弟弟就是這樣做的（4 姿勢 × 5 表情）。素材進 `assets/papa_home/characters/<角色>/`，`rig.json` 的 `poses.<姿勢>` 要有：

- `file`（整張 1024×1024、腳底在 (512, 960)）、`world_height`（公分）、`expression`（有臉的角色）、`bbox`；有尾巴加 `tail`＋`tail_pivot`。
- `parts`：`body`、`head`、`front` 一定要有，`front2`、`hind` 有就拆；每個零件是同尺寸畫布的透明圖，`pivot` 在畫布內（肩、脖子、髖）。

拆件與修圖工具（`apps/ops-cli/mamababy/cli/scripts/`）：

| 步驟 | 指令 | QA（`libs/content/tests/test_papa_home_assets.py` 會擋） |
|---|---|---|
| 拆零件 | `python -m mamababy_private.scripts.papa_rig_parts --who 誰 --pose 姿勢 --step gen cut`（修圖先 agy，沒對齊才 Vertex） | 零件疊回去和原圖 alpha IoU ≥ 0.99（外框不能變淡、不能破洞） |
| 身體去掉四肢 | `python -m mamababy_private.scripts.papa_rig_bodies --who 誰 --pose 姿勢` | `parts.body.qa`：`inside` ≥ 0.97、`iou` ≥ 0.985、`|dx|+|dy|` ≤ 20；殘影用 `reports/papa-home/rig/bodies/sheet_<角色>.png` 人眼看（手一動多出手＝身體還畫著手，2026-11-04 爸爸聳肩變 4 隻手） |
| 姿勢專用表情頭 | `python -m mamababy_private.scripts.papa_pose_heads --who 誰 --pose 姿勢 --step cut`（外框補 `--step heal`） | `qa.iou` ≥ 0.95、`body_diff` ≤ 12、`center` 各 ≤ 8px、`neck` ≤ 8；和原本頭零件 alpha IoU ≥ 0.85、不超出原本頭 12px；不過的不寫進 rig |
| 頭像眨眼貼片 | 同上（heads.*.blink） | 貼片只在眼框外擴 20px 內 |

姿勢可選欄位：`shadow`（接觸陰影位置，坐、蹲要往上加寬）、`head_locked: true`（頭和前腳畫在一起，不能做頭部動作）。
物種可選欄位：`head_shift`／`arm_scale`（頭的平移、手的旋轉乘上多少；小孩 0.3／0.5，圓頭短脖子、短袖肩膀接縫）。
其他規則：`avatar_scale` 在 0.2–1.2；姿勢的 `expression` 要是 `heads` 裡有的表情；新角色要在 `assets/papa_home/motion/species.json` 的 `characters` 掛到一個物種（有閉眼表情就填 `closed_eyes`，有尾巴填 `tail_wag_period`）。
最後重產文件、跑 `test_papa_home_assets.py` 與 `test_papa_motion.py`，並 build 一鏡用靜幀看接縫。
