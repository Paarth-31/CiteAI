import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  typedRoutes: false,
  // Prevent Next from crawling outside this directory
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
