"use client";

import { useState } from "react";
import { ChatFollowupChips } from "@/components/chat-widget/chat-followup-chips";
import { ChatInput } from "@/components/chat-widget/chat-input";
import { ChatMessageList } from "@/components/chat-widget/chat-message-list";
import { useChatConversation } from "@/lib/use-chat-conversation";

// FE-09: 화면설계서 2.7 챗봇 위젯(전역 컴포넌트, 전용 URL 없음). 데스크톱/태블릿은
// 우하단 플로팅 패널(360×505, radius 10 — design-tokens.md), 모바일은 하단 고정
// 바 → 탭 시 전체화면 바텀시트로 전환한다(반응형 동작 표). layout.tsx가 `main`
// 바깥에 이 컴포넌트를 배치해 페이지 전환에도 대화 상태가 유지된다.
export function ChatWidget() {
  const [isExpanded, setIsExpanded] = useState(false);
  const { sessionId, messages, isSending, sendMessage, resetConversation } =
    useChatConversation();

  // CHAT-11: 후속질문칩은 항상 가장 최근 봇 답변에 종속(와이어프레임 예시와
  // 동일). 다음 메시지를 보내는 중에는 낡은 칩이 잠깐 보이지 않게 숨긴다.
  const lastBotMessage = [...messages].reverse().find((m) => m.role === "bot");
  const followupQuestions = isSending ? [] : (lastBotMessage?.followups ?? []);

  return (
    <>
      {isExpanded && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="챗봇"
          className="fixed inset-0 z-50 flex flex-col bg-surface-card md:inset-auto md:bottom-24 md:right-6 md:h-[505px] md:w-[360px] md:rounded-bubble md:border md:border-border-default md:shadow-lg"
        >
          <div className="flex items-center justify-between bg-primary px-4 py-3 text-text-on-brand md:rounded-t-bubble">
            <span className="text-body font-bold">TFT 챗봇</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label="새 대화"
                onClick={resetConversation}
                className="text-caption"
              >
                새 대화
              </button>
              <button
                type="button"
                aria-label="챗봇 접기"
                onClick={() => setIsExpanded(false)}
              >
                ✕
              </button>
            </div>
          </div>

          <ChatMessageList messages={messages} sessionId={sessionId} />
          <ChatFollowupChips
            questions={followupQuestions}
            onSelect={(question) => void sendMessage(question)}
          />
          <ChatInput
            isSending={isSending}
            onSend={(text) => void sendMessage(text)}
          />
        </div>
      )}

      {/* 태블릿/데스크톱: 우하단 원형 토글 버튼(항상 노출, collapsed/expanded 공용) */}
      <button
        type="button"
        aria-label={isExpanded ? "챗봇 닫기" : "챗봇 열기"}
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((prev) => !prev)}
        className="fixed bottom-4 right-4 z-40 hidden h-14 w-14 items-center justify-center rounded-full bg-primary text-2xl text-text-on-brand shadow-lg md:right-6 md:flex"
      >
        💬
      </button>

      {/* 모바일: collapsed 상태에서만 하단 고정 바 노출(expanded는 전체화면 시트).
          접근성 이름은 버튼 텍스트("무엇이든 물어보세요...")를 그대로 사용해
          위의 데스크톱 토글 버튼("챗봇 열기")과 겹치지 않게 한다. */}
      {!isExpanded && (
        <button
          type="button"
          aria-expanded={isExpanded}
          onClick={() => setIsExpanded(true)}
          className="fixed inset-x-0 bottom-0 z-40 flex items-center gap-2 border-t border-border-default bg-surface-card px-4 py-3 text-body text-text-tertiary md:hidden"
        >
          <span aria-hidden="true">💬</span>
          <span>무엇이든 물어보세요...</span>
        </button>
      )}
    </>
  );
}
