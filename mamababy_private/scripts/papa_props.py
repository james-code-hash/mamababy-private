"""《帕帕貝貝家》手部特寫道具：照現有手部特寫的畫風生成新道具圖，綠底去背、檢查後登記到素材包。

生圖順序（業主定）：Codex → agy → Vertex AI Nano Banana 2.1（前一個沒額度或失敗才換下一個）；
每張最多試 3 次（`--tries`），檢查不過就重生，3 次都不過結束碼 1、工作階段整次停下來等業主。

    uv run python -m mamababy_private.scripts.papa_props reports/papa-home/props/ep02.json --project <GCP 專案>
    uv run python -m mamababy_private.scripts.papa_props reports/papa-home/props/ep02.json --only mom_spoon --force

spec JSON：[{"name": "mom_spoon", "ref": "mom_bottle", "label": "中文說明（給編劇看）", "desc": "英文描述畫面內容"}, ...]
（畫面裡本來就有東西從上緣伸進來，例如水龍頭，加 "from_top": true）
- `ref`＝畫風參考的現有手部特寫（`characters/hands/<ref>.webp`；袖子顏色跟著參考：媽媽米色毛衣、爸爸灰色帽T）。
- 回圖存在 `reports/papa-home/props/raw/`（已有就不重生，`--force` 重生），通過檢查才寫進
  `characters/hands/<name>.webp` 並登記到 `hands/rig.json`；最後輸出對照圖給人看。
生圖要花錢：每集先列好道具清單、業主同意再跑（企劃見 docs/papa-home-series.md §5）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from mamababy_private.scripts.papa_rig_parts import GREEN, chroma_key, clean_alpha, on_bg, save_webp, vertex_edit
from moneyerp.content import image_gen
from mamababy_private.papa_home import library as lib
from moneyerp.core.config import PROJECT_ROOT

HANDS = lib.ASSETS / "characters" / "hands"
WORK = Path(PROJECT_ROOT) / "reports" / "papa-home" / "props"
PROMPT = ("Use this picture only as the style reference: the same children's picture-book look, soft coloured pencil and "
          "warm watercolour, thin brown ink outlines, the same hands and sleeves (same skin tone, same sleeve colour and "
          "knit), the same scale. Draw a NEW close-up insert shot on a 1:1 canvas: {desc} The hands come in from the bottom "
          "edge, like the reference. Background: flat pure green (#00FF00) everywhere, no shadow, no floor, no table edge, "
          "no text, no extra hands, no faces. Keep every object fully inside the canvas except the sleeves at the edge.")


def check(rgba: np.ndarray, from_top: bool = False) -> list[str]:
    """去背後的道具圖檢查：有東西、手從畫面邊緣伸進來、沒有殘綠、主體沒被切。
    from_top：畫面裡本來就有東西從上緣伸進來（例：水龍頭），上緣不算被切。"""
    a = rgba[..., 3] > 128
    probs = []
    cover = a.mean()
    if not 0.08 <= cover <= 0.65:
        probs.append(f"主體面積 {cover:.0%}（要 8–65%）")
    if from_top:  # 從上緣伸進來的東西（水龍頭）碰到上緣也算從邊緣進來
        if not (a[:6].any() or a[-6:].any() or a[:, :6].any() or a[:, -6:].any()):
            probs.append("沒有東西碰到畫面邊緣（道具要從邊緣伸進來）")
    elif not (a[-6:].any() or a[:, :6].any() or a[:, -6:].any()):
        probs.append("沒有東西碰到下緣或左右緣（手要從畫面邊緣伸進來）")
    if a[:6].mean() > 0.02 and not from_top:
        probs.append("主體碰到上緣（被切掉）")
    rgb = rgba[..., :3].astype(int)
    greenish = a & (rgb[..., 1] > rgb[..., 0] + 40) & (rgb[..., 1] > rgb[..., 2] + 40)
    if greenish.sum() > 0.003 * a.sum():
        probs.append(f"殘留綠色 {greenish.sum()} px")
    return probs


class ConfigError(RuntimeError):
    """設定錯誤（沒設 Vertex 專案）：重試也一樣，直接停。"""


def generate(it: dict, raw: Path, project: str) -> str:
    """生一張道具回圖存到 raw：Codex → agy → Vertex；回傳用了哪個工具，全部失敗 raise RuntimeError。"""
    ref_path = WORK / "raw" / f"_ref_{it['ref']}.png"
    on_bg(Image.open(HANDS / f"{it['ref']}.webp").convert("RGBA"), GREEN).save(ref_path)
    prompt = PROMPT.format(desc=it["desc"])
    try:
        _, tool = image_gen.run_prompt(
            lambda names: (f"Generate exactly one image with your image generation tool. The attached {', '.join(names)} is the "
                           f"style reference. {prompt} Save it as out.png in the current directory. Do not end your reply until "
                           "the image has been generated and saved; then reply only with DONE."),
            raw, None, refs=[ref_path])
        return tool
    except RuntimeError as exc:
        if not project:
            raise ConfigError(f"{exc}；Vertex 沒設 --project／PAPA_VERTEX_PROJECT") from exc
        try:
            vertex_edit(Image.open(ref_path), prompt, project).save(raw)
        except Exception as vexc:  # noqa: BLE001 — 沒憑證是 DefaultCredentialsError，不是 RuntimeError；收成一張失敗，不讓整批崩掉
            raise RuntimeError(f"{exc}；Vertex 也失敗：{type(vexc).__name__}: {str(vexc)[:200]}") from vexc
        return "vertex"


def sheet(paths: list[Path], out: Path) -> None:
    tiles = []
    for p in paths:
        im = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", im.size, (236, 226, 212, 255))
        bg.alpha_composite(im)
        tiles.append(bg.convert("RGB").resize((512, 512)))
    canvas = Image.new("RGB", (512 * max(1, len(tiles)), 512), "white")
    for i, t in enumerate(tiles):
        canvas.paste(t, (512 * i, 0))
    canvas.save(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--project", default=os.environ.get("PAPA_VERTEX_PROJECT", ""), help="Vertex AI 的 GCP 專案（或 PAPA_VERTEX_PROJECT）")
    ap.add_argument("--only", nargs="*", help="只做這幾個")
    ap.add_argument("--force", action="store_true", help="已有回圖也重生")
    ap.add_argument("--tries", type=int, default=3, help="每張最多試幾次（預設 3）")
    args = ap.parse_args(argv)
    items = [i for i in json.loads(args.spec.read_text(encoding="utf-8")) if not args.only or i["name"] in args.only]
    (WORK / "raw").mkdir(parents=True, exist_ok=True)
    rig_path = HANDS / "rig.json"
    rig = json.loads(rig_path.read_text(encoding="utf-8"))
    done, failed = [], []
    for it in items:
        raw = WORK / "raw" / f"{it['name']}.png"
        rgba, probs = None, ["還沒生"]
        for k in range(args.tries):
            if args.force or k > 0 or not raw.exists():
                try:
                    tool = generate(it, raw, args.project)
                except RuntimeError as exc:
                    probs = [str(exc)[:300]]
                    print(f"  第 {k + 1} 次生圖失敗：{probs[0]}")
                    if isinstance(exc, ConfigError):
                        break  # 設定錯誤，重試沒意義
                    continue
                print(f"  第 {k + 1} 次：{tool}")
            rgba = clean_alpha(np.asarray(chroma_key(Image.open(raw).convert("RGB").resize((1024, 1024)), GREEN)), 400)
            probs = check(rgba, bool(it.get("from_top")))
            if not probs:
                break
            print(f"  第 {k + 1} 次檢查不過：{'；'.join(probs)}")
        if probs:
            failed.append(it["name"])
            print(f"✗ {it['name']}：試了 {args.tries} 次還不行（{'；'.join(probs)}；回圖 {raw}）")
            continue
        save_webp(Image.fromarray(rgba, "RGBA"), HANDS / f"{it['name']}.webp")
        rig["files"][it["name"]] = f"{it['name']}.webp"
        if it.get("label"):
            rig.setdefault("labels", {})[it["name"]] = it["label"]
        done.append(HANDS / f"{it['name']}.webp")
        print(f"✓ {it['name']}")
    if done:  # 沒有新登記的道具就不重寫 rig.json
        rig_path.write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if done:
        sheet(done, WORK / "sheet.png")
        print(f"對照圖：{WORK / 'sheet.png'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
