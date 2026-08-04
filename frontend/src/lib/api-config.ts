// 정적 export(FE-01 결정, 서버 런타임 없음)라 빌드 시점에 값이 고정된다.
// 로컬 개발 시 NEXT_PUBLIC_API_BASE_URL로 override 가능(예: http://localhost:8000).
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "https://tft-hideout-backend.onrender.com";
