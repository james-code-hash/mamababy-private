---
name: papa-home-episode
description: 《帕帕貝貝家》每集 Reel 的製作與審片：業主說「做第 N 集」「渲染」「先看成片」、回報「幾秒哪裡怪」「像簡報」「太長」「沒親和力」、或要改分鏡、素材、片頭片名時使用。
---

# 《帕帕貝貝家》做一集

真相來源：企劃 `docs/papa-home-series.md`、分鏡格式 `libs/content/mamababy_private/papa_home/compile.py` 開頭、指令 `docs/cli.md` §19、範例分鏡 `libs/content/mamababy_private/papa_home/episodes/archive/ep01_baby.json`（舊角色，只參考格式與節奏）。
對業主 James 一律繁體中文；他看成片後用「幾秒＋哪裡怪」回報，一次改一輪、重渲、再看。

分鏡檔在哪：每一集都在 `libs/content/mamababy_private/papa_home/episodes/epNN.json`（進版控，測試要求每一集都能驗證）。2026-11-05 重製前的舊第 1 集（有寶寶）封存在 `episodes/archive/ep01_baby.json`（`archived: true`，只用來守住引擎畫面不變，新分鏡不能用寶寶）。成片與專案放 `reports/papa-home/epNN_vK/`，同一輪原地覆蓋，換版本才開新資料夾。

## 流程

```bash
uv run python main.py papa validate <分鏡.json>              # 錯誤（擋）＋ ! 警告（不擋，但要處理）
uv run python main.py papa build <分鏡.json> -o <out>         # 只建專案，不渲染
cd <out>/full && npx -y hyperframes@0.9.8 snapshot --review --output /tmp/rev   # 每鏡起點／中點＋每個接點前後 5 格
cd <out>/full && npx -y hyperframes@0.9.8 check --json        # 零 error 才渲染
uv run python main.py papa build <分鏡.json> -o <out> --render # 正片＋精華版，約 10 分鐘，放背景跑
open <out>/papa_home_ep01_full.mp4
uv run python main.py papa build <分鏡.json> -o <out>_mute --only full --no-lines --render   # 不畫泡泡那一版：關掉字幕也要看得懂
```

每輪改完一定重跑 validate → build → 針對改的那幾秒 `snapshot --at t1,t2,…` 看靜幀 → 才重渲。重渲前先用靜幀確認，省掉 10 分鐘。

## 業主會抓、程式抓不到的（每集審片清單）

對著 `snapshot --review` 的 beat sheet 一鏡一鏡看，手機寬度再看一次：

- **角色站的位置**：腳在地板或墊子上；沒有半隻在家具前面、沒有被桌緣蓋到（角色畫在家具上層，一重疊就像「趴在桌上」）；沒有踩到別人。
- **動作圖的來源**：一張圖裡畫了什麼就一起動。「貓毛＋梳子」同一張圖不能來回位移（貓會跟著動）；要動的東西和不動的東西要分開的圖。
- **素材裡有沒有多餘的東西**：從大圖切出來的道具常帶著鄰居（毛團帶梳齒）。去背切不乾淨就用 Nano Banana 重畫同風格版本再綠幕去背（`reports/papa-home/gen/`）。
- **圖文一致**：SPLIT 的 ✕／○ 字要描述那張圖（圖是人用梳子就寫「拿人的梳子」，不是「以為不用梳」）。
- **笑點有鋪陳**：揭曉句前要有一句引子（「於是爸爸拿出…」→「他自己的梳子。」）；縮長度時不要砍引子。
- **每個錯都有回答**：爸爸犯的錯，後面要有一句或一張字卡明確回應（「所以，還是要梳。」），不能靠觀眾自己連。
- **片頭 2 秒是記憶點**，不縮；片名 `library.SERIES_TITLE`。
- **毛球、梳子、吸塵器這些示範**：拿起來→看到成果→按下去，三段都要看得到因果。
- **關掉字幕看得懂嗎**（2026-11-04 回饋「沒看字不知道要表達什麼」）：用 `--no-lines` 渲一版靜音看，每個情節點都要有人在「演」——誰犯錯（爸爸聳肩）、誰難受（帕帕乾嘔）、誰舒服（閉眼靠過去）、誰看誰（寶寶看向帕帕）。說話的角色嘴要動（`mouth: talk`），台詞只是補充。

