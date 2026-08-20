// Theek Karo SLO load test (Phase 10, ROADMAP exit: p95 held under load)
//
// Targets the compose API through its host port (8001). Thresholds encode the
// SLOs in docs/SLOs.md: p95 latency < 500ms on civic/report reads; error rate
// < 1% (4xx allowed only for the known-missing paths used to exercise 404s).
// Run: k6 run infra/k6/slo-smoke.js
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const fiveXx = new Rate("tk_api_5xx_rate");

export const options = {
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: 10,
      duration: "30s",
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<500"],
    tk_api_5xx_rate: ["rate<0.01"],
    checks: ["rate>0.99"],
  },
};

const BASE = __ENV.TK_API_URL || "http://127.0.0.1:8001";
const CATEGORY = "school"; // seeded category (fixed slug — init context cannot do I/O)

export default function () {
  fiveXx.add(is5xx(http.get(`${BASE}/api/v1/civic/categories`)));
  const civic = http.get(`${BASE}/api/v1/civic/categories`);
  check(civic, { "categories 200": (r) => r.status === 200 });

  const reports = http.get(`${BASE}/api/v1/reports?limit=20`);
  check(reports, { "reports 200": (r) => r.status === 200 });

  const detail = http.get(`${BASE}/api/v1/civic/categories/${CATEGORY}`);
  check(detail, { "category detail 200": (r) => r.status === 200 });

  const gis = http.get(
    `${BASE}/api/v1/gis/boundaries?kind=state&lat=26.9124&lng=75.7873`,
  );
  check(gis, { "gis tree 200": (r) => r.status === 200 });

  const missing = http.get(`${BASE}/api/v1/reports/00000000-0000-0000-0000-000000000000`);
  check(missing, { "missing report 404": (r) => r.status === 404 });

  sleep(0.2);
}

function is5xx(response) {
  return response.status >= 500;
}