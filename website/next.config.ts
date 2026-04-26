import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Locks module resolution to this project only
  experimental: {
    typedRoutes: false,
  },
  // Prevent Next from crawling outside this directory
  outputFileTracingRoot: __dirname,
};

export default nextConfig;