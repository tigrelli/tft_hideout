import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { streamChatMessage } from "@/lib/chat-stream";

// chat_stream.py의 build_sse_stream()이 실제로 보내는 와이어 포맷을 그대로
// 재현: 토큰 내부 개행은 "\n" -> "\\n"으로 이스케이프돼 있다(CHAT-12).
function mockSseResponse(tokens: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const token of tokens) {
        controller.enqueue(encoder.encode(`data: ${token}\n\n`));
      }
      controller.enqueue(encoder.encode("event: done\ndata: [DONE]\n\n"));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("streamChatMessage — CHAT-12 토큰 내부 개행 이스케이프 복원", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("토큰에 이스케이프된 \\n이 있으면 실제 개행 문자로 복원해서 onToken에 전달한다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponse(["손길\\n- 이즈리얼:", "아이템"]),
    );

    const received: string[] = [];
    await streamChatMessage("session-1", "질문", (token) => {
      received.push(token);
    });

    expect(received).toEqual(["손길\n- 이즈리얼:", "아이템"]);
  });

  it("이스케이프된 토큰이 SSE 이벤트 경계(\\n\\n)를 깨지 않고 온전히 전달된다", async () => {
    const fetchMock = vi.mocked(fetch);
    // 원문 개행을 그대로 실었다면 이벤트 구분이 깨져 두 번째 줄이 사라졌을
    // 케이스 — 이스케이프 덕분에 하나의 온전한 토큰으로 도착해야 한다.
    fetchMock.mockResolvedValue(mockSseResponse(["첫줄\\n둘째줄\\n셋째줄"]));

    const received: string[] = [];
    await streamChatMessage("session-1", "질문", (token) => {
      received.push(token);
    });

    expect(received).toEqual(["첫줄\n둘째줄\n셋째줄"]);
  });
});
