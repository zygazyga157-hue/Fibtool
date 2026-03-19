# launcher.py

Purpose
-------
Process orchestrator that spawns `live_entry_bot_mt5.py` child processes for each symbol/timeframe defined in `symbols_timeframes.json`. Provides restart-on-crash with exponential backoff, heartbeat notifications to Telegram, and status persistence.

Quick CLI
---------
PowerShell example:

```powershell
python launcher.py --interval 60 --heartbeat-interval 300 --heartbeat-dest admin --max-retries 5
```

Behavior and config
-------------------
- Reads `symbols_timeframes.json` to determine which symbol/timeframe pairs to spawn.
- Spawns one child process per pair using the system Python interpreter.
- The first spawned child can be given `--start-admin-poller` to centralize admin command handling.

Supervision
-----------
- Logs process events to `outputs/orchestrator_log.csv` and writes status to `outputs/orchestrator_status.json`.
- Implements exponential backoff (configurable via `--backoff-base` and `--backoff-cap`) and stops restarting after `--max-retries`.

Heartbeat
---------
- Periodic heartbeat messages summarize recent activity and process statuses. Sent to admin or group depending on `--heartbeat-dest`.
- Heartbeat checks `outputs/orders.csv` and `outputs/auto_state.json` for telemetry.

Best-run strategies
-------------------
- Run launcher on a stable environment (systemd, Windows service, or screen/tmux). On Windows, wrap via NSSM or Task Scheduler.
- Keep `config.py` available to child processes or provide env vars for Telegram/MT5 secrets.
- Monitor `outputs/orchestrator_log.csv` for child exits and backoff/retry counts.

Edge cases and notes
--------------------
- If child processes fail immediately, launcher will backoff and eventually give up; check child stdout/stderr to debug.
- Launcher uses `sys.executable` to spawn children — ensure virtualenv consistency if using one.
- If Telegram keys are missing, heartbeats are skipped silently.
