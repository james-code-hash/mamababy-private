# 《帕帕貝貝家》每日 Reel 系列企劃

片頭片尾顯示的片名是「帕帕貝貝家」（呼應店名 PapaBaby，`library.SERIES_TITLE`）；程式與 Firestore 的代號是 `papa_home`。對外文字（配文、Slack、後台）一律寫「帕帕貝貝家」，不寫「帕帕家」。

PapaBaby 每日 Reel 改成固定角色的情境喜劇系列。本檔是企劃與系列設定集（series bible）的初稿；正式執行時設定集的「會變動的部分」（時間線、過去集數、固定哏）存 Firestore `series/papa_home`，本檔只寫不常變的規則。

取代 PR #112 的「LLM 從效果清單挑效果」做法：先有故事和固定鏡頭語言，再由程式保證畫面品質。週報影片與 IG 輪播之後再重新設計，暫時沿用 PR #112。

## 1. 目標

- 主打**轉傳**（給伴侶、朋友），其次**收藏**，用系列感換**追蹤**。
- 前 3–4 週以人流為主（`social_watch.PLAN_RULES`）：不推商品、不寫價格、正文不放連結。
- 每週 2 支（IG 的 2 支 Reels 額度），同步 FB、TikTok、YouTube Shorts。

## 2. 世界觀

一間台灣公寓，一家人＋兩隻寵物。帕帕（Papa）＋貝貝（Baby）＝品牌名。

| 角色 | 設定 | 說話 | 畫法 |
|---|---|---|---|
| 帕帕 | 橘虎斑貓、藍色圍兜，家裡最早的成員。第一人稱旁白，嘴有點毒但很愛這個家 | 全片唯一的台詞來源（對話泡泡） | 完整角色，有表情 |
| 貝貝 | 中型米克斯／柴犬感的狗，熱情過頭、傻呼呼，帕帕的吐槽對象 | 不說話，只有表情、動作、擬聲字 | 完整角色，有表情 |
| 爸爸 | 笨手笨腳，主要搞笑來源 | 不說話 | 不畫臉：手、背影、剪影 |
| 媽媽 | 比較懂、穩，示範正確做法；不演成兇或碎念 | 不說話 | 不畫臉：手、背影、剪影 |
| 姊姊 | 國小，齊瀏海短鮑伯頭、黃白條紋 T 恤配牛仔吊帶裙；好奇、愛問、想幫忙照顧寵物和弟弟。旁白叫「姊姊」，不取名 | 不說話 | 完整角色，有表情 |
| 弟弟 | 2 歲多，小平頭、橘色恐龍 T 恤；愛笑、什麼都想摸、跟貝貝最好。旁白叫「弟弟」，不取名 | 不說話 | 完整角色，有表情 |

2026-11-05 業主重製：照業主自己家的組合，寶寶退役（素材留著，舊第 1 集封存在 `episodes/archive/ep01_baby.json`），從第 1 集重來。孩子的出生年月是個資，只存 Firestore 設定集（`kids`），年齡每集自動算；不用真名、畫臉但不照真人畫、不出現學校、制服、地標等認得出這一家的東西。

**時間線**跟真實世界同步：孩子的年齡依出生年月自動算、季節跟現實走。設定集在 `papa ship` 交付一集後記下這集、下一集加一。

## 3. 一集的結構（約 60 秒）

2026-11-04 試播集給外部看的回饋：「像簡報」「太長」「沒親和力」。量過 90 秒版有 68 秒畫面幾乎不動，問題不是秒數是空白秒數，所以結構改成約 60 秒（驗證器允許 45–120）、每鏡 1.2–4 秒、長鏡頭一定要有事發生。

