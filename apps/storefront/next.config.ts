import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone", // imagem Docker enxuta
  // Monorepo: o trace precisa enxergar a raiz para incluir packages/shared no standalone.
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  transpilePackages: ["@print3d/shared"],
  poweredByHeader: false,
  reactStrictMode: true,
};

export default config;
