import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: "standalone",

  // Allow backend proxy to handle long-running requests (graph build, NLP extraction)
  experimental: {
    proxyTimeout: 120_000, // 120 seconds (default is 30s)
  },

  // API proxy to backend service
  // Proxies /api/* from browser to backend at /api/v1/*
  // Uses BACKEND_URL for server-side (Docker internal), NEXT_PUBLIC_API_URL for fallback
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
