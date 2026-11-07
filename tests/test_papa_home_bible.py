"""《帕帕貝貝家》設定集、Firestore store、來源切句、知識點檢查（離線）。"""
import copy
import json
import unittest
from datetime import date
from pathlib import Path

from mamababy_private.papa_home import bible as bb
from mamababy_private.papa_home import library as lib
from mamababy_private.papa_home import checks, sources
from mamababy_private.papa_home.store import PapaStore
from moneyerp.core.testing.fake_firestore import FakeFirestore

EP01 = json.loads((Path(lib.__file__).parent / "episodes" / "archive" / "ep01_baby.json").read_text(encoding="utf-8"))
TODAY = date(2026, 11, 10)


KIDS = {"sister": "2018-01", "brother": "2024-01"}  # 假日期：業主孩子的出生年月只存 Firestore，不進 repo


class TestBible(unittest.TestCase):
    def test_kids_ages_follow_calendar(self) -> None:
        b = bb.default_bible(KIDS)
        self.assertEqual(bb.ages(b, date(2026, 11, 30)), {"sister": (8, 10), "brother": (2, 10)})
        self.assertEqual(bb.ages(b, date(2027, 1, 1)), {"sister": (9, 0), "brother": (3, 0)})
        self.assertEqual(bb.age_numbers(b, date(2026, 11, 30)), {"8", "10", "106", "2", "34"})
        self.assertEqual(bb.ages(None, date(2026, 11, 30)), {})

    def test_published_records_episode_and_bumps_number(self) -> None:
        b = bb.default_bible(KIDS, next_episode_no=1)
        b2 = bb.published(b, {"episode": 1, "title": "換毛季", "logline": "…"}, date(2026, 12, 5))
        self.assertEqual(b2["next_episode_no"], 2)
        self.assertEqual(b2["episodes"][-1]["title"], "換毛季")
        self.assertEqual(b2["kids"], KIDS)
        self.assertEqual(b["episodes"], [])  # 純函式，不改原本的

    def test_brief_mentions_ages_and_past(self) -> None:
        b = bb.published(bb.default_bible(KIDS), {"episode": 1, "title": "換毛季"}, date(2026, 11, 8))
        text = bb.brief(b, TODAY)
        self.assertIn("姊姊 8 歲 10 個月、弟弟 2 歲 10 個月", text)
        self.assertIn("第 1 集《換毛季》", text)
        self.assertNotIn("寶寶", "".join(b["cast"]))


class TestStore(unittest.TestCase):
    def test_episode_status_history_and_topics(self) -> None:
        st = PapaStore(FakeFirestore())
        st.save_bible(bb.default_bible(KIDS))
        self.assertEqual(st.bible()["kids"], KIDS)
        st.save_episode(2, {"status": "scripted", "title": "副食品"})
        st.save_episode(2, {"status": "rendered"})
        st.add_feedback(2, "第二幕太長")
        ep = st.episode(2)
        self.assertEqual([h["status"] for h in ep["status_history"]], ["scripted", "rendered"])
        self.assertEqual(ep["title"], "副食品")
        self.assertEqual(ep["feedback"][0]["text"], "第二幕太長")
        with self.assertRaises(ValueError):
            st.save_episode(2, {"status": "lost"})
        st.save_topic("b", {"title": "B", "order": 2, "status": "queued"})
        st.save_topic("a", {"title": "A", "order": 1, "status": "queued"})
        st.save_topic("c", {"title": "C", "order": 0, "status": "used"})
        self.assertEqual([t["id"] for t in st.topics()], ["a", "b"])
        self.assertEqual(len(st.topics(None)), 3)


