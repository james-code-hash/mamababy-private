"""高階分鏡 → 低階分鏡（相機、站位座標、泡泡位置、配樂段落），以及驗證。

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
"""
from __future__ import annotations

import copy
import re

from mamababy_private.papa_home import library as lib
from mamababy_private.papa_home import motion

ACT_MOOD = {"cold": "trouble", "title": "theme", "act1": "daily", "act2": "solution", "act3": "twist", "close": "theme"}
SCENE_TYPES = {"WIDE", "TRACK", "INSERT", "REACTION", "WHIP", "PULLOUT", "POV"}
HEAD_TYPES = {"CU", "REACTION"}
ACT_TIMES = ("mood_at", "look_at_at", "gesture_at")
STATIC_TYPES = {"WIDE", "CU", "REACTION", "POV", "INSERT"}
STEP_CARD_BOTTOM = 460  # 步驟字卡（engine .step）top 200＋最高約 260
DEFAULT_POS, LOW_POS = (70, 230), (70, 620)
HEAD_TARGET = (540, 1160)  # 頭像鏡：泡泡尾巴指向頭頂（頭像畫在畫面下半）
ONOMA_SLOTS = [(620, 260, -8), (200, 380, 7), (560, 440, -5), (240, 300, 6)]


# ── 驗證 ────────────────────────────────────────────────────────────────
def reading_chars(text: str) -> int:
    """要讀的字數：中文字、英文字母、數字（標點與空格不算）。"""
    return len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbfA-Za-z0-9]", text))


def _line_errors(where: str, line: dict, shot_dur: float) -> list[str]:
    errs = []
    rows = line.get("text") or []
    if not rows or len(rows) > lib.LINE_MAX_ROWS:
        errs.append(f"{where}：泡泡要 1–{lib.LINE_MAX_ROWS} 行")
    for r in rows:
        if len(r) > lib.LINE_MAX_CHARS:
            errs.append(f"{where}：「{r}」超過 {lib.LINE_MAX_CHARS} 字")
    need = max(lib.MIN_HOLD, sum(reading_chars(r) for r in rows) / lib.READ_CHARS_PER_SEC)
    dur, at = float(line.get("dur") or 0), float(line.get("at") or 0)
    if dur + 0.01 < need:
        errs.append(f"{where}：停留 {dur}s 不夠讀（至少 {need:.1f}s）")
    if at + dur > shot_dur + 0.01:
        errs.append(f"{where}：泡泡超出鏡頭長度")
    av = line.get("avatar")
    if av and av not in lib.EXPRESSIONS_PAPA_AVATAR:
        errs.append(f"{where}：頭像表情 {av} 不存在")
    return errs


def _cast_errors(where: str, scene: str | None, c: dict, cast: list[dict] | None = None, dur: float = 8.0) -> list[str]:
    errs = []
    who, pose = c.get("who"), c.get("pose")
    if who not in lib.CHARACTERS:
        return [f"{where}：沒有角色 {who}"]
    if pose not in lib.poses(who):
        errs.append(f"{where}：{who} 沒有姿勢 {pose}")
    for key in ("spot", "move_to"):
        v = c.get(key)
        if isinstance(v, str) and scene and v not in lib.spots(scene):
            errs.append(f"{where}：場景 {scene} 沒有站位 {v}")
    if not c.get("spot") and c.get("x") is None:
        errs.append(f"{where}：{who} 要有 spot 或 x/y")
    if c.get("action") and c["action"] not in motion.actions():
        errs.append(f"{where}：沒有動作 {c['action']}（{'/'.join(motion.actions())}）")
    errs += _acting_errors(where, c, cast or [], dur)
    return errs


def _acting_errors(where: str, c: dict, cast: list[dict], dur: float) -> list[str]:
    """表演欄位：表情要存在、動作名在清單、look_at 的對象要在同一鏡。"""
    errs = []
    who = c.get("who")
    if who not in lib.CHARACTERS:
        return errs  # 角色名不對（_cast_errors 已報），表演欄位驗不下去
    pose_ok = c.get("pose") in lib.poses(who)
    for key in ("mood", "mood_to"):
        if c.get(key) and c[key] not in lib.heads(who):
            errs.append(f"{where}：{who} 沒有表情 {c[key]}" + ("（不畫臉）" if not lib.heads(who) else ""))
        elif c.get(key) and pose_ok and c[key] not in lib.pose_expressions(who, c["pose"]):
            avail = "、".join(sorted(lib.pose_expressions(who, c["pose"]))) or "（只有原本的頭）"
            errs.append(f"{where}：{who} 的姿勢 {c['pose']} 沒有 {c[key]} 表情（可用：{avail}）")
    if c.get("eyes") == "closed" and pose_ok and lib.heads(who):
        closed = lib.CLOSED_EYES.get(who)
        if closed not in lib.pose_expressions(who, c["pose"]):
            errs.append(f"{where}：{who} 的姿勢 {c['pose']} 沒有閉眼表情 {closed}")
    if c.get("mood_to") and not c.get("mood_at"):
        errs.append(f"{where}：{who} 換表情要有 mood_at（秒）")
    if c.get("gesture"):
        rig_pose = lib.rig(who)["poses"][c["pose"]] if pose_ok else None
        errs += [f"{where}：{e}" for e in motion.gesture_errors(c["gesture"], who, rig_pose)]
    if c.get("beat"):
        errs += [f"{where}：{e}" for e in motion.beat_errors(c["beat"], who)]
    la = c.get("look_at")
    if la is not None:
        if isinstance(la, str):
            if la != "camera" and not any(o is not c and o.get("who") == la for o in cast):
                errs.append(f"{where}：look_at 的 {la} 不在這一鏡（要是 camera、同鏡的角色或 [x, y]）")
        elif not (isinstance(la, (list, tuple)) and len(la) == 2 and all(isinstance(v, (int, float)) for v in la)):
            errs.append(f"{where}：look_at 要是 camera、角色名或 [x, y]")
    if c.get("eyes") and c["eyes"] not in lib.EYES:
        errs.append(f"{where}：eyes 要是 {'/'.join(lib.EYES)}")
    for key in (*ACT_TIMES, "beat_at"):
        if c.get(key) is not None and not 0 <= float(c[key]) < dur:
            errs.append(f"{where}：{who} 的 {key} 超出鏡頭長度")
    if c.get("mouth") and c["mouth"] not in lib.MOUTHS:
        errs.append(f"{where}：mouth 要是 {'/'.join(lib.MOUTHS)}")
    return errs


