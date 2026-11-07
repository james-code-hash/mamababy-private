"""帕帕貝貝家的設定（不在主程式 REGISTRY 裡，讀環境變數；上線開關另可讀後台 settings/app 舊值）。"""

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ASSETS = PACKAGE / "assets" / "papa_home"
REPO_ROOT = PACKAGE.parent  # 以 editable 安裝（開發機）時是 repo 根目錄；映像檔裡不用

PAPA_AUDIO_DIR = os.environ.get("PAPA_AUDIO_DIR", "~/.moneyerp/papa-home-audio")  # 配樂 music/ 與音效 sfx/（不進 repo）
LIVE_KEY = "SOCIAL_PAPA_HOME_LIVE"  # 1＝已上線：每日社群週二、週五的 Reels 改發帕帕貝貝家


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes")


def live_from(environ: dict, settings_values: dict | None) -> bool:
    """環境變數優先；沒設就看後台 settings/app 存的舊值（舊版後台有這個開關）。"""
    if environ.get(LIVE_KEY, "") != "":
        return _truthy(environ[LIVE_KEY])
    return _truthy((settings_values or {}).get(LIVE_KEY))
