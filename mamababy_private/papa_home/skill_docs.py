"""產生製作工作階段用的 skill 參考文件（.claude/skills/papa-home-motion/references/*.md）：從動作庫 JSON 與 rig.json 寫成表格。

資料改了就重產：`python main.py papa motion-docs`；pytest 比對檔案是不是最新的。
"""
from __future__ import annotations

import json
from pathlib import Path

from mamababy_private.papa_home import library as lib
from mamababy_private.papa_home import motion
from mamababy_private.config import REPO_ROOT

SKILLS = REPO_ROOT / ".claude" / "skills"  # Claude Code 工作階段從這裡載入 skill
MOTION_REFS = SKILLS / "papa-home-motion" / "references"
GENERATED = "<!-- 由 papa_home/skill_docs.py 從 assets/papa_home/motion/*.json 與 rig.json 產生；不要手改，改資料後跑 `python main.py papa motion-docs` -->\n\n"


def _status(d: dict) -> str:
    return "試用" if d.get("status") == "draft" else "已審"


def _members(species: list[str]) -> list[str]:
    sp = motion.species_data()["species"]
    return [m for s in species for m in sp[s]["members"] if m in lib.ACTIVE]


def _species_label(species: list[str]) -> str:
    """物種中文名；全部角色都退役的物種（寶寶）不列。"""
    sp = motion.species_data()["species"]
    return "、".join(sp[x]["label"] for x in species if any(m in lib.ACTIVE for m in sp[x]["members"]))


def _example_pose(name: str, who: str) -> str | None:
    for pose in lib.poses(who):
        if not motion.gesture_errors(name, who, lib.rig(who)["poses"][pose]):
            return pose
    return None


def _example(name: str, g: dict) -> str:
    whos = _members(g["species"])
    if g.get("head_shot") or "tail" in g.get("needs", []):  # 臉部、尾巴的動作用帕帕示範
        whos = sorted(whos, key=lambda w: w != "papa")
    for who in whos:
        pose = _example_pose(name, who)
        if pose:
            c = {"who": who, "pose": pose, "spot": "front_center", "gesture": name, "gesture_at": 0.4}
            if name in ("point", "reach", "lean", "wave", "sniff"):
                c["look_at"] = "camera" if name == "wave" else [1500, 1500]
            return json.dumps({"id": "s05", "type": "WIDE", "dur": 2.4, "act": "act1", "scene": "living", "cast": [c]},
                              ensure_ascii=False)
    return ""


def _value_str(v) -> str:
    return str(v).replace("*dir", "×方向").replace("*alt", "×交替")


def _params(g: dict) -> str:
    """參數摘要：哪些零件、幅度、時間。"""
    parts, amps = [], []

    def walk(steps):
        for st in steps:
            if "repeat" in st:
                amps.append(f"重複 {st['repeat']} 次／每 {st['every']}s")
                walk(st["steps"])
                continue
            if st["part"] not in parts:
                parts.append(st["part"])
            to = st.get("to") or {}
            for k in ("rotation", "xPercent", "yPercent", "y"):
                if k in to and to[k] not in (0, "0") and len(amps) < 4:
                    amps.append(f"{st['part']}.{k} {_value_str(to[k])}")

    walk(g["steps"])
    return f"零件 {'/'.join(parts)}；" + "，".join(amps)


def motions_md() -> str:
    m = motion.motions_data()
    out = [GENERATED, "# 動作庫（assets/papa_home/motion/motions.json）\n",
           ("分鏡寫法：場景鏡 `cast[].gesture` ＋ `gesture_at`（秒）；頭像鏡 `head.gesture` ＋ `head.gesture_at`（只能用「頭像鏡」打勾的）。"
            "方向：有 `look_at` 跟著看的方向，沒有就跟 `flip`（flip＝向左）。一鏡一個角色最多一個 gesture。\n"),
           "「試用」＝還沒經過業主看片確認，可以用（業主 2026-11-04 同意第 2 集起使用）；業主看片確認後改成已審。\n",
           "## 零件動作（gesture）\n",
           "| 名稱 | 中文 | 狀態 | 物種 | 頭像鏡 | 需要零件 | 長度 | 參數 |", "|---|---|---|---|---|---|---|---|"]
    for name, g in m["gestures"].items():
        species = _species_label(g["species"])
        hold = "（維持到鏡尾）" if g.get("holds") else ""
        out.append(f"| `{name}` | {g['label']}：{g['desc']} | {_status(g)} | {species} | {'✓' if g.get('head_shot') else ''} | "
                   f"{'/'.join(g.get('needs', []))} | {g['length']}s{hold} | {_params(g)} |")
    out += ["", "### 範例鏡頭", ""]
    for name, g in m["gestures"].items():
        ex = _example(name, g)
        if ex:
            out += [f"- `{name}`：`{ex}`"]
    out += ["", "## 整隻角色的動作（cast.action）", "", "| 名稱 | 中文 | 物種 | 參數 | 寫法 |", "|---|---|---|---|---|"]
    usage = {"hop": '`"action": "hop"`', "pop_in": '`"action": "pop_in", "at": 0.15`',
             "dive": '`"action": "dive", "at": 4.1, "dive_dx": -340`（通常配 `show` 接在 run 後面）'}
    for name, a in m["actions"].items():
        species = _species_label(a["species"])
        params = "、".join(f"{k}={v}" for k, v in a["params"].items())
        out.append(f"| `{name}` | {a['label']}：{a['desc']} | {species} | {params} | {usage.get(name, '')} |")
    out += ["", "## 走位與進出場", ""]
    out += [f"- `{k}`（{v['label']}）：{v['desc']}" for k, v in m["movement"].items()]
    out += ["", "## 表情與視線（face）", ""]
    out += [f"- {v['label']}：{v['desc']}（欄位 {'、'.join(f'`{f}`' for f in v['fields'])}）" for v in m["face"].values()]
    out += ["", "## 程式自動加的（不用寫）", ""]
    out += [f"- {v['label']}：{v['desc']}" for v in m["ambient"].values()]
    out += ["", "## 手部特寫的動法（INSERT 的 hand.motion）", ""]
    out += [f"- `{k}`（{v['label']}）：{v['desc']}" for k, v in m["hand_motions"].items()]
    out += ["", "# 表演套路（assets/papa_home/motion/beats.json）", "",
            ("分鏡寫 `cast[].beat`＋`beat_at`（秒，預設 0.3），要看誰另寫 `look_at`。展開成下面的欄位；cast 自己寫的欄位優先，"
             "這個姿勢沒有的表情就不換臉（不會報錯）。"),
            "", "| 名稱 | 中文 | 狀態 | 物種 | 展開成 | 例 |", "|---|---|---|---|---|---|"]
    for name, b in motion.beats_data().items():
        species = _species_label(b["species"])
        sets = "；".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in b["set"].items())
        out.append(f"| `{name}` | {b['label']}：{b['desc']} | {_status(b)} | {species} | {sets} | {b.get('example', '')} |")
    return "\n".join(out) + "\n"


