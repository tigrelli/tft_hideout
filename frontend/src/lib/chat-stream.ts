import { API_BASE_URL } from "@/lib/api-config";

// CHAT-05/API-09가 만드는 SSE 스트림(`data: <token>\n\n` 반복 + 마지막
// `event: done\ndata: [DONE]\n\n`)을 파싱한다. fetchJson은 response.json()을
// 가정하므로 스트리밍 응답에는 쓸 수 없어 별도 함수로 분리한다.
//
// CHAT-11: 토큰 스트림이 끝나면 `event: followups\ndata: [...]\n\n`가
// 한 번(있을 때만) 더 올 수 있다. onFollowups는 선택 콜백이라 안 넘겨도
// 기존 호출부(onToken만 쓰는 코드)는 그대로 동작한다.
//
// CHAT-12: 토큰 내부 개행은 `chat_stream.py`의 `build_sse_stream()`이
// `\n` -> `\\n`으로 이스케이프해서 보낸다(원문 개행을 그대로 실으면 아래
// "\n\n" 단위 이벤트 구분과 섞여 그 줄 이후 내용이 통째로 사라지는 문제가
// 있었음, CHAT-12 작업결과 참고) — 토큰 데이터만 여기서 원래 문자로 되돌린다
// (followups JSON은 이스케이프 대상이 아니라 그대로 둔다).
export async function streamChatMessage(
  sessionId: string,
  message: string,
  onToken: (token: string) => void,
  onFollowups?: (questions: string[]) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`API 요청 실패(${response.status}): /api/v1/chat/message`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      if (event.startsWith("event: done")) {
        return;
      }
      const dataLine = event
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!dataLine) {
        continue;
      }
      const data = dataLine.slice("data: ".length);
      if (event.startsWith("event: followups")) {
        if (onFollowups) {
          try {
            onFollowups(JSON.parse(data) as string[]);
          } catch {
            // 후속질문 파싱 실패는 본 답변 스트리밍에 영향을 주지 않고 무시한다.
          }
        }
        continue;
      }
      onToken(data.replace(/\\n/g, "\n"));
    }
  }
}
