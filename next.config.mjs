/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Docker builds set NEXT_OUTPUT=standalone (see Dockerfile.web); Vercel uses its default output.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // API routes read these at runtime; make sure serverless bundles include them.
  outputFileTracingIncludes: {
    "/api/**/*": ["./data/processed/catalog.json", "./data/processed/catalog_meta.json", "./config/engine.json"],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "img-src 'self' https://m.media-amazon.com data:",
              "style-src 'self' 'unsafe-inline'",
              "script-src 'self'" + (process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""),
              "connect-src 'self'",
              "font-src 'self'",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
