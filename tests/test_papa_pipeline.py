"""《帕帕貝貝家》工作階段用的流程指令：機械檢查、自動補泡泡、截靜幀、交付（全部離線，用假物件）。"""
import copy
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest
from mamababy_private.papa_home import bible as bb
from mamababy_private.papa_home import checks, render, sources
from mamababy_private.papa_home import compile as comp
from mamababy_private.papa_home import library as lib

EPISODES = Path(lib.__file__).parent / "episodes"
EP01 = json.loads((EPISODES / "archive" / "ep01_baby.json").read_text(encoding="utf-8"))
BIBLE = bb.default_bible({"sister": "2018-01", "brother": "2024-01"}, 2)  # 假日期（真的出生年月只在 Firestore）


@pytest.mark.parametrize("path", sorted(EPISODES.glob("ep*.json")), ids=lambda p: p.stem)
def test_every_episode_in_repo_still_validates(path):
    """動作庫、素材或規則改了，repo 裡已經做好的每一集都還要能驗證、能重渲。"""
    ep = json.loads(path.read_text(encoding="utf-8"))
    assert comp.validate(ep) == []
    if ep.get("cut"):
        assert comp.validate(comp.cut_episode(ep), full=False) == []
    if ep.get("sources"):
        assert checks.fact_errors(ep, ep["sources"], {str(ep["episode"]), "4"}) == []
    assert comp.review(ep) == []  # 審片警告（憑空出現、疊在一起…）也要處理掉；刻意碰到用 touch


def test_short_bubble_hold_is_fixed():
    ep = copy.deepcopy(EP01)
    ep["shots"][0]["lines"][0]["dur"] = 1.4  # 「我先說，／這不全是我的。」9 個字＝要 1.8s
    notes = checks.fit_lines(ep)
    assert ep["shots"][0]["lines"][0]["dur"] == 1.8 and notes == ["s01 第 1 句停留 1.4→1.8s"]


def test_fit_lines_moves_single_line_earlier_and_leaves_impossible_ones():
    ep = {"shots": [{"id": "a", "dur": 2.0, "lines": [{"text": ["我先說，", "這不全是我的。"], "at": 0.5, "dur": 1.5}]},
                    {"id": "b", "dur": 1.5, "lines": [{"text": ["我先說，", "這不全是我的。"], "at": 0.0, "dur": 1.5}]},
                    {"id": "c", "dur": "兩秒", "lines": [{"text": ["x"], "at": 0, "dur": 0.2}]}]}
    notes = checks.fit_lines(ep)
    assert ep["shots"][0]["lines"][0] == {"text": ["我先說，", "這不全是我的。"], "at": 0.2, "dur": 1.8}  # 往後放不下，往前挪
    assert ep["shots"][1]["dur"] == 1.8 and ep["shots"][1]["lines"][0]["dur"] == 1.8  # 放不下：鏡頭拉長（最多 1 秒）
    assert len(notes) == 2
    still = {"shots": [{"id": "f", "type": "CU", "dur": 2.5, "head": {"who": "papa", "expr": "smug"},
                        "lines": [{"text": ["一二三四五六七", "一二三四五六七"], "at": 0.3, "dur": 2.2}]}]}
    checks.fit_lines(still)
    assert still["shots"][0]["dur"] == 2.5  # 拉到 3 秒以上又沒動作事件會像投影片：不拉


def test_check_without_bible_only_allows_source_and_episode_numbers():
    ep = copy.deepcopy(EP01)
    srcs = ep["sources"]
    four_months = bb.default_bible({"sister": "2018-01", "brother": "2026-07"})  # 舊第 1 集台詞有「4 個月」
    assert checks.check(ep, srcs, date(2026, 11, 10), four_months) == []
    ep["shots"][0]["lines"][0]["text"] = ["我先說，", "這 7 根不是我的。"]
    assert any("台詞數字 ['7']" in e for e in checks.check(ep, srcs, date(2026, 11, 10), None))