| 時間 | 段落 | 內容 |
|---|---|---|
| 0–3s | 冷開場 | 本集最糗的一刻先放，帕帕一句「事情是這樣的…」 |
| 3–5s | 片頭 | 固定 2 秒片名「帕帕貝貝家｜第 N 集」＋主題曲短句（記憶點，不縮） |
| 5–25s | 第一幕：出事了 | 前 10 秒先放一個暖拍（寶寶／帕帕的親密畫面），毒舌放後面；爸爸用錯方法、失敗；一個貝貝哏當小鉤子 |
| 24–42s | 第二幕：怎麼做才對 | 媽媽或帕帕示範 2–3 步（收藏點，每步約 3 秒），示範時要有角色的反應（例：梳毛時帕帕舒服閉眼），結尾一個 SPLIT 對照 |
| 42–55s | 第三幕：結果＋反轉 | 解決了，但出現意外笑點 |
| 55–60s | 收尾 | 拉遠全家入鏡（爸爸也要有被原諒的一刻），帕帕一句轉傳句＋2 秒下集預告 |

- 每 10–15 秒一個新的小鉤子（笑點、轉折、問題）。台詞總共 15–18 句。
- 同一份分鏡自動剪 **25 秒精華版**：冷開場＋第二幕步驟＋第三幕笑點。前 4 週正片與精華版輪流發，之後看數據（平均觀看秒數、完播率、轉傳、收藏）定長度。
- **接點不是硬切**（HyperFrames 規範：硬切最多佔接點三分之一，轉場要有畫面上的原因）。程式依鏡頭類型決定接點，分鏡可用 `seam` 覆寫：特寫前一鏡有帕帕→`push`（舊鏡推進帕帕的臉、新鏡從放大模糊落定）、特寫回場景→`pull`、REACTION／INSERT→`iris`（新鏡提早 0.22 秒疊在舊鏡上開圓）、WHIP→`whip`、片頭片尾→`dip`（暗 40% 再切）、特寫接特寫→`cut`。
- **切在拍點上**：渲染前用 `hyperframes beats` 抓每首配樂的拍點（存 `PAPA_AUDIO_DIR/beats/`），鏡頭結尾往最近的拍點挪（−0.15～+0.35 秒，泡泡與示範時間不會被挪壞）。
- **動態規範**：進場長尾 ease（expo.out）、離場短且加速（power3.in）、全片開 `data-motion-blur`、頭像不用呼吸迴圈（角色的 idle 才是表演，標題與 UI 的漂浮迴圈是「生成感」）。
- **不准像投影片**：不能有「大頭貼在單色底＋文字框」的鏡頭（特寫背景一律是景深模糊的場景）、步驟字卡不能是方框（手寫圈號＋螢光筆寫出）、3 秒以上的全景／特寫一定要有動作事件（驗證器 `STATIC_MIN`）。

## 4. 鏡頭庫（LLM 只能從這 11 種挑，填參數）

每集最多用 8 種。數字是預設值，由程式實作，LLM 不能改。

| 鏡頭 | 用途 | 動作 |
|---|---|---|
| `WIDE` 全景 | 開場、交代場景 | 整個房間，整鏡慢推 1.0→1.12（手機上要看得出在動） |
| `CU` 帕帕特寫 | 吐槽、內心話 | 0.25s 快推到臉；背景是場景（`scene`／`bg_spot`）的景深模糊畫面，會眨眼；集中線只在 `fx: ["lines"]` 時畫 |
| `TRACK` 跟拍 | 角色移動 | 鏡頭跟角色橫移，三層視差（前景 1.3×、中景 1×、遠景 0.6×） |
| `INSERT` 道具特寫 | 秀道具、重點 | 推到道具，手繪墨線圈起來 |
| `REACTION` 反應 | 貝貝或寶寶的表情 | 0.5–1s 硬切 |
| `EXPLAIN` 帕帕講解 | 2–3 個步驟 | 帕帕舉板子，步驟編號一條條寫出 |
| `WHIP` 甩鏡 | 換房間、換時間 | 快速橫甩＋動態模糊 |
| `PULLOUT` 拉遠 | 結尾 | 拉到全家入鏡，最後一句停 2s |
| `POV` 貓視角 | 系列招牌 | 低角度，從沙發底或門縫看出去，邊緣暗角 |
| `FREEZE` 定格 | 情境喜劇笑點 | 畫面停住＋紙質感，彈出帕帕內心話，配唱片刮擦聲 |
| `SPLIT` 分割對照 | 錯 vs 對 | 上下分割（9:16 窄），上爸爸錯法、下正確做法 |

