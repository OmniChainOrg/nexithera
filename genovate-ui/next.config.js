/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    typedRoutes: false,
  },
  // The Genovate API is consumed at runtime via NEXT_PUBLIC_API_URL.
  // No server-side rewrites are required for the dashboard foundation.
};

module.exports = nextConfig;
