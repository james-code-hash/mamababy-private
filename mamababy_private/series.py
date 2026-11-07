"""帕帕貝貝家接進每日社群：`moneyerp.series` entry point（介面見主程式 `moneyerp.core.plugins.Series`）。"""

from __future__ import annotations

import os
from pathlib import Path

from mamababy_private import config


class PapaSeries:
    """週二、週五的 Reels 格子發審過（`papa ship`／`papa approve`）、還沒排過的下一集。"""

    key = "papa_home"
    name = "帕帕貝貝家"
    keep_dir = "papa_home"  # 成片在 media_store.root()/papa_home，不被清理

    def __init__(self, client=None) -> None:
        self._client = client

    def _db(self):
        if self._client is None:
            from moneyerp.core.firestore_client import get_client
            self._client = get_client()
        return self._client

    def _store(self):
        from mamababy_private.papa_home.store import PapaStore
        return PapaStore(self._db())

    def live(self) -> bool:
        values = None
        if os.environ.get(config.LIVE_KEY, "") == "":
            snap = self._db().collection("settings").document("app").get()
            values = ((snap.to_dict() or {}).get("values") or {}) if snap.exists else {}
        return config.live_from(dict(os.environ), values)

    def next_to_post(self) -> dict | None:
        return self._store().next_to_post()

    def video(self, item: dict) -> tuple[Path, str]:
        from moneyerp.core import media_store
        media = item.get("media") or {}
        p = Path(media.get("path") or media_store.root() / media["dest"])
        if not p.is_file():
            raise FileNotFoundError(f"正式機找不到成片 {p}，請在正式機重跑 papa approve")
        return p, media["dest"]

    def mark_drafted(self, item: dict, day: str, post_ids: list[str]) -> None:
        self._store().save_episode(int(item["episode"]), {"daily_draft": {"day": day, "post_ids": list(post_ids)}})