def has_event(s: dict) -> bool:
    """鏡頭裡有沒有「會動的事」：角色移動／動作、飄毛、道具進場、表情變化、擬聲字、定格、板子、分割。"""
    if any(s.get(k) is not None and s.get(k) != [] for k in lib.EVENT_KEYS):  # freeze_at 0.0 也算
        return True
    if any(f in ("tufts", "floor_tufts") for f in s.get("fx") or []):
        return True
    if any(c.get("move_to") is not None or c.get("action") or c.get("show") or has_acting(c) for c in s.get("cast") or []):
        return True
    h = s.get("head") or {}
    return bool(h.get("expr_to"))


def has_acting(c: dict) -> bool:
    """角色有沒有表演（換表情、看向、動作、閉眼、說話）。"""
    return any(c.get(k) is not None for k in ("mood_to", "look_at", "gesture", "mouth", "beat")) or c.get("eyes") == "closed"


def _prop_ok(name: str, props: set[str]) -> bool:
    return name in lib.hands() or name in props


def expand_beats(ep: dict) -> dict:
    """cast 的表演套路（beat，assets/papa_home/motion/beats.json）展開成表演欄位；沒有 beat 的分鏡原樣回傳。"""
    if not any(c.get("beat") for s in ep.get("shots") or [] if isinstance(s, dict) for c in s.get("cast") or []):
        return ep
    out = copy.deepcopy(ep)
    for s in out["shots"]:
        cast = s.get("cast") or []
        for k, c in enumerate(cast):
            if not c.get("beat"):
                continue
            who, pose = c.get("who"), c.get("pose")
            exprs = lib.pose_expressions(who, pose) if who in lib.CHARACTERS and pose in lib.poses(who) and lib.heads(who) else set()
            cast[k] = motion.expand_beat(c, exprs)
    return out


