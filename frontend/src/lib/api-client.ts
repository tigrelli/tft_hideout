import { API_BASE_URL } from "@/lib/api-config";

// 공용 데이터 fetching 유틸(CLAUDE.md 10.1) — 컴포넌트가 각자 fetch를 직접 호출하지
// 않고 이 함수를 통해서만 백엔드 API를 호출한다.
export async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`API 요청 실패(${response.status}): ${path}`);
  }
  return (await response.json()) as T;
}
