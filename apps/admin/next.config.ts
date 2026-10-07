import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  transpilePackages: ["@print3d/shared"],
  poweredByHeader: false,
  reactStrictMode: true,
};

export default config;
