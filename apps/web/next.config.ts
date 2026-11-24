import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.PHASE7_PROXY_TEST ? ".next-proxy-test" : ".next",
  typescript: {
    tsconfigPath: process.env.PHASE7_PROXY_TEST ? "tsconfig.proxy.json" : "tsconfig.json",
  },
  poweredByHeader: false,
  devIndicators: false,
  reactStrictMode: true,
  async rewrites() {
    const api = (process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/v1/:path*", destination: `${api}/api/v1/:path*` }];
  },
  experimental: {
    cpus: 1,
    webpackMemoryOptimizations: true,
    optimizePackageImports: ["lucide-react"],
    proxyClientMaxBodySize: "21mb",
    proxyTimeout: 190_000,
  },
};

export default nextConfig;
