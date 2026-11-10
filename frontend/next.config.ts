import type { NextConfig } from "next";

// Local sharing (ngrok): set BACKEND_URL=http://127.0.0.1:8000 and NEXT_PUBLIC_API_URL=/api,
// then /api/* is forwarded to the local backend, so one public link serves app + API.
// On Vercel, vercel.json already routes /api to the backend service.
const backendUrl = process.env.BACKEND_URL;

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // tunnels used to share the dev server (ngrok)
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok-free.dev", "*.ngrok.app", "*.ngrok.io"],
  async rewrites() {
    return backendUrl ? [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }] : [];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