def validate(ep: dict, props: set[str] | None = None, full: bool = True) -> list[str]:
    """回傳錯誤清單（空＝通過）。props：可用的道具名（素材包 props/ ＋本集生成的）。"""
    props = props if props is not None else lib.props()
    ep = expand_beats(ep)
    errs: list[str] = []
    try:
        if int(ep.get("episode")) < 1:  # type: ignore[arg-type]
            raise ValueError
    except (TypeError, ValueError):
        errs.append("episode 要是正整數")
    if not isinstance(ep.get("title"), str) or not ep["title"].strip():
        errs.append("title 要有文字")
    if ep.get("music") and ep["music"] not in lib.MUSIC_MODES:
        errs.append(f"music 要是 {'/'.join(lib.MUSIC_MODES)}")
    shots = ep.get("shots") or []
    if not shots:
        return errs + ["沒有鏡頭"]
    if not ep.get("archived"):  # 退役角色（寶寶）只留給封存的舊集數重渲
        used = {c.get("who") for s in shots for c in s.get("cast") or []} | {(s.get("head") or {}).get("who") for s in shots}
        errs += [f"角色 {w} 已退役，新分鏡不能用" for w in sorted(w for w in used if w in lib.CHARACTERS and w not in lib.ACTIVE)]
    types = {s.get("type") for s in shots} - {"TITLE", "END"}
    if len(types) > lib.MAX_TYPES:
        errs.append(f"鏡頭種類 {len(types)} 種，超過 {lib.MAX_TYPES} 種")
    if shots[0].get("type") in ("TITLE", "END"):
        errs.append("第一鏡不能是片頭卡（第 0 格是縮圖，要有角色和一句話）")
    ids = set()
    for k, s in enumerate(shots):
        where = s.get("id") or f"第 {k + 1} 鏡"
        if not s.get("id"):
            errs.append(f"{where}：要有鏡號 id")
        elif s["id"] in ids:
            errs.append(f"{where}：鏡號重複")
        ids.add(s.get("id"))
        t, dur = s.get("type"), float(s.get("dur") or 0)
        if t not in lib.SHOT_TYPES:
            errs.append(f"{where}：沒有鏡頭類型 {t}")
            continue
        if not 0.8 <= dur <= 8:
            errs.append(f"{where}：長度 {dur}s 要在 0.8–8 秒")
        if s.get("act") not in lib.ACTS:
            errs.append(f"{where}：act 要是 {'/'.join(lib.ACTS)}")
        if s.get("seam") and s["seam"] not in lib.SEAMS:
            errs.append(f"{where}：沒有接點 {s['seam']}（{'/'.join(lib.SEAMS)}）")
        if s.get("mood") and s["mood"] not in lib.MOODS:
            errs.append(f"{where}：沒有配樂情緒 {s['mood']}")
        scene = s.get("scene")
        for f in s.get("fx") or []:
            if f not in lib.FX:
                errs.append(f"{where}：沒有效果 {f}")
        if (s.get("head") and t in HEAD_TYPES) or t == "EXPLAIN":
            bg = s.get("scene") or "living"
            if bg not in lib.SCENES:
                errs.append(f"{where}：背景場景 {bg} 不存在")
            elif s.get("bg_spot") and s["bg_spot"] not in lib.spots(bg):
                errs.append(f"{where}：場景 {bg} 沒有站位 {s['bg_spot']}")
        if dur >= lib.STATIC_MIN and t in STATIC_TYPES and not has_event(s):
            errs.append(f"{where}：{dur}s 的 {t} 沒有動作事件（角色移動／動作、飄毛、道具、表情變化、擬聲字、定格…），會像一張投影片")
        if t in SCENE_TYPES - {"REACTION"} and scene not in lib.SCENES:
            errs.append(f"{where}：{t} 要有場景（{'/'.join(lib.SCENES)}）")
        if t in ("CU",) and not s.get("head"):
            errs.append(f"{where}：CU 要有 head")
        if t == "REACTION" and not s.get("head") and not s.get("cast"):
            errs.append(f"{where}：REACTION 要有 head 或 cast")
        if t in ("TRACK",) and not any(c.get("move_to") is not None or c.get("action") == "dive" for c in s.get("cast", [])):
            errs.append(f"{where}：TRACK 要有角色移動（move_to）")
        if t in ("PULLOUT", "POV") and not s.get("cast"):
            errs.append(f"{where}：{t} 要有角色 cast")
        fp = s.get("fur_pile")
        if fp and not fp.get("spot") and (fp.get("x") is None or fp.get("y") is None):
            errs.append(f"{where}：fur_pile 要有 spot 或 x/y")
        elif fp and fp.get("spot") and scene and fp["spot"] not in lib.spots(scene):
            errs.append(f"{where}：場景 {scene} 沒有站位 {fp['spot']}")
        if s.get("demo"):
            try:
                lift, press = float(s["demo"]["lift_at"]), float(s["demo"]["press_at"])
                if not 0 < lift < press < dur:
                    errs.append(f"{where}：示範時間要 0 < lift_at < press_at < 鏡頭長度")
            except (KeyError, TypeError, ValueError):
                errs.append(f"{where}：示範要有 lift_at 與 press_at（秒）")
        if t == "EXPLAIN" and not s.get("sign"):
            errs.append(f"{where}：EXPLAIN 要有板子文字 sign")
        if t == "SPLIT" and len(s.get("split") or []) != 2:
            errs.append(f"{where}：SPLIT 要有上下兩格")
        for c in s.get("cast", []):
            errs += _cast_errors(where, scene, c, s.get("cast", []), dur)
        h = s.get("head")
        if h:
            if h.get("who") not in lib.CHARACTERS or not lib.heads(h["who"]):
                errs.append(f"{where}：{h.get('who')} 沒有頭像")
            else:
                for ex in (h.get("expr"), h.get("expr_to")):
                    if ex and ex not in lib.heads(h["who"]):
                        errs.append(f"{where}：{h['who']} 沒有表情 {ex}")
            lk = h.get("look")
            if lk is not None and not (isinstance(lk, (list, tuple)) and len(lk) == 2 and all(isinstance(v, (int, float)) and -1 <= v <= 1 for v in lk)):
                errs.append(f"{where}：head.look 要是 [sx, sy]，各在 -1～1")
            if h.get("mouth") and h["mouth"] not in lib.MOUTHS:
                errs.append(f"{where}：mouth 要是 {'/'.join(lib.MOUTHS)}")
            if h.get("gesture") and h.get("who") in lib.CHARACTERS:
                errs += [f"{where}：{e}" for e in motion.gesture_errors(h["gesture"], h["who"], None, head_shot=True)]
            for key in ("at", "look_at_at", "gesture_at"):
                if h.get(key) is not None and not 0 <= float(h[key]) < dur:
                    errs.append(f"{where}：head.{key} 超出鏡頭長度")
        for key in ("hand",):
            if s.get(key) and not _prop_ok(s[key].get("prop", ""), props):
                errs.append(f"{where}：沒有道具 {s[key].get('prop')}")
        if s.get("hand") and s["hand"].get("motion") and s["hand"]["motion"] not in motion.hand_motions():
            errs.append(f"{where}：手部特寫沒有動法 {s['hand']['motion']}（{'/'.join(motion.hand_motions())}）")
        if s.get("demo"):
            for key in ("use", "full", "released", "drop"):
                if not _prop_ok(s["demo"].get(key, ""), props):
                    errs.append(f"{where}：示範缺道具 {key}={s['demo'].get(key)}")
        for half in s.get("split") or []:
            if not _prop_ok(half.get("prop", ""), props):
                errs.append(f"{where}：沒有道具 {half.get('prop')}")
        st = s.get("step")
        if st and st.get("source") not in (ep.get("sources") or {}):
            errs.append(f"{where}：步驟字卡的來源 {st.get('source')} 不在 sources")
        for j, line in enumerate(s.get("lines", [])):
            errs += _line_errors(f"{where} 第 {j + 1} 句", line, dur)
        for name, at in s.get("sfx", []):
            if name not in lib.SFX:
                errs.append(f"{where}：沒有音效 {name}")
            if not 0 <= float(at) < dur:
                errs.append(f"{where}：音效 {name} 時間 {at} 超出鏡頭")
        fa = s.get("freeze_at")
        if fa is not None and not 0 <= float(fa) < dur:
            errs.append(f"{where}：定格時間超出鏡頭")
    total = sum(float(s.get("dur") or 0) for s in shots)
    lo, hi = lib.FULL_SECONDS
    if full and not lo <= total <= hi:
        errs.append(f"全片 {total:.1f}s，要在 {lo}–{hi} 秒")
    for c in ep.get("cut") or []:
        if c.get("id") not in ids:
            errs.append(f"精華版：沒有鏡頭 {c.get('id')}")
    return errs


