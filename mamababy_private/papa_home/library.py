"""《帕帕貝貝家》固定素材與鏡頭庫：分鏡只能從這裡挑（docs/papa-home-series.md §4–§7）。"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from mamababy_private.papa_home import motion

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "papa_home"
FW, FH = 1080, 1920
HYPERFRAMES = "hyperframes@0.9.8"
SERIES_TITLE = "帕帕貝貝家"  # 片頭片尾的片名（呼應店名 PapaBaby；程式代號 papa_home）

CHARACTERS = ("papa", "beibei", "dad", "mom", "sister", "brother", "baby")  # 有素材的全部角色（baby 已退役，只留給封存的舊第 1 集）
SCENES = ("living", "nursery", "kitchen")

# 鏡頭庫（企劃 §4）＋片頭／片尾卡
SHOT_TYPES = {
    "WIDE": "全景：交代場景，慢推",
    "CU": "特寫：角色頭像反應格（帕帕吐槽、驚訝）",
    "TRACK": "跟拍：角色橫越畫面，三層視差",
    "INSERT": "道具特寫：手部特寫或道具（梳子、吸塵器）",
    "REACTION": "反應：貝貝或寶寶的頭像或全身，硬切",
    "EXPLAIN": "帕帕舉板子講解",
    "WHIP": "甩鏡進場的全景",
    "PULLOUT": "拉遠：結尾全家入鏡",
    "POV": "貓視角：從沙發底下看出去",
    "SPLIT": "上下對照：錯 vs 對",
    "TITLE": "片頭卡",
    "END": "片尾卡＋下集預告",
}
MAX_TYPES = 10  # 一集最多用幾種鏡頭（片頭、片尾不算；試播集用了 10 種並通過）

# 分幕 → 配樂情緒（企劃 §6）
ACTS = ("cold", "title", "act1", "act2", "act3", "close")
MOODS = ("theme", "daily", "trouble", "solution", "twist", "bed")  # bed＝整集一首連貫底樂（2026-11-04 試映：分幕換曲像拼的）
MUSIC_MODES = ("single", "moods")  # single：片頭片尾主題曲、其餘全用 bed；moods：依幕換曲（bed 缺檔時的退路）
SFX = ("scratch", "bark", "giggle", "gag", "whimper", "vacuum", "brush", "steps", "click", "pop", "whoosh", "purr")
FX = ("tufts", "floor_tufts", "near", "lines")  # 飄毛、地上毛團被吸走、前景遮擋、漫畫集中線（只給驚訝那一鏡）
FULL_SECONDS = (45, 120)  # 正片長度（2026-11-04 試映回饋「太長」後從 60–120 改成 45–120，目標 55–65）
STATIC_MIN = 3.0  # 這麼長的鏡頭至少要有一個明確的動作事件（角色移動、道具、表情變化…），不能只是一張圖配字
SEAMS = ("cut", "push", "pull", "iris", "whip", "dip")  # 接點：硬切／推進特寫／拉回場景／圓場／甩鏡／暗一下再切
IRIS_LEAD = 0.22  # 圓場：新鏡提早這麼久疊在舊鏡上面開圓
BEAT_SNAP = (-0.15, 0.35)  # 鏡頭結尾往最近的拍點挪，允許提前／延後的秒數
EVENT_KEYS = ("hand", "demo", "hairball_at", "poof_at", "onoma", "freeze_at", "sign", "split")  # 鏡頭層級的動作事件
# 角色表演（分件 rig，2026-11-04 業主回饋「沒看字不知道要表達什麼」後加）：分鏡在 cast 裡寫，engine 用零件演
GESTURES = {name: g["desc"] for name, g in motion.gestures().items()}  # 動作庫在 assets/papa_home/motion/motions.json（motion.py）
EYES = ("open", "closed")
MOUTHS = ("talk", "still")
LOOK_DIST = 600  # 看向目標：距離達這麼多世界 px 時頭與瞳孔轉到底

# 畫面文字（企劃 §7）
LINE_MAX_CHARS = 10
LINE_MAX_ROWS = 2
READ_CHARS_PER_SEC = 5  # 只算字（中英數），不算標點與空格
MIN_HOLD = 1.2
LINE_GAP = 0.3  # 兩行泡泡第二行晚這麼久出現（分兩拍）
SAFE = {"left": 60, "right": 850, "top": 168, "bottom": 1330}  # 文字安全區（右側 230px 留給平台 UI）
BUBBLE_FONT, BUBBLE_LINE = 64, 80
EXPRESSIONS_PAPA_AVATAR = ("neutral", "unimpressed", "surprised", "smug", "soft")


@cache
def rig(character: str) -> dict:
    """角色 rig.json（姿勢、頭像、尾巴錨點）。"""
    return json.loads((ASSETS / "characters" / character / "rig.json").read_text(encoding="utf-8"))


@cache
def scene(name: str) -> dict:
    """場景 scene.json（尺寸、圖層、站位點）。"""
    return json.loads((ASSETS / "scenes" / name / "scene.json").read_text(encoding="utf-8"))


def poses(character: str) -> list[str]:
    return list(rig(character)["poses"])


def heads(character: str) -> list[str]:
    return list(rig(character).get("heads", {}))


ACTIVE = tuple(c for c in CHARACTERS if not motion.character(c).get("retired"))  # 寫新分鏡能用的角色
CLOSED_EYES = {who: e for who in CHARACTERS if (e := motion.closed_eyes(who))}  # 場景裡「閉眼」＝換成這個角色的閉眼表情（assets/papa_home/motion/species.json）


def pose_expressions(character: str, pose: str) -> set[str]:
    """這個姿勢在場景裡可以用的表情：原圖自己的表情＋對齊過的姿勢專用表情頭（papa_pose_heads 產生、逐張驗證）。"""
    e = rig(character)["poses"][pose]
    head = (e.get("parts") or {}).get("head") or {}
    out = set(head.get("expressions") or {})
    if e.get("expression"):
        out.add(e["expression"])
    return out


def pose_avatar(character: str, pose: str) -> bool:
    """這個姿勢在場景裡能換表情（有姿勢專用表情頭）。"""
    return len(pose_expressions(character, pose)) > 1


def spots(scene_name: str) -> dict[str, dict]:
    return scene(scene_name)["spots"]


def hands() -> list[str]:
    data = json.loads((ASSETS / "characters" / "hands" / "rig.json").read_text(encoding="utf-8"))
    return list(data["files"])


def hand_labels() -> dict[str, str]:
    """手部特寫的中文說明（rig.json 的 labels），寫分鏡的人才知道每張畫的是什麼。"""
    data = json.loads((ASSETS / "characters" / "hands" / "rig.json").read_text(encoding="utf-8"))
    return data.get("labels") or {}


def props() -> set[str]:
    """素材包裡的通用道具（props/*.webp，不含副檔名）。"""
    return {p.stem for p in (ASSETS / "props").glob("*.webp")}


def menu() -> str:
    """給 LLM 的素材清單（可用的鏡頭、場景站位、姿勢、表情、音效）。"""
    lines = ["鏡頭：" + "；".join(f"{k}={v}" for k, v in SHOT_TYPES.items())]
    for sc in SCENES:
        lines.append(f"場景 {sc} 站位：" + "、".join(spots(sc)))
    for ch in ACTIVE:
        hs = heads(ch)
        lines.append(f"{ch} 姿勢：" + "、".join(poses(ch)) + (f"；頭像表情：{'、'.join(hs)}" if hs else "（不畫臉）"))
    labels = hand_labels()
    lines.append("手部特寫：" + "、".join(f"{h}（{labels[h]}）" if h in labels else h for h in hands()))
    lines.append("道具：" + "、".join(sorted(p for p in props() if not p.startswith(("tuft_", "paper")))))
    lines.append("音效：" + "、".join(SFX))
    sp = motion.species_data()["species"]
    for name, g in motion.gestures().items():
        tag = "（試用）" if g.get("status") == "draft" else ""
        head = "；頭像鏡可用" if g.get("head_shot") else ""
        lines.append(f"動作 gesture {name}{tag}：{g['label']}，{g['desc']}（{'、'.join(sp[x]['label'] for x in g['species'])}{head}）")
    lines.append("整隻動作 action：" + "；".join(f"{n}={a['label']}" for n, a in motion.actions().items()))
    for name, b in motion.beats_data().items():
        tag = "（試用）" if b.get("status") == "draft" else ""
        lines.append(f"表演套路 beat {name}{tag}：{b['label']}，{b['desc']}")
    return "\n".join(lines)


def bubble_size(lines: list[str], avatar: bool) -> tuple[int, int]:
    """對話泡泡的寬高（px）：compile 算位置、engine 畫框都用這個。"""
    n = max((len(line) for line in lines), default=1)
    w = min(790, n * BUBBLE_FONT + 96 + (130 if avatar else 0))
    h = len(lines) * BUBBLE_LINE + 80
    return w, h
