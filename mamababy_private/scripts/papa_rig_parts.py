#!/usr/bin/env python3
"""《帕帕貝貝家》角色拆件：把每個姿勢的定裝圖拆成頭／身／前腳（手）／後腳圖層，頭像拆出眼白／瞳孔／張嘴，寫回 rig.json。

    uv run python -m mamababy_private.scripts.papa_rig_parts [--who papa beibei] [--pose sit] [--step gen cut eyes mouth] [--force]

做法（docs/papa-home-series.md §5.1）：
  gen   把去背的姿勢圖鋪在綠底（媽媽洋紅底）請 agy 編輯（沒對齊或沒出圖改 Vertex Nano Banana）成「沒有頭」「沒有頭也沒有前腳」（站／走／跑另外要「沒有頭沒有四隻腳」），
        張嘴版頭像同樣用編輯；原始回圖放 reports/papa-home/rig/gen/（不進版控），已有檔就不重生（--force 才重生）。
  cut   色鍵去背 → 對齊原圖（±12px 找最大 IoU）→ 相減得頭／前腳／後腳遮罩，零件像素一律取自原圖，只有被遮住的身體用模型補的；
        寫 p_<姿勢>_{body,head,front,hind}.webp 與軸心（頸點、肩點）到 rig.json poses.<姿勢>.parts。
  eyes  用 rig.json heads.*.eyes 的眼框把瞳孔（深色塊）分出來：pupil_<表情>.webp、把瞳孔補成眼白的 iris_<表情>.webp，
        瞳孔可移動範圍寫到 heads.<表情>.eyes[].pupil。
  mouth 張嘴版頭像與原圖相減得嘴巴貼片 mouth_<表情>.webp（說話時交替顯示），框寫到 heads.<表情>.mouth。

Vertex 專案讀環境變數 PAPA_VERTEX_PROJECT（或 --project）；憑證用 gcloud ADC。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from mamababy_private.papa_home import library as lib
from moneyerp.core.config import PROJECT_ROOT

WORK = Path(PROJECT_ROOT) / "reports" / "papa-home" / "rig"
MODEL = os.environ.get("PAPA_IMAGE_MODEL", "gemini-nano-banana-2.1")
GREEN, MAGENTA = (0, 255, 0), (255, 0, 255)
FACED = ("papa", "beibei", "baby", "sister", "brother")
# 這些姿勢的頭不換成頭像（側面、頭埋著、嘴叼東西），只切頭做轉頭／點頭
AVATAR_SKIP = {("papa", "walk"), ("sister", "walk"), ("brother", "walk"), ("beibei", "run"), ("beibei", "dive"), ("beibei", "hide"), ("beibei", "carry"), ("beibei", "carry_fur")}
GAZE_SKIP = {("papa", "unimpressed"), ("papa", "smug")}  # 半瞇眼：瞳孔只剩一條，視線只轉頭不動瞳孔
TALKERS = {"papa": ("neutral", "unimpressed", "smug", "soft"), "beibei": ("innocent",), "baby": ("curious",)}
STYLE = ("This is a paper-puppet part sheet, so the remaining parts must stay at exactly the same size and position on the "
         "same 1024x1024 canvas (feet on the same spot, same scale, nothing re-centred or enlarged). Keep the same character, "
         "pose, colours, pencil-and-watercolour style and line weight; every other pixel must stay identical. "
         "Plain flat {bg} background, no shadow, no text.")
PROMPTS = {
    "nohead": "Edit this image: remove the character's whole head (including ears, face, neck fur and any collar or bib on the neck). "
              "Paint the body naturally where the head was, as a headless paper puppet body with a smooth rounded neck stump. " + STYLE,
    "parts": "Edit this image for a paper-puppet part sheet: paint the character's whole HEAD (ears, face, neck fur and any collar or bib "
             "on the neck) as solid flat pure yellow (#FFFF00); paint the two FRONT legs (or arms), including the paws or hands and "
             "anything they hold, as solid flat pure magenta (#FF00FF); paint the two HIND legs and feet as solid flat pure cyan (#00FFFF). "
             "Flat fills with crisp edges exactly along the part outlines, no shading. Everything else stays identical. " + STYLE,
    "mouth": "Edit this image: the character is talking, so open the mouth a little (a small round open mouth, dark inside, "
             "with the tongue barely visible). Keep the eyes, nose, cheeks and everything else exactly the same. " + STYLE,
}


# ── Vertex ──────────────────────────────────────────────────────────────
def vertex_edit(img: Image.Image, prompt: str, project: str, timeout: int = 300) -> Image.Image:
    """一張參考圖＋編輯指令 → 一張圖（RGB）；用服務帳號打 Vertex（`content.vertex_image`）。"""
    from moneyerp.content import vertex_image

    return vertex_image.generate(prompt, [img], "1:1", model=MODEL, project=project, timeout=timeout)


def edit_image(src: Image.Image, key: tuple[int, int, int], prompt: str, project: str,
               check_alpha: bool = True) -> tuple[Image.Image, str]:
    """修圖：先 agy，回圖沒對齊（縮放 0.95–1.05、落在原圖內 ≥ 0.95、正方形）就改 Vertex（業主 2026-11-05 定的順序）。
    src：去背的原圖（RGBA）；回傳 (RGB 回圖, 用了哪個工具)。check_alpha=False 給塗色遮罩那張（輪廓會被改色，只看比例）。"""
    import tempfile

    from moneyerp.content import image_gen

    ref = on_bg(src, key)
    with tempfile.TemporaryDirectory(prefix="papa-edit-") as tmp:
        ref_path, out = Path(tmp) / "src.png", Path(tmp) / "agy.png"
        ref.save(ref_path)
        try:
            image_gen.run_prompt(
                lambda names: (f"Use your image generation tool to EDIT the attached image {names[0]} (do not draw a new picture): "
                               f"{prompt} Output the same 1:1 square canvas. Save the edited image as out.png in the current "
                               "directory. Do not end your reply until it is saved; then reply only with DONE."),
                out, None, refs=[ref_path], runners=tuple(r for r in image_gen.RUNNERS if r[0] == "agy"))
            img = Image.open(out).convert("RGB")
            why = ""
            if abs(img.width / img.height - 1) > 0.02:
                why = f"不是正方形（{img.width}×{img.height}）"
            else:
                img = img.resize(src.size, Image.Resampling.LANCZOS)
                if check_alpha:
                    s, _dx, _dy, inside = register(np.asarray(src)[..., 3], np.asarray(chroma_key(img, key))[..., 3])
                    if not (0.95 <= s <= 1.05 and inside >= 0.95):
                        why = f"沒對齊（縮放 {s:.2f}、在原圖內 {inside:.2f}）"
            if not why:
                return img, "agy"
            print(f"    agy 回圖{why}，改用 Vertex")
        except RuntimeError as exc:
            print(f"    agy 沒出圖（{str(exc)[:120]}），改用 Vertex")
    if not project:
        raise RuntimeError("agy 不行、又沒設 Vertex 專案（--project／PAPA_VERTEX_PROJECT）")
    return vertex_edit(ref, prompt, project), "vertex"


# ── 影像工具 ────────────────────────────────────────────────────────────
def on_bg(rgba: Image.Image, key: tuple[int, int, int]) -> Image.Image:
    bg = Image.new("RGBA", rgba.size, (*key, 255))
    bg.alpha_composite(rgba)
    return bg.convert("RGB")


def chroma_key(rgb: Image.Image, key: tuple[int, int, int]) -> Image.Image:
    """色鍵去背：離底色遠＝不透明；邊緣半透明並去色溢。"""
    a = np.asarray(rgb.convert("RGB")).astype(np.float32)
    k = np.array(key, np.float32)
    # 綠底：G 高且比 R、B 都高很多；洋紅底：R、B 高且 G 低。用「底色通道減其他通道」當距離
    if key == GREEN:
        spill = a[..., 1] - np.maximum(a[..., 0], a[..., 2])
    else:
        spill = np.minimum(a[..., 0], a[..., 2]) - a[..., 1]
    alpha = np.clip((90 - spill) / 60, 0, 1)  # spill>90 全透明、<30 全不透明
    dist = np.linalg.norm(a - k, axis=-1)
    alpha = np.where(dist < 60, 0, alpha)
    out = a.copy()
    if key == GREEN:  # 去綠溢：G 高過 R、B 的像素（邊緣、毛邊）把 G 壓到 R、B 的最大值
        spilled = (alpha > 0) & (out[..., 1] > np.maximum(out[..., 0], out[..., 2]) + 6)
        out[..., 1] = np.where(spilled, np.maximum(out[..., 0], out[..., 2]), out[..., 1])
    else:
        edge = (alpha > 0) & (alpha < 1)
        out[..., 0] = np.where(edge, np.minimum(out[..., 0], out[..., 1] + 40), out[..., 0])
        out[..., 2] = np.where(edge, np.minimum(out[..., 2], out[..., 1] + 40), out[..., 2])
    rgba = np.concatenate([out, (alpha * 255)[..., None]], axis=-1).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA")
    # 去掉零星噪點：alpha 開運算
    al = im.getchannel("A").filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    im.putalpha(al)
    return im


def register(ref_alpha: np.ndarray, alpha: np.ndarray) -> tuple[float, int, int, float]:
    """找相似變換 (scale, dx, dy) 讓 alpha 套回 ref_alpha：模型回圖常把身體縮小或移位。
    分數＝落在原圖裡的像素 − 2×跑到原圖外的像素（零件被拿掉後剩下的身體一定在原圖裡面），先 1/4 解析度粗找再全解析度細修。"""
    r_full = ref_alpha > 128
    a_full = alpha > 128
    rx0, ry0, rx1, ry1 = bbox(r_full)
    ax0, ay0, ax1, ay1 = bbox(a_full)

    def score(r: np.ndarray, a: np.ndarray, s: float, dx: float, dy: float, ds: int) -> float:
        h, w = a.shape
        im = Image.fromarray((a * 255).astype(np.uint8)).transform((w, h), Image.Transform.AFFINE, (1 / s, 0, -dx / ds / s, 0, 1 / s, -dy / ds / s),
                                                                     resample=Image.Resampling.NEAREST)
        t = np.asarray(im) > 128
        return float(np.logical_and(r, t).sum() - 2 * np.logical_and(t, ~r).sum())

    ds = 4
    r_ds = np.asarray(Image.fromarray((r_full * 255).astype(np.uint8)).resize((r_full.shape[1] // ds, r_full.shape[0] // ds), Image.Resampling.NEAREST)) > 128
    a_ds = np.asarray(Image.fromarray((a_full * 255).astype(np.uint8)).resize((a_full.shape[1] // ds, a_full.shape[0] // ds), Image.Resampling.NEAREST)) > 128
    best = (1.0, 0, 0, -1e18)
    for s in np.arange(0.80, 1.25, 0.02):
        # 初值：腳底對齊、水平中心對齊
        dx0 = (rx0 + rx1) / 2 - s * (ax0 + ax1) / 2
        dy0 = ry1 - s * ay1
        for ddx in range(-24, 25, 4):
            for ddy in range(-24, 25, 4):
                v = score(r_ds, a_ds, float(s), dx0 + ddx, dy0 + ddy, ds)
                if v > best[3]:
                    best = (float(s), int(round(dx0 + ddx)), int(round(dy0 + ddy)), v)
    s0, dx0, dy0, _ = best
    best = (s0, dx0, dy0, -1e18)
    for s in (s0 - 0.01, s0, s0 + 0.01):
        for dx in range(dx0 - 4, dx0 + 5, 2):
            for dy in range(dy0 - 4, dy0 + 5, 2):
                v = score(r_full, a_full, s, dx, dy, 1)
                if v > best[3]:
                    best = (s, dx, dy, v)
    inside = best[3] / max(1, a_full.sum() * best[0] ** 2)
    return best[0], best[1], best[2], inside


def warp(rgba: np.ndarray, s: float, dx: int, dy: int) -> np.ndarray:
    """套用 register 找到的相似變換（x' = s·x + dx）。"""
    h, w = rgba.shape[:2]
    im = Image.fromarray(rgba, "RGBA").transform((w, h), Image.Transform.AFFINE, (1 / s, 0, -dx / s, 0, 1 / s, -dy / s), resample=Image.Resampling.BICUBIC)
    return np.asarray(im)


