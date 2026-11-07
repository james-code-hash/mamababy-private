"""《帕帕貝貝家》CLI：`python main.py papa …`（經 moneyerp.cli entry point 掛進主程式）。"""

import json
import os
import sys
from typing import NoReturn


def _die(msg: str, code: int = 1) -> NoReturn:
    """印錯誤訊息並退出。"""
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


# papa（《帕帕貝貝家》每日 Reel）
def _papa_load(path: str) -> dict:
    from pathlib import Path

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"讀不到分鏡 {path}：{exc}")


def cmd_papa_menu(args):
    from mamababy_private.papa_home import library

    print(library.menu())


def cmd_papa_motion_docs(args):
    from mamababy_private.papa_home import skill_docs

    for path in skill_docs.write():
        print(f"✓ {path}")


def _papa_props(folder: str | None) -> set[str] | None:
    """素材包道具＋本集道具資料夾（*.webp）的名稱；沒給資料夾就只用素材包。"""
    from pathlib import Path

    from mamababy_private.papa_home import library

    if not folder:
        return None
    path = Path(folder).expanduser()
    if not path.is_dir():
        _die(f"--props 資料夾不存在：{path}")
    return library.props() | {f.stem for f in path.glob("*.webp")}


def _papa_errors(ep: dict, props: set[str] | None) -> list[str]:
    from mamababy_private.papa_home import compile as papa_compile

    errs = papa_compile.validate(ep, props=props)
    if ep.get("cut") and not errs:
        errs += [f"精華版：{e}" for e in papa_compile.validate(papa_compile.cut_episode(ep), props=props, full=False)]
    return errs


