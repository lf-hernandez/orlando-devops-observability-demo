const durationMs = (Number(process.env.DURATION_SEC || 300)) * 1000;
const intervalMs = Number(process.env.INTERVAL_MS || 500);
const apiUrl = process.env.API_URL || "http://api:8080/order";

function randomId() {
  return Math.random().toString(36).slice(2, 10);
}

async function sendOrder() {
  const payload = {
    id: `order-${randomId()}`,
    total: Math.floor(Math.random() * 200) + 20
  };

  try {
    const res = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    await res.json().catch(() => undefined);
  } catch (err) {
    // ignore
  }
}

const start = Date.now();
const timer = setInterval(() => {
  if (Date.now() - start > durationMs) {
    clearInterval(timer);
    process.exit(0);
  }
  sendOrder();
}, intervalMs);

console.log(`loadgen: sending to ${apiUrl} for ${durationMs / 1000}s`);
