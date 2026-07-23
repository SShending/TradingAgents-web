# Phase 2 Local Operations

## Production Start

Install the Python web extra and locked frontend dependencies once:

```bash
python -m pip install -e ".[web]"
cd web && npm ci && cd ..
```

Build the frontend and start the local API/static server with one command:

```bash
./scripts/start-web.sh
```

The application binds to `127.0.0.1:8000`. Set `TRADINGAGENTS_WEB_DEMO=1` for
deterministic local demo data. Live mode is the default and requires the chosen
provider configuration. CIII uses `CIII_API_KEY`,
`TRADINGAGENTS_CIII_BASE_URL`, `TRADINGAGENTS_QUICK_THINK_LLM`, and
`TRADINGAGENTS_DEEP_THINK_LLM` on the server. None of these values are returned
to the browser.

The default database is `~/.tradingagents/web/tradingagents.db`. Override it
with `TRADINGAGENTS_WEB_DB_PATH`. Cache and generated report roots remain under
`~/.tradingagents` unless their existing configuration overrides are used.

## Docker

```bash
docker compose up --build tradingagents-web
```

The published port is bound to localhost. Named volumes separately retain the
SQLite workspace/backups, provider cache, and report output. Rebuilding or
recreating the container does not remove these volumes.

## Backup And Restore

Create and list server-controlled backups:

```bash
tradingagents-web-admin backup
tradingagents-web-admin list
```

Restoration is always a two-step operation. Stop active analyses first, inspect
the backup, then commit the same backup ID:

```bash
tradingagents-web-admin preview <backup-id>
tradingagents-web-admin restore <backup-id>
```

Preview rejects corrupt, incomplete, or newer-schema databases. The HTTP API
and browser follow the same preview-before-commit workflow and never accept an
arbitrary filesystem path.

## Recovery Semantics

At startup, persisted `queued`, `running`, or `cancelling` jobs become
`interrupted`. They never continue automatically or spend provider budget after
a restart. A Resume action is offered only when a checkpoint validator confirms
the exact stored run signature. Terminal reports, advice versions, events,
usage, evidence, trust, and conversations remain available.
