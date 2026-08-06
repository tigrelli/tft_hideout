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
      className="flex-1 space-y-3 overflow-y-auto p-4"
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
          {message.role === "bot"
            ? renderAnswerText(message.text, sessionId)
            : message.text}
        </div>
      ))}
    </div>
  );
}
