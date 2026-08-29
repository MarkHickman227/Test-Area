import type { NextConfig } from "next";

const api = process.env.API_BASE_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${api}/v1/:path*` },
      { source: "/health", destination: `${api}/health` },
    ];
  },
};

export default nextConfig;
