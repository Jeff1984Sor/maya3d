import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  transpilePackages: ["@print3d/shared"],
  poweredByHeader: false,
  reactStrictMode: true,
  // uploads de STL pelo painel (o padrão do Next é 1 MB); a API limita de novo (MAX_UPLOAD_MB)
  experimental: { serverActions: { bodySizeLimit: "50mb" } },
};

export default config;