# ── 編譯 ────────────────────────────────────────────────────────────────
def _resolve(scene: str | None, c: dict) -> dict:
    """角色 → 腳底座標與比例。"""
    out = dict(c)
    if c.get("spot") and scene:
        sp = lib.spots(scene)[c["spot"]]
        out.setdefault("x", sp["x"])
        out.setdefault("y", sp["y"])
        out.setdefault("ppc", sp["px_per_cm"])
    out["x"] = float(out["x"]) + float(c.get("dx") or 0)
    out["y"] = float(out["y"])
    out["ppc"] = float(out.get("ppc") or 6.0)
    mt = c.get("move_to")
    if isinstance(mt, str) and scene:
        out["move_to"] = float(lib.spots(scene)[mt]["x"])
    return out


def _separate(cast: list[dict]) -> None:
    """同一個站位的角色左右錯開；同一個角色換姿勢（例：站→聳肩，用 show 接）是同一個人，不錯開。"""
    seen: dict[tuple, list[str]] = {}
    for c in cast:
        key = (round(c["x"]), round(c["y"]))
        whos = seen.setdefault(key, [])
        if c["who"] in whos:
            continue
        n = len(whos)
        if n:
            c["x"] += (1 if n % 2 else -1) * 230 * ((n + 1) // 2) * c["ppc"] / 6
        whos.append(c["who"])


def _touch_on_top(cast: list[dict]) -> None:
    """圖層＝cast 順序（後面的蓋前面）。摸頭、抱這種刻意碰到（touch）的角色要蓋在被碰的上面，不然手會被擋掉。"""
    for c in [c for c in cast if c.get("touch")]:
        targets = [i for i, o in enumerate(cast) if o.get("who") == c["touch"]]
        if targets and cast.index(c) < max(targets):
            cast.remove(c)
            cast.insert(max(targets), c)  # 移除後被碰者往前一格，插在原本的 max(targets)＝緊貼被碰者上方


def _height_px(c: dict) -> float:
    return lib.rig(c["who"])["poses"][c["pose"]]["world_height"] * c["ppc"]


def _clamp(scene: str, cx: float, cy: float, z: float) -> tuple[float, float, float]:
    W, H = lib.scene(scene)["size"]
    z = max(1.0, z)
    return (round(min(max(cx, lib.FW / 2 / z), W - lib.FW / 2 / z), 1),
            round(min(max(cy, lib.FH / 2 / z), H - lib.FH / 2 / z), 1), round(z, 3))


def _camera(s: dict, cast: list[dict]) -> tuple[tuple, tuple, float | None]:
    scene, t = s["scene"], s["type"]
    W, _ = lib.scene(scene)["size"]
    if s.get("cam"):  # 人工覆寫
        a = s["cam"]
        b = a.get("to", a)
        return _clamp(scene, a["x"], a["y"], a["z"]), _clamp(scene, b["x"], b["y"], b["z"]), None
    framing = [c for c in cast if not c.get("show") or float(c["show"][0]) <= 0] or cast  # 中途才進場的角色不算構圖
    xs = [c["x"] for c in framing] or [W / 2]
    feet = [c["y"] for c in framing] or [1800]
    cx = sum(xs) / len(xs)
    if t == "TRACK":
        mover = next((c for c in cast if c.get("move_to") is not None), cast[0])
        x0, x1 = mover["x"], mover.get("move_to", mover["x"])
        cy = mover["y"] - 300
        return _clamp(scene, x0 + (x1 - x0) * 0.25, cy, 1.4), _clamp(scene, x0 + (x1 - x0) * 0.75, cy - 10, 1.4), None
    if t == "POV":
        return _clamp(scene, cx, 1209, 1.35), _clamp(scene, cx + 70, 1209, 1.46), None
    if t == "PULLOUT":
        if not cast:
            return _clamp(scene, W / 2, 1260, 2.2), _clamp(scene, W / 2, 1260, 1.0), 2.6
        f = cast[0]
        return _clamp(scene, f["x"], f["y"] - 150, 2.2), _clamp(scene, cx, 1260, 1.0), 2.6
    if t == "INSERT":
        return _clamp(scene, W / 2 - 20, 1300, 1.7), _clamp(scene, W / 2 - 20, 1300, 1.82), None
    if t == "REACTION":
        z = {1: 2.2, 2: 1.6}.get(len(framing), 1.4)  # 三個以上的角色拉遠一點，才都進框
        cy = sum(feet) / len(feet) - (140 if len(framing) == 1 else 260 if len(framing) == 2 else 220)
        return _clamp(scene, cx, cy, z), _clamp(scene, cx, cy - 10, z * 1.08), None
    span = (max(xs) - min(xs)) + 400
    z = float(s["zoom"]) if s.get("zoom") else min(1.3, max(1.0, lib.FW * 1.25 / span))
    cy = max(feet) - 520
    return _clamp(scene, cx, cy, z), _clamp(scene, cx, cy + 30, z * 1.12), None


def _papa_screen(cast: list[dict], cam: tuple) -> tuple[float, float] | None:
    cx, cy, z = cam
    for c in cast:
        if c["who"] != "papa" or c.get("show"):
            continue
        hx, hy = c["x"], c["y"] - _height_px(c) * 0.85
        sx, sy = (hx - cx) * z + lib.FW / 2, (hy - cy) * z + lib.FH / 2
        if 40 < sx < lib.FW - 40 and 400 < sy < lib.FH - 80:
            return round(sx), round(sy)
    return None


def bubble_pos(target: tuple | None, lines: list[str], avatar: bool, low: bool = False) -> tuple[int, int]:
    """泡泡放在說話者頭上（尾巴指得到的地方）並留在安全區；沒有目標就用固定位置。"""
    if not target:
        return LOW_POS if low else DEFAULT_POS
    w, h = lib.bubble_size(lines, avatar)
    tx, ty = target
    x = int(min(max(tx - w / 2, lib.SAFE["left"]), lib.SAFE["right"] - w))
    y = int(ty - h - 150)
    y = int(min(max(y, lib.SAFE["top"]), lib.SAFE["bottom"] - h))
    return x, y


def _head_world(c: dict) -> tuple[float, float]:
    return c["x"], c["y"] - _height_px(c) * 0.85


def _look_dir(c: dict, cast: list[dict]) -> tuple[float, float] | None:
    """look_at → 畫面方向 (sx, sy)，各 -1～1（camera＝0,0）。"""
    la = c.get("look_at")
    if la is None:
        return None
    if la == "camera":
        return 0.0, 0.0
    if isinstance(la, str):
        other = next((o for o in cast if o is not c and o.get("who") == la), None)
        if other is None:
            return None
        tx, ty = _head_world(other)
    else:
        tx, ty = float(la[0]), float(la[1])
    hx, hy = _head_world(c)
    return (round(max(-1.0, min(1.0, (tx - hx) / lib.LOOK_DIST)), 3), round(max(-1.0, min(1.0, (ty - hy) / lib.LOOK_DIST)), 3))


def _low_cast(c: dict, s: dict, cast: list[dict] | None = None) -> dict:
    out = {k: c[k] for k in ("who", "pose", "x", "y", "ppc") if k in c}
    out["flip"] = bool(c.get("flip"))
    cast = cast or []
    # 表演（分件 rig）
    heads = lib.heads(c["who"])
    expr = c.get("mood") or lib.rig(c["who"])["poses"][c["pose"]].get("expression")
    if heads and c.get("eyes") == "closed":
        expr = lib.CLOSED_EYES.get(c["who"], expr)  # 場景裡閉眼＝換成這個姿勢的閉眼表情
    if heads and expr:
        out["expr"] = expr
    if c.get("mood_to"):
        out["take"] = [c["mood_to"], float(c.get("mood_at") or 0)]
    look = _look_dir(c, cast)
    if look is not None:
        out["look"] = [look[0], look[1], float(c.get("look_at_at") or 0.2)]
    if c.get("gesture"):
        d = 1.0
        if look is not None and look[0] != 0:
            d = 1.0 if look[0] > 0 else -1.0
        elif c.get("flip"):
            d = -1.0
        out["gesture"] = [c["gesture"], float(c.get("gesture_at") or 0.3), d]
    if c.get("mouth") == "talk":  # 頭像泡泡的旁白（avatar）不是畫面裡的人在講，不跟著點頭
        out["talk"] = [[float(line["at"]), float(line["at"]) + float(line["dur"])] for line in s.get("lines", []) if not line.get("avatar")]
    if c.get("move_to") is not None:
        out["move_to"] = c["move_to"]
        out["move_dur"] = c.get("move_dur")
    if c.get("show"):
        out["vis"] = list(c["show"])
    act = c.get("action")
    if act == "hop" or (s["type"] == "TRACK" and c.get("move_to") is not None):
        out["hop"] = True
    if act == "pop_in":
        out["pop_in"] = float(c.get("at") or motion.param("actions", "pop_in", "default_at"))
    if act == "dive":
        at = float(c.get("at") or 0)
        dv = motion.motions_data()["actions"]["dive"]["params"]
        out["arc"] = [float(c.get("dive_dx") or dv["default_dx"]), dv["land"], at, dv["duration"]]
    return out


def _bg(s: dict) -> dict:
    """頭像鏡的背景：場景在某個站位附近、拉近、模糊（engine 畫），讓特寫還在「家裡」。"""
    scene = s.get("scene") or "living"
    sp = lib.spots(scene)[s.get("bg_spot") or "front_center"]
    cam = _clamp(scene, float(sp["x"]), float(sp["y"]) - 520, 1.5)
    return {"scene": scene, "cam": list(cam)}


def compile_shot(s: dict, t0: float, ep: dict) -> dict:
    t, d = s["type"], float(s["dur"])
    low: dict = {"id": s["id"], "t": round(t0, 3), "d": d, "sfx": [list(x) for x in s.get("sfx", [])]}
    scene = s.get("scene")
    head = s.get("head")
    cast: list[dict] = []
    cam = cam_to = None
    if head and t in HEAD_TYPES:
        low["head"] = [head["who"], head["expr"]]
        if head.get("expr_to"):
            low["head_to"] = [head["expr_to"], float(head.get("at") or d / 2)]
        if head.get("look") is not None:
            low["head_look"] = [float(head["look"][0]), float(head["look"][1]), float(head.get("look_at_at") or 0.2)]
        if head.get("gesture"):
            low["head_gesture"] = [head["gesture"], float(head.get("gesture_at") or 0.3)]
        if head["who"] == "papa" and (head.get("mouth") or "talk") == "talk":
            low["head_talk"] = [[float(line["at"]), float(line["at"]) + float(line["dur"])] for line in s.get("lines", []) if not line.get("avatar")]
        low["bg"] = _bg(s)
        low["lines"] = "lines" in (s.get("fx") or [])
    elif scene and t in SCENE_TYPES:
        cast = [_resolve(scene, c) for c in s.get("cast", [])]
        if t == "POV":
            for c in cast:
                c["y"], c["ppc"] = 1990.0, 7.3
        _separate(cast)
        _touch_on_top(cast)
        cam, cam_to, cam_dur = _camera(s, cast)
        low.update(scene=scene, cam=list(cam), cam_to=list(cam_to), cast=[_low_cast(c, s, cast) for c in cast])
        if cam_dur:
            low["cam_dur"] = cam_dur
        if t == "POV":
            low["pov"] = True
        if t == "WHIP":
            low["whip"] = True
        low["near"] = "near" in (s.get("fx") or [])
        fp = s.get("fur_pile")
        if fp:
            if fp.get("spot"):
                sp = lib.spots(scene)[fp["spot"]]
                r = {"x": float(sp["x"]), "y": float(sp["y"])}
            else:
                r = {"x": float(fp.get("x", lib.scene(scene)["size"][0] / 2)), "y": float(fp.get("y", 1800))}
            low["fur_pile"] = [r["x"], r["y"], float(fp.get("size") or 300)]
            if s.get("poof_at") is not None:
                low["poof"] = [r["x"], r["y"] - 100, float(s["poof_at"])]
    if t == "SPLIT":
        low["split"] = [{"prop": h["prop"], "label": h["label"], "good": bool(h.get("good"))} for h in s["split"]]
        low["scene"] = None
        low["split_scene"] = scene or "living"
    if t == "EXPLAIN":
        low["sign"] = list(s["sign"])
        low["bg"] = _bg(s)
    if t == "TITLE":
        low["card"] = "title"
    if t == "END":
        low["card"] = "end"
    if s.get("hand"):
        h = s["hand"]
        low["hand"] = [h["prop"], float(h.get("at") or 0.0)]
        if h.get("top") is not None:
            low["hand_top"] = h["top"]
        if h.get("motion"):
            low["hand_motion"] = h["motion"]
    if s.get("demo"):
        low["demo"] = dict(s["demo"])
    if s.get("step"):
        low["step"] = {k: s["step"][k] for k in ("n", "title", "sub")}
    for key in ("tufts", "floor_tufts"):
        if key in (s.get("fx") or []):
            low[key] = True
    if s.get("hairball_at") is not None:
        low["hairball"] = float(s["hairball_at"])
    if s.get("freeze_at") is not None:
        low["freeze_at"] = float(s["freeze_at"])
    # 擬聲字：輪流放在畫面上方幾個位置
    low["onoma"] = [{"text": o["text"], "at": float(o["at"]), "x": ONOMA_SLOTS[k % 4][0], "y": ONOMA_SLOTS[k % 4][1],
                     "rot": ONOMA_SLOTS[k % 4][2]} for k, o in enumerate(s.get("onoma", []))]
    # 泡泡：帕帕在畫面裡就指向他，不在就放頭像
    # 步驟字卡在上方：泡泡改用下方位置，就算指向帕帕也不高過字卡下緣
    has_step = bool(s.get("step"))
    low_slot = has_step or bool((s.get("hairball_at") is not None or low["onoma"]) and t in HEAD_TYPES)
    target: tuple[float, float] | None = None
    if head and t in HEAD_TYPES and head["who"] == "papa":
        target = HEAD_TARGET
    elif t == "EXPLAIN":
        target = (540, 700)
    elif cam:
        target = _papa_screen(cast, cam_to if t == "PULLOUT" and cam_to else cam)
    if cam and cam_to:
        end_pt = _papa_screen(cast, cam_to)
        if end_pt:
            low["papa_screen"] = list(end_pt)
    bubbles = []
    for line in s.get("lines", []):
        text = list(line["text"])
        pointed = bool(target) and not line.get("avatar")
        pos = list(bubble_pos(target if pointed else None, text, not pointed, low_slot))
        if has_step:
            pos[1] = max(pos[1], STEP_CARD_BOTTOM)
        b = {"text": text, "at": float(line["at"]), "dur": float(line["dur"]), "pos": pos}
        if pointed and target:
            b["target"] = list(target)
        else:
            b["avatar"] = line.get("avatar") or "neutral"
        bubbles.append(b)
    low["bubble"] = [] if ep.get("hide_bubbles") else bubbles  # hide_bubbles：審「關掉字幕看不看得懂」，嘴型照動
    return low


def seam_for(prev: dict | None, cur: dict, prev_low: dict | None) -> str:
    """新鏡怎麼接上一鏡（高階 "seam" 覆寫；否則依鏡頭類型）。"""
    if cur.get("seam"):
        return cur["seam"]
    t = cur["type"]
    if prev is None:
        return "cut"
    if t in ("TITLE", "END"):
        return "dip"
    if t == "WHIP":
        return "whip"
    head = cur.get("head") or {}
    prev_head = bool(prev.get("head")) and prev.get("type") in HEAD_TYPES or prev.get("type") == "EXPLAIN"
    if (t in HEAD_TYPES and head and head.get("who") == "papa") or t == "EXPLAIN":
        if prev_head:
            return "cut"  # 特寫接特寫＝同一場景內的硬切（punch-in）
        return "push" if prev_low and prev_low.get("papa_screen") else "iris"
    if t in ("REACTION", "INSERT", "SPLIT") and (head or not prev_head):
        return "iris"
    if prev_head and t in SCENE_TYPES:
        return "pull"
    return "cut"


def apply_seams(shots: list[dict], lows: list[dict]) -> None:
    """寫入每鏡的 seam（進場）與上一鏡的 seam_out（離場）；iris 的新鏡提早 IRIS_LEAD 開始、疊在上面。"""
    for k, (s, low) in enumerate(zip(shots, lows)):
        prev, prev_low = (shots[k - 1], lows[k - 1]) if k else (None, None)
        seam = seam_for(prev, s, prev_low)
        low["seam"] = seam
        if prev_low is not None:
            prev_low["seam_out"] = seam
            if seam == "push":
                prev_low["push_to"] = list(prev_low.get("papa_screen") or (540, 960))  # 分鏡硬指定 push 但帕帕不在前一鏡：推向畫面中央
        low["z"] = k + 1  # 後面的鏡頭永遠疊在前面的上面（iris 重疊時才看得出）
        if seam == "iris" and prev_low is not None:
            low["lead"] = lib.IRIS_LEAD
            low["layer"] = (prev_low.get("layer", 1) % 2) + 1  # 重疊的兩鏡放不同軌
        else:
            low["layer"] = 1


def _screen_rect(c: dict, cam: tuple | list) -> tuple[float, float, float, float]:
    """角色在畫面上的矩形（x0, y0, x1, y1）。"""
    cx, cy, z = cam
    e = lib.rig(c["who"])["poses"][c["pose"]]
    k = e["world_height"] * c["ppc"] / (e["bbox"][3] - e["bbox"][1])
    bx0, by0, bx1, by1 = e["bbox"]
    left, top = c["x"] - 512 * k, c["y"] - 960 * k
    return ((left + bx0 * k - cx) * z + lib.FW / 2, (top + by0 * k - cy) * z + lib.FH / 2,
            (left + bx1 * k - cx) * z + lib.FW / 2, (top + by1 * k - cy) * z + lib.FH / 2)


def _shot_acts(s: dict) -> bool:
    """鏡頭裡有人在演：角色表演或移動、頭像鏡換表情或說話。"""
    if any(has_acting(c) or c.get("move_to") is not None or c.get("action") for c in s.get("cast") or []):
        return True
    h = s.get("head") or {}
    if h and (h.get("expr_to") or h.get("look") is not None or h.get("gesture") or (h.get("who") == "papa" and h.get("mouth") != "still")):
        return True
    return bool(s.get("hand") or s.get("demo"))


def review(ep: dict) -> list[str]:
    """審片前的警告（不擋渲染）：試映回饋裡一再出現、程式算得出來的毛病。
    中途進場的角色一開始就在畫框內（憑空出現）、角色在鏡頭結束前消失（憑空不見）、兩個角色大面積重疊（像疊在一起）。"""
    warns: list[str] = []
    ep = expand_beats(ep)
    low = compile_episode(ep)
    for hi, lo in zip(ep["shots"], low["shots"]):
        if hi.get("lines") and hi.get("type") not in ("EXPLAIN", "TITLE", "END") and not _shot_acts(hi):
            warns.append(f"{hi['id']}：有台詞卻沒有任何動作（角色沒有 gesture／look_at／mood_to／mouth、也沒移動），關掉字幕就看不懂；"
                         f"至少讓說話的人嘴動（mouth: talk）或給一個動作")
        cam = lo.get("cam")
        if not cam or not lo.get("cast"):
            continue
        where, dur = hi["id"], float(hi["dur"])
        rects = []
        hi_cast = list(hi.get("cast", []))
        _touch_on_top(hi_cast)  # 編譯時 touch 的角色排到後面（圖層），配對要用同一個順序
        for c_hi, c_lo in zip(hi_cast, lo["cast"]):
            show = c_hi.get("show")
            x0, y0, x1, y1 = _screen_rect(c_lo, cam)
            handed_over = show and any(o is not c_hi and o.get("who") == c_hi.get("who") and o.get("show")
                                       and abs(float(o["show"][1]) - float(show[0])) < 0.1 for o in hi.get("cast", []))
            if (show and float(show[0]) > 0 and x1 > 0 and x0 < lib.FW and c_hi.get("action") != "pop_in" and not handed_over):
                warns.append(f"{where}：{c_lo['who']} 在 {show[0]}s 才進場，但起點已在畫框內（x {x0:.0f}–{x1:.0f}），會憑空出現；"
                             f"起點放到畫框外用 move_to 進來，或改 action pop_in")
            if show and float(show[1]) < dur - 0.05:
                taken_over = any(o is not c_hi and o.get("who") == c_hi.get("who") and o.get("show")
                                 and abs(float(o["show"][0]) - float(show[1])) < 0.1 for o in hi.get("cast", []))
                if not taken_over:
                    warns.append(f"{where}：{c_lo['who']} 在 {show[1]}s 消失、鏡頭 {dur}s 才結束，會憑空不見；show 延到鏡尾或接下一個姿勢")
            if not show or float(show[0]) <= 0:
                rects.append((c_lo["who"], (x0, y0, x1, y1)))
        touching = {(c.get("who"), c.get("touch")) for c in hi.get("cast", []) if c.get("touch")}  # 刻意碰到（摸頭、抱）不算疊在一起
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                (wa, a), (wb, b) = rects[i], rects[j]
                if (wa, wb) in touching or (wb, wa) in touching:
                    continue
                ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
                iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
                small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                if small > 0 and ix * iy / small > 0.5:
                    warns.append(f"{where}：{wa} 與 {wb} 重疊超過一半，會像疊在一起；拉開 x 或 y")
    return warns


def _media_start(mood: str, seg_len: float, used: dict[str, float], lengths: dict[str, float] | None) -> float:
    """一段配樂從曲子的第幾秒開始播：同一首接上次停的地方，放不下整段就從頭；主題曲每次從頭。music_plan 與 snap_to_beats 共用。"""
    start = 0.0 if mood == "theme" else used.get(mood, 0.0)
    length = (lengths or {}).get(mood)
    if length and start + seg_len > length:
        start = 0.0
    return start


def music_plan(shots: list[dict], moods: list[str], lengths: dict[str, float] | None = None) -> list[dict]:
    """連續同情緒的鏡頭接成一段配樂；同一首再出現時從上次停的地方接（主題曲每次從頭）。"""
    segs: list[dict] = []
    for s, mood in zip(shots, moods):
        if segs and segs[-1]["mood"] == mood:
            segs[-1]["d"] = round(s["t"] + s["d"] - segs[-1]["t"], 3)
        else:
            segs.append({"mood": mood, "t": s["t"], "d": s["d"]})
    used: dict[str, float] = {}
    out = []
    for k, g in enumerate(segs):
        start = _media_start(g["mood"], g["d"], used, lengths)
        used[g["mood"]] = start + g["d"]
        out.append({"id": f"m{k + 1}", "mood": g["mood"], "t": g["t"], "d": g["d"], "media_start": round(start, 3),
                    "fade_in": 0.0 if k == 0 else 0.25, "fade_out": 2.0 if k == len(segs) - 1 else 0.4})
    return out


def shot_moods(ep: dict, music_lengths: dict[str, float] | None = None) -> list[str]:
    """每鏡的配樂：single 模式（預設）片頭片尾主題曲、其餘一律 bed；沒有 bed 檔或指定 moods 才依幕換曲。"""
    moods = [s.get("mood") or ACT_MOOD.get(s.get("act", ""), "daily") for s in ep["shots"]]
    mode = ep.get("music") or "single"
    if mode == "single" and (music_lengths is None or "bed" in music_lengths):
        return ["theme" if m == "theme" else "bed" for m in moods]
    return moods


def compile_episode(ep: dict, music_lengths: dict[str, float] | None = None) -> dict:
    """高階 → 低階（engine.write_project 的輸入）。"""
    ep = expand_beats(ep)
    shots, t = [], 0.0
    moods = shot_moods(ep, music_lengths)
    for s in ep["shots"]:
        shots.append(compile_shot(s, t, ep))
        t += float(s["dur"])
    apply_seams(ep["shots"], shots)
    return {"episode": int(ep["episode"]), "title": ep["title"], "teaser": ep.get("teaser", ""), "shots": shots,
            "music": music_plan(shots, moods, music_lengths), "total": round(t, 3)}


def _min_dur(s: dict) -> float:
    """鏡頭最短可以縮到多少：泡泡讀完、示範／定格／擬聲／毛球都還在鏡頭裡。"""
    need = 0.8
    for line in s.get("lines", []):
        need = max(need, float(line["at"]) + float(line["dur"]))
    for key in ("freeze_at", "hairball_at", "poof_at"):
        if s.get(key) is not None:
            need = max(need, float(s[key]) + 0.5)
    for o in s.get("onoma", []):
        need = max(need, float(o["at"]) + 1.0)
    if s.get("demo"):
        need = max(need, float(s["demo"]["press_at"]) + 1.0)
    for _, at in s.get("sfx", []):
        need = max(need, float(at) + 0.1)
    return need


def snap_to_beats(ep: dict, beats: dict[str, list[float]], lengths: dict[str, float] | None = None) -> dict:
    """鏡頭結尾往配樂拍點挪（library.BEAT_SNAP 範圍內、不挪壞泡泡與示範）；片尾卡不動。回傳新的高階分鏡。"""
    if not beats:
        return ep
    out = copy.deepcopy(ep)
    shots = out["shots"]
    moods = shot_moods(ep, lengths)
    t, seg_mood, seg_t0, used, media_start = 0.0, None, 0.0, {}, 0.0
    for k, s in enumerate(shots):
        mood = moods[k]
        if mood != seg_mood:
            if seg_mood is not None:
                used[seg_mood] = media_start + (t - seg_t0)
            seg_mood, seg_t0 = mood, t
            seg_len = 0.0  # 這段還沒挪過的長度，和 music_plan 一樣決定從頭或接著播
            for j in range(k, len(shots)):
                if moods[j] != mood:
                    break
                seg_len += float(shots[j]["dur"])
            media_start = _media_start(mood, seg_len, used, lengths)
        dur = float(s["dur"])
        grid = beats.get(mood) or []
        length = (lengths or {}).get(mood)
        if grid and k < len(shots) - 1 and s.get("type") != "END":
            track_end = media_start + (t + dur - seg_t0)
            lo, hi = lib.BEAT_SNAP
            cands = [b for b in grid if lo <= b - track_end <= hi and (not length or b <= length)]
            if cands:
                b = min(cands, key=lambda x: abs(x - track_end))
                new = round(dur + (b - track_end), 3)
                if new >= max(_min_dur(s), 0.8) and new <= 8:
                    s["dur"] = new
                    dur = new
        t += dur
    return out


def cut_episode(ep: dict) -> dict:
    """精華版：照 ep["cut"] 挑鏡頭、改長度；超出新長度的泡泡和音效刪掉或縮短。"""
    ep = expand_beats(ep)
    by_id = {s["id"]: s for s in ep["shots"]}
    shots = []
    for c in ep["cut"]:
        if c.get("id") not in by_id:
            raise ValueError(f"精華版引用不存在的鏡頭 {c.get('id')}")
        s = copy.deepcopy(by_id[c["id"]])
        d = float(c.get("dur") or s["dur"])
        s["dur"] = d
        if "lines" in c:
            s["lines"] = c["lines"]
        lines = []
        for line in s.get("lines", []):
            if line["at"] + 1.0 > d:
                continue
            line = dict(line, dur=min(line["dur"], round(d - line["at"], 3)))
            lines.append(line)
        s["lines"] = lines
        s["sfx"] = [x for x in s.get("sfx", []) if x[1] < d]
        if s.get("freeze_at") is not None and s["freeze_at"] >= d:
            s.pop("freeze_at")
        old = float(by_id[c["id"]]["dur"])
        if s.get("demo") and d < old:
            k = d / old
            s["demo"] = dict(s["demo"], lift_at=round(s["demo"]["lift_at"] * k, 2), press_at=round(s["demo"]["press_at"] * k, 2))
        for key in ("hairball_at", "poof_at"):
            if s.get(key) is not None and s[key] >= d - 0.3:
                s.pop(key)
        for c in s.get("cast", []):
            if c.get("mood_at") is not None and float(c["mood_at"]) >= d - 0.3:
                c.pop("mood_to", None)
                c.pop("mood_at", None)
            for key, time_key in (("gesture", "gesture_at"), ("look_at", "look_at_at")):
                if c.get(time_key) is not None and float(c[time_key]) >= d - 0.3:
                    c.pop(key, None)
                    c.pop(time_key, None)
        h = s.get("head")
        if h:
            for key, time_key in (("gesture", "gesture_at"), ("look", "look_at_at"), ("expr_to", "at")):
                if h.get(time_key) is not None and float(h[time_key]) >= d - 0.3:
                    h.pop(key, None)
                    h.pop(time_key, None)
        shots.append(s)
    return {**ep, "shots": shots, "cut": []}
