#!/usr/bin/env python3
"""《帕帕貝貝家》身體零件去掉四肢殘留：手腳一動，身體上原本畫的手腳不能還在（2026-11-04 ep01：爸爸聳肩變 4 隻手）。

    uv run python -m mamababy_private.scripts.papa_rig_bodies [--who dad] [--pose stand] [--step gen cut sheet] [--force]

  gen    Codex（HEAD_TOO 的姿勢連頭一起拿掉；`codex exec -i`，用 Codex 的生圖額度）：姿勢原圖（綠底）＋同一張把四肢零件塗洋紅的對照圖 →
         「拿掉洋紅的部分、補好後面的身體，伸出身體外的地方變綠底」。回圖在 reports/papa-home/rig/bodies/，已有不重生。
  cut    回圖對齊（register）→ 色調用接縫附近對回原圖（match_colors）→ 只在四肢零件外擴 6px（不含頭）的範圍內換成回圖的像素，其他地方保留原本的身體。
         對齊用軀幹顏色（color_register）。驗證：對齊落在原圖內 ≥ 0.97、四肢範圍外色差 ≤ 30（Codex 會整張重畫，顏色略飄）、零件在原位拼回去
         IoU ≥ 0.985；殘留比例只記錄，有沒有鬼影看 sheet。通過才覆寫 p_<姿勢>_body.webp，數字寫進 parts.body.qa。
  sheet  對照圖：身體單獨、前腳轉 40°／後腳轉 20° 的樣子 → reports/papa-home/rig/bodies/sheet_<角色>.png（人眼看有沒有鬼影）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from mamababy_private.scripts.papa_rig_parts import GREEN, chroma_key, dilate, on_bg, save_webp, vertex_edit, warp
from moneyerp.content import image_gen
from moneyerp.core import config
from moneyerp.core.config import PROJECT_ROOT

from mamababy_private.config import ASSETS

WORK = Path(PROJECT_ROOT) / "reports" / "papa-home" / "rig" / "bodies"
CHARS = ASSETS / "characters"
LIMBS = ("front", "front2", "hind")
MAGENTA = (255, 0, 255)
HEAD_TOO = {("beibei", "hide"), ("dad", "hold_baby")}  # 身體上的頭殘留 23–25%（搖頭時看到耳朵殘影），頭也一起拿掉重補
# 寶寶躺著：軀幹幾乎都被手腳蓋住，回圖的條紋方向跟原圖對不上（色差高是條紋錯位，不是對歪；整個身體換成回圖會破洞 IoU 0.96）。
# 接縫大多在手腳底下，人眼看過 sheet 沒有殘影 → 放寬色差
DIFF_OK = {("baby", "lie"): 50.0}
# remnant（四肢底下跟原圖一樣的比例）只記錄不擋：補出來的毛色、衣服跟原本的手腳顏色接近時會誤判，殘影改看 sheet
QA = {"inside": 0.97, "outside_diff": 30.0, "iou": 0.985}
PROMPT = """Use your image generation tool to EDIT the attached image ref_0.png. It is a hand-drawn colored-pencil watercolor
illustration of a character on a flat pure #00FF00 green background. ref_1.png is the same image with some body parts painted
solid magenta: those are the limbs (arms/legs/paws and anything they hold), sometimes also the head.

Edit ref_0.png: remove everything that is magenta in ref_1.png. Repaint what was hidden behind those limbs: where a limb overlapped
the torso or body, continue the torso/body/clothing naturally (same colors, texture and outline style) so it looks complete; where a
limb stuck out beyond the body, leave flat pure #00FF00 background. If the head is magenta, paint the neck/shoulders or body that
would be behind it. Do not add new limbs or a new head.

Keep everything else identical and pixel-aligned: same canvas size (1024x1024), same framing, same position and size of the
character, same head, colors, line weight and style. Keep the flat pure #00FF00 background.

