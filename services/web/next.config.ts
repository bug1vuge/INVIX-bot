import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for a small Docker image.
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Images are already stored in the right size and served by the gateway
  // with long-lived cache headers; the built-in optimizer would keep a
  // per-instance disk cache, which we avoid to keep replicas stateless.
  images: { unoptimized: true },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Telegram Web opens Mini Apps in an iframe.
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org",
          },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
