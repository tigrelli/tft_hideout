"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { postLinkClickEvent } from "@/lib/api-client";
import type { ChatMessage } from "@/lib/use-chat-conversation";

// CHAT-07이 심는 `[이름](url)` 링크, CHAT-12 시스템 프롬프트 9번 규칙이 지시하는
// `- ` 목록까지만 파싱한다(prompt_assembly.py가 실제로 지시하는 서식이 이
// 두 가지뿐이라 전체 마크다운 파서는 여전히 과함). 처음엔 `**강조**`도 함께
// 파싱했었으나, 목록 항목에서 모델이 CHAT-06/07이 의존하는 작은따옴표 인용을
// 별표로 대체하면서 챔피언/조합 링크가 통째로 사라지는 회귀가 발견돼(2026-08-08
// PM 제보, CHAT-12 작업결과 참고) 강조 지시 자체를 프롬프트에서 제거했다 —
// 그래서 이 파서도 강조는 더 이상 다루지 않는다.
const LINK_PATTERN = /\[([^\]]+)\]\(([^)]+)\)/g;
// 토큰 사이에 항상 공백 1칸을 끼워 넣는 use-chat-conversation.ts의 재조합 방식
// 때문에("- 다음줄" 토큰 앞에 "이전줄\n" 토큰이 오면 그 사이에 공백이 끼어
// " - 다음줄"이 됨) 목록 판정 전에 줄 앞 공백을 허용해야 한다.
const BULLET_LINE_PATTERN = /^\s*[-*]\s+(.+)$/;

function renderInlineSegments(
  text: string,
  sessionId: string,
  keyPrefix: string,
): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  LINK_PATTERN.lastIndex = 0;
  let match = LINK_PATTERN.exec(text);
  while (match !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const [full, label, url] = match;
    parts.push(
      <Link
        key={`${keyPrefix}-link-${key++}`}
        href={url}
        className="cursor-pointer underline"
        onClick={() => {
          void postLinkClickEvent(sessionId, url);
        }}
      >
        {label}
      </Link>,
    );
    lastIndex = match.index + full.length;
    match = LINK_PATTERN.exec(text);
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

function renderAnswerText(text: string, sessionId: string): ReactNode[] {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let currentListItems: string[] = [];
  let blockKey = 0;

  const flushList = () => {
    if (currentListItems.length === 0) return;
    blocks.push(
      <ul key={`list-${blockKey++}`} className="list-disc space-y-1 pl-5">
        {currentListItems.map((item, itemIndex) => (
          <li key={itemIndex}>
            {renderInlineSegments(
              item,
              sessionId,
              `li-${blockKey}-${itemIndex}`,
            )}
          </li>
        ))}
      </ul>,
    );
    currentListItems = [];
  };

  lines.forEach((line, lineIndex) => {
    const bulletMatch = BULLET_LINE_PATTERN.exec(line);
    if (bulletMatch) {
      currentListItems.push(bulletMatch[1]);
      return;
    }
    flushList();
    const displayLine = lineIndex === 0 ? line : line.replace(/^ /, "");
    blocks.push(
      ...renderInlineSegments(displayLine, sessionId, `ln-${blockKey++}`),
    );
    if (lineIndex < lines.length - 1) {
      blocks.push("\n");
    }
  });
  flushList();

  return blocks;
}

// 첫 토큰이 오기 전(Render 콜드스타트·Groq 지연 등으로 느릴 수 있음, policies.md
// 9번)까지 빈 봇 말풍선만 떠 있어 응답이 멈춘 것처럼 보이던 문제 — 메신저에서
// 흔한 타이핑 점 3개 애니메이션으로 "생성 중"임을 표시한다.
function ChatTypingIndicator() {
  return (
    <div
      role="status"
      aria-label="답변 생성 중"
      className="flex gap-1 px-1 py-1"
    >
      {[0, 150, 300].map((delayMs) => (
        <span
          key={delayMs}
          aria-hidden="true"
          className="h-2 w-2 animate-bounce rounded-full bg-text-tertiary"
          style={{ animationDelay: `${delayMs}ms` }}
        />
      ))}
    </div>
  );
}

export function ChatMessageList({
  messages,
  sessionId,
}: {
  messages: ChatMessage[];
  sessionId: string;
}) {
  // 대화가 길어지면 새 메시지·스트리밍 토큰이 와도 스크롤이 따라 내려가지
  // 않아 매번 수동으로 내려야 하던 문제(PM 피드백) — 메시지 목록 맨 아래에
  // 빈 sentinel을 두고 messages가 바뀔 때마다(토큰 단위 업데이트 포함)
  // 그 위치로 스크롤한다.
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  return (
    <div
      role="log"
      aria-label="대화 내용"
      className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4"
    >
      {messages.length === 0 && (
        <p className="text-caption text-text-tertiary">
          궁금한 점을 물어보세요.
        </p>
      )}
      {messages.map((message) => (
        <div
          key={message.id}
          className={
            message.role === "user"
              ? "ml-auto max-w-[85%] wrap-break-word rounded-bubble bg-surface-user-bubble px-3 py-2 text-body text-text-primary"
              : "mr-auto max-w-[85%] whitespace-pre-wrap wrap-break-word rounded-bubble border border-border-default bg-surface-card px-3 py-2 text-body text-text-primary"
          }
        >
          {message.role === "bot" && message.text === "" ? (
            <ChatTypingIndicator />
          ) : message.role === "bot" ? (
            renderAnswerText(message.text, sessionId)
          ) : (
            message.text
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
