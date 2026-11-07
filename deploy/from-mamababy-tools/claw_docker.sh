#!/usr/bin/env bash
# claw-arm-1 從 systemd timer 換成 Docker 版內建排程器（docker/claw-compose.yaml）。在 claw-arm-1 上跑。
#
#   claw_docker.sh preflight [tag]   只讀檢查：容器讀得到 .env／Firestore／Postiz、排程表和 systemd 現況比對。
#                                   systemd 照跑，不寫任何正式資料，隨時可跑。
#   claw_docker.sh cutover [--yes]   切換：補後台排程設定（照 systemd 現況）→ 停 systemd timer → 等跑到一半的
#                                   工作做完 → 寫 ~/.mamababy/runtime=docker → 啟動容器
#   claw_docker.sh rollback [--yes]  退回：停容器（等工作做完）→ 刪記號 → 重新啟用切換前的 systemd timer
#   claw_docker.sh deploy <sha>      換版（image.yml 在 main 推完映像檔後呼叫）；還在 systemd 就什麼都不做
#   claw_docker.sh status            目前用哪一套、容器狀態、最近的 log
#
# 兩套絕對不能同時跑寫入排程（BigSeller 同帳號互踢、訂單循環重複下 1688 單），所以：
# - 記號檔 ~/.mamababy/runtime 是唯一開關；deploy_claw.sh 與 cron_schedule_sync 看到 docker 就不碰 systemd timer。
# - cutover 先停 timer、等 systemd 的工作跑完才啟動容器；rollback 先停容器（等工作跑完）才開 timer。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$REPO/docker/claw-compose.yaml"
STATE_DIR="$HOME/.mamababy"
ENV_FILE="$STATE_DIR/claw-docker.env"
MARKER="$STATE_DIR/runtime"
BEFORE="$STATE_DIR/systemd-timers.before"
IMAGE_REPO="${CLAW_IMAGE_REPO:-ghcr.io/james-code-hash/mamababy-tools-ops}"
LOCK="$STATE_DIR/claw-docker.lock"
# 換版／退回時等工作做完的上限＝所有 .service 最長的 TimeoutStartSec（compose 的 stop_grace_period 要更長）
MAX_JOB_SEC="$(grep -ho '^TimeoutStartSec=[0-9]*$' "$REPO"/apps/ops-cli/deploy/systemd/mamababy-*.service | cut -d= -f2 | sort -n | tail -1 || true)"
[[ "$MAX_JOB_SEC" =~ ^[1-9][0-9]*$ ]] || { echo "❌ systemd unit 檔找不到純秒數的 TimeoutStartSec，算不出換版要等多久" >&2; exit 1; }
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo -n docker); fi

die() { echo "❌ $*" >&2; exit 1; }
# systemd（沒有記號）／docker／switching（切換或退回進行中：兩套都不准啟動），與 bootstrap.runtime_mode 同規則
mode() {
  local m
  m="$(tr -d '[:space:]' <"$MARKER" 2>/dev/null || true)"
  case "$m" in ""|systemd) echo systemd ;; docker) echo docker ;; *) echo switching ;; esac
}
set_mode() { mkdir -p "$STATE_DIR"; echo "$1" >"$MARKER.tmp" && mv "$MARKER.tmp" "$MARKER"; }
# cutover／rollback／deploy 互斥（CI 的換版要等手動切換做完）
lock() { mkdir -p "$STATE_DIR"; exec 9>"$LOCK"; flock -w "${1:-7200}" 9 || die "等不到 $LOCK（另一個切換／換版在跑）"; }
confirm() {
  [[ "${YES:-0}" == "1" ]] && return 0
  read -r -p "$1 輸入 yes 繼續：" ans
  [[ "$ans" == "yes" ]] || die "已取消"
}