def test_source_whitelist_has_the_agreed_sites():
    for url in ("https://animal.moa.gov.tw/x.pdf", "https://www.aphia.gov.tw/a", "https://www.hpa.gov.tw/a",
                "https://www.tw-tvma.org/a", "https://www.healthychildren.org/a", "https://www.avma.org/a",
                "https://icatcare.org/a", "https://www.vet.cornell.edu/a", "https://www.who.int/a"):
        assert sources.allowed(url), url
    assert not sources.allowed("https://pethealth.com.tw/a")  # 熱門網站只能找靈感
    assert sources.sentences("Cats need fresh water every day. Short.\n一次只加一種新食物。") == [
        "Cats need fresh water every day.", "一次只加一種新食物。"]


def test_stills_names_each_frame_by_shot(tmp_path, monkeypatch):
    def fake_build(ep, project, audio, *a, **k):
        project.mkdir(parents=True, exist_ok=True)
        return project, []

    def fake_run(cmd, **k):
        out = Path(cmd[cmd.index("--output") + 1])
        out.mkdir(parents=True)
        for i in range(len(cmd[cmd.index("--at") + 1].split(","))):
            (out / f"frame-{i:02d}-at-{i}s.png").write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(render, "build", fake_build)
    monkeypatch.setattr(render.subprocess, "run", fake_run)
    frames = render.stills(EP01, tmp_path)
    assert list(frames) == [s["id"] for s in EP01["shots"]]
    assert frames["s01"] == tmp_path / "stills" / "s01.png" and frames["s01"].read_bytes() == b"png"


def test_ship_puts_videos_on_the_server_marks_approved_and_advances_bible(tmp_path, monkeypatch):
    import subprocess as sp

    from mamababy_private import cli

    ep = {**copy.deepcopy(EP01), "episode": 2, "topic": "shedding"}
    for s in ep["shots"]:  # 舊第 1 集台詞有寶寶月齡「4」，跟現在孩子的年齡對不上；這裡只測交付流程
        for line in s.get("lines") or []:
            line["text"] = [re.sub(r"\d", "", t) for t in line["text"]]
    board = tmp_path / "ep02.json"
    board.write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
    for k in ("full", "cut"):
        (tmp_path / f"papa_home_ep02_{k}.mp4").write_bytes(b"mp4")

    class Store:
        def __init__(self):
            self.episodes, self.topics, self.saved_bible = {}, {"shedding": {"status": "queued"}}, None

        def save_episode(self, no, fields):
            self.episodes[no] = fields

        def bible(self):
            return BIBLE

        def save_bible(self, b):
            self.saved_bible = b

        def topic(self, tid):
            return self.topics.get(tid)

        def save_topic(self, tid, fields):
            self.topics[tid].update(fields)

    store, cmds = Store(), []
    monkeypatch.setattr(cli, "_papa_store", lambda: store)
    monkeypatch.setattr(sp, "run", lambda cmd, **k: cmds.append(cmd) or sp.CompletedProcess(cmd, 0, "", ""))
    cli.cmd_papa_ship(type("A", (), {"storyboard": str(board), "dir": str(tmp_path), "host": "claw-arm-1"})())
    scps = [c for c in cmds if c[0] == "scp"]  # 在 MacBook 做：成片 scp 到正式機的社群素材資料夾
    assert [c[-1] for c in scps] == ["claw-arm-1:.moneyerp/social-media/papa_home/ep002.mp4",
                                     "claw-arm-1:.moneyerp/social-media/papa_home/ep002_cut.mp4"]
    media = store.episodes[2]["media"]  # 跟 papa approve 同格式：每日排程讀 media.dest（正式機 root()/dest）
    assert store.episodes[2]["status"] == "approved" and media["dest"] == "papa_home/ep002.mp4" and "path" not in media
    assert media["cut"]["dest"] == "papa_home/ep002_cut.mp4" and store.episodes[2]["daily_draft"] is None
    assert store.saved_bible["next_episode_no"] == 3 and store.saved_bible["episodes"][-1]["episode"] == 2
    assert store.topics["shedding"]["status"] == "used"


def test_ship_on_the_server_saves_locally(tmp_path, monkeypatch):
    from mamababy_private import cli
    from moneyerp.core import config

    monkeypatch.setattr(config, "SOCIAL_MEDIA_DIR", str(tmp_path / "media"))
    (tmp_path / "v.mp4").write_bytes(b"mp4")
    where = cli._papa_put_media(tmp_path / "v.mp4", "papa_home/ep002.mp4", None)
    assert where == str(tmp_path / "media" / "papa_home" / "ep002.mp4") and Path(where).read_bytes() == b"mp4"