Save the result as out.png in the current directory. Do not end until out.png is saved; then reply only with DONE."""


def _rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


def _limb_masks(d: Path, parts: dict) -> dict[str, np.ndarray]:
    return {n: _rgba(d / parts[n]["file"])[..., 3] > 128 for n in LIMBS if parts.get(n)}


def remnant(body: np.ndarray, orig: np.ndarray, mask: np.ndarray) -> float:
    """四肢底下，身體還跟原圖幾乎一樣的比例（＝手腳還畫在身體上）。"""
    same = (body[..., 3] > 128) & (np.abs(body[..., :3].astype(int) - orig[..., :3].astype(int)).max(-1) < 25)
    return float((same & mask).sum() / max(1, mask.sum()))


def color_register(orig: np.ndarray, ed: np.ndarray, torso: np.ndarray) -> tuple[float, int, int]:
    """用軀幹（不含四肢、頭）的顏色對齊：回圖只剩軀幹，用輪廓對會亂縮放。先 1/4 解析度粗找、再全解析度 ±2px 細修。"""
    def score(o: np.ndarray, e: np.ndarray, m: np.ndarray, s: float, dx: int, dy: int) -> float:
        w = warp(e, s, dx, dy)
        mm = m & (w[..., 3] > 200)
        if mm.sum() < m.sum() * 0.5:
            return 1e9
        return float(np.abs(o[..., :3].astype(int) - w[..., :3].astype(int)).mean(-1)[mm].mean() + (1 - mm.sum() / m.sum()) * 100)

    q = lambda a: np.asarray(Image.fromarray(a).resize((256, 256), Image.Resampling.BILINEAR))  # noqa: E731
    oq, eq = q(orig), q(ed)
    mq = np.asarray(Image.fromarray((torso * 255).astype(np.uint8)).resize((256, 256))) > 200
    coarse = min(((score(oq, eq, mq, s, dx, dy), s, dx, dy) for s in np.arange(0.95, 1.051, 0.01)
                  for dx in range(-6, 7) for dy in range(-6, 7)))
    _, s0, dx0, dy0 = coarse
    fine = min(((score(orig, ed, torso, float(s0), dx0 * 4 + ddx, dy0 * 4 + ddy), float(s0), dx0 * 4 + ddx, dy0 * 4 + ddy)
                for ddx in range(-2, 3) for ddy in range(-2, 3)))
    if fine[0] >= 1e9:
        raise RuntimeError("color_register 對齊失敗：軀幹露出太少或回圖對不上")
    return round(fine[1], 3), fine[2], fine[3]


def match_colors(ed: np.ndarray, orig: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Codex 整張重畫，顏色深淺會飄：用接縫附近（m）每個色版的平均與對比，把回圖調回原圖的色調。"""
    if m.sum() < 500:
        return ed
    out = ed.astype(np.float32).copy()
    for c in range(3):
        e, o = out[..., c][m], orig[..., c][m].astype(np.float32)
        gain = np.clip(o.std() / max(e.std(), 1.0), 0.6, 1.6)
        out[..., c] = (out[..., c] - e.mean()) * gain + o.mean()
    return np.clip(out, 0, 255).astype(np.uint8)


