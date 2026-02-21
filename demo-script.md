# Observability Demo - Live Demo Script

Orlando DevOps Meetup

---

## Architecture

```
                    +-----------+
  loadgen --------> |  API :8080 | ------> | Worker :8081 |
                    +-----------+          +--------------+
                         |                       |
                         |     OTLP (HTTP)       |
                         +--------+--------------+
                                  v
                         +------------------+
                         | OTel Collector   |
                         | :4317/4318       |
                         +--+---------+-----+
                            |         |     \
                            v         v      v
                        Tempo     Prometheus  Loki
                        :3200     :9090       :3100
                            \         |      /
                             +--------+-----+
                             |   Grafana    |
                             |   :3000      |
                             +--------------+

  Promtail scrapes Docker container logs --> Loki
```

**Two services**: API (receives orders) -> Worker (processes them).
Both are TypeScript/Express with OpenTelemetry auto-instrumentation.

**Data flow**:
- **Traces**: Services -> OTel Collector -> Tempo
- **Metrics**: OTel Collector generates span metrics (RED) -> Prometheus scrapes :8889
- **Logs**: Services write JSON to stdout -> Promtail reads Docker logs -> Loki

---

## Pre-Demo Setup

```bash
# Build and start everything
docker compose up -d --build

# Verify all containers are running
docker compose ps
```

All 9 containers should be `Up`:
- `otel-collector`, `prometheus`, `loki`, `promtail`, `tempo`, `grafana`, `api`, `worker`, `loadgen`

Open Grafana: http://localhost:3000 (anonymous access, no login needed)

Smoke test:
```bash
curl -s -X POST http://localhost:8080/order \
  -H "Content-Type: application/json" \
  -d '{"id":"test-001","total":99}' | jq
```

Expected: `{"status":"ok","processed":true}`

---

## Act 1: The Happy Path (5 min)

### Load generation

The `loadgen` container starts automatically with `docker compose up`. It sends a POST to `/order` every 500ms for 5 minutes with random order IDs and amounts. If it has already exited, restart it:

```bash
docker compose up -d loadgen
```

### Walk through Grafana

1. **Service Overview dashboard** - http://localhost:3000/d/service-overview

   - **Request Rate by Service**: Two lines (api + worker), steady ~2 req/s each
   - **Error Rate %**: Green, near zero
   - **P95 Latency**: Low and flat (100-300ms range)

2. **Explore a trace** - Navigate to Explore -> Tempo

   - Pick any recent trace
   - Three spans: `api` server span (POST /order), `api` client span (POST to worker), `worker` server span (POST /process)
   - "This is the full lifecycle of one order"

3. **Show log correlation** - Navigate to Explore -> Loki

   - Query: `{service="api"}`
   - Expand a log line — see structured JSON with `trace_id`, `span_id`, `order_id`
   - Click the `TraceID` derived field link to jump to the trace in Tempo
   - "One click from any log line to its full distributed trace"

### Talking points

- "OTel auto-instrumentation means zero manual span code - just import `tracing.ts` and everything is traced"
- "Span metrics connector converts every trace into request rate, error rate, and latency histograms automatically"
- "Promtail picks up structured JSON logs from Docker and ships to Loki - services just write to stdout"
- "Every log line has a `trace_id` so you can jump from any log to its full trace"

---

## Act 2: Inject Chaos (5 min)

### Enable latency injection on the worker

```bash
CHAOS_DELAY=true docker compose up -d worker
```

### What happens

- Worker now adds a 3-6 second delay on ~30% of requests
- API's `fetch()` call to worker blocks until the worker responds
- ~30% of end-to-end responses jump from ~200ms to 3-6 seconds
- P95 latency spikes dramatically on the dashboard

### Show the audience

1. **Service Overview dashboard** - watch it change in real-time:
   - **P95 Latency**: Both lines spike — worker to 3-6s, api follows since it waits on worker
   - **Request Rate**: Stays the same — loadgen keeps sending
   - **Error Rate %**: Stays low — requests are slow, not failing

2. **Find a slow trace** - Explore -> Tempo
   - Filter: Min Duration = `3s`
   - Open one of the slow traces
   - See the worker span is 3-6 seconds while api span matches
   - "The worker is slow, and the API is stuck waiting for it"

