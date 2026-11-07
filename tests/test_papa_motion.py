"""《帕帕貝貝家》動作庫：物種骨架、零件動作、表演套路的資料都對得上 rig；第 1 集改寫後畫面不變；skill 文件是最新的。"""
import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest
from mamababy_private.papa_home import compile as comp
from mamababy_private.papa_home import library as lib
from mamababy_private.papa_home import motion, skill_docs

_spec = importlib.util.spec_from_file_location("papa_golden", Path(__file__).with_name("papa_golden.py"))
papa_golden = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(papa_golden)
ROLES = set(motion.species_data()["roles"])


def _steps(steps):
    for st in steps:
        if "repeat" in st:
            yield from _steps(st["steps"])
        else:
            yield st


# ── 第 1 集畫面不變 ────────────────────────────────────────────────────────
@pytest.mark.skipif(papa_golden.node() is None, reason="需要 node 跑 GSAP 軌跡")
def test_ep01_renders_identically():
    """每鏡 DOM＋GSAP 呼叫軌跡＋低階分鏡都和改寫前（fixtures/papa_ep01_golden.json）一樣＝每一格畫面一樣。"""
    golden = json.loads(papa_golden.GOLDEN.read_text(encoding="utf-8"))
    now = papa_golden.traces(papa_golden.ep01())
    diff = {k: (golden[k], now.get(k)) for k in golden if golden[k] != now.get(k)}
    assert not diff, f"第 1 集畫面變了（確定要變才跑 papa_golden.py --write）：{diff}"


def test_ep01_compiles_and_validates():
    ep = papa_golden.ep01()
    assert comp.validate(ep) == []
    assert comp.expand_beats(ep) is ep  # 沒有套路的分鏡原樣通過


# ── 物種骨架 ──────────────────────────────────────────────────────────────
def test_every_character_has_a_species_and_mapped_parts_exist():
    data = motion.species_data()
    members = {m: s for s, sp in data["species"].items() for m in sp["members"]}
    assert set(members) == set(lib.CHARACTERS) == set(data["characters"])
    for who, ch in data["characters"].items():
        assert members[who] == ch["species"], who
        sp = data["species"][ch["species"]]
        assert set(sp["parts"]) <= ROLES
        assert bool(lib.heads(who)) == sp["face"], who
        for pose, e in lib.rig(who)["poses"].items():
            roles = motion.pose_roles(e, who)
            assert {"head", "body", "arm_a"} <= roles, (who, pose)
            if sp["tail"] and "tail" in e:
                assert "tail" in roles
        if ch.get("closed_eyes"):
            assert ch["closed_eyes"] in lib.heads(who)


# ── 零件動作 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(motion.gestures()))
def test_gesture_resolves_for_every_character_it_claims(name):
    g = motion.gestures()[name]
    assert g["status"] in ("approved", "draft")
    assert set(g["needs"]) <= ROLES and "lids" not in g["needs"]
    for st in _steps(g["steps"]):
        assert st["part"] in ROLES, st
        assert "to" in st or "back" in st, st
        for k, v in {**st.get("to", {}), **st.get("from", {})}.items():
            if isinstance(v, str) and k != "ease":
                assert motion.VALUE_RE.match(v) or re.match(r"^[+-]=\d", v), f"{name}：{k}={v} 看不懂"
    for sp in g["species"]:
        for who in motion.species_data()["species"][sp]["members"]:
            ok = [p for p in lib.poses(who) if not motion.gesture_errors(name, who, lib.rig(who)["poses"][p])]
            assert ok, f"{name} 說 {sp} 能用，但 {who} 沒有一個姿勢做得出來"
            for pose in ok:
                e = lib.rig(who)["poses"][pose]
                refs = {r: f"#{r}" for r in motion.pose_roles(e, who) if r != "arm_lead"}
                calls = motion.calls(name, 0.5, -1.0, refs)
                assert calls, (name, who, pose)
                assert all(c[0] in ("to", "fromTo") and c[-1] >= 0.3 for c in calls)
    if g.get("head_shot"):
        assert motion.calls(name, 0.5, 1, {"head": "#hg", "lids": None}), name


def test_gesture_errors():
    stand = lib.rig("dad")["poses"]["stand"]
    assert motion.gesture_errors("shrug", "dad", stand) == []
    assert "不能做" in motion.gesture_errors("wag_fast", "dad", stand)[0]  # 大人沒有尾巴這個物種能力
    dive = lib.rig("beibei")["poses"]["dive"]
    assert "沒有 tail" in motion.gesture_errors("wag_fast", "beibei", dive)[0]  # 撲的姿勢沒有尾巴圖
    assert "頭像鏡只能做" in motion.gesture_errors("shrug", "papa", None, head_shot=True)[0]
    assert "沒有動作" in motion.gesture_errors("moonwalk", "papa", None)[0]


