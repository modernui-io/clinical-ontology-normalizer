import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: "standalone",

  // Allow backend proxy to handle long-running requests (graph build, NLP extraction)
  experimental: {
    proxyTimeout: 120_000, // 120 seconds (default is 30s)
  },

  // API proxy to backend service
  // Proxies /api/v1/* from browser to backend at /api/v1/*
  // Uses BACKEND_URL (server-side only) for Docker internal networking
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8080";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
