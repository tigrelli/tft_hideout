"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { postLinkClickEvent } from "@/lib/api-client";
import type { ChatMessage } from "@/lib/use-chat-conversation";

// CHAT-07이 답변 텍스트에 심어주는 `[이름](url)` 마크다운 링크만 파싱한다
// (프롬프트가 다른 마크다운 문법을 지시하지 않으므로 전체 마크다운 파서는
// 불필요, prompt_assembly.py 참고).
const LINK_PATTERN = /\[([^\]]+)\]\(([^)]+)\)/g;

function renderAnswerText(text: string, sessionId: string): ReactNode[] {
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
        key={`link-${key++}`}
        href={url}
        className="underline"
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
              ? "ml-auto max-w-[85%] rounded-bubble bg-surface-user-bubble px-3 py-2 text-body text-text-primary"
              : "mr-auto max-w-[85%] rounded-bubble border border-border-default bg-surface-card px-3 py-2 text-body text-text-primary"
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
    </div>
  );
}
