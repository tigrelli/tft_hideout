import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatWidget } from "@/components/chat-widget/chat-widget";

// CHAT-05/API-09 SSE 포맷(chat_stream.py build_sse_stream) 그대로 재현한 mock
// 스트림: `data: <token>\n\n` 반복 후 `event: done\ndata: [DONE]\n\n`.
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

describe("ChatWidget — FE-09", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // WBS FE-09 테스트 요구사항 1: collapsed/expanded 상태 전환
  it("토글 버튼을 누르면 collapsed -> expanded로 전환되고 다시 누르면 접힌다", async () => {
    const user = userEvent.setup();
    render(<ChatWidget />);

    expect(
      screen.queryByRole("dialog", { name: "챗봇" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));
    expect(screen.getByRole("dialog", { name: "챗봇" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "챗봇 접기" }));
    expect(
      screen.queryByRole("dialog", { name: "챗봇" }),
    ).not.toBeInTheDocument();
  });

  // WBS FE-09 테스트 요구사항 2: 모바일 바텀시트 전환
  it("모바일 하단 고정 바를 탭하면 expanded 패널(바텀시트)이 열리고, 열린 동안 하단 바는 사라진다", async () => {
    const user = userEvent.setup();
    render(<ChatWidget />);

    const mobileBar = screen.getByRole("button", {
      name: "무엇이든 물어보세요...",
    });
    expect(mobileBar.className).toContain("md:hidden");

    await user.click(mobileBar);

    const panel = screen.getByRole("dialog", { name: "챗봇" });
    expect(panel.className).toContain("fixed inset-0");
    expect(panel.className).toContain("md:inset-auto");
    expect(
      screen.queryByRole("button", { name: "무엇이든 물어보세요..." }),
    ).not.toBeInTheDocument();
  });

  // WBS FE-09 테스트 요구사항 3: mock SSE 스트림 렌더링 테스트
  it("메시지를 보내면 mock SSE 스트림 토큰이 순차적으로 렌더링된다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponse(["안녕하세요,", "18.1", "패치", "기준입니다."]),
    );

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "지금 메타 알려줘");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    expect(await screen.findByText("지금 메타 알려줘")).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText("안녕하세요, 18.1 패치 기준입니다."),
      ).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/chat/message"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("답변에 포함된 [이름](url) 링크를 클릭 가능한 상세 페이지 링크로 렌더링한다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponse(["[아이오니아", "마법사](/comps?id=1)", "추천합니다."]),
    );

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "조합 추천해줘");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    const link = await screen.findByRole("link", { name: "아이오니아 마법사" });
    expect(link).toHaveAttribute("href", "/comps?id=1");
  });
});

// CHAT-05/API-09 SSE 포맷에 CHAT-11의 `event: followups\ndata: [...]\n\n`을
// done 이벤트 직전에 추가한 mock 스트림.
function mockSseResponseWithFollowups(
  tokens: string[],
  followups: string[],
): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const token of tokens) {
        controller.enqueue(encoder.encode(`data: ${token}\n\n`));
      }
      controller.enqueue(
        encoder.encode(
          `event: followups\ndata: ${JSON.stringify(followups)}\n\n`,
        ),
      );
      controller.enqueue(encoder.encode("event: done\ndata: [DONE]\n\n"));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("ChatWidget — CHAT-11 후속질문 동적 생성", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // WBS CHAT-11 테스트 요구사항: followups 이벤트 포함 mock SSE로 동적 칩 렌더링,
  // 칩 클릭 시 해당 질문이 전송되는지 테스트
  it("event: followups가 오면 답변 아래에 동적 칩이 렌더링되고, 칩을 클릭하면 그 질문이 그대로 전송된다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponseWithFollowups(
        ["1티어는", "'아이오니아", "마법사'입니다."],
        ["그 조합에 어울리는 증강체는?", "다른 S티어 조합도 알려줘"],
      ),
    );

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "지금 1티어 조합 뭐야?");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    const chip = await screen.findByRole("button", {
      name: "그 조합에 어울리는 증강체는?",
    });
    expect(
      screen.getByRole("button", { name: "다른 S티어 조합도 알려줘" }),
    ).toBeInTheDocument();

    await user.click(chip);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenLastCalledWith(
        expect.stringContaining("/api/v1/chat/message"),
        expect.objectContaining({
          body: expect.stringContaining(
            "그 조합에 어울리는 증강체는?",
          ) as string,
        }),
      );
    });
  });

  it("followups 이벤트가 없으면(빈 목록) 후속질문 칩이 렌더링되지 않는다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(mockSseResponse(["안녕하세요."]));

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "안녕");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    await screen.findByText("안녕하세요.");
    expect(screen.queryByLabelText("추천 질문")).not.toBeInTheDocument();
  });
});