2026-11-05 新家庭第 1 集重製，業主審了 11 版抓到的（每一條都已經改成程式規則或下面的修法，審片時照樣要看）：

- **頭和手接得住嗎**：中點靜幀看不出來，有換表情（`mood_to`）、轉頭（`look_at`）、動作的鏡頭要每隔 0.3–0.4 秒截一張（`snapshot --at`）看頭會不會離開脖子、手會不會斷（小孩圓頭短脖子最明顯）。
- **零件重複**：頭和前腳畫在同一張的姿勢（貝貝 hide）一做頭部動作就變四隻腳；遇到就在 rig 標 `head_locked`。
- **貼地**：坐、蹲的角色要有屁股和腿下面的陰影，不然像浮起來；躺在家具上要整隻在坐墊上，不要 1/3 懸空。
- **真的碰到**：摸頭、梳毛的手要落在對方身上（照手指尖位置算站位），碰人的那個要在上層（`touch`）；伸手的角色要面向互動對象，不要背對著朝空的地方伸。
- **在玩什麼要看得到**：玩毛＝手伸進毛團、毛在飛；道具和角色的手要對得上，構圖要把主角和道具都框進來（多一個旁觀的角色會把相機拉走，不需要就拿掉）。
- **動作像不像**：零件只能整片轉，聳肩、手肘彎這種做不出來；業主說「看起來只是手抬起來」就畫一張該動作的姿勢圖用 `show` 換上去，不要硬調角度。
- **換姿勢、中途進場**：轉場（iris／push）那幾格也要看，同一個角色兩張圖不能同時出現、還沒進場的角色不能先露臉。
- **帕帕的旁白對得上畫面**：「弟弟已經在抓地上的毛了」＝畫面裡弟弟正在抓毛；「媽媽出手了」＝媽媽在畫面裡做事。

## 每週製作（Claude Code 工作階段；2026-11-05 業主定，取代 LangGraph／deepagents 編劇 agent）

每週日 06:30 MacBook 的 Claude 桌面版排程開一個工作階段，做這週 2 集（週二、週五發）。沒人在旁邊時照下面做；任何一步**試 3 次還不行就整次停下來**，Slack 通知業主停在哪、為什麼。

1. **挑題目**（AI 自己挑）：`papa bible` 看孩子年齡、季節、最近幾集；每集要有寵物＋孩子的切入點、不跟前幾集重複。熱門網站只能找靈感。
2. **找出處**：`papa sources <網址> --keyword …`，只收白名單（`papa_home/sources.py` `ALLOWED_SUFFIXES`：台灣政府 .gov.tw（國健署、衛福部、疾管署、食藥署、農業部動保網 animal.moa.gov.tw、防檢署）、兒科醫學會、獸醫師公會全聯會、AAP／healthychildren、WHO；台灣找不到才用 AVMA、International Cat Care、康乃爾貓健康中心）。一個題目找不到出處換題，換到第 3 個還不行就停。挑好的題目 `papa topic-add` 記下來。
3. **寫分鏡**：讀 skill `papa-home-story`、`papa-home-motion`，寫到 `libs/content/mamababy_private/papa_home/episodes/epNN.json`（進 repo），`papa validate <檔> --fix` 到沒有 ✗。
4. **缺動作**：照 `papa-home-motion/references/adding-motions.md` 加進 `motions.json`／`beats.json`（標 draft），`papa motion-docs` 重產文件，靜幀看過才用。
5. **缺道具**：寫 spec 跑 `python -m mamababy_private.scripts.papa_props <spec>`（Codex → agy → Vertex，每張最多 3 次）；不用問業主，但要自己打開回圖看過（多手、畫風、跟描述一致）才用。檢查擋下但圖其實沒問題時（例：水龍頭本來就從上緣伸進來），在 spec 加 `from_top: true` 重跑（不重生圖），不要硬改檢查。
   - 生圖工具的狀況（2026-11-05）：Codex Plus 生圖額度會用完（`usage_limit_reached`，幾小時後重置），每張先失敗再換 agy；agy 登入大約半小時就會失效、每叫一次跳 Google 登入頁，程式看到一次就這次不再叫 agy、改 Vertex。沒人在旁邊時照樣跑完，結束時在 Slack 提一句「agy 要重新登入」。