def cmd_papa_validate(args):
    from pathlib import Path

    from mamababy_private.papa_home import checks
    from mamababy_private.papa_home import compile as papa_compile

    ep = _papa_load(args.storyboard)
    if args.fix:  # 泡泡停留只差一點：直接補好寫回（機械性錯誤）
        for note in checks.fit_lines(ep):
            print(f"  ~ 自動補：{note}")
        Path(args.storyboard).write_text(json.dumps(ep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    errs = _papa_errors(ep, _papa_props(args.props))
    if ep.get("sources"):
        errs += _papa_fact_errors(ep, _papa_bible_for(args))
    for e in errs:
        print(f"  ✗ {e}")
    if errs:
        _die(f"{len(errs)} 個問題")
    total = sum(float(s["dur"]) for s in ep["shots"])
    print(f"✓ 第 {ep.get('episode')} 集《{ep.get('title')}》{len(ep['shots'])} 鏡、{total:.1f} 秒")
    for w in papa_compile.review(ep):
        print(f"  ! {w}")


def cmd_papa_build(args):
    from mamababy_private.papa_home import render as papa_render
    from pathlib import Path

    from mamababy_private.config import PAPA_AUDIO_DIR

    ep = _papa_load(args.storyboard)
    if args.no_lines:
        ep["hide_bubbles"] = True  # 審「關掉字幕看不看得懂」：泡泡不畫、嘴型照動
    errs = _papa_errors(ep, _papa_props(args.props))
    if errs and not args.force:
        for e in errs:
            print(f"  ✗ {e}")
        _die("分鏡驗證不過（--force 略過）")
    from mamababy_private.papa_home import compile as papa_compile

    for w in papa_compile.review(ep):
        print(f"  ! {w}")
    out = Path(args.out)
    audio = Path(args.audio_dir or PAPA_AUDIO_DIR).expanduser()
    props = Path(args.props).expanduser() if args.props else None
    for name, cut in (("full", False), ("cut", True)):
        if cut and not ep.get("cut"):
            continue
        if args.only and args.only != name:
            continue
        project, warn = papa_render.build(ep, out / name, audio, props, cut=cut)
        for w in warn:
            print(f"  ! {w}")
        print(f"專案：{project}")
        if args.render:
            mp4 = out / f"papa_home_ep{int(ep.get('episode') or 0):02d}_{name}.mp4"
            papa_render.render(project, mp4, workers=args.workers)
            print(f"成片：{mp4}")


def _papa_store():
    from mamababy_private.papa_home.store import PapaStore
    from moneyerp.core.firestore_client import get_client

    return PapaStore(get_client())


def _papa_today(value: str | None):
    from datetime import date

    return date.fromisoformat(value) if value else date.today()


def cmd_papa_bible_init(args):
    from mamababy_private.papa_home import bible

    kids = {}
    for item in args.kid or []:
        who, _, born = item.partition("=")
        if who not in bible.KID_LABEL or not re.fullmatch(r"\d{4}-\d{2}", born):
            _die(f"--kid 要寫成 sister=YYYY-MM 或 brother=YYYY-MM（現在是 {item}）")
        kids[who] = born
    if set(kids) != set(bible.KID_LABEL):
        _die("姊姊、弟弟的出生年月都要給：--kid sister=YYYY-MM --kid brother=YYYY-MM")
    st = _papa_store()
    if st.bible() and not args.force:
        _die("設定集已存在（--force 覆蓋）")
    b = bible.default_bible(kids, args.next)
    st.save_bible(b)
    print(f"✓ 設定集：{bible.ages_text(b, _papa_today(None))}，下一集第 {args.next} 集（出生年月只存 Firestore）")


def cmd_papa_bible(args):
    from mamababy_private.papa_home import bible

    b = _papa_store().bible()
    if not b:
        _die("還沒有設定集（papa bible-init）")
    print(bible.brief(b, _papa_today(args.today)))
    print(f"下一集：第 {b.get('next_episode_no')} 集")


def cmd_papa_topic_add(args):
    st = _papa_store()
    fields = {"title": args.title, "pet_point": args.pet or "", "kid_point": args.kid or "", "angle": args.angle or "",
              "reason": args.reason or "",
              "keywords": args.keywords or [], "source_urls": args.source or [], "order": args.order}
    if not st.topic(args.id):  # 新題目才設 queued；更新既有題目不動它的狀態（已用過的不會被打回佇列）
        fields["status"] = "queued"
    st.save_topic(args.id, fields)
    print(f"✓ 題目 {args.id}：{args.title}")


def cmd_papa_topics(args):
    rows = _papa_store().topics(None if args.all else "queued")
    for r in rows:
        print(f"{r.get('order', '-'):>3}  {r['id']:<20} [{r.get('status', 'queued')}] {r.get('title')}"
              f"  來源 {len(r.get('source_urls') or [])}")
    if not rows:
        print("（沒有題目）")


def cmd_papa_sources(args):
    from mamababy_private.papa_home import sources

    try:
        rows = sources.load(args.url)
    except (ValueError, OSError) as exc:
        _die(str(exc))
    for i, s in enumerate(rows, 1):
        if not args.keyword or any(k in s for k in args.keyword):
            print(f"{i:>4}. {s}")


def _papa_fact_errors(ep: dict, bible: dict | None) -> list[str]:
    """知識點：步驟字卡逐字引用來源、台詞數字要有來源（validate 與 ship 共用同一條規則）。"""
    from datetime import date

    from mamababy_private.papa_home import checks

    if not ep.get("sources"):
        return []
    allowed = {str(ep.get("episode", ""))} | checks.bb.age_numbers(bible, date.today())
    return checks.fact_errors(ep, ep["sources"], allowed)


def _papa_bible_for(args):
    """設定集：--bible-file 優先，否則讀 Firestore；讀不到回 None（台詞只允許來源與集數的數字）。"""
    from pathlib import Path

    if getattr(args, "bible_file", None):  # 使用者指定的檔案錯了要講清楚，不能悄悄降級
        try:
            return json.loads(Path(args.bible_file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _die(f"--bible-file 讀不到：{exc}")
    try:
        return _papa_store().bible()
    except Exception as exc:  # noqa: BLE001 — 離線也要能驗證格式；只是少了年齡數字的白名單
        print(f"  ! 讀不到設定集（{type(exc).__name__}），台詞只允許來源與集數的數字")
        return None


def cmd_papa_stills(args):
    from pathlib import Path

    from mamababy_private.papa_home import render as papa_render

    ep = _papa_load(args.storyboard)
    try:
        frames = papa_render.stills(ep, Path(args.out))
    except (RuntimeError, ValueError) as exc:
        _die(f"截靜幀失敗：{exc}")
    for sid, path in frames.items():
        print(f"{sid}  {path}")


def _papa_put_media(local, dest: str, host: str | None) -> str:
    """成片放到正式機的社群素材資料夾：host 有給（在 MacBook 製作）就 scp 到那台的 ~/.moneyerp/social-media/<dest>，
    沒給（就在正式機上跑）就照 papa approve 存本機。回傳放好的位置（給人看）。"""
    import subprocess

    from moneyerp.core import media_store

    if not host:
        return str(media_store.save(local, dest))
    remote = f".moneyerp/social-media/{dest}"  # 正式機 SOCIAL_MEDIA_DIR 沒設＝這個位置（每日排程用 root()/dest 找）
    for cmd in (["ssh", "-o", "BatchMode=yes", host, f"mkdir -p ~/{remote.rsplit('/', 1)[0]}"],
                ["scp", "-q", "-o", "BatchMode=yes", str(local), f"{host}:{remote}"]):
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            _die(f"傳到 {host} 失敗（{' '.join(cmd[:1])}）：{(r.stdout + r.stderr).strip()[-300:]}")
    return f"{host}:~/{remote}"


def cmd_papa_ship(args):
    """業主看過成片說 OK 之後：成片放到正式機 → Firestore 標 approved → 設定集記這集、下一集加一 → 題目標已用。"""
    from datetime import date, datetime, timezone
    from pathlib import Path

    from mamababy_private.papa_home import bible as papa_bible

    ep = _papa_load(args.storyboard)
    no = int(ep.get("episode") or 0)
    st = _papa_store()
    b = st.bible()
    errs = _papa_errors(ep, None) + _papa_fact_errors(ep, b)  # 跟 papa validate 同一套規則
    if errs:
        _die("分鏡驗證不過，不能交付：" + "；".join(errs[:5]))
    folder = Path(args.dir)
    files = {k: folder / f"papa_home_ep{no:02d}_{k}.mp4" for k in ("full", "cut")}
    missing = [str(f) for k, f in files.items() if not f.exists() and (k == "full" or ep.get("cut"))]
    if missing:
        _die("找不到成片：" + "、".join(missing) + "（先 papa build --render）")
    media = {}
    for k, f in files.items():  # 格式跟 papa approve 一樣：每日排程讀 media.dest（正式機 root()/dest）發正片
        if not f.exists():
            continue
        dest = f"papa_home/ep{no:03d}.mp4" if k == "full" else f"papa_home/ep{no:03d}_cut.mp4"
        where = _papa_put_media(f, dest, args.host)
        info = {"dest": dest, "bytes": f.stat().st_size, "uploaded_at": datetime.now(timezone.utc).isoformat()}
        if not args.host:
            info["path"] = where
        print(f"✓ {k} → {where}")
        if k == "full":
            media.update(info)
        else:
            media["cut"] = info
    st.save_episode(no, {"status": "approved", "title": ep.get("title", ""), "logline": ep.get("logline", ""),
                         "topic": ep.get("topic", ""), "storyboard": ep, "media": media,
                         "daily_draft": None})  # 重新交付＝可以再排一次
    if b:
        st.save_bible(papa_bible.published(b, ep, date.today()))
    if ep.get("topic") and st.topic(ep["topic"]):
        st.save_topic(ep["topic"], {"status": "used", "episode": no})
    print(f"✓ 第 {no} 集《{ep.get('title')}》已交付（approved），週二／週五發佈排程會拿到")


def cmd_papa_approve(args):
    """成片審過：存進正式機的社群素材資料夾、狀態改 approved，每日排程週二／週五依集數順序排進 21:00 草稿。"""
    from datetime import datetime, timezone
    from pathlib import Path

    from moneyerp.core import media_store

    mp4 = Path(args.video).expanduser()
    if not mp4.is_file():
        _die(f"找不到成片 {mp4}")
    st = _papa_store()
    ep = st.episode(args.episode)
    if not ep:
        _die(f"Firestore 沒有第 {args.episode} 集（新的一集用 papa ship 交付；approve 只用來換已交付那集的成片）")
    dest = f"papa_home/ep{int(args.episode):03d}.mp4"
    stored = media_store.save(mp4, dest)
    fields = {"status": "approved", "media": {"path": str(stored), "dest": dest, "bytes": mp4.stat().st_size,
                                              "uploaded_at": datetime.now(timezone.utc).isoformat()},
              "daily_draft": None}  # 重新核准＝可以再排一次（例如上次在 Slack 退回）
    if args.title:
        fields["title"] = args.title
    st.save_episode(args.episode, fields)
    print(f"✓ 第 {args.episode} 集《{fields.get('title') or ep.get('title')}》已核准，成片 {stored}；"
          "每日排程開著且「帕帕貝貝家已上線」時，最近的週二或週五 21:00 會建草稿（Slack 核准才發）")



def _build_papa_parser(sub):
    pa = sub.add_parser("papa", help="《帕帕貝貝家》每週 Reel（Claude Code 工作階段製作）：驗證分鏡、截靜幀、渲染、交付")
    pa_sub = pa.add_subparsers(dest="action", required=True)

    p = pa_sub.add_parser("menu", help="列出可用的鏡頭、站位、姿勢、表情、道具、音效")
    p.set_defaults(func=cmd_papa_menu)

    p = pa_sub.add_parser("motion-docs", help="動作庫 JSON 改了之後重產 writer skill 的參考文件")
    p.set_defaults(func=cmd_papa_motion_docs)

    p = pa_sub.add_parser("validate", help="驗證高階分鏡 JSON（含精華版）")
    p.add_argument("storyboard", help="分鏡 JSON 路徑")
    p.add_argument("--props", default=None, help="本集額外道具資料夾（*.webp），一起算可用道具")
    p.add_argument("--fix", action="store_true", help="泡泡停留只差一點就自動補好寫回檔案")
    p.add_argument("--bible-file", default=None, help="改讀本機設定集 JSON（不碰 Firestore）")
    p.set_defaults(func=cmd_papa_validate)

    p = pa_sub.add_parser("build", help="分鏡 → HyperFrames 專案（full/ 與 cut/），--render 順便出 MP4")
    p.add_argument("storyboard", help="分鏡 JSON 路徑")
    p.add_argument("-o", "--out", required=True, help="輸出資料夾")
    p.add_argument("--render", action="store_true", help="渲染 MP4 並把響度拉到 -15 LUFS")
    p.add_argument("--only", choices=["full", "cut"], default=None, help="只做正片或精華版")
    p.add_argument("--audio-dir", default=None, help="配樂／音效資料夾（預設設定 PAPA_AUDIO_DIR）")
    p.add_argument("--props", default=None, help="本集額外道具資料夾（*.webp）")
    p.add_argument("--workers", type=int, default=None, help="渲染平行分頁數")
    p.add_argument("--force", action="store_true", help="驗證不過也照建")
    p.add_argument("--no-lines", action="store_true", help="不畫對話泡泡（審「關掉字幕看不看得懂」用，嘴型照動）")
    p.set_defaults(func=cmd_papa_build)

    p = pa_sub.add_parser("bible-init", help="建立系列設定集（Firestore papa_home_series/bible；孩子出生年月只存這裡）")
    p.add_argument("--kid", action="append", help="孩子出生年月：sister=YYYY-MM、brother=YYYY-MM（兩個都要）")
    p.add_argument("--next", type=int, default=1, help="下一集集數（重製後從第 1 集開始）")
    p.add_argument("--force", action="store_true", help="覆蓋既有設定集")
    p.set_defaults(func=cmd_papa_bible_init)

    p = pa_sub.add_parser("bible", help="看設定集摘要（角色、孩子年齡、季節、最近幾集）")
    p.add_argument("--today", default=None, help="以哪一天計算孩子年齡（YYYY-MM-DD）")
    p.set_defaults(func=cmd_papa_bible)

    p = pa_sub.add_parser("topic-add", help="新增／更新題目庫的題目")
    p.add_argument("id", help="題目 id（英文，例 solid-food）")
    p.add_argument("--title", required=True)
    p.add_argument("--pet", default=None, help="寵物點")
    p.add_argument("--kid", default=None, help="孩子／育兒點（姊姊或弟弟那一側）")
    p.add_argument("--reason", default=None, help="為什麼挑這個題目（季節、孩子年齡、熱門話題…；AI 挑題時寫）")
    p.add_argument("--angle", default=None, help="切入角度或笑點方向")
    p.add_argument("--source", action="append", help="官方來源網址（可多個；要在白名單）")
    p.add_argument("--keywords", nargs="*", help="只取含這些字的來源句子")
    p.add_argument("--order", type=int, default=999, help="排序（小的先做）")
    p.set_defaults(func=cmd_papa_topic_add)

    p = pa_sub.add_parser("topics", help="列出題目庫")
    p.add_argument("--all", action="store_true", help="含已用過的")
    p.set_defaults(func=cmd_papa_topics)

    p = pa_sub.add_parser("sources", help="抓官方來源（網頁或 PDF）切成句子，挑 keywords 用")
    p.add_argument("url")
    p.add_argument("--keyword", nargs="*", help="只印含這些字的句子")
    p.set_defaults(func=cmd_papa_sources)

    p = pa_sub.add_parser("stills", help="每鏡中間一格 PNG（stills/<鏡頭 id>.png），給工作階段看圖審片")
    p.add_argument("storyboard", help="分鏡 JSON 路徑")
    p.add_argument("-o", "--out", required=True, help="輸出資料夾")
    p.set_defaults(func=cmd_papa_stills)

    p = pa_sub.add_parser("ship", help="業主看過說 OK 後交付：成片放到正式機、Firestore 標 approved、設定集記這集、題目標已用")
    p.add_argument("storyboard", help="分鏡 JSON（repo 的 papa_home/episodes/epNN.json）")
    p.add_argument("--dir", required=True, help="成片資料夾（papa build --render 的 -o，內有 papa_home_epNN_full.mp4／_cut.mp4）")
    p.add_argument("--host", default=os.environ.get("PAPA_MEDIA_HOST", ""),
                   help="在 MacBook 製作時：成片 scp 到這台正式機（ssh 名稱，例 claw-arm-1；或環境變數 PAPA_MEDIA_HOST）；在正式機上跑就不用給")
    p.set_defaults(func=cmd_papa_ship)

    p = pa_sub.add_parser("approve", help="成片審過：存進正式機社群素材資料夾、標 approved，每日排程週二／週五依集數順序排進 21:00 草稿")
    p.add_argument("episode", type=int, help="集數")
    p.add_argument("video", help="成片 mp4（給哪個版本就發哪個：正片或精華版）")
    p.add_argument("--title", default=None, help="改這集的標題（配文會用）")
    p.set_defaults(func=cmd_papa_approve)



def register(sub) -> None:
    """moneyerp.cli entry point。"""
    _build_papa_parser(sub)
