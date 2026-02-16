import json
import logging
import os
import random
import time
from datetime import datetime

from fastapi import FastAPI, Request
from opentelemetry import trace

app = FastAPI(title="Payment Service")
tracer = trace.get_tracer("payment-service")

INJECT_LATENCY = os.getenv("INJECT_LATENCY", "false").lower() == "true"

# Structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("payment-service")


def log_structured(level: str, message: str, **kwargs):
    span = trace.get_current_span()
    ctx = span.get_span_context()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "message": message,
        "service": "payment-service",
        "trace_id": format(ctx.trace_id, "032x") if ctx.trace_id else "",
        "span_id": format(ctx.span_id, "016x") if ctx.span_id else "",
        **kwargs,
    }
    logger.info(json.dumps(entry))


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "payment-service"}


@app.post("/process")
async def process_payment(request: Request):
    body = await request.json()
    order_id = body.get("order_id", "unknown")
    amount = body.get("amount", 0)

    current_span = trace.get_current_span()
    current_span.set_attribute("order.id", order_id)
    current_span.set_attribute("payment.amount", float(amount))
    current_span.set_attribute("chaos.inject_latency", INJECT_LATENCY)

    log_structured(
        "info",
        "Processing payment",
        order_id=order_id,
        amount=amount,
        inject_latency=INJECT_LATENCY,
    )

    # Chaos injection: ~30% of requests get 5-10 second delay
    if INJECT_LATENCY and random.random() < 0.3:
        delay = random.uniform(5, 10)
        current_span.set_attribute("chaos.delayed", True)
        current_span.set_attribute("chaos.delay_seconds", delay)
        log_structured(
            "warn",
            "CHAOS: Injecting latency",
            order_id=order_id,
            delay_seconds=round(delay, 2),
        )
        time.sleep(delay)
    else:
        # Normal processing delay (100-500ms)
        delay = random.uniform(0.1, 0.5)
        current_span.set_attribute("chaos.delayed", False)
        time.sleep(delay)

    log_structured(
        "info",
        "Payment processed",
        order_id=order_id,
        amount=amount,
    )

    return {
        "order_id": order_id,
        "status": "approved",
        "transaction_id": f"txn-{order_id[:8]}",
    }
