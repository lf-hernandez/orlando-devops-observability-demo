import http from "k6/http";
import { check, sleep } from "k6";
import { randomIntBetween } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

export const options = {
  vus: 5,
  duration: "5m",
  thresholds: {
    http_req_duration: ["p(95)<5000"],
  },
};

const customers = [
  "cust-001",
  "cust-002",
  "cust-003",
  "cust-004",
  "cust-005",
];

const products = [
  { id: "prod-laptop", name: "Laptop", price: 999.99 },
  { id: "prod-mouse", name: "Mouse", price: 29.99 },
  { id: "prod-keyboard", name: "Keyboard", price: 79.99 },
  { id: "prod-monitor", name: "Monitor", price: 449.99 },
  { id: "prod-headset", name: "Headset", price: 149.99 },
];

export default function () {
  const customer = customers[randomIntBetween(0, customers.length - 1)];
  const numItems = randomIntBetween(1, 3);
  const items = [];
  let total = 0;

  for (let i = 0; i < numItems; i++) {
    const product = products[randomIntBetween(0, products.length - 1)];
    const qty = randomIntBetween(1, 5);
    items.push({
      product_id: product.id,
      name: product.name,
      quantity: qty,
      price: product.price,
    });
    total += product.price * qty;
  }

  const payload = JSON.stringify({
    customer_id: customer,
    items: items,
    total: Math.round(total * 100) / 100,
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  const res = http.post("http://api-gateway:8080/api/orders", payload, params);

  check(res, {
    "status is 200": (r) => r.status === 200,
    "has order_id": (r) => {
      try {
        return JSON.parse(r.body).order_id !== undefined;
      } catch {
        return false;
      }
    },
  });

  sleep(randomIntBetween(1, 3));
}
