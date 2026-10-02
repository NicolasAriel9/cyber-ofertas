import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // Emit product/index.html instead of product.html so direct loads and
  // refreshes of /product?id=... work on any static host.
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