def _codex(workdir: Path, timeout: int = 900) -> None:
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    codex = os.environ.get("CODEX_BIN") or shutil.which("codex") or str(Path.home() / ".local/bin/codex")
    r = subprocess.run([codex, "exec", "--sandbox", "workspace-write", "-m", config.CODEX_MODEL,
                        "-i", "ref_0.png", "-i", "ref_1.png", "-"], cwd=workdir, input=PROMPT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    if r.returncode != 0 or not (workdir / "out.png").exists():
        raise RuntimeError(f"codex 失敗：{(r.stdout + r.stderr).strip()[-200:]}")


def gen(who: str, pose: str, e: dict, force: bool) -> str:
    raw = WORK / who / f"{pose}.png"
    if raw.exists() and not force:
        return f"・{who}/{pose} 已有回圖"
    d = CHARS / who
    orig = Image.open(d / e["file"]).convert("RGBA")
    limbs = np.logical_or.reduce(list(_limb_masks(d, e["parts"]).values()))
    if (who, pose) in HEAD_TOO:
        limbs = limbs | (_rgba(d / e["parts"]["head"]["file"])[..., 3] > 128)
    painted = np.asarray(on_bg(orig, GREEN)).copy()
    painted[limbs] = MAGENTA
    with tempfile.TemporaryDirectory(prefix="papa-body-") as tmp:
        wd = Path(tmp)
        on_bg(orig, GREEN).save(wd / "ref_0.png")
        Image.fromarray(painted).save(wd / "ref_1.png")
        raw.parent.mkdir(parents=True, exist_ok=True)
        try:
            _codex(wd)
            shutil.copy(wd / "out.png", raw)
            tool = "codex"
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:  # Codex 沒額度或找不到執行檔：改 agy → Vertex（業主定的順序）
            tool = _fallback(wd, raw, str(exc))
            if not tool:
                return f"✗ {who}/{pose} 生圖失敗（Codex、agy、Vertex 都不行）：{str(exc)[:200]}"
    return f"✓ {who}/{pose} 回圖 {raw.name}（{tool}）"


def _fallback(wd: Path, raw: Path, why: str) -> str | None:
    """Codex 不行時改 agy（兩張參考圖），再不行用 Vertex（只給塗洋紅的那張）；回傳用了哪個工具。"""
    agy = tuple(r for r in image_gen.RUNNERS if r[0] == "agy")
    try:
        image_gen.run_prompt(lambda names: PROMPT, raw, None, refs=[wd / "ref_0.png", wd / "ref_1.png"], runners=agy)
        return "agy"
    except RuntimeError as exc:
        print(f"  Codex 不行（{why[:120]}），agy 也不行（{str(exc)[:120]}），改用 Vertex")
    project = os.environ.get("PAPA_VERTEX_PROJECT", "")
    if not project:
        return None
    try:
        vertex_edit(Image.open(wd / "ref_1.png"), "Edit this image: remove every magenta area completely and repaint the body "
                    "behind it naturally (same clothes, same colored-pencil watercolor style), so the character has no arms or "
                    "legs where the magenta was. Keep everything else pixel-identical. Keep the flat pure #00FF00 background.",
                    project).save(raw)
    except Exception as vexc:  # noqa: BLE001 — 沒回圖、沒憑證都收成這個姿勢失敗，不中斷整批
        print(f"  Vertex 也失敗：{type(vexc).__name__}: {str(vexc)[:200]}")
        return None
    return "vertex"


def cut(who: str, pose: str, e: dict) -> tuple[str, dict | None]:
    raw = WORK / who / f"{pose}.png"
    if not raw.exists():
        return f"・{who}/{pose} 沒有回圖，略過", None
    d = CHARS / who
    parts = e["parts"]
    orig = _rgba(d / e["file"])
    body0 = WORK / who / f"{pose}_body0.webp"  # 第一次 cut 前的身體；重跑都從它開始，不會疊在上次的結果上
    if not body0.exists():
        shutil.copy(d / parts["body"]["file"], body0)
    body = _rgba(body0)
    head = _rgba(d / parts["head"]["file"])[..., 3] > 128
    masks = _limb_masks(d, parts)
    limbs = np.logical_or.reduce(list(masks.values()))
    ed = np.asarray(chroma_key(Image.open(raw).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS), GREEN))
    keep = limbs | head if (who, pose) in HEAD_TOO else limbs  # 頭沒被改的姿勢，頭也拿來對齊（軀幹露出來的太少時最穩）
    try:
        s, dx, dy = color_register(orig, ed, (orig[..., 3] > 200) & ~dilate(keep, 10))
    except RuntimeError as exc:
        return f"✗ {who}/{pose} {exc}", None
    ed = warp(ed, s, dx, dy)
    inside = float(((ed[..., 3] > 128) & (orig[..., 3] > 64)).sum() / max(1, (ed[..., 3] > 128).sum()))
    if (who, pose) in HEAD_TOO:
        masks["head"] = head
        zone = dilate(limbs | head, 6)
    else:
        zone = dilate(limbs, 6) & ~dilate(head, 2)
    ring = dilate(zone, 30) & ~dilate(zone, 8) & (orig[..., 3] > 200) & (ed[..., 3] > 200) & ~dilate(head, 4)  # 接縫附近；頭畫在最上面不算
    if ring.sum() < 500:  # 接縫附近太少（四肢蓋滿軀幹）：改用四肢以外的軀幹比色差，不能空著就算通過
        ring = (orig[..., 3] > 200) & (ed[..., 3] > 200) & ~dilate(head | limbs, 6)
    if ring.sum() < 500:
        return f"✗ {who}/{pose} 軀幹露出太少，沒辦法驗證色差", None
    ed = match_colors(ed, orig, ring)
    w = np.asarray(Image.fromarray((zone * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[..., None] / 255
    new = np.clip(body.astype(np.float32) * (1 - w) + ed.astype(np.float32) * w, 0, 255).astype(np.uint8)
    # 輪廓：不能超出原圖；四肢以外的地方原本的身體不能變透明（接縫外擴那 6px 也是）
    soft = [_rgba(d / parts[n]["file"])[..., 3] > 8 for n in LIMBS if parts.get(n)]  # 四肢的柔邊也算（外框墨線的半透明像素）
    if (who, pose) in HEAD_TOO:
        soft.append(_rgba(d / parts["head"]["file"])[..., 3] > 8)
    hole_ok = dilate(np.logical_or.reduce(soft), 3)
    new[..., 3] = np.where(hole_ok, new[..., 3], np.maximum(new[..., 3], body[..., 3]))
    new[..., 3] = np.minimum(new[..., 3], np.where(dilate(orig[..., 3] > 0, 1), 255, 0)).astype(np.uint8)
    outside_diff = float(np.abs(orig[..., :3].astype(int) - ed[..., :3].astype(int)).mean(-1)[ring].mean())
    comp = Image.fromarray(new)
    for n in ("hind", "front", "front2", "head"):
        if parts.get(n):
            comp.alpha_composite(Image.open(d / parts[n]["file"]).convert("RGBA"))
    oa, ca = orig[..., 3] > 128, np.asarray(comp)[..., 3] > 128
    qa = {"scale": round(s, 4), "dx": dx, "dy": dy, "inside": round(float(inside), 3), "outside_diff": round(outside_diff, 1),
          "iou": round(float((oa & ca).sum() / max(1, (oa | ca).sum())), 4),
          "remnant": {n: round(remnant(new, orig, m), 3) for n, m in masks.items()},
          "remnant_before": {n: round(remnant(body, orig, m), 3) for n, m in masks.items()}}
    fails = [k for k, ok in (("inside", qa["inside"] >= QA["inside"]), ("outside_diff", qa["outside_diff"] <= DIFF_OK.get((who, pose), QA["outside_diff"])),
                             ("iou", qa["iou"] >= QA["iou"])) if not ok]
    if fails:
        return f"✗ {who}/{pose} 不合格 {fails} {qa}", None
    save_webp(Image.fromarray(new), d / parts["body"]["file"])
    return f"✓ {who}/{pose} {qa}", qa


def _rot(img: Image.Image, deg: float, pivot: list[int]) -> Image.Image:
    return img.rotate(deg, resample=Image.Resampling.BICUBIC, center=(float(pivot[0]), float(pivot[1])))


def sheet(who: str, rig: dict) -> Path:
    d = CHARS / who
    tiles = []
    for pose, e in rig["poses"].items():
        parts = e["parts"]
        row = []
        for k in (0, 1):
            bg = Image.new("RGBA", (1024, 1024), (251, 243, 232, 255))
            bg.alpha_composite(Image.open(d / parts["body"]["file"]).convert("RGBA"))
            if k:
                for n, deg in (("hind", 20), ("front", 40), ("front2", -40)):
                    if parts.get(n):
                        bg.alpha_composite(_rot(Image.open(d / parts[n]["file"]).convert("RGBA"), deg, parts[n]["pivot"]))
                bg.alpha_composite(Image.open(d / parts["head"]["file"]).convert("RGBA"))
            row.append(bg.convert("RGB").resize((256, 256)))
        tiles.append(row)
    out = Image.new("RGB", (512, 256 * len(tiles)), "white")
    for i, (a, b) in enumerate(tiles):
        out.paste(a, (0, i * 256))
        out.paste(b, (256, i * 256))
    path = WORK / f"sheet_{who}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", nargs="*", default=["papa", "beibei", "dad", "mom", "baby", "sister", "brother"])
    ap.add_argument("--pose", nargs="*", default=None)
    ap.add_argument("--step", nargs="*", default=["gen", "cut", "sheet"])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for who in a.who:
        path = CHARS / who / "rig.json"
        rig = json.loads(path.read_text())
        for pose, e in rig["poses"].items():
            if a.pose and pose not in a.pose:
                continue
            if "gen" in a.step:
                print(gen(who, pose, e, a.force), flush=True)
            if "cut" in a.step:
                line, qa = cut(who, pose, e)
                print(line, flush=True)
                if qa:
                    e["parts"]["body"]["qa"] = qa
        path.write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n")
        if "sheet" in a.step:
            print("對照圖", sheet(who, rig), flush=True)


if __name__ == "__main__":
    main()