write_env() {  # $1 = 映像檔 tag（寫進檔案，之後 up 用這個版本）
  local sock_gid docker_bin root_env="/dev/null"
  sock_gid="$(stat -c %g /var/run/docker.sock)"
  docker_bin="$(readlink -f "$(command -v docker)")" || die "主機找不到 docker 指令"
  mkdir -p "$STATE_DIR" "$HOME/mamababy-tools/data" "$HOME/mamababy-tools/reports"  # compose 掛的是正式 checkout 的 data／reports
  # systemd 版會讀 repo 根目錄 .env（load_root_env，會蓋掉其他來源）；有的話掛成容器的 /app/.env
  [[ -f "$HOME/mamababy-tools/.env" ]] && root_env="$HOME/mamababy-tools/.env"
  cat >"$ENV_FILE.tmp" <<EOF
IMAGE=$IMAGE_REPO:$1
CLAW_UID=$(id -u)
CLAW_GID=$(id -g)
CLAW_HOME=$HOME
CLAW_DOCKER_GID=$sock_gid
CLAW_DOCKER_BIN=$docker_bin
CLAW_ROOT_ENV=$root_env
CLAW_DRAIN_SEC=$MAX_JOB_SEC
CLAW_STOP_GRACE=$(( MAX_JOB_SEC + 300 ))s
EOF
  mv "$ENV_FILE.tmp" "$ENV_FILE"
}

compose() { "${DOCKER[@]}" compose -p mamababy-claw -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }
in_container() { compose run --rm --no-deps -T ops "$@"; }  # 一次性容器（同樣的掛載與 uid）

enabled_timers() {
  systemctl --user list-unit-files 'mamababy-*.timer' --state=enabled --no-legend 2>/dev/null | awk '{print $1}' | sort
}
running_services() {
  systemctl --user list-units 'mamababy-*.service' --state=activating,active,deactivating --no-legend --plain 2>/dev/null \
    | awk '{print $1}'
}

pull() {  # $1 = tag；$2 = keep：只拿來檢查，不改正在跑的容器要用的版本（環境變數 IMAGE 優先於 env 檔）
  if [[ "${2:-}" == "keep" && -f "$ENV_FILE" ]]; then
    local cur
    cur="$(grep '^IMAGE=' "$ENV_FILE" | cut -d= -f2-)"
    write_env "${cur##*:}"
    export IMAGE="$IMAGE_REPO:$1"
  else
    write_env "$1"
    unset IMAGE
  fi
  echo "▶ 下載映像檔 $IMAGE_REPO:$1"
  compose pull -q ops
}

check_python() {  # 容器裡的只讀檢查（不印任何金鑰內容）
  in_container -c '
import os, shutil, subprocess, sys
from mamababy.cli.scripts.cron_utils import setup_env
setup_env()
ok = True
def line(good, msg):
    global ok
    ok = ok and good
    print(("✅ " if good else "❌ ") + msg)
home = os.path.expanduser("~")
line(os.path.isfile(os.path.join(home, ".mamababy/.env")), f"HOME={home}，讀得到 ~/.mamababy/.env")
line(os.path.isfile(os.path.join(home, ".mamababy/secret_key.pem")), "私鑰 ~/.mamababy/secret_key.pem")
line(os.path.isfile(os.path.join(home, ".bigseller_cookies.json")), "BigSeller cookie 檔（只看在不在，不登入）")
missing = sorted(k for k, v in os.environ.items()
                 if v.startswith("/") and "PATH" not in k and k not in ("HOME", "PWD", "OLDPWD", "SHELL")
                 and not v.startswith(("/usr", "/bin", "/opt", "/app", "/run/user")) and not os.path.exists(v.split(":")[0]))
line(not missing, "設定裡的路徑容器都看得到" + (f"（看不到：{', '.join(missing)}）" if missing else ""))
try:
    from mamababy.core.bootstrap import firebase_project_id
    from mamababy.core.firestore_client import get_client
    pid = firebase_project_id()
    snap = get_client(pid).collection("settings").document("app").get()
    line(snap.exists, f"Firestore {pid} 讀得到 settings/app")
except Exception as e:
    line(False, f"Firestore：{type(e).__name__}: {str(e)[:200]}")
line(os.path.isfile(os.path.join(home, ".mamababy/onboarding_done")), "開機精靈已標完成（會寫入的排程才會跑）")
try:
    from mamababy.core import postiz
    line(bool(postiz.query("SELECT 1")), "Postiz 資料庫（docker exec postiz-postgres）")
except Exception as e:
    line(False, f"Postiz 資料庫：{e}")
for tool in ("codex", "agy", "claude", "ffmpeg", "tesseract"):
    path = shutil.which(tool) or "沒有"
    line(path != "沒有", f"{tool}：{path}")
for tool, home_dir in (("codex", ".codex"), ("claude", ".claude"), ("agy", ".gemini")):
    line(os.path.isdir(os.path.join(home, home_dir)), f"{tool} 登入資料 ~/{home_dir}")
sys.exit(0 if ok else 1)
'
}

