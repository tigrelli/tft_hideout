"use client";

// 화면설계서 2.7 SuggestedFollowupChips(visible/hidden). 백엔드가 대화 맥락별
// 후속 질문을 생성해주지 않아(CHAT-01~09 어디에도 관련 응답 필드 없음), 의도
// 4분류(glossary.md)를 대표하는 고정 예시 질문을 대화 시작 전에만 노출하는
// 방식으로 구현했다 — PRD/화면설계서 미명시 항목에 대한 가정(PM 확인 필요,
// 화면설계서 2.7의 다른 미확정 항목과 동일한 방식).
const STARTER_QUESTIONS = [
  "지금 메타에서 강한 조합 추천해줘",
  "캐리 챔피언 아이템은 뭘 써야 해?",
  "지금 좋은 증강체 추천해줘",
  "이번 패치 전체적인 메타 알려줘",
];

export function ChatFollowupChips({
  visible,
  onSelect,
}: {
  visible: boolean;
  onSelect: (question: string) => void;
}) {
  if (!visible) {
    return null;
  }

  return (
    <div
      aria-label="추천 질문"
      className="flex flex-wrap gap-2 border-t border-border-default p-3"
    >
      {STARTER_QUESTIONS.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onSelect(question)}
          className="rounded-badge border border-border-input px-2 py-1 text-label text-text-secondary"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
