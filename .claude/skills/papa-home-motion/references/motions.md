<!-- 由 papa_home/skill_docs.py 從 assets/papa_home/motion/*.json 與 rig.json 產生；不要手改，改資料後跑 `python main.py papa motion-docs` -->


# 動作庫（assets/papa_home/motion/motions.json）

分鏡寫法：場景鏡 `cast[].gesture` ＋ `gesture_at`（秒）；頭像鏡 `head.gesture` ＋ `head.gesture_at`（只能用「頭像鏡」打勾的）。方向：有 `look_at` 跟著看的方向，沒有就跟 `flip`（flip＝向左）。一鏡一個角色最多一個 gesture。

「試用」＝還沒經過業主看片確認，可以用（業主 2026-11-04 同意第 2 集起使用）；業主看片確認後改成已審。

## 零件動作（gesture）

| 名稱 | 中文 | 狀態 | 物種 | 頭像鏡 | 需要零件 | 長度 | 參數 |
|---|---|---|---|---|---|---|---|
| `shrug` | 聳肩：頭歪、兩手（前腳）往外抬，攤手 | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） |  | head | 1.2s | 零件 head/arm_a/arm_b/body；head.rotation 7×方向，head.yPercent -1，arm_a.rotation 38，arm_a.yPercent -2.2 |
| `point` | 指：靠目標那隻手抬起指向 look_at 的目標 | 已審 | 四腳（貓、狗）、小孩（兩腳、有臉） |  | head/arm_lead | 1.45s | 零件 head/arm_lead；head.rotation -4×方向，arm_lead.rotation -75×方向 |
| `reach` | 伸手：兩手往目標伸、身體前傾，1 秒後收回 | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） |  | head | 1.4s | 零件 head/body/arm_a/arm_b；head.rotation 5×方向，head.xPercent 1.2×方向，body.rotation 7×方向，arm_a.rotation -55×方向 |
| `lean` | 靠過去：身體往目標傾、頭跟著，維持到鏡尾（配閉眼＝舒服） | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） |  | head | 0.35s（維持到鏡尾） | 零件 head/body；head.rotation 5×方向，head.xPercent 1.2×方向，body.rotation 7×方向 |
| `gag` | 乾嘔：頭往前抽兩下、身體擠壓、閉眼 | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 0.72s | 零件 head/body/lids；重複 2 次／每 0.26s，head.yPercent 1.0，head.rotation 9×方向，head.xPercent 1.8×方向 |
| `sniff` | 聞：頭湊向目標點三下 | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 1.25s | 零件 head；head.rotation 6×方向，head.xPercent 1.2×方向，head.yPercent 0.8，重複 3 次／每 0.17s |
| `nod` | 點頭：點頭兩下（同意、好） | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 0.64s | 零件 head；重複 2 次／每 0.36s，head.rotation 3，head.yPercent 1.2 |
| `shake` | 搖頭：搖頭三下（不要、不對） | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 0.52s | 零件 head；重複 3 次／每 0.12s，head.rotation 3×交替，head.xPercent 1.3×交替 |
| `wave` | 揮手：靠方向那隻手舉高左右揮三下（打招呼、叫人過來） | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） |  | head/arm_lead | 1.3s | 零件 arm_lead/head；arm_lead.rotation -110×方向，arm_lead.yPercent -1.5，head.rotation 4×方向，重複 3 次／每 0.24s |
| `cheer` | 歡呼：兩手（前腳）舉高、整隻往上彈一下（成功了、好開心） | 試用 | 四腳（貓、狗）、小孩（兩腳、有臉） |  | head | 1.35s | 零件 body/arm_a/arm_b/head；body.y -36，arm_a.rotation 120，arm_a.yPercent -2.5，arm_b.rotation -120 |
| `tilt` | 歪頭：頭往一邊歪、停一下再回來（疑惑、好奇、聽不懂） | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 1.75s | 零件 head；head.rotation 12×方向，head.xPercent 0.6×方向 |
| `startle` | 嚇一跳：整隻往上彈、頭往後縮、兩手張開，然後落回來（被嚇到、出事了） | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 0.9s | 零件 body/head/arm_a/arm_b；body.y -48，head.rotation -8×方向，head.yPercent -1.6，arm_a.rotation 48 |
| `sigh` | 低頭嘆氣：頭慢慢往下垂、手跟著垂，停一下再抬起來（無奈、又來了） | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | ✓ | head | 1.8s | 零件 head/arm_a/arm_b；head.rotation -5×方向，head.yPercent 1.6，arm_a.rotation -6，arm_b.rotation 6 |
| `wag_fast` | 甩尾加速：尾巴快速甩十下（超興奮、看到好東西） | 試用 | 四腳（貓、狗） |  | tail | 0.9s | 零件 tail；tail.rotation 22 |

### 範例鏡頭

- `shrug`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "dad", "pose": "stand", "spot": "front_center", "gesture": "shrug", "gesture_at": 0.4}]}`
- `point`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "point", "gesture_at": 0.4, "look_at": [1500, 1500]}]}`
- `reach`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "dad", "pose": "stand", "spot": "front_center", "gesture": "reach", "gesture_at": 0.4, "look_at": [1500, 1500]}]}`
- `lean`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "dad", "pose": "stand", "spot": "front_center", "gesture": "lean", "gesture_at": 0.4, "look_at": [1500, 1500]}]}`
- `gag`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "gag", "gesture_at": 0.4}]}`
- `sniff`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "sniff", "gesture_at": 0.4, "look_at": [1500, 1500]}]}`
- `nod`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "nod", "gesture_at": 0.4}]}`
- `shake`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "shake", "gesture_at": 0.4}]}`
- `wave`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "dad", "pose": "stand", "spot": "front_center", "gesture": "wave", "gesture_at": 0.4, "look_at": "camera"}]}`
- `cheer`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "cheer", "gesture_at": 0.4}]}`
- `tilt`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "tilt", "gesture_at": 0.4}]}`
- `startle`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "startle", "gesture_at": 0.4}]}`
- `sigh`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "sigh", "gesture_at": 0.4}]}`
- `wag_fast`：`{"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [{"who": "papa", "pose": "sit", "spot": "front_center", "gesture": "wag_fast", "gesture_at": 0.4}]}`

## 整隻角色的動作（cast.action）

| 名稱 | 中文 | 物種 | 參數 | 寫法 |
|---|---|---|---|---|
| `hop` | 蹦跳：整鏡上下彈跳（TRACK 有 move_to 時自動加） | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | period=0.26、height=38 | `"action": "hop"` |
| `pop_in` | 彈出：從下面彈進畫面（壓扁→回彈），at 秒開始 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | default_at=0.15、from_y=220、squash=0.7、duration=0.45 | `"action": "pop_in", "at": 0.15` |
| `dive` | 撲：拋物線撲過去（dive_dx 世界 px，預設 -250），at 秒起跳、0.6 秒落地 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | default_dx=-250、rise=130、land=90、duration=0.6 | `"action": "dive", "at": 4.1, "dive_dx": -340`（通常配 `show` 接在 run 後面） |

## 走位與進出場

- `move_to`（走位）：從 spot／x 等速移到另一個站位名或 x（move_dur 秒，預設整鏡）；TRACK 必用
- `show`（進出場）：show:[t0, t1]：t0 秒出現、t1 秒消失；換姿勢＝同一角色兩筆 cast，前一筆的 t1＝下一筆的 t0
- `flip`（轉向）：flip:true 左右鏡像（面向另一邊）；動作方向跟著反過來

## 表情與視線（face）

- 換表情：mood_to＋mood_at：預備下沉→壓扁→換新臉→回彈，身體慢一拍（欄位 `mood`、`mood_to`、`mood_at`）
- 看向：look_at（camera／同鏡角色名／[x, y]）＋look_at_at：頭轉過去（欄位 `look_at`、`look_at_at`）
- 說話：mouth: talk：台詞期間場景裡的頭輕點、頭像鏡嘴巴貼片開合（欄位 `mouth`）
- 閉眼：eyes: closed：整鏡換成這個角色的閉眼表情（species.json closed_eyes）（欄位 `eyes`）

## 程式自動加的（不用寫）

- 呼吸：身體上下微縮放，每個角色每一鏡自動
- 歪頭待機：每 3 秒左右小幅歪頭，自動
- 甩尾：有尾巴的姿勢整鏡甩尾，週期看角色（species.json tail_wag_period）
- 眨眼：頭像鏡的臉約每 2.4 秒眨一次，自動；eyes: closed 改整鏡閉眼

## 手部特寫的動法（INSERT 的 hand.motion）

- `stroke`（梳）：INSERT 手部特寫：圖不動、慢推，梳子頭每 0.6 秒刷出兩團毛
- `sweep`（掃）：INSERT 手部特寫：左右來回掃（吸地）

# 表演套路（assets/papa_home/motion/beats.json）

分鏡寫 `cast[].beat`＋`beat_at`（秒，預設 0.3），要看誰另寫 `look_at`。展開成下面的欄位；cast 自己寫的欄位優先，這個姿勢沒有的表情就不換臉（不會報錯）。

| 名稱 | 中文 | 狀態 | 物種 | 展開成 | 例 |
|---|---|---|---|---|---|
| `comfy` | 舒服：閉眼、身體靠過去（被梳、被摸、被抱） | 已審 | 四腳（貓、狗）、小孩（兩腳、有臉） | eyes="closed"；gesture="lean" | ep01 s15：帕帕被媽媽梳，閉眼靠過去 |
| `oops` | 糟糕：做錯事、被抓包：聳肩攤手、看鏡頭 | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="shrug"；look_at="camera" | ep01 s08：爸爸拿自己的梳子，聳肩 |
| `disgusted` | 嫌棄：換成嫌棄臉、乾嘔 | 已審 | 四腳（貓、狗）、小孩（兩腳、有臉） | gesture="gag"；mood_to={"papa": "unimpressed", "beibei": "scared", "baby": "cry", "sister": "angry", "brother": "angry"} | 帕帕聞到怪味 |
| `refuse` | 不要：搖頭（不對、不要、才不是） | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="shake" | ep01 s01：爸爸慌張搖頭 |
| `agree` | 對啦：看向對方、點頭（同意、示範時說好） | 已審 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="nod" | ep01 s12：媽媽點頭進場 |
| `proud` | 得意：換成得意／開心的臉、點頭、看鏡頭 | 已審 | 四腳（貓、狗）、小孩（兩腳、有臉） | gesture="nod"；look_at="camera"；mood_to={"papa": "smug", "beibei": "happy", "baby": "giggle", "sister": "happy", "brother": "laugh"} | 收尾帕帕一句金句 |
| `surprised` | 嚇到：換成驚訝／害怕的臉、嚇一跳 | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="startle"；mood_to={"papa": "surprised", "beibei": "scared", "baby": "cry", "sister": "surprised", "brother": "surprised"} | 貝貝撲進毛堆那一刻，帕帕嚇一跳 |
| `curious` | 好奇：看向目標、歪頭（這是什麼？） | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="tilt"；mood_to={"baby": "curious", "beibei": "innocent", "papa": "neutral", "sister": "smile", "brother": "smile"} | 寶寶第一次看到湯匙 |
| `sniff_check` | 聞聞看：頭湊過去聞三下（寵物檢查新東西） | 已審 | 四腳（貓、狗）、小孩（兩腳、有臉） | gesture="sniff" | 貝貝聞寶寶的副食品 |
| `explain` | 說明：指向目標、邊指邊說（帕帕講解；mouth talk 只對有臉的角色有效） | 已審 | 四腳（貓、狗）、小孩（兩腳、有臉） | gesture="point"；mouth="talk" | 帕帕指著梳子講 |
| `celebrate` | 歡呼：換成開心的臉、兩手舉高彈一下 | 試用 | 四腳（貓、狗）、小孩（兩腳、有臉） | gesture="cheer"；mood_to={"papa": "smug", "beibei": "excited", "baby": "giggle", "sister": "happy", "brother": "laugh"} | 寶寶第一口吃下去，全家歡呼 |
| `resigned` | 無奈：換成無言的臉、低頭嘆氣（又來了） | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="sigh"；mood_to={"papa": "unimpressed", "beibei": "innocent", "sister": "sad", "brother": "cry"} | 帕帕看爸爸又拿錯東西 |
| `greet` | 打招呼：看向對方、揮手 | 試用 | 大人（兩腳）、四腳（貓、狗）、小孩（兩腳、有臉） | gesture="wave" | 爸爸下班回家揮手 |
| `excited` | 超興奮：換成興奮的臉、尾巴猛甩（狗看到玩具） | 試用 | 四腳（貓、狗） | gesture="wag_fast"；mood_to={"beibei": "excited", "papa": "surprised"} | 貝貝看到毛堆 |
