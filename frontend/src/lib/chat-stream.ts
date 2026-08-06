import { API_BASE_URL } from "@/lib/api-config";

// CHAT-05/API-09가 만드는 SSE 스트림(`data: <token>\n\n` 반복 + 마지막
// `event: done\ndata: [DONE]\n\n`)을 파싱한다. fetchJson은 response.json()을
// 가정하므로 스트리밍 응답에는 쓸 수 없어 별도 함수로 분리한다.
export async function streamChatMessage(
  sessionId: string,
  message: string,
  onToken: (token: string) => void,
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
      if (dataLine) {
        onToken(dataLine.slice("data: ".length));
      }
    }
  }
}
