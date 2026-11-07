"""《帕帕貝貝家》改 engine／compile／動作庫前後逐格比對：兩個 HyperFrames 專案各截 N 格，比像素。

    uv run python main.py papa build ep01.json -o /tmp/before --only full   # 改之前（git stash 或舊 commit）
    uv run python main.py papa build ep01.json -o /tmp/after  --only full   # 改之後
    uv run python -m mamababy_private.scripts.papa_frame_diff /tmp/before/full /tmp/after/full --frames 40

每格最大像素差 > --tolerance 就列出來、結束碼 1。平常的守門是 pytest 的 GSAP 軌跡比對（test_papa_motion.py），這支是真的渲染。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from mamababy_private.papa_home import library as lib


def snapshot(project: Path, out: Path, frames: int) -> list[Path]:
    r = subprocess.run(["npx", "-y", lib.HYPERFRAMES, "snapshot", str(project), "--frames", str(frames), "--no-end", "--output", str(out)],
                       check=False, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"hyperframes snapshot 失敗（{project}，rc={r.returncode}）：\n{(r.stdout + r.stderr)[-1500:]}")
    return sorted(out.glob("frame-*.png"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--tolerance", type=int, default=0, help="允許的最大像素差（0–255）")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        a = snapshot(args.before, Path(tmp) / "a", args.frames)
        b = snapshot(args.after, Path(tmp) / "b", args.frames)
        if [p.name for p in a] != [p.name for p in b]:
            print(f"格數或時間不一樣：{len(a)} vs {len(b)}")
            return 1
        bad = 0
        for x, y in zip(a, b):
            d = np.abs(np.asarray(Image.open(x).convert("RGB"), int) - np.asarray(Image.open(y).convert("RGB"), int))
            if d.max() > args.tolerance:
                bad += 1
                thr = max(args.tolerance, 8)
                print(f"✗ {x.name}：最大差 {d.max()}，{(d > thr).mean():.2%} 的像素差 > {thr}")
    print(f"{len(a)} 格，{bad} 格不一樣" if bad else f"✓ {len(a)} 格完全一樣")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
