"""《帕帕貝貝家》動作庫：物種骨架（assets/papa_home/motion/species.json）、零件動作（assets/papa_home/motion/motions.json）、表演套路（assets/papa_home/motion/beats.json）。

分鏡只寫動作名；這裡把動作名展開成 GSAP tween（engine 照抄進時間軸），把套路展開成 cast 欄位（compile 用）。
加新動作、新套路只改 JSON，不用改程式；格式見 skills/papa-home-motion/references/adding-motions.md。

零件動作的 step：
    {"part": role, "at": 秒, "to": {...GSAP vars}, "from": {...}（有＝fromTo）}
    {"part": role, "at": 秒, "back": 秒}                       回到原位（rotation／xPercent／yPercent 歸零）
    {"repeat": n, "every": 秒, "at": 秒, "steps": [...]}       重複 n 次，第 k 次的時間＝(t＋at)＋k×every＋step.at
值可以寫數字、"7*dir"（乘方向，向右 1、向左 −1）、"1.3*alt"（重複時正負交替，第 0 次為負）、"+=0.5"（相對值，原樣給 GSAP）。
part 缺的時候（姿勢沒有第二隻手、頭像鏡沒有身體）那一步略過。
"""
from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "assets" / "papa_home" / "motion"
VALUE_RE = re.compile(r"^(-?\d+(?:\.\d+)?)((?:\*(?:dir|alt))*)$")
BACK = {"rotation": 0, "xPercent": 0, "yPercent": 0}


@cache
def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def species_data() -> dict:
    return _load("species.json")


def motions_data() -> dict:
    return _load("motions.json")


def beats_data() -> dict:
    return _load("beats.json")["beats"]


def gestures() -> dict[str, dict]:
    return motions_data()["gestures"]


def actions() -> dict[str, dict]:
    return motions_data()["actions"]


def hand_motions() -> dict[str, dict]:
    return motions_data()["hand_motions"]


def param(group: str, name: str, key: str) -> Any:
    """actions／ambient 的參數（engine、compile 讀）。"""
    return motions_data()[group][name]["params"][key]


def character(who: str) -> dict:
    return species_data()["characters"][who]


def species_of(who: str) -> str:
    return character(who)["species"]


def closed_eyes(who: str) -> str | None:
    return character(who).get("closed_eyes")


def tail_wag_period(who: str) -> float:
    return float(character(who).get("tail_wag_period") or 0.7)


def head_gestures() -> tuple[str, ...]:
    """頭像鏡（只有頭）能做的動作。"""
    return tuple(n for n, g in gestures().items() if g.get("head_shot"))


def pose_roles(rig_pose: dict, who: str) -> set[str]:
    """這個姿勢有哪些零件角色（依物種的 role→part 對照與 rig 實際拆出來的零件）。"""
    parts = rig_pose.get("parts") or {}
    mapping = species_data()["species"][species_of(who)]["parts"]
    roles = {r for r, p in mapping.items() if (p == "tail" and rig_pose.get("tail")) or (p != "tail" and parts.get(p))}
    if "arm_a" in roles or "arm_b" in roles:
        roles.add("arm_lead")
    return roles


def gesture_errors(name: str, who: str, rig_pose: dict | None, head_shot: bool = False) -> list[str]:
    """這個角色（這個姿勢）能不能做這個動作；回傳問題（空＝可以）。"""
    g = gestures().get(name)
    if g is None:
        pool = head_gestures() if head_shot else tuple(gestures())
        return [f"沒有動作 {name}（{'/'.join(pool)}）"]
    if head_shot and not g.get("head_shot"):
        return [f"頭像鏡只能做 {'/'.join(head_gestures())}，沒有 {name}"]
    sp = species_of(who)
    if sp not in g["species"]:
        return [f"{who}（{species_data()['species'][sp]['label']}）不能做 {name}"]
    if rig_pose is not None and not head_shot:
        missing = [r for r in g.get("needs", []) if r not in pose_roles(rig_pose, who)]
        if missing:
            return [f"{who} 這個姿勢沒有 {'/'.join(missing)}，做不了 {name}"]
        if rig_pose.get("head_locked") and _moves(g["steps"], "head"):
            return [f"{who} 這個姿勢的頭不能動（頭和前腳畫在一起，一動會變四隻腳），做不了 {name}"]
    return []


def _moves(steps: list[dict], role: str) -> bool:
    return any(_moves(st["steps"], role) if "repeat" in st else st.get("part") == role for st in steps)


def _value(v: Any, d: float, alt: float) -> Any:
    if not isinstance(v, str):
        return v
    m = VALUE_RE.match(v)
    if not m:
        return v  # "+=0.5" 這類相對值或 ease 名原樣給 GSAP
    out = float(m.group(1))
    num = int(out) if out.is_integer() and "." not in m.group(1) else out
    for op in re.findall(r"\*(dir|alt)", m.group(2)):
        num = num * (d if op == "dir" else alt)
    return num