## 5. 美術與素材包

**分層紙偶**，畫風沿用現有帕帕的色鉛筆暖色調。角色與場景是固定素材，每集重複使用；每集只另外生成道具。素材第一版用 Vertex AI Nano Banana 2.1（GCP 專案 `needle-prod-489015`，模型 `gemini-nano-banana-2.1`）生成，再在 MacBook 本機去背拆層。規格固定，之後換繪師照同一份規格交件，動畫程式不用改。

### 5.1 角色零件規格（分件 rig，v2）

```
libs/content/mamababy_private/assets/papa_home/characters/<角色>/
  rig.json                  畫布、腳底點；每個姿勢的 world_height（cm）、內建表情、bbox、尾巴與尾根 tail_pivot、零件 parts；頭像的脖子錨點、眼框、瞳孔、嘴
  pose_<姿勢>.webp          去背全身定裝圖（不含尾巴），1024×1024 透明底，腳底中心在 (512, 960)；拆件的來源，引擎不再直接畫它
  p_<姿勢>_body.webp        身體（沒有頭、尾巴、四肢；被前後腳蓋住的地方由 Codex 補好，手腳一動不會露洞也不會多出手腳）
  p_<姿勢>_head.webp        這個姿勢自己的頭（含圍兜／項圈）；parts.head.pivot＝頸點（轉頭、歪頭的軸心）
  p_<姿勢>_front.webp       前腳／手（兩隻分開時另有 p_<姿勢>_front2.webp，左邊那隻是 front）；pivot＝肩點
  p_<姿勢>_hind.webp        後腳（有分出來才有）
  tail_<姿勢>.webp          帕帕、貝貝該姿勢的尾巴，同畫布對齊，繞 tail_pivot 旋轉＝甩尾
  p_<姿勢>_head_<表情>.webp 這個姿勢換成某表情的頭（同畫布、跟 p_<姿勢>_head 對齊；場景裡換表情用它）；parts.head.expressions.<表情>＝{file, qa}
  head_<表情>.webp          正面表情頭像，1024×1024 置中；只給 CU／REACTION／泡泡頭像用（不再接到場景裡的身體上）
  blink_<表情>.webp         頭像的閉眼貼片（只有眼睛附近），眨眼時閃 0.13 秒；heads.<表情>.blink
  mouth_<表情>.webp         張嘴貼片（特寫說話時交替顯示）；heads.<表情>.mouth.bbox
…/assets/papa_home/characters/hands/<道具>.webp   手部特寫，整張畫面當 INSERT
```

