"""《帕帕貝貝家》第 1 集「畫面不變」的指紋：每鏡 DOM（去掉 script）與 GSAP 呼叫軌跡（papa_trace.js）各一個 sha256。

engine／compile／動作庫改寫後，指紋一樣＝每一格畫面一樣（同樣的元素、同樣的 tween、同樣的時間與順序）。
比對：uv run python tests/papa_golden.py（不一致結束碼 1）
重產（確定畫面本來就要變時）：uv run python tests/papa_golden.py --write
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from mamababy_private.papa_home import compile as comp
from mamababy_private.papa_home import engine
from mamababy_private.papa_home import library as lib

HERE = Path(__file__).resolve().parent
TRACE_JS = HERE / "papa_trace.js"
GOLDEN = HERE / "fixtures" / "papa_ep01_golden.json"
EP01 = Path(lib.__file__).parent / "episodes" / "archive" / "ep01_baby.json"


def node() -> str | None:
    return shutil.which("node")


def traces(ep: dict) -> dict[str, dict]:
    """正片與精華版每一鏡的 {dom, js, n}（n＝tween 呼叫數，方便看差在哪）。"""
    items, doms = [], {}
    for name, src in (("full", ep), ("cut", comp.cut_episode(ep))):
        low = comp.compile_episode(src)
        doms[f"_compile/{name}"] = json.dumps(low, ensure_ascii=False, sort_keys=True)
        for s in low["shots"]:
            html = engine.build_shot(s, low)
            key = f"{name}/{s['id']}"
            items.append({"id": key, "html": html})
            doms[key] = re.sub(r"<script>[\s\S]*?</script>", "", html)
    exe = node()
    if exe is None:
        raise RuntimeError("找不到 node：GSAP 軌跡要用 node 跑 papa_trace.js")
    r = subprocess.run([exe, str(TRACE_JS)], input=json.dumps(items), capture_output=True, text=True, check=True)
    calls = json.loads(r.stdout)
    out = {}
    for key, dom in doms.items():
        if key.startswith("_compile/"):  # 低階分鏡（座標、時間）本身也要一樣
            out[key] = {"sha": hashlib.sha256(dom.encode()).hexdigest()[:16]}
            continue
        js = json.dumps(calls[key], ensure_ascii=False, sort_keys=True)
        out[key] = {"dom": hashlib.sha256(dom.encode()).hexdigest()[:16], "js": hashlib.sha256(js.encode()).hexdigest()[:16],
                    "n": len(calls[key])}
    return out


def ep01() -> dict:
    return json.loads(EP01.read_text(encoding="utf-8"))


if __name__ == "__main__":
    if "--write" in sys.argv:
        GOLDEN.write_text(json.dumps(traces(ep01()), indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"寫入 {GOLDEN}")
    else:  # 預設：和 fixture 比對，不一致結束碼 1（pytest test_ep01_renders_identically 做同一件事）
        got, want = traces(ep01()), json.loads(GOLDEN.read_text(encoding="utf-8"))
        diff = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
        if diff:
            print("第 1 集指紋不一致：" + "、".join(diff))
            sys.exit(1)
        print(f"✓ 第 1 集指紋一致（{len(want)} 項）")
