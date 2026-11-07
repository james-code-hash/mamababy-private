"""低階分鏡（座標已算好）→ HyperFrames 專案：每鏡一個 sub-composition＋配樂／音效軌。

輸入由 `compile.compile_episode` 產生，這裡不做判斷，只負責畫。手法沿用試播集（2026-11 ep01）：
分層紙偶場景（遠景 0.6 視差、中景 1.0、前景 1.3）、頭像反應格、手繪對話泡泡（線條 1/12 秒抖一次）、定格紙紋。

2026-11-04 試映回饋（像簡報、太長、沒親和力）後加的畫法，全部由程式保證、分鏡不用寫：
角色腳下接觸陰影、每 3 秒左右小幅歪頭（idle）、頭像眨眼（rig.json heads.*.eyes）、頭像鏡背景是景深模糊的場景不再是單色底、
夜景暖光＋暗角、飄毛左右搖、泡泡貼著說話者兩行分兩拍出現、步驟字卡改手寫圈號＋螢光筆寫出、全片只用粉圓一種字體。

分件 rig（2026-11-04 業主回饋「沒看字不知道要表達什麼」）：rig.json poses.*.parts 有身／頭／前腳（手）／後腳，角色就用零件組；
有表情的角色在場景裡用姿勢自己的表情頭（parts.head.expressions），可以換表情（take）、看向目標（轉頭）、說話（頭輕點）；特寫頭像另有眨眼（blink 貼片）、說話（mouth 貼片）。
同一個動作頭先動、身體後跟（0.06–0.1 秒）、兩眼兩手不同步（HyperFrames references/types/character.md）。沒有 parts 的姿勢退回整張圖。
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

from mamababy_private.papa_home import library as lib
from mamababy_private.papa_home import motion

FW, FH = lib.FW, lib.FH
INK = "#4A3A2E"
ORANGE = "#E8833A"
GSAP = '<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>'
PANEL = {"furry": "#FBE7C6", "unimpressed": "#E9E1D3", "smug": "#F8E3A8", "surprised": "#D8E9F2", "soft": "#F7DCD6",
         "curious": "#E3EEDC", "giggle": "#FBE0B8", "neutral": "#F3E6CF", "happy": "#FBE7C6", "innocent": "#EFE6D8",
         "scared": "#E2E6EE", "excited": "#FBE0B8", "cry": "#E2E6EE", "sleep": "#E9E1F0"}
SPEED_LINES = ("surprised", "giggle", "smug", "excited")
MUSIC_VOL = 0.5
SFX_VOL = {"scratch": 0.9, "bark": 0.8, "giggle": 0.8, "gag": 0.9, "whimper": 0.8, "vacuum": 0.55, "brush": 0.7,
           "steps": 0.7, "click": 0.9, "pop": 0.8, "whoosh": 0.7}

CSS = f"""
@font-face {{ font-family: 'Huninn'; src: url('assets/fonts/huninn.woff2'); }}
#root {{ position:absolute; inset:0; overflow:hidden; background:#FBF3E8; font-family:'Huninn'; }}
.stage, .lay {{ position:absolute; left:0; top:0; transform-origin:0 0; }}
.lay img.plate {{ display:block; }}
.bgblur {{ filter:blur(14px) saturate(0.9) brightness(1.04); }}
.bgdim {{ position:absolute; inset:0; background:#FBF3E8; opacity:.22; }}
.ch {{ position:absolute; }}
.ch-f, .ch-b {{ position:absolute; inset:0; }}
.ch-b {{ transform-origin:50% 93.75%; }}
.ch img {{ position:absolute; inset:0; width:100%; height:100%; }}
.part {{ position:absolute; inset:0; }}
.hg {{ position:absolute; inset:0; }}
.av {{ position:absolute; }}
.hw {{ position:absolute; inset:0; }}
.hw img, .pupil, .blinkp {{ position:absolute; inset:0; width:100%; height:100%; }}
.mouth {{ opacity:0; }}
.shadow {{ position:absolute; border-radius:50%; background:radial-gradient(ellipse at center, rgba(74,58,46,.30) 0%, rgba(74,58,46,.12) 45%, rgba(74,58,46,0) 70%); }}
.near {{ position:absolute; inset:0; }}
.near img {{ width:1080px; height:1920px; }}
.warm {{ position:absolute; inset:0; background:radial-gradient(ellipse 60% 45% at 30% 26%, rgba(255,196,120,.32), rgba(255,196,120,0) 70%); mix-blend-mode:screen; }}
.vig {{ position:absolute; inset:0; background:radial-gradient(ellipse 75% 70% at 50% 55%, rgba(60,40,25,0) 55%, rgba(60,40,25,.26) 100%); }}
.bubble {{ position:absolute; }}
.bin {{ position:absolute; inset:0; transform-origin:50% 100%; }}
.bin svg {{ position:absolute; left:0; overflow:visible; }}
.bv {{ fill:#FFFDF8; stroke:{INK}; stroke-width:6; stroke-linejoin:round; stroke-linecap:round; }}
.btxt {{ position:absolute; top:40px; font-size:64px; line-height:80px; color:{INK}; white-space:nowrap; }}
.bav {{ position:absolute; width:140px; height:140px; border-radius:50%; background:#F6E3C8; }}
.head {{ position:absolute; left:90px; top:1000px; width:900px; height:900px; }}
.head img {{ position:absolute; inset:0; width:100%; height:100%; filter:drop-shadow(0 22px 26px rgba(74,58,46,.28)); }}
.lid {{ position:absolute; transform:scaleY(0); transform-origin:50% 0; border-radius:50% 50% 45% 45% / 60% 60% 40% 40%; border-bottom:5px solid {INK}; box-sizing:border-box; }}
.paper {{ position:absolute; inset:0; background:url('assets/props/paper_grain.webp'); mix-blend-mode:multiply; }}
.onoma {{ position:absolute; font-size:150px; color:{ORANGE}; -webkit-text-stroke:12px #fff; paint-order:stroke fill; }}
.st {{ position:absolute; left:70px; top:190px; width:780px; height:170px; }}
.st .num {{ position:absolute; left:0; top:4px; width:92px; height:92px; }}
.st .num svg {{ position:absolute; left:-8px; top:-8px; overflow:visible; }}
.st .num span {{ position:absolute; inset:0; text-align:center; font-size:56px; line-height:92px; color:{INK}; }}
.st .t1 {{ position:absolute; left:112px; top:0; padding:0 16px; font-size:60px; line-height:92px; color:{INK}; white-space:nowrap;
          background:linear-gradient(transparent 48%, #F7D77A 48%, #F7D77A 90%, transparent 90%); clip-path:inset(0px 100% 0px 0px); }}
.st .t2 {{ position:absolute; left:128px; top:100px; font-size:42px; line-height:56px; color:{INK}; white-space:nowrap; opacity:0; }}
"""

JS_HELPERS = """
const root = gsap.timeline({ paused: true });
const tl = gsap.timeline();
const D = __DUR__;
function breathe(sel, d){ const n=Math.max(1,Math.round(d/__BREATHE_P__)); tl.fromTo(sel,{scaleY:1},{scaleY:__BREATHE_S__,duration:d/n/2,ease:"sine.inOut",yoyo:true,repeat:n*2-1},0); }
function wag(sel, d, p){ const n=Math.max(1,Math.round(d/p)); tl.fromTo(sel,{rotation:-__WAG__},{rotation:__WAG__,duration:d/n,ease:"sine.inOut",yoyo:true,repeat:n-1},0); }
function hop(sel, d, p){ const n=Math.max(1,Math.round(d/p)); tl.fromTo(sel,{y:0},{y:-__HOP_H__,duration:p/2,ease:"power2.out",yoyo:true,repeat:n*2-1},0); }
function pop(sel, t, d, rot){ tl.fromTo(sel,{scale:0.6,opacity:0,rotation:rot*2.5},{scale:1,opacity:1,rotation:rot,duration:0.28,ease:"elastic.out(1,0.55)"},t);
  tl.to(sel,{opacity:0,filter:"blur(6px)",duration:0.14,ease:"power2.in"},t+d-0.15);
  if(document.querySelector(sel+" .l1")) tl.fromTo(sel+" .l1",{opacity:0,y:8},{opacity:1,y:0,duration:0.12,ease:"power2.out"},t+__GAP__);
  for(let k=0;k*0.0833<d;k++){ const v=k%3; tl.set(sel+" .bv",{opacity:0},t+k*0.0833); tl.set(sel+" .bv"+v,{opacity:1},t+k*0.0833); } }
function blink(sel, d, seed){ for(let t=0.9+seed; t<d-0.3; t+=2.4+((seed*7)%1.4)){ tl.fromTo(sel,{scaleY:0},{scaleY:1,duration:0.07,ease:"power2.in",immediateRender:false},t); tl.to(sel,{scaleY:0,duration:0.09,ease:"power2.out"},t+0.16); } }
function idle(sel, d, seed){ for(let t=0.8+seed; t<d-0.5; t+=__IDLE_EVERY__+seed*0.6){ tl.to(sel,{rotation:__IDLE_A__,duration:0.38,ease:"sine.inOut",yoyo:true,repeat:1},t); if(t+1.6<d-0.5) tl.to(sel,{rotation:__IDLE_B__,duration:0.38,ease:"sine.inOut",yoyo:true,repeat:1},t+1.6); } }
function bob(hg, wins){ for(const w of wins){ let t=w[0]+0.05, k=0; while(t<w[1]-0.15){ tl.to(hg,{yPercent:"+=0.5",duration:0.08,ease:"sine.out"},t); tl.to(hg,{yPercent:"-=0.5",duration:0.1,ease:"sine.in"},t+0.08); t+=0.32+(k%3)*0.07; k++; } } }
function blinkp(sel, d, seed){ for(let t=0.9+seed; t<d-0.3; t+=2.4+((seed*7)%1.4)){ tl.set(sel,{opacity:1},t); tl.set(sel,{opacity:0},t+0.13); } }
function talk(sel, wins){ for(const w of wins){ let t=w[0]+0.05, k=0; while(t<w[1]-0.1){ tl.set(sel,{opacity:1},t); tl.set(sel,{opacity:0},t+0.09+(k%3)*0.02); t+=0.17+(k%2)*0.06; k++; } } }
function look(hg, pupils, sx, sy, t, flip, f=1){ const fx=flip?-sx:sx; tl.to(hg,{xPercent:fx*1.4*f,yPercent:sy*1.0*f,rotation:-fx*4,duration:0.28,ease:"power2.out"},t);
  pupils.forEach((p,i)=>{ tl.to(p.sel,{xPercent:fx*p.rx*(i?0.92:1),yPercent:sy*p.ry*(i?0.92:1),duration:0.2,ease:"power3.out"},t+0.02+i*0.04); }); }
function take(hg, body, h0, h1, t, f=1){ tl.to(hg,{yPercent:"+="+(0.6*f),scaleY:0.96,duration:0.1,ease:"power2.in"},t-0.1); tl.to(hg,{scaleY:0.86,scaleX:1.08,duration:0.06,ease:"power2.in"},t);
  tl.set(h0,{opacity:0},t+0.06); tl.set(h1,{opacity:1},t+0.06); tl.to(hg,{scaleY:1.06,scaleX:0.97,yPercent:"-="+(1*f),duration:0.12,ease:"power2.out"},t+0.06);
  tl.to(hg,{scaleX:1,scaleY:1,yPercent:"-=0",duration:0.3,ease:"elastic.out(1,0.5)"},t+0.18); if(body) tl.to(body,{scaleX:1.04,duration:0.09,yoyo:true,repeat:1,ease:"power2.out"},t+0.08); }
function play(cs){ for(const c of cs){ if(c[0]==="fromTo") tl.fromTo(c[1],c[2],c[3],c[4]); else tl[c[0]](c[1],c[2],c[3]); } }
function sway(sel, d, amp, p){ const n=Math.max(1,Math.round(d/p)); tl.fromTo(sel,{x:-amp},{x:amp,duration:d/n,ease:"sine.inOut",yoyo:true,repeat:n-1},0); }
"""


def _helpers() -> str:
    """共用 JS（呼吸、歪頭、甩尾、蹦跳的幅度與週期讀 assets/papa_home/motion/motions.json）。"""
    m = motion.motions_data()
    amb, hop = m["ambient"], m["actions"]["hop"]["params"]
    subs = {"__BREATHE_P__": amb["breathe"]["params"]["period"], "__BREATHE_S__": amb["breathe"]["params"]["scale"],
            "__WAG__": amb["wag"]["params"]["angle"], "__HOP_H__": hop["height"], "__IDLE_EVERY__": amb["idle"]["params"]["every"],
            "__IDLE_A__": amb["idle"]["params"]["angle"], "__IDLE_B__": amb["idle"]["params"]["angle_back"]}
    out = JS_HELPERS
    for k, v in subs.items():
        out = out.replace(k, str(v))
    return out


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def prop_src(name: str) -> str:
    """手部特寫（hands/）或道具（props/）的專案內路徑。"""
    if name in lib.hands():
        return f"assets/characters/hands/{name}.webp"
    return f"assets/props/{name}.webp"


def layer_xf(scene: str, cx: float, cy: float, z: float, par: float) -> dict:
    """遠景 par<1：水平中心偏移打折（縮放與中景相同，才不會露出底邊）。"""
    W, _ = lib.scene(scene)["size"]
    cxx = W / 2 + (cx - W / 2) * par
    return {"x": round(FW / 2 - cxx * z, 1), "y": round(FH / 2 - cy * z, 1), "scale": round(z, 4)}


def wobbly_rect(w: float, h: float, v: int) -> str:
    """手繪圓角矩形；v 不同＝抖動不同（線條 boil）。"""
    r, seg = 46, 14

    def j(a: int, b: int) -> float:
        return math.sin(a * 12.9898 + b * 78.233 + v * 37.719) * 43758.5453 % 1 - 0.5

    d = ""
    per = 2 * (w + h)
    for i in range(seg * 4):
        s = i / (seg * 4) * per
        if s < w:
            px, py = s, 0.0
        elif s < w + h:
            px, py = w, s - w
        elif s < 2 * w + h:
            px, py = w - (s - w - h), h
        else:
            px, py = 0.0, h - (s - 2 * w - h)
        cx, cy = min(max(px, r), w - r), min(max(py, r), h - r)
        dx, dy = px - cx, py - cy
        dist = math.hypot(dx, dy)
        if dist > r:
            px, py = cx + dx / dist * r, cy + dy / dist * r
        px += j(i, 1) * 5.0
        py += j(i, 2) * 5.0
        d += ("M" if i == 0 else "L") + f"{px:.1f},{py:.1f} "
    return d + "Z"


def bubble_html(sid: str, j: int, lines: list[str], at: tuple, target, avatar, start: float, dur: float) -> str:
    bid = f"{sid}-b{j}"
    w, h = lib.bubble_size(lines, bool(avatar))
    x, y = at
    paths = "".join(f'<path class="bv bv{v}" d="{wobbly_rect(w, h, v)}"/>' for v in range(3))
    tail = ""
    if target:
        tx, ty = target
        bx = min(max(tx, x + 120), x + w - 120) - x
        down = ty > y + h
        by = h if down else 0
        tip = (max(-200, min(200, (tx - x) - bx)) * 0.3 + bx, by + (70 if down else -70))
        e1, e2 = (4, 7) if down else (-4, -7)
        tail = (f'<path d="M{bx - 34},{by - e1} L{tip[0]:.0f},{tip[1]} L{bx + 34},{by - e1}" '
                f'fill="#FFFDF8" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>'
                f'<path d="M{bx - 30},{by - e2} L{bx + 30},{by - e2}" stroke="#FFFDF8" stroke-width="9"/>')
    av = (f'<img class="bav" src="assets/characters/papa/head_{avatar}.webp" style="left:20px;top:{h / 2 - 70:.0f}px">'
          if avatar else "")
    pad = 48 + (130 if avatar else 0)
    rows = "<br>".join(f'<span class="l{k}">{_e(t)}</span>' for k, t in enumerate(lines))
    return (f'<div id="{bid}" class="bubble clip" data-start="{start}" data-duration="{dur}" '
            f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            f'<div id="{bid}-in" class="bin"><svg width="{w}" height="{h + 80}" viewBox="0 -40 {w} {h + 80}" style="top:-40px">'
            f'{tail}{paths}</svg>{av}<div class="btxt" style="left:{pad}px;right:40px">'
            f'{rows}</div></div></div>')


def speed_lines(sid: str, ex: str) -> str:
    """漫畫集中線：驚訝／開心類表情才放。"""
    if ex not in SPEED_LINES:
        return ""
    cx, cy, out = 540, 1150, []
    for k in range(44):
        a = k / 44 * 2 * math.pi + (k % 3) * 0.02
        r0 = 560 + (k * 97) % 180
        x0, y0 = cx + math.cos(a) * r0, cy + math.sin(a) * r0
        x1, y1 = cx + math.cos(a) * 1500, cy + math.sin(a) * 1500
        w = 6 + (k * 53) % 14
        out.append(f'<path d="M{x0:.0f},{y0:.0f} L{x1 + math.sin(a) * w:.0f},{y1 - math.cos(a) * w:.0f} '
                   f'L{x1 - math.sin(a) * w:.0f},{y1 + math.cos(a) * w:.0f} Z"/>')
    return (f'<svg id="{sid}-sl" width="1080" height="1920" style="position:absolute;left:0;top:0" fill="#FFFDF8" opacity="0.75">'
            + "".join(out) + "</svg>")


def _pct(v: float) -> str:
    return f"{v / 10.24:.2f}%"


def avatar_html(prefix: str, ch: str, expr: str, expr2: str | None, opts: dict) -> tuple[str, dict, list[str]]:
    """頭像（可換表情、看向＝轉頭、眨眼、說話）：回傳 (html, refs, js)。refs：h0/h1/pupils/lids 的選擇器給 take／look／gesture 用
    （pupils 一律空：瞳孔圖層已拿掉，papa_pose_heads --step pupils）。
    opts：talk[[t0,t1]…]、eyes("closed")、seed、D。外層容器要是正方形（頭像畫布 1024 等比）。"""
    heads = lib.rig(ch)["heads"]
    js: list[str] = []
    refs: dict = {"h0": f"#{prefix}-h0", "h1": f"#{prefix}-h1", "pupils": [], "lids": None}
    out = ""
    closed = opts.get("eyes") == "closed"
    for n, ex in enumerate([expr] + ([expr2] if expr2 else [])):
        h = heads[ex]
        hid = f"{prefix}-h{n}"
        inner = f'<img src="assets/characters/{ch}/{h["file"]}">'
        if h.get("blink"):
            inner += f'<img id="{hid}-bk" class="blinkp" src="assets/characters/{ch}/{h["blink"]}" style="opacity:0">'
        lids = ""
        for k, eye in enumerate([] if h.get("blink") else (h.get("eyes") or [])):
            lids += (f'<div class="lid {hid}-lid {hid}-lid{k}" style="left:{_pct(eye["x"])};top:{_pct(eye["y"])};'
                     f'width:{_pct(eye["w"])};height:{_pct(eye["h"])};background:{eye["color"]}"></div>')
        if h.get("mouth"):
            inner += f'<img id="{hid}-m" class="mouth" src="assets/characters/{ch}/{h["mouth"]["file"]}">'
            if opts.get("talk"):  # 兩個表情都動：take 換臉後台詞還在講，嘴要接著動
                js.append(f'talk("#{hid}-m", {json.dumps(opts["talk"])});')
        out += f'<div id="{hid}" class="hw"{" style=opacity:0" if n else ""}>{inner}{lids}</div>'
        if h.get("blink"):
            if n == 0:
                refs["lids"] = f"#{hid}-bk"
            if closed:
                js.append(f'tl.set("#{hid}-bk",{{opacity:1}},0);')
            else:
                js.append(f'blinkp("#{hid}-bk", D, {float(opts.get("seed", 0.3)):.2f});')
        elif h.get("eyes"):
            if n == 0:
                refs["lids"] = f".{hid}-lid"
            if closed:
                js.append(f'tl.set(".{hid}-lid",{{scaleY:1}},0);')
            else:
                seed = float(opts.get("seed", 0.3))
                js.append(f'blink(".{hid}-lid0", D, {seed:.2f}); blink(".{hid}-lid1", D, {seed + 0.03:.2f});')
    return out, refs, js


def char_html(sid: str, i: int, c: dict) -> tuple[str, str]:
    """c：{who, pose, x, y, ppc, flip, move_to, move_dur, vis, arc, pop_in, hop, expr, take, look, gesture, eyes, talk}。"""
    ch, pose, x, y = c["who"], c["pose"], c["x"], c["y"]
    e = lib.rig(ch)["poses"][pose]
    k = e["world_height"] * c["ppc"] / (e["bbox"][3] - e["bbox"][1])
    size, left, top = 1024 * k, x - 512 * k, y - 960 * k
    cid = f"{sid}-c{i}"
    flip = "transform:scaleX(-1);" if c.get("flip") else ""
    tail = ""
    if "tail" in e:
        px, py = e["tail_pivot"]
        tail = (f'<img id="{cid}-t" class="tail" src="assets/characters/{ch}/{e["tail"]}" '
                f'style="transform-origin:{px / 10.24:.2f}% {py / 10.24:.2f}%">')
    sd = e.get("shadow") or {}  # 坐、蹲：屁股和腿也貼地，陰影要往上、加寬（rig.json poses.<姿勢>.shadow；沒寫＝腳底一條）
    bx0, bx1 = sd.get("x", [e["bbox"][0], e["bbox"][2]])
    sw = (bx1 - bx0) * k * sd.get("w", 0.8)
    sh = sw * sd.get("h", 0.2)
    shadow = (f'<div class="shadow" style="left:{(bx0 + bx1) / 2 * k - sw / 2:.0f}px;top:{sd.get("y", 960) * k - sh / 2:.0f}px;'
              f'width:{sw:.0f}px;height:{sh:.0f}px"></div>')
    parts = e.get("parts")
    js = [f'breathe("#{cid}-b", D);']
    if not parts:  # 舊素材：整張圖
        inner = f'{tail}<img class="body" src="assets/characters/{ch}/{e["file"]}">'
        js.append(f'idle("#{cid}-b", D, {(i * 0.7) % 1.9:.2f});')
    else:
        inner = tail
        for name in ("body", "hind", "front", "front2"):  # 後腳畫在身體上面（定裝圖裡腿在軀幹前面）
            pt = parts.get(name)
            if not pt:
                continue
            origin = f"transform-origin:{_pct(pt['pivot'][0])} {_pct(pt['pivot'][1])};" if pt.get("pivot") else ""
            inner += f'<img id="{cid}-{name}" class="part" src="assets/characters/{ch}/{pt["file"]}" style="{origin}">'
        hp = parts["head"]
        hx, hy = hp["pivot"]
        own = e.get("expression")
        pose_heads = hp.get("expressions") or {}

        def head_file(ex: str | None) -> str:
            """這個姿勢的某個表情頭（對齊過）；原本的表情或沒有就用原本的頭零件。"""
            if ex and ex != own and ex in pose_heads:
                return pose_heads[ex]["file"]
            return hp["file"]

        expr = c.get("expr")
        take_to = (c.get("take") or [None])[0]
        head_inner = f'<div id="{cid}-h0" class="hw"><img src="assets/characters/{ch}/{head_file(expr)}"></div>'
        refs: dict = {"h0": f"#{cid}-h0", "h1": None, "pupils": [], "lids": None}
        hjs: list[str] = []
        if take_to and head_file(take_to) != head_file(expr):
            head_inner += (f'<div id="{cid}-h1" class="hw" style="opacity:0">'
                           f'<img src="assets/characters/{ch}/{head_file(take_to)}"></div>')
            refs["h1"] = f"#{cid}-h1"
        if c.get("talk"):  # 場景裡沒有對齊的嘴型貼片：說話時頭輕輕點動
            hjs.append(f'bob("#{cid}-hg", {json.dumps(c["talk"])});')
        inner += f'<div id="{cid}-hg" class="hg" style="transform-origin:{_pct(hx)} {_pct(hy)}">{head_inner}</div>'
        js.append(f'idle("#{cid}-hg", D, {(i * 0.7) % 1.9:.2f});')
        js += hjs
        if c.get("take") and refs.get("h1"):
            hf = motion.amplitude(ch)[0]  # 小孩的頭平移縮小，不然脖子露縫
            js.append(f'take("#{cid}-hg", "#{cid}-b", "{refs["h0"]}", "{refs["h1"]}", {c["take"][1]}{"" if hf == 1 else f", {hf}"});')
        if c.get("look"):
            sx, sy, t = c["look"]
            hf = motion.amplitude(ch)[0]
            js.append(f'look("#{cid}-hg", {json.dumps(refs["pupils"])}, {sx}, {sy}, {t}, {"true" if c.get("flip") else "false"}'
                      f'{"" if hf == 1 else f", {hf}"});')
        if c.get("gesture"):
            name, t, d = c["gesture"]
            roles = {"head": f"#{cid}-hg", "body": f"#{cid}-b", "lids": refs.get("lids"),
                     "arm_a": f"#{cid}-front" if parts.get("front") else None,
                     "arm_b": f"#{cid}-front2" if parts.get("front2") else None,
                     "tail": f"#{cid}-t" if "tail" in e else None}
            js.append(motion.calls_js(name, t, -d if c.get("flip") else d, roles, ch))
    hidden = ";opacity:0" if c.get("vis") and c["vis"][0] > 0 else ""  # 中途才進場：一開始就藏（接點提早疊上來時 tl.set 還沒生效）
    out = (f'<div id="{cid}" class="ch" style="left:{left:.1f}px;top:{top:.1f}px;width:{size:.1f}px;height:{size:.1f}px{hidden}">{shadow}'
           f'<div class="ch-f" style="{flip}"><div id="{cid}-b" class="ch-b">{inner}</div></div></div>')
    if "tail" in e:
        js.append(f'wag("#{cid}-t", D, {motion.tail_wag_period(ch)});')
    if c.get("move_to") is not None:
        js.append(f'tl.fromTo("#{cid}", {{x:0}}, {{x:{c["move_to"] - x:.1f}, duration:{c.get("move_dur") or "D"}, ease:"none"}}, 0);')
    if c.get("vis"):
        v0, v1 = c["vis"]
        js.append(f'tl.set("#{cid}",{{opacity:{0 if v0 > 0 else 1}}},0); tl.set("#{cid}",{{opacity:1}},{v0}); tl.set("#{cid}",{{opacity:0}},{v1});')
    if c.get("arc"):
        ax, ay, a0, ad = c["arc"]
        js.append(f'tl.fromTo("#{cid}",{{x:0}},{{x:{ax},duration:{ad},ease:"none"}},{a0});'
                  f'tl.fromTo("#{cid}-b",{{y:0}},{{y:-{motion.param("actions", "dive", "rise")},duration:{ad * 0.45:.3f},ease:"power2.out"}},{a0});'
                  f'tl.to("#{cid}-b",{{y:{ay},duration:{ad * 0.55:.3f},ease:"power2.in"}},{a0 + ad * 0.45:.3f});')
    if c.get("pop_in") is not None:
        pp = motion.motions_data()["actions"]["pop_in"]["params"]
        js.append(f'tl.fromTo("#{cid}",{{y:{pp["from_y"]},scaleY:{pp["squash"]},opacity:0}},{{y:0,scaleY:1,opacity:1,duration:{pp["duration"]},'
                  f'ease:"back.out(2.2)"}},{c["pop_in"]});')
    if c.get("hop"):
        js.append(f'hop("#{cid}-b", D, {motion.param("actions", "hop", "period")});')
    return out, "\n".join(js)


def scene_layers(s: dict) -> tuple[str, str]:
    sid, sc, d = s["id"], s["scene"], s["d"]
    W, H = lib.scene(sc)["size"]
    c0, c1 = s["cam"], s.get("cam_to", s["cam"])
    chars_html, js = [], []
    for i, c in enumerate(s.get("cast", [])):
        h, j = char_html(sid, i, c)
        chars_html.append(h)
        js.append(j)
    props, extra = "", []
    if s.get("fur_pile"):
        px, py, pw = s["fur_pile"]
        props += (f'<img id="{sid}-pile" src="assets/props/fur_pile.webp" '
                  f'style="position:absolute;left:{px - pw / 2:.0f}px;top:{py - pw * 0.62:.0f}px;width:{pw}px">')
    if s.get("poof"):
        px, py, pt = s["poof"]
        for k in range(6):
            props += (f'<img id="{sid}-pf{k}" src="assets/props/tuft_{k}.webp" '
                      f'style="position:absolute;left:{px - 60:.0f}px;top:{py - 60:.0f}px;width:120px;opacity:0">')
            a = k / 6 * 2 * math.pi + 0.4
            extra.append(f'tl.fromTo("#{sid}-pf{k}",{{x:0,y:0,opacity:1,rotation:0}},{{x:{math.cos(a) * 260:.0f},'
                         f'y:{-abs(math.sin(a)) * 300 - 60:.0f},opacity:0,rotation:{120 - k * 40},duration:0.9,ease:"power2.out"}},{pt});')
        if s.get("fur_pile"):
            extra.append(f'tl.fromTo("#{sid}-pile",{{scaleY:1,scaleX:1}},{{scaleY:0.7,scaleX:1.2,duration:0.12,yoyo:true,repeat:1,ease:"power2.out"}},{pt});')
    out = (f'<div id="{sid}-far" class="lay"><img class="plate" src="assets/scenes/{sc}/far.webp" width="{W}" height="{H}"></div>'
           f'<div id="{sid}-mid" class="lay"><img class="plate" src="assets/scenes/{sc}/mid.webp" width="{W}" height="{H}">'
           f'{props}{"".join(chars_html)}</div>')
    cam_dur = s.get("cam_dur") or d
    for lay, par in (("far", 0.6), ("mid", 1.0)):
        a, b = layer_xf(sc, c0[0], c0[1], c0[2], par), layer_xf(sc, c1[0], c1[1], c1[2], par)
        js.insert(0, f'tl.fromTo("#{sid}-{lay}", {json.dumps(a)}, {{...{json.dumps(b)}, duration:{cam_dur}, ease:"power2.inOut"}}, 0);')
    if s.get("near"):
        dx = -(c1[0] - c0[0]) * c0[2] * 1.3
        out += f'<div id="{sid}-near" class="near"><img src="assets/scenes/{sc}/near.webp"></div>'
        js.append(f'tl.fromTo("#{sid}-near", {{x:0}}, {{x:{dx:.1f}, duration:{d}, ease:"power2.inOut"}}, 0);')
    return out, "\n".join(js + extra)


def bg_html(sid: str, bg: dict, d: float) -> tuple[str, str]:
    """頭像鏡／講解鏡的背景：場景遠景＋中景拉近、模糊、慢推，上面壓一層淡奶油色讓字好讀。"""
    sc, (cx, cy, z) = bg["scene"], bg["cam"]
    W, H = lib.scene(sc)["size"]
    out = (f'<div id="{sid}-bg" class="stage bgblur" style="width:{FW}px;height:{FH}px">'
           f'<div id="{sid}-bgf" class="lay"><img class="plate" src="assets/scenes/{sc}/far.webp" width="{W}" height="{H}"></div>'
           f'<div id="{sid}-bgm" class="lay"><img class="plate" src="assets/scenes/{sc}/mid.webp" width="{W}" height="{H}"></div></div>'
           f'<div class="bgdim"></div>')
    js = []
    for lay, par in (("bgf", 0.6), ("bgm", 1.0)):
        a, b = layer_xf(sc, cx, cy, z, par), layer_xf(sc, cx + 18, cy - 16, z * 1.12, par)
        js.append(f'tl.fromTo("#{sid}-{lay}", {json.dumps(a)}, {{...{json.dumps(b)}, duration:{d}, ease:"sine.inOut"}}, 0);')
    return out, "\n".join(js)


def _head(s: dict, body: list, js: list) -> None:
    sid, d = s["id"], s["d"]
    ch, ex = s["head"]
    bg, bjs = bg_html(sid, s.get("bg") or {"scene": "living", "cam": [1190, 1300, 1.5]}, d)
    body.append(bg + '<div class="vig"></div>')
    js.append(bjs)
    if s.get("lines"):
        body.append(speed_lines(sid, ex))
    ex2, t2 = s.get("head_to") or (None, None)
    av, refs, hjs = avatar_html(f"{sid}-hd", ch, ex, ex2, {"talk": s.get("head_talk"), "seed": (len(sid) * 0.37) % 1.1})
    body.append(f'<div id="{sid}-hd" class="head"><div id="{sid}-hg" class="hg" style="transform-origin:50% 100%">{av}</div></div>')
    js += hjs
    if ex2:
        js.append(f'take("#{sid}-hg", null, "{refs["h0"]}", "{refs["h1"]}", {t2});')
    if s.get("head_look"):
        sx, sy, t = s["head_look"]
        js.append(f'look("#{sid}-hg", {json.dumps(refs["pupils"])}, {sx}, {sy}, {t}, false);')
    if s.get("head_gesture"):
        name, t = s["head_gesture"]
        js.append(motion.calls_js(name, t, 1, {"head": f"#{sid}-hg", "lids": refs.get("lids")}))
    if s.get("seam") not in ("push", "pull"):
        js.append(f'tl.fromTo("#{sid}-hd", {{scale:0.62, y:260}}, {{scale:1, y:0, duration:0.25, ease:"expo.out"}}, 0);')
    js.append(f'idle("#{sid}-hd", D, 0.6);'
              f'tl.fromTo("#{sid}-hd", {{x:0}}, {{x:-14, duration:{max(0.8, d):.2f}, ease:"sine.inOut"}}, 0.25);')


def puffs(prefix: str, times: list[float], x: float, y: float) -> tuple[str, str]:
    """梳子每刷一下，從梳子頭（畫面座標 x,y）冒出兩小團毛往上飄散。回傳 (html, js)。"""
    html_out, js_out = [], []
    for k, t in enumerate(times):
        for j in range(2):
            pid = f"{prefix}-pf{k}{j}"
            html_out.append(f'<img id="{pid}" src="assets/props/tuft_{(k + j) % 6}.webp" '
                            f'style="position:absolute;left:{x - 80 + j * 50:.0f}px;top:{y - 80:.0f}px;width:160px;opacity:0;'
                            f'filter:drop-shadow(0 0 6px #fff) drop-shadow(0 2px 3px rgba(74,58,46,.35))">')
            js_out.append(f'tl.fromTo("#{pid}",{{x:0,y:0,scale:0.4,opacity:1,rotation:0}},{{x:{140 + j * 150},y:{-280 - j * 80},scale:1,'
                          f'rotation:{70 - j * 150},duration:0.85,ease:"power2.out",immediateRender:false}},{t:.2f});'
                          f'tl.to("#{pid}",{{opacity:0,duration:0.3}},{t + 0.55:.2f});')
    return "".join(html_out), "\n".join(js_out)


def _demo(s: dict, body: list, js: list) -> None:
    """產品三段示範：乾淨的道具使用中 → 拿起來看到成果 → 按下去成果整片掉落（例：自潔排梳）。"""
    sid, m = s["id"], s["demo"]
    tb, tc = m["lift_at"], m["press_at"]
    ph, pj = puffs(f"{sid}-ca", [0.65 + k * 0.6 for k in range(int(max(0, tb - 0.9) / 0.6) + 1)], 600, 1120)
    body.append(f'<div id="{sid}-dim" style="position:absolute;inset:0;background:#FBF3E8;opacity:.35"></div>'
                f'<img id="{sid}-ca" src="{prop_src(m["use"])}" style="position:absolute;left:0;top:660px;width:1080px;height:1080px">'
                f'<div id="{sid}-cbw" style="position:absolute;left:0;top:560px;width:1080px;height:1080px;opacity:0">'
                f'<img id="{sid}-cb" src="{prop_src(m["full"])}" style="position:absolute;inset:0;width:100%;height:100%">'
                f'<img id="{sid}-cc" src="{prop_src(m["released"])}" style="position:absolute;inset:0;width:100%;height:100%;opacity:0"></div>'
                f'<img id="{sid}-cf" src="{prop_src(m["drop"])}" style="position:absolute;left:0;top:560px;width:1080px;height:1080px;opacity:0">'
                f'<div id="{sid}-pa" class="onoma" style="left:640px;top:520px;font-size:110px">{_e(m.get("sound_word", "喀！"))}</div>{ph}')
    js += [
        f'tl.fromTo("#{sid}-ca", {{x:320, y:360}}, {{x:0, y:0, duration:0.5, ease:"expo.out"}}, 0);',
        f'tl.to("#{sid}-ca", {{scale:1.07, x:-20, y:-30, duration:{tb:.2f}, ease:"sine.inOut"}}, 0.5);',
        pj,
        f'tl.set("#{sid}-ca",{{opacity:0}},{tb}); tl.set("#{sid}-cbw",{{opacity:1}},{tb}); tl.set("#{sid}-cf",{{opacity:1}},{tb});',
        f'tl.fromTo(["#{sid}-cbw","#{sid}-cf"], {{y:140, rotation:-5}}, {{y:0, rotation:0, duration:0.45, ease:"back.out(1.8)", immediateRender:false}}, {tb});',
        f'tl.set("#{sid}-cb",{{opacity:0}},{tc}); tl.set("#{sid}-cc",{{opacity:1}},{tc});',
        f'tl.fromTo("#{sid}-cbw", {{scale:1}}, {{scale:0.97, duration:0.07, yoyo:true, repeat:1, ease:"power2.out", immediateRender:false}}, {tc});',
        f'tl.fromTo("#{sid}-cf", {{y:0, x:0, rotation:0}}, {{y:1150, x:-90, rotation:-28, duration:0.9, ease:"power2.in", immediateRender:false}}, {tc + 0.05});',
        f'tl.fromTo("#{sid}-pa", {{scale:0.3, opacity:0, rotation:-16}}, {{scale:1, opacity:1, rotation:-8, duration:0.2, ease:"back.out(2.4)"}}, {tc});'
        f' tl.to("#{sid}-pa", {{opacity:0, duration:0.15}}, {tc + 0.8});',
    ]


def _hand(s: dict, body: list, js: list) -> None:
    sid, d = s["id"], s["d"]
    name, at = s["hand"]
    dim = "" if s.get("head") else f'<div id="{sid}-dim" style="position:absolute;inset:0;background:#FBF3E8;opacity:.35"></div>'
    body.append(f'{dim}<img id="{sid}-hand" src="{prop_src(name)}" '
                f'style="position:absolute;left:0;top:{s.get("hand_top", 660)}px;width:1080px;height:1080px">')
    js.append(f'tl.fromTo("#{sid}-hand", {{x:320, y:360}}, {{x:0, y:0, duration:0.55, ease:"expo.out"}}, {at});')
    motion = s.get("hand_motion")
    if motion == "stroke":  # 梳毛：手和毛畫在同一張圖，圖不動，改慢推＋梳子頭刷出毛團
        js.append(f'tl.to("#{sid}-hand", {{scale:1.07, x:-20, y:-30, duration:{max(0.8, d - at - 0.6):.2f}, ease:"sine.inOut"}}, {at + 0.6});')
        ph, pj = puffs(f"{sid}-hand", [at + 0.7 + k * 0.6 for k in range(int(max(0, d - at - 1.1) / 0.6) + 1)], 520, s.get("hand_top", 660) + 520)
        body.append(ph)
        js.append(pj)
    elif motion == "sweep":  # 左右掃（吸地）
        js.append(f'tl.to("#{sid}-hand", {{x:-240, y:-30, duration:1.1, ease:"sine.inOut", yoyo:true, repeat:{max(1, int((d - 0.7) / 1.1) - 1)}}}, {at + 0.7});')


def build_shot(s: dict, ep: dict) -> str:
    sid, d = s["id"], s["d"]
    body: list[str] = []
    js: list[str] = []
    if s.get("scene") and not s.get("head"):
        h, j = scene_layers(s)
        body.append(f'<div id="{sid}-stage" class="stage" style="width:{FW}px;height:{FH}px">{h}</div><div class="warm"></div><div class="vig"></div>')
        js.append(j)
    if s.get("pov"):
        body.append(f'<svg width="1080" height="1920" style="position:absolute;left:0;top:0">'
                    f'<defs><radialGradient id="{sid}-vg" cx="50%" cy="62%" r="70%"><stop offset="55%" stop-color="#2b1d14" stop-opacity="0"/>'
                    f'<stop offset="100%" stop-color="#2b1d14" stop-opacity="0.75"/></radialGradient></defs>'
                    f'<rect width="1080" height="1920" fill="url(#{sid}-vg)"/>'
                    f'<path d="M0,0 H1080 V300 C900,330 760,280 600,320 C430,360 260,300 0,340 Z" fill="#5b4a3d"/>'
                    f'<path d="M0,330 C160,300 300,350 470,330 C650,300 820,345 1080,300" stroke="#3b2e25" stroke-width="10" fill="none"/></svg>')
    if s.get("tufts"):
        for k in range(6):
            x0, y0, w = 120 + k * 160 + (k % 2) * 40, 300 + (k * 263) % 900, 120 + (k * 37) % 70
            body.append(f'<img id="{sid}-tf{k}" src="assets/props/tuft_{k}.webp" style="position:absolute;left:{x0}px;top:{y0}px;width:{w}px">')
            js.append(f'tl.fromTo("#{sid}-tf{k}", {{y:0, rotation:{-20 + k * 9}}}, {{y:{140 + k * 25}, '
                      f'rotation:{30 - k * 7}, duration:{d}, ease:"sine.inOut"}}, 0); sway("#{sid}-tf{k}", D, {38 + k * 6}, {1.1 + k * 0.17:.2f});')
    if s.get("floor_tufts"):
        for k in range(4):
            body.append(f'<img id="{sid}-ft{k}" src="assets/props/tuft_{k}.webp" style="position:absolute;left:{140 + k * 150}px;top:{1250 + (k % 2) * 80}px;width:150px">')
            js.append(f'tl.fromTo("#{sid}-ft{k}", {{x:0,y:0,scale:1,opacity:1}}, {{x:{420 - k * 150},y:-60,scale:0.2,opacity:0,duration:0.5,'
                      f'ease:"power3.in",immediateRender:false}}, {0.9 + k * max(0.35, (d - 1.5) / 4):.2f});')
    if s.get("head"):
        _head(s, body, js)
    if s.get("demo"):
        _demo(s, body, js)
    if s.get("hairball") is not None:
        body.append(f'<img id="{sid}-hb" src="assets/props/hairball.webp" style="position:absolute;left:470px;top:1500px;width:150px">')
        js.append(f'tl.fromTo("#{sid}-hb", {{scale:0, x:0, y:0, rotation:0}}, {{scale:1, x:430, y:-660, rotation:200, duration:0.6, ease:"back.out(1.6)"}}, {s["hairball"]});')
    if s.get("hand"):
        _hand(s, body, js)
    if s.get("sign") is not None:
        e = lib.rig("papa")["poses"]["sign"]
        bg, bjs = bg_html(sid, s.get("bg") or {"scene": "living", "cam": [1190, 1300, 1.5]}, d)
        body.append(bg + '<div class="vig"></div>')
        js.append(bjs)
        body.append(f'<div id="{sid}-sg" style="position:absolute;left:28px;top:560px;width:1024px;height:1024px">'
                    f'<img src="assets/characters/papa/{e["file"]}" style="width:100%;height:100%;filter:drop-shadow(0 22px 26px rgba(74,58,46,.28))">'
                    f'<div style="position:absolute;left:150px;top:520px;width:600px;text-align:center;font-size:74px;line-height:96px;color:{INK}">'
                    f'{"<br>".join(_e(t) for t in s["sign"])}</div></div>')
        js.append(f'tl.fromTo("#{sid}-sg", {{y:500}}, {{y:0, duration:0.5, ease:"back.out(1.3)"}}, 0); breathe("#{sid}-sg", D);')
    if s.get("step"):
        st = s["step"]
        circle = "".join(f'<path class="bv bv{v}" d="{wobbly_rect(92, 92, v + 11)}" style="fill:#F2B544;stroke-width:5"/>' for v in range(3))
        body.append(f'<div id="{sid}-st" class="st"><div id="{sid}-sn" class="num"><svg width="108" height="108" viewBox="-8 -8 108 108">{circle}</svg>'
                    f'<span>{st["n"]}</span></div><div id="{sid}-s1" class="t1">{_e(st["title"])}</div>'
                    f'<div id="{sid}-s2" class="t2">{_e(st["sub"])}</div></div>')
        js.append(f'tl.fromTo("#{sid}-sn", {{scale:0, rotation:-30}}, {{scale:1, rotation:0, duration:0.35, ease:"back.out(2)"}}, 0.2);'
                  f'tl.fromTo("#{sid}-s1", {{clipPath:"inset(0px 100% 0px 0px)"}}, {{clipPath:"inset(0px 0% 0px 0px)", duration:0.45, ease:"power2.out"}}, 0.4);'
                  f'tl.fromTo("#{sid}-s2", {{opacity:0, y:10}}, {{opacity:1, y:0, duration:0.25, ease:"power2.out"}}, 0.9);'
                  f'for(let k=0;k*0.0833<D;k++){{ const v=k%3; tl.set("#{sid}-sn .bv",{{opacity:0}},k*0.0833); tl.set("#{sid}-sn .bv"+v,{{opacity:1}},k*0.0833); }}')
    if s.get("split"):
        bg = s.get("split_scene") or "living"
        W, H = lib.scene(bg)["size"]
        for k, half in enumerate(s["split"]):
            good = half["good"]
            mark, col = ("○", "#4E9A6A") if good else ("✕", "#D9534F")
            body.append(f'<div id="{sid}-p{k}" style="position:absolute;left:0;top:{k * 960}px;width:1080px;height:960px;overflow:hidden" data-layout-allow-overflow>'
                        f'<img src="assets/scenes/{bg}/far.webp" style="position:absolute;left:-700px;top:-700px;width:{W}px;height:{H}px">'
                        f'<div style="position:absolute;inset:0;background:#FBF3E8;opacity:.4"></div>'
                        f'<img id="{sid}-ph{k}" src="{prop_src(half["prop"])}" style="position:absolute;left:160px;top:60px;width:900px;height:900px">'
                        f'<div id="{sid}-pm{k}" style="position:absolute;left:60px;top:{60 if k == 0 else 140}px;width:150px;height:150px;border-radius:50%;'
                        f'background:{col};color:#fff;font-size:100px;line-height:150px;text-align:center">{mark}</div>'
                        f'<div style="position:absolute;left:230px;top:{86 if k == 0 else 166}px;font-size:64px;line-height:100px;color:{INK};background:#FFFDF8;'
                        f'border:5px solid {INK};border-radius:30px;padding:0 30px">{_e(half["label"])}</div></div>')
            js.append(f'tl.fromTo("#{sid}-pm{k}", {{scale:0}}, {{scale:1, duration:0.4, ease:"back.out(2)"}}, {0.5 + k * 1.5});')
            js.append(f'tl.fromTo("#{sid}-ph{k}", {{x:200}}, {{x:0, duration:0.5, ease:"expo.out"}}, {k * 1.5});')
            js.append(f'tl.to("#{sid}-ph{k}",{{scale:1.08,duration:{max(0.5, d - 1.5 - k):.2f},ease:"none"}},{1.0 + k});')
        body.append(f'<div style="position:absolute;left:0;top:952px;width:1080px;height:16px;background:{INK}"></div>')
    if s.get("card") == "title":
        body.append(f'<div style="position:absolute;inset:0;background:#FBF3E8"></div>'
                    f'<img id="{sid}-hp" src="assets/characters/papa/head_smug.webp" style="position:absolute;left:120px;top:360px;width:460px">'
                    f'<img id="{sid}-hb" src="assets/characters/beibei/head_happy.webp" style="position:absolute;left:520px;top:390px;width:440px">'
                    f'<div id="{sid}-t1" style="position:absolute;left:0;width:1080px;top:900px;text-align:center;font-size:{min(230, 980 // len(lib.SERIES_TITLE))}px;color:{INK}">{_e(lib.SERIES_TITLE)}</div>'
                    f'<div id="{sid}-t2" style="position:absolute;left:0;width:1080px;top:1180px;text-align:center;font-size:66px;color:#C87132">'
                    f'第 {ep["episode"]} 集｜{_e(ep["title"])}</div>')
        js.append(f'tl.fromTo("#{sid}-t1",{{scale:1.25,opacity:0}},{{scale:1,opacity:1,duration:0.35,ease:"expo.out"}},0.05);'
                  f'tl.fromTo("#{sid}-hp",{{y:260,rotation:-14}},{{y:0,rotation:0,duration:0.5,ease:"back.out(1.8)"}},0.2);'
                  f'tl.fromTo("#{sid}-hb",{{y:260,rotation:14}},{{y:0,rotation:0,duration:0.5,ease:"back.out(1.8)"}},0.32);'
                  f'tl.fromTo("#{sid}-t2",{{opacity:0,filter:"blur(8px)"}},{{opacity:1,filter:"blur(0px)",duration:0.2}},0.1);')
    elif s.get("card") == "end":
        body.append(f'<div style="position:absolute;inset:0;background:#FBF3E8"></div>'
                    f'<img id="{sid}-hp" src="assets/characters/papa/head_soft.webp" style="position:absolute;left:310px;top:300px;width:460px">'
                    f'<div id="{sid}-t1" style="position:absolute;left:0;width:1080px;top:760px;text-align:center;font-size:{min(200, 900 // len(lib.SERIES_TITLE))}px;color:{INK}">{_e(lib.SERIES_TITLE)}</div>'
                    f'<div id="{sid}-t2" style="position:absolute;left:90px;width:900px;top:1030px;text-align:center;font-size:56px;line-height:80px;'
                    f'color:{INK};background:#FFFDF8;border:5px solid {INK};border-radius:36px;padding:26px 0">下集<br>{_e(ep.get("teaser", ""))}</div>')
        js.append(f'tl.fromTo("#{sid}-hp",{{y:200,scale:.8}},{{y:0,scale:1,duration:0.5,ease:"back.out(1.6)"}},0.0);'
                  f'tl.fromTo("#{sid}-t1",{{opacity:0,scale:1.2}},{{opacity:1,scale:1,duration:0.35,ease:"expo.out"}},0.15);'
                  f'tl.fromTo("#{sid}-t2",{{opacity:0,y:30}},{{opacity:1,y:0,duration:0.3,ease:"expo.out"}},0.6);')
    for j, b in enumerate(s.get("bubble", [])):
        body.append(bubble_html(sid, j, b["text"], b["pos"], b.get("target"), b.get("avatar"), b["at"], b["dur"]))
        rot = ((j * 7 + len(sid)) % 5 - 2) * 0.7  # −1.4°～1.4°，每個泡泡略歪
        js.append(f'pop("#{sid}-b{j}-in", {b["at"]}, {b["dur"]}, {rot});')
    for k, o in enumerate(s.get("onoma", [])):
        body.append(f'<div id="{sid}-o{k}" class="onoma" style="left:{o["x"]}px;top:{o["y"]}px">{_e(o["text"])}</div>')
        js.append(f'tl.fromTo("#{sid}-o{k}", {{scale:0.3, rotation:{o["rot"] * 2}, opacity:0}}, '
                  f'{{scale:1, rotation:{o["rot"]}, opacity:1, duration:0.22, ease:"back.out(2.4)"}}, {o["at"]});')
        js.append(f'tl.to("#{sid}-o{k}", {{opacity:0, duration:0.15}}, {o["at"] + 0.9});')
    if s.get("freeze_at") is not None:
        ft = s["freeze_at"]
        body.append(f'<div id="{sid}-fz" style="position:absolute;inset:0;opacity:0"><div style="position:absolute;inset:0;background:#F3E6CF;opacity:.16"></div>'
                    f'<div class="paper" style="opacity:.28"></div></div><div id="{sid}-fl" style="position:absolute;inset:0;background:#fff;opacity:0"></div>')
        js.append(f'tl.set("#{sid}-fz",{{opacity:1}},{ft}); tl.fromTo("#{sid}-fl",{{opacity:0.85}},{{opacity:0,duration:0.1,immediateRender:false}},{ft});')
        tgt = f"#{sid}-hd" if s.get("head") else f"#{sid}-stage"
        if s.get("head") or s.get("scene"):
            js.append(f'tl.fromTo("{tgt}",{{rotation:0}},{{rotation:1.6,duration:0.08,ease:"power3.out",immediateRender:false}},{ft});')
    body.append('<div class="paper" style="opacity:.07"></div>')
    lead = float(s.get("lead") or 0)
    script = (_helpers().replace("__DUR__", str(d)).replace("__GAP__", str(lib.LINE_GAP)) + "\n".join(js)
              + f'\n{seam_out_js(s)}\nroot.add(tl, {lead}); {seam_in_js(s)}\nwindow.__timelines = window.__timelines || {{}};\nwindow.__timelines["{sid}"] = root;')
    dip = f'<div id="{sid}-dipov" style="position:absolute;inset:0;background:#2b1d14;opacity:0;pointer-events:none"></div>' if s.get("seam_out") == "dip" else ""
    return (f'<template><style>{CSS}</style>'
            f'<div id="root" data-composition-id="{sid}" data-width="{FW}" data-height="{FH}" data-layout-allow-overflow data-layout-allow-overlap data-motion-blur="on"'
            f'{" style=background:transparent" if s.get("seam") == "iris" else ""}>'
            f'<div id="{sid}-view" style="position:absolute;inset:0;transform-origin:50% 50%">{"".join(body)}</div>{dip}</div>{GSAP}<script>{script}</script></template>')


def seam_in_js(s: dict) -> str:
    """新鏡的進場（掛在 root 時間軸 0 秒）：push 從放大模糊落定、pull 從拉近落定、iris 開圓、whip 甩進、dip／cut 無。"""
    sid, seam, lead = s["id"], s.get("seam", "cut"), float(s.get("lead") or 0)
    view = f"#{sid}-view"
    if seam == "push":
        return f'root.fromTo("{view}",{{scale:1.28,filter:"blur(10px)"}},{{scale:1,filter:"blur(0px)",duration:0.3,ease:"expo.out"}},0);'
    if seam == "pull":
        return f'root.fromTo("{view}",{{scale:1.16,filter:"blur(8px)"}},{{scale:1,filter:"blur(0px)",duration:0.32,ease:"expo.out"}},0);'
    if seam == "iris":
        x, y = s.get("iris_at") or (540, 1000)
        return (f'root.fromTo("{view}",{{clipPath:"circle(4% at {x}px {y}px)"}},{{clipPath:"circle(110% at {x}px {y}px)",'
                f'duration:{lead + 0.12:.2f},ease:"power1.in"}},0);')
    if seam == "whip":
        return f'root.fromTo("{view}",{{x:-700,filter:"blur(18px)"}},{{x:0,filter:"blur(0px)",duration:0.24,ease:"power3.out"}},0);'
    return ""


def seam_out_js(s: dict) -> str:
    """舊鏡的離場（掛在內容時間軸結尾）：push 推進帕帕的臉、pull 退後模糊、whip 往左甩出、dip 暗 40%；iris／cut 無。"""
    sid, seam, d = s["id"], s.get("seam_out", "cut"), s["d"]
    view = f"#{sid}-view"
    if seam == "push":
        x, y = s.get("push_to") or (540, 960)
        return f'tl.to("{view}",{{transformOrigin:"{x}px {y}px",scale:1.5,filter:"blur(10px)",duration:0.3,ease:"power3.in"}},{d - 0.3:.3f});'
    if seam == "pull":
        return f'tl.to("{view}",{{scale:0.9,filter:"blur(8px)",duration:0.22,ease:"power3.in"}},{d - 0.22:.3f});'
    if seam == "whip":
        return f'tl.to("{view}",{{x:380,filter:"blur(14px)",duration:0.15,ease:"power3.in"}},{d - 0.15:.3f});'
    if seam == "dip":
        return f'tl.to("#{sid}-dipov",{{opacity:0.4,duration:0.1,ease:"power2.in"}},{d - 0.1:.3f});'
    return ""


def audio_html(ep: dict, sfx_durations: dict[str, float]) -> str:
    """配樂（ep["music"]）＋音效（各鏡 sfx，同時響的分到不同軌）。缺檔的音效略過。"""
    out = []
    for m in ep["music"]:
        out.append(f'<audio id="{m["id"]}" class="clip" data-timeline-role="music" src="assets/music/{m["mood"]}.mp3" data-start="{m["t"]}" data-duration="{m["d"]}" '
                   f'data-media-start="{m["media_start"]}" data-volume="{MUSIC_VOL}" data-fade-in="{m["fade_in"]}" '
                   f'data-fade-out="{m["fade_out"]}" data-track-index="3"></audio>')
    n, lanes = 0, []
    for s in ep["shots"]:
        for name, off in s.get("sfx", []):
            if name not in sfx_durations:
                continue
            n += 1
            st, d = round(s["t"] + off + 0.033, 3), round(sfx_durations[name], 3)
            lane = next((i for i, end in enumerate(lanes) if end <= st), None)
            if lane is None:
                lanes.append(0.0)
                lane = len(lanes) - 1
            lanes[lane] = st + d
            out.append(f'<audio id="x{n}" class="clip" src="assets/sfx/{name}.mp3" data-start="{st}" data-duration="{d}" '
                       f'data-volume="{SFX_VOL.get(name, 0.8)}" data-track-index="{4 + lane}"></audio>')
    return "\n".join(out)


def write_project(ep: dict, project: Path, sfx_durations: dict[str, float]) -> Path:
    """寫 index.html 與 compositions/*.html；素材（assets/）由呼叫端放好。"""
    comp = project / "compositions"
    comp.mkdir(parents=True, exist_ok=True)
    hosts = []
    shots = ep["shots"]
    for k, s in enumerate(shots):
        (comp / f"{s['id']}.html").write_text(build_shot(s, ep), encoding="utf-8")
        lead = float(s.get("lead") or 0)
        tail = float(shots[k + 1].get("lead") or 0) if k + 1 < len(shots) else 0.0  # 下一鏡圓場時舊鏡多留一下
        layer = int(s.get("layer") or 1)
        hosts.append(f'<div id="{s["id"]}" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" '
                     f'data-start="{round(s["t"] - lead, 3)}" data-duration="{round(s["d"] + lead + tail, 3)}" data-track-index="{layer}" data-track-kind="graphics" '
                     f'data-width="{FW}" data-height="{FH}" style="z-index:{int(s.get("z") or 1)}"></div>')
    (project / "index.html").write_text(
        '<!doctype html>\n<html lang="zh-Hant" data-resolution="portrait">\n'
        f'<head><meta charset="UTF-8"><meta name="viewport" content="width=1080, height=1920">{GSAP}\n'
        '<style>*{margin:0;padding:0;box-sizing:border-box} html,body{width:1080px;height:1920px;overflow:hidden;background:#FBF3E8}</style></head>\n'
        f'<body><div id="root" data-composition-id="main" data-start="0" data-duration="{ep["total"]}" data-width="{FW}" data-height="{FH}">\n'
        + "\n".join(hosts) + "\n" + audio_html(ep, sfx_durations) + "\n</div>\n"
        '<script>window.__timelines = window.__timelines || {};window.__timelines["main"] = gsap.timeline({ paused: true });</script></body></html>\n',
        encoding="utf-8")
    (project / "meta.json").write_text(json.dumps({"name": f"papa-home-ep{ep['episode']:02d}"}), encoding="utf-8")
    (project / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "assets": "assets"}}), encoding="utf-8")
    return project
