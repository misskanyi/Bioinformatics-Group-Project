import type { NextConfig } from "next";

// The browser talks to /api/* on the Next.js origin; requests are proxied to
// the FastAPI backend so no CORS configuration is needed in development.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
