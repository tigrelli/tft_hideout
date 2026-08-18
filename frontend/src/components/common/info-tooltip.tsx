"use client";

import { useState } from "react";

// 정보 아이콘을 hover(데스크톱)·tap(모바일)하면 상세 설명을 레이어 팝업으로
// 보여주는 공용 컴포넌트(comp-detail/item-icon-row.tsx의 hover/tap 패턴 재사용).
// hover·pinned(클릭) 상태를 분리한다 — 클릭 시 브라우저가 클릭 직전에
// mouseenter도 함께 쏘는데, 단일 토글 상태였다면 mouseenter로 이미 열린 걸
// 클릭이 곧바로 다시 닫아버리는 문제가 있다(item-icon-row.tsx와 동일 이슈).
export function InfoTooltip({
  text,
  label = "자세히 보기",
}: {
  text: string;
  label?: string;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const isOpen = isHovered || isPinned;

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={isOpen}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={() => setIsPinned((pinned) => !pinned)}
        onBlur={() => setIsPinned(false)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-caption text-text-tertiary hover:text-text-secondary"
      >
        ⓘ
      </button>
      {isOpen && (
        <span
          role="tooltip"
          // 아이콘이 보통 문장 끝(줄의 오른쪽)에 위치해 left-0으로 펼치면
          // 화면 밖으로 잘린다(2026-08-18 실기기 확인) — 오른쪽 끝을
          // 트리거에 맞추고 왼쪽으로 펼친다. 위(bottom-full)로 펼치면
          // 페이지 상단 근처 사용처에서 뷰포트 위로 잘릴 수 있어 아래
          // (top-full)로 펼친다.
          className="absolute top-full right-0 z-20 mt-2 w-64 max-w-[calc(100vw-2rem)] rounded-control border border-border-default bg-surface-card p-3 text-caption text-text-secondary shadow-md"
        >
          {text}
        </span>
      )}
    </span>
  );
}
