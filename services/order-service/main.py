import json
import logging
import os
import uuid
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Request
from opentelemetry import trace

app = FastAPI(title="Order Service")
tracer = trace.get_tracer("order-service")

INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8082")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8083")

# Structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("order-service")


def log_structured(level: str, message: str, **kwargs):
    span = trace.get_current_span()
    ctx = span.get_span_context()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "message": message,
        "service": "order-service",
        "trace_id": format(ctx.trace_id, "032x") if ctx.trace_id else "",
        "span_id": format(ctx.span_id, "016x") if ctx.span_id else "",
        **kwargs,
    }
    logger.info(json.dumps(entry))


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "order-service"}


@app.post("/orders")
async def create_order(request: Request):
    body = await request.json()
    order_id = str(uuid.uuid4())

    log_structured("info", "Processing new order", order_id=order_id, body=body)

    current_span = trace.get_current_span()
    current_span.set_attribute("order.id", order_id)

    # Step 1: Check inventory
    with tracer.start_as_current_span("check-inventory") as span:
        span.set_attribute("order.id", order_id)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{INVENTORY_SERVICE_URL}/check",
                    json={"order_id": order_id, "items": body.get("items", [])},
                    timeout=5.0,
                )
            if resp.status_code != 200:
                log_structured(
                    "error",
                    "Inventory check failed",
                    order_id=order_id,
                    status=resp.status_code,
                )
                raise HTTPException(
                    status_code=resp.status_code,
                    detail="Inventory check failed",
                )
            log_structured("info", "Inventory check passed", order_id=order_id)
        except httpx.RequestError as e:
            log_structured(
                "error",
                "Inventory service unavailable",
                order_id=order_id,
                error=str(e),
            )
            raise HTTPException(status_code=502, detail="Inventory service unavailable")

    # Step 2: Process payment (3-second timeout — key for chaos demo)
    with tracer.start_as_current_span("process-payment") as span:
        span.set_attribute("order.id", order_id)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{PAYMENT_SERVICE_URL}/process",
                    json={
                        "order_id": order_id,
                        "amount": body.get("total", 0),
                        "customer_id": body.get("customer_id", ""),
                    },
                    timeout=3.0,  # 3-second timeout — chaos causes this to fail
                )
            if resp.status_code != 200:
                log_structured(
                    "error",
                    "Payment processing failed",
                    order_id=order_id,
                    status=resp.status_code,
                )
                raise HTTPException(
                    status_code=resp.status_code,
                    detail="Payment processing failed",
                )
            log_structured("info", "Payment processed successfully", order_id=order_id)
        except httpx.ReadTimeout:
            log_structured(
                "error",
                "Payment service timeout after 3s",
                order_id=order_id,
            )
            raise HTTPException(
                status_code=504,
                detail="Payment service timeout",
            )
        except httpx.RequestError as e:
            log_structured(
                "error",
                "Payment service unavailable",
                order_id=order_id,
                error=str(e),
            )
            raise HTTPException(status_code=502, detail="Payment service unavailable")

    log_structured("info", "Order completed successfully", order_id=order_id)

    return {
        "order_id": order_id,
        "status": "completed",
        "message": "Order processed successfully",
    }