- 圖層順序（engine.char_html）：接觸陰影 → 尾巴 → 後腳 → 身體 → 前腳 → 頭。場景裡的頭一律是**這個姿勢自己的頭**：原本的表情用 `p_<姿勢>_head`，其他表情用 `p_<姿勢>_head_<表情>`（2026-11-04 試映：正面頭像接到側身、四分之三側的身體上，角度、大小、領口都對不上，看起來頭斷掉，所以改掉）。可用的表情＝`library.pose_expressions(角色, 姿勢)`，分鏡寫了這個姿勢沒有的表情會被驗證器擋並列出可用的；`eyes: closed` 換成閉眼表情（`library.CLOSED_EYES`：帕帕 soft、貝貝 happy、寶寶 sleep）。場景裡不疊瞳孔、眼皮、嘴型貼片（都是照正面頭像畫的，對不到側臉），說話＝頭輕點（`bob`），視線＝轉頭。貝貝趴著埋頭（hide）臉被爪子蓋住，只有原本的頭。爸爸媽媽不畫臉，只拆頭／身／手臂。
- 身體去掉四肢（`apps/ops-cli/mamababy/cli/scripts/papa_rig_bodies.py`，2026-11-04 試映：爸爸聳肩變 4 隻手、貓狗走路多出腳——舊版身體上還畫著 30–100% 的手腳）：姿勢原圖＋四肢塗洋紅的對照圖交給 Codex（`codex exec -i`，用 Codex 生圖額度）「拿掉洋紅的部分、補好後面的身體」→ 用軀幹（含沒改的頭）顏色對齊、接縫附近調回原圖色調 → 只在四肢外擴 6px 換成回圖像素，輪廓不超出原圖、四肢以外不變透明。每張驗證（對齊落在原圖內 ≥ 0.97、接縫色差 ≤ 30、零件拼回去 IoU ≥ 0.985），殘影看 `--step sheet` 的對照圖（四肢轉開的樣子）。第一次 cut 前的身體留在 `reports/papa-home/rig/bodies/<角色>/<姿勢>_body0.webp`，重跑都從它開始。貝貝趴著埋頭（hide）原圖只畫 3 隻腳，已請 Codex 補上第 4 隻後腳（只取新腳的像素、併進 hind 零件）。
- 姿勢表情頭的做法（`apps/ops-cli/mamababy/cli/scripts/papa_pose_heads.py`）：姿勢原圖請 Nano Banana 2.1「只換表情」→ 對齊回原圖 → 只取原本頭零件外擴 10px 的像素。每張都驗證，不過不寫進 rig.json：整體 IoU ≥ 0.95、頭以外色差 ≤ 12、頭確實變了（色差 ≥ 5）、新頭中心與脖子跟原頭差 ≤ 8px、寬度 0.92–1.08。特寫頭像的眨眼一樣做法，只取眼框外擴 18px。零件拼回去要等於原圖（`test_parts_recombine_to_pose` IoU ≥ 0.99）：`cut_layer` 只柔化零件之間的接縫，角色外框保留原圖 alpha（舊版連外框一起柔化，墨線變淡；`--step heal` 補回）。
- **動作庫**（2026-11-04，業主定的四層；資料在 `libs/content/mamababy_private/assets/papa_home/motion/`，加動作不用改程式）：
  1. 物種骨架 `species.json`：大人 human（爸爸、媽媽，不畫臉）／四腳 quadruped（帕帕、貝貝）／寶寶 baby，每個物種把零件角色（`head`、`body`、`arm_a`、`arm_b`、`arm_lead`、`tail`、`lids`）對到 rig 零件；角色的閉眼表情、甩尾週期也在這裡。
  2. 動作庫 `motions.json`：零件動作 `gestures`（每個寫能用的物種、需要的零件、長度，`steps` 是對零件的 GSAP 補間，engine 照抄成 `play([...])`）；整隻角色的 `actions`（hop／pop_in／dive）、自動的 `ambient`（呼吸、歪頭、甩尾、眨眼）參數、INSERT 的 `hand_motions`。已審 8 個：shrug／point／reach／lean／gag／sniff／nod／shake；試用 6 個（業主還沒看片）：wave／cheer／tilt／startle／sigh／wag_fast。
  3. 姿勢＋表情：各角色 `rig.json`（不變）。
  4. 表演套路 `beats.json`：分鏡 cast 寫 `beat`（＋`beat_at`），compile 展開成 gesture／mood_to／eyes／look_at／mouth；例 comfy（舒服＝閉眼＋靠過去）、oops（糟糕＝聳肩看鏡頭）、disgusted、proud、surprised…；姿勢沒有那個表情就不換臉。
  驗證器依物種與姿勢的零件擋（大人不能 wag_fast、貝貝 dive 沒有尾巴…）。改寫後第 1 集每一格不變：`libs/content/tests/fixtures/papa_ep01_golden.json` 記每鏡 DOM 與 GSAP 呼叫軌跡（`papa_trace.js` 用假 GSAP 跑），pytest 比對。動作庫改了跑 `papa motion-docs` 重產 writer skill 的參考文件。