6. **審片**：`papa stills <檔> -o <dir>` 每鏡一張，逐張用上面的審片清單看；有表演、轉場、換姿勢的鏡頭再用 `snapshot --at` 每 0.3–0.4 秒截幾張看頭手接縫；不合格就改那幾鏡、重截。過了 `papa build <檔> -o reports/papa-home/epNN_v1 --render`。
7. **通知**：2 集都好了在 Slack 叫業主來看片（附成片路徑與新增的動作／道具清單）。
8. **業主看片**：照「幾秒＋哪裡怪」改，一輪一輪重渲。業主說 OK 後：新增的動作、道具、分鏡開一個 PR（`episodes/epNN.json` 有測試守著，之後改動作庫壞掉 CI 會擋）→ 合併 → `papa ship <分鏡> --dir <成片資料夾>`（上傳 GCS、Firestore 標 approved、設定集記這集、題目標已用）。週二／週五發佈排程只拿 approved 的集數，發文前業主還要在 Slack 按核准。

## 分鏡上的表演（分件 rig）

角色是零件組的（身／頭／前後腳＋頭像的瞳孔、眼皮、嘴），分鏡在 `cast` 裡寫要演什麼，驗證器擋不存在的名字：

| 欄位 | 寫法 | 畫面 |
|---|---|---|
| `mood` | 表情名（`papa menu` 列的） | 這一鏡一開始的臉（沒寫＝姿勢內建表情） |
| `mood_to` ＋ `mood_at` | 表情名、秒 | 換表情的 take：預備下沉→壓扁→新臉→回彈，身體慢一拍跟上 |
| `look_at` ＋ `look_at_at` | `camera`、同鏡角色名、或 `[x, y]` 世界座標 | 頭轉過去、瞳孔跟著移（兩眼不同步） |
| `gesture` ＋ `gesture_at` | 動作庫名稱（已審：shrug／point／reach／lean／gag／sniff／nod／shake；試用：wave／cheer／tilt／startle／sigh／wag_fast；point、cheer 不給爸媽用） | 聳肩攤手、指、伸手、靠過去（維持到鏡尾）、乾嘔、聞、點頭、搖頭…；方向跟 `look_at`，沒有就跟 `flip`；能不能做看物種與姿勢零件 |
| `beat` ＋ `beat_at` | 表演套路（comfy／oops／disgusted／refuse／agree／proud／explain…） | 一個名字展開成 gesture＋換表情＋閉眼＋看鏡頭；cast 自己寫的欄位優先 |
| `eyes` | `closed` | 整鏡閉眼（配 lean＝舒服） |
| `mouth` | `talk` | 台詞期間嘴巴貼片交替＝在說話 |

頭像鏡（CU／REACTION 的 `head`）：`look: [sx, sy]`（-1～1）、`gesture`（只有頭能做的：gag／sniff／nod／shake＋試用 tilt／startle／sigh）、`mouth`（帕帕有台詞預設 talk）。
每個姿勢能換的表情不一樣（貝貝 hide 完全不能換臉），看 `skills/papa-home-motion/references/characters.md` 或 `papa menu`。
每個情節點挑一個最能「讀」出來的動作，不要堆：一鏡一個 gesture，看向目標用 `look_at`。

## 程式已經保證、不用再寫進分鏡的

改 `engine.py`／`compile.py`／動作庫之後，第 1 集要每一格不變：`test_papa_motion.py::test_ep01_renders_identically` 比對每鏡 DOM 與 GSAP 呼叫軌跡；確定畫面本來就要變才跑 `uv run python libs/content/tests/papa_golden.py --write`。真的渲染比對：改前改後各 `papa build … --only full`，再 `uv run python -m mamababy_private.scripts.papa_frame_diff <前>/full <後>/full --frames 40`（像素逐格比）。

接點（push／pull／iris／whip／dip，硬切 ≤ 1/3）、切在配樂拍點、動態模糊、角色接觸陰影、歪頭、眨眼、特寫背景是模糊場景、泡泡貼說話者兩行分兩拍、步驟字卡手寫圈號、暖光暗角、飄毛。改這些去 `engine.py`，不要在分鏡裡硬做。

`papa validate` 的 `!` 警告（`compile.review`）：中途進場的角色起點已在畫框內（憑空出現）、角色在鏡尾前消失（憑空不見）、兩角色重疊過半、**有台詞卻沒有任何動作**。看到就改分鏡，不要帶著警告渲染。

## 分鏡上常用的修法

