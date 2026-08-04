"use client";

import { useState } from "react";

// 화면설계서 2.1 ChatWidgetToggle `chat-toggle`(collapsed 상태만 정의) — 전역
// 컴포넌트(glossary.md "챗봇 위젯: 없음(전역), 전용 URL 없음"). 실제 대화 UI는
// FE-09에서 구현하고, 여기서는 화면 우하단 슬롯 배치와 펼침/닫힘 토글, 준비중
// 안내까지만 담당한다.
export function ChatWidgetToggle() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <>
      {isExpanded && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="챗봇"
          className="fixed bottom-24 right-4 z-40 flex h-[360px] w-[320px] flex-col rounded-bubble border border-border-default bg-surface-card shadow-lg md:right-6 md:h-[480px] md:w-[360px]"
        >
          <div className="flex items-center justify-between rounded-t-bubble bg-primary px-4 py-3 text-text-on-brand">
            <span className="text-body font-bold">TFT 챗봇</span>
            <button
              type="button"
              aria-label="챗봇 닫기"
              onClick={() => setIsExpanded(false)}
            >
              ✕
            </button>
          </div>
          <p className="flex-1 p-4 text-body text-text-secondary">
            챗봇 위젯은 준비 중입니다.
          </p>
        </div>
      )}

      <button
        type="button"
        aria-label={isExpanded ? "챗봇 닫기" : "챗봇 열기"}
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((prev) => !prev)}
        className="fixed bottom-4 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-2xl text-text-on-brand shadow-lg md:right-6"
      >
        💬
      </button>
    </>
  );
}