- 程式動作（不用另外畫，全在零件上）：呼吸（身體）、甩尾、跳、走路上下彈跳、每 3 秒左右小幅歪頭（頭）、腳下接觸陰影、眨眼（特寫頭像閃閉眼貼片；閉眼表情 `eyes: null` 不眨）。
- 表演（分鏡 cast 欄位，動作庫）：`mood`／`mood_to`＋`mood_at`（換表情走 take：預備下沉→壓扁→換臉→回彈，身體慢 0.08 秒跟上）、`look_at`（轉頭；瞳孔圖層 iris／pupil 已全部拿掉：一移動，原圖高光留在原位變白斑，2026-11-04 ep01 特寫）、`gesture`（動作庫的名字）、`beat`（表演套路）、`eyes: closed`、`mouth: talk`（特寫：台詞期間嘴巴貼片以 0.17–0.23 秒交替；場景：頭輕點）。頭先動、手與身體依序晚 0.05–0.1 秒。
- 製作方式（v2，`apps/ops-cli/mamababy/cli/scripts/papa_rig_parts.py`，可重跑）：Nano Banana 2.1 依去背定裝圖做兩個編輯——「拿掉頭、補好脖子」（給身體用）與「頭塗純黃、前腳塗純洋紅、後腳塗純青」（當遮罩）——回圖用相似變換（縮放＋位移）對齊原圖後，零件像素一律取自原圖，只有被頭蓋住的身體用模型補的、被腳蓋住的用周圍顏色填；頭像的張嘴版另請模型編輯再相減成貼片。原始回圖與工作檔在 `reports/papa-home/rig/`（不進版控，已有檔不重生）；進 repo 的是 WebP（quality 90、alpha 無損）。v1 的做法（綠底生成單張姿勢、尾巴相減）仍用來做新姿勢的定裝圖。
- 姿勢圖（要另外畫）：

| 角色 | 姿勢 | 表情 |
|---|---|---|
| 帕帕 | 坐、站、趴、舉板子、側走 | 平常、嫌棄（半瞇眼）、驚訝、得意、心軟 |
| 貝貝 | 坐、站、側跑、趴（頭埋起來）、叼東西 | 開心吐舌、無辜、害怕、興奮 |
| 爸爸 | 站、蹲、抱寶寶、手忙腳亂 | 不畫臉 |
| 媽媽 | 站、蹲、抱寶寶、示範（手部特寫） | 不畫臉 |
| 姊姊 | 站、坐、走、蹲 | 微笑、開心、生氣、驚訝、想哭 |
| 弟弟 | 站、坐、走、蹲 | 微笑、大笑（閉眼）、生氣、驚訝、哭 |
| 寶寶（已退役） | 躺、趴、扶坐、被抱 | 笑、哭、睡、好奇 |

- 另有**手部特寫組**（拿梳子、拿奶瓶、拿紗布巾；第 2 集加了副食品組：`mom_spoon` 小碗＋小湯匙、`dad_spoon_heap` 一次堆太多、`dad_salt` 撒鹽、`dad_honey` 加蜂蜜）；第二幕示範主要用這組，每集的道具畫在手部特寫裡。新道具用 `apps/ops-cli/mamababy/cli/scripts/papa_props.py`：spec 列名稱、畫風參考（現有手部特寫，袖子跟著它）、中文說明、英文畫面描述 → 綠底生成（Codex → agy → Vertex Nano Banana 2.1，每張最多 3 次）→ 去背 → 檢查（面積、從畫面邊緣伸入、沒被切、沒殘綠）→ 寫進 `characters/hands/` 並登記 `rig.json`（`labels` 是給編劇看的說明，會出現在 writer skill 的參考文件）。生圖不用先問業主（2026-11-05 業主定），但工作階段要自己打開圖看過（多手、畫風、跟描述一致）才用；3 次都不行就整次停下來通知業主。新角色的姿勢與表情頭像用 `scripts/papa_character.py`（同一個生圖順序與 3 次規則），再接 `papa_rig_parts`／`papa_rig_bodies`／`papa_pose_heads` 拆件。
- 合計約 23 張姿勢圖＋13 個表情。LLM 寫分鏡只能選清單裡的姿勢、表情與動作，選了不存在的由驗證器擋下。

