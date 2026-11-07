"""《帕帕貝貝家》素材包：rig.json／scene.json 引用的檔案都在、錨點在畫布內。"""
import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from mamababy_private.config import ASSETS

ROOT = ASSETS
CHARACTERS = ["papa", "beibei", "dad", "mom", "sister", "brother", "baby"]
SCENES = ["living", "nursery", "kitchen"]


def _dilate(mask: "np.ndarray", px: int) -> "np.ndarray":
    return np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * px + 1))) > 0


def _inside(pt: list[int], size: tuple[int, int]) -> bool:
    return 0 <= pt[0] < size[0] and 0 <= pt[1] < size[1]


class TestPapaHomeAssets(unittest.TestCase):
    def test_character_rigs(self) -> None:
        for ch in CHARACTERS:
            d = ROOT / "characters" / ch
            rig = json.loads((d / "rig.json").read_text())
            size = tuple(rig["canvas"])
            self.assertTrue(rig["poses"], ch)
            for pose, e in rig["poses"].items():
                with self.subTest(character=ch, pose=pose):
                    im = Image.open(d / e["file"])
                    self.assertEqual(im.size, size)
                    self.assertEqual(im.mode, "RGBA")
                    self.assertGreater(e["world_height"], 0)
                    x0, y0, x1, y1 = e["bbox"]
                    self.assertTrue(0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1])
                    self.assertEqual(y1, rig["foot"][1])  # 腳底對齊
                    if "tail" in e:
                        self.assertEqual(Image.open(d / e["tail"]).size, size)
                        self.assertTrue(_inside(e["tail_pivot"], size))
            for expr, h in rig["heads"].items():
                with self.subTest(character=ch, head=expr):
                    self.assertEqual(Image.open(d / h["file"]).size, size)
                    self.assertTrue(_inside(h["neck"], (size[0], size[1] + 1)))

    def test_head_eyes_inside_canvas(self) -> None:
        """眨眼用的眼框：兩眼、都在畫布內、左眼在右眼左邊；閉眼表情是 null。"""
        for ch in ("papa", "beibei", "baby"):
            rig = json.loads((ROOT / "characters" / ch / "rig.json").read_text())
            W, H = rig["canvas"]
            for ex, head in rig["heads"].items():
                with self.subTest(character=ch, head=ex):
                    self.assertIn("eyes", head)
                    eyes = head["eyes"]
                    if eyes is None:
                        continue
                    self.assertEqual(len(eyes), 2)
                    for e in eyes:
                        self.assertTrue(0 <= e["x"] and e["x"] + e["w"] <= W and 0 <= e["y"] and e["y"] + e["h"] <= H, e)
                        self.assertRegex(e["color"], r"^#[0-9a-f]{6}$")
                    self.assertLess(eyes[0]["x"], eyes[1]["x"])

    def test_parts(self) -> None:
        """分件：每個姿勢的身／頭／前後腳檔都在、軸心在畫布內；有頭像的角色 avatar_scale 合理。"""
        for ch in CHARACTERS:
            d = ROOT / "characters" / ch
            rig = json.loads((d / "rig.json").read_text())
            size = tuple(rig["canvas"])
            for pose, e in rig["poses"].items():
                with self.subTest(character=ch, pose=pose):
                    parts = e.get("parts")
                    self.assertTrue(parts, f"{ch}.{pose} 還沒拆件（papa_rig_parts）")
                    self.assertIn("body", parts)
                    self.assertIn("head", parts)
                    self.assertIn("front", parts)
                    for name, pt in parts.items():
                        self.assertEqual(Image.open(d / pt["file"]).size, size, name)
                        if "pivot" in pt:
                            self.assertTrue(_inside(pt["pivot"], size), name)
                        if "bbox" in pt:
                            x0, y0, x1, y1 = pt["bbox"]
                            self.assertTrue(0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1], name)
                    sc = parts["head"].get("avatar_scale")
                    if sc is not None:
                        self.assertTrue(rig["heads"], f"{ch}.{pose} 沒頭像卻有 avatar_scale")
                        self.assertTrue(0.2 <= sc <= 1.2, sc)

    def test_gaze_and_mouth_layers(self) -> None:
        """視線：有 pupil 的眼睛要有 iris／pupil 檔、瞳孔在眼框內；嘴巴貼片檔在、框在畫布內。"""
        for ch in ("papa", "beibei", "baby"):
            d = ROOT / "characters" / ch
            rig = json.loads((d / "rig.json").read_text())
            W, H = rig["canvas"]
            for ex, head in rig["heads"].items():
                with self.subTest(character=ch, head=ex):
                    eyes = head.get("eyes") or []
                    if any(e.get("pupil") for e in eyes):
                        self.assertEqual(Image.open(d / head["iris"]).size, (W, H))
                        self.assertEqual(Image.open(d / head["pupil"]).size, (W, H))
                        for e in eyes:
                            pu = e["pupil"]
                            self.assertTrue(e["x"] <= pu["cx"] <= e["x"] + e["w"] and e["y"] <= pu["cy"] <= e["y"] + e["h"], pu)
                            self.assertTrue(pu["range"][0] >= 3 and pu["range"][1] >= 3, pu)
                    m = head.get("mouth")
                    if m:
                        self.assertEqual(Image.open(d / m["file"]).size, (W, H))
                        x0, y0, x1, y1 = m["bbox"]
                        self.assertTrue(0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H)
            self.assertTrue(any(h.get("mouth") for h in rig["heads"].values()) or ch != "papa", "帕帕要有嘴型")

    def test_pose_expression_heads(self) -> None:
        """姿勢專用表情頭（papa_pose_heads）：檔案在、QA 數字在門檻內、對齊原本的頭零件；特寫頭像的眨眼貼片只在眼睛附近。"""
        from mamababy_private.papa_home import library as lib

        for ch in ("papa", "beibei", "baby"):
            d = ROOT / "characters" / ch
            rig = json.loads((d / "rig.json").read_text())
            for pose, e in rig["poses"].items():
                hp = e["parts"]["head"]
                ha = np.asarray(Image.open(d / hp["file"]))[..., 3] > 128
                for ex, info in (hp.get("expressions") or {}).items():
                    with self.subTest(character=ch, pose=pose, expr=ex):
                        self.assertIn(ex, rig["heads"])
                        q = info["qa"]
                        self.assertGreaterEqual(q["iou"], 0.95)
                        self.assertLessEqual(q["body_diff"], 12)
                        self.assertLessEqual(max(abs(v) for v in q["center"]), 8)
                        self.assertLessEqual(abs(q["neck"]), 8)
                        na = np.asarray(Image.open(d / info["file"]))[..., 3] > 128
                        self.assertGreaterEqual((na & ha).sum() / (na | ha).sum(), 0.85)
                        self.assertFalse((na & ~_dilate(ha, 12)).any(), "表情頭超出原本頭的範圍")
                self.assertIn(e["expression"], lib.pose_expressions(ch, pose) | {None})
            for ex, h in rig["heads"].items():
                if not h.get("blink"):
                    continue
                with self.subTest(character=ch, blink=ex):
                    bk = np.asarray(Image.open(d / h["blink"]))[..., 3] > 128
                    eyes = np.zeros(bk.shape, bool)
                    for eye in h["eyes"]:
                        eyes[eye["y"]:eye["y"] + eye["h"], eye["x"]:eye["x"] + eye["w"]] = True
                    self.assertTrue(bk.any())
                    self.assertFalse((bk & ~_dilate(eyes, 20)).any(), "眨眼貼片超出眼睛範圍")

    def test_parts_recombine_to_pose(self) -> None:
        """零件疊回去＝姿勢原圖（外框不能變淡、不能破洞）。"""
        for ch in CHARACTERS:
            d = ROOT / "characters" / ch
            rig = json.loads((d / "rig.json").read_text())
            for pose, e in rig["poses"].items():
                with self.subTest(character=ch, pose=pose):
                    comp = Image.new("RGBA", tuple(rig["canvas"]))
                    for n in ("body", "hind", "front", "front2", "head"):
                        if e["parts"].get(n):
                            comp.alpha_composite(Image.open(d / e["parts"][n]["file"]).convert("RGBA"))
                    oa = np.asarray(Image.open(d / e["file"]).convert("RGBA"))[..., 3] > 128
                    ca = np.asarray(comp)[..., 3] > 128
                    self.assertGreaterEqual((oa & ca).sum() / (oa | ca).sum(), 0.99)

    def test_bodies_cleaned_of_limbs(self) -> None:
        """身體零件上不能還畫著手腳（四肢一動就多出手腳；2026-11-04 爸爸聳肩變 4 隻手）：每個姿勢的身體都要經過
        papa_rig_bodies 重補並通過 QA（對齊、接縫色差、零件拼回去）。殘影本身靠 sheet 人眼看（顏色比對會誤判）。"""
        for ch in CHARACTERS:
            rig = json.loads((ROOT / "characters" / ch / "rig.json").read_text())
            for pose, e in rig["poses"].items():
                with self.subTest(character=ch, pose=pose):
                    qa = e["parts"]["body"].get("qa")
                    self.assertIsNotNone(qa, f"{ch}.{pose} 身體還沒去掉四肢（papa_rig_bodies）")
                    self.assertGreaterEqual(qa["inside"], 0.97)
                    self.assertGreaterEqual(qa["iou"], 0.985)
                    self.assertLessEqual(abs(qa["dx"]) + abs(qa["dy"]), 20)  # 回圖沒有被大幅移位

    def test_pose_expressions_exist_as_heads(self) -> None:
        for ch in CHARACTERS:
            rig = json.loads((ROOT / "characters" / ch / "rig.json").read_text())
            for pose, e in rig["poses"].items():
                if e["expression"] and rig["heads"]:
                    self.assertIn(e["expression"], rig["heads"], f"{ch}.{pose}")

    def test_hands(self) -> None:
        d = ROOT / "characters" / "hands"
        rig = json.loads((d / "rig.json").read_text())
        for name, f in rig["files"].items():
            with self.subTest(hand=name):
                self.assertEqual(Image.open(d / f).size, tuple(rig["canvas"]))

    def test_scenes(self) -> None:
        for s in SCENES:
            d = ROOT / "scenes" / s
            sj = json.loads((d / "scene.json").read_text())
            size = tuple(sj["size"])
            with self.subTest(scene=s):
                self.assertEqual(Image.open(d / sj["layers"]["far"]["file"]).size, size)
                self.assertEqual(Image.open(d / sj["layers"]["mid"]["file"]).size, size)
                self.assertEqual(Image.open(d / sj["layers"]["near"]["file"]).size, tuple(sj["frame"]))
                self.assertGreaterEqual(size[0], 2 * sj["frame"][0])  # 夠 TRACK 橫移
                for name, sp in sj["spots"].items():
                    self.assertTrue(_inside([sp["x"], sp["y"]], size), name)
                    self.assertGreater(sp["px_per_cm"], 0)


if __name__ == "__main__":
    unittest.main()
