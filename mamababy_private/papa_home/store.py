"""《帕帕貝貝家》Firestore：設定集、集數、題目庫（都是小集合，可以整批讀）。

    papa_home_series/bible        設定集（bible.py）
    papa_home_episodes/{ep:03d}   每集：status、storyboard、sources、feedback、media（成片在正式機的位置，`papa ship`／`papa approve`）、
                                  daily_draft（每日排程排進 Postiz 的那天與草稿 id）、insights
    papa_home_topics/{id}         題目庫：title、pet_point、kid_point、reason、source_urls、status（queued/used）
"""
from __future__ import annotations

from datetime import datetime

SERIES, EPISODES, TOPICS = "papa_home_series", "papa_home_episodes", "papa_home_topics"
STATUSES = ("planned", "scripted", "rendered", "approved", "published", "rejected")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class PapaStore:
    def __init__(self, client):
        self.c = client

    # 設定集
    def bible(self) -> dict | None:
        snap = self.c.collection(SERIES).document("bible").get()
        return snap.to_dict() if snap.exists else None

    def save_bible(self, bible: dict) -> None:
        self.c.collection(SERIES).document("bible").set({**bible, "updated_at": _now()})

    # 集數
    def episode(self, no: int) -> dict | None:
        snap = self.c.collection(EPISODES).document(f"{int(no):03d}").get()
        return snap.to_dict() if snap.exists else None

    def save_episode(self, no: int, fields: dict) -> None:
        """只合併寫到的欄位；status 會一起記進 status_history。"""
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"沒有狀態 {fields['status']}")
        ref = self.c.collection(EPISODES).document(f"{int(no):03d}")
        doc = {**fields, "episode": int(no), "updated_at": _now()}
        if "status" in fields:
            old = (ref.get().to_dict() or {}).get("status_history", [])
            doc["status_history"] = [*old, {"status": fields["status"], "at": doc["updated_at"]}]
        ref.set(doc, merge=True)

    def add_feedback(self, no: int, text: str) -> None:
        old = (self.episode(no) or {}).get("feedback", [])
        self.save_episode(no, {"feedback": [*old, {"at": _now(), "text": text}]})

    def next_to_post(self) -> dict | None:
        """審過（approved）、有成片、還沒排進每日發文的最前面一集（集數小的先發）。"""
        rows = [d.to_dict() or {} for d in self.c.collection(EPISODES).stream()]
        ready = [r for r in rows if r.get("status") == "approved" and (r.get("media") or {}).get("dest")
                 and not r.get("daily_draft")]
        return min(ready, key=lambda r: int(r.get("episode") or 0)) if ready else None

    # 題目庫
    def topics(self, status: str | None = "queued") -> list[dict]:
        rows = [{**(d.to_dict() or {}), "id": d.id} for d in self.c.collection(TOPICS).stream()]
        rows = [r for r in rows if status is None or r.get("status", "queued") == status]
        return sorted(rows, key=lambda r: (r.get("order", 999), r["id"]))

    def topic(self, topic_id: str) -> dict | None:
        snap = self.c.collection(TOPICS).document(topic_id).get()
        return {**snap.to_dict(), "id": topic_id} if snap.exists else None

    def save_topic(self, topic_id: str, fields: dict) -> None:
        self.c.collection(TOPICS).document(topic_id).set({**fields, "updated_at": _now()}, merge=True)