def dilate(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * px + 1))
    return np.asarray(im) > 0


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(2 * px + 1))
    return np.asarray(im) > 0


def components(mask: np.ndarray) -> list[np.ndarray]:
    """連通區塊（4 鄰），大的在前。"""
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        comp = np.zeros_like(mask, bool)
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            comp[y, x] = True
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        out.append(comp)
    out.sort(key=lambda c: -int(c.sum()))
    return out


def bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def diff_mask(orig: np.ndarray, edited: np.ndarray, thr: float = 60.0, near: int = 40) -> np.ndarray:
    """原圖有、編輯後沒有（透明了，或在透明區附近顏色差很多）的像素。顏色差只看透明區附近，模型重畫毛紋時才不會整隻都算進去。"""
    oa, ea = orig[..., 3] > 128, edited[..., 3] > 128
    gone = oa & ~ea
    gone = erode(dilate(gone, 2), 2)
    both = oa & ea
    d = np.linalg.norm(orig[..., :3].astype(np.float32) - edited[..., :3].astype(np.float32), axis=-1)
    return gone | (both & (d > thr) & dilate(gone, near))


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """把被遮罩包住的洞補起來（臉的中央和補上的毛色太像，相減會留洞）。"""
    out = mask.copy()
    h, w = mask.shape
    for c in components(~mask):
        ys, xs = np.nonzero(c)
        if ys.min() == 0 or xs.min() == 0 or ys.max() == h - 1 or xs.max() == w - 1:
            continue
        out |= c
    return out


