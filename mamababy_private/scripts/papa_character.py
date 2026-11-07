"""《帕帕貝貝家》新角色：從業主定案的定裝圖生出各姿勢的全身定裝圖與正面表情頭像，去背、對齊到素材規格，寫 rig.json 骨架。

    uv run python -m mamababy_private.scripts.papa_character reports/papa-home/characters/sister.json [--step poses heads] [--only stand]

之後照現有流程拆件（docs/papa-home-series.md §5.1）：
    papa_rig_parts --who <角色> --step gen cut   →  papa_rig_bodies --who <角色>  →  papa_pose_heads --who <角色>

spec JSON：
    {"who": "sister", "design": "reports/papa-home/design/sister_final.png",
     "subject": "英文：這個角色是誰（給生圖用）",
     "poses": {"stand": {"height": 128, "expression": "smile", "desc": "英文姿勢描述"}, ...},
     "heads": {"smile": "英文表情描述", ...}}

生圖順序（業主定）：Codex → agy → Vertex AI；每張最多試 3 次，去背後檢查不過就重生，3 次都不過結束碼 1（工作階段整次停下來）。
規格（跟現有角色一樣）：1024×1024 透明底；全身圖腳底中心在 (512, 960)、最高點 y=60（太寬就縮到寬 980）；
頭像置中、上緣 62、脖子底部中心在 (512, 962)。回圖與工作檔在 reports/papa-home/characters/<角色>/（不進版控）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from mamababy_private.scripts.papa_rig_parts import GREEN, chroma_key, clean_alpha, components, save_webp, vertex_edit
from moneyerp.content import image_gen
from mamababy_private.papa_home import library as lib
from moneyerp.core.config import PROJECT_ROOT

WORK = Path(PROJECT_ROOT) / "reports" / "papa-home" / "characters"
CANVAS, FOOT_Y, TOP_Y, MAX_W = 1024, 960, 60, 980
HEAD_TOP, NECK_Y = 62, 962
STYLE = ("children's picture-book style identical to the reference: soft coloured pencil and warm watercolour, thin brown ink "
         "outlines, same face, hair, outfit, colours and proportions. Background: flat pure green (#00FF00) everywhere, no "
         "shadow, no floor, no text, no other characters, nothing cut off by the frame.")


def pose_prompt(spec: dict, desc: str) -> str:
    return (f"Draw the SAME character as the attached reference design ({spec['subject']}) in a new pose: {desc} "
            f"Full body, the whole character inside the canvas. {STYLE}")


def head_prompt(spec: dict, desc: str) -> str:
    return (f"Draw a close-up portrait of the SAME character as the attached reference design ({spec['subject']}): only the "
            f"head and the top of the collar, facing the viewer, centred, the head filling most of the canvas. Expression: {desc} "
            f"{STYLE}")


def generate(prompt: str, ref: Path, raw: Path, project: str) -> str:
    """生一張回圖存到 raw：Codex → agy → Vertex；回傳用了哪個工具，全部失敗 raise RuntimeError。"""
    try:
        _, tool = image_gen.run_prompt(
            lambda names: (f"Generate exactly one image with your image generation tool. The attached {', '.join(names)} is the "
                           f"character reference. {prompt} Save it as out.png in the current directory. Do not end your reply "
                           "until the image has been generated and saved; then reply only with DONE."),
            raw, None, refs=[ref])
        return tool
    except RuntimeError as exc:
        if not project:
            raise RuntimeError(f"{exc}；Vertex 沒設 --project／PAPA_VERTEX_PROJECT") from exc
        print(f"    Codex／agy 沒出圖，改用 Vertex：{str(exc)[:200]}")
        try:
            vertex_edit(Image.open(ref), prompt, project).save(raw)
        except Exception as vexc:  # noqa: BLE001 — 沒憑證是 DefaultCredentialsError：收成這張失敗，下一次重試或停
            raise RuntimeError(f"{exc}；Vertex 也失敗：{type(vexc).__name__}: {str(vexc)[:200]}") from vexc
        return "vertex"


def cutout(raw: Path) -> np.ndarray:
    """綠底回圖 → 去背 RGBA，只留最大的那塊（加上靠近它的小塊，例如分開畫的手）。"""
    rgba = clean_alpha(np.asarray(chroma_key(Image.open(raw).convert("RGB"), GREEN)), 400)
    return rgba


def place(rgba: np.ndarray, top: int, bottom: int, max_w: int) -> Image.Image:
    """裁到主體 → 等比縮放：高度填滿 top..bottom（太寬就縮到 max_w）→ 底部中心放在 (512, bottom)。"""
    ys, xs = np.nonzero(rgba[..., 3] > 16)
    crop = Image.fromarray(rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA")
    scale = min((bottom - top) / crop.height, max_w / crop.width)
    crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    out.alpha_composite(crop, (CANVAS // 2 - crop.width // 2, bottom - crop.height))
    return out


def check(rgba: np.ndarray, kind: str) -> list[str]:
    """去背後檢查：主體一大塊、沒被畫框切到、沒殘綠、比例像全身或頭像。"""
    a = rgba[..., 3] > 128
    probs = []
    if a.mean() < 0.04:
        probs.append(f"主體太小（{a.mean():.0%}）")
    edge = np.concatenate([a[:3].ravel(), a[-3:].ravel(), a[:, :3].ravel(), a[:, -3:].ravel()]).mean()
    if kind == "pose" and edge > 0.002:
        probs.append("主體碰到畫框（被切到）")
    parts = sorted((c.sum() for c in components(a)), reverse=True)
    if parts and len(parts) > 1 and parts[1] > 0.15 * parts[0]:
        probs.append(f"去背後分成好幾大塊（{len(parts)} 塊），可能多畫了東西或底色不乾淨")
    rgb = rgba[..., :3].astype(int)
    greenish = a & (rgb[..., 1] > rgb[..., 0] + 40) & (rgb[..., 1] > rgb[..., 2] + 40)
    if greenish.sum() > 0.003 * max(1, a.sum()):
        probs.append(f"殘留綠色 {greenish.sum()} px")
    ys, xs = np.nonzero(a)
    if len(ys):
        h, w = int(np.ptp(ys)) + 1, int(np.ptp(xs)) + 1
        if kind == "head" and not 0.6 <= w / h <= 1.6:
            probs.append(f"頭像寬高比 {w / h:.2f} 不像頭像")
    return probs


def make(name: str, prompt: str, ref: Path, folder: Path, kind: str, tries: int, project: str, force: bool) -> Image.Image | None:
    raw = folder / f"{name}.png"
    probs = ["還沒生"]
    for k in range(tries):
        if force or k > 0 or not raw.exists():
            try:
                print(f"  {name} 第 {k + 1} 次：{generate(prompt, ref, raw, project)}")
            except RuntimeError as exc:
                probs = [str(exc)[:300]]
                print(f"  {name} 第 {k + 1} 次生圖失敗：{probs[0]}")
                continue
        rgba = cutout(raw)
        probs = check(rgba, kind)
        if not probs:
            if kind == "pose":
                return place(rgba, TOP_Y, FOOT_Y, MAX_W)
            return place(rgba, HEAD_TOP, NECK_Y, MAX_W)
        print(f"  {name} 第 {k + 1} 次檢查不過：{'；'.join(probs)}")
    print(f"✗ {name}：試了 {tries} 次還不行（{'；'.join(probs)}；回圖 {raw}）")
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--step", nargs="*", default=["poses", "heads"], choices=["poses", "heads"])
    ap.add_argument("--only", nargs="*", help="只做這幾個姿勢／表情")
    ap.add_argument("--project", default=os.environ.get("PAPA_VERTEX_PROJECT", ""), help="Vertex AI 的 GCP 專案（或 PAPA_VERTEX_PROJECT）")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="已有回圖也重生")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    who = spec["who"]
    out_dir = lib.ASSETS / "characters" / who
    out_dir.mkdir(parents=True, exist_ok=True)
    folder = WORK / who
    folder.mkdir(parents=True, exist_ok=True)
    design = Path(PROJECT_ROOT) / spec["design"]
    rig_path = out_dir / "rig.json"
    rig = json.loads(rig_path.read_text(encoding="utf-8")) if rig_path.exists() else {
        "canvas": [CANVAS, CANVAS], "foot": [CANVAS // 2, FOOT_Y], "poses": {}, "heads": {},
        "note": "world_height 單位 cm；新角色由 scripts/papa_character.py 從定裝圖生成，零件由 papa_rig_parts 拆"}
    failed = []
    if "heads" in args.step:
        for expr, desc in spec["heads"].items():
            if args.only and expr not in args.only:
                continue
            im = make(f"head_{expr}", head_prompt(spec, desc), design, folder, "head", args.tries, args.project, args.force)
            if im is None:
                failed.append(f"head_{expr}")
                continue
            save_webp(im, out_dir / f"head_{expr}.webp")
            rig["heads"][expr] = {"file": f"head_{expr}.webp", "neck": [CANVAS // 2, NECK_Y], "eyes": None}
    if "poses" in args.step:
        for pose, p in spec["poses"].items():
            if args.only and pose not in args.only:
                continue
            im = make(f"pose_{pose}", pose_prompt(spec, p["desc"]), design, folder, "pose", args.tries, args.project, args.force)
            if im is None:
                failed.append(f"pose_{pose}")
                continue
            save_webp(im, out_dir / f"pose_{pose}.webp")
            box = list(im.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox() or (0, 0, CANVAS, CANVAS))
            rig["poses"][pose] = {**rig["poses"].get(pose, {}), "file": f"pose_{pose}.webp", "world_height": p["height"],
                                  "expression": p["expression"], "bbox": box}
    rig_path.write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"rig：{rig_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