preflight() {
  local tag="${1:-main}" rc=0
  lock  # 會改 env 檔，跟 deploy／cutover 排隊
  echo "── 主機 ──"
  echo "使用者 $(id -un) uid=$(id -u) gid=$(id -g) HOME=$HOME"
  echo "目前排程：$(mode)"
  echo "docker：${DOCKER[*]}；$("${DOCKER[@]}" compose version 2>&1 | head -1)"
  echo "docker CLI：$(readlink -f "$(command -v docker)")（$(file -b "$(readlink -f "$(command -v docker)")" 2>/dev/null | cut -c1-60)）"
  echo "systemd 啟用中的 timer：$(enabled_timers | tr '\n' ' ')"
  echo "systemd 正在跑的工作：$(running_services | tr '\n' ' ')"
  [[ -f "$HOME/mamababy-tools/.env" ]] && echo "ℹ️ repo 根目錄有 .env，容器會掛成 /app/.env（與 systemd 版一樣讀）"
  echo "── 容器（$tag）──"
  pull "$tag" keep
  in_container main.py --help >/dev/null && echo "✅ main.py 跑得起來" || { echo "❌ main.py 跑不起來"; rc=1; }
  check_python || rc=1
  echo "── 排程比對（照後台設定＋systemd 現況）──"
  local list
  list="$(enabled_timers | tr '\n' ',')"
  if [[ -n "$list" ]]; then
    in_container -m mamababy.cli.scripts.schedule_freeze --enabled "$list" || rc=1
  else
    echo "ℹ️ systemd 沒有啟用中的 timer（目前 $(mode)），略過比對"
  fi
  echo "── 容器排程器會用的排程（補完上面的設定後）──"
  in_container -m mamababy.cli.scheduler --once --live || rc=1
  if [[ "$rc" == 0 ]]; then
    echo "✅ preflight 全部通過，可以 cutover"
  else
    echo "❌ 有項目沒過（見上方），先別 cutover"
  fi
  return "$rc"
}

wait_systemd_idle() {  # 最多等最長的工作逾時＋5 分鐘；等不到回 1
  local deadline=$(( $(date +%s) + MAX_JOB_SEC + 300 )) busy
  while :; do
    busy="$(running_services | tr '\n' ' ')"
    [[ -z "${busy// }" ]] && return 0
    (( $(date +%s) < deadline )) || { echo "⚠️ 等太久還有 systemd 工作在跑：$busy" >&2; return 1; }
    echo "⏳ 等 systemd 工作跑完：$busy"
    sleep 20
  done
}

restore_systemd() {  # 切換失敗：把 timer 開回來、刪記號，不要讓兩套都停著
  echo "↩️ 開回 systemd timer：$(tr '\n' ' ' <"$BEFORE")" >&2
  # shellcheck disable=SC2046
  systemctl --user enable --now $(cat "$BEFORE") || true
  rm -f "$MARKER"
}