def characters_md() -> str:
    sp = motion.species_data()
    out = [GENERATED, "# 角色、姿勢與表情（rig.json）\n",
           "物種骨架（assets/papa_home/motion/species.json）：動作只認零件角色（role），每個姿勢有哪些 role 決定能做哪些動作。\n",
           "| role | 意思 |", "|---|---|"]
    out += [f"| `{r}` | {d} |" for r, d in sp["roles"].items()]
    out.append("")
    for sname, s in sp["species"].items():
        members = [m for m in s["members"] if m in lib.ACTIVE]  # 退役角色（寶寶）不給寫分鏡的人看
        if not members:
            continue
        out += [f"## {s['label']}（`{sname}`）：{'、'.join(members)}", "", s["note"], ""]
        for who in members:
            ch = sp["characters"][who]
            heads = lib.heads(who)
            out += [f"### {ch['label']}（`{who}`）", ""]
            if heads:
                out.append(f"頭像（CU／REACTION 的 head.expr）：{'、'.join(f'`{h}`' for h in heads)}；閉眼＝`{ch.get('closed_eyes')}`")
            else:
                out.append("不畫臉：沒有頭像鏡，cast 不能寫 mood／mood_to／eyes／mouth。")
            out += ["", "| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |", "|---|---|---|---|---|"]
            for pose in lib.poses(who):
                e = lib.rig(who)["poses"][pose]
                exprs = sorted(lib.pose_expressions(who, pose)) if heads else []
                roles = sorted(motion.pose_roles(e, who))
                ok = [n for n in motion.gestures() if not motion.gesture_errors(n, who, e)]
                out.append(f"| `{pose}` | {e.get('expression') or '—'} | {'、'.join(exprs) or '—'} | {'/'.join(roles)} | {'、'.join(ok)} |")
            out.append("")
    out += ["## 場景站位（spot）", ""]
    out += [f"- `{sc}`：{'、'.join(f'`{k}`' for k in lib.spots(sc))}" for sc in lib.SCENES]
    labels = lib.hand_labels()
    out += ["", "## 道具與手部特寫", "",
            "手部特寫（hand.prop／split.prop）：" + "、".join(f"`{h}`（{labels[h]}）" if h in labels else f"`{h}`" for h in lib.hands()),
            "",
            "道具（props/，split／demo 用）：" + "、".join(f"`{p}`" for p in sorted(p for p in lib.props() if not p.startswith(("tuft_", "paper")))),
            "", "音效（sfx）：" + "、".join(f"`{x}`" for x in lib.SFX),
            "", "畫面效果（fx）：" + "、".join(f"`{x}`" for x in lib.FX)]
    return "\n".join(out) + "\n"


def format_md() -> str:
    """分鏡 JSON 欄位說明（compile.py 開頭的 docstring）＋鏡頭類型。"""
    from mamababy_private.papa_home import compile as comp

    shots = "\n".join(f"- `{k}`：{v}" for k, v in lib.SHOT_TYPES.items())
    return (GENERATED + "# 分鏡 JSON 格式\n\n```text\n" + (comp.__doc__ or "").strip() + "\n```\n\n## 鏡頭類型（type）\n\n" + shots
            + f"\n\n## 其他名稱\n\n- act：{'、'.join(lib.ACTS)}\n- mood（配樂）：{'、'.join(lib.MOODS)}\n- seam（接點，通常不用寫）：{'、'.join(lib.SEAMS)}\n")


def generated() -> dict[Path, str]:
    return {MOTION_REFS / "motions.md": motions_md(), MOTION_REFS / "characters.md": characters_md(),
            SKILLS / "papa-home-story" / "references" / "format.md": format_md()}


def write() -> list[Path]:
    out = []
    for path, text in generated().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        out.append(path)
    return out
