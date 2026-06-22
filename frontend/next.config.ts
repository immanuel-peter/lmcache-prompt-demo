import type { NextConfig } from "next";

// API requests are proxied to the backend by a route handler at runtime
// (app/api/[...path]/route.ts), which reads BACKEND_URL per request. We
// deliberately do NOT use next.config `rewrites()` for this: its destination is
// evaluated at build time and frozen into the routes manifest, so it cannot be
// re-pointed at runtime (the Hostess "no runtime resolution for images" problem).
const nextConfig: NextConfig = {};

export default nextConfig;
