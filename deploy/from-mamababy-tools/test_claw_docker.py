"""claw-arm-1 從 systemd 換 Docker：兩套不能同時跑的防呆。"""
from mamababy.cli import schedules as sch
from mamababy.cli.scripts import cron_schedule_sync, schedule_freeze
from mamababy.core import bootstrap
from mamababy.core.config import PROJECT_ROOT


def test_runtime_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bootstrap.runtime_mode() == "systemd"
    (tmp_path / ".mamababy").mkdir()
    (tmp_path / ".mamababy/runtime").write_text("docker\n")
    assert bootstrap.runtime_mode() == "docker"
    (tmp_path / ".mamababy/runtime").write_text("something")
    assert bootstrap.runtime_mode() == "switching"
    (tmp_path / ".mamababy/runtime").write_text("")
    assert bootstrap.runtime_mode() == "systemd"


def test_schedule_sync_leaves_systemd_alone_in_docker_mode(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".mamababy").mkdir()
    (tmp_path / ".mamababy/runtime").write_text("docker")
    monkeypatch.setattr(cron_schedule_sync, "setup_env", lambda: (_ for _ in ()).throw(AssertionError("不該跑")))
    assert cron_schedule_sync.main() == 0
    assert "Docker 版" in capsys.readouterr().out


def test_freeze_fills_only_missing_jobs_with_systemd_state():
    order, erp = "mamababy-order-cycle", "mamababy-erp-sync"
    jobs_doc = {erp: {"enabled": False}}
    add, notes = schedule_freeze.freeze(jobs_doc, enabled={erp, "mamababy-listing-health-check"})
    assert erp not in add and any(erp in n for n in notes)  # 後台已有設定：不動、只提醒
    assert add[order] == {**next(j for j in sch.JOBS if j.timer == order).default, "enabled": False}
    assert add["mamababy-listing-health-check"]["enabled"] is True
    assert set(add) == {j.timer for j in sch.JOBS} - {erp}


def test_deploy_claw_checks_docker_marker_before_enabling_timers():
    text = (PROJECT_ROOT / "apps/ops-cli/deploy/deploy_claw.sh").read_text("utf-8")
    guard = text.index('"$runtime" != "systemd"')
    assert guard < text.index("systemctl --user enable --now")
    assert guard < text.index("cron_schedule_sync")


def test_claw_docker_drains_for_the_longest_job():
    script = (PROJECT_ROOT / "apps/ops-cli/deploy/claw_docker.sh").read_text("utf-8")
    compose = (PROJECT_ROOT / "docker/claw-compose.yaml").read_text("utf-8")
    assert "TimeoutStartSec" in script and "CLAW_DRAIN_SEC=$MAX_JOB_SEC" in script
    assert "MAMABABY_DRAIN_SEC: ${CLAW_DRAIN_SEC" in compose and "stop_grace_period: ${CLAW_STOP_GRACE" in compose


def test_switching_marker_blocks_both_sides(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".mamababy").mkdir()
    (tmp_path / ".mamababy/runtime").write_text("switching")
    assert bootstrap.runtime_mode() == "switching"
    assert cron_schedule_sync.main() == 0


def test_scheduler_children_get_env_before_setup(monkeypatch):
    from mamababy.cli import scheduler as sd

    monkeypatch.setattr(sd, "_BASE_ENV", {"A": "1"})
    env = sd._child_env()
    assert env == {"A": "1"} and env is not sd._BASE_ENV


def test_freeze_rejects_empty_or_unknown_enabled(capsys):
    assert schedule_freeze.main(["--enabled", ""]) == 2
    assert schedule_freeze.main(["--enabled", "mamababy-no-such-job"]) == 2
    assert "不在排程清單" in capsys.readouterr().out
