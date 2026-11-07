"""組 HyperFrames 專案（素材用連結）→ 渲染 → 響度拉到社群平台標準。

配樂與音效不進 repo（Pixabay 授權不能把原始檔轉散布），放在 `mamababy_private.config.PAPA_AUDIO_DIR`：
    music/{theme,daily,trouble,solution,twist}.mp3   每首已拉到 -16 LUFS
    sfx/{scratch,bark,...}.mp3                        已裁好、-18 LUFS
缺檔的音效略過並記在 errors；整個資料夾沒有就是無聲片（呼叫端決定要不要發）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from mamababy_private.papa_home import compile as comp
from mamababy_private.papa_home import engine
from mamababy_private.papa_home import library as lib

TARGET_LUFS = -15


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _link(src: Path, dst: Path) -> None:
    if dst.is_symlink() or dst.exists():
        dst.unlink() if dst.is_symlink() or dst.is_file() else shutil.rmtree(dst)
    dst.symlink_to(src.resolve())


def assemble(project: Path, audio_dir: Path | None, extra_props: Path | None = None) -> tuple[dict, dict, list[str]]:
    """放素材：角色／場景／字體連到素材包；props 合併素材包＋本集道具；music／sfx 連到 audio_dir。"""
    errors: list[str] = []
    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("characters", "scenes", "fonts"):
        _link(lib.ASSETS / name, assets / name)
    props = assets / "props"
    if props.is_symlink():
        props.unlink()
    props.mkdir(exist_ok=True)
    for src in [*(lib.ASSETS / "props").glob("*.webp"), *((extra_props or Path("/nonexistent")).glob("*.webp"))]:
        _link(src, props / src.name)
    music, sfx = {}, {}
    if audio_dir and audio_dir.is_dir():
        for kind, store, names in (("music", music, lib.MOODS), ("sfx", sfx, lib.SFX)):
            (assets / kind).mkdir(exist_ok=True)
            for n in names:
                f = audio_dir / kind / f"{n}.mp3"
                if f.exists():
                    _link(f, assets / kind / f.name)
                    store[n] = _duration(f)
                elif n == "bed":
                    errors.append("缺整集底樂 bed.mp3，退回依幕換曲")
                else:
                    errors.append(f"缺{('配樂' if kind == 'music' else '音效')} {n}")
    else:
        errors.append(f"沒有音效資料夾 {audio_dir}，成片無聲")
    return music, sfx, errors


def beat_grid(audio_dir: Path | None, music: dict[str, float]) -> dict[str, list[float]]:
    """每首配樂的拍點（秒），`npx hyperframes beats` 算一次存 audio_dir/beats/<mood>.json；抓不到的曲子略過。"""
    grid: dict[str, list[float]] = {}
    if not audio_dir or not music:
        return grid
    cache = audio_dir / "beats"
    cache.mkdir(exist_ok=True)
    for mood in music:
        f = cache / f"{mood}.json"
        if not f.exists():
            r = subprocess.run(["npx", "-y", lib.HYPERFRAMES, "beats", str(audio_dir / "music" / f"{mood}.mp3"), "--json"],
                               capture_output=True, text=True, check=False, env={**os.environ, "HYPERFRAMES_SKIP_SKILLS": "1"})
            try:
                data = json.loads(r.stdout[r.stdout.index("{"):]) if r.returncode == 0 else {}
            except ValueError:
                data = {}
            if not data.get("beatTimes"):
                continue  # 抓不到拍點不落盤（下次再算），這首這輪不對拍
            f.write_text(json.dumps({"bpm": data.get("bpm"), "beatTimes": data["beatTimes"]}), encoding="utf-8")
        times = json.loads(f.read_text(encoding="utf-8")).get("beatTimes") or []
        if times:
            grid[mood] = [float(x) for x in times]
    return grid


def build(ep: dict, project: Path, audio_dir: Path | None, extra_props: Path | None = None,
          cut: bool = False) -> tuple[Path, list[str]]:
    """高階分鏡 → 可渲染的 HyperFrames 專案資料夾（鏡頭結尾先對到配樂拍點）。"""
    music, sfx, errors = assemble(project, audio_dir, extra_props)
    src = comp.cut_episode(ep) if cut else ep
    src = comp.snap_to_beats(src, beat_grid(audio_dir, music), music)
    low = comp.compile_episode(src, music)
    if not music:
        low["music"] = []
    else:
        low["music"] = [m for m in low["music"] if m["mood"] in music]
    engine.write_project(low, project, sfx)
    return project, errors


def render(project: Path, output: Path, timeout: int = 1800, workers: int | None = None) -> Path:
    """npx hyperframes render；平行擷取逾時就改單一分頁重來。成功後響度拉到 TARGET_LUFS。"""
    raw = output.with_suffix(".raw.mp4")
    base = ["npx", "-y", lib.HYPERFRAMES, "render", str(project), "-o", str(raw), "--quality", "looks", "--quiet"]
    failures = []
    for n in ([workers] if workers == 1 else [workers, 1]):
        raw.unlink(missing_ok=True)
        try:
            r = subprocess.run(base + (["--workers", str(n)] if n else []), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout, check=False, env={**os.environ, "HYPERFRAMES_SKIP_SKILLS": "1"})
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"HyperFrames 渲染超過 {timeout} 秒") from None
        if r.returncode == 0 and raw.exists():
            break
        failures.append(f"workers={n or '預設'} rc={r.returncode}：" + "\n".join((r.stdout + r.stderr).strip().splitlines()[-6:])[:400])
    else:
        raise RuntimeError("HyperFrames 渲染失敗（" + "；".join(failures) + "）")
    has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                                str(raw)], capture_output=True, text=True).stdout.strip()
    if has_audio:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "copy",
                        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-movflags", "+faststart", str(output)], check=True)
        raw.unlink()
    else:
        raw.replace(output)
    return output


def stills(ep: dict, out: Path, timeout: int = 900) -> dict[str, Path]:
    """每鏡中間一格 PNG（不放音樂、不對拍，時間和分鏡一致）→ out/stills/<鏡頭 id>.png；給工作階段看圖審片。"""
    project, _ = build(ep, out / "project", None)
    low = comp.compile_episode(ep)
    times = [round(s["t"] + s["d"] / 2, 3) for s in low["shots"]]
    raw = out / "raw"
    if raw.exists():
        shutil.rmtree(raw)
    r = subprocess.run(["npx", "-y", lib.HYPERFRAMES, "snapshot", str(project), "--at", ",".join(map(str, times)), "--no-end",
                        "--output", str(raw)], capture_output=True, text=True, timeout=timeout, check=False)
    files = sorted(raw.glob("frame-*.png"), key=lambda p: int(p.name.split("-")[1]))
    if r.returncode != 0 or len(files) != len(times):
        raise RuntimeError(f"hyperframes snapshot rc={r.returncode}：{(r.stdout + r.stderr)[-400:]}")
    dest = out / "stills"
    dest.mkdir(parents=True, exist_ok=True)
    result = {}
    for s, f in zip(low["shots"], files):
        result[s["id"]] = dest / f"{s['id']}.png"
        shutil.copyfile(f, result[s["id"]])
    return result
