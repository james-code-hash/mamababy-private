<!-- 由 papa_home/skill_docs.py 從 assets/papa_home/motion/*.json 與 rig.json 產生；不要手改，改資料後跑 `python main.py papa motion-docs` -->

# 分鏡 JSON 格式

```text
高階分鏡 → 低階分鏡（相機、站位座標、泡泡位置、配樂段落），以及驗證。

高階分鏡（LLM 寫、人可讀，只用名稱不寫座標）：

    {"episode": 1, "title": "換毛季", "teaser": "寶寶要開始吃副食品了？",
     "sources": {"S2": {"url": "...", "quotes": ["原句…"]}},
     "shots": [
       {"id": "s01", "type": "WIDE", "dur": 2.0, "act": "cold", "scene": "living", "freeze_at": 0.0, "fx": ["tufts"],
        "cast": [{"who": "papa", "pose": "lie", "spot": "sofa"}, {"who": "dad", "pose": "flail", "spot": "front_center"}],
        "lines": [{"text": ["我先說，", "這不全是我的。"], "at": 0.0, "dur": 2.0}],
        "sfx": [["scratch", 0.0]]},
       ...],
     "cut": [{"id": "s01", "dur": 2.0}, ...]}

鏡頭欄位：type（library.SHOT_TYPES）、dur、act（library.ACTS，決定配樂）、mood（覆寫配樂）、scene、
cast[{who, pose, spot | x,y,ppc, dx, flip, move_to(站位或 x), move_dur, show[t0,t1], touch(刻意碰到的角色，例摸頭：不警告重疊，圖層自動蓋在對方上面), action(hop|pop_in|dive), at, beat(表演套路 assets/papa_home/motion/beats.json)/beat_at,
     表演：mood(起始表情) mood_to/mood_at(換表情的 take：預備→壓扁→新表情→回彈)、look_at(誰|camera|[x,y])/look_at_at(頭與瞳孔轉向)、
     gesture(動作庫 assets/papa_home/motion/motions.json)/gesture_at、eyes(open|closed)、mouth(talk＝台詞期間嘴動)}]、
zoom（WIDE 的縮放）、head{who, expr, expr_to, at, look[sx,sy], look_at_at, gesture(gag|sniff|nod|shake), gesture_at, mouth(talk|still；帕帕有台詞預設 talk)}、hand{prop, at, top, motion(stroke|sweep)}、demo{use, full, released, drop, lift_at, press_at}、
sign[行]、step{n, title, sub, source}、split[{prop, label, good}×2]、lines[{text[], at, dur, avatar}]、
onoma[{text, at}]、fx[tufts|floor_tufts|near|lines]、hairball_at、fur_pile{spot|x,y, size}、poof_at、freeze_at、sfx[[名, 秒]]。
頭像鏡（CU／REACTION 帶 head、EXPLAIN）不再用單色底：背景是該 scene（預設 living）在 bg_spot（預設 front_center）的景深模糊畫面。
2026-11-04 試映回饋（像簡報、太長、沒親和力）後的規則：泡泡貼著說話者、長鏡頭要有動作事件（library.STATIC_MIN）、
相機推鏡看得見、全片 45–120 秒。
接點（seam，可用 "seam" 覆寫，library.SEAMS）：特寫前一鏡有帕帕→push（舊鏡推進帕帕的臉、新鏡從放大模糊落定）、
特寫回場景→pull、REACTION／INSERT→iris（新鏡提早 IRIS_LEAD 疊上去開圓）、WHIP→whip、片頭片尾→dip、其餘 cut。
鏡頭結尾會往配樂的拍點挪（snap_to_beats，render.build 讀 beats），泡泡與示範時間都不會被挪壞。
```

## 鏡頭類型（type）

- `WIDE`：全景：交代場景，慢推
- `CU`：特寫：角色頭像反應格（帕帕吐槽、驚訝）
- `TRACK`：跟拍：角色橫越畫面，三層視差
- `INSERT`：道具特寫：手部特寫或道具（梳子、吸塵器）
- `REACTION`：反應：貝貝或寶寶的頭像或全身，硬切
- `EXPLAIN`：帕帕舉板子講解
- `WHIP`：甩鏡進場的全景
- `PULLOUT`：拉遠：結尾全家入鏡
- `POV`：貓視角：從沙發底下看出去
- `SPLIT`：上下對照：錯 vs 對
- `TITLE`：片頭卡
- `END`：片尾卡＋下集預告

## 其他名稱

- act：cold、title、act1、act2、act3、close
- mood（配樂）：theme、daily、trouble、solution、twist、bed
- seam（接點，通常不用寫）：cut、push、pull、iris、whip、dip
