import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // SSR proxy: the browser only ever calls the frontend's own origin (`/api/*`),
  // and the Next.js server forwards those requests to the backend. `rewrites()`
  // runs when the server boots (`next start` loads this file at runtime), so
  // BACKEND_URL is resolved at runtime in the container — unlike NEXT_PUBLIC_*
  // values, which are inlined into the client bundle at build time and cannot
  // be re-pointed afterward (the Hostess "runtime resolution doesn't happen for
  // images" problem). The API can therefore stay on an internal-only URL.
  async rewrites() {
    const backendUrl = (
      process.env.BACKEND_URL ?? "http://localhost:8000"
    ).replace(/\/$/, "");
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