wait_started() {  # $1 = compose up 之前的時間（只看新容器的 log）
  local i since="${1:?}"
  for i in $(seq 1 24); do
    if [[ -n "$(compose ps -q --status running ops 2>/dev/null)" ]] \
       && compose logs --since "$since" ops 2>/dev/null | grep -q "內建排程器啟動"; then
      echo "✅ 容器排程器已啟動"
      compose logs --tail 20 ops
      return 0
    fi
    sleep 5
  done
  compose logs --tail 50 ops || true
  echo "❌ 容器 2 分鐘內沒有啟動排程器（log 在上面）" >&2
  return 1
}

cutover() {
  lock
  [[ "$(mode)" == "docker" ]] && die "已經是 Docker 版了（$0 status 看狀態）"
  pull main
  check_python || die "容器檢查沒過，先跑 $0 preflight 看細節"
  local timers
  timers="$(enabled_timers)"
  if [[ -z "$timers" && -s "$BEFORE" ]]; then  # 上次 cutover 停完 timer 後中斷：沿用當時記下的清單
    timers="$(cat "$BEFORE")"
    echo "ℹ️ timer 已停用，沿用上次記下的清單 $BEFORE"
  fi
  [[ -n "$timers" ]] || die "systemd 沒有啟用中的 mamababy timer，不知道要沿用什麼；先確認現況"
  echo "systemd 目前啟用：$(echo "$timers" | tr '\n' ' ')"
  confirm "會停掉上面這些 systemd timer、改由容器跑（訂單循環、1688 下單等照常）。"
  echo "$timers" >"$BEFORE"
  echo "▶ 1/5 後台排程補上 systemd 現況（只補沒設定的）"
  in_container -m mamababy.cli.scripts.schedule_freeze --enabled "$(echo "$timers" | tr '\n' ',')" --commit
  echo "▶ 2/5 寫記號 switching（這之後部署不會再開 timer）、停 systemd timer"
  set_mode switching
  # 之後任何一步意外中斷（指令失敗、ssh 斷線、Ctrl-C）：開回 systemd，不要停在兩套都不跑
  trap 'rc=$?; trap - EXIT; if [[ "$(mode)" == switching ]]; then compose down >/dev/null 2>&1 || true; restore_systemd; echo "↩️ cutover 中斷，已退回 systemd" >&2; fi; exit $rc' EXIT
  trap 'exit 130' INT TERM
  # shellcheck disable=SC2046
  systemctl --user disable --now $(echo "$timers")
  echo "▶ 3/5 等還在跑的 systemd 工作結束"
  wait_systemd_idle || { restore_systemd; die "沒有切換，已退回 systemd；等那些工作跑完再重跑 cutover"; }
  echo "▶ 4/5 啟動容器"
  since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  compose up -d ops
  wait_started "$since" || { compose down; restore_systemd; die "容器沒起來，已退回 systemd（log 在上面）"; }
  echo "▶ 5/5 寫記號 docker"
  set_mode docker
  echo "✅ 已切到 Docker 版。看 log：$0 status；退回：$0 rollback"
}

