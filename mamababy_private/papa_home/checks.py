"""分鏡的機械檢查與自動修正（Claude Code 工作階段寫分鏡，這裡只驗證、只修機械性錯誤）。

知識點規則：
- 每張步驟字卡（step）要帶 `source`（S1…）與 `quote`（來源裡逐字的一句），字卡文字裡的數字要出現在那一句；
- 台詞裡的數字只能是來源原句裡有的，或孩子的年齡、集數。
"""
from __future__ import annotations

import math
import re
from datetime import date

from mamababy_private.papa_home import bible as bb
from mamababy_private.papa_home import compile as comp
from mamababy_private.papa_home import library as lib

FIT_EXTEND = 1.0  # 自動補泡泡時鏡頭最多拉長幾秒


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def fact_errors(ep: dict, srcs: dict, allowed_numbers: set[str]) -> list[str]:
    """知識點檢查：步驟字卡要引用來源原句；數字不能憑空出現。"""
    errs = []
    all_quotes = [q for s in srcs.values() for q in s["quotes"]]
    quote_nums = set().union(*(numbers(q) for q in all_quotes)) if all_quotes else set()
    for s in ep.get("shots", []):
        where = s.get("id", "?")
        st = s.get("step")
        if st:
            src = srcs.get(st.get("source") or "")
            q = (st.get("quote") or "").strip()
            if not src:
                errs.append(f"{where}：步驟字卡的 source {st.get('source')} 不在來源裡")
            elif q not in src["quotes"]:
                errs.append(f"{where}：步驟字卡的 quote 要從 {st['source']} 逐字複製一句（現在是「{q[:30]}」）")
            else:
                extra = numbers(f"{st.get('title', '')}{st.get('sub', '')}") - numbers(q)
                if extra:
                    errs.append(f"{where}：字卡數字 {sorted(extra)} 不在引用的原句裡")
        for line in s.get("lines", []):
            extra = numbers("".join(line.get("text", []))) - quote_nums - allowed_numbers
            if extra:
                errs.append(f"{where}：台詞數字 {sorted(extra)} 沒有來源")
    return errs


def fit_lines(ep: dict) -> list[str]:
    """泡泡停留只差一點不夠讀時直接補（機械性錯誤，不值得整份退回）：鏡頭裡放得下就延長；放不下而且這鏡只有一句，就往前挪；
    再不行就把鏡頭拉長最多 FIT_EXTEND 秒。
    回傳改了什麼（記進紀錄）；型別不對的欄位不碰，留給驗證報錯。"""
    notes = []
    for s in ep.get("shots") or []:
        lines = s.get("lines") or []
        try:
            shot_dur = float(s.get("dur") or 0)
        except (TypeError, ValueError):
            continue
        for j, line in enumerate(lines):
            rows = line.get("text") or []
            if not isinstance(rows, list) or not all(isinstance(r, str) for r in rows):
                continue
            try:
                at, dur = float(line.get("at") or 0), float(line.get("dur") or 0)
            except (TypeError, ValueError):
                continue
            need = math.ceil(max(lib.MIN_HOLD, sum(comp.reading_chars(r) for r in rows) / lib.READ_CHARS_PER_SEC) * 10 - 1e-9) / 10
            if dur + 0.01 >= need:
                continue
            later = [float(o.get("at") or 0) for k, o in enumerate(lines) if k != j and isinstance(o.get("at"), (int, float))
                     and float(o.get("at") or 0) > at]
            limit = min(later) if later else None  # 補長不能蓋到同一鏡下一句的泡泡
            if limit is not None and at + need > limit + 0.01:
                continue
            if at + need <= shot_dur + 0.01:
                line["dur"] = need
                notes.append(f"{s.get('id')} 第 {j + 1} 句停留 {dur}→{need}s")
            elif len(lines) == 1 and need <= shot_dur:
                line["at"], line["dur"] = round(shot_dur - need, 2), need
                notes.append(f"{s.get('id')} 第 {j + 1} 句提前到 {line['at']}s、停留 {need}s")
            elif at + need - shot_dur <= FIT_EXTEND + 0.01 and at + need <= 8 and not (
                    at + need >= lib.STATIC_MIN and s.get("type") in comp.STATIC_TYPES and not comp.has_event(s)):  # 拉長不能變成「像投影片」
                new = round(at + need, 2)
                line["dur"] = need
                notes.append(f"{s.get('id')} 鏡頭 {shot_dur}→{new}s 讓第 {j + 1} 句讀完")
                s["dur"] = shot_dur = new
    return notes


def check(ep: dict, srcs: dict, today: date, bible: dict | None) -> list[str]:
    """格式驗證（compile.validate）＋知識點檢查＋精華版。沒有設定集時，台詞只允許來源與集數的數字。"""
    errs = comp.validate(ep)
    allowed_nums = {str(ep.get("episode", ""))} | bb.age_numbers(bible, today)
    errs += fact_errors(ep, srcs, allowed_nums)
    if not errs and ep.get("cut"):
        try:
            errs += [f"精華版：{e}" for e in comp.validate(comp.cut_episode(ep), full=False)]
        except ValueError as exc:
            errs.append(f"精華版：{exc}")
    return errs
