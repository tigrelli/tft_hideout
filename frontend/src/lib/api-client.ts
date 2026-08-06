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

// CHAT-07이 만든 상세 페이지 링크를 챗봇에서 클릭했을 때 전환율 계측용
// link_click_events에 적재한다(schema.md). KPI 계측 실패가 사용자의 실제
// 페이지 이동까지 막으면 안 되므로 실패는 조용히 무시한다.
export function postLinkClickEvent(
  sessionId: string,
  targetPage: string,
): Promise<void> {
  return fetch(`${API_BASE_URL}/api/v1/chat/events/link-click`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, target_page: targetPage }),
  })
    .then(() => undefined)
    .catch(() => undefined);
}
