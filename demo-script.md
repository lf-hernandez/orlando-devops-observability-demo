# Observability Demo — Live Demo Script

## Pre-Demo Setup

```bash
# Start the full stack
docker compose up -d --build

# Wait for services to be healthy (~30-60 seconds)
docker compose ps

# Verify Grafana is up
open http://localhost:3000  # admin/admin (or anonymous access)
```

## Act 1: The Happy Path (5 min)

### Start load generation
```bash
docker compose run --rm loadgen
# Or run k6 locally:
# k6 run loadgen/script.js
```

### Show the audience
1. **Grafana → Service Overview dashboard**
   - `http://localhost:3000/d/service-overview`
   - Point out: all services have steady request rate, near-zero errors
   - Latency is low and stable (p95 < 500ms)

2. **Explore a single trace**
   - Go to Explore → Tempo
   - Pick any recent trace
   - Walk through the 4 spans: `api-gateway → order-service → inventory-service + payment-service`
   - "This is the full journey of an order"

3. **Show log correlation**
   - Click a span → "Logs for this span"
   - Show structured JSON logs with `trace_id` field
   - "Every log line is connected to its trace"

### Key talking points
- OTel Collector as the single pipeline — apps don't know about Prometheus/Loki/Tempo
- Python auto-instrumentation: zero code changes for spans
- Go explicit instrumentation: full control over span attributes

## Act 2: Inject Chaos (5 min)

### Enable the latency injection
```bash
INJECT_LATENCY=true docker compose up -d payment-service
```

### What happens
- ~30% of payment requests now take 5-10 seconds
- Order Service has a 3-second timeout on payment calls
- Those requests fail with 504 Gateway Timeout
- Error rate climbs above 5%

### Show the audience
1. **Service Overview dashboard** — watch error rate climb in real-time
   - Error Rate % stat panel goes from green → yellow → red
   - Request rate stays the same (load gen keeps sending)
   - p95 latency spikes for order-service

2. **Alert fires** after 2 minutes
   - "Order Error Rate High" alert
   - Show the alert rule and its threshold

## Act 3: Root Cause Analysis (5 min)

### Walk through the investigation
1. **Start from the alert**
   - "We got paged. Error rate > 5% on order-service. Let's investigate."

2. **Check the Order Service Detail dashboard**
   - `http://localhost:3000/d/order-service-detail`
   - Error rate gauge shows the problem
   - Downstream latency panel: payment-service p95 is way up

3. **Find a failing trace**
   - Explore → Tempo → filter by `service_name=order-service` and status=error
   - Open a failed trace
   - See: `order-service → process-payment` span shows timeout after 3s
   - The `payment-service` span (if it completed) shows 5-10s duration
   - "The payment service is slow, and order service times out waiting"

4. **Check payment service logs**
   - Explore → Loki → `{exporter="OTLP"} |= "CHAOS" | json`
   - Find log lines: `"CHAOS: Injecting latency"` with `delay_seconds`
   - "Here's our root cause — artificial latency injection"

5. **Correlate log → trace**
   - Click the TraceID link in a log line
   - Jump directly to the full trace
   - "Logs, metrics, and traces — all connected"

## Act 4: Resolution (2 min)

### Disable chaos
```bash
docker compose up -d payment-service
```

### Show recovery
- Error rate drops back to 0
- Latency returns to normal
- Alert resolves

### Wrap up
- "This is the power of correlated observability"
- "Metrics told us WHAT was wrong (error rate)"
- "Traces told us WHERE it was wrong (payment service timeout)"
- "Logs told us WHY (chaos injection / the specific cause)"

## Useful Queries

### Prometheus (Explore)
```promql
# Error rate percentage
sum(rate(span_metrics_calls_total{service_name="order-service", status_code="STATUS_CODE_ERROR"}[5m]))
/
sum(rate(span_metrics_calls_total{service_name="order-service"}[5m]))

# p95 latency
histogram_quantile(0.95,
  sum by (le) (rate(span_metrics_duration_milliseconds_bucket{service_name="order-service"}[5m]))
)
```

### Loki (Explore)
```logql
# All order-service logs
{exporter="OTLP"} |= "order-service" | json

# Only errors
{exporter="OTLP"} |= "order-service" |= "error" | json

# Chaos injection logs
{exporter="OTLP"} |= "CHAOS" | json

# Payment timeouts
{exporter="OTLP"} |= "timeout" | json
```

### Tempo (Explore)
- Service Name: `order-service`
- Status: `error`
- Min Duration: `3s` (to find timeout traces)

## Ports Reference
| Service | Port |
|---|---|
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| API Gateway | http://localhost:8080 |
| OTel Collector (gRPC) | localhost:4317 |
| OTel Collector (HTTP) | localhost:4318 |
| Loki | http://localhost:3100 |
| Tempo | http://localhost:3200 |