def test_values_follow_direction_and_alternate():
    left = motion.calls("point", 1.0, -1.0, {"head": "#h", "arm_a": "#a", "arm_b": "#b"})
    assert left[1][1] == "#a" and left[1][2]["rotation"] == 75  # 向左用 arm_a，-75×(-1)
    right = motion.calls("point", 1.0, 1.0, {"head": "#h", "arm_a": "#a", "arm_b": None})
    assert right[1][1] == "#a"  # 沒有 arm_b 就用另一隻
    shake = motion.calls("shake", 0.0, 1.0, {"head": "#h"})
    assert [c[2]["xPercent"] for c in shake[:3]] == [-1.3, 1.3, -1.3]
    sniff = motion.calls("sniff", 0.0, 1.0, {"head": "#h"})
    assert sniff[1][2]["yPercent"] == "+=0.5"


# ── 表演套路 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(motion.beats_data()))
def test_beat_uses_library_names(name):
    b = motion.beats_data()[name]
    g = b["set"].get("gesture")
    if g:
        assert g in motion.gestures(), g
        assert set(b["species"]) <= set(motion.gestures()[g]["species"])
        if motion.gestures()[g]["status"] == "draft":
            assert b["status"] == "draft", f"{name} 用了試用動作 {g}，自己也要標試用"
    for key in ("mood", "mood_to"):
        for who, ex in (b["set"].get(key) or {}).items():
            assert ex in lib.heads(who), (name, who, ex)
    assert set(b["set"]) <= {"gesture", "mood", "mood_to", "eyes", "look_at", "mouth"}


def test_beat_expands_and_cast_fields_win():
    c = {"who": "papa", "pose": "sit", "spot": "sofa", "beat": "proud", "beat_at": 0.6, "look_at": "dad"}
    out = motion.expand_beat(c, lib.pose_expressions("papa", "sit"))
    assert out["gesture"] == "nod" and out["gesture_at"] == 0.6
    assert out["mood_to"] == "smug" and out["mood_at"] == 0.6
    assert out["look_at"] == "dad"  # cast 自己寫的優先
    hide = motion.expand_beat({**c, "who": "beibei", "pose": "hide"}, lib.pose_expressions("beibei", "hide"))
    assert "mood_to" not in hide and hide["gesture"] == "nod"  # 頭埋著的姿勢沒有 happy 表情頭：不換臉，動作照做
    assert motion.expand_beat({"who": "dad", "pose": "stand", "beat": "comfy"}, set()) == {"who": "dad", "pose": "stand", "beat": "comfy"}


def _ep(**cast_overrides) -> dict:
    ep = copy.deepcopy(papa_golden.ep01())
    s = next(s for s in ep["shots"] if s["id"] == "s08")
    s["cast"][0] = {**{k: v for k, v in s["cast"][0].items() if k not in ("gesture", "gesture_at")}, **cast_overrides}
    return ep


def test_validate_uses_motion_library():
    assert comp.validate(_ep(beat="oops", beat_at=0.4)) == []
    assert any("不能演" in e for e in comp.validate(_ep(beat="comfy")))  # 大人不能演「舒服」（要閉眼）
    assert any("沒有表演套路" in e for e in comp.validate(_ep(beat="dance")))
    assert any("不能做 wag_fast" in e for e in comp.validate(_ep(gesture="wag_fast", gesture_at=0.4)))
    assert any("beat_at 超出" in e for e in comp.validate(_ep(beat="oops", beat_at=9)))
    ep = copy.deepcopy(papa_golden.ep01())
    next(s for s in ep["shots"] if s["id"] == "s16")["hand"]["motion"] = "spin"
    assert any("沒有動法 spin" in e for e in comp.validate(ep))


def test_beat_compiles_to_gesture_and_cut_keeps_it_consistent():
    ep = _ep(beat="oops", beat_at=0.4)
    low = comp.compile_episode(ep)
    s08 = next(s for s in low["shots"] if s["id"] == "s08")
    assert s08["cast"][0]["gesture"][:2] == ["shrug", 0.4]
    assert s08["cast"][0]["look"][:2] == [0.0, 0.0]  # look_at camera
    ep["cut"] = [{"id": "s08", "dur": 0.6}]
    cut = comp.cut_episode(ep)
    assert "gesture" not in cut["shots"][0]["cast"][0]  # 精華版縮短後動作時間超出就拿掉


# ── skill 文件 ────────────────────────────────────────────────────────────
def test_skill_references_are_up_to_date():
    for path, text in skill_docs.generated().items():
        assert path.exists() and path.read_text(encoding="utf-8") == text, f"{path.name} 過期：python main.py papa motion-docs"


def test_skill_frontmatter_and_story_rules_match_library():
    for name in ("papa-home-motion", "papa-home-story"):
        head = (skill_docs.SKILLS / name / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
        assert f"name: {name}" in head and "description:" in head
    rules = (skill_docs.SKILLS / "papa-home-story" / "references" / "text-rules.md").read_text(encoding="utf-8")
    assert f"每行最多 {lib.LINE_MAX_CHARS} 字" in rules and f"字數÷{lib.READ_CHARS_PER_SEC}" in rules
    assert f"≥ {lib.MIN_HOLD} 秒" in rules and f"最多 {lib.MAX_TYPES} 種鏡頭" in rules
    assert "/".join(lib.EXPRESSIONS_PAPA_AVATAR) in rules