### 5.2 場景規格

客廳、寶寶房、廚房三個場景，每個三層：

```
libs/content/mamababy_private/assets/papa_home/scenes/<場景>/
  far.webp   遠景＝空房間（牆、地板、窗、天花板），高 1920、寬約 2400，供 TRACK 橫移
  mid.webp   中景＝所有家具與物品，與 far 同尺寸、像素對齊，透明底
  near.webp  前景遮擋物（植物、扶手、嬰兒床欄杆等），1080×1920 畫面座標，透明底
  scene.json 各層視差係數、站位點（腳底座標＋該深度 px_per_cm）、POV 機位
```

- 製作方式（v1）：2K 重繪原場景 → 編輯成「清空家具」得 far、編輯成「牆地換洋紅、只留家具」再去背得 mid；near 另外生成。
- 角色要站在站位點上，不要放在前景遮擋物後面；站位點是初版目測值，試播集時再校。

## 6. 聲音

- 不配旁白（多數人靜音滑；中文 TTS 的機器感不適合當角色聲音）。
- **系列主題曲**：3–4 小節「帕帕貝貝家」旋律，用 `sfx/synth.py` 程式合成，片頭、片尾用，版權自有。
- **整集一首底樂**（`music/bed.mp3`，預設模式 `single`）：跟主題曲同調同速同樂器（C 大調 110 BPM、烏克麗麗／馬林巴／鐘琴），片頭片尾才切主題曲。2026-11-04 試映回饋「配樂不連貫、像分好幾 part」：原本依幕換曲（日常／出事／解法／反轉，各 20–34 秒、速度 90–130 不等）已退為備援（分鏡 `"music": "moods"` 或 bed 缺檔時）。曲子用 ACE-Step 1.5 本機生成，每次 2 版、業主親耳挑。
- **角色音效**：帕帕嫌棄喵、貝貝汪＋尾巴拍地、寶寶笑／哭、爸爸出糗「咚」，CC0，固定使用。定格配唱片刮擦。
- 鏡頭切在配樂拍點上（程式自動挪，見 §3）。

## 7. 畫面文字

- 帕帕台詞＝手繪邊框對話泡泡（線條抖動、每個略歪），放在帕帕頭上、尾巴指向他，兩行分兩拍出現；帕帕不在畫面時用角落小頭像＋泡泡。
- 每行 ≤10 字、≤2 行；閱讀時間每秒 5 字、最少 1.2 秒。全片台詞約 250–350 字。
- 擬聲字（咚！汪！）用漫畫大字，跟動作同格出現。
- 步驟字卡（手寫圈號＋標題螢光筆寫出＋小字，沒有方框）跟著示範鏡頭出現，編號 1／2／3。
- 字體：全片只用 jf open 粉圓（OFL）；Noto Sans TC 不再用（看起來像簡報）。
- 安全區：y 168–1330，右側 230px 不放字。

## 8. 選題與內容正確性