def test_ship_refuses_without_the_rendered_video(tmp_path, monkeypatch):
    from mamababy_private import cli

    board = tmp_path / "ep02.json"
    board.write_text(json.dumps({**EP01, "episode": 2}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cli, "_papa_store", lambda: type("S", (), {"bible": lambda self: BIBLE})())
    with pytest.raises(SystemExit):
        cli.cmd_papa_ship(type("A", (), {"storyboard": str(board), "dir": str(tmp_path), "host": ""})())


def test_ship_applies_the_same_fact_checks_as_validate(tmp_path, monkeypatch):
    from mamababy_private import cli

    ep = {**copy.deepcopy(EP01), "episode": 2}
    ep["shots"][13]["step"]["quote"] = "每天梳三次就不會掉毛。"  # 不是來源原句
    board = tmp_path / "ep02.json"
    board.write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "papa_home_ep02_full.mp4").write_bytes(b"mp4")
    monkeypatch.setattr(cli, "_papa_store", lambda: type("S", (), {"bible": lambda self: BIBLE})())
    with pytest.raises(SystemExit):
        cli.cmd_papa_ship(type("A", (), {"storyboard": str(board), "dir": str(tmp_path), "host": ""})())


def test_validate_with_a_broken_bible_file_stops_instead_of_guessing(tmp_path):
    from mamababy_private import cli

    bad = tmp_path / "bible.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli._papa_bible_for(type("A", (), {"bible_file": str(bad)})())


def test_fit_lines_never_stretches_a_bubble_over_the_next_line():
    ep = {"shots": [{"id": "a", "dur": 4.0, "lines": [{"text": ["我先說，", "這不全是我的。"], "at": 0.0, "dur": 1.2},
                                                      {"text": ["好"], "at": 1.5, "dur": 1.2}]}]}
    assert checks.fit_lines(ep) == []  # 第 1 句要 1.8 秒，但第 2 句 1.5 秒就出來：不自動補，留給驗證報錯
    assert ep["shots"][0]["lines"][0]["dur"] == 1.2


def test_props_stop_retrying_on_missing_vertex_project_and_survive_credential_errors(tmp_path, monkeypatch):
    from mamababy_private.scripts import papa_props
    from moneyerp.content import image_gen

    def no_tools(*a, **k):
        raise RuntimeError("codex：沒額度；agy：沒出圖")

    monkeypatch.setattr(image_gen, "run_prompt", no_tools)
    monkeypatch.setattr(papa_props, "WORK", tmp_path)
    (tmp_path / "raw").mkdir()
    it = {"name": "x", "ref": "mom_bottle", "desc": "a spoon"}
    with pytest.raises(papa_props.ConfigError):
        papa_props.generate(it, tmp_path / "raw" / "x.png", "")

    class DefaultCredentialsError(Exception):
        pass

    def no_creds(*a, **k):
        raise DefaultCredentialsError("no ADC")

    monkeypatch.setattr(papa_props, "vertex_edit", no_creds)
    with pytest.raises(RuntimeError, match="Vertex 也失敗"):
        papa_props.generate(it, tmp_path / "raw" / "x.png", "proj")


def test_touch_puts_the_toucher_right_above_its_target():
    cast = [{"who": "mom", "touch": "papa"}, {"who": "papa"}, {"who": "sister"}]
    comp._touch_on_top(cast)
    assert [c["who"] for c in cast] == ["papa", "mom", "sister"]  # 緊貼被碰者上方，不多越過別人


def test_props_from_top_accepts_a_prop_that_only_touches_the_top_edge():
    import numpy as np
    from mamababy_private.scripts import papa_props

    rgba = np.zeros((1024, 1024, 4), np.uint8)
    rgba[0:400, 450:574] = (180, 180, 190, 255)  # 只從上緣伸下來的水龍頭
    assert "沒有東西碰到下緣或左右緣" in "；".join(papa_props.check(rgba))
    assert papa_props.check(rgba, from_top=True) == [] or all("邊緣" not in p for p in papa_props.check(rgba, from_top=True))
