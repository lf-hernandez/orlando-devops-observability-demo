import "./tracing.js";

import express, { type Request, type Response } from "express";
import { context, trace } from "@opentelemetry/api";

const app = express();
app.use(express.json());

const chaosEnabled = (process.env.CHAOS_DELAY || "false").toLowerCase() === "true";

function log(level: string, msg: string, extra: Record<string, unknown> = {}) {
  const span = trace.getSpan(context.active());
  const spanCtx = span ? span.spanContext() : null;
  const payload = {
    timestamp: new Date().toISOString(),
    level,
    service: "worker",
    msg,
    trace_id: spanCtx ? spanCtx.traceId : "",
    span_id: spanCtx ? spanCtx.spanId : "",
    ...extra
  };
  console.log(JSON.stringify(payload));
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok", service: "worker" });
});

app.post("/process", async (req: Request, res: Response) => {
  const order = (req.body as Record<string, unknown>) || {};
  const orderId = typeof order.id === "string" ? order.id : "unknown";

  if (chaosEnabled && Math.random() < 0.3) {
    const delayMs = 3000 + Math.floor(Math.random() * 3000);
    log("warn", "CHAOS delay", { delay_ms: delayMs });
    await sleep(delayMs);
  } else {
    await sleep(100 + Math.floor(Math.random() * 200));
  }

  log("info", "processed order", { order_id: orderId });
  res.json({ status: "ok", processed: true });
});

const port = 8081;
app.listen(port, () => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: "info",
    service: "worker",
    msg: `listening on ${port}`
  }));
});