- 題目來源優先序：業主點子 → 孩子年齡＋季節 → KOL 熱門話題（只當切入角度，`social_watch`）。每集盡量同時碰一個寵物點和一個育兒或居家點。
- 題目庫 `series/papa_home/topics` 保持未來 8 週，每週一挑 2 集隨週計畫給業主核准。
- **第二幕的知識點必須引用官方來源原句**：白名單（國健署、衛福部、疾管署、農業部動保司、獸醫師公會等）網頁切句，LLM 只能根據清單裡的句子寫，每步標出依據哪一句，驗證器比對不到就退回（沿用 PR #112 `page_capture` 與週報的檢查方式）。不給醫療建議，只能說「出現 X 去看醫生」。來源連結放 IG 留言。找不到來源 → 降級為純生活情境，不放知識點。

## 9. 流程與把關

1. 週一：週計畫裡帶每集一句話大綱 → 業主核准。
2. 製作（2026-11-05 起每週一次，Claude Code 工作階段；原本的 LangGraph／deepagents 編劇 agent 已拆掉——新動作、新道具常常要當場加，而且要記進 repo）：每週日 06:30 排程開工作階段 → AI 挑題目、白名單找出處 → 寫分鏡（`episodes/epNN.json`）→ `papa validate --fix` → 缺動作／道具自己加（試 3 次不行整次停）→ `papa stills` 看圖 → 渲染 → Slack 叫業主看片 → 業主 OK 後 PR 合併、`papa ship`。細節見 `.claude/skills/papa-home-episode/SKILL.md`。
3. 渲染完上傳 Postiz 媒體庫；Slack 一則訊息附成片連結、分鏡靜幀、腳本 → 業主回 OK 或修改意見（意見當修改指示重新產生，重渲染約 8 分鐘）。
4. OK 後排進 Postiz：IG、FB、TikTok、YouTube Shorts。
5. 發佈後更新設定集；第 1、3、7 天補 `insights`。

任何一步失敗就退回 PR #112 的簡單版 Reel，讓草稿照樣有影片。

## 10. 資料

影片檔不放 GCS（拿掉 `core.gcs`／`SOCIAL_MEDIA_BUCKET`），改放 Postiz 媒體庫；YouTube 當發佈平台。YouTube API 專案未通過 Google 審核前，API 上傳的影片強制為私人，需業主在 YouTube 後台手動公開。

```
papa_home_series/bible           設定集：cast、home、rules、running_gags、timeline{baby_age_months, as_of}、episodes[摘要]、next_episode_no
papa_home_episodes/{ep:03d}      每集：status（planned→scripted→rendered→approved→published／rejected）＋status_history、
                                 title、logline、topic、storyboard（完整高階分鏡，含 sources 原句）、feedback[]、media、postiz、insights
papa_home_topics/{id}            題目庫：title、pet_point、kid_point、angle、reason（AI 挑題的理由）、keywords、source_urls、order、status（queued／used）
```

（Firestore 用平的集合，不用子集合：三個都是小集合，整批讀也不會超過免費額度。）

## 11. 進度

1. 素材包：角色定裝圖 → 業主核准 → 拆零件；三個場景。
2. 設定集（本檔＋Firestore 初值）。
3. 試播集《認識帕帕貝貝家｜換毛季》在 MacBook 手工做，分鏡靜幀多審一次。
   - 冷開場：凌晨，爸爸黑褲沾滿貓毛，帕帕「我先說，這不全是我的。」
   - 第一幕：角色依序登場；爸爸拿錯梳子、逆毛梳。
   - 第二幕：媽媽示範梳毛 3 步（須有官方或獸醫來源）。
   - 第三幕：貝貝把梳下的毛團叼去給寶寶看，寶寶笑。
   - 收尾：「轉給家裡負責吸地的那個人」＋下集預告。
