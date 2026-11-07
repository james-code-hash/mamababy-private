#!/usr/bin/env python3
"""《帕帕貝貝家》每個姿勢專用的表情頭＋特寫頭像的眨眼貼片，全部對齊原圖並逐張驗證。

    uv run python -m mamababy_private.scripts.papa_pose_heads [--who papa] [--pose sit] [--step gen cut blink pupils] [--force]

為什麼：正面的表情頭像接到側身、四分之三側的身體上，角度、大小、領口都對不上（看起來頭斷掉）。改成
拿姿勢原圖請 Nano Banana 只換表情，對齊回原圖後只取頭部範圍的像素 → 角度、大小、領口天生跟身體一致。

  gen    姿勢原圖（綠底）→「只換成某個表情」；特寫頭像 → 「眨眼閉上」。原始回圖在 reports/papa-home/rig/heads/，已有不重生。
  cut    對齊（register）→ 頭部遮罩＝原本頭零件外擴 10px → p_<姿勢>_head_<表情>.webp；
         驗證：整體 IoU ≥ 0.95、頭以外色差 ≤ 12、頭部確實改變（色差 ≥ 5）、新頭中心與脖子 ±8px、寬度 0.92–1.08。
         通過才寫 rig.json poses.<姿勢>.parts.head.expressions.<表情>（含 qa 數字）。
  blink  特寫頭像閉眼版 → 只取眼框外擴 18px → blink_<表情>.webp；驗證眼框外色差 ≤ 12、眼框內有變。通過寫 heads.<表情>.blink。
  heal   零件拼回去比原圖淡的外框像素補回去（舊版 cut_layer 連角色外框也柔化，墨線變淡、重組 IoU < 0.99）。
  pupils 拿掉所有頭像的 iris／pupil 圖層（瞳孔一動，原位留下高光白斑），理由記在 heads.<表情>.pupil_off；看向＝轉頭。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from mamababy_private.scripts.papa_rig_parts import (GREEN, bbox, char_dir, chroma_key, cut_layer, dilate, register,
                                                 save_webp, edit_image, warp)
from moneyerp.core.config import PROJECT_ROOT

WORK = Path(PROJECT_ROOT) / "reports" / "papa-home" / "rig" / "heads"
FACED = ("papa", "beibei", "baby", "sister", "brother")
SKIP_POSES = {("beibei", "hide")}  # 臉被爪子遮住
EXPR_TEXT = {
    "papa": {"neutral": "calm neutral face, eyes open, mouth closed", "unimpressed": "unimpressed sarcastic half-closed eyes, flat mouth",
             "surprised": "surprised wide round eyes, small open mouth", "smug": "smug proud smirk, eyes narrowed",
             "soft": "soft affectionate smile, eyes gently closed"},
    "beibei": {"happy": "happy, eyes closed smiling, tongue out", "innocent": "innocent big shiny puppy eyes, mouth closed",
               "scared": "scared, worried eyebrows, small sweat drop, mouth tight", "excited": "over-excited, sparkling eyes, wide open happy mouth"},
    "baby": {"giggle": "giggling, eyes squeezed happy, open mouth", "cry": "crying with tears, mouth wide open",
             "sleep": "sleeping peacefully, eyes closed", "curious": "curious wide-eyed, small round mouth"},
    "sister": {"smile": "gentle closed-mouth smile, eyes open", "happy": "big happy open-mouth grin, eyes open",
               "angry": "annoyed pout, eyebrows down, cheeks puffed", "surprised": "surprised wide eyes, small round open mouth",
               "sad": "about to cry, teary eyes, trembling lip"},
    "brother": {"smile": "gentle closed-mouth smile, eyes open", "laugh": "laughing with eyes squeezed shut into happy arcs, mouth wide open",
                "angry": "grumpy toddler pout, eyebrows down, lips pushed out", "surprised": "surprised wide eyes, small round open mouth",
                "cry": "crying loudly with tears, mouth wide open"},
}
EDIT = ("Edit the attached illustration: change ONLY the character's facial expression to: {expr}. Keep the head exactly the same "
        "size, tilt, angle, position and outline; keep the ears, fur, collar or bib, body, paws and everything else identical and "
        "pixel-aligned. Same soft colored-pencil watercolor style and line weight. Keep the flat pure #00FF00 background.")
BLINK = ("Edit the attached illustration: the character blinks — both eyes fully closed as soft curved lid lines, same expression "
         "otherwise. Change NOTHING else: same head, same mouth, same ears, same bib or collar, same framing, pixel-aligned. "
         "Keep the flat pure #00FF00 background.")
QA = {"iou": 0.95, "body_diff": 12.0, "head_changed": 5.0, "center": 8, "neck": 8, "w_lo": 0.92, "w_hi": 1.08}


def _rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a > 128, b > 128
    return float((a & b).sum() / max(1, (a | b).sum()))


def _cdiff(a: np.ndarray, b: np.ndarray, m: np.ndarray) -> float:
    m = m & (a[..., 3] > 200) & (b[..., 3] > 200)
    if not m.any():
        return 0.0
    return float(np.abs(a[..., :3].astype(int) - b[..., :3].astype(int)).mean(-1)[m].mean())


def _gen(path: Path, src: Image.Image, prompt: str, project: str, force: bool) -> Image.Image:
    if path.exists() and not force:
        return Image.open(path).convert("RGB")
    out, tool = edit_image(src, GREEN, prompt, project)  # 先 agy，沒對齊才 Vertex
    print(f"    {path.name}：{tool}", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)
    return out


def _aligned(orig: np.ndarray, raw: Image.Image, body: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """回圖對齊原圖：先用外框（alpha）找縮放與位移；給了 body（不該變的區域）就在 ±2px 內再挑顏色最吻合的位移。
    外框對齊常差 1px（2026-11-05 姊姊蹲姿：外框挑 (-1, +1)，牛仔布細紋對不上，身體色差 13.8；(0, 0) 只有 5.9）。"""
    ed = np.asarray(chroma_key(raw.resize((1024, 1024), Image.Resampling.LANCZOS), GREEN))
    s, dx, dy, inside = register(orig[..., 3], ed[..., 3])
    if body is not None:
        cands = {(dx + i, dy + j) for i in range(-2, 3) for j in range(-2, 3)} | {(0, 0)}
        dx, dy = min(cands, key=lambda o: (_cdiff(orig, warp(ed, s, o[0], o[1]), body), abs(o[0] - dx) + abs(o[1] - dy)))
    return warp(ed, s, dx, dy), {"scale": round(s, 4), "dx": dx, "dy": dy, "inside": round(inside, 3)}


def pose_heads(who: str, only_pose: str | None, project: str, force: bool, steps: set[str]) -> list[str]:
    d = char_dir(who)
    rig = json.loads((d / "rig.json").read_text())
    log = []
    if who not in EXPR_TEXT:
        return [f"✗ {who} 沒有表情頭定義（EXPR_TEXT），略過"]
    for pose, e in rig["poses"].items():
        parts = e.get("parts") or {}
        hp = parts.get("head")
        if not hp or (who, pose) in SKIP_POSES or (only_pose and pose != only_pose):
            continue
        orig = _rgba(d / e["file"])
        head = _rgba(d / hp["file"])
        ha = head[..., 3] > 128
        hb = bbox(dilate(ha, 10) & (orig[..., 3] > 128))  # 跟新頭用同一個遮罩切原圖的外框比
        own = e.get("expression")
        exprs = hp.setdefault("expressions", {})
        for ex, text in EXPR_TEXT[who].items():
            if ex == own:
                continue
            raw_path = WORK / who / f"{pose}_{ex}.png"
            if "gen" in steps:
                try:
                    _gen(raw_path, Image.fromarray(orig), EDIT.format(expr=text), project, force)
                except RuntimeError as exc:
                    log.append(f"✗ {who}/{pose}/{ex} 生圖失敗：{exc}")
                    continue
            if "cut" not in steps or not raw_path.exists():
                continue
            ed, reg = _aligned(orig, Image.open(raw_path), ~dilate(ha, 24))
            mask = dilate(ha, 10) & (ed[..., 3] > 8)
            layer = np.asarray(cut_layer(ed, mask, feather=2))
            la = layer[..., 3] > 128
            nb = bbox(la) if la.any() else (0, 0, 1, 1)
            qa = {**reg, "iou": round(_iou(orig[..., 3], ed[..., 3]), 3),
                  "body_diff": round(_cdiff(orig, ed, ~dilate(ha, 24)), 1),
                  "head_changed": round(_cdiff(orig, ed, ha), 1),
                  "center": [int((nb[0] + nb[2] - hb[0] - hb[2]) / 2), int((nb[1] + nb[3] - hb[1] - hb[3]) / 2)],
                  "neck": int(nb[3] - hb[3]), "w_ratio": round((nb[2] - nb[0]) / (hb[2] - hb[0]), 3)}
            fails = [k for k, ok in (("iou", qa["iou"] >= QA["iou"]), ("body_diff", qa["body_diff"] <= QA["body_diff"]),
                                     ("head_changed", qa["head_changed"] >= QA["head_changed"]),
                                     ("center", max(abs(v) for v in qa["center"]) <= QA["center"]),
                                     ("neck", abs(qa["neck"]) <= QA["neck"]),
                                     ("w_ratio", QA["w_lo"] <= qa["w_ratio"] <= QA["w_hi"])) if not ok]
            name = f"p_{pose}_head_{ex}.webp"
            if fails:
                exprs.pop(ex, None)
                log.append(f"✗ {who}/{pose}/{ex} 不合格 {fails} {qa}")
                continue
            save_webp(Image.fromarray(layer), d / name)
            exprs[ex] = {"file": name, "qa": qa}
            log.append(f"✓ {who}/{pose}/{ex} {qa}")
    (d / "rig.json").write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n")
    return log


def blinks(who: str, project: str, force: bool, steps: set[str]) -> list[str]:
    d = char_dir(who)
    rig = json.loads((d / "rig.json").read_text())
    log = []
    for ex, h in rig["heads"].items():
        if not h.get("eyes"):
            continue  # 閉眼的表情不用眨眼
        orig = _rgba(d / h["file"])
        raw_path = WORK / who / f"blink_{ex}.png"
        if "gen" in steps:
            try:
                _gen(raw_path, Image.fromarray(orig), BLINK, project, force)
            except RuntimeError as exc:
                log.append(f"✗ {who}/blink/{ex} 生圖失敗：{exc}")
                continue
        if "blink" not in steps or not raw_path.exists():
            continue
        ed, reg = _aligned(orig, Image.open(raw_path))
        eyes = np.zeros(orig.shape[:2], bool)
        for eye in h["eyes"]:
            eyes[eye["y"]:eye["y"] + eye["h"], eye["x"]:eye["x"] + eye["w"]] = True
        mask = dilate(eyes, 18) & (orig[..., 3] > 128)
        patch = ed.copy()
        patch[..., 3] = np.where(mask, orig[..., 3], 0)  # 貼片在眼睛範圍內完全蓋住原圖
        qa = {**reg, "outside_diff": round(_cdiff(orig, ed, ~dilate(eyes, 40)), 1),
              "eye_changed": round(_cdiff(orig, ed, eyes), 1)}
        fails = [k for k, ok in (("outside_diff", qa["outside_diff"] <= QA["body_diff"]),
                                 ("eye_changed", qa["eye_changed"] >= 8)) if not ok]
        if fails:
            h.pop("blink", None)
            log.append(f"✗ {who}/blink/{ex} 不合格 {fails} {qa}")
            continue
        name = f"blink_{ex}.webp"
        save_webp(Image.fromarray(patch), d / name)
        h["blink"], h["blink_qa"] = name, qa
        log.append(f"✓ {who}/blink/{ex} {qa}")
    (d / "rig.json").write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n")
    return log


def pupils(who: str) -> list[str]:
    """拿掉所有頭像的 iris／pupil 圖層：瞳孔一移動，原圖的高光與補色留在原位變白斑（2026-11-04 ep01 55 秒特寫），
    手繪的眼睛拆不乾淨 → 看向目標一律只轉頭。"""
    d = char_dir(who)
    rig = json.loads((d / "rig.json").read_text())
    log = []
    for ex, h in rig["heads"].items():
        files = [h.pop(k) for k in ("iris", "pupil") if h.get(k)]
        for eye in h.get("eyes") or []:
            eye.pop("pupil", None)
        if files:
            h["pupil_off"] = "瞳孔移動會在原位留下高光白斑，已拿掉；看向目標只轉頭"
            for f in files:
                (d / f).unlink(missing_ok=True)
            log.append(f"✓ {who}/{ex} 拿掉瞳孔圖層 {files}")
    (d / "rig.json").write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n")
    return log


PART_ORDER = ("body", "hind", "front", "front2", "head")


def heal_edges(who: str) -> list[str]:
    """零件拼回去比原圖淡的外框像素（舊版 cut_layer 連外框一起柔化）→ 原圖像素補回 alpha 最高的那個零件。"""
    d = char_dir(who)
    rig = json.loads((d / "rig.json").read_text())
    log = []
    for pose, e in rig["poses"].items():
        parts = e.get("parts") or {}
        names = [n for n in PART_ORDER if parts.get(n)]
        if not names:
            continue
        orig = _rgba(d / e["file"])
        layers = {n: _rgba(d / parts[n]["file"]).copy() for n in names}
        comp = Image.new("RGBA", orig.shape[1::-1])
        for n in names:
            comp.alpha_composite(Image.fromarray(layers[n]))
        ca = np.asarray(comp)[..., 3].astype(int)
        hole = orig[..., 3].astype(int) > ca + 24
        if not hole.any():
            continue
        # 每個缺的像素交給附近 alpha 最高的零件（外擴 3px 找，沒有零件碰到的也有主）
        near = np.stack([np.asarray(Image.fromarray(layers[n][..., 3]).filter(ImageFilter.MaxFilter(7))) for n in names])
        owner = near.argmax(0)
        before = _iou(orig[..., 3], ca)
        for i, n in enumerate(names):
            m = hole & (owner == i)
            if m.any():
                layers[n][m] = orig[m]
                save_webp(Image.fromarray(layers[n]), d / parts[n]["file"])
        comp = Image.new("RGBA", orig.shape[1::-1])
        for n in names:
            comp.alpha_composite(Image.fromarray(layers[n]))
        after = _iou(orig[..., 3], np.asarray(comp)[..., 3])
        log.append(f"{'✓' if after >= 0.99 else '✗'} {who}/{pose} 外框補 {int(hole.sum())} px，重組 IoU {before:.3f} → {after:.3f}")
    return log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", nargs="*", default=list(FACED))
    ap.add_argument("--pose", default=None)
    ap.add_argument("--step", nargs="*", default=["heal", "gen", "cut", "blink", "pupils"])
    ap.add_argument("--project", default=os.environ.get("PAPA_VERTEX_PROJECT", ""))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    steps = set(a.step)
    if "gen" in steps and not a.project:
        sys.exit("要 --project 或環境變數 PAPA_VERTEX_PROJECT")
    if "heal" in steps:  # 所有角色的零件外框（dad、mom 沒有表情頭但也有零件）
        for who in ("papa", "beibei", "dad", "mom", "baby", "sister", "brother"):
            for line in heal_edges(who):
                print(line, flush=True)
    for who in a.who:
        for line in pose_heads(who, a.pose, a.project, a.force, steps):
            print(line, flush=True)
        if not a.pose:
            for line in blinks(who, a.project, a.force, steps):
                print(line, flush=True)
        if "pupils" in steps:
            for line in pupils(who):
                print(line, flush=True)


if __name__ == "__main__":
    main()
