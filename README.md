# Simple Observability Demo (Node.js + TypeScript)

## Quick Start
```bash
docker compose up -d --build
```

Run load:
```bash
docker compose run --rm loadgen
```

Chaos (slow worker calls ~30%):
```bash
CHAOS_DELAY=true docker compose up -d worker
```

Disable chaos:
```bash
docker compose up -d worker
```

## Grafana
- http://localhost:3000 (admin/admin or anonymous)
- Dashboard: Service Overview

## Services
- API: http://localhost:8080
- Worker: http://localhost:8081

## Local Dev (IntelliSense)
From `services/api` or `services/worker`:
```bash
npm install
npm run dev:ts
```

## Notes
- Metrics are generated from traces via OTel Collector spanmetrics.
- Logs are collected by Promtail from container stdout and shown in Loki.