4. 試播通過後自動化（三階段）：
   - 第 1 階段（完成）：`mamababy_private.papa_home` 渲染核心＋`papa` CLI，第 1 集用高階分鏡重建，與試播一致。
   - 第 2 階段（完成，PR #116）：LLM 依設定集＋題目＋來源原句寫高階分鏡，驗證不過退回重寫（`papa write`）；Firestore 設定集／集數／題目庫（`papa bible-init`、`topic-add`）。
   - 第 2.5 階段：動作庫（四層資料化、writer skill）＋編劇流程改 LangGraph＋deepagents（照 IG 輪播 agent），看圖只退回不合格的鏡頭。
   - 第 3 階段：週一大綱、渲染、Slack 審片、Postiz 發佈、cron 部署 claw-arm-1。
   - 2026-11-05 業主決定：每集每週在 Claude 工作階段做（常要新增動作、道具並記進動作庫，agent 自動產不了）；做好審過跑 `papa approve <集數> <mp4>`，發佈交給社群每日產出（`cron_social_daily`）週二、週五 21:00，配文當天寫，Slack 核准才發。
5. 程式：PR #105、#112 已合併；每日 Reel 新流程另開 PR。

## 12. 程式

- `papa_home/library.py`：固定素材與鏡頭庫（鏡頭類型、場景站位、姿勢、表情、道具、音效）與字數規則。
- `papa_home/compile.py`：高階分鏡的格式說明、`validate`（回傳錯誤清單）、`compile_episode`（相機依鏡頭類型自動算、泡泡指向畫面裡的帕帕否則放頭像、連續同情緒的鏡頭接成一段配樂）、`cut_episode`（精華版）。
- `papa_home/engine.py`：低階分鏡 → HyperFrames（每鏡一個 sub-composition）；角色用零件組（`char_html`），頭像（`avatar_html`）同時給場景與特寫用，表演的 GSAP 寫在 `JS_HELPERS`（take／look／talk），零件動作由 `motion.calls_js` 從動作庫產生。
- `papa_home/motion.py`：讀動作庫三個 JSON；零件動作 → GSAP 呼叫清單、動作能不能做（物種、姿勢零件）、表演套路展開。`skill_docs.py`：從資料產生 skill 的參考文件（`papa motion-docs`）。
- `papa_home/checks.py`：分鏡的機械檢查（知識點逐字引用、數字來源）與自動補泡泡停留（`fit_lines`，`papa validate --fix`）。`render.stills`：每鏡中間一格靜幀（`papa stills`）。
- `.claude/skills/papa-home-story`（結構、畫面文字、分鏡格式）與 `.claude/skills/papa-home-motion`（動作庫、角色姿勢表情、加新動作與素材 QA）：製作工作階段讀的 skill；做一集的流程在 `.claude/skills/papa-home-episode`。
- `papa_home/render.py`：素材用連結組專案（props 合併素材包與本集道具；配樂音效讀 `PAPA_AUDIO_DIR`）→ 渲染（失敗改單一分頁重來）→ 響度 -15 LUFS。
- `papa_home/bible.py`：設定集（孩子年齡依出生年月推算、交付後更新）；`store.py`：Firestore；`sources.py`：白名單網頁／PDF → 句子；`writer.py`：單次呼叫的提示詞（設定集、題目、來源原句、素材＋動作清單、第 1 集範例）、知識點檢查（步驟字卡要逐字引用原句、數字不能憑空出現）；`write()` 走 agent.py 同一個流程。
- 驗證規則：一集最多 10 種鏡頭（片頭片尾不算；試播集用了 10 種）、每行 ≤10 字、≤2 行、停留 ≥ 字數/5 秒且 ≥1.2 秒（只算中英數，不算標點空格）、第一鏡不能是片頭卡、步驟字卡要有來源、全片 45–120 秒、≥3 秒的 WIDE／CU／REACTION／POV／INSERT 要有動作事件（角色移動或動作、表演、飄毛、道具、表情變化、擬聲字、定格）、`fx` 只能是 tufts／floor_tufts／near／lines、表演欄位的表情／動作名／`look_at` 對象要存在且時間在鏡頭內。審片警告（`review`）：有台詞卻沒有任何動作的鏡頭（關掉字幕看不懂）。

業主待辦：YouTube 頻道與帳號、申請 YouTube API 審核、ERP 設定填 `LLM_API_KEY`。
