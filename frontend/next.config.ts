import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        // WebSocket proxy is handled via the dev server middleware below.
        // The rewrites entry below is a fallback for HTTP upgrade requests.
        source: "/ws",
        destination: `${BACKEND_URL}/ws`,
      },
    ];
  },
};

export default nextConfig;