rollback() {
  [[ -f "$BEFORE" ]] || die "找不到切換前的 timer 清單 $BEFORE，無法自動退回（可改跑 deploy_claw.sh --local 後手動開訂單循環）"
  [[ "$(mode)" == "systemd" ]] && die "已經是 systemd 了（$0 status 看狀態）"
  confirm "會停掉容器（等工作做完，最多 $(( MAX_JOB_SEC / 60 )) 分鐘）、重新啟用 systemd：$(tr '\n' ' ' <"$BEFORE")。"
  lock
  [[ "$(mode)" == "systemd" ]] && die "已經是 systemd 了（$0 status 看狀態）"
  echo "▶ 1/4 寫記號 switching（這之後 CI 不會再換版容器）"
  set_mode switching
  # 中途中斷：容器確定停了就照樣開回 systemd；容器還在跑就留在 switching（兩套都不會重複），印出怎麼接手
  trap 'rc=$?; trap - EXIT; if [[ "$(mode)" == switching ]]; then
          if [[ -z "$(compose ps -q --status running ops 2>/dev/null)" ]]; then restore_systemd; echo "↩️ rollback 中斷，容器已停，已開回 systemd" >&2;
          else echo "⚠️ rollback 中斷，容器還在跑、記號停在 switching；再跑一次 $0 rollback" >&2; fi; fi; exit $rc' EXIT
  trap 'exit 130' INT TERM
  if [[ -f "$ENV_FILE" ]]; then
    echo "▶ 2/4 停容器（等還在跑的工作結束）"
    compose down
  fi
  echo "▶ 3/4 裝最新的 systemd unit（Docker 期間部署不會更新它們）"
  mkdir -p "$HOME/.config/systemd/user"
  cp "$HOME"/mamababy-tools/apps/ops-cli/deploy/systemd/mamababy-*.{service,timer} "$HOME/.config/systemd/user/"
  systemctl --user daemon-reload
  echo "▶ 4/4 啟用 systemd timer、刪記號"
  rm -f "$MARKER"
  # shellcheck disable=SC2046
  systemctl --user enable --now $(cat "$BEFORE")
  (cd "$HOME/mamababy-tools" && uv run python -m mamababy.cli.scripts.cron_schedule_sync) \
    || echo "⚠️ 後台排程設定套用失敗，timer 先維持切換前的狀態"
  systemctl --user list-timers 'mamababy-*' --no-pager
  echo "✅ 已退回 systemd"
}

deploy() {
  local sha="${1:?用法：$0 deploy <sha>}"
  lock
  if [[ "$(mode)" != "docker" ]]; then
    echo "ℹ️ claw-arm-1 排程是 $(mode)，容器不部署（切換用 $0 cutover）"
    return 0
  fi
  local cur
  cur="$(grep '^IMAGE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | sed 's/.*://')"
  if [[ -n "$cur" && "$cur" != "$sha" && "$cur" != main ]]; then
    if ! git -C "$REPO" cat-file -e "$cur^{commit}" 2>/dev/null; then
      git -C "$REPO" fetch -q origin "$cur" 2>/dev/null || true
    fi
    if ! git -C "$REPO" cat-file -e "$cur^{commit}" 2>/dev/null; then
      echo "⚠️ 查不到容器目前的版本 ${cur:0:8}，不確定 ${sha:0:8} 是否較新，先不換版（手動：$0 deploy <sha>，或改 $ENV_FILE）"
      return 0
    fi
    if git -C "$REPO" merge-base --is-ancestor "$sha" "$cur"; then
      echo "ℹ️ 容器已是較新的 ${cur:0:8}，不退回舊版 ${sha:0:8}"
      return 0
    fi
  fi
  pull "$sha"
  echo "▶ 換版到 ${sha:0:8}（舊容器會等跑到一半的工作做完）"
  local since
  since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  compose up -d ops
  wait_started "$since" || die "新版容器沒起來；要退回 systemd：$0 rollback"
}

status() {
  echo "目前排程：$(mode)"
  echo "systemd 啟用中的 timer：$(enabled_timers | tr '\n' ' ')"
  if [[ -f "$ENV_FILE" ]]; then
    grep '^IMAGE=' "$ENV_FILE"
    compose ps
    compose logs --tail 40 ops || true
  else
    echo "容器還沒設定過（$ENV_FILE 不存在）"
  fi
}

cmd="${1:-}"; shift || true
YES=0
args=()
for a in "$@"; do [[ "$a" == "--yes" ]] && YES=1 || args+=("$a"); done
case "$cmd" in
  preflight) preflight "${args[@]}" ;;
  cutover) cutover ;;
  rollback) rollback ;;
  deploy) deploy "${args[@]}" ;;
  status) status ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
