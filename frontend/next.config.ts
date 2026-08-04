import type { NextConfig } from "next";

// Cloudflare Workers([assets] 전용, SET-06/SET-07 결정)에 정적 파일로 배포하므로
// 서버 런타임 없이 빌드 시점에 완전히 정적 HTML로 export한다.
const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: import.meta.dirname,
  },
};

export default nextConfig;