def cut_layer(orig: np.ndarray, mask: np.ndarray, feather: int = 2) -> Image.Image:
    """用遮罩從原圖切零件：只柔化零件之間的接縫，角色外框保留原圖的 alpha（不然外框墨線變淡）。"""
    seam = mask | (orig[..., 3] < 10)  # 透明背景當作遮罩內 → 模糊只發生在接縫
    soft = np.asarray(Image.fromarray((seam * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(feather))).astype(np.float32) / 255
    soft[~mask] = 0
    out = orig.copy()
    out[..., 3] = (orig[..., 3].astype(np.float32) * np.clip(soft * 1.3, 0, 1)).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def save_webp(im: Image.Image, path: Path) -> None:
    im.save(path, "WEBP", quality=90, exact=True, method=6)


# ── 步驟 ────────────────────────────────────────────────────────────────
def char_dir(who: str) -> Path:
    return lib.ASSETS / "characters" / who


def key_for(who: str) -> tuple[int, int, int]:
    return MAGENTA if who == "mom" else GREEN


def load_rig(who: str) -> dict:
    return json.loads((char_dir(who) / "rig.json").read_text(encoding="utf-8"))


def save_rig(who: str, rig: dict) -> None:
    (char_dir(who) / "rig.json").write_text(json.dumps(rig, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def variants_for(who: str, pose: str) -> list[str]:
    return ["nohead", "parts"]


def step_gen(who: str, poses: list[str], project: str, force: bool) -> None:
    rig = load_rig(who)
    gen = WORK / "gen"
    gen.mkdir(parents=True, exist_ok=True)
    key = key_for(who)
    jobs: list[tuple[Path, Image.Image, str]] = []
    for pose in poses:
        src = Image.open(char_dir(who) / rig["poses"][pose]["file"]).convert("RGBA")
        for v in variants_for(who, pose):
            jobs.append((gen / f"{who}_{pose}_{v}.png", src, PROMPTS[v]))
    for ex in TALKERS.get(who, ()):
        if ex in rig.get("heads", {}):
            src = Image.open(char_dir(who) / rig["heads"][ex]["file"]).convert("RGBA")
            jobs.append((gen / f"{who}_head_{ex}_mouth.png", src, PROMPTS["mouth"]))
    for path, src, prompt in jobs:
        if path.exists() and not force:
            print(f"  已有 {path.name}，略過")
            continue
        k = GREEN if path.stem.endswith("_parts") else key  # 零件塗色的那張一律綠底
        print(f"  生成 {path.name} …", flush=True)
        img, tool = edit_image(src, k, prompt.format(bg="magenta" if k == MAGENTA else "green"), project,
                               check_alpha=not path.stem.endswith("_parts"))
        print(f"    {tool}", flush=True)
        if img.size != src.size:
            img = img.resize(src.size, Image.Resampling.LANCZOS)
        img.save(path)


def clean_alpha(rgba: np.ndarray, min_area: int) -> np.ndarray:
    """模型回圖的底色常留下零星非底色小點：只留大塊的不透明區。"""
    keep = np.logical_or.reduce([c for c in components(rgba[..., 3] > 128) if c.sum() >= min_area] or [np.zeros(rgba.shape[:2], bool)])
    keep = dilate(keep, 2)
    out = rgba.copy()
    out[..., 3] = np.where(keep, out[..., 3], 0)
    return out


def _load_variant(who: str, pose_or_head: str, v: str, ref: np.ndarray) -> tuple[np.ndarray, float] | None:
    path = WORK / "gen" / f"{who}_{pose_or_head}_{v}.png"
    if not path.exists():
        return None
    keyed = np.asarray(chroma_key(Image.open(path), GREEN if v == "parts" else key_for(who)))
    keyed = clean_alpha(keyed, int((ref[..., 3] > 128).sum() * 0.01))
    s, dx, dy, fit = register(ref[..., 3], keyed[..., 3])
    return warp(keyed, s, dx, dy), fit


def inpaint(rgba: np.ndarray, mask: np.ndarray, rounds: int = 40) -> np.ndarray:
    """把 mask 內的像素用周圍顏色填起來（四肢抬起時露出的身體）：反覆用鄰近不透明像素的平均往內長。"""
    out = rgba.astype(np.float32).copy()
    known = erode(rgba[..., 3] > 250, 3) & ~mask  # 只拿實心內部當顏色來源，避開邊緣的溢色
    out[mask] = 0  # 只清要補的地方；邊緣半透明像素保留原色，不然會變黑邊
    for _ in range(rounds):
        pm = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
        pre = np.asarray(pm).astype(np.float32)
        a = (known * 255).astype(np.uint8)
        bl = np.asarray(Image.fromarray(a).filter(ImageFilter.BoxBlur(3))).astype(np.float32)
        rgb_bl = np.stack([np.asarray(Image.fromarray(np.where(known, pre[..., c], 0).astype(np.uint8)).filter(ImageFilter.BoxBlur(3))).astype(np.float32)
                           for c in range(3)], -1)
        grow = (~known) & (bl > 8) & mask
        if not grow.any():
            break
        out[grow, :3] = rgb_bl[grow] / (bl[grow][:, None] / 255)
        out[grow, 3] = 255
        known = known | grow
    filled = known & mask
    rgb = Image.fromarray(np.clip(out[..., :3], 0, 255).astype(np.uint8), "RGB")
    soft = np.asarray(rgb.filter(ImageFilter.GaussianBlur(7))).astype(np.float32)
    inner = erode(mask, 3) & filled
    out[inner, :3] = soft[inner]  # 只糊顏色，alpha 保持實心
    out[..., 3] = np.where(filled, 255, rgba[..., 3] * (~mask))
    return np.clip(out, 0, 255).astype(np.uint8)


def color_mask(rgba: np.ndarray, which: str) -> np.ndarray:
    """塗色遮罩：要夠純（橘毛、米毛的高光不能算成黃）。"""
    r, g, b = (rgba[..., i].astype(int) for i in range(3))
    opaque = rgba[..., 3] > 128
    if which == "magenta":
        return (r > 170) & (b > 170) & (g < 110) & ((r + b) // 2 - g > 140) & opaque
    if which == "yellow":
        return (r > 185) & (g > 185) & (b < 90) & ((r + g) // 2 - b > 140) & (abs(r - g) < 70) & opaque
    return (g > 170) & (b > 170) & (r < 110) & ((g + b) // 2 - r > 140) & opaque


def step_cut(who: str, poses: list[str], report: list[str]) -> None:
    rig = load_rig(who)
    out_dir = char_dir(who)
    for pose in poses:
        e = rig["poses"][pose]
        orig = np.asarray(Image.open(out_dir / e["file"]).convert("RGBA"))
        got = {v: _load_variant(who, pose, v, orig) for v in variants_for(who, pose)}
        if any(g is None for g in got.values()):
            report.append(f"{who}.{pose}：缺生成圖，先跑 --step gen")
            continue
        nohead, fit_h = got["nohead"]  # type: ignore[misc]
        painted, fit_p = got["parts"]  # type: ignore[misc]
        parts: dict = {}
        canvas_mask = orig[..., 3] > 128
        # 頭＝塗黃、前腳／手＝塗洋紅、後腳＝塗青色；太小的塊是雜訊
        head = color_mask(painted, "yellow") & canvas_mask
        head = dilate(erode(head, 2), 2)  # 開運算去掉細條紋
        head = erode(dilate(head, 4), 4)
        comps = components(head)
        if not comps:
            report.append(f"{who}.{pose}：模型沒把頭塗成黃色，略過")
            continue
        head = dilate(fill_holes(comps[0]), 2) & canvas_mask
        limb_masks: dict[str, np.ndarray] = {}
        for name, color in (("front", "magenta"), ("hind", "cyan")):
            m = color_mask(painted, color) & canvas_mask & ~dilate(head, 2)
            m = erode(dilate(m, 3), 3)
            cs = [c for c in components(m) if c.sum() > 1200][:2]
            if name == "front" and len(cs) == 2:  # 兩隻前腳分開存，才能一前一後動
                cs.sort(key=lambda c: bbox(c)[0])
                limb_masks["front"] = dilate(cs[0], 2) & canvas_mask
                limb_masks["front2"] = dilate(cs[1], 2) & canvas_mask
            elif cs:
                limb_masks[name] = dilate(np.logical_or.reduce(cs), 2) & canvas_mask
        front = limb_masks.get("front", np.zeros_like(head))
        front2 = limb_masks.get("front2")
        hind = limb_masks.get("hind")
        # 身體：頭的範圍用模型補的無頭版，四肢的範圍用周圍顏色補
        covered = dilate(head, 4)
        w = np.asarray(Image.fromarray((covered * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))).astype(np.float32) / 255
        body = orig.astype(np.float32) * (1 - w[..., None]) + nohead.astype(np.float32) * w[..., None]
        body = np.clip(body, 0, 255).astype(np.uint8)
        limb_all = front | (front2 if front2 is not None else False) | (hind if hind is not None else False)
        if limb_all.any():
            torso = (body[..., 3] > 128) & ~limb_all
            enclosed = erode(dilate(torso, 60), 60)  # 只補被軀幹包住的部分；垂在身體外面的手臂後面本來就是空的
            body = inpaint(body, dilate(limb_all, 5) & (body[..., 3] > 128) & enclosed)
        body_im = Image.fromarray(body, "RGBA")
        hx0, hy0, hx1, hy1 = bbox(head)
        ys, xs = np.nonzero(head)
        head_pivot = [int(xs.mean()), int(hy1 - (hy1 - hy0) * 0.12)]
        parts["body"] = {"file": f"p_{pose}_body.webp"}
        parts["head"] = {"file": f"p_{pose}_head.webp", "pivot": head_pivot, "bbox": [hx0, hy0, hx1, hy1]}
        save_webp(body_im, out_dir / parts["body"]["file"])
        save_webp(cut_layer(orig, head), out_dir / parts["head"]["file"])
        for name, m in (("front", front), ("front2", front2)):
            if m is not None and m.any():
                fx0, fy0, fx1, fy1 = bbox(m)
                parts[name] = {"file": f"p_{pose}_{name}.webp", "pivot": [int((fx0 + fx1) / 2), int(fy0 + (fy1 - fy0) * 0.15)],
                               "bbox": [fx0, fy0, fx1, fy1]}
                save_webp(cut_layer(orig, m), out_dir / parts[name]["file"])
        if hind is not None and hind.any():
            gx0, gy0, gx1, gy1 = bbox(hind)
            parts["hind"] = {"file": f"p_{pose}_hind.webp", "pivot": [int((gx0 + gx1) / 2), int(gy0 + (gy1 - gy0) * 0.15)],
                             "bbox": [gx0, gy0, gx1, gy1]}
            save_webp(cut_layer(orig, hind), out_dir / parts["hind"]["file"])
        e["parts"] = parts
        # 頭像套在身上的比例：頭像去背高度 ↔ 姿勢頭高
        if rig.get("heads") and (who, pose) not in AVATAR_SKIP:
            expr = e.get("expression") or next(iter(rig["heads"]))
            av = np.asarray(Image.open(out_dir / rig["heads"][expr]["file"]).convert("RGBA"))
            ax0, ay0, ax1, ay1 = bbox(av[..., 3] > 128)
            neck_y = rig["heads"][expr]["neck"][1]
            av_h = neck_y - ay0
            e["parts"]["head"]["avatar_scale"] = round((hy1 - hy0) / av_h * 1.08, 4)
        report.append(f"{who}.{pose}：對齊 fit 無頭 {fit_h:.2f}／塗色 {fit_p:.2f}，頭 {hx1 - hx0}×{hy1 - hy0}"
                      + (f"，前腳 {parts['front']['bbox']}" if "front" in parts else "，沒切到前腳")
                      + (f"，後腳 {parts['hind']['bbox']}" if "hind" in parts else ""))
    save_rig(who, rig)


def _pupil(av: np.ndarray, eye: dict, who: str) -> tuple[np.ndarray, np.ndarray] | None:
    """眼框內：內縮橢圓當眼睛內部，深色塊＝瞳孔（含高光），回傳 (瞳孔遮罩, 眼睛內部遮罩)。"""
    H, W = av.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = eye["x"] + eye["w"] / 2, eye["y"] + eye["h"] / 2
    rx, ry = eye["w"] / 2 * 0.86, eye["h"] / 2 * 0.86
    inside = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    rgb = av[..., :3].astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    if who == "papa":  # 藍色虹膜淺、瞳孔深藍
        dark = (lum < 115) & (rgb[..., 2] >= rgb[..., 0] - 5)  # 深藍與近黑都算，排除棕色墨線
    else:  # 狗、寶寶：眼白白、瞳孔深棕黑
        dark = lum < 105
    cand = inside & dark
    cand = erode(dilate(cand, 2), 2)
    comps = [c for c in components(cand) if c.sum() > 200]
    if not comps:
        return None
    pupil = comps[0]
    # 填洞（高光）
    hole = inside & ~pupil
    for c in components(hole):
        x0, y0, x1, y1 = bbox(c)
        if c.sum() < 1500 and (c & ~erode(inside, 2)).sum() == 0:
            pupil |= c
    return pupil, inside


def step_eyes(who: str, report: list[str]) -> None:
    rig = load_rig(who)
    out_dir = char_dir(who)
    for ex, h in rig.get("heads", {}).items():
        if not h.get("eyes") or (who, ex) in GAZE_SKIP:
            for eye in h.get("eyes") or []:
                eye.pop("pupil", None)
            h.pop("iris", None)
            h.pop("pupil", None)
            continue
        av = np.asarray(Image.open(out_dir / h["file"]).convert("RGBA")).copy()
        iris = np.zeros_like(av)
        pupils = np.zeros_like(av)
        ok = True
        for eye in h["eyes"]:
            got = _pupil(av, eye, who)
            if got is None:
                ok = False
                break
            pupil, inside = got
            px0, py0, px1, py1 = bbox(pupil)
            # 眼白：內部非瞳孔的顏色中位數，蓋住瞳孔
            ring = dilate(pupil, 9) & ~dilate(pupil, 2) & inside  # 眼白＝緊貼瞳孔外圍那一圈的亮色，不混到毛色
            whites = av[ring][:, :3].astype(np.float32)
            if len(whites):
                lum = whites @ np.array([0.299, 0.587, 0.114])
                bright = whites[lum >= np.percentile(lum, 50)]
                fill = np.median(bright, axis=0).astype(np.uint8)
            else:
                fill = np.array([235, 240, 245], np.uint8)
            patch = dilate(pupil, 6) & inside
            iris[patch, :3] = fill
            iris[patch, 3] = 255
            pupils[pupil] = av[pupil]
            pupils[pupil, 3] = 255
            ex_, ey_ = (px0 + px1) / 2, (py0 + py1) / 2
            cx, cy = eye["x"] + eye["w"] / 2, eye["y"] + eye["h"] / 2
            eye["pupil"] = {"cx": int(ex_), "cy": int(ey_), "w": px1 - px0, "h": py1 - py0,
                            "range": [int(max(4, eye["w"] / 2 * 0.86 - (px1 - px0) / 2)), int(max(3, eye["h"] / 2 * 0.86 - (py1 - py0) / 2))],
                            "center_dx": int(ex_ - cx), "center_dy": int(ey_ - cy)}
        if not ok:
            report.append(f"{who}.{ex}：分不出瞳孔，這個表情不做視線")
            for eye in h["eyes"]:
                eye.pop("pupil", None)
            continue
        h["iris"] = f"iris_{ex}.webp"
        h["pupil"] = f"pupil_{ex}.webp"
        save_webp(Image.fromarray(iris, "RGBA").filter(ImageFilter.GaussianBlur(0.6)), out_dir / h["iris"])
        save_webp(Image.fromarray(pupils, "RGBA"), out_dir / h["pupil"])
        report.append(f"{who}.{ex}：瞳孔 " + "、".join(f"{e['pupil']['w']}×{e['pupil']['h']} 可動 ±{e['pupil']['range']}" for e in h["eyes"]))
    save_rig(who, rig)


def step_mouth(who: str, report: list[str]) -> None:
    rig = load_rig(who)
    out_dir = char_dir(who)
    for ex in TALKERS.get(who, ()):
        h = rig.get("heads", {}).get(ex)
        if not h:
            continue
        av = np.asarray(Image.open(out_dir / h["file"]).convert("RGBA"))
        got = _load_variant(who, f"head_{ex}", "mouth", av)
        if got is None:
            report.append(f"{who}.{ex}：缺張嘴生成圖")
            continue
        edited, iou = got
        H, W = av.shape[:2]
        # 只看下半張臉中央（鼻子以下）
        yy, xx = np.mgrid[0:H, 0:W]
        zone = (yy > H * 0.42) & (yy < H * 0.82) & (xx > W * 0.28) & (xx < W * 0.72)
        d = np.linalg.norm(av[..., :3].astype(np.float32) - edited[..., :3].astype(np.float32), axis=-1)
        m = (d > 45) & zone & (av[..., 3] > 128)
        m = erode(dilate(m, 3), 3)
        comps = [c for c in components(m) if c.sum() > 800]
        if not comps:
            report.append(f"{who}.{ex}：張嘴版和原圖差異太小，略過（IoU {iou:.3f}）")
            h.pop("mouth", None)
            continue
        mouth = dilate(comps[0], 6) & (av[..., 3] > 128)
        x0, y0, x1, y1 = bbox(mouth)
        patch = edited.copy()
        soft = np.asarray(Image.fromarray((mouth * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255
        patch[..., 3] = (soft * 255).astype(np.uint8)
        h["mouth"] = {"file": f"mouth_{ex}.webp", "bbox": [x0, y0, x1, y1]}
        save_webp(Image.fromarray(patch, "RGBA"), out_dir / h["mouth"]["file"])
        report.append(f"{who}.{ex}：嘴巴貼片 {x1 - x0}×{y1 - y0}（IoU {iou:.3f}）")
    save_rig(who, rig)


def contact_sheet(who: str, poses: list[str]) -> Path:
    """每個姿勢：原圖｜身｜頭｜前腳｜後腳｜重組，給人眼檢查。"""
    rig = load_rig(who)
    cols = ["orig", "body", "head", "front", "hind", "rebuilt"]
    S = 256
    sheet = Image.new("RGB", (S * len(cols), S * len(poses)), (190, 190, 190))
    for r, pose in enumerate(poses):
        e = rig["poses"][pose]
        parts = e.get("parts") or {}
        tiles: dict[str, Image.Image | None] = {"orig": Image.open(char_dir(who) / e["file"]).convert("RGBA")}
        for k in ("body", "head", "front", "hind"):
            tiles[k] = Image.open(char_dir(who) / parts[k]["file"]).convert("RGBA") if k in parts else None
        front_tile = tiles["front"]
        if front_tile is not None and "front2" in parts:
            front_tile.alpha_composite(Image.open(char_dir(who) / parts["front2"]["file"]).convert("RGBA"))
        body_tile = tiles["body"]
        if body_tile is not None:
            rebuilt = body_tile.copy()
            for k in ("hind", "front", "head"):
                layer = tiles[k]
                if layer is not None:
                    rebuilt.alpha_composite(layer)
            if "front2" in parts:
                rebuilt.alpha_composite(Image.open(char_dir(who) / parts["front2"]["file"]).convert("RGBA"))
            tiles["rebuilt"] = rebuilt
        else:
            tiles["rebuilt"] = None
        for c, k in enumerate(cols):
            t = tiles[k]
            if t is not None:
                sheet.paste(t.resize((S, S)), (c * S, r * S), t.resize((S, S)))
    out = WORK / f"sheet_parts_{who}.png"
    sheet.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--who", nargs="*", default=list(lib.CHARACTERS), help="角色（預設全部）")
    ap.add_argument("--pose", nargs="*", default=None, help="姿勢（預設該角色全部）")
    ap.add_argument("--step", nargs="*", default=["gen", "cut", "eyes", "mouth"], choices=["gen", "cut", "eyes", "mouth", "sheet"])
    ap.add_argument("--project", default=os.environ.get("PAPA_VERTEX_PROJECT", ""), help="Vertex AI 的 GCP 專案（或環境變數 PAPA_VERTEX_PROJECT）")
    ap.add_argument("--force", action="store_true", help="已有生成圖也重生")
    args = ap.parse_args(argv)
    if "gen" in args.step and not args.project:
        print("要 --project 或環境變數 PAPA_VERTEX_PROJECT", file=sys.stderr)
        return 2
    report: list[str] = []
    for who in args.who:
        rig = load_rig(who)
        poses = args.pose or list(rig["poses"])
        bad = [p for p in poses if p not in rig["poses"]]
        if bad:
            print(f"{who} 沒有姿勢 {bad}", file=sys.stderr)
            return 2
        print(f"== {who}：{'、'.join(poses)}")
        if "gen" in args.step:
            step_gen(who, poses, args.project, args.force)
        if "cut" in args.step:
            step_cut(who, poses, report)
        if "eyes" in args.step and who in FACED:
            step_eyes(who, report)
        if "mouth" in args.step and who in TALKERS:
            step_mouth(who, report)
        if "sheet" in args.step or "cut" in args.step:
            print(f"  對照表：{contact_sheet(who, poses)}")
    for line in report:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
