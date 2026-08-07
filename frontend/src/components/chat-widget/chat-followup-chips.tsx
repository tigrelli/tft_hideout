"use client";

// 화면설계서 2.7 SuggestedFollowupChips(visible/hidden). CHAT-11이 답변 직후
// Groq로 생성한 맥락 기반 질문을 SSE `event: followups`로 보내주면 그 목록만
// 그대로 렌더링한다(와이어프레임 예시 "(그 조합에 어울리는 증강체는?)"처럼
// 항상 직전 봇 답변에 종속 — 질문 목록 자체를 고르는 로직은 여기 없음).
// 목록이 비어 있으면 컴포넌트 자체가 hidden 상태로 아무것도 렌더링하지 않는다.
export function ChatFollowupChips({
  questions,
  onSelect,
}: {
  questions: string[];
  onSelect: (question: string) => void;
}) {
  if (questions.length === 0) {
    return null;
  }

  return (
    <div
      aria-label="추천 질문"
      className="flex flex-wrap gap-2 border-t border-border-default p-3"
    >
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onSelect(question)}
          className="cursor-pointer rounded-badge border border-border-input px-2 py-1 text-label text-text-secondary"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
