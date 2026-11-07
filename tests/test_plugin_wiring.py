"""帕帕貝貝家經 entry points 接進主程式：papa 指令、每週系列、成片保留、上線開關。"""
import argparse

from moneyerp.core import plugins
from moneyerp.core.testing.fake_firestore import FakeFirestore

from mamababy_private import config
from mamababy_private.series import PapaSeries


def test_entry_points_are_installed():
    plugins._series_all.cache_clear()
    s = plugins.series()
    assert isinstance(s, PapaSeries) and isinstance(s, plugins.Series)
    assert plugins.keep_dirs() == ("papa_home",)
    parser = argparse.ArgumentParser()
    assert "papa" in plugins.register_cli(parser.add_subparsers(dest="module"))


def test_live_env_wins_then_console_value(monkeypatch):
    db = FakeFirestore()
    db.collection("settings").document("app").set({"values": {config.LIVE_KEY: "1"}})
    monkeypatch.delenv(config.LIVE_KEY, raising=False)
    assert PapaSeries(db).live() is True
    monkeypatch.setenv(config.LIVE_KEY, "0")
    assert PapaSeries(db).live() is False
    monkeypatch.delenv(config.LIVE_KEY)
    assert PapaSeries(FakeFirestore()).live() is False


def test_next_episode_video_and_mark_drafted(tmp_path, monkeypatch):
    from moneyerp.core import media_store

    from mamababy_private.papa_home.store import PapaStore
    db = FakeFirestore()
    st = PapaStore(db)
    st.save_episode(2, {"status": "approved", "title": "換毛季", "media": {"dest": "papa_home/ep002.mp4"}})
    st.save_episode(1, {"status": "approved", "title": "已排", "media": {"dest": "x"}, "daily_draft": {"day": "d"}})
    monkeypatch.setattr(media_store, "root", lambda: tmp_path)
    s = PapaSeries(db)
    item = s.next_to_post()
    assert item["episode"] == 2
    try:
        s.video(item)
        raise AssertionError("沒有成片應該 raise")
    except FileNotFoundError as exc:
        assert "papa approve" in str(exc)
    (tmp_path / "papa_home").mkdir()
    (tmp_path / "papa_home" / "ep002.mp4").write_bytes(b"mp4")
    assert s.video(item) == (tmp_path / "papa_home" / "ep002.mp4", "papa_home/ep002.mp4")
    s.mark_drafted(item, "2026-11-10", ["p1", "p2"])
    assert st.episode(2)["daily_draft"] == {"day": "2026-11-10", "post_ids": ["p1", "p2"]}
    assert s.next_to_post() is None
