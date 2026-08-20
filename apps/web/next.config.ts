import type { NextConfig } from "next";

const API_UPSTREAM = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

const SECURITY_HEADERS = [
  // Content-Security-Policy (Step 14). Next.js App Router injects an inline
  // hydration-bootstrap script and inline styles, so script-src/style-src
  // allow 'unsafe-inline'; connect-src covers the proxied API upstream.
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      `connect-src 'self' ${API_UPSTREAM.split("//")[1]?.split("/")[0] ?? "localhost"}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(self)",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: SECURITY_HEADERS,
      },
    ];
  },
  async rewrites() {
    // dev/self-host stable contract: the web talks to /api/v1, Next proxies to
    // the tk_api service (compose host port 8001).
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_UPSTREAM}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;