def _vars(spec: dict, d: float, alt: float) -> dict:
    return {k: _value(v, d, alt) for k, v in spec.items()}


def _target(role: str, refs: dict, d: float) -> str | None:
    if role == "arm_lead":
        a, b = refs.get("arm_a"), refs.get("arm_b")
        return (b or a) if d > 0 else (a or b)
    return refs.get(role)


def _expand(steps: list[dict], base: float, d: float, refs: dict, alt: float, out: list) -> None:
    for st in steps:
        if "repeat" in st:
            start = base + st.get("at", 0)
            for k in range(int(st["repeat"])):
                _expand(st["steps"], start + k * st["every"], d, refs, 1.0 if k % 2 else -1.0, out)
            continue
        sel = _target(st["part"], refs, d)
        if not sel:
            continue
        at = base + st.get("at", 0)
        if "back" in st:
            out.append(["to", sel, {**BACK, "duration": st["back"], "ease": "power2.inOut"}, at])
        elif "from" in st:
            out.append(["fromTo", sel, _vars(st["from"], d, alt), _vars(st["to"], d, alt), at])
        else:
            out.append(["to", sel, _vars(st["to"], d, alt), at])


def amplitude(who: str | None) -> tuple[float, float]:
    """物種的動作幅度 (head_shift, arm_scale)：頭的平移、手的旋轉乘上多少（species.json；沒寫＝1）。
    小孩的頭是圓的、脖子短，頭一平移就露出脖子的縫；短袖手轉太開肩膀接縫會露出來（2026-11-05 第 1 集重製）。"""
    if not who or who not in species_data()["characters"]:
        return 1.0, 1.0
    sp = species_data()["species"][species_of(who)]
    return float(sp.get("head_shift", 1.0)), float(sp.get("arm_scale", 1.0))


def _scale(v, f: float):
    if f == 1.0:
        return v
    if isinstance(v, (int, float)):
        return round(v * f, 4)
    if isinstance(v, str) and v[:2] in ("+=", "-="):
        return f"{v[:2]}{round(float(v[2:]) * f, 4)}"
    return v


def calls(name: str, t: float, d: float, refs: dict, who: str | None = None) -> list[list]:
    """動作 → GSAP 呼叫清單 [method, selector, vars(, toVars), position]。refs：role → CSS 選擇器（沒有就 None）。
    who：照該角色物種的幅度縮放頭的平移與手的旋轉（amplitude）。"""
    out: list[list] = []
    _expand(gestures()[name]["steps"], t, d, refs, -1.0, out)
    head_f, arm_f = amplitude(who)
    if head_f == 1.0 and arm_f == 1.0:
        return out
    arms = {refs.get(r) for r in ("arm_a", "arm_b", "arm_lead")} - {None}
    for c in out:
        keys = ("xPercent", "yPercent") if c[1] == refs.get("head") else ("rotation",) if c[1] in arms else ()
        f = head_f if c[1] == refs.get("head") else arm_f
        for v in c[2:-1]:
            for k in keys:
                if k in v:
                    v[k] = _scale(v[k], f)
    return out


def calls_js(name: str, t: float, d: float, refs: dict, who: str | None = None) -> str:
    """engine 用：play([...]) 一行。"""
    return f"play({json.dumps(calls(name, t, d, refs, who), ensure_ascii=False, separators=(',', ':'))});"


# ── 表演套路 ───────────────────────────────────────────────────────────────
BEAT_TIME = {"gesture": "gesture_at", "mood_to": "mood_at"}


def beat_errors(name: str, who: str) -> list[str]:
    b = beats_data().get(name)
    if b is None:
        return [f"沒有表演套路 {name}（{'/'.join(beats_data())}）"]
    if species_of(who) not in b["species"]:
        return [f"{who} 不能演 {name}（{b['label']}）"]
    return []


def expand_beat(c: dict, pose_exprs: set[str] | None = None) -> dict:
    """cast 的 beat → 展開成表演欄位（cast 自己寫的欄位優先；這個姿勢沒有的表情就不換臉）。"""
    name = c.get("beat")
    b = beats_data().get(name or "")
    if not b or c.get("who") not in species_data()["characters"] or species_of(c["who"]) not in b["species"]:
        return c  # 名字或物種不對：留給驗證報錯
    out = dict(c)
    at = float(c.get("beat_at") if c.get("beat_at") is not None else 0.3)
    for key, val in b["set"].items():
        if key in ("mood", "mood_to") and isinstance(val, dict):
            val = val.get(c["who"])
            if val is None or (pose_exprs is not None and val not in pose_exprs):
                continue
        if key == "eyes" and pose_exprs is not None and closed_eyes(c["who"]) not in pose_exprs:
            continue
        if out.get(key) is not None:
            continue
        out[key] = val
        tk = BEAT_TIME.get(key)
        if tk and out.get(tk) is None:
            out[tk] = at
    return out
