"""系列設定集（series bible）：角色、世界、孩子的出生年月、過去集數。存 Firestore `papa_home_series/bible`。

2026-11-05 業主重製：家裡是爸爸、媽媽、姊姊（國小）、弟弟（2 歲）、帕帕、貝貝；寶寶退役。
孩子的出生年月是業主家的個資，**只存 Firestore**（`kids`），repo 與測試只用假日期；年齡每集依日期自動算。
社群貼文的人設（真人爸爸口吻、大寶 2018-09 生、小寶 2024-08 生，年紀依日期換算）在 `moneyerp.core.persona`；改家庭成員時兩邊一起改。
"""
from __future__ import annotations

from datetime import date

CAST = {
    "papa": "帕帕：橘虎斑貓、藍色圍兜，家裡最早的成員，第一人稱旁白。嘴有點毒但很愛這個家。全片唯一的台詞來源。",
    "beibei": "貝貝：中型米克斯狗（柴犬感、折耳、紅項圈），熱情過頭、傻呼呼，帕帕的吐槽對象。不說話，只有表情和動作。",
    "dad": "爸爸：笨手笨腳，主要搞笑來源。不畫臉（背影、手、剪影），不說話。",
    "mom": "媽媽：比較懂、穩，示範正確做法；不演成兇或碎念。不畫臉，不說話。",
    "sister": "姊姊：國小，齊瀏海短鮑伯頭、黃白條紋 T 恤配牛仔吊帶裙。好奇、愛問、想幫忙照顧寵物和弟弟。旁白叫「姊姊」，不取名，不說話。",
    "brother": "弟弟：2 歲多的幼兒，小平頭、橘色恐龍 T 恤。愛笑、什麼都想摸、跟貝貝最好。旁白叫「弟弟」，不取名，不說話。",
}
RULES = (
    "只有帕帕說話（對話泡泡），台詞是帕帕的內心話、嘴有點毒但溫暖；台灣用語。"
    "不推商品、不寫價格、不說品牌名；自家商品只能在道具清單裡、以示範動作出現。"
    "孩子跟寵物相處要安全（不拉尾巴、不搶寵物的食物，2 歲的弟弟身邊一定有大人），不靠近危險物；爸媽不畫臉；"
    "不出現學校名稱、制服、地標等認得出這一家的東西。"
    "知識點（第二幕步驟字卡）只能根據提供的官方來源原句，不給醫療建議，只能說「出現 X 就去看醫生」。"
)
KID_LABEL = {"sister": "姊姊", "brother": "弟弟"}


def default_bible(kids: dict[str, str], next_episode_no: int = 1) -> dict:
    """開播時的設定集。kids＝{"sister": "YYYY-MM", "brother": "YYYY-MM"}（出生年月，只存 Firestore）。"""
    return {
        "cast": dict(CAST),
        "rules": RULES,
        "home": "台灣小公寓：客廳（living）、孩子房（nursery）、廚房（kitchen）。",
        "kids": dict(kids),
        "running_gags": ["帕帕：「我先說，…」開場", "貝貝把什麼都當玩具", "爸爸拿錯東西"],
        "episodes": [],
        "next_episode_no": next_episode_no,
    }


def ages(bible: dict | None, today: date) -> dict[str, tuple[int, int]]:
    """孩子在 today 幾歲幾個月：{"sister": (8, 2), ...}（以出生年月的 1 號算）。"""
    out = {}
    for who, born in ((bible or {}).get("kids") or {}).items():
        y, m = (int(x) for x in str(born).split("-")[:2])
        months = max(0, (today.year - y) * 12 + today.month - m)
        out[who] = (months // 12, months % 12)
    return out


def age_numbers(bible: dict | None, today: date) -> set[str]:
    """台詞裡可以出現的年齡數字（歲、零幾個月、總月數）。"""
    nums = set()
    for y, m in ages(bible, today).values():
        nums |= {str(y), str(m), str(y * 12 + m)}
    return nums


def ages_text(bible: dict | None, today: date) -> str:
    return "、".join(f"{KID_LABEL.get(w, w)} {y} 歲 {m} 個月" for w, (y, m) in ages(bible, today).items()) or "（沒設孩子出生年月）"


def season(today: date) -> str:
    m = today.month
    return {12: "冬天", 1: "冬天", 2: "冬天（過年前後）", 3: "春天（換毛季）", 4: "春天（換毛季）", 5: "春末梅雨",
            6: "夏天（梅雨）", 7: "夏天", 8: "夏天", 9: "初秋", 10: "秋天（換毛季）", 11: "入冬（換毛季）"}[m]


def published(bible: dict, ep: dict, today: date) -> dict:
    """某一集交付後的新設定集（純函式）：記下摘要、集數加一。"""
    out = {**bible, "episodes": [*bible.get("episodes", []),
                                 {"episode": ep["episode"], "title": ep["title"], "logline": ep.get("logline", ""),
                                  "published": today.isoformat()}]}
    out["next_episode_no"] = max(int(bible.get("next_episode_no", 1)), int(ep["episode"]) + 1)
    return out


def brief(bible: dict, today: date) -> str:
    """設定集摘要（`papa bible` 印出來給工作階段看）。"""
    eps = bible.get("episodes", [])[-6:]
    past = "\n".join(f"- 第 {e['episode']} 集《{e['title']}》：{e.get('logline', '')}" for e in eps) or "（還沒有）"
    return "\n".join([
        "【角色】", *bible["cast"].values(),
        f"【家】{bible['home']}",
        f"【時間】今天 {today.isoformat()}，{season(today)}；{ages_text(bible, today)}。",
        "【固定哏】" + "、".join(bible.get("running_gags", [])),
        "【最近幾集】", past,
        f"【規則】{bible['rules']}",
    ])
