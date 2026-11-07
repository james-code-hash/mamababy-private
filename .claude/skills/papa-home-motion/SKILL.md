---
name: papa-home-motion
description: 《帕帕貝貝家》紙偶角色的動作庫：物種骨架、零件動作（gesture）、整隻角色動作（action）、表情與視線、表演套路（beat）、各角色每個姿勢能換的表情與能做的動作。寫或改分鏡的 cast／head 表演欄位、挑「這一鏡誰在演什麼」、想加新動作或新姿勢時一定要先讀；分鏡只能用這裡列出的名字。
---

# 《帕帕貝貝家》動作庫

角色是分件紙偶（身／頭／兩隻前手或前腳／後腳，貓狗多一條尾巴），動作全部由這些零件演。
分鏡裡**只能用這份 skill 列出的名字**；名字或物種不對，驗證器會擋下來退回。

## 四層，從下往上

1. **物種骨架**（`assets/papa_home/motion/species.json`）：大人 human（爸爸、媽媽，不畫臉）／四腳 quadruped（帕帕、貝貝）／寶寶 baby。每個物種把零件角色（`head`、`body`、`arm_a`、`arm_b`、`arm_lead`、`tail`…）對到 rig 的零件。動作只認角色名，所以同一個「聳肩」爸爸抬手、帕帕抬前腳。
2. **動作庫**（`assets/papa_home/motion/motions.json`）：有名字的零件動作 `gesture`（聳肩、指、點頭…）、整隻角色的 `action`（蹦跳、彈出、撲）、走位 `move_to`／`show`、表情 `mood_to`、視線 `look_at`、說話 `mouth`。
3. **姿勢＋表情**（各角色 `rig.json`）：每個姿勢有哪些零件、場景裡能換哪些表情（每個姿勢不一樣，看 characters.md）。
4. **表演套路**（`assets/papa_home/motion/beats.json`）：把 2、3 組成一個情緒名，例如 `comfy`（舒服）＝閉眼＋靠過去。分鏡寫 `"beat": "comfy"` 就好。

## 怎麼挑

- 先想觀眾**關掉字幕**能不能看懂這一鏡：誰犯錯（`oops`）、誰難受（`disgusted`）、誰舒服（`comfy`）、誰看誰（`look_at`）。台詞只是補充。
- 一個情節點挑**一個**最能讀出來的動作，不要堆：一鏡一個角色最多一個 gesture 或一個 beat；要看誰另寫 `look_at`。
- 說話的角色（只有帕帕有台詞）寫 `mouth: "talk"`；帕帕不在畫面上時泡泡用 `avatar`。
- 有表情的套路（`proud`、`disgusted`…）遇到沒有那個表情的姿勢會自動不換臉；想要換臉就挑表格裡「場景裡可換的表情」有那個表情的姿勢。
- 不畫臉的大人（dad、mom）不能寫 `mood`／`mood_to`／`eyes`／`mouth`，演戲靠 `shrug`、`reach`、`nod`、`shake`（大人是背影，`point`／`cheer` 手舉太開會像斷手，不給大人用）。要拿東西給觀眾看就用 INSERT 手部特寫。
- 頭像鏡（CU／REACTION 的 `head`）只有頭：`head.gesture` 只能用「頭像鏡」打勾的動作（gag／sniff／nod／shake＋試用的 tilt／startle／sigh）。
- 「試用」動作還沒經過業主看片，可以用；挑的時候還是以「這一鏡最能讀懂」為準，不要為了用而用。

## 寫法速查

```json
{"who": "papa", "pose": "sit", "spot": "sofa",
 "mood": "smug", "mood_to": "unimpressed", "mood_at": 1.4,
 "look_at": "dad", "look_at_at": 0.2,
 "gesture": "shrug", "gesture_at": 0.5,
 "mouth": "talk"}
{"who": "papa", "pose": "sit", "spot": "sofa", "beat": "comfy", "beat_at": 0.15, "look_at": "mom"}
{"who": "beibei", "pose": "run", "x": 2400, "y": 1790, "ppc": 6.6, "flip": true, "move_to": 1720, "move_dur": 1.5, "show": [2.6, 4.1], "action": "hop"}
```

時間欄位（`*_at`）都是鏡頭內的秒數，要小於鏡頭長度；動作長度看表格，`gesture_at`＋長度最好在鏡尾前做完。

## 參考文件（要用時再讀）

- `references/motions.md`：每個 gesture／action／beat 的名稱、中文、能用的物種、需要的零件、長度、參數、範例鏡頭。**挑動作前讀。**
- `references/characters.md`：每個角色每個姿勢的內建表情、場景裡可換的表情、有哪些零件、能做哪些 gesture；場景站位、道具、音效。**寫 cast 前讀。**
- `references/adding-motions.md`：加新動作、新套路、新姿勢的格式與素材 QA 規則（給工程師與業主；寫分鏡不用讀）。
