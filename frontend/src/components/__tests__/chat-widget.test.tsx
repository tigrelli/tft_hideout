import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
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

// 첫 토큰 전송을 delayMs만큼 늦춰 "응답 대기 중" 상태를 재현하는 mock 스트림
// (Render 콜드스타트·Groq 지연 재현 목적).
function mockSseResponseDelayed(tokens: string[], delayMs: number): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
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
      name: "TFT에 관한 모든 질문, AI에게 물어보세요",
    });
    expect(mobileBar.className).toContain("md:hidden");

    await user.click(mobileBar);

    const panel = screen.getByRole("dialog", { name: "챗봇" });
    expect(panel.className).toContain("fixed inset-0");
    expect(panel.className).toContain("md:inset-auto");
    expect(
      screen.queryByRole("button", {
        name: "TFT에 관한 모든 질문, AI에게 물어보세요",
      }),
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

  // 응답이 느릴 때(Render 콜드스타트 등) 빈 말풍선만 떠 있어 멈춘 것처럼 보이던
  // 문제 — PM 요청으로 첫 토큰 전까지 타이핑 인디케이터를 추가.
  it("첫 토큰이 오기 전까지 타이핑 인디케이터가 보이고, 토큰이 오면 사라진다", async () => {
    const fetchMock = vi.mocked(fetch);
    // 2026-08-18: CI에서 간헐적으로 실패 발견(로컬 반복 실행 5/5는 항상 통과) —
    // 컴포넌트 로직 자체는 동기적이라(빈 봇 메시지가 클릭과 같은 틱에 즉시
    // 추가됨, chat-message-list.tsx 참고) 타이밍 버그가 아니라, 부하가 큰 CI
    // 러너에서 실제 타이머(50ms)와 waitFor의 폴링 타이머가 같은 매크로태스크로
    // 뭉쳐 처리되면서 "표시→소멸"이 폴링 사이로 통째로 묻히는 것으로 추정.
    // 딜레이를 크게(300ms) 늘려 이벤트 루프 혼잡과 무관하게 여유를 확보한다.
    fetchMock.mockResolvedValue(mockSseResponseDelayed(["안녕하세요."], 300));

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "안녕");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    expect(
      await screen.findByRole("status", { name: "답변 생성 중" }),
    ).toBeInTheDocument();

    await screen.findByText("안녕하세요.");
    expect(
      screen.queryByRole("status", { name: "답변 생성 중" }),
    ).not.toBeInTheDocument();
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

describe("ChatWidget — CHAT-12 답변 마크다운 서식 렌더링", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // WBS CHAT-12 테스트 요구사항: '- ' 접두 줄이 <ul><li> 목록으로 렌더링되는지 확인.
  // 토큰의 "\\n"은 chat_stream.py가 CHAT-12에서 이스케이프해 보내는 실제 SSE
  // 와이어 포맷 그대로(원문 개행이 아님) — chat-stream.ts가 수신 시 실제
  // 개행으로 되돌린다(chat-stream.test.ts 참고).
  it("'- '로 시작하는 줄들이 목록(ul/li)으로 렌더링된다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponse([
        "빌드를 안내드릴게요.\\n",
        "- 이즈리얼: 붉은 덩굴정령\\n",
        "- 자야: 무한의 대검",
      ]),
    );

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "아이템 추천해줘");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    const list = await screen.findByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("이즈리얼: 붉은 덩굴정령");
    expect(items[1]).toHaveTextContent("자야: 무한의 대검");
  });

  // 회귀 방지(2026-08-08 PM 제보): 목록 항목 안의 `[이름](url)` 링크가
  // CHAT-07이 만든 그대로 클릭 가능한 링크로 렌더링돼야 한다 — 한때 시스템
  // 프롬프트가 목록 항목에 "**강조**"도 함께 지시했는데, 모델이 CHAT-06/07이
  // 의존하는 작은따옴표 인용 대신 별표를 쓰면서 링크 자체가 생성되지 않는
  // 회귀가 있었다(원인은 백엔드 프롬프트에서 제거, 여기서는 프론트가 목록
  // 항목 안의 링크를 정상적으로 렌더링하는지 확인).
  it("목록 항목 안의 링크도 <li> 안에서 정상적으로 렌더링된다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponse([
        "빌드를 안내드릴게요.\\n",
        "- [이즈리얼](/items/builds?champion_id=1): 붉은 덩굴정령",
      ]),
    );

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "아이템 추천해줘");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    const list = await screen.findByRole("list");
    const link = within(list).getByRole("link", { name: "이즈리얼" });
    expect(link).toHaveAttribute("href", "/items/builds?champion_id=1");
  });

  // 강조(**) 파싱은 위 회귀 때문에 프론트에서도 의도적으로 지원하지 않는다
  // (prompt_assembly.py가 더 이상 지시하지 않음) — 원문 별표가 그대로 보이는
  // 것이 현재 기대 동작임을 명시해 향후 재도입 시 이 테스트가 먼저 걸리게 한다.
  it("'**텍스트**'는 특별히 처리하지 않고 원문 그대로 보여준다", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      mockSseResponse(["코어 아이템은 ", "**쇼진의 창**", "입니다."]),
    );

    const user = userEvent.setup();
    render(<ChatWidget />);
    await user.click(screen.getByRole("button", { name: "챗봇 열기" }));

    const input = screen.getByRole("textbox", { name: "챗봇 메시지 입력" });
    await user.type(input, "코어 아이템 알려줘");
    await user.click(screen.getByRole("button", { name: "메시지 전송" }));

    await screen.findByText("코어 아이템은 **쇼진의 창** 입니다.");
    expect(screen.queryByRole("strong")).not.toBeInTheDocument();
  });
});