3. **Check worker logs** - Explore -> Loki
   - Query: `{service="worker"} |= "CHAOS"`
   - See `"msg":"CHAOS delay"` with `delay_ms` values (3000-6000)
   - "Here's our smoking gun - the worker is logging that it's deliberately delaying"

4. **Correlate: log -> trace**
   - From a CHAOS log line, click the `trace_id` derived field
   - Jump straight to the trace in Tempo
   - "One click from log to trace. This is the power of correlation."

---

## Act 3: Root Cause Analysis (3 min)

### Walk through the investigation as if it were real

> "We got paged: latency is spiking. Let's figure out what's going on."

1. **Start from metrics** (Service Overview dashboard)
   - "P95 latency is way up. But only on worker. API latency is up too because it depends on worker."

2. **Look at traces** (Explore -> Tempo)
   - "Let me find a slow request... here. The worker span took 5 seconds. That's our bottleneck."

3. **Check the logs** (Explore -> Loki)
   - `{service="worker"} |= "CHAOS"`
   - "There it is. The worker is logging 'CHAOS delay' on some requests. That's the root cause."

4. **Full story**:
   - "Metrics told us **something** was slow"
   - "Traces told us **where** it was slow - the worker"
   - "Logs told us **why** - a chaos delay was injected"

---

## Act 4: Resolution (2 min)

### Disable chaos

```bash
docker compose up -d worker
```

(Without `CHAOS_DELAY` set, it defaults to `false`.)

### Show recovery

- P95 latency drops back to normal within a minute
- New traces show fast worker spans again (~100-300ms)

### Wrap up

> "This is the three pillars of observability working together:
> **Metrics** for the big picture, **traces** for the request path,
> **logs** for the details. OpenTelemetry gives us all three from a
> single instrumentation layer."

---

## Useful Queries

### Prometheus (Explore -> Prometheus)

```promql
# Request rate by service
sum by (service_name) (rate(span_metrics_calls_total{span_kind="SPAN_KIND_SERVER"}[5m]))

# Error rate %
sum by (service_name) (rate(span_metrics_calls_total{span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m]))
/
sum by (service_name) (rate(span_metrics_calls_total{span_kind="SPAN_KIND_SERVER"}[5m]))

# P95 latency
histogram_quantile(0.95,
  sum by (service_name, le) (
    rate(span_metrics_duration_milliseconds_bucket{span_kind="SPAN_KIND_SERVER"}[5m])
  )
)
```

### Loki (Explore -> Loki)

```logql
# All logs (Promtail extracts service/level as labels)
{job="docker"}

# Filter by service
{service="api"}

# Only warn-level logs (CHAOS delays)
{service="worker", level="warn"}

# Chaos delay logs (text filter)
{service="worker"} |= "CHAOS"

# Specific trace
{job="docker"} |= "<paste-trace-id-here>"
```

### Tempo (Explore -> Tempo)

- Service Name: `api` or `worker`
- Min Duration: `3s` (to find slow traces during chaos)

---

## Ports Reference

| Service | URL |
|---|---|
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| API | http://localhost:8080 |
| Worker | http://localhost:8081 |
| OTel Collector (gRPC) | localhost:4317 |
| OTel Collector (HTTP) | localhost:4318 |
| OTel Collector (metrics) | http://localhost:8889/metrics |
| Loki | http://localhost:3100 |
| Tempo | http://localhost:3200 |

---

## Quick Commands

```bash
# Start everything
docker compose up -d --build

# Restart load generator (starts automatically, runs 5 min then exits)
docker compose up -d loadgen

# Enable chaos
CHAOS_DELAY=true docker compose up -d worker

# Disable chaos
docker compose up -d worker

# Tear down
docker compose down -v

# Check a single order manually
curl -s -X POST http://localhost:8080/order \
  -H "Content-Type: application/json" \
  -d '{"id":"manual-test","total":42}' | jq

# View worker logs live
docker compose logs -f worker

# Check OTel Collector metrics
curl -s http://localhost:8889/metrics | grep span_metrics
```
