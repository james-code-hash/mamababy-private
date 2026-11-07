"""《帕帕貝貝家》分鏡：驗證、編譯（相機／泡泡／配樂）、寫 HyperFrames 專案。全部離線，不渲染。"""
import copy
import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mamababy_private.papa_home import compile as comp
from mamababy_private.papa_home import engine, render
from mamababy_private.papa_home import library as lib

EP01 = json.loads((Path(lib.__file__).parent / "episodes" / "archive" / "ep01_baby.json").read_text(encoding="utf-8"))


def _ep(**shot_overrides) -> dict:
    """ep01 的複本，第一個 WIDE 鏡套用覆寫。"""
    ep = copy.deepcopy(EP01)
    ep["shots"][0].update(shot_overrides)
    return ep


class TestValidate(unittest.TestCase):
    def test_pilot_episode_passes(self) -> None:
        self.assertEqual(comp.validate(EP01), [])
        self.assertEqual(comp.validate(comp.cut_episode(EP01), full=False), [])

    def test_reading_chars_skip_punctuation(self) -> None:
        self.assertEqual(comp.reading_chars("寶寶，4 個月，"), 5)
        self.assertEqual(comp.reading_chars("…那是我的毛。"), 5)

    def test_catches_bad_names(self) -> None:
        ep = _ep(cast=[{"who": "papa", "pose": "fly", "spot": "nowhere"}])
        errs = " ".join(comp.validate(ep))
        self.assertIn("沒有姿勢 fly", errs)
        self.assertIn("沒有站位 nowhere", errs)
        ep = _ep(sfx=[["explosion", 0.1]])
        self.assertIn("沒有音效 explosion", " ".join(comp.validate(ep)))

    def test_catches_text_limits(self) -> None:
        ep = _ep(lines=[{"text": ["這一行字實在是太長了啦超過十個字"], "at": 0, "dur": 2.0}])
        self.assertTrue(any("超過 10 字" in e for e in comp.validate(ep)))
        ep = _ep(lines=[{"text": ["我先說這不全是", "我的毛真的不是"], "at": 0, "dur": 1.2}])
        self.assertTrue(any("不夠讀" in e for e in comp.validate(ep)))
        ep = _ep(lines=[{"text": ["我先說"], "at": 1.5, "dur": 1.2}])
        self.assertTrue(any("超出鏡頭長度" in e for e in comp.validate(ep)))

    def test_title_card_cannot_open(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["shots"].insert(0, {"id": "s00", "type": "TITLE", "dur": 1.0, "act": "title"})
        self.assertTrue(any("第一鏡" in e for e in comp.validate(ep)))

    def test_step_needs_known_source(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["sources"].pop("S2")
        self.assertTrue(any("來源 S2" in e for e in comp.validate(ep)))

    def test_long_still_shot_is_rejected(self) -> None:
        """3 秒以上的全景／特寫要有動作事件，不然就是一張投影片（2026-11-04 試映回饋）。"""
        ep = _ep(dur=3.2, fx=[], freeze_at=None, lines=[{"text": ["我先說，", "這不全是我的。"], "at": 0.0, "dur": 2.0}],
                 cast=[{"who": "papa", "pose": "lie", "x": 790, "y": 1245, "ppc": 4.6}, {"who": "dad", "pose": "flail", "x": 1230, "y": 1840, "ppc": 6.2}])
        ep["shots"][0].pop("freeze_at")
        self.assertTrue(any("沒有動作事件" in e for e in comp.validate(ep)))
        for fix in ({"fx": ["tufts"]}, {"freeze_at": 0.0}, {"onoma": [{"text": "咚！", "at": 0.2}]}):
            ep2 = copy.deepcopy(ep)
            ep2["shots"][0].update(fix)
            self.assertEqual([e for e in comp.validate(ep2) if "動作事件" in e], [], fix)
        short = copy.deepcopy(ep)
        short["shots"][0]["dur"] = 2.0
        self.assertEqual([e for e in comp.validate(short) if "動作事件" in e], [])

    def test_fx_and_bg_spot_names(self) -> None:
        self.assertTrue(any("沒有效果 sparkle" in e for e in comp.validate(_ep(fx=["sparkle"]))))
        ep = copy.deepcopy(EP01)
        ep["shots"][1]["bg_spot"] = "roof"
        self.assertTrue(any("沒有站位 roof" in e for e in comp.validate(ep)))

    def test_full_length_bounds(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["shots"] = ep["shots"][:6]
        self.assertTrue(any("要在 45–120 秒" in e for e in comp.validate(ep)))

    def test_unknown_prop(self) -> None:
        ep = _ep(type="INSERT", hand={"prop": "laser_pointer"})
        self.assertTrue(any("laser_pointer" in e for e in comp.validate(ep)))
        self.assertEqual([e for e in comp.validate(ep, props=lib.props() | {"laser_pointer"}) if "laser" in e], [])


class TestValidateGuards(unittest.TestCase):
    """驗證器要在編譯前擋下會讓編譯當掉的壞分鏡。"""

    def test_top_level_fields(self) -> None:
        ep = copy.deepcopy(EP01)
        ep.pop("episode")
        ep["title"] = ""
        errs = " ".join(comp.validate(ep))
        self.assertIn("episode", errs)
        self.assertIn("title", errs)

    def test_shot_needs_id(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["shots"][3].pop("id")
        self.assertTrue(any("鏡號 id" in e for e in comp.validate(ep)))

    def test_pullout_and_pov_need_cast(self) -> None:
        for t in ("PULLOUT", "POV"):
            ep = _ep(type=t, cast=[])
            self.assertTrue(any(f"{t} 要有角色" in e for e in comp.validate(ep)), t)
        low = comp.compile_shot({"id": "x", "type": "PULLOUT", "dur": 3, "act": "close", "scene": "living"}, 0, EP01)
        self.assertEqual(low["cam_to"][2], 1.0)  # 沒角色也不當掉

    def test_fur_pile_needs_position(self) -> None:
        ep = _ep(fur_pile={"size": 300})
        self.assertTrue(any("fur_pile" in e for e in comp.validate(ep)))

    def test_demo_needs_ordered_times(self) -> None:
        ep = copy.deepcopy(EP01)
        demo = next(s for s in ep["shots"] if s.get("demo"))["demo"]
        demo["press_at"] = 1.0
        self.assertTrue(any("示範時間" in e for e in comp.validate(ep)))
        demo.pop("lift_at")
        self.assertTrue(any("lift_at" in e for e in comp.validate(ep)))

    def test_cut_with_unknown_shot_raises(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["cut"].append({"id": "s99", "dur": 2})
        self.assertTrue(any("s99" in e for e in comp.validate(ep)))
        with self.assertRaises(ValueError):
            comp.cut_episode(ep)

    def test_empty_bubble_does_not_crash_engine(self) -> None:
        self.assertIn("bubble", engine.bubble_html("s1", 0, [], (70, 230), None, "neutral", 0, 1.5))


class TestCompile(unittest.TestCase):
    def setUp(self) -> None:
        self.low = comp.compile_episode(EP01)
        self.by_id = {s["id"]: s for s in self.low["shots"]}

    def test_timing_is_contiguous(self) -> None:
        t = 0.0
        for s in self.low["shots"]:
            self.assertAlmostEqual(s["t"], t, places=3)
            t += s["d"]
        self.assertAlmostEqual(self.low["total"], 61.3)

    def test_camera_stays_inside_plate(self) -> None:
        for s in self.low["shots"]:
            if not s.get("cam"):
                continue
            W, H = lib.scene(s["scene"])["size"]
            for cx, cy, z in (s["cam"], s["cam_to"]):
                self.assertGreaterEqual(z, 1.0)
                self.assertGreaterEqual(cx - lib.FW / 2 / z, -0.5, s["id"])
                self.assertLessEqual(cx + lib.FW / 2 / z, W + 0.5, s["id"])
                self.assertGreaterEqual(cy - lib.FH / 2 / z, -0.5, s["id"])
                self.assertLessEqual(cy + lib.FH / 2 / z, H + 0.5, s["id"])

    def test_track_follows_mover(self) -> None:
        s06 = self.by_id["s06"]
        self.assertLess(s06["cam"][0], s06["cam_to"][0])
        self.assertTrue(s06["cast"][0]["hop"])

    def test_camera_push_is_visible(self) -> None:
        """全景慢推至少 10%，手機上才看得出畫面在動。"""
        s07 = self.by_id["s07"]
        self.assertGreaterEqual(s07["cam_to"][2] / s07["cam"][2], 1.10)

    def test_bubble_points_at_papa_or_shows_avatar(self) -> None:
        s07 = self.by_id["s07"]
        self.assertIn("target", s07["bubble"][0])  # 帕帕在畫面裡
        tx, ty = s07["bubble"][0]["target"]
        x, y = s07["bubble"][0]["pos"]
        self.assertLess(ty - y, 560)  # 泡泡貼著帕帕的頭（安全區內），不是釘在畫面上方
        self.assertGreaterEqual(y, lib.SAFE["top"])
        for sh in self.low["shots"]:
            for b in sh.get("bubble", []):
                self.assertLessEqual(b["pos"][0] + lib.bubble_size(b["text"], bool(b.get("avatar")))[0], lib.SAFE["right"], sh["id"])
        self.assertEqual(self.by_id["s06"]["bubble"][0]["avatar"], "neutral")  # 帕帕不在畫面
        self.assertEqual(self.by_id["s06"]["bubble"][0]["pos"], list(comp.DEFAULT_POS))
        self.assertEqual(self.by_id["s02"]["bubble"][0]["target"], list(comp.HEAD_TARGET))  # 帕帕特寫
        self.assertEqual(self.by_id["s02"]["bg"]["scene"], "living")  # 特寫背景是場景，不是單色底

    def test_seams_follow_shot_types(self) -> None:
        """接點：特寫前有帕帕→push、REACTION→iris（提早、換軌）、WHIP→whip、片尾→dip；硬切不超過三分之一。"""
        seams = {s["id"]: s["seam"] for s in self.low["shots"]}
        self.assertEqual(seams["s02"], "push")
        self.assertEqual(self.by_id["s01"]["seam_out"], "push")
        self.assertEqual(self.by_id["s01"]["push_to"], self.by_id["s01"]["papa_screen"])
        self.assertEqual(seams["s05"], "iris")
        self.assertEqual(self.by_id["s05"]["lead"], lib.IRIS_LEAD)
        self.assertEqual(self.by_id["s05"]["layer"], 2)
        self.assertEqual(seams["s12"], "whip")
        self.assertEqual(seams["s10"], "pull")
        self.assertEqual(seams["s08"], "iris")  # 爸爸聳肩那一鏡是場景反應鏡
        self.assertEqual(seams["s09"], "push")  # 前一鏡有帕帕 → 推進特寫
        self.assertEqual(seams[self.low["shots"][-1]["id"]], "dip")
        cuts = sum(1 for s in self.low["shots"][1:] if s["seam"] == "cut")
        self.assertLessEqual(cuts, len(self.low["shots"]) // 3)
        ep = copy.deepcopy(EP01)
        ep["shots"][1]["seam"] = "iris"
        self.assertEqual(comp.compile_episode(ep)["shots"][1]["seam"], "iris")  # 可覆寫
        ep2 = copy.deepcopy(EP01)
        ep2["shots"][6]["seam"] = "push"  # s07 前一鏡 s06 沒有帕帕：硬指定 push 也不能崩
        self.assertEqual(comp.compile_episode(ep2)["shots"][5]["push_to"], [540, 960])
        ep["shots"][1]["seam"] = "wipe"
        self.assertTrue(any("沒有接點 wipe" in e for e in comp.validate(ep)))

    def test_snap_to_beats_moves_cut_onto_beat(self) -> None:
        grid = {m: [round(0.5 * k, 3) for k in range(1, 400)] for m in lib.MOODS}
        snapped = comp.snap_to_beats(EP01, grid)
        self.assertEqual(comp.validate(snapped), [])  # 泡泡、示範都還讀得完
        t = 0.0
        for s in snapped["shots"][:-1]:
            t += s["dur"]
            self.assertAlmostEqual(t * 2, round(t * 2), places=2, msg=s["id"])  # 每個切點都在 0.5 s 的拍點上
        self.assertEqual(comp.snap_to_beats(EP01, {}), EP01)
        # 曲子比段落短：media_start 從頭的規則要和 music_plan 一樣，拍點才對得到同一個位置
        lengths = {"trouble": 10.0, "daily": 22, "solution": 34, "twist": 24, "theme": 20}
        snapped = comp.snap_to_beats(EP01, grid, lengths)
        low = comp.compile_episode(snapped, lengths)
        second = [m for m in low["music"] if m["mood"] == "trouble"][1]
        self.assertEqual(second["media_start"], 0.0)
        end = [s["t"] + s["d"] for s in low["shots"] if s["t"] >= second["t"]][0]
        self.assertAlmostEqual((end - second["t"]) * 2, round((end - second["t"]) * 2), places=2)

    def test_review_flags_pop_in_vanish_and_overlap(self) -> None:
        """審片警告：中途進場卻已在框內、提早消失、兩角色重疊。"""
        self.assertEqual(comp.review(EP01), [])
        ep = copy.deepcopy(EP01)
        s19 = next(s for s in ep["shots"] if s["id"] == "s19")
        runner = next(c for c in s19["cast"] if c.get("move_to") is not None)
        runner["x"] = 1700  # 起點在畫框內
        diver = next(c for c in s19["cast"] if c.get("action") == "dive")
        diver["show"] = [4.1, 4.5]  # 撲完就消失
        warns = " ".join(comp.review(ep))
        self.assertIn("憑空出現", warns)
        self.assertIn("憑空不見", warns)
        ep = copy.deepcopy(EP01)
        s07 = next(s for s in ep["shots"] if s["id"] == "s07")
        s07["cast"][1]["x"] = s07["cast"][0]["x"] + 40  # 不同座標才不會被 _separate 錯開
        s07["cast"][1]["y"] = s07["cast"][0]["y"]
        self.assertTrue(any("重疊" in w for w in comp.review(ep)))

    def test_head_shot_speed_lines_opt_in(self) -> None:
        self.assertTrue(self.by_id["s09"]["lines"])
        self.assertFalse(self.by_id["s22"]["lines"])

    def test_bubble_moves_below_step_card(self) -> None:
        shot = {"id": "x", "type": "INSERT", "dur": 4, "act": "act2", "scene": "living", "hand": {"prop": "mom_bottle"},
                "step": {"n": 1, "title": "t", "sub": "s", "source": "S1"}, "lines": [{"text": ["好"], "at": 0, "dur": 1.5}]}
        self.assertEqual(comp.compile_shot(shot, 0, EP01)["bubble"][0]["pos"], list(comp.LOW_POS))

    def test_music_continues_same_mood(self) -> None:
        moods = [(m["mood"], m["t"], m["media_start"]) for m in comp.compile_episode(dict(EP01, music="moods"))["music"]]
        self.assertEqual(moods[0], ("trouble", 0.0, 0.0))
        self.assertIn(("trouble", 14.5, 3.2), moods)  # 第二段出事配樂從上次停的地方接
        self.assertEqual(self.low["music"][-1]["fade_out"], 2.0)

    def test_single_bed_mode(self) -> None:
        """有 bed.mp3 時整集一首底樂（主題曲只在片頭片尾），沒有就退回依幕換曲。"""
        lengths = {"bed": 80.0, "theme": 20, "daily": 22, "trouble": 22, "solution": 34, "twist": 24}
        low = comp.compile_episode(EP01, lengths)
        self.assertEqual([m["mood"] for m in low["music"]], ["bed", "theme", "bed", "theme"])
        self.assertEqual(low["music"][2]["media_start"], low["music"][0]["d"])  # 片頭後接著上次停的地方
        moods = comp.compile_episode(EP01, {"theme": 20, "daily": 22, "trouble": 22, "solution": 34, "twist": 24})["music"]
        self.assertIn("trouble", [m["mood"] for m in moods])
        ep = dict(EP01, music="moods")
        self.assertIn("trouble", [m["mood"] for m in comp.compile_episode(ep, lengths)["music"]])
        self.assertTrue(any("music 要是" in e for e in comp.validate(dict(EP01, music="loop"))))

    def test_music_wraps_when_track_too_short(self) -> None:
        low = comp.compile_episode(EP01, {"trouble": 10.0, "daily": 22, "solution": 34, "twist": 24, "theme": 20})
        second = [m for m in low["music"] if m["mood"] == "trouble"][1]
        self.assertEqual(second["media_start"], 0.0)

    def test_cut_trims_lines_and_sfx(self) -> None:
        cut = comp.cut_episode(EP01)
        self.assertAlmostEqual(sum(s["dur"] for s in cut["shots"]), 24.4, places=3)
        s24 = next(s for s in cut["shots"] if s["id"] == "s24")
        self.assertEqual(s24["lines"][0]["at"], 0.4)
        s14 = next(s for s in cut["shots"] if s["id"] == "s14")
        self.assertLess(s14["demo"]["press_at"], s14["dur"])  # 示範時間跟著縮
        self.assertEqual(comp.validate(cut, full=False), [])
        for s in cut["shots"]:
            for line in s.get("lines", []):
                self.assertLessEqual(line["at"] + line["dur"], s["dur"] + 1e-6)
            for _, at in s.get("sfx", []):
                self.assertLess(at, s["dur"])


class TestActing(unittest.TestCase):
    """分件 rig 的表演欄位：驗證、編譯成低階、審片警告。"""

    def test_look_take_gesture_talk_compile(self) -> None:
        low = comp.compile_episode(EP01)
        by_id = {s["id"]: s for s in low["shots"]}
        papa = next(c for c in by_id["s08"]["cast"] if c["who"] == "papa")
        dad = next(c for c in by_id["s08"]["cast"] if c["who"] == "dad")
        self.assertEqual(papa["expr"], "smug")
        self.assertEqual(papa["take"], ["unimpressed", 1.4])
        self.assertGreater(papa["look"][0], 0)  # 爸爸在右邊
        self.assertEqual(papa["look"][2], 0.2)
        self.assertEqual(papa["talk"], [[0.1, 1.3], [1.35, 2.95]])
        self.assertEqual(dad["gesture"][0], "shrug")
        self.assertNotIn("expr", dad)  # 不畫臉
        baby = next(c for c in by_id["s05"]["cast"] if c["who"] == "baby")
        self.assertEqual(baby["expr"], "curious")  # 姿勢內建表情
        self.assertEqual(baby["take"], ["giggle", 0.4])
        runner = next(c for c in by_id["s19"]["cast"] if c["who"] == "beibei")
        self.assertLess(runner["look"][0], 0)  # 毛堆在左邊
        papa15 = next(c for c in by_id["s15"]["cast"] if c["who"] == "papa")
        self.assertEqual(papa15["expr"], lib.CLOSED_EYES["papa"])  # 場景閉眼＝換成閉眼表情頭
        self.assertEqual(papa15["gesture"], ["lean", 0.15, 1.0])
        self.assertEqual(by_id["s09"]["head_gesture"], ["gag", 0.08])
        self.assertEqual(by_id["s09"]["head_look"], [0.6, -0.4, 0.8])
        self.assertEqual(by_id["s02"]["head_talk"], [[0.0, 1.2]])  # 帕帕特寫有台詞預設嘴動
        self.assertNotIn("head_talk", by_id["s23"])  # 貝貝不說話

    def test_camera_look_is_centre(self) -> None:
        low = comp.compile_episode(EP01)
        papa = next(c for c in next(s for s in low["shots"] if s["id"] == "s07")["cast"] if c["who"] == "papa")
        self.assertEqual(papa["look"][:2], [0.0, 0.0])

    def test_flip_reverses_gesture_direction(self) -> None:
        ep = _ep(cast=[{"who": "papa", "pose": "sit", "x": 1100, "y": 1800, "flip": True, "gesture": "point"}])
        low = comp.compile_shot(ep["shots"][0], 0, ep)
        self.assertEqual(low["cast"][0]["gesture"][2], -1.0)

    def test_acting_validation(self) -> None:
        bad = [
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "mood": "angry"}, "沒有表情 angry"),
            ({"who": "dad", "pose": "stand", "x": 1, "y": 1, "mood": "smug"}, "不畫臉"),
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "gesture": "dance"}, "沒有動作 dance"),
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "look_at": "mom"}, "不在這一鏡"),
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "look_at": 3}, "look_at 要是"),
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "mood_to": "soft"}, "要有 mood_at"),
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "gesture": "nod", "gesture_at": 5}, "超出鏡頭長度"),
            ({"who": "papa", "pose": "sit", "x": 1, "y": 1, "eyes": "half"}, "eyes 要是"),
            ({"who": "beibei", "pose": "hide", "x": 1, "y": 1, "mood": "happy"}, "沒有 happy 表情"),  # 臉被爪子遮住，只有原本的頭
            ({"who": "beibei", "pose": "hide", "x": 1, "y": 1, "eyes": "closed"}, "沒有閉眼表情"),
        ]
        errs = comp.validate(_ep(cast=[{"who": "kitty", "pose": "sit", "x": 1, "y": 1, "mood": "happy"}]))  # 角色名錯不能讓驗證崩潰
        self.assertTrue(any("kitty" in e for e in errs), errs)
        for cast, msg in bad:
            with self.subTest(msg=msg):
                errs = " ".join(comp.validate(_ep(cast=[cast])))
                self.assertIn(msg, errs)
        ok = _ep(cast=[{"who": "papa", "pose": "sit", "x": 1100, "y": 1800, "look_at": [1300, 1500], "mood_to": "soft", "mood_at": 1.0, "gesture": "shrug"}])
        self.assertEqual([e for e in comp.validate(ok) if "s01" in e], [])
        ep = copy.deepcopy(EP01)
        ep["shots"][1]["head"]["gesture"] = "shrug"
        self.assertTrue(any("頭像鏡只能做" in e for e in comp.validate(ep)))
        ep["shots"][1]["head"].pop("gesture")
        ep["shots"][1]["head"]["look"] = [2, 0]
        self.assertTrue(any("head.look" in e for e in comp.validate(ep)))

    def test_review_wants_acting_with_lines(self) -> None:
        ep = copy.deepcopy(EP01)
        s07 = next(s for s in ep["shots"] if s["id"] == "s07")
        for c in s07["cast"]:
            for k in ("look_at", "look_at_at", "mouth", "gesture", "gesture_at", "mood"):
                c.pop(k, None)
        self.assertTrue(any("s07：有台詞卻沒有任何動作" in w for w in comp.review(ep)))
        self.assertEqual(comp.review(EP01), [])

    def test_cut_drops_acting_past_new_end(self) -> None:
        cut = comp.cut_episode(EP01)
        s19 = next(s for s in cut["shots"] if s["id"] == "s19")
        papa = next(c for c in s19["cast"] if c["who"] == "papa")
        self.assertNotIn("mood_to", papa)  # 2.7s 的換表情超出 3.0s 精華版尾端
        self.assertNotIn("look_at", papa)
        self.assertEqual(comp.validate(cut, full=False), [])

    def test_hide_bubbles_keeps_talk(self) -> None:
        low = comp.compile_episode(dict(EP01, hide_bubbles=True))
        s07 = next(s for s in low["shots"] if s["id"] == "s07")
        self.assertEqual(s07["bubble"], [])
        self.assertTrue(next(c for c in s07["cast"] if c["who"] == "papa")["talk"])