| 業主說 | 改哪裡 |
|---|---|
| X 秒誰位置不對 | 該鏡 `cast` 的 `x`/`y`/`dx`，用 `snapshot --at` 對著看；相機構圖只算一開始就在場的角色 |
| 誰突然出現／消失 | 進場起點放畫框外（`move_to` 進來）；`show` 的結束時間＝鏡尾或接下一個姿勢 |
| 動作要換一張圖才像（真的聳肩、手肘彎） | 新增一個姿勢（`scripts/papa_character.py` 生、照常拆件），同一個角色寫兩筆 cast、同 x/y，用 `show` 接：例 `stand` show [0, 1.45]、`shrug` show [1.45, 3.0]（2026-11-05 爸爸聳肩）；同角色換姿勢不會被錯開，中途才出場的那張一開始就藏好 |
| 摸頭、抱，手被擋掉或被警告疊在一起 | 碰人的那個角色寫 `touch: "被碰的角色"`：不警告重疊、圖層自動蓋在對方上面；位置照手指尖算（蹲姿手尖在畫布 (897, 628)，翻面就鏡射） |
| 坐著、蹲著像浮起來 | 該姿勢 rig.json 寫 `shadow`（`y` 陰影中心、`h` 高寬比、`w` 寬度比例、`x` 範圍）：坐姿陰影移到屁股和腿下面 |
| 小孩頭像要掉、手斷掉 | 物種 `child` 的 `head_shift: 0.3`、`arm_scale: 0.5` 已經把頭的平移、手的旋轉縮小；還是斷就換別的動作，別用甩手大的套路 |
| 動一下變四隻腳 | 頭跟前腳畫在一起的姿勢（貝貝 hide）在 rig.json 標 `head_locked: true`，驗證器擋頭部動作 |
| 太長 | 砍鏡不砍引子；每鏡 1.2–4 秒；3 秒以上的鏡要有動作事件（驗證器會擋） |
| 像簡報 | 不是分鏡問題，去看 `engine.py` 的接點與動態；`docs/papa-home-series.md` §3「不准像投影片」 |
| 字看不懂 | 先看是不是砍掉了前一句；泡泡每行 ≤10 字、≤2 行、停留 ≥ 字數/5 秒 |
| 不看字看不懂 | 該鏡少了表演：加 `gesture`／`look_at`／`mood_to`、說話的人 `mouth: talk`；用 `--no-lines` 渲一版驗 |
| 角色零件接縫、頭位置不對、外框變淡 | 場景裡的頭是姿勢自己的表情頭 `parts.head.expressions`；重切用 `python -m mamababy_private.scripts.papa_pose_heads --who 誰 --pose 姿勢 --step cut`（每張都有 QA，不過不寫進 rig），外框補 `--step heal`；重拆零件用 `papa_rig_parts --step cut`；手腳一動多出手腳＝身體上還畫著四肢，用 `papa_rig_bodies --who 誰 --pose 姿勢`（Codex 重補，看 `reports/papa-home/rig/bodies/sheet_<角色>.png`） |
| 片名／片頭 | `library.SERIES_TITLE`；片頭鏡 `TITLE` 長度 2.0 |

## 量化檢查（成片出來後）

```bash
# 硬切數（目標 ≤ 鏡數/3）
ffmpeg -i full.mp4 -vf "select='gt(scene,0.35)',showinfo" -f null - 2>&1 | grep -c pts_time
# 每秒畫面變化量（<2 的秒數越少越好；試播集 68/90 → 現在約 25/60）
ffmpeg -i full.mp4 -vf "scale=270:480,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG" -f null - 2>&1 | grep YAVG | awk -F= '{s+=$2;n++; if(n%30==0){printf "%ds:%.1f ",n/30,s/30;s=0}}'
```

響度由 `render` 拉到 −15 LUFS，只量不聽；配樂音效要業主親耳聽。配樂預設整集一首 `music/bed.mp3`（跟主題曲同調同速同樂器），不要依幕換曲——換曲會被聽成「分好幾 part」。

## 交付

成片兩支（`*_full.mp4`、`*_cut.mp4`）直接 `open`，回報「改了什麼、在第幾秒」，不貼長表。改分鏡＝改 fixture `ep01.json`（第 1 集）或該集的 JSON，測試 `libs/content/tests/test_papa_home.py` 跟著改總長度與鏡數。
