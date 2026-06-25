import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable React Strict Mode's dev-only double-mount. The remount tears down
  // and recreates DOM nodes, which restarts every CSS mount animation
  // (animate-fade-in, stagger-children, recharts) and re-fires each page's
  // data-fetching effect — the cause of the flicker + duplicate API calls on
  // page load. This only affects development; production never double-mounts.
  reactStrictMode: false,
};

export default nextConfig;
