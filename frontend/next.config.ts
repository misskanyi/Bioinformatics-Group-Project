import type { NextConfig } from "next";

// The browser talks to /api/* on the Next.js origin; requests are proxied to
// the FastAPI backend so no CORS configuration is needed in development.
// In production (Vercel) set BACKEND_URL to the public Render URL, e.g.
// https://pet-explorer-api.onrender.com (no trailing slash, no /api). The
// value is read at build time, so redeploy after changing it.
const configured = process.env.BACKEND_URL?.trim().replace(/\/+$/, "");
if (!configured && process.env.VERCEL) {
  throw new Error("BACKEND_URL is not set: add the Render API URL as a Vercel environment variable and redeploy.");
}
const backend = configured || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
