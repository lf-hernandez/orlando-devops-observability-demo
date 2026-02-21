import "./tracing.js";

import express, { type Request, type Response } from "express";
import { context, trace } from "@opentelemetry/api";

const app = express();
app.use(express.json());

const workerUrl = process.env.WORKER_URL || "http://localhost:8081";

function log(level: string, msg: string, extra: Record<string, unknown> = {}) {
  const span = trace.getSpan(context.active());
  const spanCtx = span ? span.spanContext() : null;
  const payload = {
    timestamp: new Date().toISOString(),
    level,
    service: "api",
    msg,
    trace_id: spanCtx ? spanCtx.traceId : "",
    span_id: spanCtx ? spanCtx.spanId : "",
    ...extra
  };
  console.log(JSON.stringify(payload));
}

app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok", service: "api" });
});

app.post("/order", async (req: Request, res: Response) => {
  const order = (req.body as Record<string, unknown>) || {};
  const orderId = typeof order.id === "string" ? order.id : "unknown";
  log("info", "received order", { order_id: orderId });

  try {
    const response = await fetch(`${workerUrl}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(order)
    });

    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    log("error", "worker request failed", { error: String(err) });
    res.status(502).json({ error: "worker unavailable" });
  }
});

const port = 8080;
app.listen(port, () => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: "info",
    service: "api",
    msg: `listening on ${port}`
  }));
});
