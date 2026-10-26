# Daily publication dispatcher

The GitHub `schedule` event has been removed because it is best-effort. The canonical trigger is a systemd timer on the Hermes automation host, which has the existing authenticated `gh` CLI. It dispatches `daily.yml` at 09:17 `Asia/Shanghai`; the workflow itself runs on a GitHub-hosted runner and uses its repository-scoped `GITHUB_TOKEN` to commit the snapshot. No personal write token or deploy key is copied to `repo-radar-prod`.

The dispatcher checks for today's README snapshot first, then triggers the workflow and monitors the result. If no archive appears, it retries up to five dispatches over 20 minutes. A host/network/GitHub/API outage can still prevent an on-time result. `Persistent=true` catches a timer missed while the automation host was down once it returns; it cannot publish during an outage. A failure-only Telegram watchdog checks again at 09:30 `Asia/Shanghai`; successful days produce no alert.

## Install on the Hermes automation host

The unit expects the repository checkout at `/root/workspace/openpulse-daily` and the active GitHub CLI account to be `asrod`:

```sh
install -o root -g root -m 0644 deploy/systemd/openpulse-daily-dispatch.service /etc/systemd/system/
install -o root -g root -m 0644 deploy/systemd/openpulse-daily-dispatch.timer /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/openpulse-daily-dispatch.service /etc/systemd/system/openpulse-daily-dispatch.timer
systemctl daemon-reload
systemctl enable --now openpulse-daily-dispatch.timer
```

## Verify and inspect

```sh
systemd-analyze calendar '*-*-* 09:17:00 Asia/Shanghai'
systemctl list-timers openpulse-daily-dispatch.timer
systemctl start openpulse-daily-dispatch.service
journalctl -u openpulse-daily-dispatch.service --since today
```

A manual service run is safe: if today's README already contains the complete dated snapshot, the dispatcher exits without triggering another workflow. GitHub Actions `workflow_dispatch` remains the manual recovery route.