class TestEngine(unittest.TestCase):
    def test_scene_head_uses_pose_expression(self) -> None:
        """場景裡換表情＝換成這個姿勢自己的表情頭（角度、大小跟身體一致），不是正面頭像。"""
        s = {"id": "s01", "type": "WIDE", "scene": "living", "dur": 3}
        c = comp._low_cast({"who": "papa", "pose": "sit", "x": 1100, "y": 1800, "mood": "smug", "mood_to": "surprised", "mood_at": 1.0}, s, None)
        c["ppc"] = 3.0
        html, _ = engine.char_html("s01", 0, c)
        heads = re.findall(r'src="assets/characters/papa/([^"]*head[^"]*)"', html)
        self.assertEqual(heads, ["p_sit_head_smug.webp", "p_sit_head_surprised.webp"])
        talk = comp._low_cast({"who": "beibei", "pose": "sit", "x": 1, "y": 1, "mouth": "talk"},
                              {**s, "lines": [{"at": 0.2, "dur": 1.0}, {"at": 1.4, "dur": 1.0, "avatar": "papa"}]}, None)
        self.assertEqual(talk["talk"], [[0.2, 1.2]])  # 帕帕頭像旁白不算貝貝在講
        _, _, js = engine.avatar_html("s02-hd", "papa", "smug", "unimpressed", {"talk": [[0.0, 2.0]], "D": 2.0})
        self.assertIn('talk("#s02-hd-h0-m"', " ".join(js))
        self.assertIn('talk("#s02-hd-h1-m"', " ".join(js))  # take 換臉後嘴接著動
        closed = comp._low_cast({"who": "beibei", "pose": "sit", "x": 1, "y": 1, "eyes": "closed"}, s, None)
        self.assertEqual(closed["expr"], lib.CLOSED_EYES["beibei"])

    def test_writes_project(self) -> None:
        low = comp.compile_episode(EP01)
        with TemporaryDirectory() as d:
            engine.write_project(low, Path(d), {"scratch": 1.2, "pop": 0.3})
            index = (Path(d) / "index.html").read_text(encoding="utf-8")
            self.assertIn('data-duration="61.3"', index)
            self.assertEqual(index.count("data-composition-src="), 24)
            self.assertIn('data-timeline-role="music"', index)
            s05 = re.search(r'<div id="s05" [^>]*>', index).group(0)  # 圓場：提早開始、第二軌、疊在上面
            self.assertIn('data-track-index="2"', s05)
            self.assertIn("z-index:5", s05)
            s04 = re.search(r'<div id="s04" [^>]*>', index).group(0)
            t04, d04 = (float(re.search(rf'data-{k}="([\d.]+)"', s04).group(1)) for k in ("start", "duration"))
            t05 = float(re.search(r'data-start="([\d.]+)"', s05).group(1))
            self.assertAlmostEqual(t05, t04 + d04 - 2 * lib.IRIS_LEAD, places=3)  # 兩鏡重疊一個 lead
            self.assertIn('src="assets/sfx/scratch.mp3"', index)
            self.assertNotIn("assets/sfx/gag.mp3", index)  # 沒有長度＝沒有檔，略過
            for s in low["shots"]:
                html = (Path(d) / "compositions" / f"{s['id']}.html").read_text(encoding="utf-8")
                self.assertIn(f'window.__timelines["{s["id"]}"] = root;', html)
                self.assertIn("window.__timelines = window.__timelines || {};", html)
                self.assertIn(f'data-composition-id="{s["id"]}"', html)
                self.assertIsNone(re.search(r"__[A-Z]+__", html))
            title = (Path(d) / "compositions" / "s03.html").read_text(encoding="utf-8")
            self.assertIn("第 1 集｜換毛季", title)
            self.assertIn(lib.SERIES_TITLE, title)
            cu = (Path(d) / "compositions" / "s02.html").read_text(encoding="utf-8")
            self.assertIn('data-motion-blur="on"', cu)
            self.assertIn('scale:1.28', cu)  # push 進場：從放大模糊落定
            self.assertNotIn("breathe(\"#s02-hd\"", cu)  # 頭像不再呼吸迴圈
            s01 = (Path(d) / "compositions" / "s01.html").read_text(encoding="utf-8")
            self.assertIn('scale:1.5,filter:"blur(10px)"', s01)  # push 離場：推進帕帕
            s05 = (Path(d) / "compositions" / "s05.html").read_text(encoding="utf-8")
            self.assertIn("clipPath", s05)
            self.assertIn("background:transparent", s05)
            self.assertIn("scenes/living/far.webp", cu)  # 特寫背景是模糊的場景
            self.assertIn('class="blinkp"', cu)  # 會眨眼（同一張頭像的閉眼貼片，不畫假眼皮）
            self.assertNotIn("NotoTC", cu)  # 全片一種字體
            wide = (Path(d) / "compositions" / "s07.html").read_text(encoding="utf-8")
            self.assertIn('class="shadow"', wide)  # 接觸陰影
            self.assertIn("idle(", wide)
            self.assertIn('class="warm"', wide)
            soft = (Path(d) / "compositions" / "s15.html").read_text(encoding="utf-8")
            self.assertNotIn('class="lid', soft)  # 閉眼表情不眨眼
            self.assertIn('play([["to","#s15-c1-hg",{"rotation":5.0', soft)  # 靠過去（動作庫 lean）
            s08 = (Path(d) / "compositions" / "s08.html").read_text(encoding="utf-8")
            self.assertIn('"#s08-c0-front",{"rotation":38', s08)  # 爸爸聳肩：手臂是獨立零件
            self.assertIn("p_stand_front", s08)
            self.assertIn('take("#s08-c1-hg"', s08)  # 帕帕得意→嫌棄的 take
            self.assertIn("papa/p_sit_head_smug.webp", s08)  # 姿勢自己的表情頭，不是正面頭像
            self.assertIn("papa/p_sit_head_unimpressed.webp", s08)
            self.assertIn('bob("#s08-c1-hg"', s08)  # 場景裡說話＝頭輕點（沒有對齊的嘴型貼片）
            self.assertIn("look(", s08)
            s09 = (Path(d) / "compositions" / "s09.html").read_text(encoding="utf-8")
            self.assertIn('play([["to","#s09-hg",{"yPercent":1.0,"scaleY":0.96', s09)  # 乾嘔
            self.assertNotIn('class="pupil"', s09)  # 瞳孔不移動（原位會留白斑），看向＝轉頭
            self.assertIn("look(", s09)
            step = (Path(d) / "compositions" / "s16.html").read_text(encoding="utf-8")
            self.assertIn('class="st"', step)
            self.assertNotIn('class="step"', step)

    def test_text_is_escaped(self) -> None:
        html = engine.bubble_html("s1", 0, ["<b>壞</b>"], (70, 230), None, "neutral", 0, 1.5)
        self.assertIn("&lt;b&gt;", html)


class TestRenderBuild(unittest.TestCase):
    def test_build_without_audio_is_silent(self) -> None:
        with TemporaryDirectory() as d:
            project, errors = render.build(EP01, Path(d) / "full", Path(d) / "no-audio")
            self.assertTrue(any("無聲" in e for e in errors))
            self.assertTrue((project / "assets" / "characters" / "papa" / "rig.json").exists())
            self.assertTrue((project / "assets" / "props" / "comb_b_full.webp").exists())
            self.assertNotIn("<audio", (project / "index.html").read_text(encoding="utf-8"))

    def test_episode_props_join_library_props(self) -> None:
        with TemporaryDirectory() as d:
            extra = Path(d) / "props"
            extra.mkdir()
            (extra / "new_toy.webp").write_bytes((lib.ASSETS / "props" / "hairball.webp").read_bytes())
            project, _ = render.build(EP01, Path(d) / "full", None, extra)
            self.assertTrue((project / "assets" / "props" / "new_toy.webp").exists())
            self.assertTrue((project / "assets" / "props" / "hairball.webp").exists())


if __name__ == "__main__":
    unittest.main()
