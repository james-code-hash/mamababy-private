# deploy

`from-mamababy-tools/` is the claw-arm-1 Docker tooling from mamababy-tools #211, copied as-is
(`claw_docker.sh`, `claw-compose.yaml`, its test). It still targets the mamababy-tools image and `~/.mamababy`.

Before the cutover it becomes `claw_v2.sh` (preflight / cutover / rollback / deploy) plus a v2 compose file
and a `deploy-claw.yml` workflow here, running the image this repo builds on top of money-erp-v2.
The generic parts of #211 (scheduler drain, runtime marker, `schedule_freeze`) are already in v2.
