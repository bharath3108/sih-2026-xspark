import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Playwright (and some local network setups) load the dev server via
  // 127.0.0.1 rather than localhost; Next 16 blocks cross-origin dev
  // requests (HMR, RSC payloads) by default unless the origin is allowlisted.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