class TestSources(unittest.TestCase):
    def test_allowlist(self) -> None:
        self.assertTrue(sources.allowed("https://www.hpa.gov.tw/x.pdf"))
        self.assertTrue(sources.allowed("https://animal.moa.gov.tw/a"))
        self.assertFalse(sources.allowed("https://example.com/gov.tw"))
        self.assertFalse(sources.allowed("https://evilgov.tw/"))
        with self.assertRaises(ValueError):
            sources.load("https://example.com/a", get=lambda u: b"")

    def test_html_sentences_skip_scripts_and_menus(self) -> None:
        html = ("<html><nav>首頁 關於我們</nav><script>var a='不要這句話。';</script>"
                "<p>每次只添加一種新食物，由少量開始。</p><p>短</p><li>1 歲以下的寶寶不可餵食蜂蜜。</li></html>")
        rows = sources.load("https://www.hpa.gov.tw/a", get=lambda u: html.encode())
        self.assertEqual(rows, ["每次只添加一種新食物，由少量開始。", "1 歲以下的寶寶不可餵食蜂蜜。"])

    def test_big5_page_is_decoded(self) -> None:
        html = '<html><meta charset="big5"><p>每次只添加一種新食物，由少量開始。</p></html>'.encode("cp950")
        self.assertEqual(sources.load("https://www.hpa.gov.tw/a", get=lambda u: html), ["每次只添加一種新食物，由少量開始。"])

    def test_empty_source_raises(self) -> None:
        with self.assertRaises(ValueError):
            sources.load("https://www.hpa.gov.tw/a", get=lambda u: b"<html><nav>menu</nav></html>")

    def test_redirect_outside_allowlist_is_rejected(self) -> None:
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def geturl(self):
                return "https://evil.example.com/x"

            def read(self):
                return b"x"

        from unittest import mock
        with mock.patch("urllib.request.urlopen", return_value=Resp()):
            with self.assertRaises(ValueError):
                sources.fetch("https://www.hpa.gov.tw/a")

    def test_pdf_wrapped_lines_are_joined(self) -> None:
        text = "‧ 每次只添加一種新食物，由少量開始，逐漸增加，觀\n察 3-5 天。\n‧ 製作副食品時應注意衛生。"
        self.assertEqual(sources.sentences(sources.join_wrapped(text)),
                         ["每次只添加一種新食物，由少量開始，逐漸增加，觀察 3-5 天。", "製作副食品時應注意衛生。"])


class TestFacts(unittest.TestCase):
    def setUp(self) -> None:
        self.srcs = EP01["sources"]

    def test_numbers_must_come_from_sources(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["shots"][0]["lines"] = [{"text": ["每天要梳 8 次"], "at": 0.0, "dur": 2.0}]
        errs = checks.fact_errors(ep, self.srcs, {"4", "2"})
        self.assertTrue(any("台詞數字 ['8']" in e for e in errs))
        ep = copy.deepcopy(EP01)
        ep["shots"][13]["step"]["sub"] = "每天 5 次"
        self.assertTrue(any("字卡數字" in e for e in checks.fact_errors(ep, self.srcs, set())))

    def test_step_quote_must_be_verbatim(self) -> None:
        ep = copy.deepcopy(EP01)
        ep["shots"][13]["step"]["quote"] = "每天梳三次就不會掉毛。"  # 不是來源原句
        self.assertTrue(any("逐字複製" in e for e in checks.fact_errors(ep, self.srcs, set())))


if __name__ == "__main__":
    unittest.main()


def test_series_name_is_papa_baby_home_everywhere():
    """對外名稱一律「帕帕貝貝家」：prompt、skill、Slack 文字不能再出現舊名。"""
    from mamababy_private.config import REPO_ROOT as PROJECT_ROOT

    old = "帕帕" + "家"
    hits = []
    for top in ("mamababy_private", ".claude", "docs"):
        for path in (PROJECT_ROOT / top).rglob("*"):
            if "node_modules" in path.parts or not path.is_file() or path.suffix not in {".py", ".md", ".json", ".ts", ".tsx", ".js"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            # 營運紀錄（issue.md、selection/plans/superpowers）是照原樣保留的歷史，不掃
            if {"selection", "plans", "superpowers"} & set(path.parts) or path.name == "issue.md":
                continue
            if old in text and path.name != "papa-home-series.md":
                hits.append(str(path.relative_to(PROJECT_ROOT)))
    assert not hits, f"還有舊名 {old}：{hits}"
